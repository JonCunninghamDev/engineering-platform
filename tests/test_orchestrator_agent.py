from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "orchestrator_agent.py"
FIXTURES = Path(__file__).parent / "fixtures" / "orchestrator"

spec = importlib.util.spec_from_file_location("orchestrator_agent", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class OrchestratorAgentTests(unittest.TestCase):
    def test_ready_context_selects_minimum_dependency_order(self) -> None:
        plan, report = module.run_orchestrator(
            load("ready-context.json"),
            load("job-search-registry.json"),
            run_id="orchestrator-test-001",
            created_at="2026-09-15T00:00:00Z",
        )
        names = [row["capability"] for row in plan["planning"]["selected"]]
        self.assertEqual(
            ["opportunity.search", "candidate.fit", "company.research"], names
        )
        self.assertEqual(0, report["metrics"]["dispatch_count"])
        self.assertNotIn("demo.design", names)
        self.assertNotIn("interview.prepare", names)

    def test_unready_context_is_rejected(self) -> None:
        with self.assertRaisesRegex(module.OrchestratorError, "not ready"):
            module.run_orchestrator(
                load("unready-context.json"), load("job-search-registry.json")
            )

    def test_disallowed_context_is_rejected(self) -> None:
        context = load("ready-context.json")
        context["handoff"]["allowed"] = False
        with self.assertRaisesRegex(module.OrchestratorError, "not allowed"):
            module.run_orchestrator(context, load("job-search-registry.json"))

    def test_higher_tier_fails_closed(self) -> None:
        with self.assertRaisesRegex(module.OrchestratorError, "not implemented"):
            module.run_orchestrator(
                load("ready-context.json"),
                load("job-search-registry.json"),
                tier="managed",
            )

    def test_dependency_cycle_is_rejected(self) -> None:
        registry = load("job-search-registry.json")
        registry["capabilities"][0]["dependencies"] = ["candidate.fit"]
        with self.assertRaisesRegex(module.OrchestratorError, "cycle"):
            module.run_orchestrator(load("ready-context.json"), registry)

    def test_demo_explains_selected_skipped_and_locked(self) -> None:
        plan, report = module.run_orchestrator(
            load("ready-context.json"),
            load("job-search-registry.json"),
            run_id="orchestrator-test-002",
            created_at="2026-09-15T00:00:00Z",
        )
        rendered = module.render_demo(plan, report)
        self.assertIn("WOULD_INVOKE", rendered)
        self.assertIn("demo.design", rendered)
        self.assertIn("MANAGED", rendered)
        self.assertIn("Dispatch count: 0", rendered)

    def test_cli_writes_plan_and_run_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "execution-plan.yaml"
            run_report = Path(directory) / "orchestrator-run.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--context",
                    str(FIXTURES / "ready-context.json"),
                    "--registry",
                    str(FIXTURES / "job-search-registry.json"),
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
            self.assertIn("WOULD_INVOKE", completed.stdout)
            payload = json.loads(run_report.read_text(encoding="utf-8"))
            self.assertEqual(0, payload["metrics"]["dispatch_count"])


if __name__ == "__main__":
    unittest.main()
