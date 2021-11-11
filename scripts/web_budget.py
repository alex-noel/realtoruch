#!/usr/bin/env python3
"""Check the uncompressed JavaScript entry referenced by an Expo web export."""

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

MAX_ENTRY_BYTES = 650_000
DEFAULT_EXPORT = Path(__file__).resolve().parents[1] / "apps/mobile/dist"


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []

    def handle_starttag(self, tag, attributes):
        if tag != "script":
            return
        src = dict(attributes).get("src")
        if not src:
            return
        url = urlsplit(src)
        path = unquote(url.path).lstrip("/")
        if not url.scheme and not url.netloc and path.startswith("_expo/static/js/web/") and path.endswith(".js"):
            self.entries.append(path)


def check_export(output_dir: Path) -> dict:
    root = output_dir.resolve()
    parser = Scripts()
    parser.feed((root / "index.html").read_text(encoding="utf-8"))
    parser.close()
    # Expo may emit shared chunks ahead of its application entry. Resolve
    # both from the HTML, but apply the main-bundle limit to the entry only.
    eager = {}
    entries = []
    for src in parser.entries:
        path = (root / src).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Expo script does not resolve to a file inside the export")
        eager[src] = path.stat().st_size
        if not path.name.startswith(("__expo-metro-runtime-", "__common-")):
            entries.append(src)
    if len(entries) != 1:
        raise ValueError(f"expected one Expo application entry in index.html; found {len(entries)}")
    entry = entries[0]
    size = eager[entry]
    return {
        "entry": entry,
        "uncompressed_bytes": size,
        "eager_scripts": eager,
        "eager_uncompressed_bytes": sum(eager.values()),
        "limit_bytes": MAX_ENTRY_BYTES,
        "pass": size <= MAX_ENTRY_BYTES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_EXPORT)
    args = parser.parse_args()
    try:
        result = check_export(args.output_dir)
    except (OSError, ValueError) as error:
        parser.exit(2, f"web budget: {error}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
