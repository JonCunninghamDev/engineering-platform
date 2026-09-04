from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "agent-steering-scenarios-v1.json"
REQUIRED = {
    "feature",
    "defect",
    "ci-failure",
    "branch-conflict",
    "promotion",
    "synchronization",
    "hotfix",
    "incident",
    "credential",
    "visual",
    "architecture",
    "destructive",
    "interrupted-run",
    "recurring-run",
}
ALLOWED_DECISIONS = {"autonomous", "recover", "human_gate"}


class AgentSteeringScenarioTests(unittest.TestCase):
    def test_required_scenarios_have_deterministic_decisions(self) -> None:
        scenarios = json.loads(FIXTURES.read_text(encoding="utf-8"))
        by_name = {scenario["name"]: scenario for scenario in scenarios}
        self.assertEqual(set(by_name), REQUIRED)
        for name, scenario in by_name.items():
            with self.subTest(scenario=name):
                self.assertIn(scenario["decision"], ALLOWED_DECISIONS)
                self.assertTrue(scenario["situation"].strip())
                self.assertTrue(scenario["reason"].strip())

    def test_human_gate_set_covers_consequential_classes(self) -> None:
        scenarios = json.loads(FIXTURES.read_text(encoding="utf-8"))
        gated = {item["name"] for item in scenarios if item["decision"] == "human_gate"}
        self.assertTrue({"promotion", "hotfix", "credential", "visual", "destructive"} <= gated)

    def test_recovery_set_covers_interrupted_and_recurring_runs(self) -> None:
        scenarios = json.loads(FIXTURES.read_text(encoding="utf-8"))
        recovery = {item["name"] for item in scenarios if item["decision"] == "recover"}
        self.assertTrue({"ci-failure", "branch-conflict", "interrupted-run", "recurring-run"} <= recovery)


if __name__ == "__main__":
    unittest.main()
