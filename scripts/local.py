"""Shared local-only paths and keys; sample and live catalogs remain separate."""

import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def local_environment(*, live=False):
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    secret_file = local / "development-secrets.json"
    if not secret_file.exists():
        with secret_file.open("x") as handle:
            secret_file.chmod(0o600)
            json.dump(
                {
                    name: secrets.token_urlsafe(48)
                    for name in (
                        "JWT_SECRET",
                        "PHONE_HASH_KEY",
                        "INTERNAL_API_KEY",
                    )
                },
                handle,
            )
    return {
        **os.environ,
        **json.loads(secret_file.read_text()),
        "DEMO_MODE": "false" if live else "true",
        "EXPO_NO_TELEMETRY": "1",
        "EXPO_OFFLINE": "1",
        "CONNECTORS_CONFIG": str(
            ROOT / "config" / ("sources.live.json" if live else "sources.json")
        ),
        "DATABASE_URL": f"sqlite:///{local / ('live-rentals.db' if live else 'rentals.db')}",
        "AUTH_DATABASE_URL": f"sqlite:///{local}/auth.db",
    }
