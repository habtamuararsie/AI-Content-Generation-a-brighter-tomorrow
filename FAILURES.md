# Failure & Troubleshooting Journal — A Brighter Tomorrow

> **Honesty Policy:** Record only real errors, blockers, and workarounds encountered during development and runs.

---

## Real Blockers Observed During Checkpoint 3 Setup

### `FAIL-01`: `ffmpeg` binary not found on Windows `PATH`
* **When Observed:** Checkpoint 3 environment preflight (`ffmpeg -version`).
* **Symptom:** `ffmpeg : The term 'ffmpeg' is not recognized as the name of a cmdlet, function, script file, or operable program.`
* **Impact:** Pure-Python validation, `.srt` subtitle generation, and `radio_cut_mix.wav` audio mixing work without FFmpeg, **but** rendering `radio_cut.mp4`, Ken Burns clips, and final `16:9` / `9:16` MP4 exports are blocked until FFmpeg is installed and resolved.
* **Workaround / Fix:**
  1. Installed `Gyan.FFmpeg` via `winget install Gyan.FFmpeg`.
  2. Added `resolve_executable()` in `pipeline/config.py` so WinGet-installed `ffmpeg.exe` / `ffprobe.exe` are automatically resolved even in terminal sessions whose `PATH` has not refreshed.

### `FAIL-03`: Windows FFmpeg `drawtext` failed with `Fontconfig error: Cannot load default config file`
* **When Observed:** First zero-cost `run-all` execution (`task-270`) during Stage 6 `render_end_card_clip`.
* **Symptom:** FFmpeg exited with code `1`: `Fontconfig error: Cannot load default config file: File not found`.
* **Impact:** `16:9` and `9:16` final MP4 export aborted when rendering the 3-second AI disclosure end card.
* **Workaround / Fix:** Added `_resolve_drawtext_font_arg()` in `pipeline/stage6_assemble.py` to pass an explicit `fontfile=` path (`C:/Windows/Fonts/arial.ttf` or fallback system font) and escaped colons in `drawtext` strings. Re-running `run-all` hit cache for all keyframes, clips, and narration and completed both `16:9` and `9:16` exports (`82.956s`).

### `FAIL-04`: Oversized `libass` subtitles overlapping faces in `9:16` vertical export
* **When Observed:** Visual frame inspection of `outputs/tmp/verify_frames/` after assembling the first `external_local` cut.
* **Symptom:** `FontSize=20,MarginV=110` (evaluated by `libass` against default `384x288` PlayRes) scaled up dramatically on the `1080x1920` vertical frame, causing large multi-line subtitles over the character's face.
* **Workaround / Fix:** Calibrated separate subtitle styles in `pipeline/stage6_assemble.py` (`FontSize=6,MarginL=12,MarginR=12,MarginV=24` for `9x16` and `FontSize=14,MarginL=24,MarginR=24,MarginV=20` for `16x9`), re-ran the full export, and verified clean lower-third caption placement on extracted frames (`9x16_t11.png`, `9x16_t52.png`, `16x9_t11.png`, `16x9_t52.png`).

### `FAIL-05`: Image container extension mismatches (`JPEG`/`WEBP` inside `.png`), scene swaps, and corner badges
* **When Observed:** Inspecting `outputs/keyframes/` with Pillow (`Image.open`) and visual inspection across user uploads.
* **Symptom:** Downloaded files used `.png` filenames while containing `JPEG` (`shot_01`, `03`–`07`, `10`) or `WEBP` (`shot_02`) image streams; initial drops also had missing/swapped scenes and AI corner badges/text overlays.
* **Workaround / Fix:** Extended `pipeline/providers/external_images.py` using Pillow `Image.open` + `im.verify()` so valid `PNG`, `JPEG`, and `WEBP` payloads load cleanly without modifying original user files, and documented remaining scene-order swaps and watermarks for final cleanup.

### `FAIL-02`: Optional third-party Python packages not yet installed in global Python `3.14.6`
* **When Observed:** Checkpoint 3 environment check (`python -m pip list`).
* **Symptom:** Global Python environment only contained `lxml`, `pip`, `python-docx`, and `typing_extensions` (missing `jsonschema`, `python-dotenv`, `requests`, `google-genai`, `pytest`).
* **Impact:** Live Gemini/Cloudflare API calls and `pytest` runner require installing `requirements.txt`.
* **Workaround / Fix:**
  1. Added pure-Python fallbacks for `.env` loading, basic schema checks, and `unittest`-compatible tests so offline validation and smoke tests pass immediately.
  2. Create a virtual environment and install `requirements.txt` before running live API calls:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     pip install -r requirements.txt
     ```
