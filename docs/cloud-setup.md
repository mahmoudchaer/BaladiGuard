# Cloud Setup (AWS DynamoDB + S3)

This guide explains how to run BaladiGuard against **real AWS** services instead of
Docker DynamoDB Local / in-memory storage / mock frontends.

Use this for staging demos and issue #115 end-to-end verification.
Keep secrets in local `.env` files only — never commit real credentials.
Prefer syncing those files from AWS Secrets Manager with
`python scripts/sync_env.py` (see [env-sync.md](./env-sync.md)) instead of sharing
`.env` files over chat.

## What “cloud mode” means

| Piece | Local / mock | Cloud |
|---|---|---|
| Mobile | Optional mock API | Real backend API (default) |
| Admin | Optional mock fixtures | Real backend API (default) |
| Backend DB | memory or DynamoDB Local | AWS DynamoDB |
| Photos | unset / failing upload | AWS S3 bucket |

## Prerequisites

- AWS account access in region `us-east-1` (or your chosen region)
- IAM user/role that can:
  - DynamoDB: create/describe tables, read/write items
  - S3: put/get objects on the report-photos bucket
  - Bedrock Runtime: `InvokeModel` / `Converse` for the chosen vision model (issue #17)
  - Amazon Location: `geo:SearchPlaceIndexForText` and `geo:SearchPlaceIndexForPosition`
    for the configured place index (issue #24)
- An S3 bucket for report photos (example name: `baladiguard-report-photos-dev`)
- Backend dependencies installed (`pip install -r requirements.txt`)
- For AI classification: enable model access in the Bedrock console
  (default `amazon.nova-lite-v1:0`)
- For live geocoding: create an Amazon Location place index and set
  `LOCATION_PLACE_INDEX_NAME` (leave empty to use the curated local Beirut index)

## 1. Configure environment

**Recommended:** pull the approved team bundle from Secrets Manager:

```bash
backend\.venv\Scripts\python.exe scripts\sync_env.py
```

To publish local changes back to the shared secret (no Console required):

```bash
backend\.venv\Scripts\python.exe scripts\sync_env.py --push
```

Details: [env-sync.md](./env-sync.md).

You can put shared AWS values in the **repo root** `.env` and backend-specific values in
`backend/.env`. The backend loads `backend/.env` first, then the root `.env` (root wins on
duplicate keys).

### Root `.env` (secrets + shared AWS)

```env
AWS_REGION=us-east-1
AWS_S3_BUCKET=baladiguard-report-photos-dev
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

### `backend/.env` (cloud DynamoDB)

```env
DATABASE_BACKEND=dynamodb
AWS_REGION=us-east-1
DYNAMODB_TABLE_PREFIX=baladiguard-
SEED_SAMPLE_TICKETS=false

# CRITICAL for cloud: leave empty so boto3 uses real AWS DynamoDB.
DYNAMODB_ENDPOINT_URL=

AWS_S3_BUCKET=baladiguard-report-photos-dev

# Optional for live Amazon Location geocoding (issue #24).
# Leave empty to use the curated local Beirut place index.
LOCATION_PLACE_INDEX_NAME=
```

If `DYNAMODB_ENDPOINT_URL=http://localhost:8001`, the API will use **Docker DynamoDB Local**
instead of cloud tables.

### Mobile / admin defaults

- Mobile: `EXPO_PUBLIC_ENABLE_MOCK_API=false` (see `mobile/.env.example`)
- Admin: `VITE_USE_MOCK_DATA=false` (see `admin/.env.example`)

For a physical phone, set:

```env
EXPO_PUBLIC_API_BASE_URL=http://<YOUR-PC-LAN-IP>:8000/v1
```

## 2. Create cloud tables and seed reference data

From `backend/`:

```bash
python scripts/db/migrate.py
python scripts/db/seed.py
```

Expected tables (prefix `baladiguard-` by default):

- `tickets`, `users`, `municipalities`, `departments`
- `ticket-status-history`, `ai-outputs`, `duplicate-groups`
- `categories`, `counters`

Seed loads municipalities, departments, and categories. Sample tickets stay off unless
`SEED_SAMPLE_TICKETS=true`.

## 3. Start the API against cloud services

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`--host 0.0.0.0` is required if a physical phone will call your PC.

Quick checks:

```bash
curl http://127.0.0.1:8000/docs
curl http://127.0.0.1:8000/v1/tickets
```

## 4. Automated cloud verification script

With cloud credentials configured and tables migrated, run:

```bash
cd backend
python scripts/verify_cloud_report_flow.py
```

This script **refuses** memory mode and DynamoDB Local. It proves:

1. Photo upload to the real S3 bucket (`head_object` succeeds)
2. Ticket create against cloud DynamoDB
3. `GET /v1/tickets/{ticketId}` returns the ticket with the same `imageObjectKey`
4. Ticket appears in `GET /v1/tickets` (admin list API)
5. Row exists in the cloud `baladiguard-tickets` table

Expected final line: `CLOUD_REPORT_FLOW_OK`

Note: `pytest` and `scripts/verify_report_submission_flow.py` still use in-memory /
moto-style paths for CI. That is intentional. Use `verify_cloud_report_flow.py` for
issue #115 cloud proof.

## 5. AI classification smoke / eval (Bedrock)

Standalone classifier (issue #17) — not yet wired into ticket submit.

Quick live smoke (multilingual text subset):

```bash
cd backend
python scripts/verify_classification.py
```

Labeled manual evaluation (accuracy + mismatches; **not CI**):

```bash
cd backend
python scripts/eval_classification.py
python scripts/eval_classification.py --text-only
python scripts/eval_classification.py --images-only
```

Eval details:

- Manifest: `backend/tests/fixtures/classification_eval_manifest.json`
- Text cases live in the repo; image binaries stay outside git (S3 by default)
- Configure with:
  - `CLASSIFICATION_EVAL_S3_PREFIX=classification-eval/`
  - `CLASSIFICATION_EVAL_S3_BUCKET=` (defaults to `AWS_S3_BUCKET`)
  - optional `CLASSIFICATION_EVAL_IMAGE_BASE_URL` for HTTPS-hosted refs
- Automated `pytest` validates the manifest schema and mocks Bedrock; it does **not**
  call the live model

Set `BEDROCK_MODEL_ID=amazon.nova-lite-v1:0` (default) and ensure the IAM user can call
Bedrock Runtime.

## 6. Location validation smoke (Amazon Location)

Standalone location validation (issue #24):

```bash
cd backend
python scripts/verify_location_validation.py
```

Requires `LOCATION_PLACE_INDEX_NAME` plus AWS credentials with Location access.
When the place index env var is unset, API tests use the local Beirut place index instead.

## 7. Manual end-to-end verification checklist

1. Mobile app mock mode is off (`EXPO_PUBLIC_ENABLE_MOCK_API=false`).
2. Submit a report with a photo from the mobile app (or run the script above).
3. Confirm the photo object appears in the S3 bucket under `reports/photos/`.
4. In DynamoDB console open **Explore items** for `baladiguard-tickets` (or click
   **Get live item count** — the overview counter can be stale).
5. Confirm `GET /v1/tickets` / `GET /v1/tickets/{ticketId}` returns that ticket.
6. Confirm the admin dashboard lists the ticket (`VITE_USE_MOCK_DATA` unset/false).

## Local Docker vs cloud (do not mix)

| Goal | `DATABASE_BACKEND` | `DYNAMODB_ENDPOINT_URL` |
|---|---|---|
| Unit tests / CI | `memory` (default in tests) | unused |
| Local Docker DB | `dynamodb` | `http://localhost:8001` |
| Cloud AWS DB | `dynamodb` | empty / unset |

## Troubleshooting

| Problem | Fix |
|---|---|
| `AccessDeniedException` on `CreateTable` / `PutItem` | Attach DynamoDB permissions to the IAM user |
| `AccessDeniedException` on S3 upload | Attach S3 put/get on the report-photos bucket |
| `AccessDeniedException` on Bedrock `Converse` / `InvokeModel` | Enable the model in Bedrock Model access and attach `bedrock:InvokeModel` for that model ARN |
| Tables still empty after migrate | Confirm region is correct and `DYNAMODB_ENDPOINT_URL` is empty |
| API still uses local Docker DB | Remove `DYNAMODB_ENDPOINT_URL` and restart Uvicorn |
| Phone cannot reach API | Use PC LAN IP, `--host 0.0.0.0`, same Wi‑Fi, firewall allows port 8000 |

## Related docs

- [Local Database Setup](./local-database-setup.md) — Docker DynamoDB Local
- [Database Design](./database.md) — table model
- [Complaint Categories](./complaint-categories.md) — taxonomy keys
