# Ethics, Consent, Licensing & AI Disclosure — A Brighter Tomorrow

## 1. Consent & Fictional-Character Policy (Zero-Score Gate Compliance)

* **Zero Real-Person Likeness or Voice:** *A Brighter Tomorrow* depicts a **100% fictional Ethiopian character** across three life stages. No real person's face, photograph, private family history, biography, or cloned voice is used anywhere in the film.
* **No Voice Cloning:** Narration uses a synthetic/prebuilt Gemini TTS voice (or offline placeholder audio during radio-cut drafting). Because no real individual is depicted or voiced, there is no unconsented real-person likeness or voice.
* **Privacy:** No personal or family-identifying names, addresses, or private stories are sent to free external API endpoints.

## 2. Cultural Respect & Representation

* **Yeqolo Temari (Shot 2):** Prompts are restricted to documented aspects of traditional Ethiopian Orthodox church reading education (*Nebab Bet*, modest white cotton *netela*, shaded church-compound courtyard, parchment *brana* / Ge'ez reading). Unverified objects (such as *gebeta*) and invented religious rituals are explicitly excluded.
* **Style Descriptions:** Visual prompts describe lighting, lens, and documentary qualities rather than imitating living artists.

## 3. Model & Tool Licensing Inventory

| Component | Model / Tool | Verified License | Notes |
| :--- | :--- | :--- | :--- |
| Script & TTS | Gemini API (`gemini-3.8-flash`, `gemini-3.8-flash-tts`) | Proprietary (Google Gemini API Terms) | Verify account tier & data terms in Google AI Studio. |
| Keyframes (Primary) | `@cf/black-forest-labs/flux-2-klein-4b` | **Apache 2.0** | Selected over `flux-2-klein-9b` (which has a non-commercial license). |
| Keyframes (Fallback) | `@cf/black-forest-labs/flux-1-schnell` | **Apache 2.0** | Permissive open-weight fallback on Cloudflare Workers AI. |
| Video (Primary) | `Wan-AI/Wan2.2-TI2V-5B` | **Apache 2.0** | Open weights; verify VRAM fit via Colab smoke test first. |
| Video (Alternative) | `tencent/HunyuanVideo-1.5` | **Tencent Community License** | Not Apache 2.0; carries territorial & anti-model-training restrictions. |
| Music | `ACE-Step/Ace-Step1.5` | **MIT License** | Outputs commercially usable per official model card; auxiliary encoders may carry Apache 2.0. |
| Assembly | FFmpeg | LGPL / GPL CLI | Local deterministic video/audio assembly. |

## 4. AI Disclosure & Provenance Plan

1. **Visible End Card:** A dedicated 3.0-second end card (`end_card` in `storyboard.json`) explicitly discloses that the film was created with AI assistance.
2. **Platform Disclosure:** When publishing on social platforms (YouTube, TikTok, Instagram/Meta), the platform's AI-generated content label will be switched on.
3. **Metadata Integrity:** Original provenance metadata/watermarks (such as SynthID or C2PA where provided) are preserved rather than stripped.
