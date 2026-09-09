#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROUTE_SCRIPT = Path(__file__).with_name("validate-delivery-route.py")
SPEC = importlib.util.spec_from_file_location("validate_delivery_route_for_pr_policy", ROUTE_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
route_validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = route_validator
SPEC.loader.exec_module(route_validator)

TEST_REQUIRED_ROUTES = {"feature", "hotfix"}


@dataclass(frozen=True)
class PolicyResult:
    route: str | None
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors and self.route is not None


def _normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def validate_pr_policy(
    *,
    base: str,
    head: str,
    title: str,
    changed_files: list[str] | tuple[str, ...],
    default_branch: str = "main",
    integration_branch: str = "develop",
    test_roots: tuple[str, ...] = ("tests",),
) -> PolicyResult:
    route_result = route_validator.validate_route(
        base=base,
        head=head,
        title=title,
        default_branch=default_branch,
        integration_branch=integration_branch,
    )
    if route_result.errors:
        return PolicyResult(route_result.route, tuple(route_result.errors))

    route = route_result.route
    files = tuple(path for path in (_normalize_path(p) for p in changed_files) if path)
    roots = tuple(_normalize_path(root).strip("/") for root in test_roots if _normalize_path(root).strip("/"))

    errors: list[str] = []
    if route in TEST_REQUIRED_ROUTES:
        has_test_change = any(
            path == root or path.startswith(f"{root}/")
            for path in files
            for root in roots
        )
        if not has_test_change:
            roots_text = ", ".join(f"{root}/" for root in roots) or "<none configured>"
            errors.append(
                f"{route} PR must include new or updated automated tests under: {roots_text}"
            )

    return PolicyResult(route, tuple(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Engineering Platform pull-request policy")
    parser.add_argument("--base", default=os.environ.get("GITHUB_BASE_REF", ""))
    parser.add_argument("--head", default=os.environ.get("GITHUB_HEAD_REF", ""))
    parser.add_argument("--title", default=os.environ.get("PR_TITLE", ""))
    parser.add_argument("--default-branch", default=os.environ.get("DEFAULT_BRANCH", "main"))
    parser.add_argument("--integration-branch", default=os.environ.get("INTEGRATION_BRANCH", "develop"))
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--changed-files-file")
    parser.add_argument("--test-root", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    changed_files = list(args.changed_file)
    if args.changed_files_file:
        changed_files.extend(Path(args.changed_files_file).read_text(encoding="utf-8").splitlines())
    test_roots = tuple(args.test_root) if args.test_root else ("tests",)
    result = validate_pr_policy(
        base=args.base,
        head=args.head,
        title=args.title,
        changed_files=changed_files,
        default_branch=args.default_branch,
        integration_branch=args.integration_branch,
        test_roots=test_roots,
    )
    if result.errors:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"pull request policy valid: route={result.route}; changed_files={len(changed_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
