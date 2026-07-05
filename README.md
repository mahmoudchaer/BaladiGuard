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

Run these commands before opening a pull request.

### Mobile

```bash
cd mobile
npm run lint
npm run format
npm run format:check
npm run typecheck
```

### Backend

Install dev dependencies once:

```bash
cd backend
pip install -r requirements-dev.txt
```

Then run:

```bash
python -m ruff check .
python -m ruff format .
python -m ruff format --check .
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

## Documentation

Project documentation is located in the `docs/` directory.

- Architecture
- API Specification
- Database Design
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

See [docs/local-database-setup.md](docs/local-database-setup.md) for full database setup, env vars, and troubleshooting.

### Mobile

Coming soon.

### Admin Dashboard

Coming soon.

## Contributors

- Mahmoud Chaer
- Rawan El Hakim
- Hadi Elham
- Mohamad Hamdan
- Zakaria Labban

---

Developed as part of the Amazon Mentorship Program 5.0.
