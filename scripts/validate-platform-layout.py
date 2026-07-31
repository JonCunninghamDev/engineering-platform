#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "README.md",
    "AGENTS.md",
    "docs/task-management.md",
    "docs/adoption.md",
    "agent/README.md",
    "standards/README.md",
    "schemas/README.md",
    "profiles/README.md",
    "templates/README.md",
    "actions/README.md",
    "tests/README.md",
    ".github/pull_request_template.md",
    ".github/workflows/ci.yml",
}

REQUIRED_DIRECTORIES = {
    "agent",
    "standards",
    "schemas",
    "profiles",
    "templates",
    "actions",
    "docs",
    "tests",
    "scripts",
    ".github/workflows",
}


def main() -> int:
    errors: list[str] = []

    for relative in sorted(REQUIRED_DIRECTORIES):
        path = ROOT / relative
        if not path.is_dir():
            errors.append(f"missing required directory: {relative}")

    for relative in sorted(REQUIRED_FILES):
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing required file: {relative}")
        elif not path.read_text(encoding="utf-8").strip():
            errors.append(f"required file is empty: {relative}")

    readme = ROOT / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        for phrase in ("authoring source of truth", "main", "develop", "pin"):
            if phrase.lower() not in text.lower():
                errors.append(f"README.md does not describe required concept: {phrase}")

    agents = ROOT / "AGENTS.md"
    if agents.is_file():
        text = agents.read_text(encoding="utf-8")
        for heading in (
            "Repository authority",
            "Startup contract",
            "Branch and pull-request contract",
            "Implementation authority",
            "Compatibility and versioning",
            "Troubleshooting",
            "Definition of done",
        ):
            if f"## {heading}" not in text:
                errors.append(f"AGENTS.md is missing heading: {heading}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("engineering platform layout validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
