from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "engineering_run.py"

spec = importlib.util.spec_from_file_location("engineering_run", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def event(name: str, second: int) -> dict:
    return {"name": name, "at": f"2026-09-18T16:00:{second:02d}+00:00"}


def build(run_id: str = "run-1", *, verified: bool = True, safe: bool = True):
    return module.build_engineering_run(
        run_id=run_id,
        created_at="2026-09-18T16:00:00+00:00",
        task={"goal": "Implement a bounded change", "workflow": "engineering.feature"},
        dimensions={
            "repository": "fixture-consumer",
            "task_class": "feature",
            "worker": "builder",
            "service_tier": "basic",
            "autonomy": "advisory",
            "mode": "demo",
        },
        events=[
            event("intent_received", 0),
            event("context_ready", 1),
            event("plan_ready", 2),
            event("first_change", 4),
            event("verification_started", 5),
            event("verification_passed", 7),
        ],
        safety={"policy_violations_escaped": 0 if safe else 1},
        reliability={
            "first_pass_verification": verified,
            "eventual_verification": verified,
            "ci_passed": None,
        },
        autonomy={
            "human_interventions": 1,
            "completed_within_granted_autonomy": True,
        },
        outcome={"status": "verified" if verified else "failed"},
    )


class EngineeringRunTests(unittest.TestCase):
    def test_run_derives_flow_metrics_and_safety(self):
        run = build()
        self.assertEqual("engineering-run/v1", run["schema_version"])
        self.assertTrue(run["safety"]["safe"])
        self.assertEqual(2000, run["derived_metrics"]["intent_to_plan_ms"])
        self.assertEqual(2000, run["derived_metrics"]["plan_to_first_change_ms"])
        self.assertEqual(2000, run["derived_metrics"]["verification_ms"])
        self.assertEqual(7000, run["derived_metrics"]["intent_to_verified_ms"])
        self.assertIsNone(run["derived_metrics"]["intent_to_pr_ms"])

    def test_escaped_policy_violation_marks_run_unsafe(self):
        self.assertFalse(build(safe=False)["safety"]["safe"])

    def test_duplicate_or_out_of_order_evidence_fails_closed(self):
        with self.assertRaisesRegex(module.EngineeringRunError, "duplicate lifecycle milestone"):
            module.normalize_events([event("intent_received", 0), event("intent_received", 1)])
        with self.assertRaisesRegex(module.EngineeringRunError, "out of temporal order"):
            module.derive_metrics([event("plan_ready", 4), event("first_change", 2)])

    def test_summary_uses_rates_and_medians(self):
        first = build("run-1")
        second = build("run-2")
        second["derived_metrics"]["intent_to_verified_ms"] = 9000
        second["autonomy"]["human_interventions"] = 3
        summary = module.summarize_runs([first, second])
        self.assertEqual(2, summary["run_count"])
        self.assertEqual(1.0, summary["rates"]["safe_run_rate"])
        self.assertEqual(1.0, summary["rates"]["first_pass_verification_rate"])
        self.assertEqual(8000, summary["medians"]["intent_to_verified_ms"])
        self.assertEqual(2, summary["medians"]["human_interventions"])

    def test_cli_summary_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            output = root / "summary.json"
            first.write_text(json.dumps(build("run-1")), encoding="utf-8")
            second.write_text(json.dumps(build("run-2")), encoding="utf-8")
            self.assertEqual(0, module.main([str(first), str(second), "--output", str(output)]))
            summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(2, summary["run_count"])


if __name__ == "__main__":
    unittest.main()
