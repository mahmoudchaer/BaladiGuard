# Local Database Setup (DynamoDB)

BaladiGuard MVP uses **Amazon DynamoDB**. For local development, run **DynamoDB Local** in Docker and apply idempotent migration/seed scripts.

The canonical persistence model is defined in [database.md](./database.md).

## Migration approach

| Item          | Choice                                                      |
| ------------- | ----------------------------------------------------------- |
| Database      | DynamoDB                                                    |
| Local runtime | DynamoDB Local (Docker)                                     |
| Migrations    | Idempotent Python scripts (`create_table` if not exists)    |
| Seeds         | JSON fixtures loaded by `backend/scripts/db/seed.py`        |
| Table design  | One table per entity, camelCase attributes matching the API |

Run migrations before seeds. Use `make db-reset` to drop and recreate all project tables during development.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Python 3.11+
- Backend dependencies installed:

```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Quick start

From the repository root:

```bash
make db-up
make db-migrate
make db-seed
```

This path is for **Docker DynamoDB Local**. For AWS cloud DynamoDB + S3 (issue #115),
use [cloud-setup.md](./cloud-setup.md) instead (`DYNAMODB_ENDPOINT_URL` empty).

Start the API against DynamoDB Local:

```bash
cd backend
set DATABASE_BACKEND=dynamodb
set DYNAMODB_ENDPOINT_URL=http://localhost:8001
set AWS_REGION=us-east-1
set AWS_ACCESS_KEY_ID=local
set AWS_SECRET_ACCESS_KEY=local
uvicorn app.main:app --reload --port 8000
```

On macOS/Linux, use `export` instead of `set`.

Copy `backend/.env.example` to `backend/.env` and set `DATABASE_BACKEND=dynamodb`. Keep `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as `local` for DynamoDB Local — boto3 requires credentials even though DynamoDB Local does not validate them.

## Make commands

| Command           | Description                                          |
| ----------------- | ---------------------------------------------------- |
| `make db-up`      | Start DynamoDB Local on port `8001`                  |
| `make db-down`    | Stop the Docker Compose stack                        |
| `make db-migrate` | Create MVP tables (idempotent)                       |
| `make db-seed`    | Load municipalities, departments, and categories     |
| `make db-reset`   | Delete project tables, recreate them, and seed again |

## Current tables (including Sprint 6 citizen persistence)

