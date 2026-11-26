"""Video provider adapters (Wan 2.2 / HunyuanVideo-1.5 GPU outputs + FFmpeg Ken Burns)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from pipeline.config import PipelineConfig
from pipeline.retry import NonRetryableError

SUPPORTED_VIDEO_PROVIDERS = ("wan22", "hunyuan15", "ken_burns")


@dataclass(frozen=True)
class PortraitFramingPreset:
    """Normalized 9:16 horizontal pan and relative zoom trajectory on a landscape keyframe."""

    cx0: float
    cx1: float
    z0: float = 1.0
    z1: float = 1.04
    cy: float = 0.44


# Curated per-shot 9:16 pan/zoom paths tuned against landscape keyframes so faces and
# key narrative props stay cleanly inside the vertical frame without edge slicing.
PORTRAIT_FRAMING_PRESETS: dict[str, PortraitFramingPreset] = {
    "shot_01": PortraitFramingPreset(cx0=0.30, cx1=0.72, z0=1.00, z1=1.04, cy=0.45),
    "shot_02": PortraitFramingPreset(cx0=0.50, cx1=0.50, z0=1.00, z1=1.06, cy=0.38),
    "shot_03": PortraitFramingPreset(cx0=0.50, cx1=0.50, z0=1.06, z1=1.00, cy=0.40),
    "shot_04": PortraitFramingPreset(cx0=0.48, cx1=0.52, z0=1.00, z1=1.05, cy=0.40),
    "shot_05": PortraitFramingPreset(cx0=0.39, cx1=0.72, z0=1.00, z1=1.07, cy=0.72),
    "shot_06": PortraitFramingPreset(cx0=0.34, cx1=0.63, z0=1.02, z1=1.04, cy=0.00),
    "shot_07": PortraitFramingPreset(cx0=0.38, cx1=0.61, z0=1.00, z1=1.02, cy=0.40),
    "shot_08": PortraitFramingPreset(cx0=0.40, cx1=0.64, z0=1.00, z1=1.02, cy=0.42),
    "shot_09": PortraitFramingPreset(cx0=0.21, cx1=0.72, z0=1.00, z1=1.02, cy=0.42),
    "shot_10": PortraitFramingPreset(cx0=0.28, cx1=0.72, z0=1.00, z1=1.02, cy=0.45),
}


@dataclass(frozen=True)
class VideoClipResult:
    """Result metadata for one generated or resolved shot video clip."""

    output_path: Path
    provider: str
    model: str
    duration_sec: float
    hardware: str
    is_fallback: bool


def _read_image_dimensions(image_path: Path) -> tuple[int, int]:
    """Read pixel width and height from a keyframe image."""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
    except OSError as exc:
        raise NonRetryableError(f"Unable to read keyframe dimensions for {image_path}: {exc}") from exc
    if w <= 0 or h <= 0:
        raise NonRetryableError(f"Invalid keyframe dimensions ({w}x{h}) for {image_path}")
    return w, h


def _default_portrait_preset(shot_index: int) -> PortraitFramingPreset:
    """Return a deterministic alternating portrait pan/zoom preset for unmapped shots."""
    mode = shot_index % 4
    if mode == 0:
        return PortraitFramingPreset(cx0=0.36, cx1=0.64, z0=1.00, z1=1.04, cy=0.42)
    if mode == 1:
        return PortraitFramingPreset(cx0=0.64, cx1=0.36, z0=1.04, z1=1.00, cy=0.42)
    if mode == 2:
        return PortraitFramingPreset(cx0=0.48, cx1=0.52, z0=1.00, z1=1.06, cy=0.40)
    return PortraitFramingPreset(cx0=0.52, cx1=0.48, z0=1.06, z1=1.00, cy=0.40)


def _even_int(value: float, minimum: int = 2) -> int:
    """Round a positive number to the nearest even integer at or above minimum."""
    return max(minimum, int(round(value / 2.0) * 2))


def build_ken_burns_filter(
    src_width: int,
    src_height: int,
    frames: int,
    shot_index: int = 0,
    fps: int = 24,
    width: int = 1920,
    height: int = 1080,
    shot_id: str | None = None,
) -> str:
    """Build an FFmpeg zoompan filtergraph preserving aspect ratio for 16:9 and 9:16 outputs."""
    frames = max(1, frames)
    ar_in = src_width / src_height
    ar_out = width / height

    # For wide keyframes rendered into portrait targets (e.g. 3:2 / 16:9 -> 9:16), pad vertically
    # to the target aspect ratio and base zoom at pad_h / work_h so zoompan can pan smoothly across
    # the entire landscape width without pre-cropping subjects off or introducing black bars.
    if height > width and ar_in > ar_out * 1.01:
        preset = PORTRAIT_FRAMING_PRESETS.get(shot_id) if shot_id else None
        if preset is None:
            preset = _default_portrait_preset(shot_index)

        work_h = max(2400, _even_int(height * 1.25))
        work_w = _even_int(work_h * ar_in)
        pad_h = max(work_h, _even_int(work_w / ar_out))
        y_off = (pad_h - work_h) // 2
        base_z = pad_h / work_h

        z0 = max(1.0, preset.z0)
        z1 = max(1.0, preset.z1)
        z_expr = f"{base_z:.6f}*({z0:.4f}+({z1 - z0:.4f})*on/{frames})"
        cx_expr = f"iw*({preset.cx0:.4f}+({preset.cx1 - preset.cx0:.4f})*on/{frames})"
        x_expr = f"clip({cx_expr}-(iw/zoom/2),0,iw-iw/zoom)"
        cy_abs = y_off + work_h * min(1.0, max(0.0, preset.cy))
        y_expr = f"clip({cy_abs:.2f}-(ih/zoom/2),{y_off},{y_off}+{work_h}-ih/zoom)"
        return (
            f"scale={work_w}:{work_h},pad={work_w}:{pad_h}:0:{y_off}:black,"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
            f"d={frames}:s={width}x{height}:fps={fps},format=yuv420p"
        )

    # Smooth, gentle documentary zoom + subtle pan across consecutive landscape shots without stretching
    mode = shot_index % 4
    if mode == 0:
        # Gentle slow zoom-in centered slightly above middle to protect faces
        zoom_expr = f"1.0+0.07*on/{frames}"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih*0.44-(ih/zoom/2)"
    elif mode == 1:
        # Gentle slow zoom-out from 1.08 to 1.00
        zoom_expr = f"1.08-0.08*on/{frames}"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih*0.44-(ih/zoom/2)"
    elif mode == 2:
        # Subtle left-to-right drift with light zoom
        zoom_expr = f"1.04+0.04*on/{frames}"
        x_expr = f"(iw-iw/zoom)*(0.38+0.24*on/{frames})"
        y_expr = "ih*0.44-(ih/zoom/2)"
    else:
        # Subtle right-to-left drift with light zoom
        zoom_expr = f"1.08-0.04*on/{frames}"
        x_expr = f"(iw-iw/zoom)*(0.62-0.24*on/{frames})"
        y_expr = "ih*0.44-(ih/zoom/2)"

    return (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2}:(iw-ow)/2:(ih-oh)*0.35,"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
        f"d={frames}:s={width}x{height}:fps={fps},format=yuv420p"
    )


def render_ken_burns_clip(
    ffmpeg_bin: str,
    keyframe_path: Path,
    output_path: Path,
    duration_sec: float,
    shot_index: int = 0,
    fps: int = 24,
    width: int = 1920,
    height: int = 1080,
    shot_id: str | None = None,
) -> VideoClipResult:
    """Render a deterministic slow zoom/pan clip from a still keyframe via FFmpeg."""
    if not keyframe_path.exists():
        raise NonRetryableError(f"Missing keyframe for Ken Burns fallback: {keyframe_path}")

    src_w, src_h = _read_image_dimensions(keyframe_path)
    frames = max(1, int(round(duration_sec * fps)))
    vf = build_ken_burns_filter(
        src_width=src_w,
        src_height=src_h,
        frames=frames,
        shot_index=shot_index,
        fps=fps,
        width=width,
        height=height,
        shot_id=shot_id,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(keyframe_path),
        "-vf",
        vf,
        "-t",
        f"{duration_sec:.3f}",
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise NonRetryableError(
            f"FFmpeg binary '{ffmpeg_bin}' was not found on PATH. Install FFmpeg first."
        ) from exc

    if proc.returncode != 0:
        raise NonRetryableError(f"FFmpeg Ken Burns failed: {proc.stderr[-400:]}")

    return VideoClipResult(
        output_path=output_path,
        provider="ken_burns",
        model="ffmpeg_zoompan",
        duration_sec=duration_sec,
        hardware="cpu",
        is_fallback=True,
    )


def resolve_shot_video(
    config: PipelineConfig,
    shot_id: str,
    shot_index: int,
    duration_sec: float,
    keyframe_path: Path,
    allow_ken_burns_fallback: bool = False,
) -> VideoClipResult:
    """Resolve a shot clip using the configured video provider.

    GPU providers (`wan22`, `hunyuan15`) consume clips produced in Google Colab / Kaggle
    and placed in `outputs/clips/{shot_id}.mp4`. They never pretend a missing clip exists.
    """
    provider = config.video_provider
    if provider not in SUPPORTED_VIDEO_PROVIDERS:
        raise NonRetryableError(
            f"Unsupported VIDEO_PROVIDER '{provider}'. Choose one of: {SUPPORTED_VIDEO_PROVIDERS}."
        )

    expected_clip = config.clips_dir / f"{shot_id}.mp4"
    if provider in ("wan22", "hunyuan15"):
        if expected_clip.exists() and expected_clip.stat().st_size > 0:
            model_name = (
                "Wan-AI/Wan2.2-TI2V-5B" if provider == "wan22" else "tencent/HunyuanVideo-1.5"
            )
            return VideoClipResult(
                output_path=expected_clip,
                provider=provider,
                model=model_name,
                duration_sec=duration_sec,
                hardware="colab_or_kaggle_gpu_precomputed",
                is_fallback=False,
            )
        if not allow_ken_burns_fallback:
            raise NonRetryableError(
                f"GPU clip missing for {shot_id} at {expected_clip} (provider='{provider}'). "
                "Generate the clip in the Colab GPU notebook first, or pass --allow-ken-burns-fallback."
            )

    fallback_out = config.clips_dir / f"{shot_id}_ken_burns.mp4"
    return render_ken_burns_clip(
        ffmpeg_bin=config.ffmpeg_bin,
        keyframe_path=keyframe_path,
        output_path=fallback_out,
        duration_sec=duration_sec,
        shot_index=shot_index,
        shot_id=shot_id,
    )
