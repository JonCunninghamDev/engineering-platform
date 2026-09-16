#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Any

AUTHORIZATION_MARKER = "policy change authorization: approved"
ISSUE_BRANCH = re.compile(r"^(?:agent|feature|fix)/issue-([0-9]+)(?:-|$)")


class ProtectedPathError(ValueError):
    """Raised when protected-path validation inputs are invalid."""


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProtectedPathError(f"policy not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProtectedPathError(f"invalid policy JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ProtectedPathError("policy must be a JSON object")
    patterns = value.get("protected_paths")
    if not isinstance(patterns, list) or not all(isinstance(item, str) and item for item in patterns):
        raise ProtectedPathError("policy protected_paths must be a string array")
    return value


def _normalize(path: str) -> str:
    value = path.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def protected_matches(changed_files: list[str] | tuple[str, ...], patterns: list[str]) -> list[str]:
    matches: list[str] = []
    for raw in changed_files:
        path = _normalize(raw)
        if not path:
            continue
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns):
            matches.append(path)
    return sorted(set(matches))


def validate(
    *,
    policy: dict[str, Any],
    changed_files: list[str] | tuple[str, ...],
    head: str,
    issue_body: str,
) -> dict[str, Any]:
    patterns = list(policy["protected_paths"])
    protected = protected_matches(changed_files, patterns)
    branch_match = ISSUE_BRANCH.match(head)
    issue_number = int(branch_match.group(1)) if branch_match else None
    authorized = bool(
        protected
        and issue_number is not None
        and AUTHORIZATION_MARKER in issue_body.lower()
    )

    errors: list[str] = []
    if protected and issue_number is None:
        errors.append(
            "protected paths changed but feature branch does not identify an issue as "
            "agent/issue-N-..., feature/issue-N-..., or fix/issue-N-..."
        )
    elif protected and not authorized:
        errors.append(
            f"issue #{issue_number} does not explicitly authorize protected-policy changes; "
            f"add a '## Policy change authorization' section containing "
            f"'{AUTHORIZATION_MARKER}' only when the issue scope genuinely requires it"
        )

    return {
        "schema_version": "protected-path-evidence/v1",
        "status": "passed" if not errors else "failed",
        "head": head,
        "issue_number": issue_number,
        "authorization_marker_present": AUTHORIZATION_MARKER in issue_body.lower(),
        "protected_files": protected,
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate protected Engineering Platform paths")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--changed-files-file", type=Path)
    parser.add_argument("--issue-body-file", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    changed_files = list(args.changed_file)
    if args.changed_files_file:
        changed_files.extend(args.changed_files_file.read_text(encoding="utf-8").splitlines())
    issue_body = ""
    if args.issue_body_file and args.issue_body_file.is_file():
        issue_body = args.issue_body_file.read_text(encoding="utf-8")

    try:
        policy = _load_policy(args.policy)
        evidence = validate(
            policy=policy,
            changed_files=changed_files,
            head=args.head,
            issue_body=issue_body,
        )
    except (ProtectedPathError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(evidence, indent=2, sort_keys=True))
    elif evidence["status"] == "passed":
        if evidence["protected_files"]:
            print(
                f"protected-path validation passed for issue #{evidence['issue_number']}: "
                + ", ".join(evidence["protected_files"])
            )
        else:
            print("protected-path validation passed: no protected files changed")
    else:
        for error in evidence["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        if evidence["protected_files"]:
            print(
                "Protected files: " + ", ".join(evidence["protected_files"]),
                file=sys.stderr,
            )
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
