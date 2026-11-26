# A Brighter Tomorrow — AI-Assisted Short Film Pipeline

**Subtitle:** *From Our Roots to Our Future*  
**Format:** 60–90 second realistic documentary short film (10 narrative shots + 3.0s AI disclosure end card; target ~80s total) in `16:9` and `9:16`.

> **Current Workflow (`external_local` + Free Local Narration & Original Score):** External PNG/JPG/JPEG keyframes placed in `outputs/keyframes/` are validated via [`external_images.py`](pipeline/providers/external_images.py), animated with FFmpeg Ken Burns (`1080p` `16:9` and native `1080x1920` `9:16`), narrated offline with `local_tts` (Windows WinRT/SAPI5 speech synthesis or POSIX `espeak-ng`/`espeak`/`say` fallback), scored with `local_score` (original 82 BPM D-major multi-instrument procedural film score synced to `storyboard.json` cues), and assembled with `.srt` subtitles, sidechain ducking, `-14 LUFS` normalization, and a 3.0s AI disclosure end card at **$0.00 API cost** (`ALLOW_PAID_API=false`). Live cloud providers (`gemini_tts`, `cloudflare_flux`, `wan22`, `ace_step_15`) remain supported via CLI/env when credentials and GPU runs are enabled.

---

## 1. Prerequisites & Local Setup

### Windows PowerShell
1. **Install FFmpeg** (required for `radio_cut.mp4`, Ken Burns fallback, and final MP4 exports):
   ```powershell
   winget install Gyan.FFmpeg
   ```
   Restart your terminal and confirm (note: `pipeline/config.py` also auto-resolves WinGet `Gyan.FFmpeg` executables even if `PATH` has not refreshed):
   ```powershell
   ffmpeg -version
   ```
2. **Create a Python virtual environment and install dependencies:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. **Create `.env` from template (never commit `.env`):**
   ```powershell
   Copy-Item .env.example .env
   ```

### Linux / Google Colab Bash
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

---

## 2. Running Offline Tests & Validation (Zero API Cost)

Run these commands first to verify the repository on your machine:

```powershell
# 1. Run all offline unit & smoke tests
python -m unittest discover -s tests -v

# 2. Validate storyboard.json against storyboard.schema.json (10 shots + 3s end card = 80s)
python -m pipeline.cli validate

# 3. Generate the offline draft Radio Cut (placeholder audio + synced .srt + mix WAV)
python -m pipeline.cli radio-cut
```

*(If `make` is installed, you can also run `make test`, `make validate`, and `make radio-cut`.)*

---

## 3. Verifying External Credentials (Before Enabling Paid/Live APIs)

By default, `.env.example` sets `ALLOW_PAID_API=false` so no command accidentally spends quota.
See [ARCHITECTURE.md](ARCHITECTURE.md#4-credential-verification-guide-windows-powershell--colablinux) for separate **Windows PowerShell** and **Google Colab / Linux** commands to test:
* `GEMINI_API_KEY`
* `CLOUDFLARE_API_TOKEN` & `CLOUDFLARE_ACCOUNT_ID` (User token `/user/tokens/verify` vs. Account token `/accounts/{id}/tokens/verify`)
* `HF_TOKEN`

Or, after putting your Cloudflare values in `.env`, run:
```powershell
python -m pipeline.cli verify-cf
```

---

## 4. Pipeline Workflow & Gates

1. **Radio Cut Review:** Run `python -m pipeline.cli radio-cut`, listen to `outputs/exports/radio_cut_mix.wav` / `outputs/exports/radio_cut.mp4`, inspect `outputs/subtitles/subtitles.srt`, and log User Test #1 in [DESIGN.md](DESIGN.md).
2. **External Image Placement & Validation:** Place `shot_01` through `shot_10` (`.png`, `.jpg`, or `.jpeg`) inside `outputs/keyframes/` and run:
   ```powershell
   .\.venv\Scripts\python.exe -m pipeline.cli validate-images
   ```
3. **One-Command Zero-Cost Film Export:** Run the complete pipeline using external keyframes, offline spoken narration (`local_tts`), original procedural D-major score (`local_score`), and FFmpeg Ken Burns motion (zero paid API calls):
   ```powershell
   .\.venv\Scripts\python.exe -m pipeline.cli run-all --image-provider external_local --narration-provider local_tts --video-provider ken_burns --music-provider local_score
   ```
   *(Or `make film` when `make` is installed.)* Outputs: `outputs/exports/a_brighter_tomorrow_16x9.mp4` (`1920x1080`) and `outputs/exports/a_brighter_tomorrow_9x16.mp4` (`1080x1920`).
