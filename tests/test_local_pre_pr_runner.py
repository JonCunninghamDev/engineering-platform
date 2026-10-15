from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "local_pre_pr_runner.py"
SPEC = importlib.util.spec_from_file_location("local_pre_pr_runner", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return p.stdout.strip()


class LocalPrePRRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "develop")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Unit Test")
        git(self.repo, "remote", "add", "origin", "https://github.com/acme/widget.git")
        (self.repo / "README.md").write_text("initial\n")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-qm", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "switch", "-qc", "feature/demo")
        (self.repo / "README.md").write_text("feature\n")
        git(self.repo, "commit", "-qam", "feature")
        self.head = git(self.repo, "rev-parse", "HEAD")
        self.output = self.root / "evidence"
        self.envelope = {
            "schema_version": "execution-envelope/v1",
            "run_id": "run-local-001",
            "authorization": {"allowed": True},
            "executor": {"adapter": "local-checkout", "provider": "local"},
            "repository": {
                "identifier": "acme/widget", "base_ref": "develop", "base_commit": self.base,
                "target_ref": "develop", "release_ref": "main", "feature_branch": "feature/demo"
            },
            "delivery": {"release_write_allowed": False},
            "verification": {
                "pre_pr_checks": ["test-one"],
                "pre_pr_commands": [
                    {"id": "test-one", "stage": "completion_gate", "capability": "test.python",
                     "command": [Path(sys.executable).name, "-c", "print('OK')"]}
                ],
            },
            "budgets": {"max_steps": 10, "max_elapsed_minutes": 1.0, "max_retries": 0},
        }

    def report(self, env=None):
        return module.validate(env if env is not None else self.envelope, self.repo, self.output)

    def test_runs_real_check_and_records_verifiable_digest(self):
        report = self.report()
        self.assertEqual("passed", report["status"])
        self.assertEqual("passed", report["verification"][0]["status"])
        self.assertEqual(0, report["verification"][0]["exit_code"])
        self.assertTrue((self.output / "check-1.log").exists())
        self.assertTrue(report["verification"][0]["evidence"].startswith("sha256:"))
        self.assertFalse(report["delivery"]["pr_creation_allowed"])
        self.assertFalse(report["delivery"]["merge_allowed"])
        self.assertEqual(self.head, report["repository"]["head_commit"])

    def test_test_failure_returns_negative_evidence(self):
        self.envelope["verification"]["pre_pr_commands"][0]["command"] = [
            Path(sys.executable).name, "-c", "raise SystemExit(6)"
        ]
        report = self.report()
        self.assertEqual("failed", report["status"])
        self.assertEqual(6, report["verification"][0]["exit_code"])

    def test_missing_required_check_binding_fails_closed(self):
        self.envelope["verification"]["pre_pr_checks"].append("nonexistent")
        with self.assertRaisesRegex(module.RunnerError, "lacks an executable command"):
            self.report()

    def test_untrusted_envelope_fails_closed(self):
        for key, value in (
            ("authorization", {"allowed": False}),
            ("executor", {"adapter": "github-actions", "provider": "github"}),
            ("delivery", {"release_write_allowed": True}),
        ):
            with self.subTest(key=key):
                env = deepcopy(self.envelope)
                env[key] = value
                with self.assertRaises(module.RunnerError):
                    self.report(env)

    def test_wrong_repo_or_branch_refused(self):
        env = deepcopy(self.envelope)
        env["repository"]["identifier"] = "someone/other"
        with self.assertRaisesRegex(module.RunnerError, "origin"):
            self.report(env)
        git(self.repo, "switch", "-q", "develop")
        with self.assertRaisesRegex(module.RunnerError, "feature branch"):
            self.report()

    def test_rewritten_history_and_dirty_checkout_refused(self):
        env = deepcopy(self.envelope)
        env["repository"]["base_commit"] = "a" * 40
        with self.assertRaisesRegex(module.RunnerError, "ancestor"):
            self.report(env)
        (self.repo / "new.txt").write_text("untracked")
        with self.assertRaisesRegex(module.RunnerError, "clean"):
            self.report()

    def test_test_that_changes_git_tracked_worktree_fails_even_if_zero_exit(self):
        self.envelope["verification"]["pre_pr_commands"][0]["command"] = [
            Path(sys.executable).name, "-c", "open('README.md','w').write('bad')"
        ]
        report = self.report()
        self.assertEqual("failed", report["status"])
        self.assertEqual(0, report["verification"][0]["exit_code"])

    def test_budget_rejects_more_checks_than_allowed(self):
        self.envelope["budgets"]["max_steps"] = 0
        with self.assertRaisesRegex(module.RunnerError, "Step budget"):
            self.report()

    def test_log_location_must_be_outside_repo(self):
        with self.assertRaisesRegex(module.RunnerError, "outside the checkout"):
            module.validate(self.envelope, self.repo, self.repo / "evidence")

    def test_shell_is_not_used_to_expand_metacharacters(self):
        self.envelope["verification"]["pre_pr_commands"][0]["command"] = [
            Path(sys.executable).name, "-c", "print('hello; echo unsafe')"
        ]
        report = self.report()
        self.assertEqual("passed", report["status"])
        self.assertIn("hello; echo unsafe", (self.output / "check-1.log").read_text())


if __name__ == "__main__":
    unittest.main()
