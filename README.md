# BaladiGuard

BaladiGuard is an AI-powered municipal complaint and infrastructure maintenance platform that enables citizens to report public infrastructure issues while helping municipalities efficiently manage, prioritize, and resolve them.

## Overview

Municipal infrastructure complaints are often submitted through fragmented channels such as phone calls, messaging applications, or social media, making them difficult to track, prioritize, and manage.

BaladiGuard provides a centralized platform where citizens can submit reports using a mobile application. The system assists municipalities by organizing complaints into structured maintenance tickets and providing a unified workflow for managing infrastructure issues.

## Key Features

### Citizen Mobile Application

- Submit infrastructure complaints
- Upload photos
- Share GPS location or enter an address
- Track complaint status

### AI-Assisted Processing

- Complaint classification
- Description cleanup
- Duplicate detection
- Urgency estimation
- Department recommendation
- Complaint summarization

### Municipality Dashboard

- View submitted complaints
- Filter by category, urgency, and status
- Assign and update tickets
- Monitor complaint locations on a map

## Repository Structure

```text
BaladiGuard/
├── mobile/
├── backend/
├── admin/
├── docs/
├── scripts/
└── .github/
```

## Branching Strategy

The `main` branch contains the stable project code.

Create all work branches from `main` and name each branch after the assigned GitHub issue.

Example:

```text
4-prepare-initial-readme-and-repo-structure-notes
12-complaint-submission-flow
27-admin-dashboard
```

## Development Workflow

1. Create a branch from `main` using the issue name.
2. Implement the assigned task.
3. Open a Pull Request.
4. Request a review from a teammate.
5. Merge into `main` after approval.

## Code Quality Commands

GitHub Actions runs automated checks on every pull request and on pushes to `main`.
Run these same checks locally before opening a pull request.

### Admin Dashboard

```bash
cd admin
npm run lint
npm run format
npm run format:check
npm run typecheck
npm test
```

### Mobile

Install dependencies once:

```bash
cd mobile
npm ci
```

Then run:

```bash
cd mobile
npm run lint
npm run format:check
npm run typecheck
npm test
```

### Backend

Install dev dependencies once:

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
```

Then run:

```bash
python -m ruff check .
python -m ruff format --check .
PYTHONPATH=. python scripts/validate_mock_tickets.py
python -m pytest
```

### All (from repository root)

With Make installed:

```bash
make lint
make format
make format-check
make typecheck
make test
make quality
```

`make quality` runs lint, format check, and typecheck across the project.
`make test` runs the Expo app, staff dashboard, and backend pytest suites. Frontend tests use
local mocks and do not require a live backend, DynamoDB, AWS, or AI credentials. Backend unit
tests mock external AI provider calls and use in-memory storage (plus moto for DynamoDB cases).

To match CI fully, also run the backend data validation step before pytest:

```bash
cd backend
PYTHONPATH=. python scripts/validate_mock_tickets.py
python -m pytest
```

Backend unit tests cover ticket ID generation, status workflow validation, AI classification
fallbacks, and description-cleaning fallback/preservation rules (with external AI provider calls
mocked).

### AI intake regression tests

The lightweight multilingual regression subset is deterministic and never calls Bedrock. It loads
the issue #21 dataset, checks every supported category (including
`PENDING_CLASSIFICATION`), covers Arabic, French, Lebanese Arabizi, and mixed-language reports,
and verifies that cleaned output preserves required details without introducing prohibited facts.
Cleaned descriptions are English-normalized by default (inputs stay multilingual; place names are
preserved as written).

Run the same subset used by CI:

```bash
cd backend
python -m pytest -m ai_intake_regression -q
```

Or, with Make:

```bash
make test-ai-regression
```

Each dataset case is a separate pytest node named with its stable case ID. Failure output includes
the original input, expected result, and actual result.

## Documentation

Project documentation is located in the `docs/` directory.

- Architecture
- API Specification
- Database Design
- [Complaint Categories](docs/complaint-categories.md)
- [Urgency Scoring Rules](docs/urgency-scoring.md)
- [Notification Message Templates](docs/notification-templates.md)
- [Local Database Setup](docs/local-database-setup.md)
- [Cloud Setup (AWS DynamoDB + S3)](docs/cloud-setup.md)
- Design Decisions
- Sprint Notes

## Getting Started

### Backend (cloud AWS by default)

1. Install backend dependencies:

```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

