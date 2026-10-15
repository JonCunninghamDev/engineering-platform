#!/usr/bin/env python3
"""Run required pre-PR checks in an existing trusted local checkout.

Validation-only adapter: no clone, worker execution, push, PR, merge, or
sandboxing. Run only repository-owned commands from an authorized envelope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SHA = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class RunnerError(ValueError):
    """The authorized execution or checkout could not be verified."""


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True,
        text=True, timeout=15, check=False,
    )
    if result.returncode:
        raise RunnerError("Git verification failed for " + args[0])
    return result.stdout.strip()


def _verify_repo(envelope: dict[str, Any], checkout: Path) -> dict[str, str]:
    if envelope.get("schema_version") != "execution-envelope/v1":
        raise RunnerError("Expected execution-envelope/v1")
    if envelope.get("authorization", {}).get("allowed") is not True:
        raise RunnerError("Execution envelope is not authorized")
    if envelope.get("executor") != {"adapter": "local-checkout", "provider": "local"}:
        raise RunnerError("Envelope is not authorized for the local-checkout executor")
    if envelope.get("delivery", {}).get("release_write_allowed") is not False:
        raise RunnerError("Release write boundary is not disabled")
    repo = envelope.get("repository")
    if not isinstance(repo, dict):
        raise RunnerError("Missing repository authorization")
    identifier, branch, base = (repo.get(k) for k in ("identifier", "feature_branch", "base_commit"))
    if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
        raise RunnerError("Invalid repository identifier")
    if not isinstance(base, str) or not SHA.fullmatch(base):
        raise RunnerError("Invalid authorized base commit")
    if not isinstance(branch, str) or not branch.startswith(("feature/", "agent/", "fix/")):
        raise RunnerError("Expected a temporary feature branch")
    if repo.get("target_ref") == branch or repo.get("release_ref") == branch:
        raise RunnerError("Cannot execute checks on an integration or release branch")
    root = Path(checkout).resolve(strict=True)
    if not root.is_dir():
        raise RunnerError("Checkout must be a directory")
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True) != root:
        raise RunnerError("Checkout path must be the Git repository root")
    remote = _git(root, "remote", "get-url", "origin")
    remotes = (
        f"https://github.com/{identifier}.git", f"https://github.com/{identifier}",
        f"git@github.com:{identifier}.git", f"ssh://git@github.com/{identifier}.git",
    )
    if remote not in remotes:
        raise RunnerError("Git origin does not match authorized repository")
    if _git(root, "symbolic-ref", "--quiet", "--short", "HEAD") != branch:
        raise RunnerError("Checkout is not on the authorized feature branch")
    head = _git(root, "rev-parse", "HEAD")
    if not SHA.fullmatch(head) or head == base:
        raise RunnerError("Feature branch must have a commit beyond the approved base")
    if subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", base, "HEAD"],
        capture_output=True, timeout=15, check=False,
    ).returncode != 0:
        raise RunnerError("Authorized base commit is not an ancestor of checkout HEAD")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise RunnerError("Checkout must be clean before validation")
    return {"identifier": identifier, "branch": branch, "base_commit": base, "head_commit": head}


def _checks(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    verification = envelope.get("verification")
    if not isinstance(verification, dict):
        raise RunnerError("Missing verification bindings")
    required = verification.get("pre_pr_checks")
    commands = verification.get("pre_pr_commands")
    if not isinstance(required, list) or not required or not all(isinstance(x, str) for x in required):
        raise RunnerError("At least one required pre-PR check is needed")
    if not isinstance(commands, list):
        raise RunnerError("Missing pre-PR command bindings")
    if len(set(required)) != len(required):
        raise RunnerError("Duplicate required pre-PR check")
    bound: dict[str, dict[str, Any]] = {}
    for item in commands:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise RunnerError("Invalid command binding")
        identifier = item["id"]
        command = item.get("command")
        if identifier in bound or not isinstance(command, list) or not command:
            raise RunnerError("Duplicate or missing command binding")
        if not all(isinstance(arg, str) and arg and "\x00" not in arg for arg in command):
            raise RunnerError("Commands must be nonempty argument arrays")
        if "\n" in command[0] or "/" in command[0] or "\\" in command[0]:
            raise RunnerError("Command executable must be a bare executable name")
        bound[identifier] = item
    if any(identifier not in bound for identifier in required):
        raise RunnerError("A required pre-PR check lacks an executable command binding")
    return [bound[identifier] for identifier in required]


def validate(envelope: dict[str, Any], checkout: Path, artifact_dir: Path) -> dict[str, Any]:
    root = Path(checkout).resolve(strict=True)
    output = Path(artifact_dir).resolve()
    if output == root or root in output.parents:
        raise RunnerError("Validation artifacts must be outside the checkout")
    repo = _verify_repo(envelope, root)
    commands = _checks(envelope)
    budget = envelope.get("budgets", {})
    if not isinstance(budget, dict):
        raise RunnerError("Missing execution budget")
    max_steps = budget.get("max_steps")
    minutes = budget.get("max_elapsed_minutes")
    if type(max_steps) is not int or max_steps < len(commands):
        raise RunnerError("Step budget cannot cover the required checks")
    if type(minutes) not in (float, int) or minutes <= 0:
        raise RunnerError("Missing positive validation time budget")
    output.mkdir(parents=True, exist_ok=True)
    begin = time.monotonic()
    records: list[dict[str, Any]] = []
    status = "passed"
    for index, item in enumerate(commands):
        remaining = minutes * 60 - (time.monotonic() - begin)
        if remaining <= 0:
            status = "failed"
            break
        name = item["id"]
        command = item["command"]
        start = time.monotonic()
        try:
            result = subprocess.run(
                command, cwd=root, capture_output=True, timeout=remaining,
                check=False, shell=False,
            )
            returncode = result.returncode
            logs = result.stdout + b"\n[STDERR]\n" + result.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            returncode = 124 if isinstance(exc, subprocess.TimeoutExpired) else 127
            logs = f"Execution error: {type(exc).__name__}\n".encode()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        digest = hashlib.sha256(logs).hexdigest()
        log_path = output / f"check-{index + 1}.log"
        log_path.write_bytes(logs)
        record = {
            "name": name, "status": "passed" if returncode == 0 else "failed",
            "exit_code": returncode, "duration_ms": elapsed_ms,
            "evidence": "sha256:" + digest,
        }
        records.append(record)
        if returncode != 0:
            status = "failed"
            break
        try:
            current = _verify_repo(envelope, root)
            if current != repo:
                raise RunnerError("Checkout changed during validation")
        except (RunnerError, OSError, subprocess.TimeoutExpired):
            status = "failed"
            break
    elapsed_ms = int((time.monotonic() - begin) * 1000)
    if len(records) != len(commands):
        status = "failed"
    try:
        if _verify_repo(envelope, root) != repo:
            status = "failed"
    except (RunnerError, OSError, subprocess.TimeoutExpired):
        status = "failed"
    return {
        "schema_version": "local-pre-pr-validation/v1",
        "run_id": envelope.get("run_id"),
        "repository": repo,
        "status": status,
        "verification": records,
        "budget": {"steps": len(records), "elapsed_ms": elapsed_ms, "retries": 0, "cost_usd": None},
        "delivery": {"pr_creation_allowed": False, "merge_allowed": False},
        "limitation": "Local trusted-checkout validation only; not an isolated worker or a PR authorization",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run authorized pre-PR tests in a trusted Git checkout")
    parser.add_argument("--envelope", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        envelope = json.loads(args.envelope.read_text(encoding="utf-8"))
        report = validate(envelope, args.checkout, args.artifact_dir)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
