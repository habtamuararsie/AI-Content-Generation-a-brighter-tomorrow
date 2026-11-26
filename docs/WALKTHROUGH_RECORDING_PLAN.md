# Assignment 2 Walkthrough Video — Recording Plan & Script

**Goal:** Record a clear, beginner-friendly walkthrough video (**maximum 5:00**, target **~4:40**) demonstrating the pipeline architecture, how `storyboard.json` drives every stage, one hard technical problem solved in code, and a live single-shot regeneration verified by `logs/runs.jsonl`, manifests, and timestamps.

> **Safety & Code Verification Note:** Every command, file side effect, cache key rule, and log format below was verified directly against `pipeline/cli.py`, `pipeline/stage2_storyboard.py`, `pipeline/stage4_audio.py`, `pipeline/stage5_qa.py`, `pipeline/stage6_assemble.py`, `pipeline/providers/music_adapter.py`, `pipeline/cache.py`, and `pipeline/logger.py`. No production files or outputs were modified while creating this plan.

---

## 1. Time Budget Overview (Target: `4:40` / Max `5:00`)

| Segment | Topic | Target Time | Cumulative | What Is Shown on Screen |
| :--- | :--- | :---: | :---: | :--- |
| **1** | Intro, Story Purpose & 6-Stage Architecture | `0:50` | `0:00 – 0:50` | `README.md`, Mermaid diagram in `ARCHITECTURE.md`, `pipeline/` folder |
| **2** | How `storyboard.json` Controls the Pipeline & Cache | `0:50` | `0:50 – 1:40` | `storyboard.json`, `storyboard.schema.json`, `pipeline/cache.py`, `pipeline.cli validate` |
| **3** | Hardest Technical Problem & Solution | `1:00` | `1:40 – 2:40` | `FAILURES.md` (`FAIL-04`), `pipeline/providers/video_adapter.py`, `pipeline/stage6_assemble.py` |
| **4** | Live Single-Shot Edit & Cached Re-Run (`shot_10`) | `1:20` | `2:40 – 4:00` | Edit `shot_10.narration.text` -> run `radio-cut` live (`~8–12s`, no pause needed) |
| **5** | Verification (`runs.jsonl`, Manifests, Timestamps) & Wrap-Up | `0:40` | `4:00 – 4:40` | Latest `run_id` (`14` rows) in `logs/runs.jsonl`, `outputs/narration/*.wav` timestamps |

---

## 2. Code-Verified Behavior of `radio-cut` (What Runs & What Changes)

**Recommended Command:**
```powershell
.\.venv\Scripts\python.exe -m pipeline.cli radio-cut --narration-provider local_tts --music-provider local_score
```

Direct inspection of `pipeline/cli.py` and the modules it calls confirms:

