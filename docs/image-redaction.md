# Public image redaction

This document is the operational and contract reference for issue #253. The
feature keeps report originals private, detects and blurs faces and vehicle
license plates asynchronously, and exposes only an approved derivative to
public clients.

## End-to-end behavior

1. A report upload is stored as a private original under `reports/photos/v2/`.
2. Ticket submission enqueues the ticket's current redaction generation. The
   deterministic job id makes duplicate enqueue attempts idempotent.
3. A separate worker claims the job and changes the ticket from `pending` to
   `processing`.
4. The processor verifies the original's `upload-state=linked` and
   ticket-scope tags before reading it.
5. EXIF orientation is normalized. Amazon Rekognition `DetectFaces` detects
   faces and the local pretrained ONNX model detects general license plates.
6. All accepted boxes receive padding and Gaussian blur. The output is encoded
   as a new JPEG, which removes EXIF and other unnecessary embedded metadata.
7. The derivative is encrypted and written beneath the server-generated key
   `reports/redacted/v1/<ticket-scope>/g<generation>/<uuid>.jpg`.
8. Only a successfully completed derivative becomes
   `publicImageObjectKey`. Public list and detail responses validate that key
   and return its short-lived URL. They never fall back to `imageObjectKey`.

The report's publication state remains a staff decision. Redaction makes an
image eligible for an already published or later-published report; it does not
publish the report itself.

## Detection providers and model lifecycle

