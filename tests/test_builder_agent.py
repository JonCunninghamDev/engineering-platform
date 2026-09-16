from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "builder_agent.py"
FIXTURES = Path(__file__).parent / "fixtures" / "builder"

spec = importlib.util.spec_from_file_location("builder_agent", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class BuilderAgentTests(unittest.TestCase):
    def test_valid_task_produces_scope_checked_change_set(self) -> None:
        change_set, report = module.run_builder(
            load("execution-plan.json"),
            load("valid-task.json"),
            run_id="builder-test-001",
            created_at="2026-09-16T00:00:00Z",
        )
        self.assertEqual("change-set/v1", change_set["schema_version"])
        self.assertEqual("engineering.implement", change_set["assigned_capability"])
        self.assertEqual(2, change_set["summary"]["change_count"])
        self.assertEqual(0, change_set["summary"]["actual_write_count"])
        self.assertEqual(2, report["metrics"]["proposed_write_count"])
        self.assertTrue(change_set["changes"][0]["diff"].startswith("--- /dev/null"))
        self.assertIn("+++ b/README.md", change_set["changes"][1]["diff"])
        self.assertEqual(64, len(change_set["changes"][0]["after_sha256"]))

    def test_assignment_must_be_explicit_and_allowed(self) -> None:
        task = load("valid-task.json")
        task["assignment"]["allowed"] = False
        with self.assertRaisesRegex(module.BuilderError, "assignment is not allowed"):
            module.run_builder(load("execution-plan.json"), task)

    def test_plan_capability_must_be_selected_and_builder_owned(self) -> None:
        task = load("valid-task.json")
        task["plan"]["capability"] = "engineering.verify"
        with self.assertRaisesRegex(module.BuilderError, "not selected"):
            module.run_builder(load("execution-plan.json"), task)

        plan = load("execution-plan.json")
        plan["planning"]["selected"][0]["provider"] = "reviewer"
        with self.assertRaisesRegex(module.BuilderError, "provider 'builder'"):
            module.run_builder(plan, load("valid-task.json"))

    def test_scope_rejects_outside_protected_and_traversal_paths(self) -> None:
        task = load("valid-task.json")
        task["changes"][0]["path"] = "docs/greeting.py"
        with self.assertRaisesRegex(module.BuilderError, "outside allowed scope"):
            module.run_builder(load("execution-plan.json"), task)

        task = load("valid-task.json")
        task["scope"]["allowed_paths"].append(".github/")
        task["changes"][0]["path"] = ".github/workflows/ci.yml"
        with self.assertRaisesRegex(module.BuilderError, "protected"):
            module.run_builder(load("execution-plan.json"), task)

        task = load("valid-task.json")
        task["changes"][0]["path"] = "../outside.py"
        with self.assertRaisesRegex(module.BuilderError, "traversal"):
            module.run_builder(load("execution-plan.json"), task)

    def test_delete_is_rejected_at_basic_tier(self) -> None:
        task = load("valid-task.json")
        task["changes"][0]["operation"] = "delete"
        with self.assertRaisesRegex(module.BuilderError, "create or update"):
            module.run_builder(load("execution-plan.json"), task)

    def test_higher_tier_fails_closed(self) -> None:
        with self.assertRaisesRegex(module.BuilderError, "not implemented"):
            module.run_builder(
                load("execution-plan.json"), load("valid-task.json"), tier="managed"
            )

    def test_demo_reports_would_write_locked_tiers_and_zero_actual_writes(self) -> None:
        change_set, report = module.run_builder(
            load("execution-plan.json"),
            load("valid-task.json"),
            run_id="builder-test-002",
            created_at="2026-09-16T00:00:00Z",
        )
        rendered = module.render_demo(change_set, report)
        self.assertIn("WOULD_WRITE", rendered)
        self.assertIn("MANAGED", rendered)
        self.assertIn("Actual write count: 0", rendered)
        self.assertIn("PROPOSED / NOT APPLIED", rendered)

    def test_cli_writes_change_set_and_run_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "change-set.yaml"
            run_report = Path(directory) / "builder-run.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--plan",
                    str(FIXTURES / "execution-plan.json"),
                    "--task",
                    str(FIXTURES / "valid-task.json"),
                    "--output",
                    str(output),
                    "--run-report",
                    str(run_report),
                    "--mode",
                    "demo",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(output.exists())
            self.assertTrue(run_report.exists())
            self.assertIn("WOULD_WRITE", completed.stdout)
            payload = json.loads(run_report.read_text(encoding="utf-8"))
            self.assertEqual(0, payload["metrics"]["actual_write_count"])


if __name__ == "__main__":
    unittest.main()