All tables use the `DYNAMODB_TABLE_PREFIX` (default `baladiguard-`).
Citizen account tables are created by `make db-migrate` (issue #169). Public OTP
request/verify HTTP routes remain #170; the challenge/session tables are the shared
persistence foundation.

| Table                                | Partition key      | GSIs                                                                                        |
| ------------------------------------ | ------------------ | ------------------------------------------------------------------------------------------- |
| `baladiguard-tickets`                | `ticketId`         | `ticketNumber-index`, `trackingCode-index`, `ownerUserId-ownerHistorySortKey-index`         |
| `baladiguard-users`                  | `userId`           | `phone-index` (lookup/reconciliation aid only; not uniqueness authority). No `email-index`. |
| `baladiguard-phone-claims`           | `phoneKey`         | No GSI; transactional phone-uniqueness authority.                                           |
| `baladiguard-citizen-otp-challenges` | `challengeId`      | TTL on `ttl`; plain OTP codes are never stored.                                             |
| `baladiguard-citizen-sessions`       | `sessionId`        | `userId-index` for account-wide revocation; TTL on `ttl`.                                   |
| `baladiguard-staff-users`            | `staffId`          | Staff accounts (#175); password hashes never returned.                                      |
| `baladiguard-staff-username-claims`  | `usernameKey`      | Transactional username uniqueness (`USERNAME#…`).                                           |
| `baladiguard-municipalities`         | `municipalityId`   | —                                                                                           |
| `baladiguard-departments`            | `departmentId`     | `municipalityId-index`                                                                      |
| `baladiguard-ticket-status-history`  | `historyId`        | `ticketId-index`                                                                            |
| `baladiguard-ticket-audit-history`   | `auditId`          | `ticketId-index` (ticket mutation audit, #143 / #181)                                       |
| `baladiguard-account-audit`          | `auditId`          | `targetStaffId-index` (staff/admin account audit, #181)                                     |
| `baladiguard-ai-outputs`             | `aiOutputId`       | `ticketId-index`                                                                            |
| `baladiguard-duplicate-groups`       | `duplicateGroupId` | —                                                                                           |
| `baladiguard-categories`             | `categoryId`       | —                                                                                           |
| `baladiguard-counters`               | `counterId`        | — (ticket number sequence)                                                                  |
| `baladiguard-rate-limit-buckets`     | `bucketKey`        | Shared rate-limit counters (#186); TTL on `expiresAt`.                                      |
| `baladiguard-ticket-submission-claims` | `idempotencyKey` | Ticket create Idempotency-Key claims + replay (#258); TTL on `ttl` (14-day completed retention). |

### Legacy `users` table migration

Environments created before #169 may still have an `email-index` GSI on `users`.
Email is no longer an identity key; new migrations create `users` without that index
and add `phone-claims`, `citizen-otp-challenges`, and `citizen-sessions`.

- **Local DynamoDB:** run `make db-reset` (delete + recreate + seed).
- **Cloud / shared:** recreate or replace the `users` table definition (delete
  `email-index`, keep optional `phone-index`), then create the three new tables.
  Do not rely on `email-index` for lookups. Existing citizen rows (if any) must be
  backfilled into `phone-claims` with `phoneKey = PHONE#<E.164>` before uniqueness
  can be enforced; empty environments need no backfill.

Report images are stored on the ticket as `imageObjectKey` (no separate images table in MVP).

## Seed data

Default seed loads:

- **1 municipality** — Beirut Municipality
- **8 departments** — roads, waste, lighting, water, noise, traffic, drainage, public facilities
- **10 categories** — including `PENDING_CLASSIFICATION`; see
  [Complaint Categories](complaint-categories.md) for stable keys, labels, examples, and department mappings
- **Demo staff accounts** (when `SEED_DEMO_STAFF=true`): `admin` (administrator) and `staff`
  (municipal_staff for Beirut roads + lighting), password from `DEMO_STAFF_PASSWORD`

### Staff password reset (issue #178)

Staff recovery uses `staff-password-reset-challenges` (hashed 6-digit codes, TTL attribute `ttl`).
Request/confirm endpoints are account-neutral and never return codes over HTTP. In local/test/
development, automated tests read issued codes via the in-process peek adapter
(`staff_password_reset_service.peek_dev_reset_code`). Production email/SMS delivery is not
required for MVP; configure a real provider later behind the same request lifecycle.

Citizens have no password-reset path (OTP-only auth).

Optional sample tickets from `mock_tickets.json`:

```bash
set SEED_SAMPLE_TICKETS=true
make db-seed
```

Or bypass env-file collisions entirely:

```bash
cd backend
python scripts/db/seed.py --with-samples
```

Sample tickets are **off by default** so local `POST /v1/tickets` testing starts from a clean ticket
table. When enabled, the seed loads a synthetic Sprint 6 demo story: three phone-verified demo
citizens, owned reports across every MVP category, staff-reviewed AI fields, public-safe browsing
projections for published reports, status history timelines, and a duplicate group. Public sample
records use coarse `publicLocationLabel` values and approved `publicDescription` text rather than
raw citizen addresses or descriptions.

## Environment variables

| Variable                | Default        | Description                                                    |
| ----------------------- | -------------- | -------------------------------------------------------------- |
| `DATABASE_BACKEND`      | `memory`       | `memory` for tests; `dynamodb` for local/prod persistence      |
| `DYNAMODB_ENDPOINT_URL` | —              | `http://localhost:8001` for DynamoDB Local                     |
| `AWS_REGION`            | `us-east-1`    | AWS region for boto3                                           |
| `AWS_ACCESS_KEY_ID`     | —              | Use `local` for DynamoDB Local (dummy value required by boto3) |
| `AWS_SECRET_ACCESS_KEY` | —              | Use `local` for DynamoDB Local (dummy value required by boto3) |
| `DYNAMODB_TABLE_PREFIX` | `baladiguard-` | Prefix for all table names                                     |
| `SEED_SAMPLE_TICKETS`   | `false`        | Load `mock_tickets.json` when seeding                          |

## Tests vs real local persistence

These are separate paths:

| Path                       | What it uses                                                                                 | When to use it                                             |
| -------------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Automated tests (`pytest`) | Default `DATABASE_BACKEND=memory`, plus one issue #9 Dynamo test that uses **moto**          | CI and everyday backend test runs — **no Docker required** |
| Real local API persistence | `DATABASE_BACKEND=dynamodb` + DynamoDB Local + `make db-migrate` (+ optional `make db-seed`) | Manual/demo runs against a real local database             |

So yes: for a real run (not just CI), you still need DynamoDB Local up, migrations applied, and `DATABASE_BACKEND=dynamodb`. The moto test only proves the submit → save → get-by-ID path in CI; it does not replace local DynamoDB setup.

Issue #9 DynamoDB persistence is covered in `tests/test_submit_ticket_dynamodb.py` with moto (no Docker). Seed data is optional for submit/get-by-ID; migrations create the ticket tables required for persistence.

## Durable AI worker

Ticket submission persists the ticket with `aiProcessingStatus=pending` before
returning `201`; that pending state is the durable outbox. The API then makes a
best-effort idempotent write to `ai-processing-jobs`. If that second write is
temporarily unavailable, the accepted response is unchanged (so clients do not
retry and duplicate the report), and the worker recreates the missing job from
the pending ticket on its next poll. AI calls do not run inside the API process.
Start a separate deterministic local worker in another terminal:

```bash
make ai-worker
```

`make ai-worker-once` processes at most one available job and
`make ai-worker-drain` processes all jobs whose backoff delay has elapsed. After
a crash, the worker reconciles pending tickets, recovers expired claims, and
continues. Exhausted jobs remain `dead_lettered` with a safe operator reason.
Replay one after fixing the cause with:

```bash
cd backend
python -m app.workers.ai_worker --replay ai:tkt_<ticket-id> --once
```

## Verify setup

1. Run `make db-migrate` — all tables should report as created or already existing.
2. Run `make db-seed` — should print counts for municipalities, departments, and categories. Optional for a basic submit/get check; required if your flow depends on seed reference data.
3. Start the API with `DATABASE_BACKEND=dynamodb`.
4. Obtain a **contribution-ready** citizen session (verify OTP + complete profile with full name and email). Demo/local account setup is described in the root [README.md](../README.md) and [MVP_API_CONTRACT.md](./MVP_API_CONTRACT.md). Environment variables come from `scripts/sync_env.py` / [env-sync.md](./env-sync.md) and [configuration.md](./configuration.md) — do not invent a parallel env workflow.
5. Submit a ticket with the citizen Bearer token (client does **not** send contact/owner fields):

```bash
curl -X POST http://localhost:8000/v1/tickets ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer <citizen_access_token>" ^
  -d "{\"description\":\"Large pothole near the university gate causing traffic disruption.\",\"location\":{\"latitude\":33.896112,\"longitude\":35.478419,\"addressText\":\"Near AUB Main Gate, Hamra, Beirut\",\"source\":\"PLACEHOLDER\"},\"imageObjectKey\":\"reports/mock/photo.jpg\",\"clientMetadata\":{\"platform\":\"ios\",\"appVersion\":\"0.1.0\"}}"
```

Report photos use `POST /v1/uploads/report-photo` with the **same** contribution-ready Bearer token before submit when you need a real `imageObjectKey`.

6. Confirm staff can load the ticket after login (public guest `GET /v1/tickets/{id}` is not the staff dashboard read path — use staff auth per the contract):

```bash
curl http://localhost:8000/v1/tickets/<ticketId> ^
  -H "Authorization: Bearer <staff_access_token>"
```

Tracking-code lookup remains available on the public track route documented in `MVP_API_CONTRACT.md`.

7. Validate mock fixtures (optional):

```bash
cd backend
PYTHONPATH=. python scripts/validate_mock_tickets.py
```

## Troubleshooting

| Problem                                 | Fix                                                                               |
| --------------------------------------- | --------------------------------------------------------------------------------- |
| `Could not connect to the endpoint URL` | Run `make db-up` and confirm `DYNAMODB_ENDPOINT_URL=http://localhost:8001`        |
| `Unable to locate credentials`          | Set `AWS_ACCESS_KEY_ID=local` and `AWS_SECRET_ACCESS_KEY=local` in `backend/.env` |
| `ResourceInUseException`                | Table already exists — safe to ignore during migrate                              |
| API still uses in-memory storage        | Set `DATABASE_BACKEND=dynamodb` and restart Uvicorn                               |
| Port `8001` in use                      | Change the host port in `docker-compose.yml` and update `DYNAMODB_ENDPOINT_URL`   |

## Cloud / production note

Cloud DynamoDB uses the same migration and seed scripts with `DATABASE_BACKEND=dynamodb` and
an empty `DYNAMODB_ENDPOINT_URL` (so boto3 targets real AWS endpoints).

See [cloud-setup.md](./cloud-setup.md) for AWS credentials, S3, migrate/seed against cloud, and
end-to-end verification.
