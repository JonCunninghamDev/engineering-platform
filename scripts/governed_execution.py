#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import PurePosixPath, Path
from typing import Any

REQUEST_SCHEMA = "governed-execution-request/v1"
ENVELOPE_SCHEMA = "execution-envelope/v1"
WORKER_RESULT_SCHEMA = "worker-execution-result/v1"
WORKER_VERIFICATION_SCHEMA = "worker-verification/v1"
DELIVERY_GATE_SCHEMA = "delivery-gate/v1"
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class GovernedExecutionError(ValueError):
    """Raised when governed consumer execution cannot be authorized safely."""


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GovernedExecutionError(f"{label} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise GovernedExecutionError(f"{label} must be a list")
    rows: list[str] = []
    for index, item in enumerate(value):
        rows.append(_string(item, f"{label}[{index}]"))
    if not allow_empty and not rows:
        raise GovernedExecutionError(f"{label} must not be empty")
    if len(rows) != len(set(rows)):
        raise GovernedExecutionError(f"{label} must not contain duplicates")
    return rows


def _commit_sha(value: Any, label: str) -> str:
    sha = _string(value, label)
    if not COMMIT_SHA.fullmatch(sha):
        raise GovernedExecutionError(f"{label} must be a 40-character lowercase Git commit SHA")
    return sha


def _non_negative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise GovernedExecutionError(f"{label} must be a non-negative integer")
    return value


def _non_negative_number(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise GovernedExecutionError(f"{label} must be a non-negative number")
    return float(value)


def _safe_repo_path(value: str, label: str) -> str:
    path = _string(value, label)
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or "\\" in path or any(part in {"", ".", ".."} for part in parsed.parts):
        raise GovernedExecutionError(f"{label} must be a safe repository-relative path")
    return path


def _path_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


def _allowed(path: str, patterns: list[str]) -> bool:
    return any(_path_matches(path, pattern) for pattern in patterns)


def _validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema_version") != "engineering-policy/v1":
        raise GovernedExecutionError("policy schema_version must be engineering-policy/v1")
    branches = policy.get("branches")
    review = policy.get("review")
    permissions = policy.get("permissions")
    delivery = policy.get("delivery")
    if not isinstance(branches, dict):
        raise GovernedExecutionError("policy.branches must be an object")
    for key in ("release", "integration", "temporary_prefixes"):
        if key not in branches:
            raise GovernedExecutionError(f"policy.branches.{key} is required")
    _string(branches["release"], "policy.branches.release")
    _string(branches["integration"], "policy.branches.integration")
    _string_list(branches["temporary_prefixes"], "policy.branches.temporary_prefixes", allow_empty=False)
    if not isinstance(review, dict):
        raise GovernedExecutionError("policy.review must be an object")
    _string_list(review.get("required_checks"), "policy.review.required_checks", allow_empty=False)
    _string_list(review.get("human_approval_for", []), "policy.review.human_approval_for")
    if not isinstance(permissions, dict):
        raise GovernedExecutionError("policy.permissions must be an object")
    for key in ("read", "bounded_write", "consequential_write"):
        rule = permissions.get(key)
        if not isinstance(rule, dict):
            raise GovernedExecutionError(f"policy.permissions.{key} must be an object")
        _string_list(rule.get("actions"), f"policy.permissions.{key}.actions")
    if not isinstance(delivery, dict):
        raise GovernedExecutionError("policy.delivery must be an object")
    if delivery.get("implementation_target") != "integration":
        raise GovernedExecutionError("governed execution requires integration implementation target")
    if delivery.get("direct_release_writes") is not False:
        raise GovernedExecutionError("governed execution requires direct_release_writes=false")
    _string_list(policy.get("protected_paths", []), "policy.protected_paths")


def _request_parts(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if request.get("schema_version") != REQUEST_SCHEMA:
        raise GovernedExecutionError(f"request schema_version must be {REQUEST_SCHEMA}")
    repository = request.get("repository")
    task = request.get("task")
    worker = request.get("worker")
    scope = request.get("scope")
    for label, value in (
        ("request.repository", repository),
        ("request.task", task),
        ("request.worker", worker),
        ("request.scope", scope),
    ):
        if not isinstance(value, dict):
            raise GovernedExecutionError(f"{label} must be an object")
    return repository, task, worker, scope


def authorize_execution(policy: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    _validate_policy(policy)
    repository, task, worker, scope = _request_parts(request)

    run_id = _string(request.get("run_id"), "request.run_id")
    repository_id = _string(repository.get("identifier"), "request.repository.identifier")
    base_ref = _string(repository.get("base_ref"), "request.repository.base_ref")
    base_commit = _commit_sha(repository.get("base_commit"), "request.repository.base_commit")
    target_ref = _string(repository.get("target_ref"), "request.repository.target_ref")
    feature_branch = _string(repository.get("feature_branch"), "request.repository.feature_branch")
    issue = _string(task.get("issue"), "request.task.issue")
    goal = _string(task.get("goal"), "request.task.goal")
    task_class = _string(task.get("task_class"), "request.task.task_class")
    adapter = _string(worker.get("adapter"), "request.worker.adapter")
    provider = _string(worker.get("provider"), "request.worker.provider")
    requested_actions = _string_list(
        request.get("requested_actions"), "request.requested_actions", allow_empty=False
    )
    allowed_paths = [
        _safe_repo_path(value, f"request.scope.allowed_paths[{index}]")
        for index, value in enumerate(_string_list(scope.get("allowed_paths"), "request.scope.allowed_paths", allow_empty=False))
    ]
    request_protected = [
        _safe_repo_path(value, f"request.scope.protected_paths[{index}]")
        for index, value in enumerate(_string_list(scope.get("protected_paths", []), "request.scope.protected_paths"))
    ]
    requested_pre_pr_checks = _string_list(
        request.get("verification", {}).get("pre_pr_checks", []),
        "request.verification.pre_pr_checks",
    ) if isinstance(request.get("verification", {}), dict) else []
    validation = policy.get("validation", {})
    raw_stages = validation.get("stages", []) if isinstance(validation, dict) else []
    required_policy_checks: list[str] = []
    for index, stage in enumerate(raw_stages):
        if not isinstance(stage, dict):
            raise GovernedExecutionError(f"policy.validation.stages[{index}] must be an object")
        if stage.get("required") is True:
            required_policy_checks.append(
                _string(stage.get("id"), f"policy.validation.stages[{index}].id")
            )
    pre_pr_checks = list(dict.fromkeys(required_policy_checks + requested_pre_pr_checks))
    requested_human_gates = _string_list(
        request.get("human_gates", []), "request.human_gates"
    )
    change_classes = _string_list(
        request.get("change_classes", []), "request.change_classes"
    )

    branches = policy["branches"]
    integration = branches["integration"]
    release = branches["release"]
    reasons: list[str] = []
    if base_ref != integration:
        reasons.append(f"base_ref must be integration branch {integration}")
    if target_ref != integration:
        reasons.append(f"target_ref must be integration branch {integration}")
    if feature_branch in {integration, release}:
        reasons.append("feature branch must not be a long-lived branch")
    if not any(feature_branch.startswith(prefix) for prefix in branches["temporary_prefixes"]):
        reasons.append("feature branch does not use an allowed temporary prefix")

    read_actions = set(policy["permissions"]["read"]["actions"])
    bounded_actions = set(policy["permissions"]["bounded_write"]["actions"])
    consequential_actions = set(policy["permissions"]["consequential_write"]["actions"])
    requested_set = set(requested_actions)
    ordinary_allowed = read_actions | bounded_actions
    forbidden = sorted(requested_set - ordinary_allowed)
    if forbidden:
        if requested_set & consequential_actions:
            reasons.append("request contains consequential actions that require a separate approval gate")
        reasons.append("requested actions exceed autonomous/bounded policy authority: " + ", ".join(forbidden))

    policy_protected = _string_list(policy.get("protected_paths", []), "policy.protected_paths")
    effective_protected = list(dict.fromkeys(policy_protected + request_protected))
    required_ci_checks = _string_list(policy["review"]["required_checks"], "policy.review.required_checks", allow_empty=False)
    policy_gate_classes = _string_list(
        policy["review"].get("human_approval_for", []),
        "policy.review.human_approval_for",
    )
    applicable_policy_gates = [
        gate for gate in policy_gate_classes if gate in set(change_classes)
    ]
    human_gates = list(dict.fromkeys(applicable_policy_gates + requested_human_gates))

    authorization = {
        "allowed": not reasons,
        "reasons": reasons,
        "authority_class": "bounded_write",
        "requested_actions": requested_actions,
        "authorized_actions": sorted(requested_set & ordinary_allowed),
        "consequential_actions": sorted(requested_set & consequential_actions),
    }

    return {
        "schema_version": ENVELOPE_SCHEMA,
        "run_id": run_id,
        "repository": {
            "identifier": repository_id,
            "base_ref": base_ref,
            "base_commit": base_commit,
            "target_ref": target_ref,
            "release_ref": release,
            "feature_branch": feature_branch,
        },
        "task": {
            "issue": issue,
            "goal": goal,
            "task_class": task_class,
        },
        "worker": {
            "adapter": adapter,
            "provider": provider,
        },
        "authorization": authorization,
        "scope": {
            "allowed_paths": allowed_paths,
            "protected_paths": effective_protected,
        },
        "verification": {
            "pre_pr_checks": pre_pr_checks,
            "required_ci_checks": required_ci_checks,
        },
        "human_gates": human_gates,
        "budgets": policy.get("execution_budgets", {}),
        "delivery": {
            "pr_required": policy["review"].get("pull_requests_required") is True,
            "pr_creation_allowed": False,
            "merge_allowed": False,
            "release_write_allowed": False,
        },
        "ledger": {
            "schema_version": "engineering-run/v1",
            "run_id": run_id,
        },
    }


def _require_authorized(envelope: dict[str, Any]) -> None:
    if envelope.get("schema_version") != ENVELOPE_SCHEMA:
        raise GovernedExecutionError(f"envelope schema_version must be {ENVELOPE_SCHEMA}")
    authorization = envelope.get("authorization")
    if not isinstance(authorization, dict) or authorization.get("allowed") is not True:
        raise GovernedExecutionError("execution envelope is not authorized")


def verify_worker_result(envelope: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    _require_authorized(envelope)
    if result.get("schema_version") != WORKER_RESULT_SCHEMA:
        raise GovernedExecutionError(f"worker result schema_version must be {WORKER_RESULT_SCHEMA}")
    if result.get("run_id") != envelope.get("run_id"):
        raise GovernedExecutionError("worker result run_id does not match execution envelope")

    executor = result.get("executor")
    repository = result.get("repository")
    budget = result.get("budget")
    security = result.get("security")
    for label, value in (
        ("worker_result.executor", executor),
        ("worker_result.repository", repository),
        ("worker_result.budget", budget),
        ("worker_result.security", security),
    ):
        if not isinstance(value, dict):
            raise GovernedExecutionError(f"{label} must be an object")

    adapter = _string(executor.get("adapter"), "worker_result.executor.adapter")
    provider = _string(executor.get("provider"), "worker_result.executor.provider")
    execution_id = _string(executor.get("execution_id"), "worker_result.executor.execution_id")
    violations: list[str] = []
    if adapter != envelope["worker"]["adapter"]:
        violations.append("executor adapter does not match authorized worker adapter")
    if provider != envelope["worker"]["provider"]:
        violations.append("executor provider does not match authorized worker provider")

    repository_id = _string(repository.get("identifier"), "worker_result.repository.identifier")
    base_commit = _commit_sha(repository.get("base_commit"), "worker_result.repository.base_commit")
    branch = _string(repository.get("branch"), "worker_result.repository.branch")
    head_commit = _commit_sha(repository.get("head_commit"), "worker_result.repository.head_commit")
    commits = [
        _commit_sha(value, f"worker_result.repository.commits[{index}]")
        for index, value in enumerate(
            _string_list(repository.get("commits"), "worker_result.repository.commits", allow_empty=False)
        )
    ]
    if repository_id != envelope["repository"]["identifier"]:
        violations.append("worker result repository does not match execution envelope")
    if base_commit != envelope["repository"]["base_commit"]:
        violations.append("worker result base commit does not match authorized base commit")
    if branch != envelope["repository"]["feature_branch"]:
        violations.append("worker result branch does not match authorized feature branch")
    if commits[-1] != head_commit:
        violations.append("worker result head_commit must equal the final reported commit")
    if head_commit == base_commit:
        violations.append("worker result must advance beyond the authorized base commit")

    changed_paths = result.get("changed_paths")
    if not isinstance(changed_paths, list) or not changed_paths:
        raise GovernedExecutionError("worker result changed_paths must be a non-empty list")
    normalized_paths = [
        _safe_repo_path(value, f"worker_result.changed_paths[{index}]")
        for index, value in enumerate(changed_paths)
    ]
    if len(normalized_paths) != len(set(normalized_paths)):
        raise GovernedExecutionError("worker result changed_paths must not contain duplicates")
    allowed_patterns = envelope["scope"]["allowed_paths"]
    protected_patterns = envelope["scope"]["protected_paths"]
    for path in normalized_paths:
        if not _allowed(path, allowed_patterns):
            violations.append(f"outside allowed scope: {path}")
        if _allowed(path, protected_patterns):
            violations.append(f"protected path: {path}")

    actions = _string_list(result.get("actions", []), "worker_result.actions")
    authorized_actions = set(envelope["authorization"]["authorized_actions"])
    for action in actions:
        if action not in authorized_actions:
            violations.append(f"unauthorized action: {action}")

    if result.get("direct_shared_branch_writes", 0) != 0:
        violations.append("worker recorded direct writes to a shared branch")

    attempted = _string_list(
        security.get("consequential_actions_attempted", []),
        "worker_result.security.consequential_actions_attempted",
    )
    blocked = _string_list(
        security.get("consequential_actions_blocked", []),
        "worker_result.security.consequential_actions_blocked",
    )
    unblocked = sorted(set(attempted) - set(blocked))
    if unblocked:
        violations.append(
            "consequential actions were attempted without block evidence: " + ", ".join(unblocked)
        )

    steps = _non_negative_int(budget.get("steps"), "worker_result.budget.steps")
    elapsed_ms = _non_negative_int(budget.get("elapsed_ms"), "worker_result.budget.elapsed_ms")
    retries = _non_negative_int(budget.get("retries"), "worker_result.budget.retries")
    cost_usd_raw = budget.get("cost_usd")
    cost_usd = (
        None
        if cost_usd_raw is None
        else _non_negative_number(cost_usd_raw, "worker_result.budget.cost_usd")
    )
    configured = envelope.get("budgets", {})
    if isinstance(configured.get("max_steps"), int) and steps > configured["max_steps"]:
        violations.append("worker exceeded max_steps budget")
    max_elapsed = configured.get("max_elapsed_minutes")
    if isinstance(max_elapsed, (int, float)) and elapsed_ms > float(max_elapsed) * 60_000:
        violations.append("worker exceeded max_elapsed_minutes budget")
    if isinstance(configured.get("max_retries"), int) and retries > configured["max_retries"]:
        violations.append("worker exceeded max_retries budget")
    max_cost = configured.get("max_cost_usd")
    if isinstance(max_cost, (int, float)):
        if cost_usd is None:
            violations.append("worker omitted cost evidence required by max_cost_usd budget")
        elif cost_usd > float(max_cost):
            violations.append("worker exceeded max_cost_usd budget")

    checks = result.get("verification", [])
    if not isinstance(checks, list):
        raise GovernedExecutionError("worker_result.verification must be a list")
    check_map: dict[str, str] = {}
    evidence_map: dict[str, str] = {}
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise GovernedExecutionError(f"worker_result.verification[{index}] must be an object")
        name = _string(check.get("name"), f"worker_result.verification[{index}].name")
        status = _string(check.get("status"), f"worker_result.verification[{index}].status")
        if status not in {"passed", "failed", "unavailable"}:
            raise GovernedExecutionError(f"worker_result.verification[{index}].status is unsupported")
        if name in check_map:
            raise GovernedExecutionError(f"duplicate worker verification check: {name}")
        duration_ms = _non_negative_int(
            check.get("duration_ms"), f"worker_result.verification[{index}].duration_ms"
        )
        exit_code = check.get("exit_code")
        evidence = check.get("evidence")
        if status == "passed":
            if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code != 0:
                raise GovernedExecutionError(
                    f"worker_result.verification[{index}].exit_code must be 0 for passed checks"
                )
            evidence_map[name] = _string(
                evidence,
                f"worker_result.verification[{index}].evidence",
            )
        elif status == "failed":
            if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code == 0:
                raise GovernedExecutionError(
                    f"worker_result.verification[{index}].exit_code must be non-zero for failed checks"
                )
            if evidence is not None:
                evidence_map[name] = _string(
                    evidence,
                    f"worker_result.verification[{index}].evidence",
                )
        else:
            if exit_code is not None:
                raise GovernedExecutionError(
                    f"worker_result.verification[{index}].exit_code must be null for unavailable checks"
                )
            if evidence is not None:
                evidence_map[name] = _string(
                    evidence,
                    f"worker_result.verification[{index}].evidence",
                )
        check_map[name] = status

    missing_pre_pr = [
        name for name in envelope["verification"]["pre_pr_checks"]
        if check_map.get(name) != "passed"
    ]
    if missing_pre_pr:
        violations.append("required pre-PR verification not passed: " + ", ".join(missing_pre_pr))

    passed = not violations
    return {
        "schema_version": WORKER_VERIFICATION_SCHEMA,
        "run_id": envelope["run_id"],
        "status": "verified" if passed else "rejected",
        "executor": {
            "adapter": adapter,
            "provider": provider,
            "execution_id": execution_id,
        },
        "repository": {
            "identifier": repository_id,
            "base_commit": base_commit,
            "branch": branch,
            "head_commit": head_commit,
            "commits": commits,
        },
        "scope": {
            "changed_paths": normalized_paths,
            "violations": violations,
        },
        "verification": {
            "reported": checks,
            "required_pre_pr": envelope["verification"]["pre_pr_checks"],
            "evidence": evidence_map,
        },
        "budget": {
            "steps": steps,
            "elapsed_ms": elapsed_ms,
            "retries": retries,
            "cost_usd": cost_usd,
        },
        "security": {
            "consequential_actions_attempted": attempted,
            "consequential_actions_blocked": blocked,
        },
        "delivery": {
            "pr_creation_allowed": passed,
            "merge_allowed": False,
        },
    }

def evaluate_delivery_gate(
    envelope: dict[str, Any],
    worker_verification: dict[str, Any],
    *,
    ci_checks: list[dict[str, str]],
    approvals: list[str],
) -> dict[str, Any]:
    _require_authorized(envelope)
    if worker_verification.get("schema_version") != WORKER_VERIFICATION_SCHEMA:
        raise GovernedExecutionError(f"worker verification schema_version must be {WORKER_VERIFICATION_SCHEMA}")
    if worker_verification.get("run_id") != envelope.get("run_id"):
        raise GovernedExecutionError("worker verification run_id does not match execution envelope")
    if worker_verification.get("status") != "verified":
        return {
            "schema_version": DELIVERY_GATE_SCHEMA,
            "run_id": envelope["run_id"],
            "merge_allowed": False,
            "pending_ci_checks": envelope["verification"]["required_ci_checks"],
            "pending_human_gates": envelope["human_gates"],
            "reasons": ["worker result is not verified"],
        }

    ci_map: dict[str, str] = {}
    for index, check in enumerate(ci_checks):
        if not isinstance(check, dict):
            raise GovernedExecutionError(f"ci_checks[{index}] must be an object")
        name = _string(check.get("name"), f"ci_checks[{index}].name")
        status = _string(check.get("status"), f"ci_checks[{index}].status")
        if status not in {"passed", "failed", "pending"}:
            raise GovernedExecutionError(f"ci_checks[{index}].status is unsupported")
        ci_map[name] = status

    pending_ci = [
        name for name in envelope["verification"]["required_ci_checks"]
        if ci_map.get(name) != "passed"
    ]
    approval_set = set(_string_list(approvals, "approvals"))
    pending_human = [gate for gate in envelope["human_gates"] if gate not in approval_set]
    reasons: list[str] = []
    if pending_ci:
        reasons.append("required CI checks are not all passed")
    if pending_human:
        reasons.append("required human gates are not all approved")

    return {
        "schema_version": DELIVERY_GATE_SCHEMA,
        "run_id": envelope["run_id"],
        "merge_allowed": not reasons,
        "pending_ci_checks": pending_ci,
        "pending_human_gates": pending_human,
        "reasons": reasons,
    }


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernedExecutionError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GovernedExecutionError(f"top-level JSON must be an object: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authorize a bounded consumer Engineering Run")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        envelope = authorize_execution(_load(args.policy), _load(args.request))
    except GovernedExecutionError as exc:
        print(f"ERROR: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not envelope["authorization"]["allowed"]:
        print("Execution NOT AUTHORIZED")
        for reason in envelope["authorization"]["reasons"]:
            print(f"- {reason}")
        return 3
    print(f"Execution authorized: {envelope['run_id']} -> {envelope['repository']['feature_branch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
