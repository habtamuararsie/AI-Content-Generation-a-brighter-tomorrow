"""Stage 6: Radio-cut rendering and full FFmpeg dual-aspect (16:9 & 9:16) assembly."""

from __future__ import annotations

import shutil
import struct
import subprocess
import time
import wave
from pathlib import Path
from typing import Any

from pipeline.config import PipelineConfig
from pipeline.logger import RunLogEntry, append_run_log
from pipeline.providers.video_adapter import render_ken_burns_clip
from pipeline.retry import NonRetryableError
from pipeline.stage4_audio import AudioStageOutput


def _read_pcm_mono_24k(wav_path: Path) -> list[int]:
    """Read a 16-bit PCM WAV file into integer samples (resampling-free for 24kHz mono)."""
    with wave.open(str(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    if width != 2:
        raise NonRetryableError(f"Expected 16-bit WAV at {wav_path}, got sample width {width}.")
    samples = list(struct.unpack(f"<{len(raw) // 2}h", raw))
    if channels == 1:
        return samples
    return samples[::channels]


def mix_radio_cut_wav(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    audio_out: AudioStageOutput,
) -> Path:
    """Mix timeline narration WAVs and ducked temp music into one playable WAV in pure Python."""
    sample_rate = 24000
    total_sec = sum(t["effective_shot_duration_sec"] for t in audio_out.shot_timings) + float(
        storyboard["end_card"]["duration_sec"]
    )
    total_samples = max(1, int(round(total_sec * sample_rate)))
    mix_buf = [0] * total_samples

    # Lay down music bed with gentle ducking under spoken windows
    music_samples = _read_pcm_mono_24k(audio_out.music_result.output_path)
    active_speech = [False] * total_samples
    for timing in audio_out.shot_timings:
        s_idx = max(0, int(round(timing["narration_start_sec"] * sample_rate)))
        e_idx = min(total_samples, int(round(timing["narration_end_sec"] * sample_rate)))
        for idx in range(s_idx, e_idx):
            active_speech[idx] = True

    if music_samples:
        cur_gain = 0.55
        step = 0.33 / max(1, int(0.12 * sample_rate))
        for i in range(total_samples):
            target = 0.22 if active_speech[i] else 0.55
            if cur_gain > target:
                cur_gain = max(target, cur_gain - step)
            elif cur_gain < target:
                cur_gain = min(target, cur_gain + step)
            mix_buf[i] += int(music_samples[i % len(music_samples)] * cur_gain)

    # Layer narration clips at their exact scheduled start times
    for timing in audio_out.shot_timings:
        shot_id = timing["shot_id"]
        wav_path = audio_out.narration_paths[shot_id]
        nar_samples = _read_pcm_mono_24k(wav_path)
        start_idx = int(round(timing["narration_start_sec"] * sample_rate))
        for offset, val in enumerate(nar_samples):
            pos = start_idx + offset
            if pos >= total_samples:
                break
            mix_buf[pos] += val

    out_wav = config.exports_dir / "radio_cut_mix.wav"
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        clamped = [max(-32767, min(32767, s)) for s in mix_buf]
        wf.writeframes(struct.pack(f"<{len(clamped)}h", *clamped))

    return out_wav


def _run_ffmpeg(ffmpeg_bin: str, args: list[str]) -> None:
    if shutil.which(ffmpeg_bin) is None:
        raise NonRetryableError(
            f"FFmpeg binary '{ffmpeg_bin}' was not found on PATH. "
            "Install FFmpeg (Windows: `winget install Gyan.FFmpeg`; Colab/Linux: `apt-get install -y ffmpeg`)."
        )
    proc = subprocess.run([ffmpeg_bin, "-y", *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise NonRetryableError(f"FFmpeg command failed:\n{proc.stderr[-800:]}")


def _escape_ffmpeg_sub_path(path: Path) -> str:
    """Escape path for FFmpeg `subtitles=` filter across Windows and POSIX."""
    resolved = str(path.resolve()).replace("\\", "/")
    return resolved.replace(":", "\\:")


def _escape_drawtext(value: str) -> str:
    """Escape characters special to FFmpeg drawtext filter arguments."""
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _resolve_drawtext_font_arg() -> str:
    """Return an explicit `fontfile=...:` option for drawtext when a system font exists."""
    candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for font_path in candidates:
        if font_path.exists():
            escaped = str(font_path).replace("\\", "/").replace(":", "\\:")
            return f"fontfile='{escaped}':"
    return ""


def render_end_card_clip(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    width: int,
    height: int,
    out_path: Path,
) -> Path:
    """Render a clean 3-second visible AI disclosure end card with FFmpeg."""
    end_card = storyboard["end_card"]
    duration = float(end_card["duration_sec"])
    title = _escape_drawtext(end_card["title"])
    subtitle = _escape_drawtext(end_card["subtitle"])

    # Wrap disclosure onto two clean lines so vertical 9:16 never clips horizontally
    raw_disc = end_card["ai_disclosure_text"]
    words = raw_disc.split()
    mid = max(1, len(words) // 2)
    disc_line1 = _escape_drawtext(" ".join(words[:mid]))
    disc_line2 = _escape_drawtext(" ".join(words[mid:]))

    title_size = max(40, width // 22)
    sub_size = max(24, width // 38)
    disc_size = max(18, width // 54)
    font_arg = _resolve_drawtext_font_arg()

    vf = (
        f"drawtext={font_arg}text='{title}':fontcolor=white:fontsize={title_size}:"
        f"x=(w-text_w)/2:y=h*0.36,"
        f"drawtext={font_arg}text='{subtitle}':fontcolor=#E6C77D:fontsize={sub_size}:"
        f"x=(w-text_w)/2:y=h*0.46,"
        f"drawtext={font_arg}text='{disc_line1}':fontcolor=#CCCCCC:fontsize={disc_size}:"
        f"x=(w-text_w)/2:y=h*0.62,"
        f"drawtext={font_arg}text='{disc_line2}':fontcolor=#CCCCCC:fontsize={disc_size}:"
        f"x=(w-text_w)/2:y=h*0.66,format=yuv420p"
    )
    _run_ffmpeg(
        config.ffmpeg_bin,
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=#101418:s={width}x{height}:d={duration:.3f}:r=24",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ],
    )
    return out_path


def run_stage6_radio_cut(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    audio_out: AudioStageOutput,
    run_id: str,
) -> dict[str, Path | None]:
    """Build playable radio-cut audio WAV and (when FFmpeg is installed) black-screen MP4."""
    config.ensure_directories()
    t0 = time.perf_counter()
    mix_wav = mix_radio_cut_wav(config, storyboard, audio_out)
    mp4_path: Path | None = None

    if shutil.which(config.ffmpeg_bin) is not None:
        shots_dur = sum(t["effective_shot_duration_sec"] for t in audio_out.shot_timings)
        end_dur = float(storyboard["end_card"]["duration_sec"])
        total_dur = shots_dur + end_dur
        candidate_mp4 = config.exports_dir / "radio_cut.mp4"
        sub_escaped = _escape_ffmpeg_sub_path(audio_out.srt_path)
        _run_ffmpeg(
            config.ffmpeg_bin,
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s=1280x720:d={total_dur:.3f}:r=24",
                "-i",
                str(mix_wav),
                "-vf",
                f"subtitles='{sub_escaped}',format=yuv420p",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(candidate_mp4),
            ],
        )
        mp4_path = candidate_mp4

    elapsed = round(time.perf_counter() - t0, 3)
    append_run_log(
        config.logs_path,
        RunLogEntry(
            run_id=run_id,
            stage="stage6_radio_cut",
            shot_id="all",
            provider="local_radio_cut",
            model="pure_python_wav_and_ffmpeg",
            status="success",
            latency_sec=elapsed,
            metadata={
                "mix_wav": str(mix_wav),
                "radio_cut_mp4": str(mp4_path) if mp4_path else None,
            },
        ),
    )
    return {"mix_wav": mix_wav, "radio_cut_mp4": mp4_path}


def _build_ducked_audio_master(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    audio_out: AudioStageOutput,
    out_wav: Path,
) -> Path:
    """Mix narration + music with FFmpeg sidechaincompress ducking and -14 LUFS loudnorm."""
    nar_concat_txt = config.outputs_dir / "tmp" / "narration_padded.txt"
    nar_concat_txt.parent.mkdir(parents=True, exist_ok=True)
    padded_clips: list[Path] = []

    for idx, timing in enumerate(audio_out.shot_timings):
        shot_id = timing["shot_id"]
        src_wav = audio_out.narration_paths[shot_id]
        padded_wav = config.outputs_dir / "tmp" / f"{shot_id}_padded.wav"
        dur = float(timing["effective_shot_duration_sec"])
        lead_ms = int(round((timing["narration_start_sec"] - timing["shot_start_sec"]) * 1000))
        _run_ffmpeg(
            config.ffmpeg_bin,
            [
                "-i",
                str(src_wav),
                "-af",
                f"adelay={lead_ms}|{lead_ms},apad=whole_dur={dur:.3f}",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(padded_wav),
            ],
        )
        padded_clips.append(padded_wav)

    # Append silence for the 3s end card
    end_silence = config.outputs_dir / "tmp" / "end_card_silence.wav"
    end_dur = float(storyboard["end_card"]["duration_sec"])
    _run_ffmpeg(
        config.ffmpeg_bin,
        [
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=48000:cl=stereo:d={end_dur:.3f}",
            str(end_silence),
        ],
    )
    padded_clips.append(end_silence)

    lines = [f"file '{p.resolve().as_posix()}'" for p in padded_clips]
    nar_concat_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    nar_full = config.outputs_dir / "tmp" / "narration_full.wav"
    _run_ffmpeg(
        config.ffmpeg_bin,
        ["-f", "concat", "-safe", "0", "-i", str(nar_concat_txt), "-c", "copy", str(nar_full)],
    )

    total_dur = sum(t["effective_shot_duration_sec"] for t in audio_out.shot_timings) + end_dur
    # Carve a subtle vocal presence pocket on music, duck tightly with fast attack, then normalize to -14 LUFS / -1 dBTP
    _run_ffmpeg(
        config.ffmpeg_bin,
        [
            "-i",
            str(nar_full),
            "-stream_loop",
            "-1",
            "-i",
            str(audio_out.music_result.output_path),
            "-filter_complex",
            (
                f"[1:a]atrim=0:{total_dur:.3f},aresample=48000,"
                f"aformat=channel_layouts=stereo,"
                f"equalizer=f=1800:t=q:w=0.9:g=-3.0,volume=0.35[mus];"
                f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[voice][sc];"
                f"[mus][sc]sidechaincompress=threshold=0.015:ratio=7:attack=45:release=650[ducked];"
                f"[voice][ducked]amix=inputs=2:duration=first:normalize=0,"
                f"loudnorm=I=-14:TP=-1:LRA=9[outa]"
            ),
            "-map",
            "[outa]",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-t",
            f"{total_dur:.3f}",
            str(out_wav),
        ],
    )
    return out_wav


def run_stage6_assemble(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    audio_out: AudioStageOutput,
    clip_paths: dict[str, Path],
    run_id: str,
    keyframe_paths: dict[str, Path] | None = None,
) -> dict[str, Path]:
    """Assemble final 16:9 and 9:16 MP4 films with ducked score, subtitles, and 3s AI end card."""
    config.ensure_directories()
    if shutil.which(config.ffmpeg_bin) is None:
        raise NonRetryableError(
            f"FFmpeg binary '{config.ffmpeg_bin}' not found on PATH. Cannot assemble final MP4s."
        )

    t0 = time.perf_counter()
    master_audio = _build_ducked_audio_master(
        config, storyboard, audio_out, config.outputs_dir / "tmp" / "master_audio.wav"
    )
    sub_escaped = _escape_ffmpeg_sub_path(audio_out.srt_path)

    exports: dict[str, Path] = {}
    targets = {
        "16x9": (1920, 1080, config.exports_dir / "a_brighter_tomorrow_16x9.mp4"),
        "9x16": (1080, 1920, config.exports_dir / "a_brighter_tomorrow_9x16.mp4"),
    }

    for ratio_key, (w, h, final_out) in targets.items():
        scaled_parts: list[Path] = []
        for idx, timing in enumerate(audio_out.shot_timings):
            shot_id = timing["shot_id"]
            src_clip = clip_paths[shot_id]
            dur = float(timing["effective_shot_duration_sec"])
            part_out = config.outputs_dir / "tmp" / f"{shot_id}_{ratio_key}.mp4"

            # Render native 9:16 Ken Burns directly from original keyframe to avoid double-cropping
            if (
                ratio_key == "9x16"
                and config.video_provider == "ken_burns"
                and keyframe_paths
                and shot_id in keyframe_paths
                and keyframe_paths[shot_id].exists()
            ):
                render_ken_burns_clip(
                    ffmpeg_bin=config.ffmpeg_bin,
                    keyframe_path=keyframe_paths[shot_id],
                    output_path=part_out,
                    duration_sec=dur,
                    shot_index=idx,
                    fps=24,
                    width=w,
                    height=h,
                    shot_id=shot_id,
                )
                scaled_parts.append(part_out)
                continue

            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:(iw-ow)/2:(ih-oh)*0.35,fps=24,format=yuv420p"
            )
            _run_ffmpeg(
                config.ffmpeg_bin,
                [
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(src_clip),
                    "-t",
                    f"{dur:.3f}",
                    "-vf",
                    vf,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(part_out),
                ],
            )
            scaled_parts.append(part_out)

        end_clip = render_end_card_clip(
            config,
            storyboard,
            width=w,
            height=h,
            out_path=config.outputs_dir / "tmp" / f"end_card_{ratio_key}.mp4",
        )
        scaled_parts.append(end_clip)

        concat_txt = config.outputs_dir / "tmp" / f"video_concat_{ratio_key}.txt"
        concat_txt.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in scaled_parts) + "\n",
            encoding="utf-8",
        )
        silent_video = config.outputs_dir / "tmp" / f"video_silent_{ratio_key}.mp4"
        _run_ffmpeg(
            config.ffmpeg_bin,
            ["-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(silent_video)],
        )

        if ratio_key == "9x16":
            sub_style = (
                "FontName=Arial,FontSize=6,Alignment=2,BorderStyle=1,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1.0,"
                "Shadow=0.5,MarginL=12,MarginR=12,MarginV=24"
            )
        else:
            sub_style = (
                "FontName=Arial,FontSize=14,Alignment=2,BorderStyle=1,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1.5,"
                "Shadow=1,MarginL=24,MarginR=24,MarginV=20"
            )
        _run_ffmpeg(
            config.ffmpeg_bin,
            [
                "-i",
                str(silent_video),
                "-i",
                str(master_audio),
                "-vf",
                f"subtitles='{sub_escaped}':force_style='{sub_style}',format=yuv420p",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-b:a",
                "192k",
                "-shortest",
                str(final_out),
            ],
        )
        exports[ratio_key] = final_out

    elapsed = round(time.perf_counter() - t0, 3)
    append_run_log(
        config.logs_path,
        RunLogEntry(
            run_id=run_id,
            stage="stage6_assemble",
            shot_id="all",
            provider="ffmpeg",
            model="libx264_aac_loudnorm",
            status="success",
            latency_sec=elapsed,
            metadata={k: str(v) for k, v in exports.items()},
        ),
    )
    return exports