2. Sync local env files from AWS Secrets Manager (preferred — issue #124):

```bash
# Windows
backend\.venv\Scripts\python.exe scripts\sync_env.py

# macOS / Linux
backend/.venv/bin/python scripts/sync_env.py
```

This writes `.env`, `backend/.env`, `mobile/.env`, and `admin/.env` from the shared
secret `baladiguard/local-dev/env`. See [docs/env-sync.md](docs/env-sync.md).

Owners can update that secret **without the AWS Console** after editing local files:

```bash
# Windows
backend\.venv\Scripts\python.exe scripts\sync_env.py --push

# macOS / Linux
backend/.venv/bin/python scripts/sync_env.py --push
```

Manual fallback (never commit secrets):

```bash
copy backend\.env.example backend\.env
copy .env.example .env
```

`backend/.env.example` defaults to **cloud DynamoDB** (`DATABASE_BACKEND=dynamodb` and
empty `DYNAMODB_ENDPOINT_URL`). Put `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and
`AWS_S3_BUCKET` in `.env` / `backend/.env`.

3. Create cloud tables and seed reference data:

```bash
cd backend
python scripts/db/migrate.py
python scripts/db/seed.py
```

4. Run the API:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

5. Check backend health (local or deployed):

```bash
curl http://localhost:8000/health
```

Expected shape:

```json
{
  "status": "ok",
  "service": "baladiguard-api",
  "env": "local",
  "database": {
    "backend": "memory",
    "status": "ok"
  }
}
```

After deployment, use the same path on the public API host, for example
`https://<your-api-host>/health`. A `200` response means the app process is up.
If `status` is `degraded` or `database.status` is `error`, the API is running but
database connectivity needs attention.

Important request errors, AI processing failures, and notification emit failures are
written to the backend logs (`LOG_LEVEL`, default `INFO`) and do not roll back a
successful ticket create/update.

6. Verify the real cloud path (S3 + DynamoDB + API):

```bash
cd backend
python scripts/verify_cloud_report_flow.py
```

Optional live Bedrock checks (manual / scheduled; not part of PR CI):

```bash
cd backend
python scripts/verify_classification.py
python scripts/verify_cleaning.py
python scripts/eval_classification.py
python scripts/eval_ai_intake.py

# Opt-in pytest: real Bedrock with the in-memory store
RUN_LIVE_AI=1 pytest tests/test_ai_submission_integration.py -k live_submission_processes_real_ai

# Opt-in pytest: real Bedrock + real cloud DynamoDB persistence + read API
RUN_LIVE_AI=1 RUN_LIVE_DYNAMODB=1 pytest tests/test_ai_submission_integration.py -k live_submission_persists_real_ai_to_cloud_dynamodb
```

`eval_classification.py` is the labeled accuracy suite (text + external S3/URL images).
`eval_ai_intake.py` runs the full multilingual classification and cleaning dataset, exits nonzero
on category mismatches or cleaning fallbacks, and can write scheduled-run artifacts with
`--json-output artifacts/ai-intake-eval.json`. These live commands are manual/scheduled only and
are not part of pull-request CI.

`pytest` still uses in-memory storage by default (plus moto for some DynamoDB unit tests),
so CI does not need AWS credentials. The cloud DynamoDB live test requires provisioned
tables and `DATABASE_BACKEND=dynamodb` credentials (no `DYNAMODB_ENDPOINT_URL`).

For Docker DynamoDB Local instead of cloud, see
[docs/local-database-setup.md](docs/local-database-setup.md).
For full cloud setup details, see [docs/cloud-setup.md](docs/cloud-setup.md).

### Mobile

Install dependencies once:

```bash
cd mobile
npm ci
```

Run quality checks:

```bash
cd mobile
npm run lint
npm run format:check
npm run typecheck
npm test
```

Start the Expo app:

```bash
cd mobile
npm start
```

By default the mobile app talks to the real backend API. Mock mode is opt-in only
(`EXPO_PUBLIC_ENABLE_MOCK_API=true`).

For real end-to-end submission:

1. Copy `mobile/.env.example` to `mobile/.env` (mock stays off by default).
2. Start the backend API on port `8000` (see Backend section above).
3. Configure `backend/.env` with database settings and AWS S3 credentials for photo uploads.
4. Set `EXPO_PUBLIC_API_BASE_URL` to your API URL (`http://localhost:8000/v1` for emulators; use your machine IP for a physical device).

See `mobile/.env.example` for the full checklist.

### Admin Dashboard

```bash
cd admin
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). By default the dashboard talks to the
local backend API (`VITE_USE_MOCK_DATA=false`). Set `VITE_USE_MOCK_DATA=true` only when you
intentionally want mock fixtures.

## Contributors

- Mahmoud Chaer
- Rawan El Hakim
- Hadi Elham
- Mohamad Hamdan
- Zakaria Labban

---

Developed as part of the Amazon Mentorship Program 5.0.
