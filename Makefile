.PHONY: lint format format-check typecheck quality

lint:
	cd mobile && npm run lint
	cd backend && python -m ruff check .

format:
	cd mobile && npm run format
	cd backend && python -m ruff format .

format-check:
	cd mobile && npm run format:check
	cd backend && python -m ruff format --check .

typecheck:
	cd mobile && npm run typecheck

quality: lint format-check typecheck
