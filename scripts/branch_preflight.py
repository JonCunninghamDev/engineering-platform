#!/usr/bin/env python3
"""Deterministic branch/PR preflight over a fresh, caller-verified GitHub snapshot.

This does not fetch GitHub state or authorize an actual GitHub write. An adapter
must obtain an authoritative snapshot immediately before each create/merge action,
verify its completeness, and honor the deny-by-default result.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SHA = re.compile(r"^[0-9a-f]{40}$")
TEMPORARY = ("agent/", "feature/", "fix/", "release/")


def decision(code: str, reason: str, *, branch: str = "") -> dict[str, str]:
    return {"decision": code, "reason": reason, "branch": branch}


def evaluate(snapshot: Any) -> dict[str, str]:
    deny = lambda message: decision("BLOCK", message)
    if not isinstance(snapshot, dict) or snapshot.get("verified") is not True:
        return deny("Fresh, complete GitHub snapshot has not been verified")
    if not isinstance(snapshot.get("observed_at"), str) or not snapshot["observed_at"].strip():
        return deny("Missing live snapshot observation timestamp")
    try:
        observed = datetime.fromisoformat(snapshot["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return deny("Snapshot observation timestamp must include a timezone")
    except ValueError:
        return deny("Invalid snapshot observation timestamp")
    refs = snapshot.get("refs")
    prs = snapshot.get("pull_requests")
    request = snapshot.get("request")
    if not isinstance(refs, dict) or not isinstance(prs, list) or not isinstance(request, dict):
        return deny("Explicit remote refs, all open/draft PRs, and request are required")
    if not all(isinstance(k, str) and isinstance(v, str) and SHA.fullmatch(v) for k, v in refs.items()):
        return deny("Remote refs must contain actual branch names and full commit SHAs")
    if not ("main" in refs and "develop" in refs):
        return deny("Both main and develop remote heads must be present")
    operation = request.get("operation")
    issue = request.get("issue")
    branch = request.get("branch")
    if operation not in ("create", "resume", "merge") or type(issue) is not int or issue <= 0:
        return deny("Valid operation and linked issue number are required")
    if not isinstance(branch, str) or not branch.startswith(TEMPORARY) or branch in ("main", "develop"):
        return deny("An issue-linked temporary branch is required")

    for pr in prs:
        if not isinstance(pr, dict) or type(pr.get("number")) is not int:
            return deny("Unidentified PR in snapshot")
        if pr.get("state") != "open" or not isinstance(pr.get("draft"), bool):
            return deny("PR inventory must contain open and draft PRs with known state")
        if not isinstance(pr.get("head"), str) or type(pr.get("issue")) is not int:
            return deny("PR branch and issue linkage must be resolved")
    same_issue = [pr for pr in prs if pr["issue"] == issue]
    active = [name for name in refs if name.startswith(TEMPORARY)]
    other_prs = [pr for pr in prs if pr["issue"] != issue]

    if operation == "create":
        if same_issue:
            return deny("Resume existing PR #" + str(same_issue[0]["number"]) + " rather than creating a duplicate")
        if branch in refs:
            return deny("Resume existing remote branch rather than creating a duplicate")
        if any(pr.get("overlaps_requested") is not False for pr in other_prs):
            return deny("Conflicting or unassessed open/draft PR: reconcile dependencies first")
        if len(active) >= 2:
            return deny("Two temporary implementation branches already exist")
        if active:
            if request.get("independent_of_active_work") is not True:
                return deny("Second implementation must be independently scoped")
            if any(pr.get("waiting") is not True for pr in other_prs):
                return deny("Existing PR is not exclusively waiting for CI/review/acceptance")
            if any(name not in {pr["head"] for pr in prs} for name in active):
                return deny("Active branch without a linked PR must be reconciled")
        return decision("ALLOW_CREATE", "New independent issue branch permitted", branch=branch)

    if branch not in refs:
        return deny("Requested existing branch is absent from remote GitHub refs")
    if operation == "resume":
        if not same_issue and request.get("branch_issue_verified") is not True:
            return deny("Existing branch has no PR: verify its issue ownership before resuming")
        if same_issue and any(pr["head"] != branch for pr in same_issue):
            return deny("Issue has a different existing PR branch; reconcile before writing")
        return decision("ALLOW_RESUME", "Continue the existing issue branch/PR", branch=branch)

    # Re-read GitHub immediately before merge and provide exact-head CI/review evidence.
    matching = [pr for pr in same_issue if pr["head"] == branch and pr.get("base") == "develop"]
    if len(matching) != 1:
        return deny("Exactly one open PR for this issue/branch targeting develop is required")
    pr = matching[0]
    if pr["draft"]:
        return deny("Draft PR is not mergeable")
    head_sha = refs[branch]
    if pr.get("head_sha") != head_sha or request.get("checked_head_sha") != head_sha:
        return deny("Live branch head, PR head, and checked CI commit must match")
    if pr.get("checks") != "success" or type(pr.get("unresolved_threads")) is not int or pr["unresolved_threads"] != 0:
        return deny("Exact-head CI must pass and review threads must be resolved")
    if pr.get("mergeable") is not True:
        return deny("GitHub must confirm PR is mergeable without conflicts")
    if request.get("merge_authorized_by_policy") is not True:
        return deny("Repository policy does not explicitly authorize this merge")
    if type(pr.get("human_gate")) is not bool:
        return deny("Human-gate classification must be explicit")
    if pr["human_gate"] and pr.get("human_accepted") is not True:
        return deny("Required human acceptance has not been recorded")
    if any(other.get("overlaps_requested") is not False for other in other_prs):
        return deny("Another open/draft PR overlaps or has unknown dependency")
    return decision("ALLOW_MERGE", "Exact-head checks, dependencies, and authority satisfied", branch=branch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate fresh branch/PR reconciliation evidence")
    parser.add_argument("snapshot", type=Path, help="JSON snapshot verified by the GitHub adapter")
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        result = evaluate(snapshot)
    except (OSError, ValueError) as exc:
        result = decision("BLOCK", "Invalid or unreadable snapshot: " + str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"].startswith("ALLOW_") else 1


if __name__ == "__main__":
    sys.exit(main())
