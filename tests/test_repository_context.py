from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location("repository_context", SCRIPTS / "repository_context.py")
repository_context = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["repository_context"] = repository_context
SPEC.loader.exec_module(repository_context)

ORCH_SPEC = importlib.util.spec_from_file_location("orchestrator_agent", SCRIPTS / "orchestrator_agent.py")
orchestrator_agent = importlib.util.module_from_spec(ORCH_SPEC)
assert ORCH_SPEC and ORCH_SPEC.loader
sys.modules["orchestrator_agent"] = orchestrator_agent
ORCH_SPEC.loader.exec_module(orchestrator_agent)

INPUT_SCHEMA = json.loads((ROOT / "schemas/context-input-v1.schema.json").read_text(encoding="utf-8"))
MANIFEST_SCHEMA = json.loads((ROOT / "schemas/context-manifest-v1.schema.json").read_text(encoding="utf-8"))
REPOSITORY_SCHEMA = json.loads((ROOT / "schemas/repository-context-v1.schema.json").read_text(encoding="utf-8"))

CONTRACT = {
    "schema_version": "context-contract/v1",
    "workflow": "repository-feature-work",
    "fields": [
        {
            "key": "product_objective",
            "requirement": "required",
            "prompt": "What product outcome should this change serve?",
        }
    ],
}


def payload(*, bootstrap: bool = False, feature_spec: str | None = "ai/specs/feature.md") -> dict:
    return {
        "schema_version": "context-input/v1",
        "goal": "Implement a repository-linked feature without inventing product truth.",
        "context": [
            {
                "key": "product_objective",
                "value": "Deliver a verified repository-aware feature.",
                "source": "human",
                "confidence": "high",
            }
        ],
        "repository": {
            "provider": "local",
            "identifier": "example/consumer",
            "ref": "develop",
            "manifest_path": "ai/project-context.json",
            "feature_spec": feature_spec,
            "bootstrap": {"allowed": bootstrap},
        },
    }


def repository_manifest() -> dict:
    return {
        "schema_version": "repository-context/v1",
        "specs": {
            "product": {"path": "ai/project/product.md", "required": True},
            "architecture": {"path": "ai/project/architecture.md", "required": True},
        },
        "feature_specs": {
            "directory": "ai/specs",
            "required_for_feature_work": True,
        },
    }


