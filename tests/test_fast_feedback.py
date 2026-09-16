from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_fast_feedback.py"
SPEC = importlib.util.spec_from_file_location("run_fast_feedback", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(module)


class FastFeedbackTests(unittest.TestCase):
    def _config(self, command: list[str]) -> dict[str, object]:
        return {
            "schema_version": "fast-feedback/v1",
            "policy": "engineering-policy.json",
            "stages": {
                "after_write": [{"id": "after", "command": command}],
                "pre_commit": [{"id": "pre", "command": command}],
                "completion_gate": [{"id": "complete", "command": command}],
            },
        }

    def test_passing_stage_records_structured_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = module.run_stage(
                root=Path(temp),
                config=self._config([sys.executable, "-c", "print('ok')"]),
                stage="completion_gate",
                echo=False,
            )
        self.assertEqual("passed", evidence["status"])
        self.assertEqual("completion_gate", evidence["stage"])
        self.assertEqual(0, evidence["commands"][0]["return_code"])
        self.assertIn("ok", evidence["commands"][0]["stdout"])

    def test_failing_stage_refuses_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = module.run_stage(
                root=Path(temp),
                config=self._config([sys.executable, "-c", "raise SystemExit(7)"]),
                stage="completion_gate",
                echo=False,
            )
        self.assertEqual("failed", evidence["status"])
        self.assertEqual(7, evidence["commands"][0]["return_code"])

    def test_runner_stops_after_first_failure(self) -> None:
        config = self._config([sys.executable, "-c", "raise SystemExit(1)"])
        config["stages"]["pre_commit"].append(
            {"id": "should-not-run", "command": [sys.executable, "-c", "print('later')"]}
        )
        with tempfile.TemporaryDirectory() as temp:
            evidence = module.run_stage(
                root=Path(temp), config=config, stage="pre_commit", echo=False
            )
        self.assertEqual(1, len(evidence["commands"]))

    def test_invalid_config_rejects_unknown_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            config = self._config([sys.executable, "-c", "pass"])
            config["stages"]["host_specific"] = [{"id": "bad", "command": ["true"]}]
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(module.FastFeedbackConfigError):
                module.load_config(path)

    def test_write_evidence_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "nested" / "evidence.json"
            module.write_evidence(path, {"status": "passed"})
            self.assertEqual({"status": "passed"}, json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
