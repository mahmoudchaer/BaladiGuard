# Local Database Setup (DynamoDB)

BaladiGuard MVP uses **Amazon DynamoDB**. For local development, run **DynamoDB Local** in Docker and apply idempotent migration/seed scripts.

The canonical persistence model is defined in [database.md](./database.md).

## Migration approach

| Item | Choice |
|---|---|
| Database | DynamoDB |
| Local runtime | DynamoDB Local (Docker) |
| Migrations | Idempotent Python scripts (`create_table` if not exists) |
| Seeds | JSON fixtures loaded by `backend/scripts/db/seed.py` |
| Table design | One table per entity, camelCase attributes matching the API |

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

Start the API against DynamoDB:

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

| Command | Description |
|---|---|
| `make db-up` | Start DynamoDB Local on port `8001` |
| `make db-down` | Stop the Docker Compose stack |
| `make db-migrate` | Create MVP tables (idempotent) |
| `make db-seed` | Load municipalities, departments, and categories |
| `make db-reset` | Delete project tables, recreate them, and seed again |

## Tables created

All tables use the `DYNAMODB_TABLE_PREFIX` (default `baladiguard-`).

| Table | Partition key | GSIs |
|---|---|---|
| `baladiguard-tickets` | `ticketId` | `ticketNumber-index`, `trackingCode-index` |
| `baladiguard-users` | `userId` | `phone-index`, `email-index` |
| `baladiguard-municipalities` | `municipalityId` | — |
| `baladiguard-departments` | `departmentId` | `municipalityId-index` |
| `baladiguard-ticket-status-history` | `historyId` | `ticketId-index` |
| `baladiguard-ai-outputs` | `aiOutputId` | `ticketId-index` |
| `baladiguard-duplicate-groups` | `duplicateGroupId` | — |
| `baladiguard-categories` | `categoryId` | — |
| `baladiguard-counters` | `counterId` | — (ticket number sequence) |

Report images are stored on the ticket as `imageObjectKey` (no separate images table in MVP).

## Seed data

Default seed loads:

- **1 municipality** — Beirut Municipality
- **8 departments** — roads, waste, lighting, water, noise, traffic, drainage, public facilities
- **10 categories** — including `PENDING_CLASSIFICATION` and the mock taxonomy

Optional sample tickets from `mock_tickets.json`:

```bash
set SEED_SAMPLE_TICKETS=true
make db-seed
```

Sample tickets are **off by default** so local `POST /v1/tickets` testing starts from a clean ticket table.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_BACKEND` | `memory` | `memory` for tests; `dynamodb` for local/prod persistence |
| `DYNAMODB_ENDPOINT_URL` | — | `http://localhost:8001` for DynamoDB Local |
| `AWS_REGION` | `us-east-1` | AWS region for boto3 |
| `AWS_ACCESS_KEY_ID` | — | Use `local` for DynamoDB Local (dummy value required by boto3) |
| `AWS_SECRET_ACCESS_KEY` | — | Use `local` for DynamoDB Local (dummy value required by boto3) |
| `DYNAMODB_TABLE_PREFIX` | `baladiguard-` | Prefix for all table names |
| `SEED_SAMPLE_TICKETS` | `false` | Load `mock_tickets.json` when seeding |

Most unit tests force `DATABASE_BACKEND=memory` and do not require Docker. Issue #9 DynamoDB persistence is covered by `tests/test_submit_ticket_dynamodb.py` using moto (no Docker required).

## Verify setup

1. Run `make db-migrate` — all tables should report as created or already existing.
2. Run `make db-seed` — should print counts for municipalities, departments, and categories.
3. Start the API with `DATABASE_BACKEND=dynamodb` and submit a ticket:

```bash
curl -X POST http://localhost:8000/v1/tickets ^
  -H "Content-Type: application/json" ^
  -d "{\"description\":\"Large pothole near the university gate causing traffic disruption.\",\"contact\":{\"phone\":\"+96170123456\"},\"location\":{\"latitude\":33.896112,\"longitude\":35.478419,\"addressText\":\"Near AUB Main Gate, Hamra, Beirut\",\"source\":\"PLACEHOLDER\"},\"imageObjectKey\":\"reports/mock/photo.jpg\",\"clientMetadata\":{\"platform\":\"ios\",\"appVersion\":\"0.1.0\"}}"
```

4. Confirm the saved ticket can be retrieved by ID (for dashboard use):

```bash
curl http://localhost:8000/v1/tickets/<ticketId>
```

5. Validate mock fixtures (optional):

```bash
cd backend
PYTHONPATH=. python scripts/validate_mock_tickets.py
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Could not connect to the endpoint URL` | Run `make db-up` and confirm `DYNAMODB_ENDPOINT_URL=http://localhost:8001` |
| `Unable to locate credentials` | Set `AWS_ACCESS_KEY_ID=local` and `AWS_SECRET_ACCESS_KEY=local` in `backend/.env` |
| `ResourceInUseException` | Table already exists — safe to ignore during migrate |
| API still uses in-memory storage | Set `DATABASE_BACKEND=dynamodb` and restart Uvicorn |
| Port `8001` in use | Change the host port in `docker-compose.yml` and update `DYNAMODB_ENDPOINT_URL` |

## Production note

Production/staging DynamoDB tables will use the same migration scripts without `DYNAMODB_ENDPOINT_URL` set, so boto3 targets real AWS endpoints. That deployment wiring is out of scope for this issue.
