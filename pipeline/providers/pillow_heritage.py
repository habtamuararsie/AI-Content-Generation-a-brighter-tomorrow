"""Offline Python Pillow generator for three Ethiopian heritage character references.

Creates three distinct, culturally grounded 1024x1024 PNG reference images in
`outputs/references/` without calling any external API or modifying the original
character sheet candidates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from pipeline.config import PipelineConfig
from pipeline.retry import NonRetryableError

SIZE = 1024


@dataclass(frozen=True)
class HeritageReferenceSpec:
    """Output specification for one life-stage heritage reference PNG."""

    stage: str
    filename: str
    width: int
    height: int


STAGE_SPECS = (
    HeritageReferenceSpec(
        stage="childhood",
        filename="heritage_ref_stage1_childhood_qolo_temari.png",
        width=SIZE,
        height=SIZE,
    ),
    HeritageReferenceSpec(
        stage="adolescence",
        filename="heritage_ref_stage2_adolescence_highschool.png",
        width=SIZE,
        height=SIZE,
    ),
    HeritageReferenceSpec(
        stage="young_adulthood",
        filename="heritage_ref_stage3_young_adulthood_ai_dev.png",
        width=SIZE,
        height=SIZE,
    ),
)


def _vertical_gradient(
    width: int,
    height: int,
    top_rgb: tuple[int, int, int],
    bottom_rgb: tuple[int, int, int],
) -> Image.Image:
    """Create a smooth vertical RGB gradient canvas."""
    grad = Image.new("RGB", (width, height))
    px = grad.load()
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * t)
        g = int(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * t)
        b = int(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * t)
        for x in range(width):
            px[x, y] = (r, g, b)
    return grad


def _draw_highland_hills(
    draw: ImageDraw.ImageDraw,
    width: int,
    base_y: int,
    amplitude: int,
    freq: float,
    phase: float,
    color: tuple[int, int, int],
    bottom_y: int,
) -> None:
    """Paint smooth terraced Ethiopian highland ridges."""
    pts = [(0, bottom_y)]
    for x in range(0, width + 8, 8):
        y = base_y - int(
            amplitude * math.sin((x / width) * freq + phase)
            + (amplitude * 0.35) * math.cos((x / width) * freq * 2.1)
        )
        pts.append((x, y))
    pts.append((width, bottom_y))
    draw.polygon(pts, fill=color)


def _draw_traditional_tukul(
    draw: ImageDraw.ImageDraw, cx: int, base_y: int, w: int, h: int
) -> None:
    """Draw a modest Ethiopian rural stone-and-thatch tukul home silhouette."""
    wall_h = int(h * 0.48)
    roof_h = h - wall_h
    draw.rectangle(
        [cx - w // 2, base_y - wall_h, cx + w // 2, base_y],
        fill=(136, 114, 88),
        outline=(92, 74, 56),
    )
    draw.polygon(
        [
            (cx - w // 2 - 12, base_y - wall_h + 4),
            (cx, base_y - wall_h - roof_h),
            (cx + w // 2 + 12, base_y - wall_h + 4),
        ],
        fill=(104, 84, 54),
    )
    draw.rectangle(
        [cx - w // 7, base_y - wall_h // 2, cx + w // 7, base_y],
        fill=(54, 40, 28),
    )


def _draw_stone_church(draw: ImageDraw.ImageDraw, cx: int, base_y: int) -> None:
    """Draw a dignified traditional Ethiopian stone church silhouette."""
    draw.rectangle([cx - 88, base_y - 120, cx + 88, base_y], fill=(116, 102, 84))
    draw.polygon(
        [(cx - 102, base_y - 116), (cx, base_y - 196), (cx + 102, base_y - 116)],
        fill=(94, 78, 56),
    )
    # Subtle finial cross at roof apex
    draw.line([(cx, base_y - 196), (cx, base_y - 224)], fill=(214, 178, 96), width=4)
    draw.line([(cx - 11, base_y - 213), (cx + 11, base_y - 213)], fill=(214, 178, 96), width=4)
    # Arched doorway
    draw.pieslice([cx - 24, base_y - 78, cx + 24, base_y - 28], 180, 360, fill=(44, 34, 24))
    draw.rectangle([cx - 24, base_y - 53, cx + 24, base_y], fill=(44, 34, 24))


def _load_stage_portrait(config: PipelineConfig, stage: str) -> Image.Image:
    """Load the cropped stage portrait (never modifies existing reference files)."""
    crop_path = config.references_dir / f"ref_{stage}.png"
    if crop_path.exists() and crop_path.stat().st_size > 0:
        return Image.open(crop_path).convert("RGBA")

    # Fallback: read-only crop in memory from an existing 3-panel candidate
    for cand_name in (
        "character_sheet_selected.png",
        "character_sheet_candidate_2.png",
        "character_sheet_candidate_1.png",
        "character_sheet_candidate_3.png",
    ):
        cand_path = config.references_dir / cand_name
        if cand_path.exists() and cand_path.stat().st_size > 0:
            sheet = Image.open(cand_path).convert("RGBA")
            w, h = sheet.size
            idx = {"childhood": 0, "adolescence": 1, "young_adulthood": 2}[stage]
            x0 = int(idx * w / 3) + 8
            x1 = int((idx + 1) * w / 3) - 8
            return sheet.crop((x0, 8, x1, h - 8))

    raise NonRetryableError(
        f"No existing character reference image found in {config.references_dir} for stage '{stage}'."
    )


def _composite_feathered_portrait(
    canvas: Image.Image,
    portrait: Image.Image,
    target_h: int,
    center_x: int,
    top_y: int,
    warmth: float = 1.0,
) -> Image.Image:
    """Scale, color-balance, feather, and blend a stage portrait onto the scene canvas."""
    scale = target_h / portrait.height
    target_w = int(round(portrait.width * scale))
    resized = portrait.resize((target_w, target_h), Image.Resampling.LANCZOS)

    if warmth != 1.0:
        rgb = ImageEnhance.Color(resized.convert("RGB")).enhance(warmth)
        resized = rgb.convert("RGBA")

    mask = Image.new("L", (target_w, target_h), 0)
    mdraw = ImageDraw.Draw(mask)
    pad_x = int(target_w * 0.17)
    pad_top = int(target_h * 0.12)
    pad_bot = int(target_h * 0.14)
    mdraw.ellipse(
        [pad_x, pad_top, target_w - pad_x, target_h - pad_bot],
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius=30))

    out = canvas.convert("RGBA")
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
    layer.paste(resized, (center_x - target_w // 2, top_y), mask)
    return Image.alpha_composite(out, layer)


def _render_stage1_childhood(config: PipelineConfig) -> Image.Image:
    """Childhood (8-10 yrs): Rural Ethiopian Qolo Temari learning in shaded church courtyard."""
    canvas = _vertical_gradient(SIZE, SIZE, (108, 148, 178), (242, 208, 150))
    draw = ImageDraw.Draw(canvas)

    # Morning highland sun glow
    sun_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sun_layer)
    sdraw.ellipse([80, 40, 420, 380], fill=(255, 234, 172, 110))
    sun_layer = sun_layer.filter(ImageFilter.GaussianBlur(radius=45))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), sun_layer).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # Terraced rural highlands, traditional tukuls, and stone church in midground
    _draw_highland_hills(draw, SIZE, 470, 55, 4.2, 0.4, (112, 134, 96), SIZE)
    _draw_highland_hills(draw, SIZE, 560, 42, 3.6, 2.0, (82, 108, 66), SIZE)
    _draw_traditional_tukul(draw, 145, 575, 110, 105)
    _draw_traditional_tukul(draw, 255, 595, 86, 82)
    _draw_stone_church(draw, 855, 590)

    # Shaded church-courtyard stone wall & ground
    draw.rectangle([0, 595, SIZE, SIZE], fill=(134, 120, 98))
    for sx in range(0, SIZE, 78):
        draw.rectangle([sx + 4, 605, sx + 72, 650], fill=(148, 134, 112), outline=(104, 92, 74))

    # Overhead courtyard shade tree foliage (soft dappled canopy)
    canopy = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(canopy)
    cdraw.ellipse([-120, -140, 460, 260], fill=(48, 78, 42, 210))
    cdraw.ellipse([580, -130, 1160, 240], fill=(44, 72, 38, 200))
    canopy = canopy.filter(ImageFilter.GaussianBlur(radius=18))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), canopy)

    # Blend real childhood portrait (consistent face)
    portrait = _load_stage_portrait(config, "childhood")
    canvas = _composite_feathered_portrait(canvas, portrait, target_h=620, center_x=512, top_y=185, warmth=1.05)

    # Traditional white cotton netela wrap with subtle Ethiopian tibeb border + brana manuscript
    netela_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ndraw = ImageDraw.Draw(netela_layer)
    ndraw.polygon(
        [(310, 650), (400, 588), (512, 622), (624, 588), (714, 650), (755, 935), (269, 935)],
        fill=(244, 241, 232, 236),
    )
    ndraw.polygon(
        [(350, 624), (432, 594), (512, 668), (592, 594), (674, 624), (642, 795), (382, 795)],
        fill=(250, 248, 240, 226),
    )
    netela_layer = netela_layer.filter(ImageFilter.GaussianBlur(radius=2))
    canvas = Image.alpha_composite(canvas, netela_layer)

    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    # Understated traditional tibeb border (gold, green, crimson thin lines)
    odraw.rectangle([274, 845, 750, 868], fill=(224, 216, 198, 245))
    odraw.line([(274, 850), (750, 850)], fill=(184, 140, 48, 245), width=4)
    odraw.line([(274, 857), (750, 857)], fill=(48, 108, 62, 245), width=4)
    odraw.line([(274, 864), (750, 864)], fill=(156, 48, 44, 245), width=4)

    # Open parchment brana reading manuscript resting respectfully in foreground
    odraw.polygon([(352, 815), (508, 830), (496, 985), (326, 962)], fill=(232, 214, 174, 250), outline=(132, 106, 68, 255))
    odraw.polygon([(516, 830), (672, 815), (698, 962), (528, 985)], fill=(238, 220, 182, 250), outline=(132, 106, 68, 255))
    odraw.line([(512, 828), (512, 985)], fill=(108, 82, 48, 255), width=4)
    # Clean non-garbled ruled ink lines (no pseudo-text glyphs)
    for ly in range(852, 948, 18):
        odraw.line([(365, ly), (485, ly + 8)], fill=(116, 84, 56, 170), width=2)
        odraw.line([(540, ly + 8), (660, ly)], fill=(116, 84, 56, 170), width=2)

    return Image.alpha_composite(canvas, overlay).convert("RGB")


def _render_stage2_adolescence(config: PipelineConfig) -> Image.Image:
    """Adolescence (15-17 yrs): Rural Ethiopian high-school student in classroom with highland view."""
    canvas = _vertical_gradient(SIZE, SIZE, (206, 198, 178), (168, 152, 126)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # Green classroom chalkboard on left-center
    draw.rectangle([55, 110, 620, 495], fill=(38, 72, 52), outline=(124, 88, 52), width=12)
    # Crisp geometric math / science diagrams on chalkboard (no unreadable AI text)
    draw.polygon([(115, 360), (245, 360), (245, 220)], outline=(235, 240, 228), width=3)
    draw.line([(115, 415), (295, 415)], fill=(215, 230, 212), width=2)
    draw.line([(135, 435), (135, 385)], fill=(215, 230, 212), width=2)
    # Coordinate parabola sketch
    curve_pts = [(120 + i * 8, 415 - int(0.45 * (i - 10) ** 2)) for i in range(21)]
    draw.line(curve_pts, fill=(244, 218, 146), width=3)

    # Classroom window on right showing rural Ethiopian highland hills & daylight
    draw.rectangle([668, 95, 975, 485], fill=(142, 188, 222), outline=(118, 86, 56), width=12)
    _draw_highland_hills(draw, 965, 390, 28, 3.8, 0.7, (92, 128, 84), 475)
    _draw_highland_hills(draw, 965, 430, 18, 4.2, 2.2, (68, 104, 62), 475)
    # Re-paint wall cleanly to the left of the window so hills stay strictly inside window frame
    draw.rectangle([0, 95, 668, 495], fill=(192, 182, 160))
    draw.rectangle([55, 110, 620, 495], fill=(38, 72, 52), outline=(124, 88, 52), width=12)
    draw.polygon([(115, 360), (245, 360), (245, 220)], outline=(235, 240, 228), width=3)
    draw.line(curve_pts, fill=(244, 218, 146), width=3)
    draw.rectangle([668, 95, 975, 485], outline=(118, 86, 56), width=12)
    draw.line([(822, 95), (822, 485)], fill=(118, 86, 56), width=8)
    draw.line([(668, 290), (975, 290)], fill=(118, 86, 56), width=8)

    # Soft window sunlight beam
    beam = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(beam)
    bdraw.polygon([(668, 110), (975, 110), (760, 760), (340, 760)], fill=(255, 242, 200, 48))
    beam = beam.filter(ImageFilter.GaussianBlur(radius=28))
    canvas = Image.alpha_composite(canvas, beam)

    # Blend real adolescent portrait (consistent face + school sweater)
    portrait = _load_stage_portrait(config, "adolescence")
    canvas = _composite_feathered_portrait(canvas, portrait, target_h=640, center_x=512, top_y=165, warmth=1.02)

    # Backpack strap, wooden classroom desk, open math/coding notebooks, and computer corner
    fg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(fg)
    # Backpack strap anchored over left shoulder
    fdraw.polygon([(382, 548), (424, 558), (392, 785), (346, 785)], fill=(44, 58, 78, 235), outline=(28, 36, 50, 245))
    # Wooden school desk foreground
    fdraw.rectangle([0, 785, SIZE, SIZE], fill=(132, 92, 54, 250))
    fdraw.line([(0, 785), (SIZE, 785)], fill=(94, 62, 34, 255), width=6)
    # Open exercise notebook
    fdraw.polygon([(220, 825), (470, 825), (495, 975), (195, 975)], fill=(242, 238, 224, 250), outline=(88, 76, 62, 255))
    fdraw.line([(345, 825), (345, 975)], fill=(180, 96, 96, 200), width=2)
    for ny in range(850, 958, 18):
        fdraw.line([(236, ny), (332, ny)], fill=(120, 148, 188, 180), width=2)
        fdraw.line([(360, ny), (464, ny)], fill=(120, 148, 188, 180), width=2)
    # School desktop monitor side edge on right
    fdraw.rounded_rectangle([740, 625, 965, 790], radius=12, fill=(28, 38, 52, 248), outline=(74, 92, 114, 255), width=5)
    fdraw.rectangle([758, 643, 947, 768], fill=(38, 68, 96, 240))
    fdraw.rectangle([832, 790, 872, 822], fill=(42, 48, 58, 255))

    return Image.alpha_composite(canvas, fg).convert("RGB")


def _render_stage3_young_adulthood(config: PipelineConfig) -> Image.Image:
    """Young Adulthood (23-26 yrs): Ethiopian AI developer in modern workspace connected to roots."""
    canvas = _vertical_gradient(SIZE, SIZE, (218, 226, 232), (178, 184, 188)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # Large modern office window on right showing the Ethiopian highland valley (cultural roots)
    draw.rectangle([620, 75, 972, 520], fill=(138, 184, 220), outline=(78, 86, 94), width=10)
    _draw_highland_hills(draw, 965, 410, 32, 3.6, 0.5, (86, 122, 80), 512)
    _draw_highland_hills(draw, 965, 455, 20, 4.4, 2.1, (64, 98, 58), 512)
    draw.rectangle([0, 75, 620, 520], fill=(214, 218, 220))
    draw.rectangle([620, 75, 972, 520], outline=(78, 86, 94), width=10)
    draw.line([(796, 75), (796, 520)], fill=(78, 86, 94), width=6)

    # Modern AI workstation monitor on left-center displaying neural graph + loss curve
    draw.rounded_rectangle([65, 165, 470, 475], radius=14, fill=(24, 32, 46), outline=(56, 68, 84), width=8)
    draw.rectangle([85, 185, 450, 445], fill=(16, 26, 40))
    # Neural network node graph on monitor (clean geometric nodes, zero garbled text)
    nodes_l = [(135, 255), (135, 320), (135, 385)]
    nodes_m = [(245, 235), (245, 300), (245, 365), (245, 415)]
    nodes_r = [(355, 285), (355, 355)]
    for x1, y1 in nodes_l:
        for x2, y2 in nodes_m:
            draw.line([(x1, y1), (x2, y2)], fill=(58, 140, 196), width=2)
    for x1, y1 in nodes_m:
        for x2, y2 in nodes_r:
            draw.line([(x1, y1), (x2, y2)], fill=(96, 202, 238), width=2)
    for nx, ny in nodes_l + nodes_m + nodes_r:
        draw.ellipse([nx - 8, ny - 8, nx + 8, ny + 8], fill=(144, 228, 255))

    # Modern AI workstation monitor stand + separate subtle Ethiopian woven mesob accent on right desk corner
    draw.rectangle([244, 475, 292, 545], fill=(56, 68, 84))
    draw.rectangle([205, 545, 330, 560], fill=(44, 54, 68))

    # Blend real young-adult portrait (same person, modern shirt & earth-toned jacket)
    portrait = _load_stage_portrait(config, "young_adulthood")
    canvas = _composite_feathered_portrait(canvas, portrait, target_h=650, center_x=540, top_y=155, warmth=1.0)

    # Foreground modern desk + sleek open silver laptop + small decorative mesob on far right
    fg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(fg)
    fdraw.rectangle([0, 775, SIZE, SIZE], fill=(166, 134, 98, 250))
    fdraw.line([(0, 775), (SIZE, 775)], fill=(118, 92, 62, 255), width=5)
    fdraw.polygon([(835, 775), (885, 695), (935, 775)], fill=(176, 134, 74, 245))
    fdraw.line([(850, 750), (920, 750)], fill=(146, 54, 48, 245), width=4)
    # Open silver laptop lid & base in center-right foreground
    fdraw.polygon([(375, 760), (695, 760), (725, 920), (345, 920)], fill=(186, 194, 202, 252), outline=(104, 112, 122, 255))
    fdraw.polygon([(392, 774), (678, 774), (700, 898), (370, 898)], fill=(22, 34, 50, 250))
    fdraw.polygon([(345, 920), (725, 920), (765, 988), (305, 988)], fill=(208, 214, 220, 255), outline=(112, 118, 126, 255))
    # Subtle AI telemetry curve inside laptop screen
    lcurve = [(395 + i * 16, 855 - int(26 * math.sin(i * 0.45))) for i in range(17)]
    fdraw.line(lcurve, fill=(116, 216, 255, 235), width=3)

    return Image.alpha_composite(canvas, fg).convert("RGB")


def generate_offline_heritage_references(config: PipelineConfig) -> list[Path]:
    """Generate three NEW Pillow PNG character reference images in `outputs/references/`."""
    config.ensure_directories()
    renderers = {
        "childhood": _render_stage1_childhood,
        "adolescence": _render_stage2_adolescence,
        "young_adulthood": _render_stage3_young_adulthood,
    }
    created: list[Path] = []
    for spec in STAGE_SPECS:
        img = renderers[spec.stage](config)
        out_path = config.references_dir / spec.filename
        img.save(out_path, format="PNG")
        created.append(out_path)
    return created
