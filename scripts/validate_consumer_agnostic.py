from __future__ import annotations

import re
import sys
from pathlib import Path

OWNER = "JonCunninghamDev"
PLATFORM_REPOSITORY = "engineering-platform"
REPOSITORY_REFERENCE = re.compile(rf"\b{re.escape(OWNER)}/([A-Za-z0-9_.-]+)\b")

SCANNED_SURFACES = (
    Path("README.md"),
    Path("AGENTS.md"),
    Path("docs"),
    Path("agent"),
    Path("profiles"),
    Path("schemas"),
    Path("standards"),
    Path("templates"),
    Path("actions"),
    Path("scripts"),
    Path(".github/workflows"),
)

TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".sh", ".txt"}


def _iter_scanned_files(root: Path):
    for surface in SCANNED_SURFACES:
        target = root / surface
        if not target.exists():
            continue
        if target.is_file():
            yield target
            continue
        for path in sorted(target.rglob("*")):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for path in _iter_scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in REPOSITORY_REFERENCE.finditer(line):
                repository = match.group(1)
                if repository == PLATFORM_REPOSITORY:
                    continue
                relative = path.relative_to(root)
                errors.append(
                    f"consumer-specific repository reference in {relative}:{line_number}: "
                    f"{OWNER}/{repository}"
                )
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate(root)
    if errors:
        print("Consumer-agnostic platform validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Consumer-agnostic platform validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
