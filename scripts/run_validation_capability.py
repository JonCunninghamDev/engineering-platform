#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "standards" / "validation-capabilities-v1.json"
DEFAULT_REGISTRY_SCHEMA = ROOT / "schemas" / "validation-capability-registry-v1.schema.json"
BUDGET_DIMENSIONS = (
    "max_steps",
    "max_elapsed_minutes",
    "max_retries",
    "max_cost_usd",
)


class CapabilityExecutionError(ValueError):
    """Raised when capability execution cannot be configured safely."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CapabilityExecutionError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CapabilityExecutionError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CapabilityExecutionError(f"top-level JSON must be an object: {path}")
    return value


def load_registry(
    registry_path: Path = DEFAULT_REGISTRY,
    schema_path: Path = DEFAULT_REGISTRY_SCHEMA,
) -> dict[str, Any]:
    registry = _load_json(registry_path)
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(registry), key=lambda item: list(item.absolute_path))
    if errors:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise CapabilityExecutionError(f"validation capability registry schema failed: {detail}")

    seen: set[str] = set()
    for capability in registry["capabilities"]:
        capability_id = capability["id"]
        if capability_id in seen:
            raise CapabilityExecutionError(f"duplicate validation capability id: {capability_id}")
        seen.add(capability_id)
    return registry


def select_capabilities(
    registry: dict[str, Any],
    requested: Sequence[str],
) -> list[dict[str, Any]]:
    index = {capability["id"]: capability for capability in registry["capabilities"]}
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for capability_id in requested:
        if capability_id in seen:
            continue
        capability = index.get(capability_id)
        if capability is None:
            available = ", ".join(sorted(index))
            raise CapabilityExecutionError(
                f"unknown validation capability {capability_id!r}; available: {available}"
            )
        seen.add(capability_id)
        selected.append(capability)
    return selected


def load_budget_limits(policy_path: Path) -> dict[str, int | float | None]:
    policy = _load_json(policy_path)
    raw = policy.get("execution_budgets", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise CapabilityExecutionError("execution_budgets must be an object when present")

    required = raw.get("required_dimensions", [])
    if not isinstance(required, list):
        raise CapabilityExecutionError("execution_budgets.required_dimensions must be an array")
    for dimension in required:
        if dimension not in BUDGET_DIMENSIONS:
            raise CapabilityExecutionError(f"unknown required budget dimension: {dimension}")
        if dimension not in raw:
            raise CapabilityExecutionError(
                f"required budget dimension is not configured: {dimension}"
            )

    return {dimension: raw.get(dimension) for dimension in BUDGET_DIMENSIONS}


def budget_exhaustion_dimension(
    limits: dict[str, int | float | None],
    *,
    steps: int,
    retries: int,
    elapsed_minutes: float,
    cost_usd: float,
    next_cost_usd: float = 0.0,
    retrying: bool = False,
) -> str | None:
    max_steps = limits.get("max_steps")
    if max_steps is not None and steps >= max_steps:
        return "max_steps"

    max_elapsed = limits.get("max_elapsed_minutes")
    if max_elapsed is not None and elapsed_minutes >= max_elapsed:
        return "max_elapsed_minutes"

    max_retries = limits.get("max_retries")
    if retrying and max_retries is not None and retries >= max_retries:
        return "max_retries"

    max_cost = limits.get("max_cost_usd")
    if max_cost is not None and cost_usd + next_cost_usd > max_cost:
        return "max_cost_usd"

    return None


def _remaining_timeout_seconds(
    limits: dict[str, int | float | None],
    elapsed_minutes: float,
) -> float | None:
    maximum = limits.get("max_elapsed_minutes")
    if maximum is None:
        return None
    remaining = (float(maximum) - elapsed_minutes) * 60.0
    return max(0.001, remaining)


def _budget_evidence(
    limits: dict[str, int | float | None],
    *,
    steps: int,
    retries: int,
    elapsed_minutes: float,
    cost_usd: float,
    exhausted_dimension: str | None,
) -> dict[str, Any]:
    return {
        "limits": {dimension: limits.get(dimension) for dimension in BUDGET_DIMENSIONS},
        "consumption": {
            "steps": steps,
            "elapsed_minutes": round(max(elapsed_minutes, 0.0), 6),
            "retries": retries,
            "cost_usd": round(max(cost_usd, 0.0), 6),
        },
        "exhausted_dimension": exhausted_dimension,
    }


def run_capability(
    *,
    capability: dict[str, Any],
    command: Sequence[str],
    implementation: str,
    limits: dict[str, int | float | None],
    working_directory: Path,
    retry_on_failure: bool = False,
    cost_per_attempt_usd: float = 0.0,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    normalized_command = [str(part) for part in command if str(part)]
    if not normalized_command:
        raise CapabilityExecutionError("validation command must not be empty")
    if cost_per_attempt_usd < 0:
        raise CapabilityExecutionError("cost_per_attempt_usd must be non-negative")
    if retry_on_failure and limits.get("max_retries") is None:
        raise CapabilityExecutionError(
            "retry_on_failure requires execution_budgets.max_retries so retries cannot be unbounded"
        )

    start = clock()
    steps = 0
    retries = 0
    cost_usd = 0.0
    exhausted_dimension: str | None = None
    attempt_results: list[dict[str, Any]] = []
    status = "configuration_error"

    while True:
        elapsed_minutes = max(0.0, (clock() - start) / 60.0)
        retrying = steps > 0
        exhausted_dimension = budget_exhaustion_dimension(
            limits,
            steps=steps,
            retries=retries,
            elapsed_minutes=elapsed_minutes,
            cost_usd=cost_usd,
            next_cost_usd=cost_per_attempt_usd,
            retrying=retrying,
        )
        if exhausted_dimension is not None:
            status = "budget_exhausted"
            break

        attempt = steps + 1
        attempt_start = clock()
        timeout = _remaining_timeout_seconds(limits, elapsed_minutes)
        try:
            completed = subprocess.run(
                normalized_command,
                cwd=working_directory,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            steps += 1
            if attempt > 1:
                retries += 1
            cost_usd += cost_per_attempt_usd
            attempt_results.append(
                {
                    "attempt": attempt,
                    "status": "budget_exhausted",
                    "return_code": None,
                    "duration_ms": round(max(0.0, clock() - attempt_start) * 1000),
                    "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                    "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
                }
            )
            exhausted_dimension = "max_elapsed_minutes"
            status = "budget_exhausted"
            break

        steps += 1
        if attempt > 1:
            retries += 1
        cost_usd += cost_per_attempt_usd
        attempt_results.append(
            {
                "attempt": attempt,
                "status": "passed" if completed.returncode == 0 else "failed",
                "return_code": completed.returncode,
                "duration_ms": round(max(0.0, clock() - attempt_start) * 1000),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )

        if completed.returncode == 0:
            status = "passed"
            break
        if not retry_on_failure:
            status = "test_failed"
            break

    total_elapsed_minutes = max(0.0, (clock() - start) / 60.0)
    return {
        "schema_version": "validation-capability-evidence/v1",
        "capability": capability["id"],
        "category": capability["category"],
        "implementation": implementation,
        "status": status,
        "duration_ms": round(total_elapsed_minutes * 60_000),
        "attempts": steps,
        "retry_count": retries,
        "command": normalized_command,
        "budget": _budget_evidence(
            limits,
            steps=steps,
            retries=retries,
            elapsed_minutes=total_elapsed_minutes,
            cost_usd=cost_usd,
            exhausted_dimension=exhausted_dimension,
        ),
        "attempt_results": attempt_results,
    }


def write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one repository-owned validation command under engineering-policy execution budgets"
    )
    parser.add_argument("--capability", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--registry-schema", type=Path, default=DEFAULT_REGISTRY_SCHEMA)
    parser.add_argument("--implementation", default="repository-defined command")
    parser.add_argument("--working-directory", type=Path, default=Path.cwd())
    parser.add_argument("--retry-on-failure", action="store_true")
    parser.add_argument("--cost-per-attempt-usd", type=float, default=0.0)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]

    try:
        registry = load_registry(args.registry, args.registry_schema)
        selected = select_capabilities(registry, [args.capability])
        limits = load_budget_limits(args.policy)
        evidence = run_capability(
            capability=selected[0],
            command=command,
            implementation=args.implementation,
            limits=limits,
            working_directory=args.working_directory.resolve(),
            retry_on_failure=args.retry_on_failure,
            cost_per_attempt_usd=args.cost_per_attempt_usd,
        )
    except (CapabilityExecutionError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.evidence:
        write_evidence(args.evidence, evidence)
    if args.json:
        print(json.dumps(evidence, indent=2, sort_keys=True))
    else:
        budget = evidence["budget"]
        print(
            f"validation capability {evidence['capability']}: {evidence['status']}; "
            f"attempts={evidence['attempts']} retries={evidence['retry_count']} "
            f"duration_ms={evidence['duration_ms']} "
            f"budget_exhausted={budget['exhausted_dimension']}"
        )
        if evidence["status"] != "passed" and evidence["attempt_results"]:
            final = evidence["attempt_results"][-1]
            if final["stdout"]:
                print(final["stdout"], end="" if final["stdout"].endswith("\n") else "\n")
            if final["stderr"]:
                print(
                    final["stderr"],
                    end="" if final["stderr"].endswith("\n") else "\n",
                    file=sys.stderr,
                )

    if evidence["status"] == "passed":
        return 0
    if evidence["status"] == "test_failed":
        return 1
    if evidence["status"] == "budget_exhausted":
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
