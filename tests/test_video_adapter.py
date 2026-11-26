"""Unit tests for Ken Burns 9:16 portrait pan/zoom and 16:9 filter generation."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from pipeline.providers.video_adapter import (
    PORTRAIT_FRAMING_PRESETS,
    build_ken_burns_filter,
    render_ken_burns_clip,
)
from pipeline.retry import NonRetryableError


def test_portrait_filter_pads_and_preserves_full_width() -> None:
    """Landscape keyframes rendered into 9:16 pad vertically so zoompan can pan horizontally."""
    vf = build_ken_burns_filter(
        src_width=1248,
        src_height=832,
        frames=120,
        shot_index=4,
        fps=24,
        width=1080,
        height=1920,
        shot_id="shot_05",
    )

    assert "scale=3600:2400," in vf
    pad_match = re.search(r"pad=(\d+):(\d+):0:(\d+):black", vf)
    assert pad_match is not None
    pad_w, pad_h, y_off = (int(pad_match.group(i)) for i in (1, 2, 3))
    assert pad_w == 3600
    assert abs((pad_w / pad_h) - (1080 / 1920)) < 0.002
    assert y_off == (pad_h - 2400) // 2

    base_z = pad_h / 2400
    assert f"z='{base_z:.6f}*(" in vf
    assert "x='clip(" in vf
    assert f"y='clip(" in vf
    assert ":d=120:s=1080x1920:fps=24" in vf


def test_portrait_presets_cover_all_shots_and_headroom_anchors() -> None:
    """Every storyboard shot has a curated 9:16 preset and unmapped shots fall back safely."""
    for idx in range(1, 11):
        shot_id = f"shot_{idx:02d}"
        assert shot_id in PORTRAIT_FRAMING_PRESETS
        vf = build_ken_burns_filter(
            src_width=1920 if idx == 10 else 1264,
            src_height=1080 if idx == 10 else 848,
            frames=96,
            shot_index=idx - 1,
            width=1080,
            height=1920,
            shot_id=shot_id,
        )
        assert "pad=" in vf
        assert "s=1080x1920:fps=24" in vf

    # Shot 06 keeps top anchor (cy=0.0) so tight headroom near the upper edge is never clipped
    vf_06 = build_ken_burns_filter(1264, 848, 120, width=1080, height=1920, shot_id="shot_06")
    pad_06 = re.search(r"pad=\d+:\d+:0:(\d+):black", vf_06)
    assert pad_06 is not None
    y_off_06 = int(pad_06.group(1))
    assert f"y='clip({y_off_06:.2f}-(ih/zoom/2),{y_off_06}," in vf_06

    # Custom/unmapped shot IDs still get alternating portrait presets
    vf_custom_0 = build_ken_burns_filter(1920, 1080, 100, shot_index=0, width=1080, height=1920, shot_id="custom_99")
    vf_custom_1 = build_ken_burns_filter(1920, 1080, 100, shot_index=1, width=1080, height=1920, shot_id="custom_99")
    assert vf_custom_0 != vf_custom_1
    assert "pad=" in vf_custom_0


def test_landscape_and_matching_portrait_sources_skip_vertical_pad() -> None:
    """16:9 exports and already-portrait sources use standard zoompan crop without black padding."""
    vf_16x9 = build_ken_burns_filter(
        src_width=1264,
        src_height=848,
        frames=120,
        shot_index=0,
        fps=24,
        width=1920,
        height=1080,
        shot_id="shot_01",
    )
    assert "pad=" not in vf_16x9
    assert "scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160" in vf_16x9
    assert ":d=120:s=1920x1080:fps=24" in vf_16x9

    vf_portrait_src = build_ken_burns_filter(
        src_width=1080,
        src_height=1920,
        frames=96,
        shot_index=2,
        width=1080,
        height=1920,
        shot_id="shot_03",
    )
    assert "pad=" not in vf_portrait_src
    assert ":d=96:s=1080x1920:fps=24" in vf_portrait_src


def test_render_ken_burns_clip_invokes_ffmpeg_with_portrait_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """render_ken_burns_clip reads image size and forwards shot_id to build_ken_burns_filter."""
    kf = tmp_path / "shot_08.png"
    Image.new("RGB", (1248, 832), (20, 40, 60)).save(kf)
    out = tmp_path / "shot_08_9x16.mp4"

    captured_cmds: list[list[str]] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        captured_cmds.append(cmd)
        out.write_bytes(b"fake-mp4")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = render_ken_burns_clip(
        ffmpeg_bin="ffmpeg",
        keyframe_path=kf,
        output_path=out,
        duration_sec=5.0,
        shot_index=7,
        fps=24,
        width=1080,
        height=1920,
        shot_id="shot_08",
    )

    assert res.output_path == out
    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert "-loop" not in cmd
    vf_arg = cmd[cmd.index("-vf") + 1]
    assert "pad=3600:" in vf_arg
    assert "s=1080x1920:fps=24" in vf_arg


def test_render_ken_burns_clip_rejects_corrupt_keyframe(tmp_path: Path) -> None:
    """Unreadable image files fail cleanly with NonRetryableError."""
    bad = tmp_path / "bad.png"
    bad.write_text("not an image", encoding="utf-8")
    with pytest.raises(NonRetryableError):
        render_ken_burns_clip("ffmpeg", bad, tmp_path / "out.mp4", duration_sec=2.0)
