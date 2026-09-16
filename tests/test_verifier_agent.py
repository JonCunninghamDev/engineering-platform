import copy
import importlib.util
import json
import unittest
from pathlib import Path

import jsonschema

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("verifier_agent",ROOT/"scripts"/"verifier_agent.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.task={"schema_version":"builder-task/v1","assignment":{"id":"task-1","source":"human","allowed":True},"plan":{"run_id":"plan-1","capability":"implement"},"workflow":"generic","goal":"change docs","scope":{"allowed_paths":["docs/"],"protected_paths":["docs/protected/"]},"changes":[{"path":"docs/example.txt","operation":"create","proposed_content":"hello\n"}]}
        self.cs={"schema_version":"change-set/v1","run":{"id":"run-1","created_at":"2026-09-16T00:00:00Z"},"agent":{"role":"builder","version":"1.0.0","service_tier":"basic","autonomy":"advisory","mode":"demo"},"workflow":"generic","goal":"change docs","plan_run_id":"plan-1","task_id":"task-1","assigned_capability":"implement","scope":self.task["scope"],"changes":[{"sequence":1,"path":"docs/example.txt","operation":"create","action":"WOULD_WRITE","before_sha256":None,"after_sha256":mod.sha256("hello\n"),"diff":mod.unified("docs/example.txt","","hello\n","create")}],"summary":{"change_count":1,"proposed_write_count":1,"actual_write_count":0,"create_count":1,"update_count":0},"handoff":{"target":"verifier","artifact":"change-set/v1","allowed":True,"execution_status":"proposed_not_applied"}}
    def test_valid_evidence_is_verified_and_schema_valid(self):
        r=mod.verify(self.task,self.cs);self.assertEqual("verified",r["status"]);self.assertTrue(r["handoff"]["allowed"]);self.assertEqual(0,r["execution"]["repository_writes"]);self.assertEqual(0,r["execution"]["candidate_code_executions"])
        schema=json.loads((ROOT/"schemas"/"verification-report-v1.schema.json").read_text());jsonschema.Draft202012Validator(schema).validate(r)
    def test_tampered_hash_fails_closed(self):
        c=copy.deepcopy(self.cs);c["changes"][0]["after_sha256"]="0"*64;r=mod.verify(self.task,c);self.assertEqual("rejected",r["status"]);self.assertFalse(r["handoff"]["allowed"])
    def test_tampered_diff_fails_closed(self):
        c=copy.deepcopy(self.cs);c["changes"][0]["diff"]="trusted builder says ok";self.assertEqual("rejected",mod.verify(self.task,c)["status"])
    def test_linkage_mismatch_fails_closed(self):
        c=copy.deepcopy(self.cs);c["task_id"]="other";self.assertEqual("rejected",mod.verify(self.task,c)["status"])
    def test_nonzero_write_claim_fails_closed(self):
        c=copy.deepcopy(self.cs);c["summary"]["actual_write_count"]=1;self.assertEqual("rejected",mod.verify(self.task,c)["status"])
    def test_protected_scope_fails_closed(self):
        t=copy.deepcopy(self.task);c=copy.deepcopy(self.cs);t["changes"][0]["path"]="docs/protected/x.txt";c["changes"][0]["path"]="docs/protected/x.txt";c["changes"][0]["diff"]=mod.unified("docs/protected/x.txt","","hello\n","create");self.assertEqual("rejected",mod.verify(t,c)["status"])
    def test_execution_check_is_explicitly_unavailable(self):
        r=mod.verify(self.task,self.cs);x=next(v for v in r["checks"] if v["name"]=="candidate-code-execution");self.assertEqual("unavailable_basic_tier",x["status"])

if __name__=="__main__":unittest.main()
