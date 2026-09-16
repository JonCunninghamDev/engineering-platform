from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-protected-paths.py"
SPEC = importlib.util.spec_from_file_location("validate_protected_paths", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(module)


class ProtectedPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "protected_paths": [
                ".github/workflows/**",
                "engineering-policy.json",
                "schemas/**",
            ]
        }

    def test_unprotected_feature_change_passes_without_authorization(self) -> None:
        evidence = module.validate(
            policy=self.policy,
            changed_files=["scripts/example.py", "tests/test_example.py"],
            head="agent/issue-42-example",
            issue_body="",
        )
        self.assertEqual("passed", evidence["status"])
        self.assertEqual([], evidence["protected_files"])

    def test_protected_change_requires_issue_authorization(self) -> None:
        evidence = module.validate(
            policy=self.policy,
            changed_files=[".github/workflows/ci.yml"],
            head="agent/issue-42-example",
            issue_body="ordinary feature issue",
        )
        self.assertEqual("failed", evidence["status"])
        self.assertEqual([".github/workflows/ci.yml"], evidence["protected_files"])
        self.assertIn("does not explicitly authorize", " ".join(evidence["errors"]))

    def test_protected_change_passes_with_explicit_issue_marker(self) -> None:
        evidence = module.validate(
            policy=self.policy,
            changed_files=["engineering-policy.json", "schemas/example.json"],
            head="feature/issue-42-policy-work",
            issue_body="## Policy change authorization\nPolicy change authorization: approved\n",
        )
        self.assertEqual("passed", evidence["status"])
        self.assertEqual(42, evidence["issue_number"])
        self.assertTrue(evidence["authorization_marker_present"])

    def test_develop_to_main_release_route_allows_protected_changes(self) -> None:
        evidence = module.validate(
            policy=self.policy,
            changed_files=["engineering-policy.json", ".github/workflows/ci.yml"],
            head="develop",
            base="main",
            issue_body="",
        )
        self.assertEqual("passed", evidence["status"])
        self.assertTrue(evidence["release_route"])
        self.assertIsNone(evidence["issue_number"])

    def test_develop_to_non_main_does_not_get_release_exception(self) -> None:
        evidence = module.validate(
            policy=self.policy,
            changed_files=["schemas/example.json"],
            head="develop",
            base="staging",
            issue_body="",
        )
        self.assertEqual("failed", evidence["status"])
        self.assertFalse(evidence["release_route"])

    def test_other_branch_to_main_does_not_get_release_exception(self) -> None:
        evidence = module.validate(
            policy=self.policy,
            changed_files=["schemas/example.json"],
            head="release/candidate",
            base="main",
            issue_body="Policy change authorization: approved",
        )
        self.assertEqual("failed", evidence["status"])
        self.assertFalse(evidence["release_route"])

    def test_protected_change_without_issue_branch_fails_closed(self) -> None:
        evidence = module.validate(
            policy=self.policy,
            changed_files=["schemas/example.json"],
            head="feature/policy-work",
            issue_body="Policy change authorization: approved",
        )
        self.assertEqual("failed", evidence["status"])
        self.assertIsNone(evidence["issue_number"])
        self.assertIn("neither the governed develop-to-main release route", " ".join(evidence["errors"]))

    def test_glob_matching_is_repository_relative(self) -> None:
        matches = module.protected_matches(
            ["./.github/workflows/ci.yml", "docs/example.md"],
            self.policy["protected_paths"],
        )
        self.assertEqual([".github/workflows/ci.yml"], matches)


if __name__ == "__main__":
    unittest.main()
