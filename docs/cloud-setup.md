# Cloud Setup (AWS DynamoDB + S3)

This guide explains how to run BaladiGuard against **real AWS** services instead of
Docker DynamoDB Local / in-memory storage / mock frontends.

Use this for staging demos and issue #115 end-to-end verification.
Keep secrets in local `.env` files only — never commit real credentials.

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
- An S3 bucket for report photos (example name: `baladiguard-report-photos-dev`)
- Backend dependencies installed (`pip install -r requirements.txt`)

## 1. Configure environment

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

## 4. End-to-end verification checklist

1. Mobile app mock mode is off.
2. Submit a report with a photo from the mobile app.
3. Confirm the photo object appears in the S3 bucket.
4. Confirm a new item appears in DynamoDB table `baladiguard-tickets` with `imageObjectKey`.
5. Confirm `GET /v1/tickets` / `GET /v1/tickets/{ticketId}` returns that ticket.
6. Confirm the admin dashboard lists the ticket (mock mode off).

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
| Tables still empty after migrate | Confirm region is correct and `DYNAMODB_ENDPOINT_URL` is empty |
| API still uses local Docker DB | Remove `DYNAMODB_ENDPOINT_URL` and restart Uvicorn |
| Phone cannot reach API | Use PC LAN IP, `--host 0.0.0.0`, same Wi‑Fi, firewall allows port 8000 |

## Related docs

- [Local Database Setup](./local-database-setup.md) — Docker DynamoDB Local
- [Database Design](./database.md) — table model
- [Complaint Categories](./complaint-categories.md) — taxonomy keys
