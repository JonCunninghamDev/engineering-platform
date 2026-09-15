from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "demo_context_to_orchestrator.py"
FIXTURES = ROOT / "tests" / "fixtures"


class ContextOrchestratorDemoTests(unittest.TestCase):
    def test_ready_context_flows_into_orchestrator_without_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--contract",
                    str(FIXTURES / "context-agent" / "job-search-contract.json"),
                    "--input",
                    str(FIXTURES / "context-agent" / "ready-input.json"),
                    "--registry",
                    str(FIXTURES / "orchestrator" / "job-search-registry.json"),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("=== CONTEXT STAGE ===", completed.stdout)
            self.assertIn("Handoff allowed: YES", completed.stdout)
            self.assertIn("=== HANDOFF ===", completed.stdout)
            self.assertIn("Context manifest accepted by Orchestrator", completed.stdout)
            self.assertIn("=== ORCHESTRATOR STAGE ===", completed.stdout)
            self.assertIn("Dispatch count: 0", completed.stdout)
            self.assertIn("WOULD_INVOKE", completed.stdout)

            expected = {
                "context.yaml",
                "context-run.json",
                "execution-plan.yaml",
                "orchestrator-run.json",
            }
            self.assertEqual(expected, {path.name for path in output_dir.iterdir()})

            context_report = json.loads(
                (output_dir / "context-run.json").read_text(encoding="utf-8")
            )
            orchestrator_report = json.loads(
                (output_dir / "orchestrator-run.json").read_text(encoding="utf-8")
            )
            self.assertTrue(context_report["handoff"]["allowed"])
            self.assertEqual(0, orchestrator_report["metrics"]["dispatch_count"])
            self.assertEqual(3, orchestrator_report["metrics"]["selected_capability_count"])

            context_yaml = (output_dir / "context.yaml").read_text(encoding="utf-8")
            plan_yaml = (output_dir / "execution-plan.yaml").read_text(encoding="utf-8")
            self.assertIn("ready_for_orchestration: true", context_yaml)
            self.assertIn("context_run_id:", plan_yaml)
            self.assertIn("dispatch_count: 0", plan_yaml)

    def test_unready_context_stops_before_orchestrator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--contract",
                    str(FIXTURES / "context-agent" / "job-search-contract.json"),
                    "--input",
                    str(FIXTURES / "context-agent" / "missing-input.json"),
                    "--registry",
                    str(FIXTURES / "orchestrator" / "job-search-registry.json"),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(2, completed.returncode)
            self.assertIn("Handoff allowed: NO", completed.stdout)
            self.assertIn("NOT INVOKED", completed.stdout)
            self.assertTrue((output_dir / "context.yaml").exists())
            self.assertFalse((output_dir / "execution-plan.yaml").exists())


if __name__ == "__main__":
    unittest.main()
