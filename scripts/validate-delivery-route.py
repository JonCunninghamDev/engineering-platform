#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

RESERVED_PREFIXES = ("Release:", "Sync:", "Hotfix:")


@dataclass(frozen=True)
class RouteResult:
    route: str | None
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors and self.route is not None


def _starts_with(title: str, prefix: str) -> bool:
    return title.strip().lower().startswith(prefix.lower())


def validate_route(
    *,
    base: str,
    head: str,
    title: str,
    default_branch: str = "main",
    integration_branch: str = "develop",
) -> RouteResult:
    """Validate a pull-request delivery route using only PR metadata.

    The validator is intentionally product-agnostic. Consumers can supply their
    own default and integration branch names while retaining the route semantics.
    """
    base = base.strip()
    head = head.strip()
    title = title.strip()
    default_branch = default_branch.strip()
    integration_branch = integration_branch.strip()
    errors: list[str] = []

    if not all((base, head, title, default_branch, integration_branch)):
        missing = [
            name
            for name, value in (
                ("base", base),
                ("head", head),
                ("title", title),
                ("default_branch", default_branch),
                ("integration_branch", integration_branch),
            )
            if not value
        ]
        return RouteResult(None, (f"missing required route metadata: {', '.join(missing)}",))

    if default_branch == integration_branch:
        return RouteResult(None, ("default and integration branches must be different",))

    if base == head:
        return RouteResult(None, (f"base and head are identical ({base}); route is ambiguous",))

    route: str | None = None

    if base == default_branch and head == integration_branch:
        route = "promotion"
        if not _starts_with(title, "Release:"):
            errors.append("promotion PR title must start with 'Release:'")
    elif base == integration_branch and head == default_branch:
        route = "synchronization"
        if not _starts_with(title, "Sync:"):
            errors.append("synchronization PR title must start with 'Sync:'")
    elif base == default_branch:
        if _starts_with(title, "Hotfix:"):
            route = "hotfix"
            if head in {default_branch, integration_branch}:
                errors.append("hotfix head must be a dedicated branch, not a shared branch")
        else:
            errors.append(
                "direct-main route rejected: ordinary work must target the integration branch; "
                "use 'Release:' for integration promotion or 'Hotfix:' for a dedicated hotfix branch"
            )
    elif base == integration_branch:
        route = "feature"
        if head in {default_branch, integration_branch}:
            errors.append("ordinary integration work must come from a dedicated task branch")
        for prefix in RESERVED_PREFIXES:
            if _starts_with(title, prefix):
                errors.append(
                    f"ordinary integration PR cannot use reserved '{prefix}' title prefix; "
                    "route metadata is ambiguous"
                )
                break
    else:
        errors.append(
            f"unsupported base branch '{base}'; expected '{integration_branch}' for ordinary work "
            f"or '{default_branch}' for release/hotfix work"
        )

    if route == "promotion" and (_starts_with(title, "Sync:") or _starts_with(title, "Hotfix:")):
        errors.append("promotion PR uses a reserved title for a different route")
    if route == "synchronization" and (_starts_with(title, "Release:") or _starts_with(title, "Hotfix:")):
        errors.append("synchronization PR uses a reserved title for a different route")

    return RouteResult(route if not errors else route, tuple(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a shared Engineering Platform delivery route")
    parser.add_argument("--base", default=os.environ.get("GITHUB_BASE_REF", ""))
    parser.add_argument("--head", default=os.environ.get("GITHUB_HEAD_REF", ""))
    parser.add_argument("--title", default=os.environ.get("PR_TITLE", ""))
    parser.add_argument("--default-branch", default=os.environ.get("DEFAULT_BRANCH", "main"))
    parser.add_argument("--integration-branch", default=os.environ.get("INTEGRATION_BRANCH", "develop"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_route(
        base=args.base,
        head=args.head,
        title=args.title,
        default_branch=args.default_branch,
        integration_branch=args.integration_branch,
    )
    if result.errors:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"delivery route valid: {result.route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
