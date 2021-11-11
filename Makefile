.PHONY: install dev live journey journey-event collect test web-build compose-check reliability backup-check postgres-backup-check load-check mobile-check
install:
	python3.12 -m venv .venv
	.venv/bin/pip install -r backend/requirements-dev.lock -e './backend[dev]'
	cd apps/mobile && npm ci
dev:
	.venv/bin/python scripts/dev.py
live:
	.venv/bin/python scripts/dev.py --live
journey:
	.venv/bin/python scripts/dev.py --journey
journey-event:
	.venv/bin/python scripts/journey.py $(ARGS)
collect:
	.venv/bin/python scripts/collect.py $(ARGS)
test:
	.venv/bin/pytest backend/tests
	cd apps/mobile && npm run typecheck
web-build:
	cd apps/mobile && EXPO_NO_TELEMETRY=1 EXPO_OFFLINE=1 npm run build:web
compose-check:
	docker compose config --quiet
reliability:
	.venv/bin/python scripts/reliability.py $(ARGS)
backup-check:
	.venv/bin/python scripts/backup_check.py $(ARGS)
postgres-backup-check:
	.venv/bin/python scripts/postgres_backup_check.py $(ARGS)
load-check:
	.venv/bin/python scripts/load_check.py $(ARGS)
mobile-check:
	.venv/bin/python scripts/mobile_check.py $(ARGS)

.PHONY: verify verify-services verify-web
verify:
	.venv/bin/python scripts/verify.py offline $(ARGS)
verify-services:
	.venv/bin/python scripts/verify.py services $(ARGS)
verify-web:
	.venv/bin/python scripts/verify.py web $(ARGS)
