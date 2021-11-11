#!/usr/bin/env python3
"""Report native release prerequisites without creating builds or uploading anything."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from local import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero if any required item is missing",
    )
    args = parser.parse_args()
    node = shutil.which("node")
    version = (
        subprocess.check_output([node, "--version"], text=True).strip()
        if node
        else "missing"
    )
    sdk = Path(
        os.environ.get("ANDROID_SDK_ROOT")
        or os.environ.get("ANDROID_HOME")
        or str(Path.home() / "Library/Android/sdk")
    )
    xcode = (
        subprocess.run(["xcode-select", "-p"], text=True, capture_output=True)
        if shutil.which("xcode-select")
        else None
    )
    selected = xcode.stdout.strip() if xcode else ""
    public = ("EXPO_PUBLIC_API_URL", "EXPO_PUBLIC_AUTH_URL")
    numbers = (
        tuple(int(part) for part in version.lstrip("v").split(".")[:2])
        if node
        else (0, 0)
    )
    major, minor = numbers
    checks = {
        "supported_node": (major == 22 and minor >= 13)
        or (major == 24 and minor >= 3)
        or major >= 26,
        "xcode_selected": selected.endswith("Xcode.app/Contents/Developer"),
        "cocoapods_available": bool(shutil.which("pod")),
        "android_sdk_platform_tools": (sdk / "platform-tools/adb").is_file(),
        "android_maps_key_configured": bool(os.getenv("GOOGLE_MAPS_ANDROID_API_KEY")),
        "production_https_endpoints": all(
            urlsplit(os.getenv(name, "")).scheme == "https" for name in public
        ),
    }
    result = {
        "node": version,
        "checks": checks,
        "manual_release_checks": [
            "Physical Android and iOS testing",
            "Signing identities and provisioning",
            "Real email delivery",
            "Native notification permissions if push is enabled",
        ],
        "missing": [name for name, passed in checks.items() if not passed],
    }
    (ROOT / ".local").mkdir(exist_ok=True)
    (ROOT / ".local/mobile-check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(args.strict and bool(result["missing"]))


if __name__ == "__main__":
    raise SystemExit(main())
