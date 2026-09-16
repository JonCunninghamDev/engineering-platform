#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AGENT_ROLE = "orchestrator"
AGENT_VERSION = "1.0.0"
SUPPORTED_TIER = "basic"
SUPPORTED_AUTONOMY = {"advisory", "supervised", "policy"}
SUPPORTED_MODES = {"demo", "test", "production"}

BASIC_CAPABILITIES = (
    "validate_context_handoff",
    "inspect_capability_registry",
    "select_minimum_capabilities",
    "construct_dependency_graph",
    "explain_plan_decisions",
    "produce_execution_plan",
)
MANAGED_CAPABILITIES = (
    "dispatch_agents",
    "track_live_task_state",
    "bounded_retry_and_replan",
    "parallel_workstream_execution",
    "route_human_gates",
)
FULL_CAPABILITIES = (
    "dynamic_capacity_optimization",
    "cost_risk_aware_scheduling",
    "continuous_replanning",
    "self_healing_orchestration",
)


class OrchestratorError(ValueError):
    """Raised when the Basic Orchestrator cannot safely create a plan."""


@dataclass(frozen=True)
class Capability:
    name: str
    provider: str
    description: str
    trigger_terms: tuple[str, ...]
    dependencies: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    risk: str
    minimum_tier: str
    human_gate: bool


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OrchestratorError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise OrchestratorError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise OrchestratorError(f"top-level JSON must be an object: {path}")
    return data


def _validate_context(context: dict[str, Any]) -> None:
    if context.get("schema_version") != "context-manifest/v1":
        raise OrchestratorError("context schema_version must be 'context-manifest/v1'")
    readiness = context.get("readiness")
    handoff = context.get("handoff")
    if not isinstance(readiness, dict) or readiness.get("ready_for_orchestration") is not True:
        raise OrchestratorError("context handoff is not ready for orchestration")
    if not isinstance(handoff, dict) or handoff.get("allowed") is not True:
        raise OrchestratorError("context handoff is not allowed")
    if handoff.get("target") not in {None, "orchestrator"}:
        raise OrchestratorError("context handoff target must be orchestrator")
    goal = context.get("goal")
    workflow = context.get("workflow")
    if not isinstance(goal, str) or not goal.strip():
        raise OrchestratorError("context.goal must be a non-empty string")
    if not isinstance(workflow, str) or not workflow.strip():
        raise OrchestratorError("context.workflow must be a non-empty string")


def _parse_string_list(raw: dict[str, Any], key: str, index: int) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise OrchestratorError(f"registry.capabilities[{index}].{key} must be a string list")
    return tuple(item.strip() for item in value)


