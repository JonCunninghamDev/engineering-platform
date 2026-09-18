from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "governed_execution.py"

spec = importlib.util.spec_from_file_location("governed_execution", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def policy():
    return {
        "schema_version": "engineering-policy/v1",
        "branches": {
            "release": "main",
            "integration": "develop",
            "temporary_prefixes": ["feature/", "fix/"],
        },
        "review": {
            "pull_requests_required": True,
            "required_checks": ["CI / check"],
            "human_approval_for": ["release", "credentials"],
        },
        "delivery": {
            "implementation_target": "integration",
            "release_route": "integration_to_release",
            "direct_release_writes": False,
            "hotfix_route": "integration_first",
        },
        "permissions": {
            "read": {
                "tier": "autonomous",
                "risk": "low",
                "actions": ["repository.read", "issue.read"],
            },
            "bounded_write": {
                "tier": "bounded",
                "risk": "medium",
                "actions": [
                    "branch.write",
                    "code.write",
                    "test.write",
                    "pr.create",
                    "merge.integration",
                ],
            },
            "consequential_write": {
                "tier": "approval_required",
                "risk": "high",
                "actions": ["release.write", "credential.write"],
            },
        },
        "protected_paths": [".github/**", "engineering-policy.json", "ai/project/**"],
        "validation": {
            "stages": [
                {
                    "id": "consumer-completion",
                    "stage": "completion_gate",
                    "capability": "test.node",
                    "required": True,
                }
            ]
        },
        "execution_budgets": {"max_steps": 120, "max_retries": 2},
    }


def request():
    return {
        "schema_version": "governed-execution-request/v1",
        "run_id": "world-vibes-31-001",
        "repository": {
            "identifier": "JonCunninghamDev/world-vibes",
            "base_ref": "develop",
            "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "target_ref": "develop",
            "feature_branch": "feature/issue-31-photorealistic-3d",
        },
        "task": {
            "issue": "31",
            "goal": "Add capability-aware photorealistic 3D city close-up",
            "task_class": "feature",
        },
        "worker": {"adapter": "chatgpt-codex", "provider": "openai"},
        "requested_actions": ["repository.read", "branch.write", "code.write", "test.write", "pr.create", "merge.integration"],
        "scope": {
            "allowed_paths": ["src/", "server/", "tests/", "ai/specs/"],
            "protected_paths": [],
        },
        "verification": {"pre_pr_checks": []},
        "change_classes": ["visual_change"],
        "human_gates": ["visual_acceptance"],
    }


def result():
    return {
        "schema_version": "worker-execution-result/v1",
        "run_id": "world-vibes-31-001",
        "executor": {
            "adapter": "chatgpt-codex",
            "provider": "openai",
            "execution_id": "executor-run-001",
        },
        "repository": {
            "identifier": "JonCunninghamDev/world-vibes",
            "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "branch": "feature/issue-31-photorealistic-3d",
            "head_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "commits": ["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
        },
        "actions": ["code.write", "test.write"],
        "changed_paths": ["src/globeRenderer.ts", "tests/scenePlan.test.mjs"],
        "verification": [
            {
                "name": "consumer-completion",
                "status": "passed",
                "evidence": "process://npm-run-check/exit-0",
                "exit_code": 0,
                "duration_ms": 1250,
            }
        ],
        "budget": {
            "steps": 12,
            "elapsed_ms": 42000,
            "retries": 0,
            "cost_usd": None,
        },
        "security": {
            "consequential_actions_attempted": [],
            "consequential_actions_blocked": [],
        },
        "direct_shared_branch_writes": 0,
    }


class GovernedExecutionTests(unittest.TestCase):
    def test_authorizes_only_integration_feature_route(self):
        envelope = module.authorize_execution(policy(), request())
        self.assertTrue(envelope["authorization"]["allowed"])
        self.assertEqual("develop", envelope["repository"]["target_ref"])
        self.assertEqual(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            envelope["repository"]["base_commit"],
        )
        self.assertEqual(["CI / check"], envelope["verification"]["required_ci_checks"])
        self.assertEqual(["consumer-completion"], envelope["verification"]["pre_pr_checks"])
        self.assertIn("visual_acceptance", envelope["human_gates"])
        self.assertFalse(envelope["delivery"]["release_write_allowed"])

    def test_only_applicable_policy_categories_become_human_gates(self):
        envelope = module.authorize_execution(policy(), request())
        self.assertEqual(["visual_acceptance"], envelope["human_gates"])

        candidate = request()
        candidate["change_classes"] = ["credentials"]
        envelope = module.authorize_execution(policy(), candidate)
        self.assertEqual(["credentials", "visual_acceptance"], envelope["human_gates"])

    def test_rejects_direct_release_or_wrong_branch_route(self):
        candidate = request()
        candidate["repository"]["target_ref"] = "main"
        envelope = module.authorize_execution(policy(), candidate)
        self.assertFalse(envelope["authorization"]["allowed"])
        self.assertTrue(any("integration branch" in reason for reason in envelope["authorization"]["reasons"]))

        candidate = request()
        candidate["repository"]["feature_branch"] = "develop"
        envelope = module.authorize_execution(policy(), candidate)
        self.assertFalse(envelope["authorization"]["allowed"])

    def test_rejects_consequential_or_unknown_action(self):
        candidate = request()
        candidate["requested_actions"].append("release.write")
        envelope = module.authorize_execution(policy(), candidate)
        self.assertFalse(envelope["authorization"]["allowed"])
        self.assertTrue(any("consequential" in reason for reason in envelope["authorization"]["reasons"]))

    def test_worker_result_must_stay_in_scope_and_out_of_protected_paths(self):
        envelope = module.authorize_execution(policy(), request())
        bad = result()
        bad["changed_paths"].append(".github/workflows/ci.yml")
        verification = module.verify_worker_result(envelope, bad)
        self.assertEqual("rejected", verification["status"])
        self.assertTrue(any("protected path" in row for row in verification["scope"]["violations"]))

    def test_verified_worker_result_allows_pr_but_not_merge(self):
        envelope = module.authorize_execution(policy(), request())
        verification = module.verify_worker_result(envelope, result())
        self.assertEqual("verified", verification["status"])
        self.assertTrue(verification["delivery"]["pr_creation_allowed"])
        self.assertFalse(verification["delivery"]["merge_allowed"])

    def test_pre_pr_check_must_pass_when_consumer_requires_it(self):
        candidate = request()
        candidate["verification"]["pre_pr_checks"] = ["npm run check"]
        envelope = module.authorize_execution(policy(), candidate)
        verification = module.verify_worker_result(envelope, result())
        self.assertEqual("rejected", verification["status"])

        passed = result()
        passed["verification"].append({
            "name": "npm run check",
            "status": "passed",
            "evidence": "process://npm-run-check/exit-0",
            "exit_code": 0,
            "duration_ms": 1500,
        })
        verification = module.verify_worker_result(envelope, passed)
        self.assertEqual("verified", verification["status"])

    def test_required_policy_validation_cannot_be_omitted_by_request(self):
        candidate = request()
        candidate["verification"]["pre_pr_checks"] = []
        envelope = module.authorize_execution(policy(), candidate)
        self.assertEqual(["consumer-completion"], envelope["verification"]["pre_pr_checks"])

        missing = result()
        missing["verification"] = []
        verification = module.verify_worker_result(envelope, missing)
        self.assertEqual("rejected", verification["status"])
        self.assertTrue(any("consumer-completion" in row for row in verification["scope"]["violations"]))

    def test_passed_verification_requires_concrete_evidence(self):
        envelope = module.authorize_execution(policy(), request())
        missing_evidence = result()
        missing_evidence["verification"][0].pop("evidence")
        with self.assertRaisesRegex(module.GovernedExecutionError, "evidence"):
            module.verify_worker_result(envelope, missing_evidence)

    def test_passed_check_requires_zero_exit_code_and_duration(self):
        envelope = module.authorize_execution(policy(), request())
        invalid = result()
        invalid["verification"][0]["exit_code"] = 1
        with self.assertRaisesRegex(module.GovernedExecutionError, "exit_code"):
            module.verify_worker_result(envelope, invalid)

        invalid = result()
        invalid["verification"][0].pop("duration_ms")
        with self.assertRaisesRegex(module.GovernedExecutionError, "duration_ms"):
            module.verify_worker_result(envelope, invalid)

    def test_duplicate_verification_check_is_rejected(self):
        envelope = module.authorize_execution(policy(), request())
        duplicate = result()
        duplicate["verification"].append(dict(duplicate["verification"][0]))
        with self.assertRaisesRegex(module.GovernedExecutionError, "duplicate worker verification check"):
            module.verify_worker_result(envelope, duplicate)

    def test_worker_result_must_match_executor_and_base_commit(self):
        envelope = module.authorize_execution(policy(), request())

        mismatch = result()
        mismatch["executor"]["provider"] = "different-provider"
        verification = module.verify_worker_result(envelope, mismatch)
        self.assertEqual("rejected", verification["status"])
        self.assertTrue(any("provider" in row for row in verification["scope"]["violations"]))

        mismatch = result()
        mismatch["repository"]["base_commit"] = "cccccccccccccccccccccccccccccccccccccccc"
        verification = module.verify_worker_result(envelope, mismatch)
        self.assertEqual("rejected", verification["status"])
        self.assertTrue(any("base commit" in row for row in verification["scope"]["violations"]))

    def test_worker_result_enforces_execution_budgets(self):
        candidate_policy = policy()
        candidate_policy["execution_budgets"]["max_elapsed_minutes"] = 0.5
        envelope = module.authorize_execution(candidate_policy, request())
        over = result()
        over["budget"]["elapsed_ms"] = 31_000
        verification = module.verify_worker_result(envelope, over)
        self.assertEqual("rejected", verification["status"])
        self.assertTrue(any("max_elapsed_minutes" in row for row in verification["scope"]["violations"]))

        envelope = module.authorize_execution(policy(), request())
        over = result()
        over["budget"]["steps"] = 121
        verification = module.verify_worker_result(envelope, over)
        self.assertEqual("rejected", verification["status"])
        self.assertTrue(any("max_steps" in row for row in verification["scope"]["violations"]))

    def test_consequential_action_attempts_require_block_evidence(self):
        envelope = module.authorize_execution(policy(), request())
        unsafe = result()
        unsafe["security"]["consequential_actions_attempted"] = ["release.write"]
        verification = module.verify_worker_result(envelope, unsafe)
        self.assertEqual("rejected", verification["status"])

        safe = result()
        safe["security"]["consequential_actions_attempted"] = ["release.write"]
        safe["security"]["consequential_actions_blocked"] = ["release.write"]
        verification = module.verify_worker_result(envelope, safe)
        self.assertEqual("verified", verification["status"])

    def test_delivery_gate_requires_ci_and_human_gate(self):
        envelope = module.authorize_execution(policy(), request())
        verification = module.verify_worker_result(envelope, result())

        gate = module.evaluate_delivery_gate(
            envelope,
            verification,
            ci_checks=[{"name": "CI / check", "status": "passed"}],
            approvals=[],
        )
        self.assertFalse(gate["merge_allowed"])
        self.assertEqual(["visual_acceptance"], gate["pending_human_gates"])

        gate = module.evaluate_delivery_gate(
            envelope,
            verification,
            ci_checks=[{"name": "CI / check", "status": "passed"}],
            approvals=["visual_acceptance"],
        )
        self.assertTrue(gate["merge_allowed"])
        self.assertEqual([], gate["pending_ci_checks"])
        self.assertEqual([], gate["pending_human_gates"])


if __name__ == "__main__":
    unittest.main()
