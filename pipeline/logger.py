"""Structured append-only JSONL logging to `logs/runs.jsonl`."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def new_run_id() -> str:
    """Generate a short unique identifier for one CLI invocation."""
    return uuid.uuid4().hex[:12]


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunLogEntry:
    """One structured event in `runs.jsonl`. Never include secret values."""

    run_id: str
    stage: str
    shot_id: str
    provider: str
    model: str
    status: str
    cache_hit: bool = False
    seed: int | None = None
    latency_sec: float = 0.0
    estimated_cost_usd: float = 0.0
    actual_hardware: str = "cpu"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp_utc: str = field(default_factory=utc_now_iso)


def append_run_log(logs_path: Path, entry: RunLogEntry) -> None:
    """Append a single JSON line to `logs/runs.jsonl`."""
    logs_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(entry), ensure_ascii=False)
    with logs_path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")
