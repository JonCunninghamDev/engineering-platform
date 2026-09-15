#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

RESERVED_PREFIXES = ("Release:", "Sync:")


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
    """Validate the two-long-lived-branch delivery model using PR metadata.

    All implementation branches target the integration branch. The integration
    branch promotes to the release/default branch, and released history may then
    synchronize back to integration. There is no direct implementation route to
    the release/default branch.
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
        errors.append(
            "direct-main route rejected: all implementation work must branch from the integration "
            "branch, return to the integration branch, and reach production only through an "
            "integration-to-main release promotion"
        )
    elif base == integration_branch:
        route = "feature"
        if head in {default_branch, integration_branch}:
            errors.append("ordinary integration work must come from a dedicated temporary branch")
        for prefix in RESERVED_PREFIXES:
            if _starts_with(title, prefix):
                errors.append(
                    f"ordinary integration PR cannot use reserved '{prefix}' title prefix; "
                    "route metadata is ambiguous"
                )
                break
    else:
        errors.append(
            f"unsupported base branch '{base}'; expected '{integration_branch}' for implementation "
            f"work or '{default_branch}' only for integration release promotion"
        )

    if route == "promotion" and _starts_with(title, "Sync:"):
        errors.append("promotion PR uses a reserved title for a different route")
    if route == "synchronization" and _starts_with(title, "Release:"):
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
