# Experiments Log — A Brighter Tomorrow

> **Honesty Policy:** Only record experiments that were actually executed and backed by entries in `logs/runs.jsonl`. Do **not** fabricate results, latencies, or quality judgments.

**Current Status:** `0` live paid API experiments executed (`ALLOW_PAID_API=false`); `5` zero-cost offline/local runs (`EXP-01`–`EXP-05`) executed and logged in `logs/runs.jsonl`.

## Experiment Registry

| ID | Stage | Hypothesis | Status |
| :--- | :--- | :--- | :--- |
| `EXP-01` | Radio Cut | Draft narration (~156 words) fits cleanly inside 60–90s when timed with placeholder cues. | `EXECUTED (OFFLINE)` (`83.028s` in `qa_report.json`) |
| `EXP-02` | Offline Zero-Cost Full Cut | Combine existing `character_sheet_candidate_2.png` stage crops + local SVG/PNG backgrounds + FFmpeg Ken Burns + placeholder audio into `16:9` and `9:16` MP4s at `$0.00` API cost. | `EXECUTED (OFFLINE)` (`82.956s` measured via `ffprobe`) |
| `EXP-03` | External Keyframes + Native `16:9`/`9:16` Ken Burns | Importing all 10 user-supplied external keyframes (`external_local`) and rendering native `1920x1080` and `1080x1920` Ken Burns clips + calibrated captions yields sharp dual exports at `$0.00` API spend. | `EXECUTED (OFFLINE)` (`18.23 MB` `16:9`, `15.37 MB` `9:16`, `82.956s`, 0 black frames) |
| `EXP-04` | Free Local Spoken Narration + Original Procedural Score | Replacing placeholder cues with `local_tts` (`windows_winrt:Microsoft George`) and `local_score` (`procedural_d_major_82bpm_v1`, synced to storyboard cues) plus `48 kHz` AAC mastering eliminates placeholder audio warnings while preserving `$0.00` API spend. | `EXECUTED (LOCAL)` (`80.252s`, `-14.0 LUFS`, `0` QA warnings) |
| `EXP-05` | Audience Test #1 Audio Refinement (Dry Clarity EQ + Pentatonic Heritage Score) | Removing `220 Hz` TTS mud boost, tightening sidechain attack (`300ms` -> `45ms`), shortening pluck decay (`0.9965` -> `0.9915`), and replacing Western chords with pentatonic heritage-inspired synthesis improves voice clarity and cultural fit inside `60–90s`. | `EXECUTED (LOCAL)` (`80.014s`, `-14.2 LUFS`, `-1.0 dBFS`, `0` black frames) |
| `EXP-06` | Character Sheet | `flux-2-klein-4b` produces a recognizable 3-age character reference sheet across 3 candidate seeds. | `EXISTING CANDIDATES REUSED` (`candidate_1..3.png`) |
| `EXP-07` | Gemini TTS | `gemini-3.8-flash-tts` generates clear, unhurried English narration and fits within target shot budgets. | `PENDING APPROVAL` |
| `EXP-08` | Keyframes (API) | Conditioning shot keyframes on `character_sheet_selected.png` reduces facial drift vs. text-only prompts. | `PENDING APPROVAL` |
| `EXP-09` | Colab Video Smoke Test | Evaluate whether `Wan2.2-TI2V-5B` fits on available Colab GPU (480p + offloading vs. OOM) or requires fallback. | `PENDING COLAB TEST` |
| `EXP-10` | ACE-Step 1.5 Sample | Test short instrumental sample (~15–20s) in Colab and record VRAM, latency, and audio clarity. | `PENDING COLAB TEST` |

---

## Executed Experiment Entries

### `EXP-01` — Offline Radio Cut Timing Validation
* **Hypothesis:** Draft narration (156 words) timed with placeholder cues plus the 3.0s end card stays within the 60–90s requirement.
* **Result:** `qa_report.json` passed with `shots_duration_sec: 80.028`, `end_card_duration_sec: 3.0`, `total_duration_sec: 83.028`.

### `EXP-02` — Zero-Cost Offline End-to-End Film Production
* **Hypothesis:** Cropping `character_sheet_candidate_2.png` into 3 life-stage portraits and compositing them over locally generated Ethiopian heritage SVG/PNG scenes with FFmpeg Ken Burns motion yields a complete `16:9` and `9:16` film at `$0.00` API cost.
* **Result:** Both `outputs/exports/a_brighter_tomorrow_16x9.mp4` (`1920x1080`, `24 fps`, `82.956s`, `11.22 MB`) and `outputs/exports/a_brighter_tomorrow_9x16.mp4` (`1080x1920`, `24 fps`, `82.956s`, `12.95 MB`) rendered cleanly via local FFmpeg with `$0.00` API spend. Limitation: backgrounds are stylized vector/gradient scenes and audio uses offline placeholder cues (`is_placeholder: true`).

