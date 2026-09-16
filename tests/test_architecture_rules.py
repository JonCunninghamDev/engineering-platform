from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_architecture.py"
SPEC = importlib.util.spec_from_file_location("validate_architecture", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(module)


class ArchitectureRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self._write_valid_fixture()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_json(self, relative: str, value: object) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def _read_json(self, relative: str) -> dict[str, object]:
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def _write_valid_fixture(self) -> None:
        (self.root / "schemas").mkdir(parents=True, exist_ok=True)
        for name in (
            "architecture-decision-v1.schema.json",
            "architecture-rule-registry-v1.schema.json",
        ):
            shutil.copy(ROOT / "schemas" / name, self.root / "schemas" / name)

        self._write_json(
            "engineering-policy.json",
            {
                "branches": {
                    "release": "main",
                    "integration": "develop",
                    "temporary_prefixes": ["agent/"],
                }
            },
        )
        self._write_json(
            "architecture/decisions/ADR-0001.json",
            {
                "schema_version": "architecture-decision/v1",
                "id": "ADR-0001",
                "title": "Use exactly two long-lived delivery branches",
                "status": "accepted",
                "decision": "Use main and develop for release and integration.",
                "rationale": "A stable promotion boundary separates released and integration state.",
                "consequences": ["Feature work uses temporary branches."],
                "supersedes": [],
                "superseded_by": None,
                "enforcement": {
                    "required": True,
                    "rules": ["delivery.two-long-lived-branches"],
                },
            },
        )
        self._write_json(
            "standards/architecture-rules-v1.json",
            {
                "schema_version": "architecture-rule-registry/v1",
                "rules": [
                    {
                        "id": "delivery.two-long-lived-branches",
                        "adr": "ADR-0001",
                        "description": "main and develop are the long-lived branch roles.",
                        "validator": {
                            "type": "python",
                            "path": "scripts/check.py",
                            "entrypoint": "check",
                        },
                        "tests": ["tests/test_check.py"],
                        "repair": "Restore main/develop branch roles.",
                    }
                ],
            },
        )
        for relative in ("scripts/check.py", "tests/test_check.py"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# executable evidence\n", encoding="utf-8")

    def test_repository_architecture_is_valid(self) -> None:
        self.assertEqual([], module.validate(ROOT))

    def test_minimal_valid_fixture_passes(self) -> None:
        self.assertEqual([], module.validate(self.root))

    def test_missing_validator_failure_includes_rule_adr_rationale_and_repair(self) -> None:
        (self.root / "scripts" / "check.py").unlink()
        errors = module.validate(self.root)
        joined = "\n".join(errors)
        self.assertIn("architecture rule delivery.two-long-lived-branches violated", joined)
        self.assertIn("ADR-0001 Use exactly two long-lived delivery branches", joined)
        self.assertIn("Rationale:", joined)
        self.assertIn("Repair:", joined)

    def test_branch_rule_failure_has_architectural_context(self) -> None:
        policy = self._read_json("engineering-policy.json")
        policy["branches"]["release"] = "production"
        self._write_json("engineering-policy.json", policy)
        joined = "\n".join(module.validate(self.root))
        self.assertIn("architecture rule delivery.two-long-lived-branches violated", joined)
        self.assertIn("expected release=main and integration=develop", joined)
        self.assertIn("Rationale:", joined)
        self.assertIn("Repair:", joined)

    def test_adr_to_rule_reference_cannot_drift(self) -> None:
        decision = self._read_json("architecture/decisions/ADR-0001.json")
        decision["enforcement"]["rules"] = ["delivery.missing"]
        self._write_json("architecture/decisions/ADR-0001.json", decision)
        joined = "\n".join(module.validate(self.root))
        self.assertIn("ADR-0001 references unknown architecture rule: delivery.missing", joined)
        self.assertIn("ADR does not reference the rule", joined)

    def test_rule_cannot_reference_unknown_adr(self) -> None:
        registry = self._read_json("standards/architecture-rules-v1.json")
        registry["rules"][0]["adr"] = "ADR-9999"
        self._write_json("standards/architecture-rules-v1.json", registry)
        joined = "\n".join(module.validate(self.root))
        self.assertIn("references unknown ADR: ADR-9999", joined)

    def test_supersession_reference_must_exist(self) -> None:
        decision = self._read_json("architecture/decisions/ADR-0001.json")
        decision["supersedes"] = ["ADR-0009"]
        self._write_json("architecture/decisions/ADR-0001.json", decision)
        joined = "\n".join(module.validate(self.root))
        self.assertIn("ADR-0001 supersedes unknown ADR: ADR-0009", joined)


if __name__ == "__main__":
    unittest.main()
