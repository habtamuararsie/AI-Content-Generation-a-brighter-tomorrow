"""External keyframe import and validation (supports PNG, JPG/JPEG, and WEBP without modifying originals)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from pipeline.cache import file_sha256
from pipeline.config import PipelineConfig
from pipeline.retry import NonRetryableError

SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
SUPPORTED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}
MIN_IMAGE_DIMENSION_PX = 320


@dataclass(frozen=True)
class ExternalImageInfo:
    """Validated metadata for one externally supplied shot image."""

    shot_id: str
    path: Path
    actual_format: str
    width: int
    height: int
    aspect_ratio: float
    size_bytes: int
    sha256: str


def find_shot_image_candidates(keyframes_dir: Path, shot_id: str) -> list[Path]:
    """Return all matching PNG/JPG/JPEG/WEBP files in `keyframes_dir` for `shot_id`."""
    if not keyframes_dir.exists():
        return []
    matches: list[Path] = []
    for ext in SUPPORTED_IMAGE_EXTENSIONS:
        candidate = keyframes_dir / f"{shot_id}{ext}"
        if candidate.exists() and candidate.is_file():
            matches.append(candidate)
    return matches


def inspect_external_image(shot_id: str, image_path: Path) -> ExternalImageInfo:
    """Validate readability, real image format, and dimensions without altering the file."""
    if not image_path.exists() or image_path.stat().st_size == 0:
        raise NonRetryableError(f"{shot_id}: image file is missing or empty: {image_path}")

    try:
        with Image.open(image_path) as probe:
            probe.verify()
        with Image.open(image_path) as img:
            width, height = img.size
            actual_format = (img.format or "UNKNOWN").upper()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise NonRetryableError(
            f"{shot_id}: image file is corrupted or unreadable ({image_path}): {exc}"
        ) from exc

    if actual_format not in {"PNG", "JPEG", "WEBP"}:
        raise NonRetryableError(
            f"{shot_id}: unsupported decoded image format '{actual_format}' in {image_path}. "
            "Use PNG, JPG/JPEG, or WEBP."
        )

    if width < MIN_IMAGE_DIMENSION_PX or height < MIN_IMAGE_DIMENSION_PX:
        raise NonRetryableError(
            f"{shot_id}: image resolution {width}x{height} is below minimum "
            f"{MIN_IMAGE_DIMENSION_PX}px ({image_path})."
        )

    return ExternalImageInfo(
        shot_id=shot_id,
        path=image_path,
        actual_format=actual_format,
        width=width,
        height=height,
        aspect_ratio=round(width / height, 3),
        size_bytes=image_path.stat().st_size,
        sha256=file_sha256(image_path),
    )


def validate_external_keyframes(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    shot_id_filter: str | None = None,
) -> dict[str, ExternalImageInfo]:
    """Validate that every required storyboard shot has a unique, readable image file."""
    results: dict[str, ExternalImageInfo] = {}
    errors: list[str] = []

    for shot in storyboard["shots"]:
        shot_id = shot["shot_id"]
        if shot_id_filter and shot_id != shot_id_filter:
            continue

        candidates = find_shot_image_candidates(config.keyframes_dir, shot_id)
        if not candidates:
            errors.append(
                f"{shot_id}: missing image in {config.keyframes_dir} "
                f"(expected {shot_id}.png, {shot_id}.jpg, {shot_id}.jpeg, or {shot_id}.webp)."
            )
            continue
        if len(candidates) > 1:
            names = ", ".join(p.name for p in candidates)
            errors.append(
                f"{shot_id}: duplicate image files found ({names}). Keep only one file per shot."
            )
            continue

        try:
            results[shot_id] = inspect_external_image(shot_id, candidates[0])
        except NonRetryableError as exc:
            errors.append(str(exc))

    if errors:
        raise NonRetryableError(
            "External keyframe validation failed:\n- " + "\n- ".join(errors)
        )

    return results
