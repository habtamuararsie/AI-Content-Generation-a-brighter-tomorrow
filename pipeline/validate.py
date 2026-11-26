"""Storyboard schema, timing, cultural guardrail, and subtitle QA validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIN_SHOTS = 8
MAX_SHOTS = 12
MIN_TOTAL_DURATION_SEC = 60.0
MAX_TOTAL_DURATION_SEC = 90.0
MAX_SUBTITLE_LINE_CHARS = 40
MAX_SUBTITLE_LINES = 2
FORBIDDEN_UNVERIFIED_TERMS = ("gebeta",)


@dataclass(frozen=True)
class ValidationReport:
    """Summary returned after validating storyboard.json."""

    valid: bool
    shot_count: int
    shots_duration_sec: float
    end_card_duration_sec: float
    total_duration_sec: float
    total_narration_words: int
    errors: list[str]
    warnings: list[str]


def _fallback_schema_check(data: Any, schema: dict[str, Any]) -> list[str]:
    """Pure-Python structural checks used when `jsonschema` is not installed."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root storyboard must be a JSON object."]

    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"Missing required root field: '{field}'")

    shots = data.get("shots")
    if not isinstance(shots, list):
        errors.append("'shots' must be a list.")
    else:
        if len(shots) < MIN_SHOTS or len(shots) > MAX_SHOTS:
            errors.append(
                f"'shots' length must be between {MIN_SHOTS} and {MAX_SHOTS}, got {len(shots)}."
            )
        shot_required = schema["properties"]["shots"]["items"]["required"]
        for idx, shot in enumerate(shots):
            if not isinstance(shot, dict):
                errors.append(f"shots[{idx}] must be an object.")
                continue
            for req in shot_required:
                if req not in shot:
                    errors.append(f"shots[{idx}] missing required field '{req}'.")
            narration = shot.get("narration")
            if not isinstance(narration, dict) or not narration.get("text"):
                errors.append(f"shots[{idx}].narration.text must be a non-empty string.")

    end_card = data.get("end_card")
    if not isinstance(end_card, dict):
        errors.append("'end_card' must be a JSON object.")
    else:
        for req in schema["properties"]["end_card"]["required"]:
            if req not in end_card:
                errors.append(f"end_card missing required field '{req}'.")
        if end_card.get("enabled") is not True:
            errors.append("end_card.enabled must be true to satisfy the AI end-card requirement.")

    return errors


def validate_with_schema(storyboard: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate storyboard against JSON Schema (using `jsonschema` when available)."""
    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft202012Validator(schema)
        errs = sorted(validator.iter_errors(storyboard), key=lambda e: list(e.path))
        return [
            f"{'.'.join(str(p) for p in err.path) or 'root'}: {err.message}" for err in errs
        ]
    except ImportError:
        return _fallback_schema_check(storyboard, schema)


def validate_storyboard_data(
    storyboard: dict[str, Any],
    schema: dict[str, Any],
) -> ValidationReport:
    """Validate schema, 60-90s total duration (shots + end card), uniqueness, and guardrails."""
    errors = validate_with_schema(storyboard, schema)
    warnings: list[str] = []

    shots = storyboard.get("shots", [])
    end_card = storyboard.get("end_card", {})
    shots_duration = sum(
        float(s.get("duration_sec", 0.0)) for s in shots if isinstance(s, dict)
    )
    end_card_duration = (
        float(end_card.get("duration_sec", 0.0))
        if isinstance(end_card, dict) and end_card.get("enabled")
        else 0.0
    )
    total_duration = round(shots_duration + end_card_duration, 3)

    if total_duration < MIN_TOTAL_DURATION_SEC or total_duration > MAX_TOTAL_DURATION_SEC:
        errors.append(
            f"Total film duration (shots {shots_duration:.2f}s + end_card {end_card_duration:.2f}s "
            f"= {total_duration:.2f}s) must be between {MIN_TOTAL_DURATION_SEC:.0f}s and "
            f"{MAX_TOTAL_DURATION_SEC:.0f}s."
        )

    target_total = storyboard.get("project", {}).get("target_total_duration_sec")
    if isinstance(target_total, (int, float)) and abs(total_duration - float(target_total)) > 1.0:
        warnings.append(
            f"Sum of shot durations + end card ({total_duration:.2f}s) differs from "
            f"project.target_total_duration_sec ({target_total:.2f}s)."
        )

    seen_ids: set[str] = set()
    total_words = 0
    for idx, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        shot_id = str(shot.get("shot_id", f"index_{idx}"))
        if shot_id in seen_ids:
            errors.append(f"Duplicate shot_id: '{shot_id}'")
        seen_ids.add(shot_id)

        narration = shot.get("narration", {})
        text = str(narration.get("text", "")) if isinstance(narration, dict) else ""
        words = len(re.findall(r"\S+", text))
        total_words += words

        # Guardrail against unverified cultural terms in prompts/notes
        combined_text = " ".join(
            [
                str(shot.get("image_prompt", "")),
                str(shot.get("motion_prompt", "")),
                str(shot.get("cultural_notes", "")),
            ]
        ).lower()
        for forbidden in FORBIDDEN_UNVERIFIED_TERMS:
            if forbidden in combined_text:
                errors.append(
                    f"{shot_id}: contains unverified cultural term '{forbidden}'."
                )

    if total_words < 100 or total_words > 230:
        warnings.append(
            f"Narration word count ({total_words}) is outside typical 60-90s spoken range (100-230 words)."
        )

    return ValidationReport(
        valid=len(errors) == 0,
        shot_count=len(shots) if isinstance(shots, list) else 0,
        shots_duration_sec=round(shots_duration, 3),
        end_card_duration_sec=round(end_card_duration, 3),
        total_duration_sec=total_duration,
        total_narration_words=total_words,
        errors=errors,
        warnings=warnings,
    )


def load_and_validate_storyboard(
    storyboard_path: Path,
    schema_path: Path,
) -> tuple[dict[str, Any], ValidationReport]:
    """Load JSON files from disk and return `(storyboard_dict, ValidationReport)`."""
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    report = validate_storyboard_data(storyboard, schema)
    return storyboard, report


def wrap_subtitle_text(
    text: str,
    max_chars_per_line: int = MAX_SUBTITLE_LINE_CHARS,
    max_lines: int = MAX_SUBTITLE_LINES,
) -> list[str]:
    """Wrap narration into readable subtitle chunks (each <=2 lines, <=40 chars/line)."""
    words = text.strip().split()
    if not words:
        return []

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars_per_line:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    chunks: list[str] = []
    for idx in range(0, len(lines), max_lines):
        chunks.append("\n".join(lines[idx : idx + max_lines]))
    return chunks
