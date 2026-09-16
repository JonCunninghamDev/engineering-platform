#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DECISION_SCHEMA = ROOT / "schemas" / "architecture-decision-v1.schema.json"
REGISTRY_SCHEMA = ROOT / "schemas" / "architecture-rule-registry-v1.schema.json"
DECISIONS_DIR = ROOT / "architecture" / "decisions"
REGISTRY_PATH = ROOT / "standards" / "architecture-rules-v1.json"
POLICY_PATH = ROOT / "engineering-policy.json"


class ArchitectureValidationError(ValueError):
    """Raised when architecture metadata cannot be parsed safely."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArchitectureValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ArchitectureValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArchitectureValidationError(f"top-level JSON must be an object: {path}")
    return value


def _schema_errors(instance: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def _repository_path(root: Path, value: str, label: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or "\\" in value:
        raise ArchitectureValidationError(f"{label} must be a repository-relative POSIX path: {value!r}")
    return root / pure


def format_rule_failure(rule: dict[str, Any], decision: dict[str, Any], detail: str) -> str:
    return (
        f"architecture rule {rule['id']} violated ({decision['id']} {decision['title']}): {detail} "
        f"Rationale: {decision['rationale']} Repair: {rule['repair']}"
    )


def check_two_long_lived_branches(
    root: Path,
    rule: dict[str, Any],
    decision: dict[str, Any],
) -> list[str]:
    policy = _load_json(root / "engineering-policy.json")
    branches = policy.get("branches")
    if not isinstance(branches, dict):
        return [format_rule_failure(rule, decision, "engineering-policy.json has no branches object.")]

    errors: list[str] = []
    release = branches.get("release")
    integration = branches.get("integration")
    temporary = branches.get("temporary_prefixes")
    if release != "main" or integration != "develop":
        errors.append(
            format_rule_failure(
                rule,
                decision,
                f"expected release=main and integration=develop, found release={release!r} integration={integration!r}.",
            )
        )
    if not isinstance(temporary, list) or not temporary:
        errors.append(
            format_rule_failure(
                rule,
                decision,
                "temporary implementation branch prefixes are missing.",
            )
        )
    return errors


BUILT_IN_RULE_CHECKS = {
    "delivery.two-long-lived-branches": check_two_long_lived_branches,
}


def validate(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []

    try:
        decision_schema = _load_json(root / "schemas" / DECISION_SCHEMA.name)
        registry_schema = _load_json(root / "schemas" / REGISTRY_SCHEMA.name)
        registry = _load_json(root / "standards" / REGISTRY_PATH.name)
    except ArchitectureValidationError as exc:
        return [str(exc)]

    registry_schema_errors = _schema_errors(registry, registry_schema)
    errors.extend(f"architecture registry schema: {error}" for error in registry_schema_errors)

    decisions: dict[str, dict[str, Any]] = {}
    decision_dir = root / "architecture" / "decisions"
    for path in sorted(decision_dir.glob("*.json")):
        try:
            decision = _load_json(path)
        except ArchitectureValidationError as exc:
            errors.append(str(exc))
            continue
        for error in _schema_errors(decision, decision_schema):
            errors.append(f"{path.relative_to(root)}: {error}")
        decision_id = decision.get("id")
        if isinstance(decision_id, str):
            if decision_id in decisions:
                errors.append(f"duplicate architecture decision id: {decision_id}")
            else:
                decisions[decision_id] = decision

    if not decisions:
        errors.append("no architecture decisions found")

    rules: dict[str, dict[str, Any]] = {}
    for rule in registry.get("rules", []):
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("id")
        if not isinstance(rule_id, str):
            continue
        if rule_id in rules:
            errors.append(f"duplicate architecture rule id: {rule_id}")
            continue
        rules[rule_id] = rule

        adr_id = rule.get("adr")
        if adr_id not in decisions:
            errors.append(f"architecture rule {rule_id} references unknown ADR: {adr_id}")
            continue

        try:
            validator_path = _repository_path(
                root,
                rule["validator"]["path"],
                f"architecture rule {rule_id} validator",
            )
            if not validator_path.is_file():
                errors.append(
                    format_rule_failure(
                        rule,
                        decisions[adr_id],
                        f"validator path does not exist: {rule['validator']['path']}.",
                    )
                )
            for test_path_text in rule.get("tests", []):
                test_path = _repository_path(
                    root,
                    test_path_text,
                    f"architecture rule {rule_id} test",
                )
                if not test_path.is_file():
                    errors.append(
                        format_rule_failure(
                            rule,
                            decisions[adr_id],
                            f"test path does not exist: {test_path_text}.",
                        )
                    )
        except (ArchitectureValidationError, KeyError, TypeError) as exc:
            errors.append(f"architecture rule {rule_id}: {exc}")

    for decision_id, decision in decisions.items():
        for superseded in decision.get("supersedes", []):
            if superseded not in decisions:
                errors.append(f"{decision_id} supersedes unknown ADR: {superseded}")
        superseded_by = decision.get("superseded_by")
        if superseded_by is not None and superseded_by not in decisions:
            errors.append(f"{decision_id} is superseded by unknown ADR: {superseded_by}")

        enforcement = decision.get("enforcement", {})
        decision_rules = enforcement.get("rules", []) if isinstance(enforcement, dict) else []
        if decision.get("status") == "accepted" and enforcement.get("required"):
            if not decision_rules:
                errors.append(f"{decision_id} is accepted/enforceable but has no executable rule")
        for rule_id in decision_rules:
            rule = rules.get(rule_id)
            if rule is None:
                errors.append(f"{decision_id} references unknown architecture rule: {rule_id}")
            elif rule.get("adr") != decision_id:
                errors.append(
                    f"{decision_id} references rule {rule_id}, but the rule points to {rule.get('adr')}"
                )

    for rule_id, rule in rules.items():
        adr_id = rule.get("adr")
        decision = decisions.get(adr_id)
        if decision is None:
            continue
        if rule_id not in decision.get("enforcement", {}).get("rules", []):
            errors.append(
                f"architecture rule {rule_id} points to {adr_id}, but the ADR does not reference the rule"
            )

        check = BUILT_IN_RULE_CHECKS.get(rule_id)
        if check is not None:
            try:
                errors.extend(check(root, rule, decision))
            except ArchitectureValidationError as exc:
                errors.append(format_rule_failure(rule, decision, str(exc)))

    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    decision_count = len(list((ROOT / "architecture" / "decisions").glob("*.json")))
    registry = _load_json(REGISTRY_PATH)
    print(
        f"architecture validation passed: decisions={decision_count} rules={len(registry['rules'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
