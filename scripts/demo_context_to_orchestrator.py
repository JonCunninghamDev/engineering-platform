#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import context_agent
import orchestrator_agent


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"top-level JSON must be an object: {path}")
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Engineering Platform Context -> Orchestrator demo"
    )
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("demo-output"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        contract = _load_json(args.contract)
        supplied = _load_json(args.input)
        registry = _load_json(args.registry)

        context_manifest, context_report = context_agent.run_context_agent(
            contract,
            supplied,
            tier="basic",
            autonomy="advisory",
            mode="demo",
            output_name="context.yaml",
        )
    except (ValueError, context_agent.ContextAgentError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    context_path = args.output_dir / "context.yaml"
    context_report_path = args.output_dir / "context-run.json"
    context_path.write_text(context_agent.to_yaml(context_manifest) + "\n", encoding="utf-8")
    context_report_path.write_text(json.dumps(context_report, indent=2) + "\n", encoding="utf-8")

    print("=== CONTEXT STAGE ===")
    print(context_agent.render_demo(context_report))

    if not context_manifest["handoff"]["allowed"]:
        print("\n=== ORCHESTRATOR STAGE ===")
        print("NOT INVOKED: Context Agent did not allow the handoff.")
        return 2

    try:
        plan, orchestrator_report = orchestrator_agent.run_orchestrator(
            context_manifest,
            registry,
            tier="basic",
            autonomy="advisory",
            mode="demo",
            output_name="execution-plan.yaml",
        )
    except orchestrator_agent.OrchestratorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    plan_path = args.output_dir / "execution-plan.yaml"
    orchestrator_report_path = args.output_dir / "orchestrator-run.json"
    plan_path.write_text(orchestrator_agent.to_yaml(plan) + "\n", encoding="utf-8")
    orchestrator_report_path.write_text(
        json.dumps(orchestrator_report, indent=2) + "\n", encoding="utf-8"
    )

    print("\n=== HANDOFF ===")
    print(
        f"{context_manifest['run']['id']} -> {plan['context_run_id']} "
        "(Context manifest accepted by Orchestrator)"
    )
    print("\n=== ORCHESTRATOR STAGE ===")
    print(orchestrator_agent.render_demo(plan, orchestrator_report))
    print("\n=== ARTIFACTS ===")
    for path in (
        context_path,
        context_report_path,
        plan_path,
        orchestrator_report_path,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
