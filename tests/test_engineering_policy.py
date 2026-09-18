from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_engineering_policy.py"
SCHEMA = ROOT / "schemas" / "engineering-policy-v1.schema.json"
PROFILE_SCHEMA = ROOT / "schemas" / "repository-profile-v1.schema.json"
PROFILES = ROOT / "profiles"
EXAMPLES = PROFILES / "examples"
FIXTURES = Path(__file__).parent / "fixtures" / "engineering-policy"

spec = importlib.util.spec_from_file_location("validate_engineering_policy", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class EngineeringPolicyTests(unittest.TestCase):
    def validate(self, name: str):
        return module.validate_policy(
            EXAMPLES / name,
            policy_schema_path=SCHEMA,
            profile_schema_path=PROFILE_SCHEMA,
            profiles_dir=PROFILES,
        )

    def test_node_python_example_resolves_independent_capabilities(self) -> None:
        summary = self.validate("node-python-policy.json")
        self.assertEqual(["node-python"], summary["profiles"])
        self.assertEqual(["runtime.node", "runtime.python"], summary["capabilities"]["toolchain"])
        self.assertEqual(["test.node", "test.python"], summary["capabilities"]["tests"])

    def test_node_python_blender_composes_blender_independently(self) -> None:
        summary = self.validate("node-python-blender-policy.json")
        self.assertEqual(["node-python-blender"], summary["profiles"])
        self.assertEqual(
            ["runtime.blender", "runtime.node", "runtime.python"],
            summary["capabilities"]["toolchain"],
        )
        self.assertEqual(
            ["test.blender", "test.node", "test.python"],
            summary["capabilities"]["tests"],
        )
        self.assertEqual(1, summary["override_count"])

    def test_profiles_do_not_embed_consumer_identity_or_product_paths(self) -> None:
        paths = sorted(PROFILES.glob("*.json")) + sorted((PROFILES / "capabilities").glob("*.json"))
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("joncunningham", text)
            self.assertNotIn("low-poly", text)
            self.assertNotIn("src/", text)
            self.assertNotIn("visual acceptance", text)
        for name in ("node.json", "python.json", "blender.json"):
            payload = json.loads((PROFILES / "capabilities" / name).read_text(encoding="utf-8"))
            self.assertEqual("capability", payload["kind"])

    def test_invalid_fixtures_fail_closed(self) -> None:
        cases = {
            "invalid-branch-conflict.json": "must be different",
            "invalid-missing-profile.json": "unknown repository profile",
            "invalid-broadening-override.json": "policy schema validation failed",
            "invalid-budget-required-dimension.json": "requires configured limit",
        }
        for name, message in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(module.PolicyValidationError, message):
                    module.validate_policy(
                        FIXTURES / name,
                        policy_schema_path=SCHEMA,
                        profile_schema_path=PROFILE_SCHEMA,
                        profiles_dir=PROFILES,
                    )

    def test_scope_and_capability_cross_checks_fail_closed(self) -> None:
        base = json.loads((EXAMPLES / "node-python-policy.json").read_text(encoding="utf-8"))
        cases = []

        protected = json.loads(json.dumps(base))
        protected["protected_paths"].append("../secrets/**")
        cases.append((protected, "policy schema validation failed"))

        missing_capability = json.loads(json.dumps(base))
        missing_capability["capabilities"]["tests"].append("test.blender")
        cases.append((missing_capability, "not provided by selected profiles"))

        invalid_stage = json.loads(json.dumps(base))
        invalid_stage["validation"]["stages"].append(
            {"id": "blender", "stage": "completion_gate", "capability": "test.blender", "required": True}
        )
        cases.append((invalid_stage, "not supplied by profiles"))

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            for index, (policy, message) in enumerate(cases):
                with self.subTest(index=index):
                    path = directory_path / f"invalid-{index}.json"
                    path.write_text(json.dumps(policy), encoding="utf-8")
                    with self.assertRaisesRegex(module.PolicyValidationError, message):
                        module.validate_policy(
                            path,
                            policy_schema_path=SCHEMA,
                            profile_schema_path=PROFILE_SCHEMA,
                            profiles_dir=PROFILES,
                        )

    def test_validation_stage_can_bind_repository_owned_command(self) -> None:
        policy = json.loads((EXAMPLES / "node-python-policy.json").read_text(encoding="utf-8"))
        policy["validation"]["stages"][0]["command"] = ["python", "-m", "unittest"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            summary = module.validate_policy(
                path,
                policy_schema_path=SCHEMA,
                profile_schema_path=PROFILE_SCHEMA,
                profiles_dir=PROFILES,
            )
        self.assertEqual("v1.0.0", summary["platform_version"])

    def test_validation_command_must_be_non_empty_when_present(self) -> None:
        policy = json.loads((EXAMPLES / "node-python-policy.json").read_text(encoding="utf-8"))
        policy["validation"]["stages"][0]["command"] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(module.PolicyValidationError, "policy schema validation failed"):
                module.validate_policy(
                    path,
                    policy_schema_path=SCHEMA,
                    profile_schema_path=PROFILE_SCHEMA,
                    profiles_dir=PROFILES,
                )

    def test_schema_rejects_permission_broadening(self) -> None:
        policy = json.loads((EXAMPLES / "node-python-policy.json").read_text(encoding="utf-8"))
        policy["permissions"]["consequential_write"]["tier"] = "autonomous"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(module.PolicyValidationError, "policy schema validation failed"):
                module.validate_policy(
                    path,
                    policy_schema_path=SCHEMA,
                    profile_schema_path=PROFILE_SCHEMA,
                    profiles_dir=PROFILES,
                )

    def test_exceptions_are_auditable_not_implicit_authority(self) -> None:
        policy = json.loads((EXAMPLES / "node-python-policy.json").read_text(encoding="utf-8"))
        policy["exceptions"] = [
            {
                "id": "temporary-branch-migration",
                "target": "branches.integration",
                "reason": "Temporary migration requires explicit local approval.",
                "approval_reference": "https://example.invalid/issues/123",
                "expires_on": "2026-12-31",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            summary = module.validate_policy(
                path,
                policy_schema_path=SCHEMA,
                profile_schema_path=PROFILE_SCHEMA,
                profiles_dir=PROFILES,
            )
        self.assertEqual(1, summary["exception_count"])

    def test_cli_validates_example(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--policy",
                str(EXAMPLES / "node-python-policy.json"),
                "--schema",
                str(SCHEMA),
                "--profile-schema",
                str(PROFILE_SCHEMA),
                "--profiles-dir",
                str(PROFILES),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("engineering policy valid", completed.stdout)


if __name__ == "__main__":
    unittest.main()
