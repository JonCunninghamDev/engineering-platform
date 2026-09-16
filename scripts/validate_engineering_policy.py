#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_SCHEMA = ROOT / "schemas" / "engineering-policy-v1.schema.json"
DEFAULT_PROFILE_SCHEMA = ROOT / "schemas" / "repository-profile-v1.schema.json"
DEFAULT_PROFILES_DIR = ROOT / "profiles"
SEMVER = re.compile(r"^v?([0-9]+)\.([0-9]+)\.([0-9]+)$")


class PolicyValidationError(ValueError):
    """Raised when an engineering policy or referenced profile is invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PolicyValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PolicyValidationError(f"top-level JSON must be an object: {path}")
    return value


def _schema_errors(instance: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def _semver_tuple(value: str, label: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(value)
    if not match:
        raise PolicyValidationError(f"{label} must be semantic versioning: {value!r}")
    return tuple(int(group) for group in match.groups())


def _validate_repository_pattern(value: str, label: str) -> None:
    if "\\" in value:
        raise PolicyValidationError(f"{label} must use POSIX '/' separators: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise PolicyValidationError(f"{label} must be repository-relative without traversal: {value!r}")


def _profile_files(profiles_dir: Path) -> list[Path]:
    files = sorted(profiles_dir.glob("*.json"))
    capabilities = profiles_dir / "capabilities"
    if capabilities.is_dir():
        files.extend(sorted(capabilities.glob("*.json")))
    return files


def _load_profiles(
    profiles_dir: Path,
    profile_schema: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for path in _profile_files(profiles_dir):
        profile = _load_json(path)
        errors = _schema_errors(profile, profile_schema)
        if errors:
            joined = "; ".join(errors)
            raise PolicyValidationError(f"profile schema validation failed for {path}: {joined}")
        profile_id = profile["id"]
        if profile_id in profiles:
            raise PolicyValidationError(f"duplicate profile id: {profile_id}")
        profiles[profile_id] = profile
    if not profiles:
        raise PolicyValidationError(f"no repository profiles found under {profiles_dir}")
    return profiles


def _resolve_profile(
    profile_id: str,
    profiles: dict[str, dict[str, Any]],
    cache: dict[str, dict[str, set[str]]],
    stack: tuple[str, ...] = (),
) -> dict[str, set[str]]:
    if profile_id in cache:
        return cache[profile_id]
    if profile_id in stack:
        cycle = " -> ".join((*stack, profile_id))
        raise PolicyValidationError(f"profile include cycle detected: {cycle}")
    if profile_id not in profiles:
        raise PolicyValidationError(f"unknown repository profile: {profile_id}")

    profile = profiles[profile_id]
    resolved = {
        "toolchain": set(profile["capabilities"]["toolchain"]),
        "tests": set(profile["capabilities"]["tests"]),
    }
    next_stack = (*stack, profile_id)
    for included in profile.get("includes", []):
        child = _resolve_profile(included, profiles, cache, next_stack)
        resolved["toolchain"].update(child["toolchain"])
        resolved["tests"].update(child["tests"])
    cache[profile_id] = resolved
    return resolved


def validate_policy(
    policy_path: Path,
    *,
    policy_schema_path: Path = DEFAULT_POLICY_SCHEMA,
    profile_schema_path: Path = DEFAULT_PROFILE_SCHEMA,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> dict[str, Any]:
    policy = _load_json(policy_path)
    policy_schema = _load_json(policy_schema_path)
    profile_schema = _load_json(profile_schema_path)

    schema_errors = _schema_errors(policy, policy_schema)
    if schema_errors:
        raise PolicyValidationError("policy schema validation failed: " + "; ".join(schema_errors))

    release_branch = policy["branches"]["release"]
    integration_branch = policy["branches"]["integration"]
    if release_branch == integration_branch:
        raise PolicyValidationError("branches.release and branches.integration must be different")

    profiles = _load_profiles(profiles_dir, profile_schema)
    resolved = {"toolchain": set(), "tests": set()}
    cache: dict[str, dict[str, set[str]]] = {}
    referenced_profile_versions: dict[str, str] = {}
    for profile_id in policy["profiles"]:
        capabilities = _resolve_profile(profile_id, profiles, cache)
        resolved["toolchain"].update(capabilities["toolchain"])
        resolved["tests"].update(capabilities["tests"])
        referenced_profile_versions[profile_id] = profiles[profile_id]["version"]

    for category in ("toolchain", "tests"):
        required = set(policy["capabilities"][category])
        missing = sorted(required - resolved[category])
        if missing:
            raise PolicyValidationError(
                f"policy requires {category} capabilities not provided by selected profiles: "
                + ", ".join(missing)
            )

    all_resolved = resolved["toolchain"] | resolved["tests"]
    for stage in policy["validation"]["stages"]:
        if stage["capability"] not in all_resolved:
            raise PolicyValidationError(
                f"validation stage {stage['id']!r} references capability not supplied by profiles: "
                f"{stage['capability']}"
            )

    for index, path_pattern in enumerate(policy["protected_paths"]):
        _validate_repository_pattern(path_pattern, f"protected_paths[{index}]")

    override_ids: set[str] = set()
    for index, override in enumerate(policy.get("overrides", [])):
        override_id = override["id"]
        if override_id in override_ids:
            raise PolicyValidationError(f"duplicate override id: {override_id}")
        override_ids.add(override_id)
        for path_index, path_pattern in enumerate(
            override["restrictions"].get("add_protected_paths", [])
        ):
            _validate_repository_pattern(
                path_pattern,
                f"overrides[{index}].restrictions.add_protected_paths[{path_index}]",
            )

    exception_ids: set[str] = set()
    for exception in policy.get("exceptions", []):
        exception_id = exception["id"]
        if exception_id in exception_ids:
            raise PolicyValidationError(f"duplicate exception id: {exception_id}")
        exception_ids.add(exception_id)

    budgets = policy.get("execution_budgets", {})
    for dimension in budgets.get("required_dimensions", []):
        if dimension not in budgets:
            raise PolicyValidationError(
                f"execution_budgets.required_dimensions requires configured limit: {dimension}"
            )

    pinned = _semver_tuple(policy["platform"]["version"], "platform.version")
    minimum = _semver_tuple(
        policy["compatibility"]["minimum_platform_version"],
        "compatibility.minimum_platform_version",
    )
    if pinned < minimum:
        raise PolicyValidationError(
            "pinned platform version is older than compatibility.minimum_platform_version"
        )

    for profile_id, profile in profiles.items():
        if profile_id not in cache and profile_id not in policy["profiles"]:
            continue
        profile_minimum = _semver_tuple(
            profile["compatibility"]["minimum_platform_version"],
            f"profile {profile_id} minimum_platform_version",
        )
        if pinned < profile_minimum:
            raise PolicyValidationError(
                f"pinned platform version is older than profile {profile_id} minimum platform version"
            )

    return {
        "policy_id": policy["repository"]["policy_id"],
        "platform_version": policy["platform"]["version"],
        "profiles": list(policy["profiles"]),
        "profile_versions": referenced_profile_versions,
        "capabilities": {
            "toolchain": sorted(resolved["toolchain"]),
            "tests": sorted(resolved["tests"]),
        },
        "required_budget_dimensions": list(budgets.get("required_dimensions", [])),
        "override_count": len(policy.get("overrides", [])),
        "exception_count": len(policy.get("exceptions", [])),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate engineering-policy/v1 and profiles")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_POLICY_SCHEMA)
    parser.add_argument("--profile-schema", type=Path, default=DEFAULT_PROFILE_SCHEMA)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        summary = validate_policy(
            args.policy,
            policy_schema_path=args.schema,
            profile_schema_path=args.profile_schema,
            profiles_dir=args.profiles_dir,
        )
    except PolicyValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        "engineering policy valid: "
        f"policy={summary['policy_id']} "
        f"platform={summary['platform_version']} "
        f"profiles={','.join(summary['profiles'])} "
        f"toolchain={len(summary['capabilities']['toolchain'])} "
        f"tests={len(summary['capabilities']['tests'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
