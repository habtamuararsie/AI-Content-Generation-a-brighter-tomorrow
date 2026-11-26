"""Unit tests for storyboard.json and storyboard.schema.json validation."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from pipeline.validate import load_and_validate_storyboard, validate_storyboard_data

REPO_ROOT = Path(__file__).resolve().parent.parent
STORYBOARD_PATH = REPO_ROOT / "storyboard.json"
SCHEMA_PATH = REPO_ROOT / "storyboard.schema.json"


class StoryboardValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storyboard = json.loads(STORYBOARD_PATH.read_text(encoding="utf-8"))
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_repo_storyboard_is_valid_and_within_60_to_90_seconds(self) -> None:
        _, report = load_and_validate_storyboard(STORYBOARD_PATH, SCHEMA_PATH)
        self.assertTrue(report.valid, msg=f"Errors: {report.errors}")
        self.assertEqual(report.shot_count, 10)
        self.assertEqual(report.end_card_duration_sec, 3.0)
        self.assertGreaterEqual(report.total_duration_sec, 60.0)
        self.assertLessEqual(report.total_duration_sec, 90.0)

    def test_rejects_fewer_than_8_shots(self) -> None:
        broken = copy.deepcopy(self.storyboard)
        broken["shots"] = broken["shots"][:7]
        report = validate_storyboard_data(broken, self.schema)
        self.assertFalse(report.valid)

    def test_rejects_more_than_12_shots(self) -> None:
        broken = copy.deepcopy(self.storyboard)
        for idx in range(11, 14):
            extra = copy.deepcopy(broken["shots"][0])
            extra["shot_id"] = f"shot_{idx:02d}"
            broken["shots"].append(extra)
        report = validate_storyboard_data(broken, self.schema)
        self.assertFalse(report.valid)

    def test_duration_validation_includes_end_card(self) -> None:
        # 10 shots * 5.8s = 58.0s + 3.0s end card = 61.0s (valid)
        ok_sb = copy.deepcopy(self.storyboard)
        for shot in ok_sb["shots"]:
            shot["duration_sec"] = 5.8
        self.assertTrue(validate_storyboard_data(ok_sb, self.schema).valid)

        # 10 shots * 5.6s = 56.0s + 3.0s end card = 59.0s (< 60s, invalid)
        too_short = copy.deepcopy(self.storyboard)
        for shot in too_short["shots"]:
            shot["duration_sec"] = 5.6
        short_report = validate_storyboard_data(too_short, self.schema)
        self.assertFalse(short_report.valid)

        # 10 shots * 8.8s = 88.0s + 3.0s end card = 91.0s (> 90s, invalid)
        too_long = copy.deepcopy(self.storyboard)
        for shot in too_long["shots"]:
            shot["duration_sec"] = 8.8
        long_report = validate_storyboard_data(too_long, self.schema)
        self.assertFalse(long_report.valid)

    def test_rejects_unverified_gebeta_term(self) -> None:
        broken = copy.deepcopy(self.storyboard)
        broken["shots"][1]["image_prompt"] += " holding a gebeta board"
        report = validate_storyboard_data(broken, self.schema)
        self.assertFalse(report.valid)
        self.assertTrue(any("gebeta" in err for err in report.errors))


if __name__ == "__main__":
    unittest.main()
