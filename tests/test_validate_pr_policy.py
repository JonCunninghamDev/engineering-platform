from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-pr-policy.py"
SPEC = importlib.util.spec_from_file_location("validate_pr_policy", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class PullRequestPolicyTests(unittest.TestCase):
    def test_feature_requires_test_change(self) -> None:
        result = module.validate_pr_policy(base="develop", head="agent/issue-21-example", title="Issue #21: example", changed_files=["scripts/example.py"])
        self.assertFalse(result.valid)
        self.assertIn("must include new or updated automated tests", " ".join(result.errors))

    def test_feature_with_test_change_passes(self) -> None:
        result = module.validate_pr_policy(base="develop", head="agent/issue-21-example", title="Issue #21: example", changed_files=["scripts/example.py", "tests/test_example.py"])
        self.assertTrue(result.valid, result.errors)
        self.assertEqual("feature", result.route)

    def test_urgent_fix_uses_same_feature_route_and_requires_tests(self) -> None:
        result = module.validate_pr_policy(base="develop", head="agent/issue-31-urgent-fix", title="Urgent: repair release check", changed_files=["scripts/release.py"])
        self.assertFalse(result.valid)
        self.assertIn("feature PR", " ".join(result.errors))

    def test_release_preparation_metadata_does_not_require_fake_test_change(self) -> None:
        result = module.validate_pr_policy(base="develop", head="release/1.0.0", title="Prepare Release: engineering platform v1.0.0", changed_files=["VERSION", "CHANGELOG.md", "README.md", "docs/releases/v1.0.0.md"])
        self.assertTrue(result.valid, result.errors)
        self.assertEqual("release_preparation", result.route)

    def test_release_preparation_requires_explicit_title(self) -> None:
        result = module.validate_pr_policy(base="develop", head="release/1.0.0", title="Prepare engineering platform v1.0.0", changed_files=["VERSION"])
        self.assertFalse(result.valid)
        self.assertIn("Prepare Release:", " ".join(result.errors))

    def test_release_like_branch_with_invalid_semver_is_ordinary_feature(self) -> None:
        result = module.validate_pr_policy(base="develop", head="release/latest", title="Prepare Release: latest", changed_files=["VERSION"])
        self.assertFalse(result.valid)
        self.assertIn("reserved 'Prepare Release:'", " ".join(result.errors))

    def test_hotfix_direct_to_main_is_rejected_even_with_tests(self) -> None:
        result = module.validate_pr_policy(base="main", head="hotfix/release-check", title="Hotfix: repair release check", changed_files=["scripts/release.py", "tests/test_release.py"])
        self.assertFalse(result.valid)
        self.assertIn("direct-main route rejected", " ".join(result.errors))

    def test_promotion_does_not_require_new_test_change(self) -> None:
        result = module.validate_pr_policy(base="main", head="develop", title="Release: platform v0.2.0", changed_files=["README.md"])
        self.assertTrue(result.valid, result.errors)
        self.assertEqual("promotion", result.route)

    def test_synchronization_does_not_require_new_test_change(self) -> None:
        result = module.validate_pr_policy(base="develop", head="main", title="Sync: main into develop", changed_files=["README.md"])
        self.assertTrue(result.valid, result.errors)
        self.assertEqual("synchronization", result.route)

    def test_direct_main_feature_is_rejected_even_with_tests(self) -> None:
        result = module.validate_pr_policy(base="main", head="agent/issue-21-example", title="Issue #21: example", changed_files=["tests/test_example.py"])
        self.assertFalse(result.valid)
        self.assertIn("direct-main route rejected", " ".join(result.errors))

    def test_cli_reads_changed_files_file(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("scripts/example.py\ntests/test_example.py\n")
            changed = handle.name
        completed = subprocess.run([sys.executable, str(SCRIPT), "--base", "develop", "--head", "agent/issue-21-example", "--title", "Issue #21: example", "--changed-files-file", changed], capture_output=True, text=True, check=False)
        Path(changed).unlink(missing_ok=True)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("route=feature", completed.stdout)


if __name__ == "__main__":
    unittest.main()