- Faces use Rekognition's built-in `DetectFaces`; no face training is needed.
- Plates use `yolo-v9-s-608-license-plate-end2end` from the MIT-licensed
  [open-image-models project](https://github.com/ankandrew/open-image-models).
- The production Docker build downloads the ONNX asset, verifies SHA-256
  `2b878b38d9aa07b6ddc3ea75c4ffcb39869bc5c218e0a14002f60ab2f7b0be9a`,
  and stores it at `/opt/models/license-plate.onnx`.
- No model binary is committed to Git, no Custom Labels project is required,
  and no model endpoint must remain running.
- Each worker process lazily creates one ONNX Runtime session and reuses it for
  later jobs. A restarted or additional worker creates its own session.

The model is embedded in the image rather than downloaded from S3 at runtime so
deployment is reproducible and worker startup does not depend on an extra
network request. Update both the model URL and checksum deliberately when
upgrading the model, then rebuild and re-run representative privacy tests.

## Confidence and fail-closed states

All returned face and plate candidates are blurred. A derivative completes
automatically only when every returned candidate meets
`IMAGE_REDACTION_AUTO_CONFIDENCE` (90% by default). Any candidate below that
threshold makes the derivative `review_required` and keeps it out of the public
projection. This intentionally favors privacy over reducing the review queue;
for example, a weak candidate might be a small or distant real plate rather than
model noise.

`IMAGE_REDACTION_REVIEW_CONFIDENCE` records the operational review boundary used
by staff correction controls in issue #255; candidates below automatic
confidence are not discarded and remain `review_required` until a staff
decision. Provider errors, malformed detector output, invalid images, unbound
keys, storage failures, and exhausted retries never expose the original. A
provider/configuration failure either retries or ends in `failed` /
`review_required` while public clients receive no new photo.

The current model is a general plate detector. It is not guaranteed to find
every tiny, obscured, unusual, or severely rotated plate. Threshold changes and
model upgrades require staging evaluation on representative local images.

## State and storage contracts

Ticket records keep these concepts separate:

- `imageObjectKey`: private original; staff-only projection.
- `publicImageObjectKey`: currently approved redacted derivative.
- `imageRedactionStatus`: `pending`, `processing`, `completed`, `failed`,
  `review_required`, or `private_only`.
- `imageRedactionCandidateObjectKey`: latest non-public derivative awaiting
  staff approval. Never projected to public clients.
- generation, detector/version, face/plate counts, completion time, reason code,
  persisted blur regions, and a bounded provenance history.

Jobs live in the `image-redaction-jobs` DynamoDB table. Claims are conditional
and have a timeout, retries use bounded exponential backoff, and stale claims
are recoverable. Final ticket mutation is conditional on generation and claim
token, preventing an older worker from replacing a newer result.

Derivatives are written with AES-256 server-side encryption, private cache
headers, ticket/generation/approval tags, and a source SHA-256 fingerprint. S3
Block Public Access remains enabled; public access uses a short-lived presigned
GET URL. Clients cannot submit or approve object keys.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `IMAGE_REDACTION_ENABLED` | `true` | Enables the hybrid detector when the configured detector is `aws_rekognition` |
| `IMAGE_REDACTION_DETECTOR` | `aws_rekognition` | Selects the production detector adapter |
| `PLATE_DETECTION_MODEL` | named pretrained model | Named model for development or local ONNX path in production |
| `IMAGE_REDACTION_REVIEW_CONFIDENCE` | `60` | Operational boundary reserved for manual review/correction controls (#255); candidates are not discarded |
| `IMAGE_REDACTION_AUTO_CONFIDENCE` | `90` | Minimum confidence for automatic approval |
| `IMAGE_REDACTION_BLUR_RADIUS` | `18` | Base Gaussian blur radius |
| `IMAGE_REDACTION_BOX_PADDING` | `0.08` | Fractional padding added around each box |
| `IMAGE_REDACTION_JOB_MAX_ATTEMPTS` | `5` | Attempts before dead-letter failure |
| `IMAGE_REDACTION_JOB_TIMEOUT_SECONDS` | `300` | Claim timeout before stale recovery |
| `IMAGE_REDACTION_JOB_BACKOFF_BASE_SECONDS` | `5` | Initial retry delay |
| `IMAGE_REDACTION_JOB_BACKOFF_MAX_SECONDS` | `300` | Maximum retry delay |

Production also requires `AWS_REGION`, `AWS_S3_BUCKET`, DynamoDB configuration,
and normal AWS credential resolution. Do not place access keys in source or the
container image.

## Deployment

Run database migrations, deploy the updated backend image, and run both the API
and a continuously supervised worker from that image:

```bash
python -m app.workers.image_redaction_worker
```

For controlled operations, `--once` processes at most one job and `--drain`
processes until the queue is idle. Production should use the default continuous
mode with restart supervision. If the worker is absent, jobs remain pending and
public clients see a safe placeholder; the original is not exposed.

The runtime identity needs the existing S3/DynamoDB permissions plus only
`rekognition:DetectFaces` for this detector. It does not need
`rekognition:DetectCustomLabels` or Custom Labels management permissions.

Before enabling production traffic:

1. Apply migrations and backup controls.
2. Confirm S3 encryption, versioning, Block Public Access, and lifecycle rules.
3. Confirm the worker identity can call `DetectFaces` in `AWS_REGION`.
4. Start the worker and submit a staging report containing representative faces
   and plates.
5. Verify original staff access, derivative tags/metadata, public list/detail
   display, placeholder behavior, and the reprocessing path.

## Reprocessing and recovery

Authorized staff can request a new generation with:

```text
POST /v1/tickets/{ticketId}/image-redaction/reprocess
```

Reprocessing leaves the previous approved derivative active until the new
generation completes successfully, then swaps the key atomically. A failed or
review-required replacement therefore cannot remove or overwrite a previously
safe public image.

Operational recovery:

- `pending` with no job: queue reconciliation recreates the deterministic job.
- stale `processing`: the worker recovers the expired claim and requeues it.
- transient provider/storage error: bounded retry with exponential backoff.
- exhausted retries: inspect the safe reason code, repair configuration or the
  provider, then use the scoped reprocess endpoint.
- suspected bad automatic result: authorized staff use the ticket Image privacy
  review workspace (issue #255) to approve, reject as private-only, reprocess,
  or add bounded manual blur regions. The original is never edited.

## Staff review controls (issue #255)

Authorized staff who can already access the ticket may:

- `GET /v1/tickets/{ticketId}/image-redaction/review` — original + candidate
  URLs, status, and decision flags. Out-of-scope staff receive `404`.
- `POST /v1/tickets/{ticketId}/image-redaction/approve` — promote the current
  candidate to `publicImageObjectKey` when `expectedGeneration` and
  `expectedCandidateRevision` match. The public key is copied from the stored
  candidate in the same conditional write.
- `POST /v1/tickets/{ticketId}/image-redaction/reject` — mark `private_only`
  without publishing the candidate.
- `POST /v1/tickets/{ticketId}/image-redaction/manual-regions` — validate
  boxes that lie fully inside the image (`0 <= left/top`, positive size,
  `left+width <= 1`, `top+height <= 1`), blur the original plus prior regions,
  and write a **new** derivative with an incremented candidate revision.
  Status stays `review_required` until approve.
- Existing `POST /v1/tickets/{ticketId}/image-redaction/reprocess`.

All four decisions record the authenticated actor, role, timestamp, processor
version, and action in ticket audit history. Concurrent decisions for a stale
generation or candidate revision return `409 REDACTION_REVIEW_CONFLICT`. Public
clients still receive a photo only after an approved derivative key is recorded.

Do not log images, image bytes, citizen data, presigned URLs, credentials, or
provider payloads while diagnosing. Logs use opaque ticket/job ids and bounded
reason codes.

Backup and restore follow [the production runbook](./production-backup-restore.md).
The controls cover the redaction job table, ticket provenance, private originals,
and `reports/redacted/` objects. Restores must use isolated table names and the
`restore-tests/` S3 prefix; never restore over active production resources.

## Verification

Relevant automated coverage is in:

- `backend/tests/test_image_redaction.py`
- `backend/tests/test_image_redaction_review.py`
- `backend/tests/test_image_redaction_dynamodb.py`
- `backend/tests/test_public_ticket_browsing.py`
- `backend/tests/test_update_ticket_public_content.py`
- `backend/tests/test_backup_controls.py`
- staff authorization and privacy-lifecycle suites

At minimum, run backend lint/format, both pytest marker groups, container build,
and the repository CI/Security workflows. A staging smoke test must include a
face, a clear plate, no detections, multiple detections, and a deliberately
borderline image that remains private for review.
