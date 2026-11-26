"""Unit tests for subtitle wrapping, SRT timestamp formatting, and shot timing."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.stage4_audio import build_subtitles_srt, format_srt_timestamp
from pipeline.validate import wrap_subtitle_text

REPO_ROOT = Path(__file__).resolve().parent.parent


class SubtitleTimingTests(unittest.TestCase):
    def test_wrap_subtitle_respects_line_and_char_limits(self) -> None:
        text = (
            "In modest classrooms, numbers, science, and new languages turned quiet "
            "questions into a sharper way of seeing."
        )
        chunks = wrap_subtitle_text(text, max_chars_per_line=40, max_lines=2)
        self.assertGreaterEqual(len(chunks), 2)
        for chunk in chunks:
            lines = chunk.splitlines()
            self.assertLessEqual(len(lines), 2)
            for line in lines:
                self.assertLessEqual(len(line), 40)

    def test_srt_timestamps_and_monotonic_cues(self) -> None:
        self.assertEqual(format_srt_timestamp(0.0), "00:00:00,000")
        self.assertEqual(format_srt_timestamp(65.432), "00:01:05,432")

        sb = json.loads((REPO_ROOT / "storyboard.json").read_text(encoding="utf-8"))
        measured = {s["shot_id"]: 5.5 for s in sb["shots"]}

        with tempfile.TemporaryDirectory() as tmp:
            srt_path, timings = build_subtitles_srt(
                sb["shots"], measured, Path(tmp) / "subtitles.srt"
            )
            self.assertTrue(srt_path.exists())
            self.assertEqual(len(timings), 10)
            prev_end = -1.0
            for item in timings:
                self.assertGreater(item["narration_start_sec"], prev_end)
                self.assertLess(item["narration_end_sec"], item["shot_end_sec"])
                prev_end = item["shot_end_sec"]


if __name__ == "__main__":
    unittest.main()
