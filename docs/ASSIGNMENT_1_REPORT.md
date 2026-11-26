# Assignment 1 Report: *A Brighter Tomorrow — From Our Roots to Our Future*

**Project:** A Brighter Tomorrow — AI-Assisted Heritage Short Film & Reproducible Pipeline  
**Submission Track:** Assignment 1 (`B2W0: AI-Content Generation - Codebase and Report`)  
**Report Date:** November 26, 2026 (`EAT`)  
**Delivered Exports:** `outputs/exports/a_brighter_tomorrow_16x9.mp4` (`1920x1080`, `80.014s`) and `outputs/exports/a_brighter_tomorrow_9x16.mp4` (`1080x1920`, `80.014s`)  
**Measured External API Spend:** `$0.00` (`ALLOW_PAID_API=false`, `692` logged events across `69` `run_id`s in `logs/runs.jsonl`)

> **Honesty & Provenance Disclosure:** Every metric, experiment count, audience comment, failure, and limitation in this report is taken directly from repository manifests, logs, test outputs, and documentation (`DESIGN.md`, `EXPERIMENTS.md`, `FAILURES.md`, `COSTS.md`, `ETHICS.md`, `FINAL_PROJECT_STATUS.md`, `FINAL_VISUAL_QUALITY_REPORT.md`, and `logs/runs.jsonl`). Incomplete items—including **User Test #2 (`PENDING`)**, **5 pending experiments (`EXP-06`–`EXP-10`)**, known keyframe defects (`shot_05.png` watermark/text), unpushed Git status, unrecorded walkthrough video, and unsubmitted public post—are stated explicitly rather than glossed over.

---

## Executive Snapshot

| Dimension | Current Measured State | Primary Evidence |
| :--- | :--- | :--- |
| **Storyboard Contract** | `10` narrative shots (`77.0s`) + `3.0s` AI end card = `80.0s` target (`156` English words) | `storyboard.json`, `outputs/manifests/storyboard_manifest.json` |
| **Final Video Exports** | `80.014s` (`24 fps`, `1920` frames, `h264`, `48 kHz` stereo AAC); `16:9` (`16.40 MB`), `9:16` (`15.84 MB`) | `ffprobe`, `outputs/exports/a_brighter_tomorrow_{16x9,9x16}.mp4` |
| **Loudness & QA Status** | `passed: true`, `errors: []`, `warnings: []`; `I: -14.2 LUFS`, `True Peak: -1.0 dBFS` (`EXP-05` master cached in latest run) | `outputs/manifests/qa_report.json`, `EXPERIMENTS.md` |
| **Automated Test Suite** | **`25 / 25` passed** in `22.16s` (`pytest -v`), `validate` & `validate-images` pass (`exit 0`) | `tests/test_*.py`, `pipeline/cli.py` |
| **Executed Experiments** | **`5` formally completed (`EXP-01`–`EXP-05`)** of `10` target (`EXP-06`–`EXP-10` reused/pending); plus `2` logged Cloudflare reference runs and `shot_10` portrait pan tuning (`run_id: 36e4e1ca77ed`) | `EXPERIMENTS.md`, `logs/runs.jsonl` |
| **User Tests Completed** | **User Test #1 (`COMPLETED`)** with `3` participants; **User Test #2 (`PENDING`)** | `DESIGN.md` |
| **GitHub / Public Release** | **Not yet committed, pushed, posted, or submitted** (`No commits yet on main`) | `git status -sb`, `FINAL_PROJECT_STATUS.md` |

---

## 1. Audience & Intent

### Intended Audience & Viewing Context
As documented in [`DESIGN.md`](../DESIGN.md), *A Brighter Tomorrow — From Our Roots to Our Future* was designed before asset generation for **Ethiopian youth, students, diaspora families, and fellow software/AI developers** interested in how traditional roots connect with modern engineering. Because those viewers primarily discover short stories on **mobile vertical feeds (`9:16`, `1080x1920`)** and share or rewatch them on **desktop/YouTube (`16:9`, `1920x1080`)**, both aspect ratios are treated as first-class outputs from a single validated `storyboard.json` contract (`storyboard.schema.json`).

### Emotional Intent & Narrative Arc
The emotional goal is specific: viewers should end the 80-second film feeling **grounded pride in traditional Ethiopian learning**, **empathy for the late-night persistence behind learning to code**, and **realistic hope that technical skills can serve local communities** rather than leaving them behind.

