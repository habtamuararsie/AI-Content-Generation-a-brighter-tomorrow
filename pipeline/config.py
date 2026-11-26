"""Configuration loader for A Brighter Tomorrow.

Reads environment variables from `.env` (if present) and process environment
without ever storing or printing real API keys in logs or artifacts.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_file(env_path: Path) -> None:
    """Minimal fallback .env loader when python-dotenv is not installed."""
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=env_path, override=False)
        return
    except ImportError:
        pass

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_missing_or_placeholder(value: str | None) -> bool:
    """Return True when a credential value is empty or still an example placeholder."""
    if not value:
        return True
    cleaned = value.strip().lower()
    if not cleaned:
        return True
    if cleaned.startswith(("your_", "<", "paste_", "replace_")):
        return True
    return cleaned in {"changeme", "placeholder", "todo", "none"}


def resolve_executable(name_or_path: str) -> str:
    """Resolve an executable on PATH or common Windows WinGet FFmpeg locations."""
    found = shutil.which(name_or_path)
    if found:
        return found
    candidate_name = Path(name_or_path).name
    if not candidate_name.lower().endswith(".exe"):
        candidate_name_exe = f"{candidate_name}.exe"
    else:
        candidate_name_exe = candidate_name

    local_app = os.getenv("LOCALAPPDATA", "")
    if local_app:
        winget_root = Path(local_app) / "Microsoft" / "WinGet"
        links_cand = winget_root / "Links" / candidate_name_exe
        if links_cand.exists():
            return str(links_cand)
        packages_dir = winget_root / "Packages"
        if packages_dir.exists():
            for match in packages_dir.glob(f"Gyan.FFmpeg*/**/bin/{candidate_name_exe}"):
                if match.exists():
                    return str(match)
    return name_or_path


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable configuration resolved from repository root and environment."""

    root_dir: Path
    storyboard_path: Path
    schema_path: Path
    outputs_dir: Path
    logs_path: Path

    allow_paid_api: bool
    gemini_api_key: str
    gemini_text_model: str
    gemini_tts_model: str
    gemini_tts_voice: str

    cloudflare_account_id: str
    cloudflare_api_token: str
    cloudflare_token_type: str
    image_model: str
    image_fallback_model: str

    hf_token: str
    image_provider: str
    narration_provider: str
    video_provider: str
    music_provider: str

    ffmpeg_bin: str
    ffprobe_bin: str

    @property
    def references_dir(self) -> Path:
        return self.outputs_dir / "references"

    @property
    def keyframes_dir(self) -> Path:
        return self.outputs_dir / "keyframes"

    @property
    def clips_dir(self) -> Path:
        return self.outputs_dir / "clips"

    @property
    def narration_dir(self) -> Path:
        return self.outputs_dir / "narration"

    @property
    def music_dir(self) -> Path:
        return self.outputs_dir / "music"

    @property
    def subtitles_dir(self) -> Path:
        return self.outputs_dir / "subtitles"

    @property
    def manifests_dir(self) -> Path:
        return self.outputs_dir / "manifests"

    @property
    def exports_dir(self) -> Path:
        return self.outputs_dir / "exports"

    def ensure_directories(self) -> None:
        """Create expected output and log parent directories."""
        for folder in (
            self.references_dir,
            self.keyframes_dir,
            self.clips_dir,
            self.narration_dir,
            self.music_dir,
            self.subtitles_dir,
            self.manifests_dir,
            self.exports_dir,
            self.logs_path.parent,
        ):
            folder.mkdir(parents=True, exist_ok=True)


