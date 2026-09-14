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

AGENT_ROLE = "context"
AGENT_VERSION = "1.0.0"
SUPPORTED_TIER = "basic"
SUPPORTED_AUTONOMY = {"advisory", "supervised", "policy"}
SUPPORTED_MODES = {"demo", "test", "production"}

BASIC_CAPABILITIES = (
    "inspect_context_contract",
    "normalize_supplied_context",
    "identify_missing_context",
    "detect_explicit_conflicts",
    "formulate_blocking_questions",
    "produce_context_manifest",
)

MANAGED_CAPABILITIES = (
    "retrieve_approved_context",
    "verify_source_provenance",
    "evaluate_context_freshness",
    "generate_role_specific_context",
    "request_blocking_context_interactively",
)

FULL_CAPABILITIES = (
    "continuous_context_maintenance",
    "automatic_context_enrichment",
    "sensitivity_classification",
    "cross_project_context_relationships",
    "durable_verified_context_updates",
    "stale_context_monitoring",
)


class ContextAgentError(ValueError):
    """Raised when the Basic Context Agent receives invalid or unsupported input."""


@dataclass(frozen=True)
class ContextField:
    key: str
    requirement: str
    prompt: str


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContextAgentError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContextAgentError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContextAgentError(f"top-level JSON must be an object: {path}")
    return data


