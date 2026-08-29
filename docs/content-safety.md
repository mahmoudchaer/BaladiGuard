# Automated ticket content safety and image authenticity screening

This is the operational and contract reference for issue #319. Screening runs
**before public eligibility**. Staff review is the exception, not the default.
Authenticity scores are risk signals only and **never** auto-reject a report.

## End-to-end behavior

1. Ticket submit enrolls the report (`contentSafetyStatus=pending`) when
   `CONTENT_SAFETY_ENABLED=true` and enqueues a deterministic job
   `safety:{ticketId}:g{generation}`.
2. Classification, redaction, and content-safety jobs run independently.
   Redaction may finish first; it **must not** write `publicImageObjectKey`
   unless content safety has already `passed` (or the ticket predates this
   feature and is unenrolled).
3. The content-safety worker claims the job, loads the **private** original
   from `reports/photos/v2/`, and never persists image bytes, presigned URLs,
   or provider essays.
4. Text is gated by deterministic rules first (length, encoding, link count,
   repetition, obvious garbage). Remaining text is sent to Amazon Bedrock
   (`amazon.nova-lite-v1:0` by default) as untrusted data between
   `<<<CITIZEN_REPORT_*>>>` delimiters, using a structured tool call.
5. Images are screened with Rekognition `DetectModerationLabels`. Face/plate
   redaction stays a separate pipeline and is still required for any public
   photo.
6. Authenticity combines cheap file clues, Bedrock `DetectGeneratedContent`
   when boto3 exposes it (Titan/Nova watermarks only; a negative proves
   nothing), and the pinned Community Forensics DeepfakeDet ViT ONNX model.
   A high score alone still `passed`.
7. Disposition is stored as bounded codes. Citizen tracking and public APIs
   never expose detector internals.

## Disposition rules

| Outcome | When |
| --- | --- |
| `rejected` | Deterministic spam/garbage, or high-confidence sexual/hate/scam that is not a civic emergency |
| `private_only` | Graphic violence / accident evidence that is still a legitimate civic report. Staff can work; never public |
| `review_required` | Medium confidence, prompt-injection suspicion, authenticity **plus** another bad signal, or a fail-closed provider outage |
| `passed` | Clean text and image, **or** authenticity-high with no other bad signals |
| `failed` | Exhausted retries when fail-open (`CONTENT_SAFETY_FAIL_CLOSED=false`) |
| `superseded` | Reserved for a replaced generation |

Fail-closed (staging/production default): provider/storage outages become
`review_required`, never `passed`. Local/test default is fail-open so CI does
not need live AWS, unless `CONTENT_SAFETY_FAIL_CLOSED=true`.

Kill switch: `CONTENT_SAFETY_ENABLED=false` skips enrollment. Legacy tickets
without `contentSafetyStatus` stay unenrolled so historical redaction
auto-publish is unchanged.

## Public fail-closed race

Redaction and safety enqueue in parallel on submit. Public **text and photo**
are gated:

- `is_public_ticket_publishable()` requires enrolled `contentSafetyStatus=passed`
  (or an unenrolled pre-#319 ticket) in addition to staff public fields.
- Staff `PATCH /v1/tickets/{id}/public` refuses `PUBLISHED` until screening passed.
- `_approved_redacted_key` refuses raw originals, keys outside
  `reports/redacted/v1/<ticket-scope>/`, and any key while enrolled content
  safety is not `passed`.

If safety later `passed` and redaction already `completed`, the worker
promotes the approved candidate to `publicImageObjectKey`. If safety later
is not `passed`, any public key is cleared and a `PUBLISHED` ticket is moved
to `UNPUBLISHED` so it leaves the public GSI.

Staff list `GET /v1/tickets?contentSafetyStatus=review_required` is the
exception queue. Unredacted originals are returned only for `review_required`.

## Authenticity model

- Watermark detection only finds Amazon Titan / Nova Canvas marks. Current
  boto3/botocore still has no `DetectGeneratedContent` operation, so the
  worker records `AUTH_UNAVAILABLE` for that signal and keeps going. Titan
  Image Generator is EOL on Bedrock and Nova Canvas is legacy, so those
  models cannot be used to mint a watermarked sample until AWS ships the
  detector in a public SDK.
- The learned detector is the MIT-licensed
  [Community Forensics DeepfakeDet ViT](https://huggingface.co/buildborderless/CommunityForensics-DeepfakeDet-ViT)
  FP32 ONNX export (corrected weights; ~83 MB). No Git binary, no Hugging Face
  call at runtime after the checksummed download. Live checks: StyleGAN faces
  scored ~0.99–1.0 (`AUTH_ONNX_HIGH`) and still `passed` unless another risk
  signal was present; real photos scored ~0.00–0.03 (`AUTH_ONNX_LOW`). This
  model is a face/deepfake detector, not a general “any AI picture” detector.
- Docker pins URL + SHA256 into `/opt/models/community-forensics-deepfakedet-vit.onnx`.
- Local workers: `make download-authenticity-model` writes
  `backend/models/community-forensics-deepfakedet-vit.onnx`.
- Empty `AUTHENTICITY_DETECTION_MODEL` uses those default paths. A missing file
  records `AUTH_UNAVAILABLE`; the ticket is not failed on authenticity.

## Staff workspace

Staff (`municipal_staff` / `administrator` with ticket access) can approve,
mark private-only, reject, or reprocess a `review_required` generation.
Decisions are audited (`CONTENT_SAFETY_*`). Citizen receipts stay generic.

## Configuration

See `docs/configuration.md`. Important knobs:

| Variable | Default | Meaning |
| --- | --- | --- |
| `CONTENT_SAFETY_ENABLED` | `true` | Kill switch / enrollment |
| `CONTENT_SAFETY_FAIL_CLOSED` | true except local/test/development | Provider outage → review |
| `CONTENT_SAFETY_TEXT_MODEL_ID` | `BEDROCK_MODEL_ID` | Bedrock converse model |
| `CONTENT_SAFETY_IMAGE_REJECT_CONFIDENCE` | `80` | Rekognition high-severity cutoff |
| `CONTENT_SAFETY_IMAGE_REVIEW_CONFIDENCE` | `50` | Rekognition review cutoff |
| `CONTENT_SAFETY_AUTHENTICITY_REVIEW_SCORE` | `0.85` | ONNX score that can *contribute* to review when other signals exist |
| `AUTHENTICITY_DETECTION_MODEL` | pinned DeepfakeDet ONNX | Docker/local default path; override with an explicit `.onnx` file |
| `CONTENT_SAFETY_JOB_*` | same shape as redaction jobs | Attempts, timeout, backoff |

Worker:

```
make content-safety-worker
python -m app.workers.content_safety_worker --once
```

Staging and production run the same command as an ECS Fargate service
(`content-safety-worker`) next to `ai-worker` and `redaction-worker`. The
task role can call Bedrock `InvokeModel` (Nova text screening) and
Rekognition `DetectModerationLabels`. The authenticity ONNX model is already
baked into the backend image.

Create the DynamoDB table with `make db-migrate` (`content-safety-jobs`).

Threshold rationale, 311/Nextdoor/marketplace patterns, and FP/FN sampling
are in `docs/content-safety-research.md`.

## Out of scope

Municipality ownership, claiming AI detection proves authenticity, deleting
evidence, and moderating staff chat.

## Tests

- `backend/tests/test_content_safety.py`
- `backend/tests/eval/content_safety_cases.json`
- `admin/src/components/ContentSafetyReview.test.tsx`
