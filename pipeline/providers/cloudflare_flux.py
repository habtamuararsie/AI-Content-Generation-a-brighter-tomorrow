"""Cloudflare Workers AI (FLUX) image generation and token verification client."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.config import PipelineConfig, validate_cloudflare_settings
from pipeline.retry import NonRetryableError, classify_http_status, run_with_retry


@dataclass(frozen=True)
class ImageGenerationResult:
    """Metadata returned from generating one reference or keyframe PNG."""

    output_path: Path
    provider: str
    model: str
    width: int
    height: int
    seed: int


def get_token_verify_url(account_id: str, token_type: str = "user") -> str:
    """Return the correct Cloudflare token verification endpoint.

    User-owned API tokens verify against `/client/v4/user/tokens/verify`.
    Account-owned API tokens verify against `/client/v4/accounts/{account_id}/tokens/verify`.
    """
    normalized = token_type.strip().lower()
    if normalized == "account":
        if not account_id:
            raise ValueError("account_id is required when verifying an account-owned token.")
        return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/tokens/verify"
    if normalized == "user":
        return "https://api.cloudflare.com/client/v4/user/tokens/verify"
    raise ValueError(f"Unsupported token_type '{token_type}'. Expected 'user' or 'account'.")


def verify_cloudflare_token(config: PipelineConfig) -> dict[str, Any]:
    """Verify the configured Cloudflare API token without running inference."""
    require_acct = config.cloudflare_token_type == "account"
    issues = validate_cloudflare_settings(config, require_account_id=require_acct)
    if issues:
        raise NonRetryableError("Cloudflare configuration error:\n- " + "\n- ".join(issues))
    try:
        import requests  # type: ignore
    except ImportError as exc:
        raise NonRetryableError("requests package is required. Run `pip install -r requirements.txt`.") from exc

    url = get_token_verify_url(config.cloudflare_account_id, config.cloudflare_token_type)
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {config.cloudflare_api_token}"},
        timeout=20,
    )
    if resp.status_code >= 400:
        raise classify_http_status(resp.status_code, resp.text[:300])
    return resp.json()


def generate_flux_image(
    config: PipelineConfig,
    prompt: str,
    output_path: Path,
    width: int = 1024,
    height: int = 576,
    seed: int = 42,
    reference_images: list[Path] | None = None,
    model_override: str | None = None,
) -> ImageGenerationResult:
    """Call Cloudflare Workers AI FLUX endpoint (blocked unless `allow_paid_api=True`)."""
    if not config.allow_paid_api:
        raise NonRetryableError(
            "External Cloudflare Workers AI calls are blocked because ALLOW_PAID_API=false. "
            "Set ALLOW_PAID_API=true or pass explicit approval before generating images."
        )
    issues = validate_cloudflare_settings(config, require_account_id=True)
    if issues:
        raise NonRetryableError("Cloudflare configuration error:\n- " + "\n- ".join(issues))

    try:
        import requests  # type: ignore
    except ImportError as exc:
        raise NonRetryableError("requests package is required. Run `pip install -r requirements.txt`.") from exc

    model = model_override or config.image_model
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{config.cloudflare_account_id}/ai/run/{model}"
    )

    def _call() -> bytes:
        headers = {"Authorization": f"Bearer {config.cloudflare_api_token}"}
        if "flux-2-klein" in model:
            # flux-2-klein requires multipart/form-data and fixed 4 steps (do not send steps)
            form_fields: list[tuple[str, tuple[None, str] | tuple[str, bytes, str]]] = [
                ("prompt", (None, prompt)),
                ("width", (None, str(width))),
                ("height", (None, str(height))),
                ("seed", (None, str(seed))),
            ]
            for idx, ref_path in enumerate((reference_images or [])[:4]):
                form_fields.append(
                    (f"image_{idx}", (ref_path.name, ref_path.read_bytes(), "image/png"))
                )
            resp = requests.post(url, headers=headers, files=form_fields, timeout=120)
        else:
            payload = {"prompt": prompt, "width": width, "height": height, "seed": seed}
            resp = requests.post(url, headers=headers, json=payload, timeout=120)

        if resp.status_code >= 400:
            raise classify_http_status(resp.status_code, resp.text[:400])

        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            data = resp.json()
            b64_img = data.get("result", {}).get("image")
            if not b64_img:
                raise NonRetryableError(f"Unexpected Cloudflare JSON response: {data}")
            return base64.b64decode(b64_img)
        return resp.content

    image_bytes = run_with_retry(_call)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)
    return ImageGenerationResult(
        output_path=output_path,
        provider="cloudflare_workers_ai",
        model=model,
        width=width,
        height=height,
        seed=seed,
    )
