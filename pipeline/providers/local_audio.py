"""Free local offline narration (Windows TTS / POSIX fallback) and procedural score synthesis."""

from __future__ import annotations

import base64
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

from pipeline.config import PipelineConfig
from pipeline.providers.gemini_client import (
    NarrationResult,
    generate_placeholder_narration,
    measure_wav_duration_sec,
)
from pipeline.retry import NonRetryableError


def _build_winrt_tts_ps_script(text_file: Path, wav_out: Path, speaking_rate: float = 0.96) -> str:
    """Return PowerShell script using Windows.Media.SpeechSynthesis (prefers George)."""
    tf = str(text_file.resolve()).replace("'", "''")
    wo = str(wav_out.resolve()).replace("'", "''")
    return f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime] | Out-Null
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
}})[0]
function Await($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}}
$text = [System.IO.File]::ReadAllText('{tf}', [System.Text.Encoding]::UTF8)
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object {{ $_.DisplayName -like '*George*' }} | Select-Object -First 1
if (-not $voice) {{
    $voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object {{ $_.Language -like 'en*' }} | Select-Object -First 1
}}
if ($voice) {{ $synth.Voice = $voice }}
$synth.Options.SpeakingRate = {speaking_rate:.2f}
$stream = Await ($synth.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
$len = [uint32]$stream.Size
Await ($reader.LoadAsync($len)) ([uint32]) | Out-Null
$bytes = New-Object byte[] $len
$reader.ReadBytes($bytes)
[System.IO.File]::WriteAllBytes('{wo}', $bytes)
$voiceName = if ($synth.Voice) {{ $synth.Voice.DisplayName }} else {{ 'default' }}
$synth.Dispose()
Write-Output $voiceName
""".strip()


def _build_sapi5_tts_ps_script(text_file: Path, wav_out: Path, rate: int = -1) -> str:
    """Return PowerShell script using System.Speech SAPI5 offline synthesis."""
    tf = str(text_file.resolve()).replace("'", "''")
    wo = str(wav_out.resolve()).replace("'", "''")
    return f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText('{tf}', [System.Text.Encoding]::UTF8)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $synth.GetInstalledVoices() | Where-Object {{ $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en*' }} | Select-Object -First 1
if ($voice) {{ $synth.SelectVoice($voice.VoiceInfo.Name) }}
$synth.Rate = {rate}
$synth.SetOutputToWaveFile('{wo}')
$synth.Speak($text)
$name = $synth.Voice.Name
$synth.Dispose()
Write-Output $name
""".strip()


def _run_encoded_powershell(script: str) -> tuple[bool, str]:
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0, (proc.stdout or proc.stderr).strip()


def _normalize_tts_wav(ffmpeg_bin: str, raw_wav: Path, final_wav: Path) -> None:
    """Trim dead silence, remove boxy resonance, boost vocal clarity, and write 24kHz PCM."""
    final_wav.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which(ffmpeg_bin) is None:
        shutil.copyfile(raw_wav, final_wav)
        return

    af = (
        "silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB,"
        "areverse,"
        "silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB,"
        "areverse,"
        "highpass=f=105,"
        "equalizer=f=250:t=q:w=1.4:g=-2.8,"
        "equalizer=f=3200:t=q:w=1.2:g=2.6,"
        "acompressor=threshold=-20dB:ratio=2.5:attack=12:release=140:makeup=2,"
        "alimiter=limit=-1.5dB"
    )
    proc = subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            str(raw_wav),
            "-af",
            af,
            "-ar",
            "24000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(final_wav),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not final_wav.exists() or final_wav.stat().st_size == 0:
        raise NonRetryableError(f"FFmpeg TTS normalization failed: {proc.stderr[-500:]}")


def generate_local_tts_narration(
    config: PipelineConfig,
    text: str,
    style_instruction: str,
    output_path: Path,
    shot_index: int = 0,
) -> NarrationResult:
    """Generate offline spoken narration using OS-native free TTS engines."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        text_file = tmp_dir / "line.txt"
        raw_wav = tmp_dir / "raw_tts.wav"
        text_file.write_text(text.strip(), encoding="utf-8")

        model_used: str | None = None
        if sys.platform == "win32":
            ok, out = _run_encoded_powershell(_build_winrt_tts_ps_script(text_file, raw_wav))
            if ok and raw_wav.exists() and raw_wav.stat().st_size > 1024:
                model_used = f"windows_winrt:{out.splitlines()[-1].strip() or 'George'}"
            else:
                ok_sapi, out_sapi = _run_encoded_powershell(
                    _build_sapi5_tts_ps_script(text_file, raw_wav)
                )
                if ok_sapi and raw_wav.exists() and raw_wav.stat().st_size > 1024:
                    model_used = f"windows_sapi5:{out_sapi.splitlines()[-1].strip() or 'default'}"
        elif shutil.which("espeak-ng"):
            proc = subprocess.run(
                ["espeak-ng", "-s", "145", "-w", str(raw_wav), text.strip()],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and raw_wav.exists() and raw_wav.stat().st_size > 1024:
                model_used = "espeak_ng_local"
        elif shutil.which("espeak"):
            proc = subprocess.run(
                ["espeak", "-s", "145", "-w", str(raw_wav), text.strip()],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and raw_wav.exists() and raw_wav.stat().st_size > 1024:
                model_used = "espeak_local"
        elif shutil.which("say"):
            aiff_tmp = tmp_dir / "raw_tts.aiff"
            proc = subprocess.run(
                ["say", "-r", "165", "-o", str(aiff_tmp), text.strip()],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and aiff_tmp.exists():
                raw_wav = aiff_tmp
                model_used = "macos_say_local"

        if model_used is None:
            # Graceful fallback for minimal Linux/CI environments with no OS speech engine installed
            return generate_placeholder_narration(text=text, output_path=output_path, shot_index=shot_index)

        _normalize_tts_wav(config.ffmpeg_bin, raw_wav, output_path)

    dur = measure_wav_duration_sec(output_path)
    return NarrationResult(
        output_path=output_path,
        provider="local_tts",
        model=model_used,
        duration_sec=dur,
        is_placeholder=False,
        estimated_cost_usd=0.0,
    )


def _midi_to_hz(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _add_karplus_pluck(
    buf: list[float],
    sample_rate: int,
    start_sec: float,
    freq_hz: float,
    duration_sec: float,
    gain: float,
    rng: random.Random,
    brightness: float = 0.45,
) -> None:
    """Synthesize a dry, warm krar-inspired plucked string note via Karplus-Strong."""
    start_idx = int(round(start_sec * sample_rate))
    n_len = int(round(duration_sec * sample_rate))
    if start_idx >= len(buf) or n_len <= 4:
        return

    period = max(4, int(round(sample_rate / freq_hz)))
    ring = [rng.uniform(-1.0, 1.0) for _ in range(period)]
    for i in range(period):
        ring[i] = 0.5 * ring[i] + 0.5 * ring[(i - 1) % period]

    end_idx = min(len(buf), start_idx + n_len)
    # Shorter dry decay minimizes lingering room/ring bleed under narration
    decay = 0.9915
    attack_len = min(int(0.010 * sample_rate), n_len // 4)
    release_len = min(int(0.14 * sample_rate), n_len // 3)
    prev_out = 0.0

    for offset in range(end_idx - start_idx):
        p_idx = offset % period
        nxt = (p_idx + 1) % period
        val = ring[p_idx]
        filtered = decay * (brightness * val + (1.0 - brightness) * ring[nxt])
        ring[p_idx] = filtered
        out = 0.60 * val + 0.40 * prev_out
        prev_out = out

        env = 1.0
        if attack_len > 0 and offset < attack_len:
            env *= offset / attack_len
        rem = (end_idx - start_idx) - offset
        if release_len > 0 and rem < release_len:
            env *= rem / release_len
        buf[start_idx + offset] += gain * env * out


def _add_flute_phrase_note(
    buf: list[float],
    sample_rate: int,
    start_sec: float,
    freq_hz: float,
    duration_sec: float,
    gain: float,
    rng: random.Random,
    grace_from_hz: float | None = None,
) -> None:
    """Synthesize a soft washint-inspired airy bamboo-flute tone with gentle grace slide."""
    start_idx = int(round(start_sec * sample_rate))
    n_len = int(round(duration_sec * sample_rate))
    if start_idx >= len(buf) or n_len <= 8:
        return

    end_idx = min(len(buf), start_idx + n_len)
    atk = max(0.06, min(0.16, duration_sec * 0.22))
    rel = max(0.08, min(0.22, duration_sec * 0.28))
    phase = 0.0
    breath_lp = 0.0

    for offset in range(end_idx - start_idx):
        t = offset / sample_rate
        t_rem = (end_idx - start_idx - offset) / sample_rate
        env = min(1.0, t / atk) * min(1.0, t_rem / rel)

        cur_f = freq_hz
        if grace_from_hz is not None and t < 0.08:
            alpha = t / 0.08
            cur_f = grace_from_hz * (1.0 - alpha) + freq_hz * alpha
        vib = 1.0 + 0.004 * math.sin(2.0 * math.pi * 4.8 * t) * min(1.0, t / 0.25)
        phase += 2.0 * math.pi * cur_f * vib / sample_rate

        breath_lp = 0.85 * breath_lp + 0.15 * rng.uniform(-1.0, 1.0)
        tone = 0.84 * math.sin(phase) + 0.12 * math.sin(2.0 * phase) + 0.08 * breath_lp
        buf[start_idx + offset] += gain * env * tone


def _add_drum_pulse(
    buf: list[float],
    sample_rate: int,
    start_sec: float,
    gain: float,
    accent: bool = True,
) -> None:
    """Synthesize a dry, muted kebero-inspired skin thump with zero reverb tail."""
    start_idx = int(round(start_sec * sample_rate))
    n_len = int(round(0.11 * sample_rate))
    end_idx = min(len(buf), start_idx + n_len)
    if end_idx <= start_idx:
        return

    f_start = 108.0 if accent else 148.0
    f_end = 56.0 if accent else 84.0
    phase = 0.0
    for offset in range(end_idx - start_idx):
        t = offset / sample_rate
        f = f_end + (f_start - f_end) * math.exp(-t / 0.022)
        phase += 2.0 * math.pi * f / sample_rate
        env = min(1.0, t / 0.004) * math.exp(-t / (0.036 if accent else 0.024))
        buf[start_idx + offset] += gain * env * math.sin(phase)


def _add_low_drone(
    buf: list[float],
    sample_rate: int,
    start_sec: float,
    duration_sec: float,
    midi_notes: tuple[int, ...],
    gain: float,
) -> None:
    """Add a quiet, dry low fifth drone (begena-inspired open bass support) without wash."""
    start_idx = max(0, int(round(start_sec * sample_rate)))
    n_len = int(round(duration_sec * sample_rate))
    end_idx = min(len(buf), start_idx + n_len)
    if end_idx <= start_idx:
        return

    fade_s = min(0.45, duration_sec * 0.25)
    freqs = [_midi_to_hz(m) for m in midi_notes]
    inv_n = 1.0 / max(1, len(freqs))

    for offset in range(end_idx - start_idx):
        t = offset / sample_rate
        t_rem = (end_idx - start_idx - offset) / sample_rate
        env = min(1.0, t / fade_s) * min(1.0, t_rem / fade_s)
        acc = sum(0.82 * math.sin(2.0 * math.pi * f * t) + 0.18 * math.sin(4.0 * math.pi * f * t) for f in freqs)
        buf[start_idx + offset] += gain * env * inv_n * acc


def generate_local_original_score(
    output_path: Path,
    duration_sec: float,
    music_cfg: dict[str, Any] | None = None,
    shot_timings: list[dict[str, Any]] | None = None,
) -> Path:
    """Compose an original dry 82 BPM pentatonic heritage-inspired score synced to shot cues."""
    sample_rate = 24000
    total_samples = max(1, int(round(duration_sec * sample_rate)))
    buf = [0.0] * total_samples
    rng = random.Random(2026)

    tempo_bpm = float((music_cfg or {}).get("tempo_bpm", 82))
    beat_sec = 60.0 / max(40.0, min(180.0, tempo_bpm))

    # Original pentatonic motifs inspired by Ethiopian qenet scale intervals (D tonal center):
    # Tizita-major pentatonic (D4=62, E4=64, F#4=66, A4=69, B4=71, D5=74, E5=76)
    tizita_major_roots = [62, 66, 69, 71, 69, 66, 64, 62]
    tizita_major_lift = [69, 71, 74, 71, 69, 66, 64, 62]
    # Tizita-minor-style reflective pentatonic for Shot 7 (D4=62, E4=64, F4=65, A4=69, Bb4=70)
    tizita_minor_motif = [62, 65, 69, 70, 69, 65, 64, 62]

    if shot_timings and len(shot_timings) >= 8:
        spans = [
            (float(item["shot_start_sec"]), float(item["shot_end_sec"]), item["shot_id"])
            for item in shot_timings
        ]
    else:
        step = duration_sec / 10.0
        spans = [(i * step, (i + 1) * step, f"shot_{i + 1:02d}") for i in range(10)]

    for s_start, s_end, sid in spans:
        span_len = max(1.0, s_end - s_start)
        shot_num = int(sid.split("_")[1]) if "_" in sid and sid.split("_")[1].isdigit() else 1

        # 1. Quiet open-fifth bass drone (D2=38, A2=45), shifting to F2=41/C3=48 on Shot 7 reflection
        drone_notes = (41, 48) if shot_num == 7 else (38, 45)
        drone_gain = 0.08 if shot_num in (1, 2, 7, 10) else 0.095
        _add_low_drone(buf, sample_rate, s_start, span_len, drone_notes, gain=drone_gain)

        # 2. Dry krar-inspired pentatonic plucked ostinato (no muddy ring overlap)
        if shot_num in (1, 2):
            motif = tizita_major_roots
            step_beats = 1.0
            pluck_gain = 0.16
        elif shot_num in (3, 4, 5, 6):
            motif = tizita_major_lift
            step_beats = 0.5 if shot_num in (3, 6) else 1.0
            pluck_gain = 0.15
        elif shot_num == 7:
            motif = tizita_minor_motif
            step_beats = 1.5
            pluck_gain = 0.12
        elif shot_num in (8, 9):
            motif = tizita_major_lift
            step_beats = 0.5
            pluck_gain = 0.17
        else:
            motif = tizita_major_roots
            step_beats = 1.0
            pluck_gain = 0.14

        t_cur = s_start + 0.10
        idx_note = 0
        while t_cur < s_end - 0.30:
            midi = motif[idx_note % len(motif)]
            _add_karplus_pluck(
                buf,
                sample_rate,
                start_sec=t_cur,
                freq_hz=_midi_to_hz(midi),
                duration_sec=min(1.05, beat_sec * 1.4),
                gain=pluck_gain * (1.0 if idx_note % 2 == 0 else 0.72),
                rng=rng,
                brightness=0.42 if shot_num == 7 else 0.48,
            )
            t_cur += beat_sec * step_beats
            idx_note += 1

        # 3. Soft airy washint-inspired flute motif in opening roots (1-2) and triumphant return (9-10)
        if shot_num in (1, 2, 9, 10):
            flute_notes = (
                (69, 71, 74, 71) if shot_num in (1, 2) else (74, 76, 74, 69)
            )
            f_step = span_len / 4.2
            for f_idx, f_midi in enumerate(flute_notes):
                prev_hz = _midi_to_hz(flute_notes[max(0, f_idx - 1)]) if f_idx > 0 else None
                _add_flute_phrase_note(
                    buf,
                    sample_rate,
                    start_sec=s_start + 0.35 + f_idx * f_step,
                    freq_hz=_midi_to_hz(f_midi),
                    duration_sec=min(1.4, f_step * 0.82),
                    gain=0.095 if shot_num in (1, 2) else 0.115,
                    rng=rng,
                    grace_from_hz=prev_hz,
                )

        # 4. Subtle muted kebero-inspired heartbeat pulse during active movement & teamwork shots
        if shot_num in (3, 6, 8, 9):
            p_cur = s_start + 0.10
            p_idx = 0
            while p_cur < s_end - 0.25:
                _add_drum_pulse(
                    buf,
                    sample_rate,
                    start_sec=p_cur,
                    gain=0.14 if p_idx % 3 == 0 else 0.08,
                    accent=(p_idx % 3 == 0),
                )
                p_cur += beat_sec * (1.0 if shot_num in (3, 6) else 0.6667)
                p_idx += 1

    # Gentle D-A pentatonic final cadence across end card with clean fade-out
    tail_start = spans[-1][1] - 0.2
    if tail_start < duration_sec:
        rem_dur = max(0.8, duration_sec - tail_start)
        _add_low_drone(buf, sample_rate, tail_start, rem_dur, (38, 45, 50), gain=0.09)
        _add_karplus_pluck(buf, sample_rate, tail_start + 0.1, _midi_to_hz(62), min(1.4, rem_dur), 0.14, rng)
        _add_karplus_pluck(buf, sample_rate, tail_start + 0.45, _midi_to_hz(69), min(1.4, rem_dur), 0.12, rng)
        _add_flute_phrase_note(buf, sample_rate, tail_start + 0.3, _midi_to_hz(74), max(0.6, rem_dur - 0.5), 0.08, rng)

    # Master fade-in (0.6s), fade-out (1.8s), and clean -6 dBFS peak normalization
    fade_in_n = min(int(0.6 * sample_rate), total_samples // 4)
    fade_out_n = min(int(1.8 * sample_rate), total_samples // 3)
    for i in range(fade_in_n):
        buf[i] *= i / float(fade_in_n)
    for i in range(fade_out_n):
        idx = total_samples - 1 - i
        if idx >= 0:
            buf[idx] *= i / float(fade_out_n)

    peak = max((abs(x) for x in buf), default=1.0)
    scale = (0.48 / peak) if peak > 1e-6 else 1.0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcm = [max(-32767, min(32767, int(round(x * scale * 32767)))) for x in buf]
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(pcm)}h", *pcm))

    return output_path
