#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "standards" / "fast-feedback-v1.json"
ALLOWED_STAGES = ("after_write", "pre_commit", "completion_gate")


class FastFeedbackConfigError(ValueError):
    """Raised when repository-local fast-feedback configuration is invalid."""


def load_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FastFeedbackConfigError(f"config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FastFeedbackConfigError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FastFeedbackConfigError("fast-feedback config must be a JSON object")
    if value.get("schema_version") != "fast-feedback/v1":
        raise FastFeedbackConfigError("schema_version must be 'fast-feedback/v1'")
    stages = value.get("stages")
    if not isinstance(stages, dict):
        raise FastFeedbackConfigError("stages must be an object")
    unknown = sorted(set(stages) - set(ALLOWED_STAGES))
    if unknown:
        raise FastFeedbackConfigError(f"unknown fast-feedback stage(s): {', '.join(unknown)}")
    for stage in ALLOWED_STAGES:
        commands = stages.get(stage)
        if not isinstance(commands, list) or not commands:
            raise FastFeedbackConfigError(f"stage {stage!r} must contain at least one command")
        seen: set[str] = set()
        for index, entry in enumerate(commands):
            if not isinstance(entry, dict):
                raise FastFeedbackConfigError(f"{stage}[{index}] must be an object")
            command_id = entry.get("id")
            command = entry.get("command")
            if not isinstance(command_id, str) or not command_id.strip():
                raise FastFeedbackConfigError(f"{stage}[{index}].id must be a non-empty string")
            if command_id in seen:
                raise FastFeedbackConfigError(f"duplicate command id in {stage}: {command_id}")
            seen.add(command_id)
            if not isinstance(command, list) or not command or not all(
                isinstance(part, str) and part for part in command
            ):
                raise FastFeedbackConfigError(
                    f"{stage}[{index}].command must be a non-empty string array"
                )
    return value


def run_stage(
    *,
    root: Path,
    config: dict[str, Any],
    stage: str,
    echo: bool = True,
) -> dict[str, Any]:
    if stage not in ALLOWED_STAGES:
        raise FastFeedbackConfigError(f"unsupported stage: {stage}")

    started = time.monotonic()
    command_results: list[dict[str, Any]] = []
    status = "passed"

    for entry in config["stages"][stage]:
        command = list(entry["command"])
        if echo:
            print(f"[{stage}] {entry['id']}: {' '.join(command)}")
        command_started = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        duration_ms = round((time.monotonic() - command_started) * 1000)
        result = {
            "id": entry["id"],
            "command": command,
            "status": "passed" if completed.returncode == 0 else "failed",
            "return_code": completed.returncode,
            "duration_ms": duration_ms,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        command_results.append(result)

        if echo and completed.stdout:
            print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
        if echo and completed.stderr:
            print(
                completed.stderr,
                end="" if completed.stderr.endswith("\n") else "\n",
                file=sys.stderr,
            )

        if completed.returncode != 0:
            status = "failed"
            break

    return {
        "schema_version": "fast-feedback-evidence/v1",
        "stage": stage,
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "commands": command_results,
    }


def write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a host-neutral Engineering Platform validation stage")
    parser.add_argument("--stage", choices=ALLOWED_STAGES, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true", help="print evidence JSON to stdout")
    parser.add_argument("--quiet", action="store_true", help="suppress command output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        evidence = run_stage(
            root=args.root.resolve(),
            config=config,
            stage=args.stage,
            echo=not args.quiet and not args.json,
        )
    except FastFeedbackConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.evidence:
        write_evidence(args.evidence, evidence)
    if args.json:
        print(json.dumps(evidence, indent=2, sort_keys=True))
    elif not args.quiet:
        print(
            f"fast-feedback {args.stage}: {evidence['status']} "
            f"({len(evidence['commands'])} command(s), {evidence['duration_ms']} ms)"
        )
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
