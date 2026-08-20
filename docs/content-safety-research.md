# Content-safety research and threshold rationale

This note is the #319 research companion to `docs/content-safety.md`. It records
what we copied from 311 / neighborhood / marketplace moderation, where false
positives and false negatives show up, and why the default knobs are `80` /
`50` / `0.85`.

## What other civic and marketplace pipelines do

| Pattern | Typical policy | What we copied |
| --- | --- | --- |
| City 311 / SeeClickFix | Civic reports (crashes, floods, trash) stay in the work queue even when language is graphic. Public maps hide PII and non-civic abuse. | Staff work is never blocked by screening. `private_only` keeps graphic civic evidence off the feed. |
| Nextdoor | Neighborhood posts are fail-closed for sexual/hate; “urgent safety” posts get a human exception rather than an auto-delete of the underlying report. | High-confidence `IMAGE_SEXUAL` / `IMAGE_HATE` still auto-reject. Civic text remaps away from quarantine unless the model says `publishability=unsafe`. |
| Marketplace (Facebook/OLX-style) | Suggestive clothing and swimwear go to review, not auto-takedown, because outdoor photos of people are common. Explicit sexual activity is a hard block. | Exact Rekognition label match. `Non-Explicit Nudity` and swimwear map to `IMAGE_NUDITY_SUGGESTIVE` → `review_required`, never `IMAGE_SEXUAL`. |
| Authenticity / “AI image” badges | Marketplaces treat generators as a **risk signal**. They do not auto-reject a listing on a detector score alone (too many false positives on compression, screenshots, and real faces). | ONNX / watermark scores never auto-reject. `AUTH_ONNX_HIGH` only contributes to review when another bounded signal is present. |

Sampling process used to set defaults:

1. Deterministic text gates on the eval fixture (`tests/eval/content_safety_cases.json`) for spam, garbage, and prompt-injection.
2. Live Nova Lite civic EN/AR/FR/Arabizi samples (pothole, crash, fire, flood) — all `passed` unless the model marked `unsafe`.
3. Rekognition label fixtures (not live NSFW uploads) for explicit vs non-explicit vs swimwear parents.
4. Live DeepfakeDet ONNX: StyleGAN faces ~0.99–1.0 (`AUTH_ONNX_HIGH`) still `passed`; real photos ~0.00–0.03. Screenshot EXIF plus a high score → `review_required`.

False-positive classes we optimized against:

- Civic emergencies described with violent language (crash, fire, flood).
- People in swimwear / wet clothes at a flooded street or beach rescue.
- High deepfake scores on real faces with no other risk signal.

False-negative classes we still accept as staff review rather than auto-pass:

- Prompt-injection / delimiter-break attempts (`TEXT_PROMPT_INJECTION` or `review_required`).
- Medium-confidence Rekognition labels (`>=50` and `<80`).
- Provider outages in staging/production (`review_required`, fail-closed).

## Threshold rationale

| Knob | Default | Why |
| --- | --- | --- |
| Rekognition reject (`CONTENT_SAFETY_IMAGE_REJECT_CONFIDENCE`) | **80** | AWS moderation examples treat ~80 as “high confidence” for auto-action. We only auto-reject **explicit** sexual/hate at this cutoff. Civic emergency does **not** override those two classes. |
| Rekognition review (`CONTENT_SAFETY_IMAGE_REVIEW_CONFIDENCE`) | **50** | Rekognition `MinConfidence` default band. Labels below 50 are ignored. Graphic violence at any mapped confidence is `private_only` so staff can still work. Suggestive/non-explicit labels review at any confidence so swimwear cannot skip to `passed`. |
| ONNX authenticity review (`CONTENT_SAFETY_AUTHENTICITY_REVIEW_SCORE`) | **0.85** | Live DeepfakeDet scores on StyleGAN faces sat at 0.99+ and real photos under 0.05. 0.85 is below the fake cluster and far above the real cluster. The score is still only a **signal**; it cannot reject. |

Do not raise the sexual reject cutoff to “fix” swimwear. Swimwear must not map to `IMAGE_SEXUAL` at all.

## Eval fixture

`backend/tests/eval/content_safety_cases.json` covers:

- Civic multilingual text (EN, AR, FR, Arabizi) — deterministic rules return no hit.
- Spam links, garbage repetition, prompt-injection wording.
- Delimiter-break text that must be stripped before the Bedrock template.
- Image-label rows for swimwear/civic (review) vs explicit nudity (reject).

CI does not call live Nova or Rekognition. Live provider behavior is documented in `docs/content-safety.md`.
