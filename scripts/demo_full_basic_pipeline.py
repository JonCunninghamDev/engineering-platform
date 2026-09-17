#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import builder_agent
import context_agent
import orchestrator_agent
import verifier_agent

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "full-basic-pipeline"
CREATED_AT = "2026-01-01T00:00:00+00:00"


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"top-level JSON must be an object: {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(output_dir: Path, *, corrupt_handoff: bool = False) -> dict:
    contract = load_json(FIXTURES / "context-contract.json")
    supplied = load_json(FIXTURES / "context-input.json")
    registry = load_json(FIXTURES / "capability-registry.json")

    context, context_report = context_agent.run_context_agent(
        contract, supplied, tier="basic", autonomy="advisory", mode="demo",
        run_id="context-demo-001", created_at=CREATED_AT, output_name="context.json"
    )
    if not context["handoff"]["allowed"]:
        raise ValueError("Context did not allow Orchestrator handoff")

    plan, orchestrator_report = orchestrator_agent.run_orchestrator(
        context, registry, tier="basic", autonomy="advisory", mode="demo",
        run_id="orchestrator-demo-001", created_at=CREATED_AT, output_name="execution-plan.json"
    )
    selected = [row for row in plan["planning"]["selected"] if row["provider"] == "builder"]
    if len(selected) != 1:
        raise ValueError("demo requires exactly one Builder-owned selected capability")

    task = {
        "schema_version": "builder-task/v1",
        "assignment": {"id": "builder-assignment-demo-001", "source": "human", "allowed": True},
        "plan": {"run_id": plan["run"]["id"], "capability": selected[0]["capability"]},
        "workflow": plan["workflow"],
        "goal": plan["goal"],
        "scope": {"allowed_paths": ["src/"], "protected_paths": [".github/", "AGENTS.md"]},
        "changes": [{
            "path": "src/demo_greeting.py", "operation": "create",
            "proposed_content": "def greeting(name: str) -> str:\n    return f\"Hello, {name}!\"\n"
        }],
    }
    if corrupt_handoff:
        task["plan"]["run_id"] = "corrupted-plan-link"

    change_set, builder_report = builder_agent.run_builder(
        plan, task, tier="basic", autonomy="advisory", mode="demo",
        run_id="builder-demo-001", created_at=CREATED_AT, output_name="change-set.json"
    )
    verification = verifier_agent.verify(task, change_set)
    if verification["status"] != "verified":
        raise ValueError("Verifier rejected the Builder evidence")

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "context.json": context,
        "context-run.json": context_report,
        "execution-plan.json": plan,
        "orchestrator-run.json": orchestrator_report,
        "builder-task.json": task,
        "change-set.json": change_set,
        "builder-run.json": builder_report,
        "verification-report.json": verification,
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)

    summary = {
        "schema_version": "basic-pipeline-demo-summary/v1",
        "status": "verified",
        "stages": ["context", "orchestrator", "builder_assignment", "builder", "verifier"],
        "evidence": {name: name for name in artifacts},
        "boundaries": {
            "repository_writes": 0,
            "candidate_code_executions": 0,
            "orchestrator_dispatches": plan["planning"]["dispatch_count"],
            "builder_assignment": "explicit_human_demo_assignment",
            "change_evidence": "proposed_not_applied",
        },
    }
    write_json(output_dir / "run-summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run consumer-agnostic Context -> Orchestrator -> Builder -> Verifier Basic demo")
    parser.add_argument("--output-dir", type=Path, default=Path("demo-output/full-basic-pipeline"))
    parser.add_argument("--corrupt-handoff", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        summary = run(args.output_dir, corrupt_handoff=args.corrupt_handoff)
    except (ValueError, context_agent.ContextAgentError, orchestrator_agent.OrchestratorError, builder_agent.BuilderError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Artifacts: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