def _parse_capability(raw: dict[str, Any], index: int) -> Capability:
    for key in ("name", "provider", "description", "risk", "minimum_tier"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise OrchestratorError(f"registry.capabilities[{index}].{key} must be non-empty")
    if raw["risk"] not in {"low", "medium", "high"}:
        raise OrchestratorError(f"registry.capabilities[{index}].risk must be low, medium, or high")
    if raw["minimum_tier"] not in {"basic", "managed", "full"}:
        raise OrchestratorError(
            f"registry.capabilities[{index}].minimum_tier must be basic, managed, or full"
        )
    human_gate = raw.get("human_gate", False)
    if not isinstance(human_gate, bool):
        raise OrchestratorError(f"registry.capabilities[{index}].human_gate must be boolean")
    return Capability(
        name=raw["name"].strip(),
        provider=raw["provider"].strip(),
        description=raw["description"].strip(),
        trigger_terms=tuple(term.lower() for term in _parse_string_list(raw, "trigger_terms", index)),
        dependencies=_parse_string_list(raw, "dependencies", index),
        inputs=_parse_string_list(raw, "inputs", index),
        outputs=_parse_string_list(raw, "outputs", index),
        risk=raw["risk"],
        minimum_tier=raw["minimum_tier"],
        human_gate=human_gate,
    )


def _validate_registry(registry: dict[str, Any]) -> dict[str, Capability]:
    if registry.get("schema_version") != "capability-registry/v1":
        raise OrchestratorError("registry schema_version must be 'capability-registry/v1'")
    raw_caps = registry.get("capabilities")
    if not isinstance(raw_caps, list) or not raw_caps:
        raise OrchestratorError("registry.capabilities must be a non-empty list")
    capabilities: dict[str, Capability] = {}
    for index, raw in enumerate(raw_caps):
        if not isinstance(raw, dict):
            raise OrchestratorError(f"registry.capabilities[{index}] must be an object")
        capability = _parse_capability(raw, index)
        if capability.name in capabilities:
            raise OrchestratorError(f"duplicate capability: {capability.name}")
        capabilities[capability.name] = capability
    for capability in capabilities.values():
        for dependency in capability.dependencies:
            if dependency not in capabilities:
                raise OrchestratorError(
                    f"capability {capability.name} depends on unknown capability {dependency}"
                )
    return capabilities


def _goal_text(context: dict[str, Any]) -> str:
    pieces = [str(context.get("goal", "")), str(context.get("workflow", ""))]
    normalized = context.get("normalized_context", {})
    if isinstance(normalized, dict):
        for value in normalized.values():
            if isinstance(value, str):
                pieces.append(value)
            elif isinstance(value, list):
                pieces.extend(str(item) for item in value)
    return " ".join(pieces).lower()


def _dependency_closure(selected: set[str], capabilities: dict[str, Capability]) -> set[str]:
    result = set(selected)
    stack = list(selected)
    while stack:
        name = stack.pop()
        for dependency in capabilities[name].dependencies:
            if dependency not in result:
                result.add(dependency)
                stack.append(dependency)
    return result


def _topological_order(selected: set[str], capabilities: dict[str, Capability]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[str] = []

    def visit(name: str) -> None:
        if name in visiting:
            raise OrchestratorError(f"dependency cycle detected at {name}")
        if name in visited:
            return
        visiting.add(name)
        for dependency in sorted(capabilities[name].dependencies):
            if dependency in selected:
                visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(name)

    for name in sorted(selected):
        visit(name)
    return ordered


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
    """Serialize the plan subset to deterministic YAML without third-party dependencies."""
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


def run_orchestrator(
    context: dict[str, Any],
    registry: dict[str, Any],
    *,
    tier: str = SUPPORTED_TIER,
    autonomy: str = "advisory",
    mode: str = "demo",
    run_id: str | None = None,
    created_at: str | None = None,
    output_name: str = "execution-plan.yaml",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if tier != SUPPORTED_TIER:
        raise OrchestratorError(
            f"service tier {tier!r} is not implemented; Basic Orchestrator supports only 'basic'"
        )
    if autonomy not in SUPPORTED_AUTONOMY:
        raise OrchestratorError(f"unsupported autonomy profile: {autonomy}")
    if mode not in SUPPORTED_MODES:
        raise OrchestratorError(f"unsupported execution mode: {mode}")

    _validate_context(context)
    capabilities = _validate_registry(registry)
    text = _goal_text(context)
    directly_selected = {
        name
        for name, capability in capabilities.items()
        if capability.minimum_tier == "basic"
        and any(term in text for term in capability.trigger_terms)
    }
    if not directly_selected:
        raise OrchestratorError("no Basic capability matches the supplied goal/context")

    selected = _dependency_closure(directly_selected, capabilities)
    non_basic = [name for name in selected if capabilities[name].minimum_tier != "basic"]
    if non_basic:
        raise OrchestratorError(
            "selected plan requires capabilities unavailable at Basic tier: "
            + ", ".join(sorted(non_basic))
        )
    order = _topological_order(selected, capabilities)

    selected_rows: list[dict[str, Any]] = []
    for sequence, name in enumerate(order, start=1):
        capability = capabilities[name]
        reason = (
            "goal/context matched capability trigger"
            if name in directly_selected
            else "required dependency of a selected capability"
        )
        selected_rows.append(
            {
                "sequence": sequence,
                "capability": name,
                "provider": capability.provider,
                "dependencies": list(capability.dependencies),
                "risk": capability.risk,
                "human_gate": capability.human_gate,
                "action": "WOULD_INVOKE",
                "reason": reason,
                "inputs": list(capability.inputs),
                "outputs": list(capability.outputs),
            }
        )

    skipped: list[dict[str, str]] = []
    for name in sorted(capabilities):
        if name in selected:
            continue
        capability = capabilities[name]
        reason = (
            f"locked: requires {capability.minimum_tier} tier"
            if capability.minimum_tier != "basic"
            else "not needed: no goal/context trigger matched"
        )
        skipped.append(
            {"capability": name, "provider": capability.provider, "reason": reason}
        )

    actual_run_id = run_id or f"orchestrator-{uuid.uuid4()}"
    actual_created_at = created_at or datetime.now(timezone.utc).isoformat()
    plan: dict[str, Any] = {
        "schema_version": "execution-plan/v1",
        "run": {"id": actual_run_id, "created_at": actual_created_at},
        "agent": {
            "role": AGENT_ROLE,
            "version": AGENT_VERSION,
            "service_tier": tier,
            "autonomy": autonomy,
            "mode": mode,
        },
        "workflow": context["workflow"],
        "goal": context["goal"],
        "context_run_id": context.get("run", {}).get("id"),
        "planning": {
            "strategy": "minimum_sufficient_capabilities",
            "selected_count": len(selected_rows),
            "dispatch_count": 0,
            "selected": selected_rows,
            "skipped": skipped,
        },
        "handoff": {
            "target": "execution-runtime",
            "artifact": output_name,
            "allowed": True,
            "execution_status": "planned_not_dispatched",
        },
    }
    report: dict[str, Any] = {
        "schema_version": "agent-run-report/v1",
        "run_id": actual_run_id,
        "agent": plan["agent"],
        "why_invoked": (
            "Ready Context Agent handoff requires an explainable minimum-sufficient execution plan."
        ),
        "workflow": context["workflow"],
        "status": "complete",
        "decisions": [
            {
                "decision": "execution_plan_created",
                "reason": (
                    f"Selected {len(selected_rows)} capability step(s) with zero downstream "
                    "dispatches at Basic tier."
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
        "handoff": plan["handoff"],
        "metrics": {
            "selected_capability_count": len(selected_rows),
            "skipped_capability_count": len(skipped),
            "dispatch_count": 0,
            "human_gate_count": sum(1 for row in selected_rows if row["human_gate"]),
        },
    }
    return plan, report


def render_demo(plan: dict[str, Any], report: dict[str, Any]) -> str:
    agent = report["agent"]
    lines = [
        "ORCHESTRATOR AGENT",
        f"Service tier: {agent['service_tier'].upper()}",
        f"Autonomy: {agent['autonomy'].upper()}",
        f"Mode: {agent['mode'].upper()}",
        f"Status: {report['status'].upper()}",
        "",
        "Would invoke:",
    ]
    for row in plan["planning"]["selected"]:
        dependencies = ", ".join(row["dependencies"]) if row["dependencies"] else "none"
        lines.append(
            f"  [{row['action']}] {row['capability']} -> {row['provider']} "
            f"(depends_on={dependencies}; reason={row['reason']})"
        )
    if plan["planning"]["skipped"]:
        lines.extend(["", "Considered but skipped:"])
        for row in plan["planning"]["skipped"]:
            lines.append(f"  [skipped] {row['capability']} ({row['reason']})")
    lines.extend(["", "Locked by higher service tier:"])
    for tier, names in report["capabilities"]["locked_by_tier"].items():
        lines.append(f"  {tier.upper()}")
        lines.extend(f"    [locked] {name}" for name in names)
    lines.extend(
        [
            "",
            f"Dispatch count: {report['metrics']['dispatch_count']}",
            f"Handoff: {report['handoff']['artifact']} -> {report['handoff']['target']}",
            "Execution status: PLANNED / NOT DISPATCHED",
        ]
    )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Engineering Platform Basic Orchestrator Agent"
    )
    parser.add_argument(
        "--context",
        type=Path,
        required=True,
        help="context-manifest/v1 JSON representation",
    )
    parser.add_argument(
        "--registry", type=Path, required=True, help="capability-registry/v1 JSON file"
    )
    parser.add_argument("--output", type=Path, default=Path("execution-plan.yaml"))
    parser.add_argument("--run-report", type=Path, default=Path("orchestrator-run.json"))
    parser.add_argument("--tier", default="basic")
    parser.add_argument(
        "--autonomy", default="advisory", choices=sorted(SUPPORTED_AUTONOMY)
    )
    parser.add_argument("--mode", default="demo", choices=sorted(SUPPORTED_MODES))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        context = _load_json(args.context)
        registry = _load_json(args.registry)
        plan, report = run_orchestrator(
            context,
            registry,
            tier=args.tier,
            autonomy=args.autonomy,
            mode=args.mode,
            output_name=args.output.name,
        )
    except OrchestratorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.run_report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(to_yaml(plan) + "\n", encoding="utf-8")
    args.run_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.mode == "demo":
        print(render_demo(plan, report))
    else:
        print(
            f"Orchestrator completed: selected={report['metrics']['selected_capability_count']} "
            f"dispatch_count={report['metrics']['dispatch_count']} output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
