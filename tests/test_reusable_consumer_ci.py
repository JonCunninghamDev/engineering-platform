from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "reusable-consumer-ci.yml"
SELF_TEST = ROOT / ".github" / "workflows" / "reusable-ci-self-test.yml"
NODE_PYTHON_TEMPLATE = ROOT / "templates" / "workflows" / "node-python.yml"
BLENDER_TEMPLATE = ROOT / "templates" / "workflows" / "node-python-blender.yml"


class ReusableConsumerCIContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.self_test = SELF_TEST.read_text(encoding="utf-8")
        cls.node_python = NODE_PYTHON_TEMPLATE.read_text(encoding="utf-8")
        cls.blender = BLENDER_TEMPLATE.read_text(encoding="utf-8")

    def test_workflow_is_reusable_with_stable_job_name(self) -> None:
        self.assertIn("workflow_call:", self.workflow)
        self.assertIn("consumer-ci:", self.workflow)
        self.assertIn("name: Platform Consumer CI", self.workflow)

    def test_capabilities_are_independently_switchable(self) -> None:
        for capability in ("enable_node", "enable_python", "enable_blender"):
            self.assertIn(f"{capability}:", self.workflow)
        self.assertIn("if: ${{ inputs.enable_blender }}", self.workflow)
        self.assertIn("if: ${{ inputs.enable_node", self.workflow)
        self.assertIn("if: ${{ inputs.enable_python", self.workflow)

    def test_fast_and_full_modes_keep_one_job(self) -> None:
        self.assertIn("fast|full", self.workflow)
        self.assertIn("inputs.mode == 'full'", self.workflow)
        self.assertEqual(self.workflow.count("name: Platform Consumer CI"), 1)

    def test_diagnostics_and_artifacts_are_bounded(self) -> None:
        self.assertIn("artifact_retention_days must be between 1 and 30", self.workflow)
        self.assertIn("Upload failure diagnostics", self.workflow)
        self.assertIn("Upload build metadata", self.workflow)
        self.assertIn("retention-days: ${{ inputs.artifact_retention_days }}", self.workflow)

    def test_node_python_template_does_not_enable_blender(self) -> None:
        self.assertIn("enable_node: true", self.node_python)
        self.assertIn("enable_python: true", self.node_python)
        self.assertNotIn("enable_blender: true", self.node_python)

    def test_blender_template_composes_all_capabilities(self) -> None:
        for setting in ("enable_node: true", "enable_python: true", "enable_blender: true"):
            self.assertIn(setting, self.blender)

    def test_templates_require_immutable_pin_placeholder(self) -> None:
        pin = "@<PINNED_PLATFORM_SHA>"
        self.assertIn(pin, self.node_python)
        self.assertIn(pin, self.blender)
        self.assertNotIn("@develop", self.node_python + self.blender)
        self.assertNotIn("@main", self.node_python + self.blender)

    def test_self_test_executes_both_compositions(self) -> None:
        self.assertIn("Node/Python Fast Composition", self.self_test)
        self.assertIn("Node/Python/Blender Full Composition", self.self_test)
        self.assertIn("uses: ./.github/workflows/reusable-consumer-ci.yml", self.self_test)

    def test_shared_workflow_has_no_consumer_specific_identity(self) -> None:
        combined = (self.workflow + self.node_python + self.blender).lower()
        for forbidden in ("low-poly-character-studio", "battle-earth", "career-ops"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
