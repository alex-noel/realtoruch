"""Shared local-only paths and keys; sample and live catalogs remain separate."""

import json
import os
import secrets
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def local_environment(*, live=False, journey=False):
    if live and journey:
        raise ValueError(
            "Choose either the live catalog or the synthetic journey catalog"
        )
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    # Optional ignored mail settings; explicit shell variables take precedence.
    environment = {
        key: value
        for key, value in dotenv_values(local / "mail.env").items()
        if value is not None
    }
    environment.update(os.environ)
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
    keys = json.loads(secret_file.read_text())
    if not keys.get("VAPID_PRIVATE_KEY"):
        import base64

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        private = ec.generate_private_key(ec.SECP256R1())
        keys["VAPID_PRIVATE_KEY"] = (
            base64.urlsafe_b64encode(
                private.private_bytes(
                    serialization.Encoding.DER,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            .decode()
            .rstrip("=")
        )
        keys["VAPID_PUBLIC_KEY"] = (
            base64.urlsafe_b64encode(
                private.public_key().public_bytes(
                    serialization.Encoding.X962,
                    serialization.PublicFormat.UncompressedPoint,
                )
            )
            .decode()
            .rstrip("=")
        )
        # Development-only contact claim. Production supplies its own real contact URI.
        keys["VAPID_SUBJECT"] = "mailto:local-development@example.invalid"
        secret_file.write_text(json.dumps(keys))
        secret_file.chmod(0o600)
    return {
        **environment,
        **keys,
        "DEMO_MODE": "false" if live else "true",
        "EXPO_NO_TELEMETRY": "1",
        "EXPO_OFFLINE": "1",
        "EMAIL_DELIVERY_MODE": environment.get("EMAIL_DELIVERY_MODE", "file"),
        "EMAIL_PREVIEW_DIRECTORY": str(local / "mail"),
        "PUBLIC_WEB_URL": environment.get("PUBLIC_WEB_URL", "http://localhost:8081"),
        "CONNECTORS_CONFIG": str(
            ROOT / "config" / ("sources.live.json" if live else "sources.json")
        ),
        "DATABASE_URL": f"sqlite:///{local / ('journey-rentals.db' if journey else 'live-rentals.db' if live else 'rentals.db')}",
        "AUTH_DATABASE_URL": f"sqlite:///{local}/auth.db",
    }
