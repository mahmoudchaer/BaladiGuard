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
make quality
```

`make quality` runs lint, format check, and typecheck across the project.

To match CI fully, also run the backend data validation and test suite:

```bash
cd backend
PYTHONPATH=. python scripts/validate_mock_tickets.py
python -m pytest
```

## Documentation

Project documentation is located in the `docs/` directory.

- Architecture
- API Specification
- Database Design
- [Complaint Categories](docs/complaint-categories.md)
- [Local Database Setup](docs/local-database-setup.md)
- Design Decisions
- Sprint Notes

## Getting Started

### Backend (local API + DynamoDB)

1. Install backend dependencies:

```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

2. Start DynamoDB Local and prepare tables:

```bash
make db-up
make db-migrate
make db-seed
```

3. Copy `backend/.env.example` to `backend/.env` and set `DATABASE_BACKEND=dynamodb`.

4. Run the API:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

`pytest` uses in-memory storage by default (and moto for one DynamoDB persistence test), so CI does not require Docker. For a real local persistence run, keep DynamoDB Local running with `DATABASE_BACKEND=dynamodb` after migrate/seed.

See [docs/local-database-setup.md](docs/local-database-setup.md) for full database setup, env vars, troubleshooting, and the tests-vs-real-run distinction.

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

By default, `EXPO_PUBLIC_ENABLE_MOCK_API=true` in `mobile/.env`, so report submissions return a sample ticket without calling the backend.

For real end-to-end submission:

1. Copy `mobile/.env.example` to `mobile/.env` and set `EXPO_PUBLIC_ENABLE_MOCK_API=false`.
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

Open [http://localhost:5173](http://localhost:5173). The dashboard loads shared mock tickets from `mock_tickets.json` by default.

## Contributors

- Mahmoud Chaer
- Rawan El Hakim
- Hadi Elham
- Mohamad Hamdan
- Zakaria Labban

---

Developed as part of the Amazon Mentorship Program 5.0.