### `EXP-03` — External Keyframes + Native 1080p / 9:16 Ken Burns Assembly
* **Hypothesis:** Importing user-supplied external images (`external_local` via `external_images.py`) and rendering dedicated `1920x1080` (`16:9`) and `1080x1920` (`9:16`) Ken Burns clips from the full-resolution source images eliminates `9:16` double-crop blur while keeping `$0.00` API spend.
* **Result:** Verified via `validate-images`, `ffprobe`, `blackdetect` (0 black intervals), and frame extraction (`82.956s` duration on both `16:9` at `18.23 MB` / `18,234,909` bytes and `9:16` at `15.37 MB` / `15,366,802` bytes, `24 fps`). Visual inspection of extracted `9:16` frames caught oversized `libass` subtitles initially, which were calibrated to `FontSize=6,MarginV=24` (`9x16`) and `FontSize=14,MarginV=20` (`16x9`) and verified clean on `outputs/tmp/verify_frames/`. All 10 shots now use external images (after later user updates to `shot_02`, `03`, `08`, `09`); remaining polish notes are scene-order swaps (`05`–`07`, `03`/`10`) and platform watermarks/baked text (`02`, `03`, `04`, `05`–`07`).

### `EXP-04` — Free Local Spoken Narration (`local_tts`) & Original Procedural Score (`local_score`)
* **Hypothesis:** Synthesizing offline English narration via Windows WinRT `Microsoft George` (`local_tts`) and composing an 82 BPM D-major multi-instrument score (`local_score`) synced to `storyboard.json` cues produces valid, zero-warning `16:9` and `9:16` MP4 exports at `$0.00` API cost.
* **Result:** Executed `run-all` (`run_id: 939fac7c9625`), generating 10 spoken WAVs (`4.351s`–`6.926s`), `original_score_local.wav` (`80.276s`), `subtitles.srt`, and clean exports (`16:9`: `16,438,549` bytes; `9:16`: `14,262,830` bytes; `80.252s`, `24 fps`, `48 kHz` stereo AAC, `-14.0 LUFS`, `-1.5 dBFS` peak, `0` unintended black frames). Re-running `radio-cut` (`run_id: 62cc3d4929b6`) hit cache for all 10 narration tracks and the soundtrack (`cache_hit: true`). `qa_report.json` passed with `errors: []` and `warnings: []`.

### `EXP-05` — Audience Test #1 Audio Refinement (Dry Clarity EQ + Pentatonic Heritage Score)
* **Hypothesis:** Replacing the `+2.5 dB` `220 Hz` TTS boost and double `loudnorm` with a `105 Hz` high-pass + `-2.8 dB` `250 Hz` de-box + `+2.6 dB` `3.2 kHz` presence chain, shortening plucked-string decay (`0.9965` -> `0.9915`), removing `0.9s` synth pad smear in favor of pentatonic heritage-inspired `local_score` v2 (`procedural_pentatonic_heritage_82bpm_v2`), and tightening `sidechaincompress` (`attack=45ms`, `release=650ms`) improves dry voice clarity and cultural fit without clipping or altering visual keyframes.
* **Result:** Backed up prior deliverables to `outputs/archive/pre_audience_test1_audio_backup/`, then re-ran `run-all` and `radio-cut`. Narration (`4.246s`–`6.757s`, `mean_volume` `-20.6` to `-20.7 dB`, `max_volume` `-3.0` to `-3.7 dB`) and `original_score_local.wav` (`80.107s`, `mean_volume: -22.5 dB`, `max_volume: -6.4 dB`) mixed cleanly into `a_brighter_tomorrow_16x9.mp4` (`16,400,286` bytes) and `a_brighter_tomorrow_9x16.mp4` (`14,227,901` bytes): both `80.014s`, `24 fps` (`1920` frames), `48 kHz` stereo AAC, `I: -14.2 LUFS`, `Peak: -1.0 dBFS`, `0` `blackdetect` intervals, `qa_report.json` `passed: true` (`warnings: []`). Limitation: offline built-in `Microsoft George` still carries an `en-GB` accent rather than an Ethiopian accent.
