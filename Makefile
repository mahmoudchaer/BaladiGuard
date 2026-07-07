.PHONY: lint format format-check typecheck quality db-up db-down db-migrate db-seed db-reset

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

quality: lint format-check typecheck

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
