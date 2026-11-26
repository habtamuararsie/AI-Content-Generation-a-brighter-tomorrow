# Design & Creative Plan — A Brighter Tomorrow

**Title:** *A Brighter Tomorrow*  
**Subtitle:** *From Our Roots to Our Future*  
**Format:** 60–90 second AI-assisted realistic documentary short film (10 narrative shots + separate 3.0s AI disclosure end card; target ~80s total)  
**Aspect Ratios:** `16:9` (`1920x1080`) and `9:16` (`1080x1920`)  
**Narration Language:** English (with synchronized English `.srt` subtitles)

---

## 1. Audience & Intent

* **Intended Audience:** Ethiopian youth, students, diaspora families, and fellow developers interested in how traditional roots and modern technology connect.
* **Where They Will Watch:** Mobile vertical feeds (`9:16`) and desktop/YouTube (`16:9`).
* **Emotional Intent:** Viewers should finish the film feeling grounded pride in traditional Ethiopian learning, empathy for the persistence required to learn programming, and realistic hope that technical skills can return to serve local communities.

---

## 2. Fictional Character Design (3 Life Stages)

To avoid exposing private family details or inventing a real person's biography, the protagonist is **100% fictional**.

* **Identity Anchor:** Fictional Ethiopian male with warm medium-deep brown skin, expressive dark brown eyes, gentle earnest facial features, and natural close-cropped curly Ethiopian hair.
* **Stage 1 — Childhood (approx. 8–10 years old, Shots 2–4):** Traditional *Qolo Temari* rural education transitioning into early formal schooling; slim boyish frame, rounded youthful cheeks, wearing a clean white hand-woven cotton *netela* over a simple natural cotton tunic in the traditional Ethiopian church-school courtyard (Shot 2), then an everyday school shirt and backpack walking past traditional village homes into a modest rural classroom (Shots 3–4).
* **Stage 2 — Adolescence (approx. 15–17 years old, Shots 5–8):** Rural Ethiopian high-school student; taller lean teenager, slightly more defined jawline, same eyes and short curly hair, wearing a neat collared school shirt and navy knit sweater with a worn backpack, studying mathematics, science, computers, and programming with teachers and classmates while rural highland hills remain visible outside the classroom windows.
* **Stage 3 — Young Adulthood (approx. 23–26 years old, Shots 9–10):** Ethiopian artificial intelligence developer; mature version of the exact same face with light natural stubble and calm confident expression, wearing realistic modern professional clothing (button-down shirt and tailored earth-toned jacket, without forced traditional costume) in a modern workspace building community-serving AI technology and returning knowledge and opportunity to his rural community.

**Reference & External Asset Workflow:** Offline 3-age character references exist in `outputs/references/` (`character_sheet_candidate_1..3.png`, `character_sheet_selected.png`, and `heritage_ref_stage1..3*.png`). For the final zero-cost cut, all 10 externally generated scene keyframes placed in `outputs/keyframes/` are validated by `external_images.py` (supporting PNG, JPEG, and WEBP payloads) and preserved untouched. Remaining visual polish notes before submission: `shot_03` currently holds the church courtyard *Qolo Temari* image (with baked-in `"A Brighter Tomorrow"` / `"Made with AI"` overlays), `shot_05`–`shot_07` are permuted relative to storyboard order (night study / computer lab / Python IDE), `shot_10` depicts a modern urban office rather than the rural homeland return motif, and `shot_02` carries a small bottom-right crayon watermark.

---

## 3. Shot 2 Cultural Accuracy & Source Verification (*Yeqolo Temari*)

Shot 2 depicts traditional Ethiopian Orthodox church schooling respectfully without inventing rituals or mixing unrelated traditions.

| Cultural Element | Verification Status | Supporting Context & Prompt Rule |
| :--- | :--- | :--- |
| **Yeqolo Temari** (የቆሎ ተማሪ) | **Verified** | Traditional students in the Ethiopian Orthodox Tewahedo Church (*Abinet Timhert Bet*) system, known for ascetic discipline, oral recitation, and memorization. |
| **Nebab Bet** (ንባብ ቤት) | **Verified** | Introductory "House of Reading" stage where young students learn the Ethiopic syllabary (*Fidel*) and begin reading Ge'ez texts. |
| **Brana** (ብራና) | **Verified** | Traditional treated-parchment/vellum manuscripts used in church schools and monasteries for sacred and classical Ge'ez texts. |
| **Netela** (ነጠላ) | **Verified** | Modest hand-woven white cotton wrap traditionally worn in Ethiopia, especially in church and religious study settings. |
| **Church courtyard learning setting** | **Verified** | Studying quietly in the shaded stone courtyard of a traditional church compound under trees reflects documented open-air/compound study habits. |
| **Däbälo** (ደበሎ) | **Verified (Optional)** | Traditional sheepskin garment/mat worn for warmth in cooler northern highlands; kept optional so visual prompts stay simple and consistent. |
| **Unverified details / board games** | **Excluded / Unverified** | Unverified objects (such as *gebeta*, a traditional board game unrelated to *Yeqolo Temari* study) and any invented liturgical gestures or inscriptions are strictly excluded from prompts. |

---

## 4. Shot-by-Shot Storyboard Intent (10 Narrative Shots + End Card)

