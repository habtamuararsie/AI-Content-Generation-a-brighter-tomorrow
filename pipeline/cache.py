"""Deterministic SHA-256 caching and stage manifest helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def compute_cache_key(payload: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hex digest for a JSON-serializable payload."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file on disk."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load an existing JSON manifest or return an empty structure."""
    if not manifest_path.exists():
        return {"items": {}}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def save_manifest(manifest_path: Path, data: dict[str, Any]) -> None:
    """Persist a JSON manifest atomically enough for local pipeline stages."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def is_cache_valid(
    manifest: dict[str, Any],
    item_key: str,
    expected_cache_key: str,
    root_dir: Path,
    force: bool = False,
) -> Path | None:
    """Return cached output Path if hash matches and output file is non-empty."""
    if force:
        return None
    entry = manifest.get("items", {}).get(item_key)
    if not entry:
        return None
    if entry.get("cache_key") != expected_cache_key:
        return None
    rel_path = entry.get("output_path")
    if not rel_path:
        return None
    candidate = root_dir / rel_path
    if not candidate.exists() or candidate.stat().st_size == 0:
        return None
    return candidate
