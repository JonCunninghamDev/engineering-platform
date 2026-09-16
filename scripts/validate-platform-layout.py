#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
AGENTS_MAX_LINES = 80
AGENTS_REQUIRED_HEADINGS = (
    "Repository authority",
    "Startup reads",
    "Branch invariants",
    "Authoritative pointers",
    "Completion route",
    "Keep this entrypoint small",
)
AGENTS_FORBIDDEN_DETAIL_HEADINGS = (
    "Instruction precedence",
    "Startup contract",
    "Branch and pull-request contract",
    "Implementation authority",
    "Human acceptance testing",
    "Compatibility and versioning",
    "Validation",
    "Troubleshooting",
    "Definition of done",
)
AGENTS_REQUIRED_POINTERS = (
    "`README.md` from `main` first",
    "`engineering-policy.json`",
    "`agent/operating-contract-v1.md`",
    "`docs/task-management.md`",
    "`standards/fast-feedback-v1.json`",
    "`docs/compatibility.md`",
    "`docs/adoption.md`",
)

REQUIRED_FILES = {
    "README.md",
    "AGENTS.md",
    "VERSION",
    "CHANGELOG.md",
    "engineering-policy.json",
    "docs/task-management.md",
    "docs/adoption.md",
    "agent/README.md",
    "agent/adapters/README.md",
    "standards/README.md",
    "standards/fast-feedback-v1.json",
    "schemas/README.md",
    "profiles/README.md",
    "templates/README.md",
    "actions/README.md",
    "tests/README.md",
    "scripts/validate-pr-policy.py",
    "scripts/validate-protected-paths.py",
    "scripts/validate_agent_command.py",
    "scripts/run_fast_feedback.py",
    "scripts/install-hooks.sh",
    ".githooks/pre-commit",
    ".github/pull_request_template.md",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
}

REQUIRED_DIRECTORIES = {
    "agent",
    "agent/adapters",
    "standards",
    "schemas",
    "profiles",
    "templates",
    "actions",
    "docs",
    "docs/releases",
    "tests",
    "scripts",
    ".githooks",
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


def validate_agents_entrypoint(root: Path, errors: list[str]) -> None:
    agents = root / "AGENTS.md"
    if not agents.is_file():
        return
    text = agents.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > AGENTS_MAX_LINES:
        errors.append(
            f"AGENTS.md must remain a concise pointer surface: {len(lines)} lines exceeds {AGENTS_MAX_LINES}"
        )
    for heading in AGENTS_REQUIRED_HEADINGS:
        if f"## {heading}" not in text:
            errors.append(f"AGENTS.md is missing pointer heading: {heading}")
    for heading in AGENTS_FORBIDDEN_DETAIL_HEADINGS:
        if f"## {heading}" in text:
            errors.append(
                f"AGENTS.md duplicates detailed operating guidance instead of pointing to its authority: {heading}"
            )
    for pointer in AGENTS_REQUIRED_POINTERS:
        if pointer.lower() not in text.lower():
            errors.append(f"AGENTS.md is missing authoritative pointer: {pointer}")


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

    validate_agents_entrypoint(root, errors)

    if version:
        changelog = root / "CHANGELOG.md"
        if changelog.is_file() and f"## [{version}]" not in changelog.read_text(encoding="utf-8"):
            errors.append(f"CHANGELOG.md is missing version entry: {version}")

        release_notes = root / "docs" / "releases" / f"v{version}.md"
        if not release_notes.is_file():
            errors.append(f"missing release notes: docs/releases/v{version}.md")
        elif f"# Engineering Platform v{version}" not in release_notes.read_text(encoding="utf-8"):
            errors.append(f"release notes heading does not match VERSION: v{version}")

    ci_workflow = root / ".github" / "workflows" / "ci.yml"
    require_phrases(
        root,
        ci_workflow,
        (
            "fetch-depth: 0",
            "validate-pr-policy.py",
            "validate-protected-paths.py",
            "run_fast_feedback.py --stage pre_commit",
            "run_fast_feedback.py --stage completion_gate",
        ),
        errors,
    )

    pre_commit = root / ".githooks" / "pre-commit"
    require_phrases(
        root,
        pre_commit,
        ("run_fast_feedback.py", "--stage pre_commit"),
        errors,
    )

    install_hooks = root / "scripts" / "install-hooks.sh"
    require_phrases(
        root,
        install_hooks,
        ("core.hooksPath .githooks",),
        errors,
    )

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
