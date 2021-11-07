"""Fetch per-service configuration with Workload Identity, then exec the service."""

import json
import os
import sys


def main():
    resource = os.environ.get("GCP_CONFIG_SECRET")
    if resource:
        from google.cloud import secretmanager

        response = secretmanager.SecretManagerServiceClient().access_secret_version(name=resource)
        for key, value in json.loads(response.payload.data).items():
            os.environ[key] = str(value)
    command = sys.argv[1:]
    if not command:
        raise SystemExit("Supply a service command")
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
