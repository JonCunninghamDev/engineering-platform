#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "engineering-run/v1"
MILESTONE_NAMES = {
    "intent_received",
    "context_ready",
    "plan_ready",
    "builder_assigned",
    "first_change",
    "verification_started",
    "verification_passed",
    "pr_created",
    "human_review_started",
    "human_approved",
    "merged",
    "deployed",
}


class EngineeringRunError(ValueError):
    """Raised when Engineering Run evidence is malformed or inconsistent."""


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise EngineeringRunError("event timestamp must be a non-empty ISO-8601 string")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise EngineeringRunError(f"invalid event timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise EngineeringRunError("event timestamp must include a timezone offset")
    return parsed


def _milliseconds(start: datetime, end: datetime) -> int:
    delta = int(round((end - start).total_seconds() * 1000))
    if delta < 0:
        raise EngineeringRunError("lifecycle events are out of temporal order")
    return delta


def normalize_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(events):
        if not isinstance(raw, dict):
            raise EngineeringRunError(f"events[{index}] must be an object")
        name = raw.get("name")
        at = raw.get("at")
        if not isinstance(name, str) or name not in MILESTONE_NAMES:
            raise EngineeringRunError(f"events[{index}].name is not a supported milestone")
        if name in seen:
            raise EngineeringRunError(f"duplicate lifecycle milestone: {name}")
        seen.add(name)
        parsed = _parse_time(at)
        event: dict[str, Any] = {"name": name, "at": parsed.isoformat()}
        actor = raw.get("actor")
        if actor is not None:
            if not isinstance(actor, str) or not actor.strip():
                raise EngineeringRunError(f"events[{index}].actor must be non-empty when provided")
            event["actor"] = actor.strip()
        evidence = raw.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, str) or not evidence.strip():
                raise EngineeringRunError(f"events[{index}].evidence must be non-empty when provided")
            event["evidence"] = evidence.strip()
        normalized.append(event)
    normalized.sort(key=lambda event: _parse_time(event["at"]))
    return normalized


def derive_metrics(events: list[dict[str, Any]]) -> dict[str, int | None]:
    times = {event["name"]: _parse_time(event["at"]) for event in events}

    def between(start: str, end: str) -> int | None:
        if start not in times or end not in times:
            return None
        return _milliseconds(times[start], times[end])

    return {
        "intent_to_plan_ms": between("intent_received", "plan_ready"),
        "plan_to_first_change_ms": between("plan_ready", "first_change"),
        "verification_ms": between("verification_started", "verification_passed"),
        "intent_to_verified_ms": between("intent_received", "verification_passed"),
        "intent_to_pr_ms": between("intent_received", "pr_created"),
        "pr_cycle_ms": between("pr_created", "merged"),
        "intent_to_merge_ms": between("intent_received", "merged"),
    }