def _validate_contract(contract: dict[str, Any]) -> tuple[str, list[ContextField]]:
    if contract.get("schema_version") != "context-contract/v1":
        raise ContextAgentError("contract schema_version must be 'context-contract/v1'")
    workflow = contract.get("workflow")
    if not isinstance(workflow, str) or not workflow.strip():
        raise ContextAgentError("contract.workflow must be a non-empty string")
    raw_fields = contract.get("fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ContextAgentError("contract.fields must be a non-empty list")

    fields: list[ContextField] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_fields):
        if not isinstance(raw, dict):
            raise ContextAgentError(f"contract.fields[{index}] must be an object")
        key = raw.get("key")
        requirement = raw.get("requirement")
        prompt = raw.get("prompt")
        if not isinstance(key, str) or not key.strip():
            raise ContextAgentError(f"contract.fields[{index}].key must be non-empty")
        key = key.strip()
        if key in seen:
            raise ContextAgentError(f"duplicate contract field: {key}")
        if requirement not in {"required", "recommended", "optional"}:
            raise ContextAgentError(
                f"contract field {key!r} requirement must be required, recommended, or optional"
            )
        if not isinstance(prompt, str) or not prompt.strip():
            raise ContextAgentError(f"contract field {key!r} must define a prompt")
        seen.add(key)
        fields.append(ContextField(key=key, requirement=requirement, prompt=prompt.strip()))
    return workflow.strip(), fields


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    return False


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _validate_input(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    if payload.get("schema_version") != "context-input/v1":
        raise ContextAgentError("input schema_version must be 'context-input/v1'")
    goal = payload.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise ContextAgentError("input.goal must be a non-empty string")
    items = payload.get("context", [])
    if not isinstance(items, list):
        raise ContextAgentError("input.context must be a list")

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ContextAgentError(f"input.context[{index}] must be an object")
        key = raw.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ContextAgentError(f"input.context[{index}].key must be non-empty")
        source = raw.get("source", "human")
        if not isinstance(source, str) or not source.strip():
            raise ContextAgentError(f"input.context[{index}].source must be non-empty")
        confidence = raw.get("confidence", "unspecified")
        if confidence not in {"high", "medium", "low", "unspecified"}:
            raise ContextAgentError(
                f"input.context[{index}].confidence must be high, medium, low, or unspecified"
            )
        normalized.append(
            {
                "key": key.strip(),
                "value": _normalize_value(raw.get("value")),
                "source": source.strip(),
                "confidence": confidence,
                "observed_at": raw.get("observed_at"),
            }
        )
    return goal.strip(), normalized


def _group_values(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(item["key"], []).append(item)
    return grouped


def _detect_conflicts(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for key in sorted(grouped):
        present = [item for item in grouped[key] if not _is_missing(item["value"])]
        distinct: dict[str, Any] = {}
        for item in present:
            distinct.setdefault(_canonical(item["value"]), item["value"])
        if len(distinct) > 1:
            conflicts.append(
                {
                    "key": key,
                    "values": list(distinct.values()),
                    "sources": sorted({item["source"] for item in present}),
                }
            )
    return conflicts


def _select_context(grouped: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key in sorted(grouped):
        present = [item for item in grouped[key] if not _is_missing(item["value"])]
        distinct = {_canonical(item["value"]) for item in present}
        if len(distinct) == 1 and present:
            selected[key] = present[0]["value"]
    return selected


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
    """Serialize the manifest subset to deterministic YAML without third-party dependencies."""
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


def run_context_agent(
    contract: dict[str, Any],
    payload: dict[str, Any],
    *,
    tier: str = SUPPORTED_TIER,
    autonomy: str = "advisory",
    mode: str = "demo",
    run_id: str | None = None,
    created_at: str | None = None,
    output_name: str = "context.yaml",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if tier != SUPPORTED_TIER:
        raise ContextAgentError(
            f"service tier {tier!r} is not implemented; Basic Context Agent supports only 'basic'"
        )
    if autonomy not in SUPPORTED_AUTONOMY:
        raise ContextAgentError(f"unsupported autonomy profile: {autonomy}")
    if mode not in SUPPORTED_MODES:
        raise ContextAgentError(f"unsupported execution mode: {mode}")

    workflow, fields = _validate_contract(contract)
    goal, items = _validate_input(payload)
    grouped = _group_values(items)
    conflicts = _detect_conflicts(grouped)
    selected = _select_context(grouped)

    missing_required: list[str] = []
    missing_recommended: list[str] = []
    questions: list[dict[str, str]] = []
    requirement_by_key = {field.key: field.requirement for field in fields}

    for field in fields:
        values = [item["value"] for item in grouped.get(field.key, [])]
        has_value = any(not _is_missing(value) for value in values)
        if not has_value:
            if field.requirement == "required":
                missing_required.append(field.key)
                questions.append({"key": field.key, "question": field.prompt})
            elif field.requirement == "recommended":
                missing_recommended.append(field.key)

    blocking_conflicts = [
        conflict for conflict in conflicts if requirement_by_key.get(conflict["key"]) == "required"
    ]
    ready = not missing_required and not blocking_conflicts

    capabilities_used = [
        "inspect_context_contract",
        "normalize_supplied_context",
        "identify_missing_context",
        "detect_explicit_conflicts",
        "produce_context_manifest",
    ]
    capabilities_available_unused: list[str] = []
    if questions:
        capabilities_used.insert(-1, "formulate_blocking_questions")
    else:
        capabilities_available_unused.append("formulate_blocking_questions")

    actual_run_id = run_id or f"context-{uuid.uuid4()}"
    actual_created_at = created_at or datetime.now(timezone.utc).isoformat()

    manifest: dict[str, Any] = {
        "schema_version": "context-manifest/v1",
        "run": {"id": actual_run_id, "created_at": actual_created_at},
        "agent": {
            "role": AGENT_ROLE,
            "version": AGENT_VERSION,
            "service_tier": tier,
            "autonomy": autonomy,
            "mode": mode,
        },
        "workflow": workflow,
        "goal": goal,
        "readiness": {
            "ready_for_orchestration": ready,
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
            "blocking_conflicts": blocking_conflicts,
            "nonblocking_conflicts": [c for c in conflicts if c not in blocking_conflicts],
        },
        "normalized_context": selected,
        "provenance": items,
        "questions_for_human": questions,
        "capabilities": {
            "used": capabilities_used,
            "available_unused": capabilities_available_unused,
            "locked_by_tier": {
                "managed": list(MANAGED_CAPABILITIES),
                "full": list(FULL_CAPABILITIES),
            },
        },
        "handoff": {"target": "orchestrator", "artifact": output_name, "allowed": ready},
    }

    report: dict[str, Any] = {
        "schema_version": "agent-run-report/v1",
        "run_id": actual_run_id,
        "agent": manifest["agent"],
        "why_invoked": "Human/task context requires normalization and readiness assessment before orchestration.",
        "workflow": workflow,
        "status": "complete" if ready else "needs_context",
        "decisions": [
            {
                "decision": "context_ready" if ready else "context_not_ready",
                "reason": (
                    "All required context is present and no required field has conflicting values."
                    if ready
                    else "Required context is missing or contains unresolved required-field conflicts."
                ),
            }
        ],
        "capabilities": manifest["capabilities"],
        "outputs": [output_name],
        "handoff": manifest["handoff"],
        "metrics": {
            "supplied_context_items": len(items),
            "normalized_context_keys": len(selected),
            "missing_required_count": len(missing_required),
            "missing_recommended_count": len(missing_recommended),
            "conflict_count": len(conflicts),
            "human_questions_count": len(questions),
        },
    }
    return manifest, report


def render_demo(report: dict[str, Any]) -> str:
    agent = report["agent"]
    capabilities = report["capabilities"]
    lines = [
        "CONTEXT AGENT",
        f"Service tier: {agent['service_tier'].upper()}",
        f"Autonomy: {agent['autonomy'].upper()}",
        f"Mode: {agent['mode'].upper()}",
        f"Status: {report['status'].upper()}",
        "",
        "Why invoked:",
        f"  {report['why_invoked']}",
        "",
        "Performed at active tier:",
    ]
    lines.extend(f"  [used] {name}" for name in capabilities["used"])
    if capabilities["available_unused"]:
        lines.append("")
        lines.append("Available at active tier but not needed:")
        lines.extend(f"  [unused] {name}" for name in capabilities["available_unused"])
    lines.append("")
    lines.append("Locked by higher service tier:")
    for tier, names in capabilities["locked_by_tier"].items():
        lines.append(f"  {tier.upper()}")
        lines.extend(f"    [locked] {name}" for name in names)
    lines.extend([
        "",
        f"Handoff: {report['handoff']['artifact']} -> {report['handoff']['target']}",
        f"Handoff allowed: {'YES' if report['handoff']['allowed'] else 'NO'}",
    ])
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Engineering Platform Basic Context Agent")
    parser.add_argument("--contract", type=Path, required=True, help="context-contract/v1 JSON file")
    parser.add_argument("--input", type=Path, required=True, help="context-input/v1 JSON file")
    parser.add_argument("--output", type=Path, default=Path("context.yaml"))
    parser.add_argument("--run-report", type=Path, default=Path("context-run.json"))
    parser.add_argument("--tier", default="basic")
    parser.add_argument("--autonomy", default="advisory", choices=sorted(SUPPORTED_AUTONOMY))
    parser.add_argument("--mode", default="demo", choices=sorted(SUPPORTED_MODES))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        contract = _load_json(args.contract)
        payload = _load_json(args.input)
        manifest, report = run_context_agent(
            contract,
            payload,
            tier=args.tier,
            autonomy=args.autonomy,
            mode=args.mode,
            output_name=args.output.name,
        )
    except ContextAgentError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.run_report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(to_yaml(manifest) + "\n", encoding="utf-8")
    args.run_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.mode == "demo":
        print(render_demo(report))
    else:
        print(
            f"Context Agent completed: status={report['status']} "
            f"handoff_allowed={report['handoff']['allowed']} output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
