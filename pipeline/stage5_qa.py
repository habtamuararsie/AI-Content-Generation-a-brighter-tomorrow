"""Stage 5: Quality assurance and synchronization verification."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from typing import Any

from pipeline.cache import save_manifest
from pipeline.config import PipelineConfig
from pipeline.logger import RunLogEntry, append_run_log
from pipeline.providers.external_images import find_shot_image_candidates
from pipeline.stage4_audio import AudioStageOutput
from pipeline.validate import (
    MAX_SUBTITLE_LINE_CHARS,
    MAX_SUBTITLE_LINES,
    MAX_TOTAL_DURATION_SEC,
    MIN_TOTAL_DURATION_SEC,
)


@dataclass(frozen=True)
class QAReport:
    """Pre-assembly synchronization and compliance QA result."""

    passed: bool
    mode: str
    shots_duration_sec: float
    end_card_duration_sec: float
    total_duration_sec: float
    ffmpeg_available: bool
    errors: list[str]
    warnings: list[str]


def _check_srt_file(srt_text: str) -> list[str]:
    errors: list[str] = []
    blocks = [b.strip() for b in srt_text.strip().split("\n\n") if b.strip()]
    for idx, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        if len(lines) < 3:
            errors.append(f"SRT cue #{idx} has fewer than 3 lines.")
            continue
        text_lines = lines[2:]
        if len(text_lines) > MAX_SUBTITLE_LINES:
            errors.append(
                f"SRT cue #{idx} has {len(text_lines)} lines (max {MAX_SUBTITLE_LINES})."
            )
        for line in text_lines:
            if len(line) > MAX_SUBTITLE_LINE_CHARS:
                errors.append(
                    f"SRT cue #{idx} line exceeds {MAX_SUBTITLE_LINE_CHARS} chars: '{line}'"
                )
    return errors


def run_stage5_qa(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    audio_out: AudioStageOutput,
    run_id: str,
    mode: str = "radio_cut",
) -> QAReport:
    """Verify synchronization, 60-90s duration bounds, subtitles, and asset readiness."""
    t0 = time.perf_counter()
    errors: list[str] = []
    warnings: list[str] = []

    shots_dur = round(
        sum(t["effective_shot_duration_sec"] for t in audio_out.shot_timings), 3
    )
    end_card_dur = float(storyboard["end_card"]["duration_sec"])
    total_dur = round(shots_dur + end_card_dur, 3)

    if total_dur < MIN_TOTAL_DURATION_SEC or total_dur > MAX_TOTAL_DURATION_SEC:
        errors.append(
            f"Effective film duration ({shots_dur:.2f}s shots + {end_card_dur:.2f}s end card "
            f"= {total_dur:.2f}s) is outside {MIN_TOTAL_DURATION_SEC:.0f}-{MAX_TOTAL_DURATION_SEC:.0f}s."
        )

    if not audio_out.srt_path.exists():
        errors.append(f"Missing SRT file: {audio_out.srt_path}")
    else:
        errors.extend(_check_srt_file(audio_out.srt_path.read_text(encoding="utf-8")))

    for shot in storyboard["shots"]:
        shot_id = shot["shot_id"]
        if shot_id not in audio_out.narration_paths or not audio_out.narration_paths[shot_id].exists():
            errors.append(f"Missing narration audio for {shot_id}.")
        elif audio_out.narration_paths[shot_id].stat().st_size <= 44:
            errors.append(f"Empty WAV narration audio for {shot_id}.")

    if audio_out.music_result.is_placeholder and mode == "full":
        warnings.append(
            "Music track is currently a placeholder_temp track, not ACE-Step 1.5 output."
        )

    if mode == "full":
        if config.narration_provider == "placeholder":
            warnings.append(
                "Narration tracks are offline placeholder timing cues, not final spoken narration."
            )
        for shot in storyboard["shots"]:
            shot_id = shot["shot_id"]
            if not find_shot_image_candidates(config.keyframes_dir, shot_id):
                errors.append(
                    f"Missing keyframe image for {shot_id} in {config.keyframes_dir} "
                    f"(expected .png, .jpg, or .jpeg)."
                )

    ffmpeg_ok = shutil.which(config.ffmpeg_bin) is not None
    if not ffmpeg_ok:
        warnings.append(
            f"FFmpeg binary ('{config.ffmpeg_bin}') was not found on PATH; "
            "MP4 rendering is blocked until FFmpeg is installed."
        )

    passed = len(errors) == 0
    elapsed = round(time.perf_counter() - t0, 4)

    save_manifest(
        config.manifests_dir / "qa_report.json",
        {
            "passed": passed,
            "mode": mode,
            "shots_duration_sec": shots_dur,
            "end_card_duration_sec": end_card_dur,
            "total_duration_sec": total_dur,
            "ffmpeg_available": ffmpeg_ok,
            "errors": errors,
            "warnings": warnings,
        },
    )

    append_run_log(
        config.logs_path,
        RunLogEntry(
            run_id=run_id,
            stage="stage5_qa",
            shot_id="all",
            provider="local_qa",
            model="sync_and_duration_check",
            status="success" if passed else "failed",
            latency_sec=elapsed,
            error="; ".join(errors) if errors else None,
            metadata={
                "mode": mode,
                "total_duration_sec": total_dur,
                "ffmpeg_available": ffmpeg_ok,
                "warnings": warnings,
            },
        ),
    )

    return QAReport(
        passed=passed,
        mode=mode,
        shots_duration_sec=shots_dur,
        end_card_duration_sec=end_card_dur,
        total_duration_sec=total_dur,
        ffmpeg_available=ffmpeg_ok,
        errors=errors,
        warnings=warnings,
    )
