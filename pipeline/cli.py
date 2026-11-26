"""Unified CLI entrypoint for A Brighter Tomorrow pipeline."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from pipeline.config import PipelineConfig, load_config, validate_cloudflare_settings
from pipeline.logger import RunLogEntry, append_run_log, new_run_id
from pipeline.providers.cloudflare_flux import verify_cloudflare_token
from pipeline.providers.external_images import validate_external_keyframes
from pipeline.providers.pillow_heritage import generate_offline_heritage_references
from pipeline.retry import NonRetryableError
from pipeline.stage1_reference import run_stage1_reference
from pipeline.stage2_storyboard import run_stage2_storyboard
from pipeline.stage3_visuals import run_stage3_keyframes, run_stage3_videos
from pipeline.stage4_audio import run_stage4_audio
from pipeline.stage5_qa import run_stage5_qa
from pipeline.stage6_assemble import run_stage6_assemble, run_stage6_radio_cut


def _apply_overrides(config: PipelineConfig, args: argparse.Namespace) -> PipelineConfig:
    updates: dict[str, object] = {}
    if getattr(args, "image_provider", None):
        updates["image_provider"] = args.image_provider
    if getattr(args, "narration_provider", None):
        updates["narration_provider"] = args.narration_provider
    if getattr(args, "video_provider", None):
        updates["video_provider"] = args.video_provider
    if getattr(args, "music_provider", None):
        updates["music_provider"] = args.music_provider
    if getattr(args, "confirm_api", False):
        updates["allow_paid_api"] = True
    return replace(config, **updates) if updates else config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.cli",
        description="A Brighter Tomorrow — reproducible AI short-film pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Validate storyboard.json against storyboard.schema.json")
    sub.add_parser(
        "validate-images",
        help="Inspect and validate externally supplied keyframes in outputs/keyframes/",
    )
    sub.add_parser("check-config", help="Validate .env and Cloudflare settings offline (zero API calls)")
    sub.add_parser("verify-cf", help="Verify Cloudflare Workers AI token without calling inference")

    p_radio = sub.add_parser("radio-cut", help="Generate draft/placeholder radio cut for review")
    p_radio.add_argument("--narration-provider", choices=["placeholder", "local_tts", "gemini_tts"])
    p_radio.add_argument("--music-provider", choices=["placeholder_temp", "local_score", "ace_step_15"])
    p_radio.add_argument("--confirm-api", action="store_true")
    p_radio.add_argument("--force", action="store_true")
    p_radio.add_argument("--shot-id")

    p_ref = sub.add_parser("reference", help="Generate 3-age character reference candidates")
    p_ref.add_argument("--num-candidates", type=int, default=3)
    p_ref.add_argument("--confirm-api", action="store_true")
    p_ref.add_argument("--force", action="store_true")

    sub.add_parser(
        "heritage-refs",
        help="Generate 3 offline Pillow PNG character reference images without API calls",
    )

    p_kf = sub.add_parser("keyframes", help="Resolve external or generated shot keyframes")
    p_kf.add_argument("--shot-id")
    p_kf.add_argument("--image-provider", choices=["external_local", "offline_local", "cloudflare_flux"])
    p_kf.add_argument("--confirm-api", action="store_true")
    p_kf.add_argument("--force", action="store_true")

    p_all = sub.add_parser("run-all", help="Run full pipeline and export 16:9 and 9:16 films")
    p_all.add_argument("--shot-id")
    p_all.add_argument("--image-provider", choices=["external_local", "offline_local", "cloudflare_flux"])
    p_all.add_argument("--narration-provider", choices=["placeholder", "local_tts", "gemini_tts"])
    p_all.add_argument("--video-provider", choices=["ken_burns", "wan22", "hunyuan15"])
    p_all.add_argument("--music-provider", choices=["placeholder_temp", "local_score", "ace_step_15"])
    p_all.add_argument("--allow-ken-burns-fallback", action="store_true")
    p_all.add_argument("--confirm-api", action="store_true")
    p_all.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)
    config = _apply_overrides(load_config(), args)
    run_id = new_run_id()

    try:
        return _dispatch(args, config, run_id)
    except NonRetryableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace, config: PipelineConfig, run_id: str) -> int:
    if args.command == "check-config":
        issues = validate_cloudflare_settings(config, require_account_id=True)
        if issues:
            print("Cloudflare configuration incomplete:\n- " + "\n- ".join(issues), file=sys.stderr)
            return 1
        print(
            f"Cloudflare configuration looks valid offline "
            f"(token_type={config.cloudflare_token_type}, image_model={config.image_model})."
        )
        return 0

    if args.command == "verify-cf":
        res = verify_cloudflare_token(config)
        print(f"Cloudflare token verification response: {res}")
        return 0

    storyboard, report = run_stage2_storyboard(config, run_id=run_id)
    if args.command == "validate":
        print(
            f"VALID: {report.shot_count} shots ({report.shots_duration_sec:.1f}s) + "
            f"end_card ({report.end_card_duration_sec:.1f}s) = {report.total_duration_sec:.1f}s "
            f"| {report.total_narration_words} narration words"
        )
        for warning in report.warnings:
            print(f"WARNING: {warning}")
        return 0

    if args.command == "validate-images":
        info_map = validate_external_keyframes(config, storyboard)
        print(f"EXTERNAL IMAGES VALID ({len(info_map)} shots):")
        for sid, info in info_map.items():
            print(
                f" - {sid}: {info.path.name} | {info.actual_format} "
                f"{info.width}x{info.height} (ar={info.aspect_ratio}) | sha256={info.sha256[:12]}"
            )
        return 0

    if args.command == "radio-cut":
        audio_out = run_stage4_audio(
            config, storyboard, run_id=run_id, shot_id_filter=args.shot_id, force=args.force
        )
        qa = run_stage5_qa(config, storyboard, audio_out, run_id=run_id, mode="radio_cut")
        if not qa.passed:
            print("QA FAILED:\n- " + "\n- ".join(qa.errors), file=sys.stderr)
            return 1
        out = run_stage6_radio_cut(config, storyboard, audio_out, run_id=run_id)
        print(f"Radio cut WAV ready: {out['mix_wav']}")
        if out["radio_cut_mp4"]:
            print(f"Radio cut MP4 ready: {out['radio_cut_mp4']}")
        else:
            print(
                "NOTE: FFmpeg not found on PATH, so radio_cut.mp4 was skipped. "
                "You can listen to radio_cut_mix.wav now or install FFmpeg for radio_cut.mp4."
            )
        return 0

    if args.command == "reference":
        paths = run_stage1_reference(
            config,
            storyboard,
            run_id=run_id,
            num_candidates=args.num_candidates,
            force=args.force,
        )
        print("Generated character reference candidates:")
        for p in paths:
            print(f" - {p}")
        return 0

    if args.command == "heritage-refs":
        paths = generate_offline_heritage_references(config)
        for p in paths:
            append_run_log(
                config.logs_path,
                RunLogEntry(
                    run_id=run_id,
                    stage="stage1_heritage_refs",
                    shot_id=p.stem,
                    provider="offline_pillow",
                    model="pillow_heritage_compositor",
                    status="success",
                    actual_hardware="local_cpu_pillow",
                    metadata={"output_path": str(p)},
                ),
            )
        print("Generated offline Pillow heritage reference images:")
        for p in paths:
            print(f" - {p}")
        return 0

    if args.command == "keyframes":
        kf = run_stage3_keyframes(
            config, storyboard, run_id=run_id, shot_id_filter=args.shot_id, force=args.force
        )
        print(f"Keyframes ready ({len(kf)} shots).")
        return 0

    if args.command == "run-all":
        kf_paths = run_stage3_keyframes(
            config, storyboard, run_id=run_id, shot_id_filter=args.shot_id, force=args.force
        )
        clips = run_stage3_videos(
            config,
            storyboard,
            run_id=run_id,
            shot_id_filter=args.shot_id,
            allow_ken_burns_fallback=args.allow_ken_burns_fallback,
            force=args.force,
            keyframe_paths=kf_paths,
        )
        audio_out = run_stage4_audio(
            config, storyboard, run_id=run_id, shot_id_filter=args.shot_id, force=args.force
        )
        qa = run_stage5_qa(config, storyboard, audio_out, run_id=run_id, mode="full")
        if not qa.passed:
            print("QA FAILED:\n- " + "\n- ".join(qa.errors), file=sys.stderr)
            return 1
        exports = run_stage6_assemble(
            config, storyboard, audio_out, clips, run_id=run_id, keyframe_paths=kf_paths
        )
        print(f"Final exports complete: {exports['16x9']} and {exports['9x16']}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
