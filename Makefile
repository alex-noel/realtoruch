.PHONY: install dev live collect test web-build compose-check
install:
	python3.12 -m venv .venv
	.venv/bin/pip install -r backend/requirements-dev.lock -e './backend[dev]'
	cd apps/mobile && npm ci
dev:
	.venv/bin/python scripts/dev.py
live:
	.venv/bin/python scripts/dev.py --live
collect:
	.venv/bin/python scripts/collect.py $(ARGS)
test:
	.venv/bin/pytest backend/tests
	cd apps/mobile && npm run typecheck
web-build:
	cd apps/mobile && EXPO_NO_TELEMETRY=1 EXPO_OFFLINE=1 npm run build:web
compose-check:
	docker compose config --quiet
