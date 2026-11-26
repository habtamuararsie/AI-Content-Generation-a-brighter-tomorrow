"""Unit tests for deterministic SHA-256 caching and retry/fail-fast logic."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.cache import compute_cache_key, is_cache_valid, load_manifest, save_manifest
from pipeline.retry import NonRetryableError, RetryableError, classify_http_status, run_with_retry


class CacheAndRetryTests(unittest.TestCase):
    def test_cache_key_is_deterministic_and_sensitive_to_changes(self) -> None:
        base = {"prompt": "Ethiopian highlands", "seed": 1001, "model": "flux-2-klein-4b"}
        same = {"model": "flux-2-klein-4b", "seed": 1001, "prompt": "Ethiopian highlands"}
        changed_seed = {**base, "seed": 1002}

        self.assertEqual(compute_cache_key(base), compute_cache_key(same))
        self.assertNotEqual(compute_cache_key(base), compute_cache_key(changed_seed))

    def test_cache_hit_and_force_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_file = root / "outputs" / "keyframes" / "shot_01.png"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_bytes(b"png-bytes")

            manifest_path = root / "outputs" / "manifests" / "keyframes_manifest.json"
            key = compute_cache_key({"shot": "shot_01", "seed": 1001})
            save_manifest(
                manifest_path,
                {
                    "items": {
                        "shot_01": {
                            "cache_key": key,
                            "output_path": "outputs/keyframes/shot_01.png",
                        }
                    }
                },
            )
            manifest = load_manifest(manifest_path)

            self.assertEqual(is_cache_valid(manifest, "shot_01", key, root), out_file)
            self.assertIsNone(is_cache_valid(manifest, "shot_01", "different-key", root))
            self.assertIsNone(is_cache_valid(manifest, "shot_01", key, root, force=True))

    def test_retry_succeeds_after_transient_429_and_fails_fast_on_401(self) -> None:
        attempts = {"count": 0}
        sleeps: list[float] = []

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise classify_http_status(429, "rate limited")
            return "ok"

        result = run_with_retry(flaky, max_attempts=3, base_delay_sec=0.1, sleep_fn=sleeps.append)
        self.assertEqual(result, "ok")
        self.assertEqual(attempts["count"], 3)
        self.assertEqual(len(sleeps), 2)

        auth_attempts = {"count": 0}

        def unauthorized() -> str:
            auth_attempts["count"] += 1
            raise classify_http_status(401, "invalid token")

        with self.assertRaises(NonRetryableError):
            run_with_retry(unauthorized, max_attempts=3, sleep_fn=sleeps.append)
        self.assertEqual(auth_attempts["count"], 1)

        with self.assertRaises(RetryableError):
            run_with_retry(
                lambda: (_ for _ in ()).throw(classify_http_status(503, "unavailable")),
                max_attempts=2,
                base_delay_sec=0.05,
                sleep_fn=sleeps.append,
            )


if __name__ == "__main__":
    unittest.main()
