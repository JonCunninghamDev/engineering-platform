#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import PurePosixPath, Path
from typing import Any


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def unified(path: str, before: str, after: str, operation: str) -> str:
    old = "/dev/null" if operation == "create" else f"a/{path}"
    return "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=old, tofile=f"b/{path}"))


def safe_path(path: str) -> bool:
    p = PurePosixPath(path)
    return bool(path) and not p.is_absolute() and ".." not in p.parts and "\\" not in path


def verify(task: dict[str, Any], change_set: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    def check(name: str, ok: bool, reason: str) -> None:
        checks.append({"name": name, "status": "passed" if ok else "failed", "reason": reason})

    task_id = str(task.get("assignment", {}).get("id", ""))
    plan_id = str(task.get("plan", {}).get("run_id", ""))
    capability = str(task.get("plan", {}).get("capability", ""))
    check("schema-linkage", task.get("schema_version") == "builder-task/v1" and change_set.get("schema_version") == "change-set/v1", "Builder task and change-set must use v1 contracts")
    check("task-linkage", change_set.get("task_id") == task_id, "change-set task_id must equal assignment id")
    check("plan-linkage", change_set.get("plan_run_id") == plan_id and change_set.get("assigned_capability") == capability, "plan run and capability must match Builder task")
    check("workflow-goal", change_set.get("workflow") == task.get("workflow") and change_set.get("goal") == task.get("goal"), "workflow and goal must match")
    check("builder-handoff", change_set.get("handoff", {}).get("target") == "verifier" and change_set.get("handoff", {}).get("allowed") is True and change_set.get("handoff", {}).get("execution_status") == "proposed_not_applied", "Builder must hand off an unapplied proposal")
    check("zero-write", change_set.get("summary", {}).get("actual_write_count") == 0, "Basic Builder evidence must record zero repository writes")

    task_changes = task.get("changes", []) if isinstance(task.get("changes"), list) else []
    cs_changes = change_set.get("changes", []) if isinstance(change_set.get("changes"), list) else []
    check("change-count", len(task_changes) == len(cs_changes) and change_set.get("summary", {}).get("change_count") == len(task_changes), "task, evidence, and summary change counts must agree")
    allowed = task.get("scope", {}).get("allowed_paths", [])
    protected = task.get("scope", {}).get("protected_paths", [])

    creates = updates = 0
    for i, proposed in enumerate(task_changes, 1):
        evidence = cs_changes[i - 1] if i <= len(cs_changes) else {}
        path = proposed.get("path", "")
        operation = proposed.get("operation", "")
        before = proposed.get("original_content", "") if operation == "update" else ""
        after = proposed.get("proposed_content", "")
        scope_ok = safe_path(path) and path in allowed and path not in protected
        check(f"change-{i}-scope", scope_ok, f"{path!r} must be safe, allowed, and unprotected")
        identity_ok = evidence.get("sequence") == i and evidence.get("path") == path and evidence.get("operation") == operation and evidence.get("action") == "WOULD_WRITE"
        check(f"change-{i}-identity", identity_ok, "sequence/path/operation/action must match the Builder task")
        expected_before = sha256(before) if operation == "update" else None
        expected_after = sha256(after)
        check(f"change-{i}-hashes", evidence.get("before_sha256") == expected_before and evidence.get("after_sha256") == expected_after, "hashes are independently recomputed from task content")
        check(f"change-{i}-diff", evidence.get("diff") == unified(path, before, after, operation), "unified diff is independently recomputed from task content")
        creates += operation == "create"
        updates += operation == "update"

    summary = change_set.get("summary", {})
    check("summary-counts", summary.get("proposed_write_count") == len(task_changes) and summary.get("create_count") == creates and summary.get("update_count") == updates, "summary operation counts must match the task")
    checks.append({"name": "candidate-code-execution", "status": "unavailable_basic_tier", "reason": "Basic Verifier inspects evidence only and does not execute candidate code"})
    failed = sum(c["status"] == "failed" for c in checks)
    passed = sum(c["status"] == "passed" for c in checks)
    unavailable = sum(c["status"] == "unavailable_basic_tier" for c in checks)
    status = "rejected" if failed else "verified"
    return {"schema_version": "verification-report/v1", "agent": {"role": "verifier", "version": "1.0.0", "service_tier": "basic"}, "task_id": task_id, "plan_run_id": plan_id, "status": status, "checks": checks, "summary": {"change_count": len(task_changes), "passed": passed, "failed": failed, "unavailable": unavailable}, "execution": {"repository_writes": 0, "candidate_code_executions": 0}, "handoff": {"target": "reviewer", "allowed": status == "verified", "artifact": "verification-report/v1"}}


def main() -> int:
    p = argparse.ArgumentParser(description="Independently verify Basic Builder evidence")
    p.add_argument("--task", type=Path, required=True)
    p.add_argument("--change-set", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = verify(json.loads(args.task.read_text()), json.loads(args.change_set.read_text()))
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0 if report["status"] == "verified" else 1

if __name__ == "__main__":
    raise SystemExit(main())