def load_config(root_dir: Path | str | None = None) -> PipelineConfig:
    """Load pipeline configuration relative to `root_dir` (defaults to repo root)."""
    repo_root = Path(root_dir).resolve() if root_dir else Path(__file__).resolve().parent.parent
    _load_dotenv_file(repo_root / ".env")

    return PipelineConfig(
        root_dir=repo_root,
        storyboard_path=repo_root / "storyboard.json",
        schema_path=repo_root / "storyboard.schema.json",
        outputs_dir=repo_root / "outputs",
        logs_path=repo_root / "logs" / "runs.jsonl",
        allow_paid_api=_as_bool(os.getenv("ALLOW_PAID_API"), default=False),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_text_model=os.getenv("GEMINI_TEXT_MODEL", "gemini-3.8-flash").strip(),
        gemini_tts_model=os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts").strip(),
        gemini_tts_voice=os.getenv("GEMINI_TTS_VOICE", "Charon").strip(),
        cloudflare_account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip(),
        cloudflare_api_token=os.getenv("CLOUDFLARE_API_TOKEN", "").strip(),
        cloudflare_token_type=os.getenv("CLOUDFLARE_TOKEN_TYPE", "user").strip().lower(),
        image_model=os.getenv("IMAGE_MODEL", "@cf/black-forest-labs/flux-2-klein-4b").strip(),
        image_fallback_model=os.getenv(
            "IMAGE_FALLBACK_MODEL", "@cf/black-forest-labs/flux-1-schnell"
        ).strip(),
        hf_token=os.getenv("HF_TOKEN", "").strip(),
        image_provider=os.getenv("IMAGE_PROVIDER", "external_local").strip(),
        narration_provider=os.getenv("NARRATION_PROVIDER", "placeholder").strip(),
        video_provider=os.getenv("VIDEO_PROVIDER", "ken_burns").strip(),
        music_provider=os.getenv("MUSIC_PROVIDER", "placeholder_temp").strip(),
        ffmpeg_bin=resolve_executable(os.getenv("FFMPEG_BIN", "ffmpeg").strip()),
        ffprobe_bin=resolve_executable(os.getenv("FFPROBE_BIN", "ffprobe").strip()),
    )


def validate_cloudflare_settings(
    config: PipelineConfig,
    require_account_id: bool = True,
) -> list[str]:
    """Validate Cloudflare configuration without making any network or paid API calls."""
    issues: list[str] = []
    env_file = config.root_dir / ".env"

    if require_account_id:
        acct = config.cloudflare_account_id
        if is_missing_or_placeholder(acct):
            issues.append(
                "Missing valid CLOUDFLARE_ACCOUNT_ID. "
                "Find it in Cloudflare Dashboard -> Account Home (or Workers & Pages) right sidebar."
            )
        elif "http" in acct.lower() or "/" in acct or any(ch.isspace() for ch in acct):
            issues.append(
                "CLOUDFLARE_ACCOUNT_ID looks like a URL or contains spaces. "
                "Paste only the 32-character Account ID string."
            )

    if is_missing_or_placeholder(config.cloudflare_api_token):
        issues.append(
            "Missing valid CLOUDFLARE_API_TOKEN. "
            "Create one at Cloudflare Dashboard -> My Profile -> API Tokens -> "
            "Create Token -> Workers AI template (Read & Edit)."
        )
    elif any(ch.isspace() for ch in config.cloudflare_api_token):
        issues.append("CLOUDFLARE_API_TOKEN contains whitespace; paste only the token string.")

    if config.cloudflare_token_type not in {"user", "account"}:
        issues.append(
            f"Invalid CLOUDFLARE_TOKEN_TYPE '{config.cloudflare_token_type}'. "
            "Use 'user' (My Profile -> API Tokens) or 'account' (Manage Account -> Account API Tokens)."
        )

    if is_missing_or_placeholder(config.image_model):
        issues.append(
            "Missing IMAGE_MODEL. Expected e.g. '@cf/black-forest-labs/flux-2-klein-4b'."
        )

    if issues and not env_file.exists():
        issues.insert(
            0,
            f".env file not found at {env_file}. Create it first with: Copy-Item .env.example .env",
        )

    return issues
