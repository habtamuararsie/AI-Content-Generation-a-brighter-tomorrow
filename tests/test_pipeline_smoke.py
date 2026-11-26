"""Offline end-to-end smoke test (zero paid API calls or GPU usage)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.config import load_config, validate_cloudflare_settings
from pipeline.logger import new_run_id
from pipeline.providers.cloudflare_flux import get_token_verify_url
from pipeline.retry import NonRetryableError
from pipeline.stage2_storyboard import run_stage2_storyboard
from pipeline.stage4_audio import run_stage4_audio
from pipeline.stage5_qa import run_stage5_qa
from pipeline.stage6_assemble import run_stage6_radio_cut

REPO_ROOT = Path(__file__).resolve().parent.parent


class OfflinePipelineSmokeTests(unittest.TestCase):
    def test_offline_radio_cut_pipeline_and_caching(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copy(REPO_ROOT / "storyboard.json", tmp_root / "storyboard.json")
            shutil.copy(REPO_ROOT / "storyboard.schema.json", tmp_root / "storyboard.schema.json")

            config = load_config(tmp_root)
            run_id_1 = new_run_id()
            storyboard, report = run_stage2_storyboard(config, run_id=run_id_1)
            self.assertTrue(report.valid)

            audio_1 = run_stage4_audio(config, storyboard, run_id=run_id_1)
            self.assertEqual(len(audio_1.narration_paths), 10)
            self.assertTrue(audio_1.srt_path.exists())
            self.assertTrue(audio_1.music_result.output_path.exists())

            qa = run_stage5_qa(config, storyboard, audio_1, run_id=run_id_1, mode="radio_cut")
            self.assertTrue(qa.passed, msg=f"QA errors: {qa.errors}")
            self.assertGreaterEqual(qa.total_duration_sec, 60.0)
            self.assertLessEqual(qa.total_duration_sec, 90.0)

            radio_out = run_stage6_radio_cut(config, storyboard, audio_1, run_id=run_id_1)
            self.assertTrue(radio_out["mix_wav"] is not None and radio_out["mix_wav"].exists())

            # Second run should hit narration cache for all 10 shots
            run_id_2 = new_run_id()
            run_stage4_audio(config, storyboard, run_id=run_id_2)
            log_lines = [
                json.loads(line)
                for line in config.logs_path.read_text(encoding="utf-8").splitlines()
            ]
            run2_nar = [
                row for row in log_lines if row["run_id"] == run_id_2 and row["stage"] == "stage4_narration"
            ]
            self.assertEqual(len(run2_nar), 10)
            self.assertTrue(all(row["cache_hit"] for row in run2_nar))

    def test_paid_api_guard_blocks_unapproved_calls(self) -> None:
        from pipeline.providers.cloudflare_flux import generate_flux_image
        from pipeline.providers.gemini_client import generate_gemini_tts_narration

        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(Path(tmp))
            self.assertFalse(config.allow_paid_api)
            with self.assertRaises(NonRetryableError):
                generate_flux_image(config, "test", Path(tmp) / "out.png")
            with self.assertRaises(NonRetryableError):
                generate_gemini_tts_narration(config, "hello", "warm", Path(tmp) / "out.wav")

    def test_cloudflare_token_verify_endpoints(self) -> None:
        self.assertEqual(
            get_token_verify_url("acct123", "user"),
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
        )
        self.assertEqual(
            get_token_verify_url("acct123", "account"),
            "https://api.cloudflare.com/client/v4/accounts/acct123/tokens/verify",
        )

    def test_cloudflare_config_validation_messages(self) -> None:
        from dataclasses import replace

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = load_config(root)
            issues = validate_cloudflare_settings(cfg)
            self.assertTrue(any(".env file not found" in msg for msg in issues))
            self.assertTrue(any("CLOUDFLARE_ACCOUNT_ID" in msg for msg in issues))
            self.assertTrue(any("CLOUDFLARE_API_TOKEN" in msg for msg in issues))

            (root / ".env").write_text("", encoding="utf-8")
            bad_url_cfg = replace(
                cfg,
                cloudflare_account_id="https://dash.cloudflare.com/abc",
                cloudflare_api_token="placeholder",
                cloudflare_token_type="invalid_type",
            )
            bad_issues = validate_cloudflare_settings(bad_url_cfg)
            self.assertTrue(any("looks like a URL" in msg for msg in bad_issues))
            self.assertTrue(any("CLOUDFLARE_API_TOKEN" in msg for msg in bad_issues))
            self.assertTrue(any("Invalid CLOUDFLARE_TOKEN_TYPE" in msg for msg in bad_issues))

            good_cfg = replace(
                cfg,
                cloudflare_account_id="0123456789abcdef0123456789abcdef",
                cloudflare_api_token="cf-test-token-value",
                cloudflare_token_type="user",
            )
            self.assertEqual(validate_cloudflare_settings(good_cfg), [])

    def test_character_reference_conditioning_maps_three_stages(self) -> None:
        from pipeline.stage1_reference import build_character_sheet_prompt
        from pipeline.stage3_visuals import _compose_keyframe_prompt, get_stage_reference_paths

        sb = json.loads((REPO_ROOT / "storyboard.json").read_text(encoding="utf-8"))
        ref_prompt = build_character_sheet_prompt(sb)
        self.assertIn("Qolo Temari", ref_prompt)
        self.assertIn("high-school student", ref_prompt)
        self.assertIn("AI developer", ref_prompt)

        # Establishing shot (age_stage='none') should not attach character panel guidance
        shot_01_prompt = _compose_keyframe_prompt(sb, sb["shots"][0], has_reference=True)
        self.assertNotIn("Reference conditioning:", shot_01_prompt)

        # Childhood, adolescence, and young adulthood should map to Left, Center, and Right panels
        shot_02_prompt = _compose_keyframe_prompt(sb, sb["shots"][1], has_reference=True)
        shot_05_prompt = _compose_keyframe_prompt(sb, sb["shots"][4], has_reference=True)
        shot_09_prompt = _compose_keyframe_prompt(sb, sb["shots"][8], has_reference=True)
        self.assertIn("Left panel", shot_02_prompt)
        self.assertIn("Center panel", shot_05_prompt)
        self.assertIn("Right panel", shot_09_prompt)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_cfg = load_config(Path(tmp))
            tmp_cfg.ensure_directories()
            self.assertEqual(get_stage_reference_paths(tmp_cfg, "none"), [])
            self.assertEqual(get_stage_reference_paths(tmp_cfg, "childhood"), [])

            sel = tmp_cfg.references_dir / "character_sheet_selected.png"
            sel.write_bytes(b"fake-png")
            self.assertEqual(get_stage_reference_paths(tmp_cfg, "none"), [])
            self.assertEqual(get_stage_reference_paths(tmp_cfg, "childhood"), [sel])

            crop = tmp_cfg.references_dir / "ref_childhood.png"
            crop.write_bytes(b"fake-crop")
            self.assertEqual(get_stage_reference_paths(tmp_cfg, "childhood"), [crop, sel])

    def test_offline_visual_svg_and_background_generation(self) -> None:
        from pipeline.providers.offline_visuals import _render_background_png, write_scene_svg

        sb = json.loads((REPO_ROOT / "storyboard.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            svg_path = write_scene_svg(sb["shots"][0], tmp_dir / "shot_01.svg")
            bg_path = _render_background_png("shot_01", tmp_dir / "shot_01_bg.png", width=320, height=180)
            self.assertTrue(svg_path.exists() and "<svg" in svg_path.read_text(encoding="utf-8"))
            self.assertTrue(bg_path.exists() and bg_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")

    def test_offline_pillow_heritage_references_preserve_candidates(self) -> None:
        from PIL import Image
        from pipeline.providers.pillow_heritage import generate_offline_heritage_references

        with tempfile.TemporaryDirectory() as tmp:
            tmp_cfg = load_config(Path(tmp))
            tmp_cfg.ensure_directories()
            cand = tmp_cfg.references_dir / "character_sheet_candidate_2.png"
            Image.new("RGB", (600, 300), (120, 90, 70)).save(cand, format="PNG")
            orig_bytes = cand.read_bytes()

            outputs = generate_offline_heritage_references(tmp_cfg)
            self.assertEqual(len(outputs), 3)
            self.assertEqual(cand.read_bytes(), orig_bytes)
            for out_path in outputs:
                self.assertTrue(out_path.exists())
                with Image.open(out_path) as img:
                    self.assertEqual(img.size, (1024, 1024))

    def test_external_image_validation_formats_duplicates_and_hashing(self) -> None:
        from dataclasses import replace
        from PIL import Image
        from pipeline.providers.external_images import validate_external_keyframes
        from pipeline.stage3_visuals import run_stage3_keyframes

        sb = json.loads((REPO_ROOT / "storyboard.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            cfg = replace(load_config(tmp_root), image_provider="external_local")
            cfg.ensure_directories()

            # Missing images should fail clearly
            with self.assertRaises(NonRetryableError):
                validate_external_keyframes(cfg, sb)

            # Populate valid PNG and JPEG files (including JPEG bytes under .png name)
            for idx, shot in enumerate(sb["shots"]):
                sid = shot["shot_id"]
                if idx % 2 == 0:
                    Image.new("RGB", (640, 480), (40 + idx, 80, 60)).save(
                        cfg.keyframes_dir / f"{sid}.png", format="PNG"
                    )
                else:
                    Image.new("RGB", (800, 533), (80, 60 + idx, 40)).save(
                        cfg.keyframes_dir / f"{sid}.jpg", format="JPEG"
                    )

            ext_info = validate_external_keyframes(cfg, sb)
            self.assertEqual(len(ext_info), 10)

            # First import writes manifest & logs external_manual with seed=None, cost=0.0
            run1 = new_run_id()
            kf1 = run_stage3_keyframes(cfg, sb, run_id=run1)
            self.assertEqual(len(kf1), 10)

            # Second import hits cache for all 10 shots
            run2 = new_run_id()
            run_stage3_keyframes(cfg, sb, run_id=run2)
            rows = [json.loads(line) for line in cfg.logs_path.read_text(encoding="utf-8").splitlines()]
            r2_rows = [r for r in rows if r["run_id"] == run2 and r["stage"] == "stage3_keyframes"]
            self.assertEqual(len(r2_rows), 10)
            self.assertTrue(all(r["cache_hit"] and r["seed"] is None and r["estimated_cost_usd"] == 0.0 for r in r2_rows))

            # Duplicate extensions for shot_01 should raise clear error
            Image.new("RGB", (640, 480), (10, 10, 10)).save(
                cfg.keyframes_dir / "shot_01.jpg", format="JPEG"
            )
            with self.assertRaises(NonRetryableError):
                validate_external_keyframes(cfg, sb)
            (cfg.keyframes_dir / "shot_01.jpg").unlink()

            # Corrupted file should fail clearly
            (cfg.keyframes_dir / "shot_01.png").write_bytes(b"not-an-image")
            with self.assertRaises(NonRetryableError):
                validate_external_keyframes(cfg, sb)

    def test_local_score_synthesis_and_music_caching(self) -> None:
        import struct
        import wave
        from dataclasses import replace

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copy(REPO_ROOT / "storyboard.json", tmp_root / "storyboard.json")
            shutil.copy(REPO_ROOT / "storyboard.schema.json", tmp_root / "storyboard.schema.json")
            cfg = replace(load_config(tmp_root), music_provider="local_score")
            r1 = new_run_id()
            sb, _ = run_stage2_storyboard(cfg, run_id=r1)
            audio_1 = run_stage4_audio(cfg, sb, run_id=r1)
            self.assertEqual(audio_1.music_result.provider, "local_score")
            self.assertFalse(audio_1.music_result.is_placeholder)
            self.assertTrue(audio_1.music_result.output_path.exists())

            with wave.open(str(audio_1.music_result.output_path), "rb") as wf:
                self.assertEqual(wf.getframerate(), 24000)
                self.assertEqual(wf.getnchannels(), 1)
                frames = wf.readframes(min(wf.getnframes(), 24000))
                samples = struct.unpack(f"<{len(frames) // 2}h", frames)
                self.assertGreater(max(abs(s) for s in samples), 200)

            r2 = new_run_id()
            run_stage4_audio(cfg, sb, run_id=r2)
            rows = [json.loads(line) for line in cfg.logs_path.read_text(encoding="utf-8").splitlines()]
            mus2 = [row for row in rows if row["run_id"] == r2 and row["stage"] == "stage4_music"]
            self.assertEqual(len(mus2), 1)
            self.assertTrue(mus2[0]["cache_hit"])

    def test_local_tts_narration_generation_and_secret_hygiene(self) -> None:
        from pipeline.providers.local_audio import generate_local_tts_narration
        from pipeline.config import is_missing_or_placeholder

        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(Path(tmp))
            out_wav = Path(tmp) / "shot_01.wav"
            res = generate_local_tts_narration(
                config=cfg,
                text="High above the terraced valleys, every story begins.",
                style_instruction="Calm documentary tone",
                output_path=out_wav,
            )
            self.assertTrue(res.output_path.exists())
            self.assertGreater(res.duration_sec, 1.5)
            self.assertEqual(res.estimated_cost_usd, 0.0)

        gi = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env", gi)
        env_ex = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        for line in env_ex.splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() in {"GEMINI_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "HF_TOKEN"}:
                    self.assertTrue(is_missing_or_placeholder(v))
        logs_file = REPO_ROOT / "logs" / "runs.jsonl"
        if logs_file.exists():
            txt = logs_file.read_text(encoding="utf-8")
            self.assertNotIn("AIza", txt)
            self.assertNotIn("Bearer ", txt)


if __name__ == "__main__":
    unittest.main()