def build_engineering_run(
    *,
    run_id: str,
    created_at: str,
    task: dict[str, Any],
    dimensions: dict[str, Any],
    events: list[dict[str, Any]],
    safety: dict[str, int] | None = None,
    reliability: dict[str, Any] | None = None,
    autonomy: dict[str, Any] | None = None,
    efficiency: dict[str, Any] | None = None,
    outcome: dict[str, Any] | None = None,
    evidence: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if not isinstance(run_id, str) or not run_id.strip():
        raise EngineeringRunError("run_id must be non-empty")
    created = _parse_time(created_at)
    if not isinstance(task, dict) or not isinstance(task.get("goal"), str) or not task["goal"].strip():
        raise EngineeringRunError("task.goal must be non-empty")
    if not isinstance(task.get("workflow"), str) or not task["workflow"].strip():
        raise EngineeringRunError("task.workflow must be non-empty")
    if not isinstance(dimensions, dict):
        raise EngineeringRunError("dimensions must be an object")

    normalized_events = normalize_events(events)
    if normalized_events and _parse_time(normalized_events[0]["at"]) < created:
        raise EngineeringRunError("lifecycle event predates run creation")

    safety_defaults = {
        "policy_violations_attempted": 0,
        "policy_violations_blocked": 0,
        "policy_violations_escaped": 0,
        "unauthorized_actions_attempted": 0,
        "human_gate_bypasses": 0,
        "architecture_violations": 0,
        "security_findings_introduced": 0,
    }
    safety_payload = {**safety_defaults, **(safety or {})}
    for key, value in safety_payload.items():
        if not isinstance(value, int) or value < 0:
            raise EngineeringRunError(f"safety.{key} must be a non-negative integer")
    if safety_payload["policy_violations_blocked"] > safety_payload["policy_violations_attempted"]:
        raise EngineeringRunError("blocked policy violations cannot exceed attempted violations")
    safety_payload["safe"] = all(
        safety_payload[key] == 0
        for key in (
            "policy_violations_escaped",
            "human_gate_bypasses",
            "architecture_violations",
            "security_findings_introduced",
        )
    )

    reliability_payload = {
        "first_pass_verification": None,
        "eventual_verification": None,
        "ci_passed": None,
        "retries": 0,
        "repair_loops": 0,
        "acceptance_criteria_total": None,
        "acceptance_criteria_verified": None,
        **(reliability or {}),
    }
    for key in ("retries", "repair_loops"):
        value = reliability_payload[key]
        if not isinstance(value, int) or value < 0:
            raise EngineeringRunError(f"reliability.{key} must be a non-negative integer")

    autonomy_payload = {
        "human_interventions": 0,
        "human_minutes": None,
        "escalations": 0,
        "completed_within_granted_autonomy": None,
        **(autonomy or {}),
    }
    for key in ("human_interventions", "escalations"):
        value = autonomy_payload[key]
        if not isinstance(value, int) or value < 0:
            raise EngineeringRunError(f"autonomy.{key} must be a non-negative integer")

    efficiency_payload = {
        "model_cost_usd": None,
        "compute_ms": None,
        "tokens": None,
        "tool_calls": None,
        "failed_run_cost_usd": None,
        **(efficiency or {}),
    }

    outcome_payload = {
        "status": "planned",
        "pr": None,
        "merge_commit": None,
        "deployment": None,
        **(outcome or {}),
    }
    if outcome_payload["status"] not in {
        "planned", "proposed", "verified", "pr_open",
        "merged", "deployed", "blocked", "failed"
    }:
        raise EngineeringRunError("outcome.status is not supported")

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id.strip(),
        "created_at": created.isoformat(),
        "task": task,
        "dimensions": dimensions,
        "lifecycle": {"events": normalized_events},
        "safety": safety_payload,
        "reliability": reliability_payload,
        "autonomy": autonomy_payload,
        "efficiency": efficiency_payload,
        "outcome": outcome_payload,
        "derived_metrics": derive_metrics(normalized_events),
        "evidence": evidence or [],
    }


def _rate(values: list[bool]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value) / len(values)


def _median(values: list[int | float]) -> int | float | None:
    if not values:
        return None
    return statistics.median(values)


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {
            "schema_version": "engineering-run-summary/v1",
            "run_count": 0,
            "rates": {},
            "medians": {},
        }
    for index, run in enumerate(runs):
        if run.get("schema_version") != SCHEMA_VERSION:
            raise EngineeringRunError(f"runs[{index}] is not {SCHEMA_VERSION}")

    metric_names = (
        "intent_to_plan_ms",
        "plan_to_first_change_ms",
        "verification_ms",
        "intent_to_verified_ms",
        "intent_to_pr_ms",
        "pr_cycle_ms",
        "intent_to_merge_ms",
    )
    medians: dict[str, int | float | None] = {}
    for name in metric_names:
        values = [
            run.get("derived_metrics", {}).get(name)
            for run in runs
            if isinstance(run.get("derived_metrics", {}).get(name), (int, float))
        ]
        medians[name] = _median(values)

    human_interventions = [
        run.get("autonomy", {}).get("human_interventions")
        for run in runs
        if isinstance(run.get("autonomy", {}).get("human_interventions"), int)
    ]
    medians["human_interventions"] = _median(human_interventions)

    rates = {
        "safe_run_rate": _rate([
            value for run in runs
            if isinstance((value := run.get("safety", {}).get("safe")), bool)
        ]),
        "first_pass_verification_rate": _rate([
            value for run in runs
            if isinstance((value := run.get("reliability", {}).get("first_pass_verification")), bool)
        ]),
        "eventual_verification_rate": _rate([
            value for run in runs
            if isinstance((value := run.get("reliability", {}).get("eventual_verification")), bool)
        ]),
        "autonomy_completion_rate": _rate([
            value for run in runs
            if isinstance((value := run.get("autonomy", {}).get("completed_within_granted_autonomy")), bool)
        ]),
    }
    return {
        "schema_version": "engineering-run-summary/v1",
        "run_count": len(runs),
        "rates": rates,
        "medians": medians,
    }


def _load_run(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EngineeringRunError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EngineeringRunError(f"top-level JSON must be an object: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize Engineering Platform run evidence")
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    summary = summarize_runs([_load_run(path) for path in args.runs])
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