| Shot | Scene Title | Age Stage | Target Dur. | Stated Reason (Why This Shot Exists) |
| :--- | :--- | :--- | :--- | :--- |
| `shot_01` | Our roots | Setting | 8.0s | Establishes a fictionalized Ethiopian highland birthplace-inspired landscape and grounded community atmosphere. |
| `shot_02` | Traditional learning | Childhood | 8.0s | Honors traditional *Yeqolo Temari* (*Nebab Bet*) education as the earliest foundation of focus and literacy. |
| `shot_03` | The journey to school | Childhood | 7.5s | Visualizes the physical and emotional transition from traditional learning to formal schooling. |
| `shot_04` | Discovering knowledge | Childhood | 7.5s | Shows formal study of math, science, and languages sharpening his analytical curiosity. |
| `shot_05` | Discovering technology | Adolescence | 7.5s | Marks the pivotal adolescent encounter with a computer screen for the first time. |
| `shot_06` | Learning to code | Adolescence | 7.5s | Depicts active hands-on programming practice as he learns to translate ideas into instructions. |
| `shot_07` | Overcoming challenges | Adolescence | 7.5s | Adds emotional realism by showing late-night debugging and persistence through difficulty. |
| `shot_08` | Building together | Adolescence | 7.5s | Highlights peer collaboration and teamwork among young learners. |
| `shot_09` | Giving back | Young Adulthood | 8.0s | Delivers the payoff: as a developer, he demonstrates a useful digital tool to his local community. |
| `shot_10` | A brighter tomorrow | Young Adulthood | 8.0s | Visual motif returning to the opening highland landscape before closing. |
| `end_card` | Title & AI Disclosure | *(Separate)* | 3.0s | Distinct 3-second visible title & AI disclosure card required by the brief (included in the 60–90s total). |

---

## 5. User Tests (Real Audience Feedback Only)

> **Integrity Rule:** Never invent or pre-fill audience feedback. Complete these sections only after playing the real cuts to at least three people.

### User Test #1 — Audience Feedback Round 1
* **Status:** `COMPLETED` (`2026-11-26`)
* **Participants:** 3 participants from the intended audience *(individual identities and per-participant attributions were not recorded)*.
* **Feedback Received (Summary of 5 Suggestions):**
  1. Make the narration sound more human and natural, with a more authentic accent.
  2. Minimize echo and improve voice clarity.
  3. Add more relevant images to strengthen the visual storytelling.
  4. Consider using a local Ethiopian language with English subtitles.
  5. Make the background music more related to Ethiopian heritage and classical traditions.
* **Changes Adopted:**
  * **Voice Clarity & Echo Reduction (#2):** Updated offline TTS post-processing in `pipeline/providers/local_audio.py` (removed `+2.5 dB` `220 Hz` resonance boost, added `105 Hz` high-pass, `-2.8 dB` `250 Hz` de-box, `+2.6 dB` `3.2 kHz` consonant presence, gentle compression/limiting, and single final `loudnorm`), shortened plucked string decay (`0.9915`), removed `0.9s` synth pad smear, carved `-3 dB` (`1.8 kHz`) pocket on music, and tightened `sidechaincompress` ducking (`attack=45ms`, `release=650ms`) in `pipeline/stage6_assemble.py`.
  * **Ethiopian Heritage-Inspired Original Score (#5):** Replaced generic Western diatonic piano/pad progression in `local_score` (`procedural_pentatonic_heritage_82bpm_v2`) with original pure-Python synthesis grounded in pentatonic scale intervals (*Tizita*-major/minor intervals on `D`, `82 BPM`), featuring dry plucked string ostinatos, low open-fifth drone, breathy upper flute-like phrases, and muted percussive pulse. *(Original mathematical synthesis; makes no claim of live acoustic authenticity or authentic regional tuning beyond pentatonic intervals.)*
  * **Narration Naturalness (#1 — Partially Adopted):** Retained offline English Microsoft Windows TTS (`Microsoft George`, Option C) at `SpeakingRate=0.96` with clearer dry EQ; authentic Ethiopian-accented speech cannot be produced offline with built-in Windows `en-GB`/`en-US` voices and remains a noted limitation.
* **Suggestions Not Adopted & Reasons:**
  * **Switch Narration to Local Ethiopian Language (#4 — Deferred/Rejected for Main Cut):** Challenge brief requires narration in a chosen language plus English subtitles (English already complies); Windows offline TTS lacks Ethiopian language voices, `GEMINI_API_KEY` is unconfigured (`ALLOW_PAID_API=false`), and re-translating, re-timing, and verifying native pronunciation would jeopardize the `23:59 EAT` deadline.
  * **Add More Images / Regenerate Visuals (#3 — Not Adopted):** Storyboard already satisfies `8–12` shots (`10` shots = `80.014s` total inside `60–90s`). Adding shots or regenerating keyframes risks character drift, budget/deadline overrun, and breaking verified exports; all existing `outputs/keyframes/` images were preserved untouched.
* **Changes Made to `storyboard.json`:** *None — kept the existing 10-shot structure, English narration lines, and English `.srt` subtitles intact after verifying alignment with challenge requirements.*

### User Test #2 — Near-Final Cut
* **Status:** `PENDING` — To be conducted after reviewing the updated `80.014s` `16:9` and `9:16` exports (`a_brighter_tomorrow_16x9.mp4` / `9x16.mp4`).
* **Participants (at least 3):** *Not yet conducted.*
* **Observations & Quotes:** *None recorded yet.*
* **Changes Made Before Final Export:** *None yet.*
