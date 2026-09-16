from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_agent_command.py"
SPEC = importlib.util.spec_from_file_location("validate_agent_command", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(module)


class AgentCommandPolicyTests(unittest.TestCase):
    def test_normal_commit_passes(self) -> None:
        evidence = module.validate_command(["git", "commit", "-m", "Issue #23"])
        self.assertEqual("passed", evidence["status"])

    def test_no_verify_is_rejected(self) -> None:
        evidence = module.validate_command(["git", "commit", "--no-verify", "-m", "skip"])
        self.assertEqual("failed", evidence["status"])
        self.assertIn("hook bypass", " ".join(evidence["errors"]))

    def test_short_no_verify_is_rejected(self) -> None:
        evidence = module.validate_command("git commit -n -m skip")
        self.assertEqual("failed", evidence["status"])

    def test_disabling_hooks_path_for_commit_is_rejected(self) -> None:
        evidence = module.validate_command(
            ["git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "skip"]
        )
        self.assertEqual("failed", evidence["status"])
        self.assertIn("core.hooksPath", " ".join(evidence["errors"]))

    def test_agent_cannot_reconfigure_hooks_path(self) -> None:
        evidence = module.validate_command(["git", "config", "core.hooksPath", "/dev/null"])
        self.assertEqual("failed", evidence["status"])

    def test_hook_bypass_environment_is_rejected(self) -> None:
        evidence = module.validate_command(["HUSKY=0", "git", "commit", "-m", "skip"])
        self.assertEqual("failed", evidence["status"])


if __name__ == "__main__":
    unittest.main()
