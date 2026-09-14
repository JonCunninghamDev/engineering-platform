from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "context_agent.py"
SPEC = importlib.util.spec_from_file_location("context_agent", SCRIPT)
context_agent = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["context_agent"] = context_agent
SPEC.loader.exec_module(context_agent)

FIXTURES = ROOT / "tests" / "fixtures" / "context-agent"


class ContextAgentTests(unittest.TestCase):
    def load(self, name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def run_agent(self, input_name: str, **kwargs):
        return context_agent.run_context_agent(
            self.load("job-search-contract.json"),
            self.load(input_name),
            run_id="context-test-001",
            created_at="2026-09-14T12:00:00+00:00",
            **kwargs,
        )

    def test_ready_context_allows_handoff_and_reports_basic_tier(self):
        manifest, report = self.run_agent("ready-input.json")
        self.assertTrue(manifest["readiness"]["ready_for_orchestration"])
        self.assertTrue(manifest["handoff"]["allowed"])
        self.assertEqual(manifest["agent"]["service_tier"], "basic")
        self.assertEqual(manifest["agent"]["autonomy"], "advisory")
        self.assertEqual(manifest["agent"]["mode"], "demo")
        self.assertEqual(manifest["readiness"]["missing_required"], [])
        self.assertEqual(manifest["readiness"]["missing_recommended"], ["compensation_target"])
        self.assertIn("formulate_blocking_questions", report["capabilities"]["available_unused"])
        self.assertIn("verify_source_provenance", report["capabilities"]["locked_by_tier"]["managed"])

    def test_missing_required_context_blocks_handoff_and_formulates_questions(self):
        manifest, report = self.run_agent("missing-input.json")
        self.assertFalse(manifest["readiness"]["ready_for_orchestration"])
        self.assertFalse(manifest["handoff"]["allowed"])
        self.assertEqual(manifest["readiness"]["missing_required"], ["location_constraints", "employment_preferences"])
        self.assertEqual(len(manifest["questions_for_human"]), 2)
        self.assertIn("formulate_blocking_questions", report["capabilities"]["used"])
        self.assertEqual(report["status"], "needs_context")

    def test_conflicting_required_values_block_handoff(self):
        manifest, _ = self.run_agent("conflict-input.json")
        self.assertFalse(manifest["handoff"]["allowed"])
        conflicts = manifest["readiness"]["blocking_conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["key"], "location_constraints")
        self.assertNotIn("location_constraints", manifest["normalized_context"])

    def test_higher_service_tiers_fail_closed(self):
        with self.assertRaisesRegex(context_agent.ContextAgentError, "not implemented"):
            self.run_agent("ready-input.json", tier="managed")
        with self.assertRaisesRegex(context_agent.ContextAgentError, "not implemented"):
            self.run_agent("ready-input.json", tier="full")

    def test_demo_render_displays_active_and_locked_tiers(self):
        _, report = self.run_agent("ready-input.json")
        rendered = context_agent.render_demo(report)
        self.assertIn("Service tier: BASIC", rendered)
        self.assertIn("Mode: DEMO", rendered)
        self.assertIn("Locked by higher service tier:", rendered)
        self.assertIn("MANAGED", rendered)
        self.assertIn("FULL", rendered)
        self.assertIn("Handoff allowed: YES", rendered)

    def test_cli_writes_yaml_handoff_and_json_run_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "context.yaml"
            report = Path(directory) / "context-run.json"
            exit_code = context_agent.main([
                "--contract", str(FIXTURES / "job-search-contract.json"),
                "--input", str(FIXTURES / "ready-input.json"),
                "--output", str(output),
                "--run-report", str(report),
                "--mode", "demo",
            ])
            self.assertEqual(exit_code, 0)
            yaml_text = output.read_text(encoding="utf-8")
            self.assertIn('schema_version: "context-manifest/v1"', yaml_text)
            self.assertIn('service_tier: "basic"', yaml_text)
            self.assertIn("ready_for_orchestration: true", yaml_text)
            report_data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(report_data["schema_version"], "agent-run-report/v1")
            self.assertTrue(report_data["handoff"]["allowed"])


if __name__ == "__main__":
    unittest.main()
