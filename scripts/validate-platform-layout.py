#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

REQUIRED_FILES = {
    "README.md",
    "AGENTS.md",
    "VERSION",
    "CHANGELOG.md",
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
    ".github/workflows/release.yml",
}

REQUIRED_DIRECTORIES = {
    "agent",
    "standards",
    "schemas",
    "profiles",
    "templates",
    "actions",
    "docs",
    "docs/releases",
    "tests",
    "scripts",
    ".github/workflows",
}


def require_phrases(
    root: Path,
    path: Path,
    phrases: tuple[str, ...],
    errors: list[str],
) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    for phrase in phrases:
        if phrase.lower() not in text.lower():
            errors.append(f"{path.relative_to(root)} does not describe required concept: {phrase}")


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []

    for relative in sorted(REQUIRED_DIRECTORIES):
        path = root / relative
        if not path.is_dir():
            errors.append(f"missing required directory: {relative}")

    for relative in sorted(REQUIRED_FILES):
        path = root / relative
        if not path.is_file():
            errors.append(f"missing required file: {relative}")
        elif not path.read_text(encoding="utf-8").strip():
            errors.append(f"required file is empty: {relative}")

    version_path = root / "VERSION"
    version = ""
    if version_path.is_file():
        version = version_path.read_text(encoding="utf-8").strip()
        if not SEMVER.fullmatch(version):
            errors.append(f"VERSION is not semantic versioning: {version!r}")

    expected_tag = f"v{version}" if version else ""

    require_phrases(
        root,
        root / "README.md",
        (
            "authoring source of truth",
            "Agent startup and release verification",
            "latest non-draft, non-prerelease GitHub release",
            "main",
            "develop",
            "pin",
            expected_tag,
        ),
        errors,
    )

    agents = root / "AGENTS.md"
    if agents.is_file():
        text = agents.read_text(encoding="utf-8")
        for heading in (
            "Repository authority",
            "Instruction precedence",
            "Startup contract",
            "Branch and pull-request contract",
            "Implementation authority",
            "Human acceptance testing",
            "Compatibility and versioning",
            "Troubleshooting",
            "Definition of done",
        ):
            if f"## {heading}" not in text:
                errors.append(f"AGENTS.md is missing heading: {heading}")
        for phrase in ("`README.md` from `main` first", "latest non-draft, non-prerelease"):
            if phrase.lower() not in text.lower():
                errors.append(f"AGENTS.md does not describe required release concept: {phrase}")

    if version:
        changelog = root / "CHANGELOG.md"
        if changelog.is_file() and f"## [{version}]" not in changelog.read_text(encoding="utf-8"):
            errors.append(f"CHANGELOG.md is missing version entry: {version}")

        release_notes = root / "docs" / "releases" / f"v{version}.md"
        if not release_notes.is_file():
            errors.append(f"missing release notes: docs/releases/v{version}.md")
        elif f"# Engineering Platform v{version}" not in release_notes.read_text(encoding="utf-8"):
            errors.append(f"release notes heading does not match VERSION: v{version}")

    release_workflow = root / ".github" / "workflows" / "release.yml"
    require_phrases(
        root,
        release_workflow,
        ("workflow_run", "Platform CI", "contents: write", "gh release create"),
        errors,
    )

    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    print(f"engineering platform validation passed for v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
