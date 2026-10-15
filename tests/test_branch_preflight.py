from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "branch_preflight.py"
SPEC = importlib.util.spec_from_file_location("branch_preflight", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

MAIN = "a" * 40
DEVELOP = "b" * 40
FEATURE = "c" * 40
OTHER = "d" * 40


def snapshot(operation="create"):
    return {
        "verified": True,
        "observed_at": "2026-10-15T16:00:00Z",
        "refs": {"main": MAIN, "develop": DEVELOP},
        "pull_requests": [],
        "request": {
            "operation": operation,
            "issue": 76,
            "branch": "feature/issue-76-preflight",
        },
    }


def other_pr():
    return {
        "number": 75, "state": "open", "draft": True,
        "head": "feature/issue-74-scorecards", "base": "develop",
        "issue": 74, "waiting": True, "overlaps_requested": False,
    }


def merge_ready():
    item = snapshot("merge")
    item["refs"]["feature/issue-76-preflight"] = FEATURE
    item["pull_requests"] = [{
        "number": 77, "state": "open", "draft": False,
        "head": "feature/issue-76-preflight", "base": "develop",
        "issue": 76, "head_sha": FEATURE, "checks": "success",
        "unresolved_threads": 0, "mergeable": True,
        "human_gate": True, "human_accepted": True,
    }]
    item["request"].update({
        "checked_head_sha": FEATURE, "merge_authorized_by_policy": True,
    })
    return item


class BranchPreflightTests(unittest.TestCase):
    def decision(self, item):
        return module.evaluate(item)["decision"]

    def test_no_existing_work_permits_issue_branch(self):
        self.assertEqual("ALLOW_CREATE", self.decision(snapshot()))

    def test_unverified_or_missing_inventory_fails_closed(self):
        for change in (
            lambda x: x.update(verified=False),
            lambda x: x.pop("pull_requests"),
            lambda x: x.pop("refs"),
            lambda x: x.update(observed_at=""),
            lambda x: x["refs"].update(develop="not-a-sha"),
        ):
            with self.subTest(change=str(change)):
                item = snapshot()
                change(item)
                self.assertEqual("BLOCK", self.decision(item))

    def test_existing_draft_pr_prevents_duplicate_issue_branch(self):
        item = snapshot()
        item["pull_requests"] = [dict(other_pr(), issue=76)]
        self.assertEqual("BLOCK", self.decision(item))
        self.assertIn("Resume existing PR", module.evaluate(item)["reason"])

    def test_existing_remote_branch_prevents_duplicate_creation(self):
        item = snapshot()
        item["refs"]["feature/issue-76-preflight"] = FEATURE
        self.assertEqual("BLOCK", self.decision(item))
        item["request"]["operation"] = "resume"
        self.assertEqual("BLOCK", self.decision(item))
        item["request"]["branch_issue_verified"] = True
        self.assertEqual("ALLOW_RESUME", self.decision(item))

    def test_second_independent_branch_only_while_first_waits(self):
        item = snapshot()
        item["refs"]["feature/issue-74-scorecards"] = OTHER
        item["pull_requests"] = [other_pr()]
        self.assertEqual("BLOCK", self.decision(item))
        item["request"]["independent_of_active_work"] = True
        self.assertEqual("ALLOW_CREATE", self.decision(item))
        item["pull_requests"][0]["waiting"] = False
        self.assertEqual("BLOCK", self.decision(item))

    def test_overlapping_or_unassessed_pr_blocks_second_branch(self):
        item = snapshot()
        item["refs"]["feature/issue-74-scorecards"] = OTHER
        item["pull_requests"] = [other_pr()]
        item["request"]["independent_of_active_work"] = True
        for value in (True, None):
            with self.subTest(overlap=value):
                item["pull_requests"][0]["overlaps_requested"] = value
                self.assertEqual("BLOCK", self.decision(item))

    def test_two_active_branches_block_third(self):
        item = snapshot()
        item["refs"].update({
            "feature/issue-74-scorecards": OTHER,
            "feature/issue-73-other": FEATURE,
        })
        item["pull_requests"] = [other_pr()]
        item["request"]["independent_of_active_work"] = True
        self.assertEqual("BLOCK", self.decision(item))

    def test_branch_without_pr_requires_reconciliation_before_second(self):
        item = snapshot()
        item["refs"]["feature/issue-74-scorecards"] = OTHER
        item["request"]["independent_of_active_work"] = True
        self.assertEqual("BLOCK", self.decision(item))

    def test_descriptive_feature_branch_is_allowed_with_verified_issue(self):
        item = snapshot()
        item["request"]["branch"] = "feature/studio-earth-engine"
        self.assertEqual("ALLOW_CREATE", self.decision(item))
        item["refs"]["feature/studio-earth-engine"] = FEATURE
        item["request"]["operation"] = "resume"
        self.assertEqual("BLOCK", self.decision(item))
        item["request"]["branch_issue_verified"] = True
        self.assertEqual("ALLOW_RESUME", self.decision(item))

    def test_green_exact_head_approved_pr_may_merge(self):
        self.assertEqual("ALLOW_MERGE", self.decision(merge_ready()))

    def test_draft_failure_or_unresolved_review_never_merges(self):
        for key, value in (("draft", True), ("checks", "pending"),
                           ("unresolved_threads", 1), ("mergeable", False),
                           ("human_accepted", False)):
            with self.subTest(key=key):
                item = merge_ready()
                item["pull_requests"][0][key] = value
                self.assertEqual("BLOCK", self.decision(item))

    def test_stale_sha_or_missing_explicit_merge_authority_blocks(self):
        for key, value in (("checked_head_sha", OTHER),
                           ("merge_authorized_by_policy", False)):
            with self.subTest(key=key):
                item = merge_ready()
                item["request"][key] = value
                self.assertEqual("BLOCK", self.decision(item))
        item = merge_ready()
        item["pull_requests"][0]["head_sha"] = OTHER
        self.assertEqual("BLOCK", self.decision(item))

    def test_unknown_human_gate_fails_closed(self):
        item = merge_ready()
        del item["pull_requests"][0]["human_gate"]
        self.assertEqual("BLOCK", self.decision(item))

    def test_malformed_observation_timestamp_blocks(self):
        item = snapshot()
        item["observed_at"] = "yesterday"
        self.assertEqual("BLOCK", self.decision(item))

    def test_overlap_blocks_merge_even_with_green_ci(self):
        item = merge_ready()
        item["pull_requests"].append(dict(other_pr(), overlaps_requested=True))
        self.assertEqual("BLOCK", self.decision(item))

    def test_cli_exits_nonzero_on_denied_decision(self):
        item = snapshot()
        item["verified"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(item), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(1, completed.returncode)
        self.assertEqual("BLOCK", json.loads(completed.stdout)["decision"])


if __name__ == "__main__":
    unittest.main()