1. **All 10 shots are evaluated in Stage 4 narration:** In [`run_stage4_audio`](../pipeline/stage4_audio.py#L114-L162), omitting `--shot-id` iterates over all 10 shots (`shot_01`–`shot_10`). *(By contrast, passing `--shot-id shot_10` hits `continue` at line `125` for `shot_01`–`shot_09` and skips logging `cache_hit: true` to `logs/runs.jsonl`.)*
2. **Shots `01`–`09` hit cache; ONLY `shot_10` regenerates narration:**
   * `cache_key` in `run_stage4_audio` hashes `stage`, `provider`, `model` (`"os_local_tts_v2"`), `voice`, `text`, and `style`.
   * [`is_cache_valid`](../pipeline/cache.py#L42-L63) compares `manifest["items"][shot_id]["cache_key"]` against the expected hash and checks that `outputs/narration/{shot_id}.wav` exists and is non-empty.
   * After editing only `shot_10.narration.text`, `shot_01`–`shot_09` match `outputs/manifests/audio_manifest.json` (`cache_hit: true`, `0.0s`), while **only `shot_10` misses cache**, calls `generate_local_tts_narration`, overwrites `outputs/narration/shot_10.wav` (`~1.5–2.2s`), and updates `items["shot_10"]` in `audio_manifest.json`.
3. **What else `radio-cut` touches (exact side effects):**
   * **Rewritten:** `outputs/manifests/storyboard_manifest.json` (Stage 2), `outputs/subtitles/subtitles.srt` (Stage 4), `outputs/manifests/audio_manifest.json` (Stage 4), `outputs/manifests/qa_report.json` (Stage 5 sets `"mode": "radio_cut"`), `outputs/exports/radio_cut_mix.wav`, and `outputs/exports/radio_cut.mp4` (Stage 6 `run_stage6_radio_cut`).
   * **Music (`original_score_local.wav`):** In `run_stage4_audio` (`lines 236–245`), `music_cache_key` includes `"timings": shot_timings`. Because `shot_10`'s new WAV changes `narration_end_sec` / `measured_audio_duration_sec` by at least a few milliseconds, `music_cache_key` misses and regenerates `outputs/music/original_score_local.wav` (`~4.5–8.3s`) to stay synced to the new narration duration.
   * **Final MP4 exports (`a_brighter_tomorrow_16x9.mp4` & `9x16.mp4`):** **NOT modified.** `radio-cut` never calls `run_stage6_assemble`.
   * **Keyframes & Video clips (`outputs/keyframes/*`, `outputs/clips/*`, `keyframes_manifest.json`, `video_manifest.json`):** **NOT modified.** `radio-cut` never calls Stage 3.
4. **Why no safer CLI command exists with fewer side effects:**
   * `validate`, `validate-images`, `check-config`, and `verify-cf` do not regenerate shots or test shot caching.
   * `keyframes --image-provider external_local` hashes file bytes on disk rather than `image_prompt`, so prompt edits trigger zero regenerations; switching `keyframes` to `offline_local` or `cloudflare_flux` would overwrite `outputs/keyframes/shot_10.png`.
   * `run-all` (`make film`) additionally runs Stage 6 FFmpeg assembly for `~195s` and rewrites both final MP4s.
   * Passing `--music-provider placeholder_temp` to `radio-cut` still re-synthesizes `temp_track_placeholder.wav` and overwrites `audio_manifest.json`'s `music` block with `is_placeholder: true`, making explicit `--narration-provider local_tts --music-provider local_score` cleaner and safer.

---

## 3. Why `shot_10.narration.text` Is the Safest Shot to Edit

* **Timing safety (`3.45s` margin):** `shot_10` has `duration_sec: 8.0` and `measured_audio_duration_sec: 4.548` in `audio_manifest.json`. Replacing one word (`"for"` -> `"toward"`) preserves `156` total narration words and `80.107s` effective duration (well inside `60–90s`).
* **Zero cultural guardrail triggers:** Unlike `shot_02` (*Yeqolo Temari* rules in `pipeline/validate.py`), `shot_10` (`age_stage: "young_adulthood"`) has no keyword blockers.
* **Zero API spend (`$0.00`):** Runs offline with `ALLOW_PAID_API=false` using Windows WinRT TTS (`Microsoft George`).
* **Visible at the bottom of `storyboard.json` (lines `221–225`):** Easy to show on camera without scrolling through unrelated shots.

---

## 4. Exact Expected `logs/runs.jsonl` Output (`14` Entries)

Running `radio-cut --narration-provider local_tts --music-provider local_score` after editing only `shot_10.narration.text` appends **14 JSONL entries** under one shared `run_id`:

| # | `stage` | `shot_id` | `provider` | `model` | `status` | `cache_hit` | Expected `latency_sec` |
| :-: | :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `1` | `stage2_storyboard` | `all` | `local_validator` | `jsonschema_and_timing` | `success` | `false` | `~0.01–0.2s` |
| `2–10` | `stage4_narration` | `shot_01` .. `shot_09` (`9` rows) | `local_tts` | `os_local_tts_v2` | `cached` | **`true`** | `0.0` |
| `11` | `stage4_narration` | `shot_10` (`1` row) | `local_tts` | `windows_winrt:Microsoft George` | `success` | **`false`** | `~1.5–2.2s` |
| `12` | `stage4_music` | `soundtrack` | `local_score` | `procedural_pentatonic_heritage_82bpm_v2` | `success` | `false` *(if duration ms changed)* | `~4.5–8.3s` |
| `13` | `stage5_qa` | `all` | `local_qa` | `sync_and_duration_check` | `success` | `false` | `~0.001–0.05s` |
| `14` | `stage6_radio_cut` | `all` | `local_radio_cut` | `pure_python_wav_and_ffmpeg` | `success` | `false` | `~1.0–5.5s` |

---

## 5. Exact Safe Commands: Backup, Demonstration, Verification & Restoration

### Step A — Pre-Recording Backup (Run Before Recording)
Back up `storyboard.json` and the `radio-cut`-affected manifests/outputs outside the repo (`$env:TEMP`) so the repo stays clean and you can restore exact pre-demo `mode: "full"` state afterward:
```powershell
$backupDir = "$env:TEMP\abt_walkthrough_backup"
New-Item -ItemType Directory -Force -Path "$backupDir\manifests", "$backupDir\narration", "$backupDir\music", "$backupDir\subtitles", "$backupDir\exports" | Out-Null
Copy-Item storyboard.json "$backupDir\storyboard.json" -Force
Copy-Item outputs\manifests\storyboard_manifest.json, outputs\manifests\audio_manifest.json, outputs\manifests\qa_report.json "$backupDir\manifests\" -Force
Copy-Item outputs\narration\shot_10.wav "$backupDir\narration\" -Force
Copy-Item outputs\music\original_score_local.wav "$backupDir\music\" -Force
Copy-Item outputs\subtitles\subtitles.srt "$backupDir\subtitles\" -Force
Copy-Item outputs\exports\radio_cut_mix.wav, outputs\exports\radio_cut.mp4 "$backupDir\exports\" -Force
```

### Step B — Live Edit & Pipeline Re-Run (On Camera)
1. In `storyboard.json` line `222` (`shot_10.narration.text`), change:
   - `"Rooted in where he began, every line of code becomes a promise for a brighter tomorrow."`
   - to `"Rooted in where he began, every line of code becomes a promise toward a brighter tomorrow."`
2. Save `storyboard.json`, then run:
```powershell
.\.venv\Scripts\python.exe -m pipeline.cli radio-cut --narration-provider local_tts --music-provider local_score
```

### Step C — Live Verification (On Camera)
Show `logs/runs.jsonl` entries for the latest `run_id` and compare `outputs/narration/*.wav` timestamps:
```powershell
.\.venv\Scripts\python.exe -c "import json; rows=[json.loads(l) for l in open('logs/runs.jsonl', encoding='utf-8') if l.strip()]; rid=rows[-1]['run_id']; print('LATEST run_id:', rid); [print(f\"{r['stage']:17} | {str(r['shot_id']):10} | status={r['status']:8} | cache_hit={str(r['cache_hit']):5} | latency={r['latency_sec']}s\") for r in rows if r['run_id']==rid]"
Get-ChildItem outputs/narration/*.wav | Select-Object Name, LastWriteTime | Sort-Object LastWriteTime
```

### Step D — Post-Recording Restore (Run Immediately After Stopping Recording)
Restore the original `storyboard.json`, re-sync `audio_manifest.json` / `shot_10.wav` / `original_score_local.wav` / `subtitles.srt`, and restore `"mode": "full"` `qa_report.json` (plus check `validate` & `qa_report.json`):
```powershell
$backupDir = "$env:TEMP\abt_walkthrough_backup"
Copy-Item "$backupDir\storyboard.json" storyboard.json -Force
Copy-Item "$backupDir\narration\shot_10.wav" outputs\narration\shot_10.wav -Force
Copy-Item "$backupDir\music\original_score_local.wav" outputs\music\original_score_local.wav -Force
Copy-Item "$backupDir\subtitles\subtitles.srt" outputs\subtitles\subtitles.srt -Force
Copy-Item "$backupDir\manifests\storyboard_manifest.json", "$backupDir\manifests\audio_manifest.json", "$backupDir\manifests\qa_report.json" outputs\manifests\ -Force
Copy-Item "$backupDir\exports\radio_cut_mix.wav", "$backupDir\exports\radio_cut.mp4" outputs\exports\ -Force
.\.venv\Scripts\python.exe -m pipeline.cli validate
```
*(Alternatively, after restoring `storyboard.json`, running `.\.venv\Scripts\python.exe -m pipeline.cli run-all --image-provider external_local --narration-provider local_tts --video-provider ken_burns --music-provider local_score` cleanly hits cache for all 10 shots/music and restores `qa_report.json` to `"mode": "full"` in ~3.3 minutes.)*

---

## 6. Word-for-Word / Beat-by-Beat Narration Script (`~4:40`)

### Prep Before Pressing Record
* Close `.env` and any personal files (never expose keys on screen).
* Keep 4 clean views ready: `ARCHITECTURE.md` (Mermaid preview), `storyboard.json` (scrolled to lines `210–237`), `pipeline/providers/video_adapter.py` (lines `17–42`), and PowerShell (`14–16 pt` font) at repo root.

### Segment 1 — Project Purpose & 6-Stage Architecture (`0:00 – 0:50`)
> **Say:**  
> "Hi everyone, this is my walkthrough for *A Brighter Tomorrow — From Our Roots to Our Future*, an 80-second AI-assisted documentary short about a fictional Ethiopian learner moving from traditional *Yeqolo Temari* education to building community-serving AI tools.  
>  
> Rather than editing clips by hand, I built a modular 6-stage pipeline in `pipeline/` orchestrated by `pipeline/cli.py`. Stage 1 handles character references, Stage 2 validates `storyboard.json` against `storyboard.schema.json`, Stage 3 resolves keyframes and moving shots, Stage 4 handles narration, `.srt` subtitles, and music, Stage 5 checks timing and QA, and Stage 6 assembles both `16:9` and `9:16` MP4s at `-14 LUFS` with a 3-second AI disclosure end card—running locally at `$0.00` API spend."

### Segment 2 — How `storyboard.json` Controls the Pipeline (`0:50 – 1:40`)
> **Say:**  
> "`storyboard.json` is the single contract controlling every stage: visual style block, 3 life stages, `82 BPM` `D major` music parameters, and 10 shots with durations, prompts, narration lines, and a `reason` per shot.  
>  
> Stage 2 validates it against `storyboard.schema.json` (`8–12` shots, `60–90s` total, plus cultural guardrails for Shot 2): `[run pipeline.cli validate]` — 10 shots (`77s`) plus `3s` end card = `80s`, `156` words. Inside `pipeline/cache.py`, `compute_cache_key()` hashes each stage's exact inputs into `outputs/manifests/*.json`, so re-runs regenerate only what changed."

### Segment 3 — Hardest Technical Problem & Solution (`1:40 – 2:40`)
> **Say:**  
> "The hardest problem was maintaining dual-aspect `16:9` and `9:16` readability and framing under zero-cost and quota limits. On vertical `1080x1920`, `libass` initially blew subtitles up over faces (`FAIL-04`), and naive center-crops clipped faces on wide scenes.  
>  
> I fixed both permanently in code: `pipeline/stage6_assemble.py` calibrates separate subtitle styles for `16:9` (`FontSize=14`) and `9:16` (`FontSize=6,MarginV=24`), and `pipeline/providers/video_adapter.py` uses curated per-shot `PORTRAIT_FRAMING_PRESETS` plus vertical aspect-preserving padding—anchoring `shot_06` to `cy=0.0` for headroom and tuning `shot_10`'s pan end `cx1` from `0.76` to `0.72` so the developer's profile stays centered."

### Segment 4 — Live Single-Shot Regeneration (`2:40 – 4:00`)
> **Say:**  
> "Now let's edit one narration line in `storyboard.json` and run `radio-cut` without any single-shot filter flag so you can see the cache evaluate all 10 shots. On line `222` (`shot_10`), I'll change `'for a brighter tomorrow.'` to `'toward a brighter tomorrow.'`, save, and run `radio-cut --narration-provider local_tts --music-provider local_score`."  
> *(Runs in ~10 seconds live — `shot_01`–`shot_09` hit cache, only `shot_10.wav` regenerates, and `local_score` re-syncs cleanly to the updated `shot_10` timing while final MP4s stay untouched.)*

### Segment 5 — Log & Timestamp Verification + Wrap-Up (`4:00 – 4:40`)
> **Say:**  
> "Let's check `logs/runs.jsonl` for the latest `run_id` and inspect file timestamps in `outputs/narration/`. You can see `stage4_narration` logged `cache_hit=True` (`status=cached`) for `shot_01` through `shot_09`, and **`cache_hit=False` (`status=success`) ONLY for `shot_10`** in under two seconds. And `Get-ChildItem outputs/narration/*.wav` confirms only `shot_10.wav` updated while `shot_01` through `shot_09` kept their original timestamps. Thanks for watching."

---

## 7. Pre-Flight & Post-Recording Checklist

- [ ] **Backup created:** `$env:TEMP\abt_walkthrough_backup\` contains `storyboard.json`, manifests, `shot_10.wav`, `original_score_local.wav`, `subtitles.srt`, and `radio_cut*`.
- [ ] **No secrets visible:** `.env` closed and not echoed in terminal.
- [ ] **Only `shot_10.narration.text` edited on camera** (`"for"` -> `"toward"`).
- [ ] **Cache proof shown on camera:** `logs/runs.jsonl` latest `run_id` (`9` cached hits + `1` `shot_10` regeneration) and `outputs/narration/*.wav` timestamps.
- [ ] **Runtime <= `5:00`**.
- [ ] **Post-recording restore executed** and `pipeline.cli validate` returns `VALID` (`80.0s`, `156` words) with `qa_report.json` restored to `"mode": "full"`.
