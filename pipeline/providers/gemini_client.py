"""Gemini API & Placeholder narration providers.

By default (and whenever `allow_paid_api` is False), the pipeline uses
`PlaceholderNarrationProvider` so you can build and review the radio cut
offline with zero API calls or cost.
"""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import PipelineConfig
from pipeline.retry import NonRetryableError, classify_http_status, run_with_retry


@dataclass(frozen=True)
class NarrationResult:
    """Output produced by any narration provider."""

    output_path: Path
    provider: str
    model: str
    duration_sec: float
    is_placeholder: bool
    estimated_cost_usd: float


def write_soft_cue_wav(output_path: Path, duration_sec: float, freq_hz: float = 220.0) -> None:
    """Write a gentle low-volume WAV cue for offline radio-cut timing tests."""
    sample_rate = 24000
    num_samples = max(1, int(round(duration_sec * sample_rate)))
    fade_samples = min(int(0.08 * sample_rate), num_samples // 4)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            # Subtle pulsing warm tone so reviewers can hear shot boundaries clearly
            env = 0.06
            if fade_samples > 0:
                if i < fade_samples:
                    env *= i / fade_samples
                elif i > num_samples - fade_samples:
                    env *= (num_samples - i) / fade_samples
            val = int(32767 * env * math.sin(2.0 * math.pi * freq_hz * t))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))


def measure_wav_duration_sec(wav_path: Path) -> float:
    """Measure exact duration of a PCM WAV file in seconds."""
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return round(frames / float(rate), 3) if rate > 0 else 0.0


def estimate_spoken_duration_sec(text: str, words_per_sec: float = 2.2) -> float:
    """Estimate spoken English duration from word count for placeholder audio."""
    words = len(text.split())
    return round(max(2.5, words / words_per_sec), 3)


def generate_placeholder_narration(
    text: str,
    output_path: Path,
    shot_index: int = 0,
) -> NarrationResult:
    """Create a clearly labeled placeholder WAV matching estimated spoken duration."""
    duration = estimate_spoken_duration_sec(text)
    freq = 220.0 + (shot_index % 5) * 22.0
    write_soft_cue_wav(output_path, duration, freq_hz=freq)
    actual_dur = measure_wav_duration_sec(output_path)
    return NarrationResult(
        output_path=output_path,
        provider="placeholder",
        model="placeholder_spoken_timing_cue",
        duration_sec=actual_dur,
        is_placeholder=True,
        estimated_cost_usd=0.0,
    )


def generate_gemini_tts_narration(
    config: PipelineConfig,
    text: str,
    style_instruction: str,
    output_path: Path,
) -> NarrationResult:
    """Generate English narration via Gemini TTS (requires explicit `allow_paid_api=True`)."""
    if not config.allow_paid_api:
        raise NonRetryableError(
            "External Gemini API calls are blocked because ALLOW_PAID_API=false. "
            "Use placeholder narration for the radio cut or set ALLOW_PAID_API=true when approved."
        )
    if not config.gemini_api_key or config.gemini_api_key.startswith("your_"):
        raise NonRetryableError("Missing valid GEMINI_API_KEY in .env.")

    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError as exc:
        raise NonRetryableError(
            "google-genai package is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    prompt_text = f"{style_instruction}: {text}" if style_instruction else text

    def _call() -> bytes:
        client = genai.Client(api_key=config.gemini_api_key)
        try:
            response = client.models.generate_content(
                model=config.gemini_tts_model,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=config.gemini_tts_voice
                            )
                        )
                    ),
                ),
            )
        except Exception as err:
            msg = str(err)
            for code in (400, 401, 403, 404, 429, 500, 503):
                if str(code) in msg:
                    raise classify_http_status(code, msg) from err
            raise

        for candidate in getattr(response, "candidates", []) or []:
            for part in getattr(candidate.content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    return bytes(inline.data)
        raise NonRetryableError(
            f"Gemini TTS ({config.gemini_tts_model}) returned no audio payload."
        )

    audio_bytes = run_with_retry(_call)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Gemini TTS commonly returns raw PCM (24kHz mono 16-bit) or WAV bytes
    if audio_bytes[:4] == b"RIFF":
        output_path.write_bytes(audio_bytes)
    else:
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_bytes)

    actual_dur = measure_wav_duration_sec(output_path)
    return NarrationResult(
        output_path=output_path,
        provider="gemini_tts",
        model=config.gemini_tts_model,
        duration_sec=actual_dur,
        is_placeholder=False,
        estimated_cost_usd=0.0,
    )
