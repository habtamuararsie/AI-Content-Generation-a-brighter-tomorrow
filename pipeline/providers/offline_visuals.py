"""Zero-cost offline visual fallback: local SVG scenes, reference crops, and PNG compositor."""

from __future__ import annotations

import math
import shutil
import struct
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.config import PipelineConfig
from pipeline.retry import NonRetryableError


@dataclass(frozen=True)
class OfflineSceneTheme:
    """Color palette and scene geometry preset for one Ethiopian heritage shot."""

    sky_top: tuple[int, int, int]
    sky_bottom: tuple[int, int, int]
    hill_far: tuple[int, int, int]
    hill_near: tuple[int, int, int]
    ground: tuple[int, int, int]
    glow_color: tuple[int, int, int]
    glow_pos: tuple[float, float]
    motif: str
    portrait_scale_h: int = 470
    portrait_y_offset: int = 120


_SHOT_THEMES: dict[str, OfflineSceneTheme] = {
    "shot_01": OfflineSceneTheme(
        sky_top=(45, 68, 102),
        sky_bottom=(235, 168, 92),
        hill_far=(92, 114, 96),
        hill_near=(66, 92, 60),
        ground=(86, 72, 48),
        glow_color=(255, 214, 130),
        glow_pos=(0.50, 0.42),
        motif="highland_village_sunrise",
    ),
    "shot_02": OfflineSceneTheme(
        sky_top=(86, 120, 102),
        sky_bottom=(214, 196, 152),
        hill_far=(112, 118, 98),
        hill_near=(88, 94, 78),
        ground=(128, 116, 98),
        glow_color=(250, 224, 162),
        glow_pos=(0.35, 0.25),
        motif="yeqolo_courtyard",
        portrait_scale_h=480,
        portrait_y_offset=125,
    ),
    "shot_03": OfflineSceneTheme(
        sky_top=(72, 128, 184),
        sky_bottom=(236, 206, 150),
        hill_far=(94, 126, 86),
        hill_near=(74, 108, 64),
        ground=(156, 92, 56),
        glow_color=(255, 228, 154),
        glow_pos=(0.72, 0.28),
        motif="footpath_to_school",
        portrait_scale_h=450,
        portrait_y_offset=140,
    ),
    "shot_04": OfflineSceneTheme(
        sky_top=(52, 74, 62),
        sky_bottom=(142, 156, 128),
        hill_far=(76, 102, 74),
        hill_near=(58, 84, 56),
        ground=(116, 82, 52),
        glow_color=(252, 236, 186),
        glow_pos=(0.24, 0.34),
        motif="rural_classroom",
        portrait_scale_h=475,
        portrait_y_offset=125,
    ),
    "shot_05": OfflineSceneTheme(
        sky_top=(28, 44, 64),
        sky_bottom=(78, 106, 124),
        hill_far=(54, 78, 72),
        hill_near=(42, 64, 58),
        ground=(74, 62, 50),
        glow_color=(128, 206, 255),
        glow_pos=(0.50, 0.52),
        motif="first_computer",
        portrait_scale_h=475,
        portrait_y_offset=120,
    ),
    "shot_06": OfflineSceneTheme(
        sky_top=(22, 32, 48),
        sky_bottom=(66, 82, 98),
        hill_far=(44, 56, 68),
        hill_near=(34, 42, 52),
        ground=(76, 56, 40),
        glow_color=(140, 212, 255),
        glow_pos=(0.50, 0.38),
        motif="coding_hands",
        portrait_scale_h=0,
    ),
    "shot_07": OfflineSceneTheme(
        sky_top=(18, 22, 36),
        sky_bottom=(58, 44, 34),
        hill_far=(42, 36, 32),
        hill_near=(32, 28, 26),
        ground=(68, 48, 34),
        glow_color=(255, 192, 106),
        glow_pos=(0.28, 0.36),
        motif="evening_study",
        portrait_scale_h=470,
        portrait_y_offset=125,
    ),
    "shot_08": OfflineSceneTheme(
        sky_top=(68, 118, 158),
        sky_bottom=(228, 208, 166),
        hill_far=(88, 118, 84),
        hill_near=(68, 96, 66),
        ground=(128, 96, 62),
        glow_color=(255, 232, 178),
        glow_pos=(0.76, 0.30),
        motif="building_together",
        portrait_scale_h=470,
        portrait_y_offset=125,
    ),
    "shot_09": OfflineSceneTheme(
        sky_top=(54, 104, 148),
        sky_bottom=(226, 198, 144),
        hill_far=(84, 114, 82),
        hill_near=(64, 92, 62),
        ground=(108, 86, 64),
        glow_color=(172, 226, 255),
        glow_pos=(0.50, 0.44),
        motif="ai_community_hub",
        portrait_scale_h=475,
        portrait_y_offset=120,
    ),
    "shot_10": OfflineSceneTheme(
        sky_top=(48, 52, 92),
        sky_bottom=(242, 154, 78),
        hill_far=(96, 84, 88),
        hill_near=(62, 74, 54),
        ground=(74, 60, 42),
        glow_color=(255, 196, 104),
        glow_pos=(0.50, 0.40),
        motif="sunset_ridge_return",
        portrait_scale_h=440,
        portrait_y_offset=145,
    ),
}


