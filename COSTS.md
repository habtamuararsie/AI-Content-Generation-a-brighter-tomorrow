# Costs & Latency Ledger — A Brighter Tomorrow

> **Honesty Policy:** Verified official provider pricing is listed separately from measured runtime data. Do **not** present estimated image counts, GPU availability, or generation times as verified measurements.

## 1. Verified Provider Pricing & Free Tiers (From Official Documentation)

| Provider / Model | Free Tier / License | Official Paid Pricing | Verification Source |
| :--- | :--- | :--- | :--- |
| **Gemini 3.8 Flash** (`gemini-3.8-flash`) | Free tier available (rate-limited) | Intro through Dec 31, 2026: `$0.75`/1M input tokens, `$3.75`/1M output tokens (`$1.50` / `$7.50` starting Jan 1, 2027) | [ai.google.dev](https://ai.google.dev/) |
| **Gemini 3.8 Flash TTS** (`gemini-3.8-flash-tts`) | Free tier available (rate-limited; verify in AI Studio) | Preview through Dec 31, 2026: `$0.50`/1M text input, `$9.00`/1M audio output (`$1.00` / `$18.00` starting Jan 1, 2027) | [ai.google.dev/gemini-api/docs/speech-generation](https://ai.google.dev/gemini-api/docs/speech-generation) |
| **Cloudflare Workers AI** (`@cf/black-forest-labs/flux-2-klein-4b`) | **10,000 Neurons/day free** (resets `00:00 UTC`); Apache 2.0 | `$0.011` per 1,000 Neurons over free daily allocation (Workers Paid plan) | [developers.cloudflare.com/workers-ai/platform/pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) |
| **Wan 2.2 TI2V-5B** (`Wan-AI/Wan2.2-TI2V-5B`) | Open weights (**Apache 2.0**) | Free weights; cloud GPU compute varies by provider/tier | [huggingface.co/Wan-AI/Wan2.2-TI2V-5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) |
| **ACE-Step 1.5** (`ACE-Step/Ace-Step1.5`) | Open weights (**MIT License**) | Free weights; cloud GPU compute varies by provider/tier | [github.com/ACE-Step/ACE-Step-1.5](https://github.com/ACE-Step/ACE-Step-1.5) |
| **FFmpeg** | Free & open source | `$0.00` (local CPU) | [ffmpeg.org](https://www.ffmpeg.org/) |

---

## 2. Measured Pipeline Costs & Latency (From `logs/runs.jsonl` & Local Zero-Cost Run)

| Stage | Provider / Model | Hardware Used | Calls (Cache Misses) | Estimated / Actual Cost | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Stage 1 (Character Ref) | Existing `character_sheet_candidate_2.png` + FFmpeg 3-stage crops | Local CPU (FFmpeg) | Reused existing | `$0.00` | Preserved original candidates; cropped `ref_{childhood,adolescence,young_adulthood}.png`. |
| Stage 2 (Validation) | Local validator | Local CPU | Local | `$0.00` | `10` shots + `3.0s` end card = `80.0s` storyboard target. |
| Stage 3 (Keyframes) | `external_local` (`external_manual` PNG/JPEG import) + fallback `offline_local` | External manual + Local CPU | 10 shots | `$0.00` | Preserves original files untouched; zero external API calls (`ALLOW_PAID_API=false`). |
| Stage 3 (Moving Shots) | `ken_burns` (`ffmpeg_zoompan` 1080p `16:9` + native `1080x1920` `9:16`) | Local CPU (FFmpeg) | 10 + 10 clips | `$0.00` | Zero GPU minutes used. |
| Stage 4 (Narration & Music) | `local_tts` (`windows_winrt:Microsoft George` v2) + `local_score` (`procedural_pentatonic_heritage_82bpm_v2`) | Local CPU (WinRT TTS + FFmpeg + Python WAV) | 10 + 1 | `$0.00` | Dry clarity-EQ English narration (`4.25s`–`6.76s`/shot) and original pentatonic heritage-inspired score (`80.107s`), `is_placeholder: false`. |
| Stage 6 (FFmpeg Assembly) | `ffmpeg` (`libx264_aac_loudnorm`) | Local CPU (FFmpeg) | 2 exports (`16:9`, `9:16`) | `$0.00` | Both exports measured `80.014s` (`24 fps`, `48 kHz` AAC, `-14.2 LUFS` / `-1.0 dBFS`) via `ffprobe` & `ebur128`. |
