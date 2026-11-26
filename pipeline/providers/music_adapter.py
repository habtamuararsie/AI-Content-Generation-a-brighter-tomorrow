"""Music provider adapters (ACE-Step 1.5 precomputed WAV + offline placeholder temp track)."""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

from typing import Any

from pipeline.config import PipelineConfig
from pipeline.providers.gemini_client import measure_wav_duration_sec
from pipeline.providers.local_audio import generate_local_original_score
from pipeline.retry import NonRetryableError

SUPPORTED_MUSIC_PROVIDERS = ("ace_step_15", "local_score", "placeholder_temp")


@dataclass(frozen=True)
class MusicTrackResult:
    """Result metadata for the resolved score or radio-cut temp track."""

    output_path: Path
    provider: str
    model: str
    duration_sec: float
    is_placeholder: bool


def generate_placeholder_temp_track(output_path: Path, duration_sec: float) -> MusicTrackResult:
    """Synthesize a soft D-major harmonic bed WAV for offline radio-cut listening."""
    sample_rate = 24000
    num_samples = max(1, int(round(duration_sec * sample_rate)))
    fade_samples = min(int(1.0 * sample_rate), num_samples // 4)
    # D major triad harmonics (D3, A3, F#4) at very gentle ambient level
    freqs = (146.83, 220.00, 369.99)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            env = 0.035
            if fade_samples > 0:
                if i < fade_samples:
                    env *= i / fade_samples
                elif i > num_samples - fade_samples:
                    env *= (num_samples - i) / fade_samples
            sample = sum(math.sin(2.0 * math.pi * f * t) for f in freqs) / len(freqs)
            frames.extend(struct.pack("<h", int(32767 * env * sample)))
        wf.writeframes(bytes(frames))

    return MusicTrackResult(
        output_path=output_path,
        provider="placeholder_temp",
        model="offline_d_major_pad",
        duration_sec=measure_wav_duration_sec(output_path),
        is_placeholder=True,
    )


def resolve_music_track(
    config: PipelineConfig,
    target_duration_sec: float,
    music_cfg: dict[str, Any] | None = None,
    shot_timings: list[dict[str, Any]] | None = None,
) -> MusicTrackResult:
    """Resolve an ACE-Step 1.5 soundtrack, procedural original local score, or temp track."""
    provider = config.music_provider
    if provider not in SUPPORTED_MUSIC_PROVIDERS:
        raise NonRetryableError(
            f"Unsupported MUSIC_PROVIDER '{provider}'. Choose one of: {SUPPORTED_MUSIC_PROVIDERS}."
        )

    if provider == "ace_step_15":
        candidate_wav = config.music_dir / "soundtrack_ace_step.wav"
        if not candidate_wav.exists() or candidate_wav.stat().st_size == 0:
            raise NonRetryableError(
                f"ACE-Step 1.5 soundtrack not found at {candidate_wav}. "
                "Test a short sample in Google Colab first, then place the chosen track there, "
                "or use MUSIC_PROVIDER=local_score (or placeholder_temp for radio cut)."
            )
        return MusicTrackResult(
            output_path=candidate_wav,
            provider="ace_step_15",
            model="ACE-Step/Ace-Step1.5",
            duration_sec=measure_wav_duration_sec(candidate_wav),
            is_placeholder=False,
        )

    if provider == "local_score":
        score_path = config.music_dir / "original_score_local.wav"
        generate_local_original_score(
            output_path=score_path,
            duration_sec=target_duration_sec,
            music_cfg=music_cfg,
            shot_timings=shot_timings,
        )
        return MusicTrackResult(
            output_path=score_path,
            provider="local_score",
            model="procedural_pentatonic_heritage_82bpm_v2",
            duration_sec=measure_wav_duration_sec(score_path),
            is_placeholder=False,
        )

    temp_path = config.music_dir / "temp_track_placeholder.wav"
    return generate_placeholder_temp_track(temp_path, target_duration_sec)
