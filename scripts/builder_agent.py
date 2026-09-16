#!/usr/bin/env python3

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

AGENT_ROLE = "builder"
AGENT_VERSION = "1.0.0"
SUPPORTED_TIER = "basic"
SUPPORTED_AUTONOMY = {"advisory", "supervised", "policy"}
SUPPORTED_MODES = {"demo", "test", "production"}

BASIC_CAPABILITIES = (
    "validate_task_assignment",
    "validate_plan_linkage",
    "enforce_change_scope",
    "normalize_candidate_changes",
    "compute_diff_and_hash_evidence",
    "explain_change_decisions",
    "produce_change_set",
)
MANAGED_CAPABILITIES = (
    "apply_changes_to_workspace",
    "run_focused_validation",
    "bounded_implementation_iteration",
    "update_task_state",
)
FULL_CAPABILITIES = (
    "multi_file_refactor_strategy",
    "dependency_migration",
    "autonomous_implementation_recovery",
    "optimize_implementation_sequence",
)


class BuilderError(ValueError):
    """Raised when the Basic Builder cannot safely produce a change set."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BuilderError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BuilderError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BuilderError(f"top-level JSON must be an object: {path}")
    return data


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_repo_path(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuilderError(f"{label} must be a non-empty repository-relative path")
    path = value.strip()
    if "\\" in path:
        raise BuilderError(f"{label} must use POSIX separators")
    pure = PurePosixPath(path)
    if pure.is_absolute():
        raise BuilderError(f"{label} must be repository-relative")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise BuilderError(f"{label} contains invalid or traversal segments")
    normalized = pure.as_posix()
    if normalized.startswith("../") or normalized == "..":
        raise BuilderError(f"{label} contains path traversal")
    return normalized


def _validate_scope_entry(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuilderError(f"{label} must be a non-empty path or directory prefix")
    raw = value.strip()
    prefix = raw.endswith("/")
    candidate = raw[:-1] if prefix else raw
    normalized = _validate_repo_path(candidate, label=label)
    return f"{normalized}/" if prefix else normalized


def _path_matches_scope(path: str, entry: str) -> bool:
    return path.startswith(entry) if entry.endswith("/") else path == entry


def _validate_execution_plan(plan: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    if plan.get("schema_version") != "execution-plan/v1":
        raise BuilderError("execution plan schema_version must be 'execution-plan/v1'")

    run = plan.get("run")
    if not isinstance(run, dict) or not isinstance(run.get("id"), str) or not run["id"].strip():
        raise BuilderError("execution plan run.id must be non-empty")

    handoff = plan.get("handoff")
    if not isinstance(handoff, dict) or handoff.get("allowed") is not True:
        raise BuilderError("execution plan handoff is not allowed")

    task_plan = task.get("plan")
    if not isinstance(task_plan, dict):
        raise BuilderError("builder task plan linkage is required")
    plan_run_id = task_plan.get("run_id")
    capability_name = task_plan.get("capability")
    if plan_run_id != run["id"]:
        raise BuilderError("builder task plan run_id does not match execution plan")
    if not isinstance(capability_name, str) or not capability_name.strip():
        raise BuilderError("builder task plan.capability must be non-empty")

    planning = plan.get("planning")
    selected = planning.get("selected") if isinstance(planning, dict) else None
    if not isinstance(selected, list):
        raise BuilderError("execution plan planning.selected must be a list")

    match = next(
        (
            row
            for row in selected
            if isinstance(row, dict) and row.get("capability") == capability_name
        ),
        None,
    )
    if match is None:
        raise BuilderError("builder task capability is not selected in execution plan")
    if match.get("provider") != "builder":
        raise BuilderError("selected execution-plan capability is not assigned to provider 'builder'")
    return match


def _validate_assignment(task: dict[str, Any]) -> dict[str, Any]:
    if task.get("schema_version") != "builder-task/v1":
        raise BuilderError("builder task schema_version must be 'builder-task/v1'")
    assignment = task.get("assignment")
    if not isinstance(assignment, dict):
        raise BuilderError("builder task assignment is required")
    if assignment.get("allowed") is not True:
        raise BuilderError("builder task assignment is not allowed")
    if assignment.get("source") not in {"human", "execution-runtime"}:
        raise BuilderError("builder task assignment.source must be human or execution-runtime")
    if not isinstance(assignment.get("id"), str) or not assignment["id"].strip():
        raise BuilderError("builder task assignment.id must be non-empty")
    return assignment


def _build_diff(path: str, operation: str, before: str | None, after: str) -> str:
    before_lines = [] if before is None else before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    fromfile = "/dev/null" if operation == "create" else f"a/{path}"
    tofile = f"b/{path}"
    return "".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=fromfile,
            tofile=tofile,
            lineterm="\n",
        )
    )


def _normalize_changes(task: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    scope = task.get("scope")
    if not isinstance(scope, dict):
        raise BuilderError("builder task scope is required")
    raw_allowed = scope.get("allowed_paths")
    raw_protected = scope.get("protected_paths", [])
    if not isinstance(raw_allowed, list) or not raw_allowed:
        raise BuilderError("scope.allowed_paths must be a non-empty list")
    if not isinstance(raw_protected, list):
        raise BuilderError("scope.protected_paths must be a list")
    allowed = [
        _validate_scope_entry(value, label=f"scope.allowed_paths[{index}]")
        for index, value in enumerate(raw_allowed)
    ]
    protected = [
        _validate_scope_entry(value, label=f"scope.protected_paths[{index}]")
        for index, value in enumerate(raw_protected)
    ]

    raw_changes = task.get("changes")
    if not isinstance(raw_changes, list) or not raw_changes:
        raise BuilderError("builder task changes must be a non-empty list")

    seen: set[str] = set()
    normalized_changes: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_changes):
        if not isinstance(raw, dict):
            raise BuilderError(f"changes[{index}] must be an object")
        path = _validate_repo_path(raw.get("path"), label=f"changes[{index}].path")
        if path in seen:
            raise BuilderError(f"duplicate change path: {path}")
        seen.add(path)

        if not any(_path_matches_scope(path, entry) for entry in allowed):
            raise BuilderError(f"change path is outside allowed scope: {path}")
        if any(_path_matches_scope(path, entry) for entry in protected):
            raise BuilderError(f"change path is protected: {path}")

        operation = raw.get("operation")
        if operation not in {"create", "update"}:
            raise BuilderError(
                f"changes[{index}].operation must be create or update at Basic tier"
            )
        proposed = raw.get("proposed_content")
        if not isinstance(proposed, str):
            raise BuilderError(f"changes[{index}].proposed_content must be a string")

        original = raw.get("original_content")
        if operation == "create":
            if original not in {None, ""}:
                raise BuilderError(
                    f"changes[{index}].original_content must be omitted for create"
                )
            before = None
        else:
            if not isinstance(original, str):
                raise BuilderError(
                    f"changes[{index}].original_content must be a string for update"
                )
            before = original

        normalized_changes.append(
            {
                "path": path,
                "operation": operation,
                "before_content": before,
                "after_content": proposed,
            }
        )
    return normalized_changes, {"allowed_paths": allowed, "protected_paths": protected}


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def to_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                if not child:
                    lines.append(f"{prefix}{key}: {'{}' if isinstance(child, dict) else '[]'}")
                else:
                    lines.append(f"{prefix}{key}:")
                    lines.append(to_yaml(child, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(child)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for child in value:
            if isinstance(child, (dict, list)):
                if not child:
                    lines.append(f"{prefix}- {'{}' if isinstance(child, dict) else '[]'}")
                else:
                    lines.append(f"{prefix}-")
                    lines.append(to_yaml(child, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(child)}")
        return "\n".join(lines)
    return f"{prefix}{_yaml_scalar(value)}"


def run_builder(
    execution_plan: dict[str, Any],
    task: dict[str, Any],
    *,
    tier: str = SUPPORTED_TIER,
    autonomy: str = "advisory",
    mode: str = "demo",
    run_id: str | None = None,
    created_at: str | None = None,
    output_name: str = "change-set.yaml",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if tier != SUPPORTED_TIER:
        raise BuilderError(
            f"service tier {tier!r} is not implemented; Basic Builder supports only 'basic'"
        )
    if autonomy not in SUPPORTED_AUTONOMY:
        raise BuilderError(f"unsupported autonomy profile: {autonomy}")
    if mode not in SUPPORTED_MODES:
        raise BuilderError(f"unsupported execution mode: {mode}")

    assignment = _validate_assignment(task)
    selected_capability = _validate_execution_plan(execution_plan, task)
    normalized_changes, normalized_scope = _normalize_changes(task)

    workflow = task.get("workflow")
    goal = task.get("goal")
    if not isinstance(workflow, str) or not workflow.strip():
        raise BuilderError("builder task workflow must be a non-empty string")
    if not isinstance(goal, str) or not goal.strip():
        raise BuilderError("builder task goal must be a non-empty string")

    actual_run_id = run_id or f"builder-{uuid.uuid4()}"
    actual_created_at = created_at or datetime.now(timezone.utc).isoformat()

    rows: list[dict[str, Any]] = []
    for sequence, change in enumerate(normalized_changes, start=1):
        before = change["before_content"]
        after = change["after_content"]
        rows.append(
            {
                "sequence": sequence,
                "path": change["path"],
                "operation": change["operation"],
                "action": "WOULD_WRITE",
                "before_sha256": None if before is None else _sha256_text(before),
                "after_sha256": _sha256_text(after),
                "diff": _build_diff(change["path"], change["operation"], before, after),
            }
        )

    capability_name = task["plan"]["capability"]
    change_set: dict[str, Any] = {
        "schema_version": "change-set/v1",
        "run": {"id": actual_run_id, "created_at": actual_created_at},
        "agent": {
            "role": AGENT_ROLE,
            "version": AGENT_VERSION,
            "service_tier": tier,
            "autonomy": autonomy,
            "mode": mode,
        },
        "workflow": workflow.strip(),
        "goal": goal.strip(),
        "plan_run_id": task["plan"]["run_id"],
        "task_id": assignment["id"].strip(),
        "assignment_source": assignment["source"],
        "assigned_capability": capability_name,
        "selected_plan_sequence": selected_capability.get("sequence"),
        "scope": normalized_scope,
        "changes": rows,
        "summary": {
            "change_count": len(rows),
            "proposed_write_count": len(rows),
            "actual_write_count": 0,
            "create_count": sum(1 for row in rows if row["operation"] == "create"),
            "update_count": sum(1 for row in rows if row["operation"] == "update"),
        },
        "handoff": {
            "target": "verifier",
            "artifact": output_name,
            "allowed": True,
            "execution_status": "proposed_not_applied",
        },
    }

    report: dict[str, Any] = {
        "schema_version": "agent-run-report/v1",
        "run_id": actual_run_id,
        "agent": change_set["agent"],
        "why_invoked": (
            "An explicit Builder assignment authorizes a scope-checked candidate change set "
            "for a Builder-owned execution-plan capability."
        ),
        "workflow": workflow.strip(),
        "status": "complete",
        "decisions": [
            {
                "decision": "candidate_change_set_created",
                "reason": (
                    f"Accepted {len(rows)} bounded create/update change(s) inside declared "
                    "scope with zero repository writes at Basic tier."
                ),
            }
        ],
        "capabilities": {
            "used": list(BASIC_CAPABILITIES),
            "available_unused": [],
            "locked_by_tier": {
                "managed": list(MANAGED_CAPABILITIES),
                "full": list(FULL_CAPABILITIES),
            },
        },
        "outputs": [output_name],
        "handoff": change_set["handoff"],
        "metrics": dict(change_set["summary"]),
    }
    return change_set, report


def render_demo(change_set: dict[str, Any], report: dict[str, Any]) -> str:
    agent = report["agent"]
    lines = [
        "BUILDER AGENT",
        f"Service tier: {agent['service_tier'].upper()}",
        f"Autonomy: {agent['autonomy'].upper()}",
        f"Mode: {agent['mode'].upper()}",
        f"Status: {report['status'].upper()}",
        "",
        f"Assigned capability: {change_set['assigned_capability']}",
        f"Assignment source: {change_set['assignment_source']}",
        "",
        "Candidate changes:",
    ]
    for row in change_set["changes"]:
        lines.append(
            f"  [{row['action']}] {row['operation']} {row['path']} "
            f"(after_sha256={row['after_sha256']})"
        )
    lines.extend(["", "Locked by higher service tier:"])
    for tier, names in report["capabilities"]["locked_by_tier"].items():
        lines.append(f"  {tier.upper()}")
        lines.extend(f"    [locked] {name}" for name in names)
    lines.extend(
        [
            "",
            f"Proposed write count: {report['metrics']['proposed_write_count']}",
            f"Actual write count: {report['metrics']['actual_write_count']}",
            f"Handoff: {report['handoff']['artifact']} -> {report['handoff']['target']}",
            "Execution status: PROPOSED / NOT APPLIED",
        ]
    )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Engineering Platform Basic Builder Agent")
    parser.add_argument(
        "--plan", type=Path, required=True, help="execution-plan/v1 JSON representation"
    )
    parser.add_argument("--task", type=Path, required=True, help="builder-task/v1 JSON file")
    parser.add_argument("--output", type=Path, default=Path("change-set.yaml"))
    parser.add_argument("--run-report", type=Path, default=Path("builder-run.json"))
    parser.add_argument("--tier", default="basic")
    parser.add_argument("--autonomy", default="advisory", choices=sorted(SUPPORTED_AUTONOMY))
    parser.add_argument("--mode", default="demo", choices=sorted(SUPPORTED_MODES))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        execution_plan = _load_json(args.plan)
        task = _load_json(args.task)
        change_set, report = run_builder(
            execution_plan,
            task,
            tier=args.tier,
            autonomy=args.autonomy,
            mode=args.mode,
            output_name=args.output.name,
        )
    except BuilderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.run_report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(to_yaml(change_set) + "\n", encoding="utf-8")
    args.run_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.mode == "demo":
        print(render_demo(change_set, report))
    else:
        print(
            f"Builder completed: proposed={report['metrics']['proposed_write_count']} "
            f"actual_writes={report['metrics']['actual_write_count']} output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
