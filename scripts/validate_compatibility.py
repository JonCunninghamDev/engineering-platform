#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
WORKFLOW_INPUT_RE = re.compile(r"^      ([A-Za-z_][A-Za-z0-9_]*):\s*$", re.MULTILINE)


class CompatibilityError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise CompatibilityError(f"{path}: expected a JSON object")
    return value


def parse_semver(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value)
    if not match:
        raise CompatibilityError(f"invalid semantic version: {value}")
    return tuple(int(part) for part in match.groups())


def workflow_inputs(text: str) -> set[str]:
    marker = "    inputs:\n"
    if marker not in text:
        return set()
    block = text.split(marker, 1)[1]
    for boundary in ("\npermissions:", "\njobs:"):
        if boundary in block:
            block = block.split(boundary, 1)[0]
    return set(WORKFLOW_INPUT_RE.findall(block))


def validate_manifest(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_path = root / "schemas/platform-compatibility-v1.schema.json"
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"schema:{location}: {error.message}")

    if errors:
        return errors

    current_version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if manifest["current_platform_version"] != current_version:
        errors.append(
            "current_platform_version must match VERSION "
            f"({manifest['current_platform_version']} != {current_version})"
        )

    surfaces = manifest["surfaces"]
    surface_by_id: dict[str, dict[str, Any]] = {}
    for surface in surfaces:
        surface_id = surface["id"]
        if surface_id in surface_by_id:
            errors.append(f"duplicate compatibility surface id: {surface_id}")
            continue
        surface_by_id[surface_id] = surface

        path = root / surface["path"]
        if not path.is_file():
            errors.append(f"surface {surface_id} references missing file: {surface['path']}")
            continue

        if surface["kind"] == "profile":
            profile = load_json(path)
            if profile.get("id") != surface.get("identifier"):
                errors.append(
                    f"surface {surface_id} identifier does not match profile id "
                    f"({surface.get('identifier')} != {profile.get('id')})"
                )
            if profile.get("version") != surface["interface_version"]:
                errors.append(
                    f"surface {surface_id} interface_version does not match profile version "
                    f"({surface['interface_version']} != {profile.get('version')})"
                )
            minimum = profile.get("compatibility", {}).get("minimum_platform_version")
            if isinstance(minimum, str) and parse_semver(minimum) > parse_semver(current_version):
                errors.append(
                    f"surface {surface_id} requires platform {minimum}, newer than VERSION {current_version}"
                )

        if surface["kind"] == "workflow":
            text = path.read_text(encoding="utf-8")
            actual_inputs = workflow_inputs(text)
            declared_inputs = set(surface.get("public_inputs", []))
            missing_inputs = sorted(declared_inputs - actual_inputs)
            unregistered_inputs = sorted(actual_inputs - declared_inputs)
            if missing_inputs:
                errors.append(
                    f"surface {surface_id} declares missing workflow inputs: {', '.join(missing_inputs)}"
                )
            if unregistered_inputs:
                errors.append(
                    f"surface {surface_id} has unregistered public workflow inputs: {', '.join(unregistered_inputs)}"
                )
            for job_name in surface.get("stable_job_names", []):
                if f"name: {job_name}" not in text:
                    errors.append(
                        f"surface {surface_id} stable job name not found in workflow: {job_name}"
                    )

    for deprecation in manifest["deprecations"]:
        surface_id = deprecation["surface_id"]
        replacement_id = deprecation["replacement_surface_id"]
        if surface_id not in surface_by_id:
            errors.append(f"deprecation references unknown surface: {surface_id}")
        if replacement_id not in surface_by_id:
            errors.append(f"deprecation replacement is unknown: {replacement_id}")
        first = parse_semver(deprecation["first_deprecated_version"])
        removal = parse_semver(deprecation["earliest_removal_version"])
        if removal <= first:
            errors.append(
                f"deprecation {surface_id} earliest_removal_version must be after first_deprecated_version"
            )
        if first[0] >= 1 and removal[0] <= first[0]:
            errors.append(
                f"stable deprecation {surface_id} may not be removed before a later major version"
            )
        migration_path = root / deprecation["migration_document"]
        if not migration_path.is_file():
            errors.append(
                f"deprecation {surface_id} migration document is missing: {deprecation['migration_document']}"
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Engineering Platform compatibility contracts.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("standards/platform-compatibility-v1.json"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest

    try:
        manifest = load_json(manifest_path)
        errors = validate_manifest(root, manifest)
    except (OSError, json.JSONDecodeError, CompatibilityError) as exc:
        print(f"compatibility validation failed: {exc}", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "validated platform compatibility: "
        f"{len(manifest['surfaces'])} public surfaces, {len(manifest['deprecations'])} deprecations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
