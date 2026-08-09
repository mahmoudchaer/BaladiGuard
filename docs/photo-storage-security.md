# Report photo storage security

Report photos are private contribution artifacts. They are never served from a
public bucket URL.

## Ingestion controls

- `POST /v1/uploads/report-photo` requires a contribution-ready citizen session
  and uses the production shared upload rate limit.
- The service reads at most 5 MiB, decodes the image with Pillow, rejects
  malformed/decompression-bomb/animated/over-20-megapixel content, and requires
  the decoded format to match the declared extension and MIME type.
- JPEG, PNG, and WebP are re-encoded. EXIF and other unnecessary metadata are
  not copied to the stored object.
- Keys use an opaque owner scope plus a random UUID; the original filename and
  citizen identifier are not stored in the key.
- Objects are written with AES-256 server-side encryption and initially tagged
  `upload-state=orphan`.

Ticket submission verifies the owner scope and S3 ownership tag, then acquires a
conditional record in `photo-upload-claims`. That DynamoDB conditional write (or
the locked in-memory equivalent) gives concurrent submissions exactly one
winner before the object changes to `upload-state=linked`. If ticket persistence
fails, the service restores the orphan tag and conditionally releases the claim,
so the citizen can safely retry the same upload. Legacy keys created before this
scheme remain readable for migration, but new uploads always use
`reports/photos/v2/`.

## Private access

Staff and approved public projections receive an S3 presigned GET URL, not
credentials or a public object URL. The default lifetime is five minutes and is
controlled by `S3_PRESIGNED_URL_TTL_SECONDS` (minimum 30 seconds). Raw upload
keys are not exposed by citizen-safe endpoints.

## Bucket controls and orphan cleanup

Apply and audit the bucket controls with:

```bash
cd backend
python scripts/backup/backup_controls.py --apply
python scripts/backup/backup_controls.py
```

The controls enable bucket versioning/default AES-256 encryption, enable all
four S3 Block Public Access settings, retain non-current photo versions for 90
days, abort incomplete multipart uploads, and delete objects still tagged
`upload-state=orphan` after two days. Linked photos are not matched by the orphan
rule.

Do not log presigned URLs: their query parameters are temporary credentials.
Application errors intentionally return generic storage messages.
