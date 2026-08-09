.PHONY: lint format format-check typecheck test test-ai-regression eval-ai-intake quality ai-worker ai-worker-once ai-worker-drain db-up db-down db-migrate db-seed db-reset

lint:
	cd mobile && npm run lint
	cd admin && npm run lint
	cd backend && python -m ruff check .

format:
	cd mobile && npm run format
	cd admin && npm run format
	cd backend && python -m ruff format .

format-check:
	cd mobile && npm run format:check
	cd admin && npm run format:check
	cd backend && python -m ruff format --check .

typecheck:
	cd mobile && npm run typecheck
	cd admin && npm run typecheck

test:
	cd mobile && npm test
	cd admin && npm test
	cd backend && python -m pytest

test-ai-regression:
	cd backend && python -m pytest -m ai_intake_regression -q

eval-ai-intake:
	cd backend && python scripts/eval_ai_intake.py

quality: lint format-check typecheck

ai-worker:
	cd backend && python -m app.workers.ai_worker

ai-worker-once:
	cd backend && python -m app.workers.ai_worker --once

ai-worker-drain:
	cd backend && python -m app.workers.ai_worker --drain

db-up:
	docker compose up -d dynamodb-local

db-down:
	docker compose down

db-migrate:
	cd backend && python scripts/db/migrate.py

db-seed:
	cd backend && python scripts/db/seed.py

db-reset:
	cd backend && python scripts/db/migrate.py --reset
	cd backend && python scripts/db/seed.py
