"""Stage 1: Creative design and 3-age character reference sheet generation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pipeline.cache import compute_cache_key, file_sha256, is_cache_valid, load_manifest, save_manifest
from pipeline.config import PipelineConfig
from pipeline.logger import RunLogEntry, append_run_log
from pipeline.providers.cloudflare_flux import generate_flux_image


def build_character_sheet_prompt(storyboard: dict[str, Any]) -> str:
    """Build a three-age Ethiopian cultural character reference sheet prompt from storyboard.json."""
    project = storyboard["project"]
    char = project["character"]
    stages = char["stages"]
    return (
        f"Three-panel cinematic documentary character reference sheet showing the EXACT SAME fictional "
        f"Ethiopian male person side-by-side across three life stages, framed evenly from chest up with "
        f"identical facial identity, warm medium-deep brown skin tone, expressive dark brown eyes, "
        f"natural close-cropped curly Ethiopian hair, and consistent facial bone structure ({char['identity_anchor']}): "
        f"Left panel — Childhood (8-10 years old, Qolo Temari in rural Ethiopia): {stages['childhood']}, set against a "
        f"softly blurred traditional Ethiopian Orthodox stone church courtyard with shade trees in gentle morning light. "
        f"Center panel — Adolescence (15-17 years old, rural Ethiopian high-school student): {stages['adolescence']}, "
        f"set against a softly blurred rural Ethiopian secondary school classroom with highland hills visible outside a window. "
        f"Right panel — Young Adulthood (23-26 years old, Ethiopian AI developer): {stages['young_adulthood']}, "
        f"set against a softly blurred modern Ethiopian software and AI workspace with a laptop and monitor. "
        f"Realistic documentary portraits, natural human proportions, respectful positive representation, "
        f"avoid stereotypes or artificial costumes, do not mix unrelated cultural traditions, no text labels, no watermarks. "
        f"{project['style_block']}"
    )


def run_stage1_reference(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    run_id: str,
    num_candidates: int = 3,
    base_seed: int = 700,
    force: bool = False,
) -> list[Path]:
    """Generate candidate 3-age character reference sheets (requires ALLOW_PAID_API=true)."""
    config.ensure_directories()
    manifest_path = config.manifests_dir / "reference_manifest.json"
    manifest = load_manifest(manifest_path)
    prompt = build_character_sheet_prompt(storyboard)
    outputs: list[Path] = []

    for idx in range(num_candidates):
        seed = base_seed + idx
        item_key = f"ref_candidate_{idx + 1}"
        out_path = config.references_dir / f"character_sheet_candidate_{idx + 1}.png"
        cache_key = compute_cache_key(
            {
                "stage": "stage1_reference",
                "model": config.image_model,
                "prompt": prompt,
                "seed": seed,
                "width": 1152,
                "height": 640,
            }
        )

        cached = is_cache_valid(manifest, item_key, cache_key, config.root_dir, force=force)
        if cached is not None:
            outputs.append(cached)
            append_run_log(
                config.logs_path,
                RunLogEntry(
                    run_id=run_id,
                    stage="stage1_reference",
                    shot_id=item_key,
                    provider="cloudflare_workers_ai",
                    model=config.image_model,
                    status="cached",
                    cache_hit=True,
                    seed=seed,
                ),
            )
            continue

        t0 = time.perf_counter()
        result = generate_flux_image(
            config=config,
            prompt=prompt,
            output_path=out_path,
            width=1152,
            height=640,
            seed=seed,
        )
        elapsed = round(time.perf_counter() - t0, 3)

        manifest.setdefault("items", {})[item_key] = {
            "cache_key": cache_key,
            "output_path": str(result.output_path.relative_to(config.root_dir)).replace("\\", "/"),
            "sha256": file_sha256(result.output_path),
            "model": result.model,
            "seed": seed,
            "width": result.width,
            "height": result.height,
        }
        save_manifest(manifest_path, manifest)
        outputs.append(result.output_path)

        append_run_log(
            config.logs_path,
            RunLogEntry(
                run_id=run_id,
                stage="stage1_reference",
                shot_id=item_key,
                provider=result.provider,
                model=result.model,
                status="success",
                cache_hit=False,
                seed=seed,
                latency_sec=elapsed,
                actual_hardware="cloudflare_serverless",
            ),
        )

    return outputs
