"""Stage 2: Storyboard validation and contract manifest generation."""

from __future__ import annotations

import time
from typing import Any

from pipeline.cache import file_sha256, save_manifest
from pipeline.config import PipelineConfig
from pipeline.logger import RunLogEntry, append_run_log
from pipeline.validate import ValidationReport, load_and_validate_storyboard


def run_stage2_storyboard(
    config: PipelineConfig,
    run_id: str,
) -> tuple[dict[str, Any], ValidationReport]:
    """Validate storyboard.json against storyboard.schema.json and write manifest."""
    config.ensure_directories()
    t0 = time.perf_counter()
    storyboard, report = load_and_validate_storyboard(
        config.storyboard_path, config.schema_path
    )
    elapsed = round(time.perf_counter() - t0, 4)

    manifest_path = config.manifests_dir / "storyboard_manifest.json"
    save_manifest(
        manifest_path,
        {
            "storyboard_sha256": file_sha256(config.storyboard_path),
            "schema_sha256": file_sha256(config.schema_path),
            "valid": report.valid,
            "shot_count": report.shot_count,
            "shots_duration_sec": report.shots_duration_sec,
            "end_card_duration_sec": report.end_card_duration_sec,
            "total_duration_sec": report.total_duration_sec,
            "total_narration_words": report.total_narration_words,
            "errors": report.errors,
            "warnings": report.warnings,
        },
    )

    append_run_log(
        config.logs_path,
        RunLogEntry(
            run_id=run_id,
            stage="stage2_storyboard",
            shot_id="all",
            provider="local_validator",
            model="jsonschema_and_timing",
            status="success" if report.valid else "failed",
            latency_sec=elapsed,
            error="; ".join(report.errors) if report.errors else None,
            metadata={
                "shot_count": report.shot_count,
                "total_duration_sec": report.total_duration_sec,
            },
        ),
    )

    if not report.valid:
        raise ValueError("Storyboard validation failed:\n- " + "\n- ".join(report.errors))

    return storyboard, report