def write_complete_repo(root: Path, *, feature_status: str = "authoritative") -> None:
    (root / "ai/project").mkdir(parents=True, exist_ok=True)
    (root / "ai/specs").mkdir(parents=True, exist_ok=True)
    (root / "ai/project-context.json").write_text(
        json.dumps(repository_manifest(), indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "ai/project/product.md").write_text(
        "# Product\n\nStatus: authoritative\n\n## Objective\nShip the product.\n\n## Scope\nFeature work.\n\n## Constraints\nKeep product truth local.\n\n## Provenance\nHuman-owned spec.\n",
        encoding="utf-8",
    )
    (root / "ai/project/architecture.md").write_text(
        "# Architecture\n\nStatus: authoritative\n\n## Architecture\nContext then orchestration.\n\n## Constraints\nNo silent product invention.\n\n## Validation\nTests and CI.\n\n## Provenance\nRepository evidence.\n",
        encoding="utf-8",
    )
    (root / "ai/specs/feature.md").write_text(
        f"# Feature\n\nStatus: {feature_status}\n\n## Outcome\nRepository-aware work.\n\n## Requirements\nInspect declared specs.\n\n## Acceptance criteria\nHandoff only when ready.\n\n## Human gates\nProduct ambiguity.\n\n## Provenance\nHuman request and repo.\n",
        encoding="utf-8",
    )


class RepositoryContextTests(unittest.TestCase):
    def run_context(self, root: Path, supplied: dict):
        return repository_context.run_repository_aware_context(
            CONTRACT,
            supplied,
            repository_root=root,
            run_id="repository-context-test",
            created_at="2026-09-17T15:00:00+00:00",
        )

    def test_repository_linkage_is_additive_to_context_input_schema(self):
        linked = payload()
        Draft202012Validator(INPUT_SCHEMA).validate(linked)
        legacy = payload()
        legacy.pop("repository")
        Draft202012Validator(INPUT_SCHEMA).validate(legacy)

    def test_repository_context_manifest_schema_accepts_declared_spec_locations(self):
        Draft202012Validator(REPOSITORY_SCHEMA).validate(repository_manifest())

    def test_complete_authoritative_specs_allow_orchestration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_complete_repo(root)
            manifest, report, drafts = self.run_context(root, payload())
            Draft202012Validator(MANIFEST_SCHEMA).validate(manifest)
            self.assertTrue(manifest["readiness"]["ready_for_orchestration"])
            self.assertTrue(manifest["readiness"]["repository_specs_ready"])
            self.assertTrue(manifest["handoff"]["allowed"])
            self.assertEqual(report["status"], "complete")
            self.assertEqual(drafts, [])
            orchestrator_agent._validate_context(manifest)

    def test_missing_feature_generates_non_authoritative_draft_and_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_complete_repo(root)
            (root / "ai/specs/feature.md").unlink()
            manifest, report, drafts = self.run_context(root, payload(bootstrap=True))
            Draft202012Validator(MANIFEST_SCHEMA).validate(manifest)
            self.assertFalse(manifest["handoff"]["allowed"])
            self.assertIn("repository_specs", manifest["readiness"]["missing_required"])
            self.assertEqual(report["repository_context"]["remediation"]["action"], "review_and_apply_generated_drafts")
            self.assertEqual([item["path"] for item in drafts], ["ai/specs/feature.md"])
            self.assertIn("Status: DRAFT - SYNTHESIZED", drafts[0]["content"])
            with self.assertRaisesRegex(orchestrator_agent.OrchestratorError, "not ready"):
                orchestrator_agent._validate_context(manifest)

    def test_missing_repository_manifest_bootstraps_drafts_but_does_not_self_approve(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, report, drafts = self.run_context(root, payload(bootstrap=True))
            self.assertFalse(manifest["handoff"]["allowed"])
            self.assertEqual(report["repository_context"]["manifest"]["status"], "missing")
            paths = {item["path"] for item in drafts}
            self.assertIn("ai/project-context.json", paths)
            self.assertIn("ai/project/product.md", paths)
            self.assertIn("ai/project/architecture.md", paths)
            self.assertIn("ai/specs/feature.md", paths)

    def test_existing_draft_spec_blocks_until_reviewed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_complete_repo(root, feature_status="DRAFT - SYNTHESIZED")
            manifest, report, drafts = self.run_context(root, payload(bootstrap=True))
            self.assertFalse(manifest["handoff"]["allowed"])
            self.assertEqual(report["repository_context"]["spec_readiness"]["draft"], ["feature"])
            self.assertEqual(drafts, [])
            self.assertTrue(any(question["key"] == "feature_spec" for question in manifest["questions_for_human"]))

    def test_conflicting_required_human_context_remains_blocking_even_when_specs_are_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_complete_repo(root)
            supplied = payload()
            supplied["context"].append(
                {
                    "key": "product_objective",
                    "value": "A conflicting objective.",
                    "source": "issue",
                    "confidence": "high",
                }
            )
            manifest, _, drafts = self.run_context(root, supplied)
            self.assertFalse(manifest["handoff"]["allowed"])
            self.assertTrue(manifest["readiness"]["repository_specs_ready"])
            self.assertEqual(drafts, [])

    def test_legacy_input_without_repository_preserves_basic_context_behavior(self):
        supplied = payload()
        supplied.pop("repository")
        manifest, report, drafts = repository_context.run_repository_aware_context(
            CONTRACT,
            supplied,
            run_id="legacy-test",
            created_at="2026-09-17T15:00:00+00:00",
        )
        Draft202012Validator(MANIFEST_SCHEMA).validate(manifest)
        self.assertTrue(manifest["handoff"]["allowed"])
        self.assertNotIn("repository_context", manifest)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(drafts, [])


if __name__ == "__main__":
    unittest.main()