def ensure_selected_and_cropped_references(config: PipelineConfig) -> dict[str, Path]:
    """Select an existing character reference candidate (without overwriting originals) and crop 3 stages."""
    config.ensure_directories()
    selected = config.references_dir / "character_sheet_selected.png"
    if not selected.exists() or selected.stat().st_size == 0:
        preferred_order = [
            config.references_dir / "character_sheet_candidate_2.png",
            config.references_dir / "character_sheet_candidate_1.png",
            config.references_dir / "character_sheet_candidate_3.png",
        ]
        source = next((p for p in preferred_order if p.exists() and p.stat().st_size > 0), None)
        if source is None:
            raise NonRetryableError(
                f"No existing character reference candidates found in {config.references_dir}."
            )
        shutil.copy2(source, selected)

    crop_specs = {
        "childhood": ("ref_childhood.png", "crop=iw/3-14:ih-16:6:8"),
        "adolescence": ("ref_adolescence.png", "crop=iw/3-14:ih-16:iw/3+7:8"),
        "young_adulthood": ("ref_young_adulthood.png", "crop=iw/3-14:ih-16:2*iw/3+8:8"),
    }
    cropped_paths: dict[str, Path] = {"selected": selected}

    for stage, (filename, crop_filter) in crop_specs.items():
        out_path = config.references_dir / filename
        if not out_path.exists() or out_path.stat().st_size == 0:
            if shutil.which(config.ffmpeg_bin) is None:
                raise NonRetryableError(
                    f"FFmpeg binary '{config.ffmpeg_bin}' not found; cannot crop character reference."
                )
            proc = subprocess.run(
                [config.ffmpeg_bin, "-y", "-i", str(selected), "-vf", crop_filter, str(out_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                raise NonRetryableError(f"FFmpeg reference crop failed for {stage}: {proc.stderr[-300:]}")
        cropped_paths[stage] = out_path

    return cropped_paths


def _rgb_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def write_scene_svg(shot: dict[str, Any], svg_path: Path) -> Path:
    """Create a local Ethiopian heritage SVG scene document for a shot."""
    shot_id = shot["shot_id"]
    theme = _SHOT_THEMES.get(shot_id, _SHOT_THEMES["shot_01"])
    gx = int(theme.glow_pos[0] * 1280)
    gy = int(theme.glow_pos[1] * 720)

    extra_svg = ""
    if theme.motif in {"highland_village_sunrise", "sunset_ridge_return", "footpath_to_school"}:
        extra_svg = (
            '<path d="M180,500 L220,445 L260,500 Z" fill="#4f3d2d" opacity="0.85"/>'
            '<rect x="192" y="500" width="56" height="44" fill="#8b7355" opacity="0.85"/>'
            '<path d="M1010,485 L1045,435 L1080,485 Z" fill="#4f3d2d" opacity="0.8"/>'
            '<rect x="1020" y="485" width="50" height="40" fill="#8b7355" opacity="0.8"/>'
        )
    elif theme.motif == "yeqolo_courtyard":
        extra_svg = (
            '<rect x="80" y="210" width="210" height="330" rx="8" fill="#6b5e4c" opacity="0.75"/>'
            '<path d="M135,540 L135,390 A50,50 0 0,1 235,390 L235,540 Z" fill="#2c241d" opacity="0.85"/>'
            '<ellipse cx="1020" cy="210" rx="220" ry="130" fill="#3a5934" opacity="0.75"/>'
        )
    elif theme.motif in {"rural_classroom", "building_together"}:
        extra_svg = (
            '<rect x="240" y="130" width="800" height="260" rx="10" fill="#284a36" opacity="0.85"/>'
            '<rect x="940" y="120" width="210" height="220" fill="#dff0d8" opacity="0.65"/>'
        )
    elif theme.motif in {"first_computer", "coding_hands", "evening_study", "ai_community_hub"}:
        extra_svg = (
            '<rect x="410" y="180" width="460" height="270" rx="14" fill="#182635" stroke="#6cc4ff" stroke-width="4" opacity="0.9"/>'
            '<path d="M450,370 Q540,260 640,310 T830,240" fill="none" stroke="#8de0ff" stroke-width="5" opacity="0.85"/>'
        )

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">\n'
        "  <defs>\n"
        '    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">\n'
        f'      <stop offset="0%" stop-color="{_rgb_hex(theme.sky_top)}"/>\n'
        f'      <stop offset="100%" stop-color="{_rgb_hex(theme.sky_bottom)}"/>\n'
        "    </linearGradient>\n"
        f'    <radialGradient id="glow" cx="{gx}" cy="{gy}" r="360" gradientUnits="userSpaceOnUse">\n'
        f'      <stop offset="0%" stop-color="{_rgb_hex(theme.glow_color)}" stop-opacity="0.75"/>\n'
        f'      <stop offset="100%" stop-color="{_rgb_hex(theme.glow_color)}" stop-opacity="0"/>\n'
        "    </radialGradient>\n"
        "  </defs>\n"
        '  <rect width="1280" height="720" fill="url(#sky)"/>\n'
        '  <rect width="1280" height="720" fill="url(#glow)"/>\n'
        f'  <path d="M0,430 Q320,330 640,395 T1280,370 L1280,720 L0,720 Z" fill="{_rgb_hex(theme.hill_far)}"/>\n'
        f'  <path d="M0,500 Q380,430 760,485 T1280,465 L1280,720 L0,720 Z" fill="{_rgb_hex(theme.hill_near)}"/>\n'
        f'  <rect x="0" y="540" width="1280" height="180" fill="{_rgb_hex(theme.ground)}"/>\n'
        f"  {extra_svg}\n"
        "</svg>\n"
    )
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg, encoding="utf-8")
    return svg_path


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def _write_rgb_png(path: Path, width: int, height: int, rgb_rows: list[bytes]) -> None:
    raw = b"".join(b"\x00" + row for row in rgb_rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw, level=6)
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _render_background_png(shot_id: str, out_png: Path, width: int = 1280, height: int = 720) -> Path:
    """Render an atmospheric 1280x720 Ethiopian heritage background PNG in pure Python."""
    theme = _SHOT_THEMES.get(shot_id, _SHOT_THEMES["shot_01"])
    gx = theme.glow_pos[0] * width
    gy = theme.glow_pos[1] * height
    glow_r2 = (0.34 * width) ** 2

    rows: list[bytes] = []
    for y in range(height):
        yn = y / (height - 1)
        # Base vertical gradient
        t_sky = min(1.0, yn / 0.72)
        base_r = theme.sky_top[0] + (theme.sky_bottom[0] - theme.sky_top[0]) * t_sky
        base_g = theme.sky_top[1] + (theme.sky_bottom[1] - theme.sky_top[1]) * t_sky
        base_b = theme.sky_top[2] + (theme.sky_bottom[2] - theme.sky_top[2]) * t_sky

        row = bytearray(width * 3)
        dy2 = (y - gy) ** 2
        for x in range(width):
            xn = x / width
            far_y = 0.56 + 0.06 * math.sin(xn * 5.2 + 0.7) + 0.025 * math.cos(xn * 11.0)
            near_y = 0.67 + 0.045 * math.sin(xn * 4.0 + 2.3) + 0.02 * math.sin(xn * 9.5)
            ground_y = 0.77 + 0.01 * math.sin(xn * 6.0)

            if yn >= ground_y:
                r, g, b = theme.ground
                # Subtle footpath / desk perspective highlight near horizontal center
                if theme.motif == "footpath_to_school" and abs(xn - 0.5) < (0.04 + 0.14 * (yn - ground_y) / 0.23):
                    r, g, b = 188, 114, 70
            elif yn >= near_y:
                r, g, b = theme.hill_near
            elif yn >= far_y:
                r, g, b = theme.hill_far
            else:
                r, g, b = base_r, base_g, base_b

            # Motif-specific architectural or tech focal accents
            if theme.motif in {"rural_classroom", "building_together"}:
                if 0.16 <= xn <= 0.84 and 0.15 <= yn <= 0.56:
                    r, g, b = 42, 74, 54
                elif 0.86 <= xn <= 0.96 and 0.14 <= yn <= 0.52:
                    r, g, b = 228, 236, 214
            elif theme.motif in {"first_computer", "coding_hands", "ai_community_hub"}:
                if 0.30 <= xn <= 0.70 and 0.20 <= yn <= 0.58:
                    r, g, b = 22, 36, 54
                    if 0.33 <= xn <= 0.67 and 0.24 <= yn <= 0.54:
                        curve_y = 0.42 - 0.08 * math.sin((xn - 0.33) * 16.0)
                        if abs(yn - curve_y) < 0.012:
                            r, g, b = 120, 218, 255
                if theme.motif == "coding_hands" and 0.28 <= xn <= 0.72 and 0.66 <= yn <= 0.88:
                    # Keyboard + notebook silhouette in foreground
                    r, g, b = (48, 52, 60) if xn < 0.56 else (228, 222, 206)

            # Soft radial sun / lamp / monitor glow
            d2 = (x - gx) ** 2 + dy2
            if d2 < glow_r2:
                glow_amt = 0.55 * (1.0 - d2 / glow_r2) ** 2
                r = r + (theme.glow_color[0] - r) * glow_amt
                g = g + (theme.glow_color[1] - g) * glow_amt
                b = b + (theme.glow_color[2] - b) * glow_amt

            # Gentle cinematic edge vignette
            vx = (xn - 0.5) * 2.0
            vy = (yn - 0.5) * 2.0
            vig = max(0.55, 1.0 - 0.24 * (vx * vx + vy * vy))
            idx = x * 3
            row[idx] = max(0, min(255, int(r * vig)))
            row[idx + 1] = max(0, min(255, int(g * vig)))
            row[idx + 2] = max(0, min(255, int(b * vig)))

        rows.append(bytes(row))

    _write_rgb_png(out_png, width, height, rows)
    return out_png


def generate_offline_scene_image(
    config: PipelineConfig,
    shot: dict[str, Any],
    output_path: Path,
    cropped_refs: dict[str, Path],
) -> Path:
    """Create local SVG + 1280x720 PNG keyframe using cropped character reference portraits."""
    shot_id = shot["shot_id"]
    age_stage = shot["age_stage"]
    svg_path = config.keyframes_dir / "svg" / f"{shot_id}.svg"
    write_scene_svg(shot, svg_path)

    tmp_bg = config.outputs_dir / "tmp" / f"{shot_id}_bg.png"
    _render_background_png(shot_id, tmp_bg, width=1280, height=720)

    theme = _SHOT_THEMES.get(shot_id, _SHOT_THEMES["shot_01"])
    portrait_path = cropped_refs.get(age_stage) if age_stage != "none" else None

    if portrait_path is None or theme.portrait_scale_h <= 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp_bg, output_path)
        return output_path

    if shutil.which(config.ffmpeg_bin) is None:
        raise NonRetryableError(
            f"FFmpeg binary '{config.ffmpeg_bin}' not found; cannot composite offline keyframe."
        )

    # Feather the real cropped portrait edges smoothly onto the centered scene frame
    filter_complex = (
        f"[1:v]scale=-1:{theme.portrait_scale_h},format=rgba,"
        f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
        f"a='255*min(1,max(0,(1-hypot((X-W/2)/(W*0.47),(Y-H/2)/(H*0.48)))*3.0))'[fg];"
        f"[0:v][fg]overlay=(W-w)/2:{theme.portrait_y_offset}:format=auto,"
        f"noise=alls=3:allf=t,format=rgb24[outv]"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            config.ffmpeg_bin,
            "-y",
            "-i",
            str(tmp_bg),
            "-i",
            str(portrait_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-frames:v",
            "1",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise NonRetryableError(f"FFmpeg offline scene composite failed: {proc.stderr[-400:]}")
    return output_path
