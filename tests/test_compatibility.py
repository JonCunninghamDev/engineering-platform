from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.validate_compatibility import validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "standards" / "platform-compatibility-v1.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


class PlatformCompatibilityTest(unittest.TestCase):
    def test_repository_manifest_is_valid(self) -> None:
        self.assertEqual(validate_manifest(ROOT, load_manifest()), [])

    def test_version_must_match_version_file(self) -> None:
        manifest = load_manifest()
        manifest["current_platform_version"] = "0.9.9"
        errors = validate_manifest(ROOT, manifest)
        self.assertTrue(any("must match VERSION" in error for error in errors), errors)

    def test_surface_path_must_exist(self) -> None:
        manifest = load_manifest()
        manifest["surfaces"][0]["path"] = "missing/public-contract.md"
        errors = validate_manifest(ROOT, manifest)
        self.assertTrue(any("references missing file" in error for error in errors), errors)

    def test_profile_identifier_must_match_file(self) -> None:
        manifest = load_manifest()
        profile = next(surface for surface in manifest["surfaces"] if surface["id"] == "profile.node")
        profile["identifier"] = "capability.not-node"
        errors = validate_manifest(ROOT, manifest)
        self.assertTrue(any("identifier does not match profile id" in error for error in errors), errors)

    def test_workflow_inputs_are_a_closed_public_inventory(self) -> None:
        manifest = load_manifest()
        workflow = next(surface for surface in manifest["surfaces"] if surface["kind"] == "workflow")
        workflow["public_inputs"].remove("timeout_minutes")
        errors = validate_manifest(ROOT, manifest)
        self.assertTrue(any("unregistered public workflow inputs" in error for error in errors), errors)

    def test_stable_workflow_job_name_must_exist(self) -> None:
        manifest = load_manifest()
        workflow = next(surface for surface in manifest["surfaces"] if surface["kind"] == "workflow")
        workflow["stable_job_names"] = ["Renamed Consumer CI"]
        errors = validate_manifest(ROOT, manifest)
        self.assertTrue(any("stable job name not found" in error for error in errors), errors)

    def test_deprecation_requires_known_replacement_and_later_removal(self) -> None:
        manifest = load_manifest()
        manifest["deprecations"] = [
            {
                "surface_id": "profile.node",
                "replacement_surface_id": "profile.missing",
                "first_deprecated_version": "0.2.0",
                "earliest_removal_version": "0.2.0",
                "migration_document": "docs/compatibility.md",
            }
        ]
        errors = validate_manifest(ROOT, manifest)
        self.assertTrue(any("replacement is unknown" in error for error in errors), errors)
        self.assertTrue(any("must be after first_deprecated_version" in error for error in errors), errors)

    def test_stable_deprecation_removal_waits_for_later_major(self) -> None:
        manifest = load_manifest()
        manifest["deprecations"] = [
            {
                "surface_id": "profile.node",
                "replacement_surface_id": "profile.node-python",
                "first_deprecated_version": "1.3.0",
                "earliest_removal_version": "1.4.0",
                "migration_document": "docs/compatibility.md",
            }
        ]
        errors = validate_manifest(ROOT, manifest)
        self.assertTrue(any("later major version" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