To protect family privacy and comply with the challenge's consent rules (`ETHICS.md`), the protagonist is **100% fictional** across three life stages (`shot_01`–`shot_10`):

1. **Roots & Childhood (`shot_01`–`shot_04`, ages ~8–10):** Opens over misty terraced Ethiopian highlands (`shot_01`), honors traditional *Yeqolo Temari* (*Nebab Bet*) education in a shaded stone church courtyard (`shot_02`), transitions along a highland footpath to formal schooling (`shot_03`), and captures early curiosity in mathematics and science (`shot_04`).
2. **Adolescence & Persistence (`shot_05`–`shot_08`, ages ~15–17):** First encounter with a computer monitor (`shot_05`), hands-on coding (`shot_06`), late-night debugging under a study lamp (`shot_07`), and peer collaboration in class (`shot_08`).
3. **Young Adulthood & Return (`shot_09`–`shot_10`, ages ~23–26) + End Card:** Building practical AI tools for his community (`shot_09`), closing reflection (`shot_10`), and a dedicated `3.0s` visible AI disclosure card (`end_card`).

Every shot in `storyboard.json` carries an explicit `reason` field, and Shot 2 (`Traditional learning`) follows a documented cultural verification table in `DESIGN.md` restricting prompts to verified details (*Yeqolo Temari*, *Nebab Bet*, *brana* parchment, white cotton *netela*, shaded church courtyard) while programmatically blocking unverified objects such as *gebeta* inside [`pipeline/validate.py`](../pipeline/validate.py).

---

## 2. Audience Reflection — What the Audience Said and What Changed

This project separates **external audience feedback from real participants** from **the creator's own technical/visual inspection**, rather than blurring them together.

### A. User Test #1 — Feedback from Three Friends (`COMPLETED`, `2026-11-26`)
After generating the narration and score track, the cut was played to **three participants from the intended audience** (friends; individual identities and per-person quotes were not recorded). As logged in `DESIGN.md`, they returned five actionable suggestions:

1. *Make the narration sound more human and natural, with a more authentic accent.*
2. *Minimize echo and improve voice clarity.*
3. *Add more relevant images to strengthen the visual storytelling.*
4. *Consider using a local Ethiopian language with English subtitles.*
5. *Make the background music more related to Ethiopian heritage and classical traditions.*

#### What Changed Because of User Test #1 (`EXP-05`)
Rather than discarding the prototype or making blind manual edits, three engineering changes were implemented in code (`pipeline/providers/local_audio.py` and `pipeline/stage6_assemble.py`) and logged in `EXPERIMENTS.md` as **`EXP-05`**:

