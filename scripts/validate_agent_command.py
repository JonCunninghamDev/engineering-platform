#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shlex
import sys
from typing import Sequence

BYPASS_ENV_PREFIXES = ("HUSKY=0", "HUSKY_SKIP_HOOKS=1")


def _tokens(command: str | Sequence[str]) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return [str(part) for part in command]


def validate_command(command: str | Sequence[str]) -> dict[str, object]:
    tokens = _tokens(command)
    lowered = [token.lower() for token in tokens]
    errors: list[str] = []

    git_index = next((index for index, token in enumerate(lowered) if token == "git"), None)
    if git_index is not None:
        git_tokens = lowered[git_index + 1 :]
        if "commit" in git_tokens:
            commit_index = git_tokens.index("commit")
            commit_args = git_tokens[commit_index + 1 :]
            if "--no-verify" in commit_args or "-n" in commit_args:
                errors.append(
                    "git commit hook bypass is prohibited; run the required pre-commit validation instead"
                )
            if any(
                token.startswith("core.hookspath=")
                and token.split("=", 1)[1] in {"/dev/null", "nul", ""}
                for token in git_tokens[:commit_index]
            ):
                errors.append("disabling core.hooksPath for git commit is prohibited")
        if len(git_tokens) >= 2 and git_tokens[0] == "config" and "core.hookspath" in git_tokens:
            errors.append(
                "changing core.hooksPath through an agent command requires explicit policy-change work"
            )

    for token in tokens:
        upper = token.upper()
        if any(upper == prefix for prefix in BYPASS_ENV_PREFIXES):
            errors.append(f"validation bypass environment setting is prohibited: {token}")

    return {
        "schema_version": "agent-command-policy/v1",
        "status": "passed" if not errors else "failed",
        "command": tokens,
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an agent-proposed shell command")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.command:
        print("ERROR: command is required", file=sys.stderr)
        return 2
    evidence = validate_command(args.command)
    if args.json:
        print(json.dumps(evidence, indent=2, sort_keys=True))
    elif evidence["status"] == "passed":
        print("agent command policy passed")
    else:
        for error in evidence["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
