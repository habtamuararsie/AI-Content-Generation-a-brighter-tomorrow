"""Stage 3: Keyframe generation (Cloudflare FLUX) and video clip resolution."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pipeline.cache import compute_cache_key, file_sha256, is_cache_valid, load_manifest, save_manifest
from pipeline.config import PipelineConfig
from pipeline.logger import RunLogEntry, append_run_log
from pipeline.providers.cloudflare_flux import generate_flux_image
from pipeline.providers.external_images import find_shot_image_candidates, validate_external_keyframes
from pipeline.providers.offline_visuals import (
    ensure_selected_and_cropped_references,
    generate_offline_scene_image,
)
from pipeline.providers.video_adapter import resolve_shot_video


_STAGE_PANEL_GUIDANCE = {
    "childhood": (
        "Reference conditioning: match the exact facial identity of the Left panel "
        "(childhood, age 8-10) in the attached 3-panel character reference sheet; "
        "render one single continuous cinematic scene, not a multi-panel collage."
    ),
    "adolescence": (
        "Reference conditioning: match the exact facial identity of the Center panel "
        "(adolescence, age 15-17) in the attached 3-panel character reference sheet; "
        "render one single continuous cinematic scene, not a multi-panel collage."
    ),
    "young_adulthood": (
        "Reference conditioning: match the exact facial identity of the Right panel "
        "(young adulthood, age 23-26) in the attached 3-panel character reference sheet; "
        "render one single continuous cinematic scene, not a multi-panel collage."
    ),
}


def _compose_keyframe_prompt(
    storyboard: dict[str, Any],
    shot: dict[str, Any],
    has_reference: bool = False,
) -> str:
    project = storyboard["project"]
    char = project["character"]
    age_stage = shot["age_stage"]
    parts = [shot["image_prompt"]]
    if age_stage != "none":
        parts.append(f"Character continuity: {char['identity_anchor']}")
        parts.append(f"Age stage appearance: {char['stages'][age_stage]}")
        if has_reference and age_stage in _STAGE_PANEL_GUIDANCE:
            parts.append(_STAGE_PANEL_GUIDANCE[age_stage])
    parts.append(f"Lighting: {shot['lighting']}.")
    parts.append(project["style_block"])
    return " ".join(parts)


def get_selected_reference_path(config: PipelineConfig) -> Path | None:
    """Return user-approved character reference sheet path if it exists."""
    selected = config.references_dir / "character_sheet_selected.png"
    if selected.exists() and selected.stat().st_size > 0:
        return selected
    return None


def get_stage_reference_paths(config: PipelineConfig, age_stage: str) -> list[Path]:
    """Return reference image paths (optional per-stage crop + selected sheet) for a shot."""
    if age_stage == "none":
        return []
    refs: list[Path] = []
    stage_crop = config.references_dir / f"ref_{age_stage}.png"
    if stage_crop.exists() and stage_crop.stat().st_size > 0:
        refs.append(stage_crop)
    selected = get_selected_reference_path(config)
    if selected is not None:
        refs.append(selected)
    return refs[:4]


def run_stage3_keyframes(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    run_id: str,
    shot_id_filter: str | None = None,
    force: bool = False,
) -> dict[str, Path]:
    """Resolve/import external keyframes, or generate via offline_local / Cloudflare FLUX."""
    config.ensure_directories()
    manifest_path = config.manifests_dir / "keyframes_manifest.json"
    manifest = load_manifest(manifest_path)
    results: dict[str, Path] = {}

    if config.image_provider == "external_local":
        t0 = time.perf_counter()
        ext_map = validate_external_keyframes(config, storyboard, shot_id_filter=shot_id_filter)
        validate_elapsed = round(time.perf_counter() - t0, 4)

        for shot in storyboard["shots"]:
            shot_id = shot["shot_id"]
            if shot_id_filter and shot_id != shot_id_filter:
                continue
            info = ext_map[shot_id]
            cache_key = compute_cache_key(
                {
                    "stage": "stage3_keyframes",
                    "provider": "external_manual",
                    "source_sha256": info.sha256,
                    "source_path": str(info.path.relative_to(config.root_dir)).replace("\\", "/"),
                }
            )
            cached = is_cache_valid(manifest, shot_id, cache_key, config.root_dir, force=force)
            results[shot_id] = info.path
            if cached is not None:
                append_run_log(
                    config.logs_path,
                    RunLogEntry(
                        run_id=run_id,
                        stage="stage3_keyframes",
                        shot_id=shot_id,
                        provider="external_manual",
                        model="user_supplied_external_image",
                        status="cached",
                        cache_hit=True,
                        seed=None,
                        estimated_cost_usd=0.0,
                        actual_hardware="external_supplied",
                        metadata={
                            "actual_format": info.actual_format,
                            "width": info.width,
                            "height": info.height,
                            "sha256": info.sha256,
                        },
                    ),
                )
                continue

            manifest.setdefault("items", {})[shot_id] = {
                "cache_key": cache_key,
                "output_path": str(info.path.relative_to(config.root_dir)).replace("\\", "/"),
                "sha256": info.sha256,
                "provider": "external_manual",
                "model": "user_supplied_external_image",
                "provenance": "externally_supplied",
                "actual_format": info.actual_format,
                "width": info.width,
                "height": info.height,
                "aspect_ratio": info.aspect_ratio,
                "size_bytes": info.size_bytes,
                "seed": None,
            }
            save_manifest(manifest_path, manifest)

            append_run_log(
                config.logs_path,
                RunLogEntry(
                    run_id=run_id,
                    stage="stage3_keyframes",
                    shot_id=shot_id,
                    provider="external_manual",
                    model="user_supplied_external_image",
                    status="imported",
                    cache_hit=False,
                    seed=None,
                    latency_sec=validate_elapsed,
                    estimated_cost_usd=0.0,
                    actual_hardware="external_supplied",
                    metadata={
                        "actual_format": info.actual_format,
                        "width": info.width,
                        "height": info.height,
                        "sha256": info.sha256,
                    },
                ),
            )
        return results

    use_offline = config.image_provider == "offline_local"
    cropped_refs = ensure_selected_and_cropped_references(config) if use_offline else {}

    for shot in storyboard["shots"]:
        shot_id = shot["shot_id"]
        if shot_id_filter and shot_id != shot_id_filter:
            continue

        refs = get_stage_reference_paths(config, shot["age_stage"])
        prompt = _compose_keyframe_prompt(storyboard, shot, has_reference=bool(refs))
        seed = int(shot["seed"])
        ref_hash = (
            ",".join(file_sha256(p) for p in refs)
            if refs
            else "no_ref"
        )
        active_provider = "offline_local" if use_offline else "cloudflare_workers_ai"
        active_model = "local_svg_and_ref_crop_compositor" if use_offline else config.image_model
        target_w, target_h = (1280, 720) if use_offline else (1024, 576)

        cache_key = compute_cache_key(
            {
                "stage": "stage3_keyframes",
                "provider": active_provider,
                "model": active_model,
                "prompt": prompt,
                "seed": seed,
                "ref_sha256": ref_hash,
                "width": target_w,
                "height": target_h,
            }
        )

        cached = is_cache_valid(manifest, shot_id, cache_key, config.root_dir, force=force)
        if cached is not None:
            results[shot_id] = cached
            append_run_log(
                config.logs_path,
                RunLogEntry(
                    run_id=run_id,
                    stage="stage3_keyframes",
                    shot_id=shot_id,
                    provider=active_provider,
                    model=active_model,
                    status="cached",
                    cache_hit=True,
                    seed=seed,
                ),
            )
            continue

        out_path = config.keyframes_dir / f"{shot_id}.png"
        t0 = time.perf_counter()
        if use_offline:
            generate_offline_scene_image(
                config=config,
                shot=shot,
                output_path=out_path,
                cropped_refs=cropped_refs,
            )
            provider_used = "offline_local"
            model_used = "local_svg_and_ref_crop_compositor"
            hardware_used = "local_cpu_ffmpeg"
        else:
            img = generate_flux_image(
                config=config,
                prompt=prompt,
                output_path=out_path,
                width=target_w,
                height=target_h,
                seed=seed,
                reference_images=refs,
            )
            provider_used = img.provider
            model_used = img.model
            hardware_used = "cloudflare_serverless"
        elapsed = round(time.perf_counter() - t0, 3)

        manifest.setdefault("items", {})[shot_id] = {
            "cache_key": cache_key,
            "output_path": str(out_path.relative_to(config.root_dir)).replace("\\", "/"),
            "sha256": file_sha256(out_path),
            "provider": provider_used,
            "model": model_used,
            "seed": seed,
            "reference_used": [p.name for p in refs] if refs else None,
        }
        save_manifest(manifest_path, manifest)
        results[shot_id] = out_path

        append_run_log(
            config.logs_path,
            RunLogEntry(
                run_id=run_id,
                stage="stage3_keyframes",
                shot_id=shot_id,
                provider=provider_used,
                model=model_used,
                status="success",
                cache_hit=False,
                seed=seed,
                latency_sec=elapsed,
                actual_hardware=hardware_used,
            ),
        )

    return results


def run_stage3_videos(
    config: PipelineConfig,
    storyboard: dict[str, Any],
    run_id: str,
    shot_id_filter: str | None = None,
    allow_ken_burns_fallback: bool = False,
    force: bool = False,
    keyframe_paths: dict[str, Path] | None = None,
) -> dict[str, Path]:
    """Resolve or render moving video clips for every shot."""
    config.ensure_directories()
    manifest_path = config.manifests_dir / "video_manifest.json"
    manifest = load_manifest(manifest_path)
    results: dict[str, Path] = {}

    for idx, shot in enumerate(storyboard["shots"]):
        shot_id = shot["shot_id"]
        if shot_id_filter and shot_id != shot_id_filter:
            continue

        if keyframe_paths and shot_id in keyframe_paths:
            keyframe_path = keyframe_paths[shot_id]
        else:
            candidates = find_shot_image_candidates(config.keyframes_dir, shot_id)
            keyframe_path = candidates[0] if candidates else (config.keyframes_dir / f"{shot_id}.png")
        kf_hash = file_sha256(keyframe_path) if keyframe_path.exists() else "missing_keyframe"
        cache_key = compute_cache_key(
            {
                "stage": "stage3_videos",
                "provider": config.video_provider,
                "duration_sec": shot["duration_sec"],
                "motion_prompt": shot["motion_prompt"],
                "keyframe_sha256": kf_hash,
                "fallback": allow_ken_burns_fallback,
                "render_profile": "ken_burns_1080p_v2",
            }
        )

        cached = is_cache_valid(manifest, shot_id, cache_key, config.root_dir, force=force)
        if cached is not None:
            results[shot_id] = cached
            append_run_log(
                config.logs_path,
                RunLogEntry(
                    run_id=run_id,
                    stage="stage3_videos",
                    shot_id=shot_id,
                    provider=config.video_provider,
                    model="cached",
                    status="cached",
                    cache_hit=True,
                ),
            )
            continue

        t0 = time.perf_counter()
        clip = resolve_shot_video(
            config=config,
            shot_id=shot_id,
            shot_index=idx,
            duration_sec=float(shot["duration_sec"]),
            keyframe_path=keyframe_path,
            allow_ken_burns_fallback=allow_ken_burns_fallback,
        )
        elapsed = round(time.perf_counter() - t0, 3)

        manifest.setdefault("items", {})[shot_id] = {
            "cache_key": cache_key,
            "output_path": str(clip.output_path.relative_to(config.root_dir)).replace("\\", "/"),
            "sha256": file_sha256(clip.output_path),
            "provider": clip.provider,
            "model": clip.model,
            "duration_sec": clip.duration_sec,
            "hardware": clip.hardware,
            "is_fallback": clip.is_fallback,
        }
        save_manifest(manifest_path, manifest)
        results[shot_id] = clip.output_path

        append_run_log(
            config.logs_path,
            RunLogEntry(
                run_id=run_id,
                stage="stage3_videos",
                shot_id=shot_id,
                provider=clip.provider,
                model=clip.model,
                status="success",
                cache_hit=False,
                latency_sec=elapsed,
                actual_hardware=clip.hardware,
                metadata={"is_fallback": clip.is_fallback},
            ),
        )

    return results