* **Adopted — Voice Clarity & Echo Reduction (Suggestion #2):** Audited the prior `EXP-04` signal chain and found the real culprits behind the "echo/mud" perception: a `+2.5 dB` `220 Hz` resonance boost on TTS, double loudness passes, a `0.9s` synth pad smear, and long Karplus-Strong plucked-string decay (`0.9965`). In `local_audio.py`, the TTS chain was rebuilt with a `105 Hz` high-pass filter, `-2.8 dB` `250 Hz` de-box cut, `+2.6 dB` `3.2 kHz` consonant presence boost, gentle compression/limiting, and a single final loudness normalization pass. In `stage6_assemble.py`, the score received a `-3 dB` (`1.8 kHz`) vocal pocket and tighter FFmpeg `sidechaincompress` ducking (`attack=45ms`, `release=650ms`, down from `300ms` / `1500ms`).
* **Adopted — Ethiopian Heritage-Inspired Score (Suggestion #5):** Replaced the generic Western diatonic chord/pad bed (`procedural_d_major_82bpm_v1`) with `procedural_pentatonic_heritage_82bpm_v2` in `local_audio.py`. Built purely in Python math on `D` at `82 BPM`, it uses pentatonic (*Tizita*-major/minor-inspired) intervals, shortened dry plucked string decay (`0.9915`), a low open-fifth drone, airy *washint*-inspired flute phrases, and muted *kebero*-inspired drum pulses. *Honesty note:* as documented in `DESIGN.md`, this is procedural mathematical synthesis, not live acoustic Ethiopian instrumentation.
* **Partially Adopted — Narration Naturalness (Suggestion #1):** Retained free offline Windows WinRT TTS (`Microsoft George`) at `SpeakingRate=0.96` with the clearer dry EQ chain. An authentic Ethiopian-accented English voice cannot be produced offline from built-in Windows `en-GB`/`en-US` voices without cloud/human voiceover, leaving this a documented limitation.

#### What Was Deliberately Not Changed (and Why)
* **Not Adopted — Switching Narration to a Local Ethiopian Language (Suggestion #4):** The challenge brief permits English narration with English subtitles. Windows offline TTS lacks Ethiopian language voices, `GEMINI_API_KEY` was unconfigured under `ALLOW_PAID_API=false`, and translating, re-timing, and verifying native Amharic/Afaan Oromo pronunciation safely inside the remaining hours before `23:59 EAT` carried high regression risk.
* **Not Adopted — Adding More Keyframe Shots (Suggestion #3):** The storyboard already satisfies the strict `8–12` shot contract (`10` shots = `80.014s`, centered in `60–90s`). Adding extra shots or regenerating keyframes risked worsening character drift, hitting exhausted image quotas, and destabilizing verified exports. As a result, **`storyboard.json` remained unchanged** after User Test #1.

### B. User Test #2 — Near-Final Cut (`PENDING`)
* **Status:** **`PENDING` — Not yet conducted.**  
* Per `DESIGN.md` and `FINAL_PROJECT_STATUS.md`, three intended-audience viewers have **not yet watched and reviewed** the updated `80.014s` `16:9` and `9:16` exports (`a_brighter_tomorrow_16x9.mp4` and `a_brighter_tomorrow_9x16.mp4`). No participant observations or post-User-Test-2 edits are claimed here.

### C. Creator's Own Technical & Visual Review (Distinct from Audience Feedback)
Separate from the three friends' audio-focused feedback in User Test #1, creator inspection of extracted MP4 frames and keyframe files identified and fixed concrete visual defects:
* Caught and fixed oversized `libass` captions overlapping vertical `9:16` faces (`FAIL-04`).
* Audited all 10 external keyframes (`FINAL_VISUAL_QUALITY_REPORT.md`), regenerating `shot_02`, `shot_03`, `shot_04`, `shot_06`, and `shot_07` via `gemini-3.1-flash-image` subagents, grading/resizing user-selected `shot_10.png` (`1600x912` JPEG -> `1920x1080` warm RGB PNG matching `shot_09`), and remapping `shot_05` from backup after hitting `429 RESOURCE_EXHAUSTED`.
* Identified right-edge clipping risk on the developer's profile at the end of `shot_10` in `9:16` during frame extraction and tightened `PORTRAIT_FRAMING_PRESETS["shot_10"].cx1` from `0.76` to `0.72` in [`pipeline/providers/video_adapter.py`](../pipeline/providers/video_adapter.py#L40), re-rendering (`run_id: 36e4e1ca77ed`) and visually verifying `shot_10_9x16_end.png` (`76.5s`).

---

## 3. Hardest Problem & Solution

### The Problem: Multi-Ratio Visual Framing, Format Integrity, and Consistency Under Zero-Budget & `429` Quota Limits
The single hardest technical challenge was **preserving visual framing, pipeline reliability, and dual-aspect (`16:9` + `9:16`) readability when switching between cloud generation, external images, and deterministic FFmpeg rendering under `$0.00` spend and strict API rate limits**. Five concrete blockers compounded one another (`FAIL-01`–`FAIL-05`, `FINAL_VISUAL_QUALITY_REPORT.md`):

1. **`429 RESOURCE_EXHAUSTED` During Keyframe Cleanup:** While cleaning earlier swapped/badged visuals via `gemini-3.1-flash-image`, quota exhausted (`reset reported as 2026-11-26T17:29:31Z`) before `shot_05` could be regenerated or `shot_04`'s minor finger artifact retouched.
2. **Disguised External Containers (`FAIL-05`):** User-supplied assets saved as `shot_*.png` actually contained raw `JPEG` (`shot_01`, `03`–`07`, `10`) or `WEBP` (`shot_02`) byte streams—breaking naive PNG header assumptions.
3. **FFmpeg Windows Fontconfig & `PATH` Failures (`FAIL-01`, `FAIL-03`):** Fresh terminals missed WinGet's `Gyan.FFmpeg` path, and Stage 6 `drawtext` end-card rendering aborted with `Fontconfig error: Cannot load default config file: File not found`.
4. **`libass` Vertical Subtitle Blow-Up (`FAIL-04`):** `FontSize=20,MarginV=110` looked normal on `1920x1080` (`16:9`) but scaled against `libass`'s default `384x288` virtual `PlayRes` on `1080x1920` (`9:16`), printing huge captions across the protagonist's face.
5. **`9:16` Portrait Cropping Drift on Wide Keyframes:** Center-cropping `3:2` and `16:9` keyframes blindly to `9:16` sliced subjects on off-center scenes (`shot_06` forehead/eyes at top edge, `shot_09` developer vs. elders, `shot_10` developer profile at the pan end).

### How It Was Solved (And What Still Remains)
Instead of manually editing videos in a GUI NLE—which would break the "one command regenerates from `storyboard.json`" contract—each failure was fixed permanently inside the pipeline:

* **Auto-Resolved Executables & Font Paths (`pipeline/config.py`, `pipeline/stage6_assemble.py`):** Added `resolve_executable()` to locate WinGet `ffmpeg.exe` / `ffprobe.exe` reliably even when `PATH` has not refreshed (`FAIL-01`), and added `_resolve_drawtext_font_arg()` to inject an explicit Windows `fontfile=` path with colon escaping (`FAIL-03`).
* **Pillow Magic-Byte Validation (`pipeline/providers/external_images.py`):** Replaced filename-suffix checks with Pillow `Image.open` + `im.verify()` (`PNG`, `JPEG`, `WEBP`), rejecting corrupted/duplicate hashes while preserving source files untouched (`FAIL-05`).
* **Ratio-Calibrated `libass` Styles (`pipeline/stage6_assemble.py`):** Split subtitle styling explicitly between `16:9` (`FontSize=14,MarginL=24,MarginR=24,MarginV=20`) and `9:16` (`FontSize=6,MarginL=12,MarginR=12,MarginV=24`), verified via extracted frames (`FAIL-04`).
* **Per-Shot Native `9:16` Ken Burns Engine (`pipeline/providers/video_adapter.py`):** Built [`build_ken_burns_filter`](../pipeline/providers/video_adapter.py#L85-L180) and [`PORTRAIT_FRAMING_PRESETS`](../pipeline/providers/video_adapter.py#L30-L41) so `9:16` clips render directly at `1080x1920` from full-resolution landscape keyframes with aspect-preserving vertical pad (`pad` when `ar_in > ar_out`), shot-specific `cy` headroom (`cy=0.0` on `shot_06`), and tuned horizontal pans (`cx1=0.72` on `shot_10`).
* **Honest Triage Under Quota Limits:** Backed up prior assets (`outputs/archive/pre_visual_review_backup/`), remapped the best matching computer-lab scene into `shot_05.png`, and documented remaining visual flaws transparently rather than hiding them.

### Remaining Known Visual Issues (Unresolved in Active Exports)
1. **`shot_05.png` (Medium-High):** Remapped backup still contains a `"Made with AI"` pill at the top-right corner (edge visible in `16:9`; cropped out in `9:16`) and garbled text on classroom posters/monitors (`"TECHNOLOG IS OUR FUTURE"`, etc.).
2. **`shot_04.png` (Low):** Minor dark ring-like band on the boy's right index finger (`429` blocked retouch).
3. **`shot_06.png` (Low):** Tight upper crop clips the top of the student's forehead/eyes (mitigated in `9:16` via `cy=0.0`).
4. **`shot_10.png` (Creative Override):** Depicts a modern urban window/laptop developer scene (per creator choice, resized/graded to match `shot_09`) rather than the rural highland sunset motif originally written in `storyboard.json`.

---

## 4. Suggested Practices Tested Honestly

`Challenge Doc.pdf` suggested several engineering and design practices and asked for an honest test of **one practice that helped** and **one that did not**, backed by repository evidence.

### Practice That Helped (Beat Instinct): Schema-Locked `storyboard.json` Contract + SHA-256 Stage Caching (`pipeline/cache.py`) & `logs/runs.jsonl`
* **Initial Skepticism:** Early on, writing JSON Schema validators, SHA-256 manifest hashing, `ALLOW_PAID_API` guards, and an append-only `logs/runs.jsonl` logger felt like heavy boilerplate for an 80-second short film.
* **What Happened in Practice:** Across **`69` unique runs (`692` log entries in `logs/runs.jsonl`)**, **`453` of `692` events (`65.5%`) were `cache_hit: true` (`0.0s` execution)**. Concrete wins observed directly in logs:
  * When FFmpeg `drawtext` crashed in `FAIL-03` during Stage 6 (`task-270`), fixing `_resolve_drawtext_font_arg()` and re-running reused every cached keyframe, clip, and audio file.
  * When `User Test #1` (`EXP-05`) required changing only EQ, ducking, and music synthesis (`local_audio.py`, `stage6_assemble.py`), `10/10` keyframes stayed cached untouched.
  * When `shot_10` portrait framing (`cx1: 0.76 -> 0.72`) was adjusted after reviewing vertical frames (`run_id: 36e4e1ca77ed`), Stage 3 keyframes (`10/10`), Stage 4 narration (`10/10`), and Stage 4 music (`1/1`) all hit cache in `< 1s`, isolating work strictly to video assembly (`195.689s`).
  * Complementing this, running the cheap **`radio-cut`** first (`EXP-01`, `EXP-05`) exposed audio mud and musical mismatch during User Test #1 before touching visuals—validating the "cheap prototype first" habit too.

### Practice That Did Not Help as Expected: Relying on Generating a 3-Age Character Reference Sheet First (`stage1_reference.py`) to Guarantee Shot-to-Shot Identity Under Free-Tier Limits
* **What Was Suggested & Tested:** Generating a 3-age/multi-panel character reference sheet first (`stage1_reference.py` via Cloudflare `@cf/black-forest-labs/flux-2-klein-4b`) and conditioning all 10 shots on it (`EXP-06`). In `logs/runs.jsonl`, Cloudflare Workers AI ran twice (`run_id: 21848bf6a124` at `08:38 UTC` and `175fbac20335` at `10:57 UTC`) generating `character_sheet_candidate_1..3.png` (seeds `700`–`702`, `1152x640`, `12.38s`–`33.62s`, `$0.00` free tier), alongside local Pillow crops (`heritage_ref_stage1..3*.png`).
* **Why It Fell Short in This Workflow:**
  1. Generating a clean `character_sheet_selected.png` did **not** give usable visual continuity inside the zero-cost offline fallback (`EXP-02`): cropping one 3-stage sheet over vector SVG/PNG scenes looked like flat cutouts rather than realistic documentary cinematography.
  2. Even when moving to photorealistic scene generation (`external_local` + `gemini-3.1-flash-image`), maintaining likeness and wardrobe across 10 shots without paid/high-quota multi-reference I2I endpoints or a trained LoRA still required manual candidate pruning, scene-order repair, backup remapping (`shot_05`), and custom color grading (`shot_10` to `shot_09`). And `gemini-3.1-flash-image` `429` quota exhaustion cut off `shot_05` and `shot_04` fixes regardless of having a reference sheet on disk.
* **Honest Takeaway:** A reference sheet is necessary as a *visual compass*, not sufficient as an *automated consistency guarantee* when downstream generators lack spare I2I quota or LoRA conditioning.

### Honest Experiment Count (`EXPERIMENTS.md` vs. Target `10`)
* **Target in `Challenge Doc.pdf`:** ~`10` hypothesis-driven experiments.
* **Actual Count Completed:** **`5` formally documented experiments (`EXP-01`–`EXP-05`)** in `EXPERIMENTS.md`, covering Radio Cut timing (`83.028s`), Offline SVG/crop cut (`82.956s`), External Keyframes + Native `16:9`/`9:16` Ken Burns + subtitle calibration (`82.956s`), Free `local_tts` + `local_score` v1 (`80.252s`, `-14.0 LUFS`), and User Test #1 Audio Refinement (`80.014s`, `-14.2 LUFS`).
* **Remaining 5 Entries:** `EXP-06` is `EXISTING CANDIDATES REUSED` (backed by the two logged Cloudflare `flux-2-klein-4b` candidate runs), while **`EXP-07` (Gemini TTS), `EXP-08` (API Keyframe Conditioning), `EXP-09` (Wan 2.2 TI2V-5B Colab Smoke Test), and `EXP-10` (ACE-Step 1.5 Colab Sample)** remain **`PENDING APPROVAL` / `PENDING COLAB TEST`**.

---

## 5. Curiosity / Ceiling Work — Going Beyond the Minimum & What Was Learned

Rather than stopping at minimal sequential FFmpeg scripts with placeholder audio or simple center-cropped vertical exports, three engineering upgrades pushed well beyond the baseline floor:

### 1. Curated Per-Shot `9:16` Portrait Framing Engine & Visual Frame Audit
* **Implementation:** [`PORTRAIT_FRAMING_PRESETS`](file:///c:/Users/habta/OneDrive/Documents/GitHub/AI-Content-Generation-a-brighter-tomorrow/pipeline/providers/video_adapter.py#L30-L41) and [`build_ken_burns_filter`](file:///c:/Users/habta/OneDrive/Documents/GitHub/AI-Content-Generation-a-brighter-tomorrow/pipeline/providers/video_adapter.py#L85-L180) in `pipeline/providers/video_adapter.py`, covered by `5` dedicated unit tests in `tests/test_video_adapter.py`.
* **What Was Learned:** Dual-aspect delivery (`16:9` + `9:16`) fails when treated as a naive `crop=ih*9/16:ih` post-process. Wide shots (`shot_01`, `shot_09`, `shot_10`) need horizontal tracking (`cx0 -> cx1`), close-ups (`shot_06`) need top-anchored vertical bias (`cy=0.0`) to protect faces, and inspecting extracted frames at exact cut boundaries caught right-edge clipping (`shot_10` `cx1: 0.76 -> 0.72`) that midpoint inspection alone missed.

### 2. Zero-Cost Offline Audio Studio (`local_tts` WinRT Bridge + `local_score` Heritage Synthesizer)
* **Implementation:** `pipeline/providers/local_audio.py` (`496` lines) pairs a Windows WinRT `SpeechSynthesizer` bridge (`Microsoft George` at `SpeakingRate=0.96` + POSIX `espeak-ng`/`espeak`/`say` fallback) with an original deterministic pure-Python `local_score` composer (`procedural_pentatonic_heritage_82bpm_v2`) featuring Karplus-Strong plucked strings, *washint*-inspired airy flute lines with grace slides, *kebero*-inspired dry drum pulses, and open-fifth drones synced to `storyboard.json` cues.
* **What Was Learned:** Listening with friends in User Test #1 (`EXP-05`) proved that *spectral space and decay length matter more than musical complexity under dialogue*. Trimming `220 Hz` TTS resonance, cutting Karplus-Strong decay from `0.9965` to `0.9915`, removing `0.9s` synth pad sustain, and shortening sidechain attack (`300ms -> 45ms`) dramatically improved speech clarity at `$0.00`. Equally important, testing honestly confirmed the ceiling of offline OS voices (`en-GB` accent, no offline Ethiopian languages).

### 3. Magic-Byte Keyframe Validator, Cultural Guardrails, & 25-Test Regression Suite
* **Implementation:** `pipeline/providers/external_images.py` (Pillow stream detection + SHA-256 deduplication), `pipeline/validate.py` + `DESIGN.md` Shot 2 verification table (enforcing verified *Yeqolo Temari*/*Nebab Bet*/*brana*/*netela* elements and blocking unverified *gebeta* inclusions), and `5` test suites (`25 passed` in `22.16s`).
* **Measured Performance & Cost Ledger (`logs/runs.jsonl` + `COSTS.md`):**
  * **Actual API Spend:** **`$0.00`** (`0` paid API calls; `0` GPU minutes used—all Colab/GPU runs remain pending).
  * **Measured Cache-Miss Latencies (`logs/runs.jsonl`):** `stage1_reference` (`cloudflare_workers_ai` `flux-2-klein-4b`, 6 calls): `12.377s`–`33.615s`; `stage3_keyframes` (`external_manual`, 25 imports): `0.021s`–`0.099s`; `stage3_videos` (`ken_burns`, 36 clips): `0.835s`–`9.753s`/clip; `stage4_narration` (`local_tts`, 20 calls): `1.473s`–`2.191s`/shot; `stage4_music` (`local_score`, 2 calls): `4.494s` and `8.346s`; `stage6_assemble` (`ffmpeg` dual export, 15 runs): `94.931s`–`320.668s` (`195.689s` in latest `run_id: 36e4e1ca77ed`).
  * **Official List-Price Reference (`COSTS.md`):** Cloudflare Workers AI (`$0.011`/1k Neurons past 10k free/day); Gemini 3.8 Flash (`$0.75`/1M input, `$3.75`/1M output intro); Gemini 3.8 Flash TTS (`$0.50`/1M text input, `$9.00`/1M audio output preview); `Wan 2.2 TI2V-5B` (Apache 2.0) and `ACE-Step 1.5` (MIT) open weights.

---

## 6. Next Steps

Ordered by priority to close remaining assignment requirements and resolve known quality/completeness gaps:

1. **Conduct User Test #2 (`DESIGN.md`):** Screen the latest `80.014s` `16:9` and `9:16` exports (`a_brighter_tomorrow_16x9.mp4` and `a_brighter_tomorrow_9x16.mp4`) for at least three intended-audience viewers, record genuine quotes/observations in `DESIGN.md`, and apply any required final edits.
2. **Repair Remaining Visual Defects (Once Image Quota Resets):** Regenerate `shot_05.png` cleanly without `"Made with AI"` edge markings or garbled classroom text; optionally clean `shot_04.png` (finger band), `shot_06.png` (head headroom), and align `shot_10.png` with the opening highland landscape motif if desired.
3. **Complete Pending Experiments (`EXP-06`–`EXP-10`) & GPU Latency Benchmarks:** Run Colab GPU smoke tests for `Wan 2.2 TI2V-5B` (`EXP-09`) and `ACE-Step 1.5` (`EXP-10`), test `Gemini 3.8 Flash TTS` (`EXP-07`) including Ethiopian-accent/language prosody comparison against `local_tts`, test API keyframe conditioning (`EXP-08`), and add measured GPU minutes to `COSTS.md`.
4. **Record the Walkthrough Video (`<= 5 min`):** Explain the 6-stage pipeline and `shot_10` portrait framing decision, edit one prompt or narration line in `storyboard.json`, run the pipeline live, and display `logs/runs.jsonl` confirming only the modified shot regenerated (`cache_hit: true` on unchanged shots).
5. **Commit, Push, Publish, and Submit:** Stage and commit the clean repository (verifying `.env` remains excluded by `.gitignore`), push to the public GitHub remote (`origin/main`), verify clean-clone execution of `make film`, publish the video post with the platform AI label enabled, and submit open-access links for Assignments 1 and 2 on Tenx before `Thursday, 26 November, 23:59 EAT`.

---

## Appendix: Verified Verification Outputs (Post-Final Edit)

| Check / Artifact | Exact Observed Result |
| :--- | :--- |
| `.\.venv\Scripts\python.exe -m pytest -v` | `25 passed in 22.16s` (`test_cache_retry.py`, `test_pipeline_smoke.py`, `test_schema.py`, `test_subtitles.py`, `test_video_adapter.py`) |
| `.\.venv\Scripts\python.exe -m pipeline.cli validate` | `VALID: 10 shots (77.0s) + end_card (3.0s) = 80.0s` — `156 narration words` (`exit 0`) |
| `.\.venv\Scripts\python.exe -m pipeline.cli validate-images` | `EXTERNAL IMAGES VALID (10 shots)` (`exit 0`) |
| `outputs/manifests/qa_report.json` | `passed: true`, `mode: "full"`, `shots_duration_sec: 77.107`, `end_card_duration_sec: 3.0`, `total_duration_sec: 80.107`, `errors: []`, `warnings: []` |
| `ffprobe` (`a_brighter_tomorrow_16x9.mp4`) | `1920x1080`, `h264`, `24/1` fps, `1920` frames, `aac` `48000 Hz` stereo (`3752` frames), `80.014000s`, `16,400,286` bytes |
| `ffprobe` (`a_brighter_tomorrow_9x16.mp4`) | `1080x1920`, `h264`, `24/1` fps, `1920` frames, `aac` `48000 Hz` stereo (`3752` frames), `80.014000s`, `15,838,425` bytes |
| `logs/runs.jsonl` totals | `692` lines, `69` `run_id`s, `453` cache hits, `239` cache misses, `0` non-OK entries, `$0.00` total estimated cost |
