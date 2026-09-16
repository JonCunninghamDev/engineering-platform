#!/usr/bin/env python3
from __future__ import annotations
import argparse,difflib,hashlib,json
from pathlib import PurePosixPath,Path
from typing import Any

def sha256(text:str)->str:return hashlib.sha256(text.encode()).hexdigest()
def unified(path:str,before:str,after:str,operation:str)->str:
    return "".join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile="/dev/null" if operation=="create" else f"a/{path}",tofile=f"b/{path}",lineterm="\n"))
def safe_path(path:str)->bool:
    p=PurePosixPath(path);return bool(path) and not p.is_absolute() and all(x not in {"",".",".."} for x in p.parts) and "\\" not in path
def scope_match(path:str,entry:str)->bool:
    return path.startswith(entry) if entry.endswith("/") else path==entry

def verify(task:dict[str,Any],cs:dict[str,Any])->dict[str,Any]:
    checks=[]
    def check(name,ok,reason):checks.append({"name":name,"status":"passed" if ok else "failed","reason":reason})
    task_id=str(task.get("assignment",{}).get("id",""));plan_id=str(task.get("plan",{}).get("run_id",""));cap=str(task.get("plan",{}).get("capability",""))
    check("schema-linkage",task.get("schema_version")=="builder-task/v1" and cs.get("schema_version")=="change-set/v1","Builder task and change-set must use v1 contracts")
    check("task-linkage",cs.get("task_id")==task_id,"change-set task_id must equal assignment id")
    check("plan-linkage",cs.get("plan_run_id")==plan_id and cs.get("assigned_capability")==cap,"plan run and capability must match Builder task")
    check("workflow-goal",cs.get("workflow")==task.get("workflow") and cs.get("goal")==task.get("goal"),"workflow and goal must match")
    h=cs.get("handoff",{});check("builder-handoff",h.get("target")=="verifier" and h.get("allowed") is True and h.get("execution_status")=="proposed_not_applied","Builder must hand off an unapplied proposal")
    check("zero-write",cs.get("summary",{}).get("actual_write_count")==0,"Basic Builder evidence must record zero repository writes")
    tc=task.get("changes",[]) if isinstance(task.get("changes"),list) else [];cc=cs.get("changes",[]) if isinstance(cs.get("changes"),list) else []
    check("change-count",len(tc)==len(cc) and cs.get("summary",{}).get("change_count")==len(tc),"task, evidence, and summary change counts must agree")
    allowed=task.get("scope",{}).get("allowed_paths",[]);protected=task.get("scope",{}).get("protected_paths",[]);creates=updates=0
    for i,p in enumerate(tc,1):
        e=cc[i-1] if i<=len(cc) else {};path=p.get("path","");op=p.get("operation","");before=p.get("original_content","") if op=="update" else "";after=p.get("proposed_content","")
        scope_ok=safe_path(path) and any(scope_match(path,x) for x in allowed) and not any(scope_match(path,x) for x in protected)
        check(f"change-{i}-scope",scope_ok,f"{path!r} must be safe, allowed, and unprotected")
        check(f"change-{i}-identity",e.get("sequence")==i and e.get("path")==path and e.get("operation")==op and e.get("action")=="WOULD_WRITE","sequence/path/operation/action must match the Builder task")
        check(f"change-{i}-hashes",e.get("before_sha256")== (sha256(before) if op=="update" else None) and e.get("after_sha256")==sha256(after),"hashes are independently recomputed from task content")
        check(f"change-{i}-diff",e.get("diff")==unified(path,before,after,op),"unified diff is independently recomputed from task content")
        creates+=op=="create";updates+=op=="update"
    s=cs.get("summary",{});check("summary-counts",s.get("proposed_write_count")==len(tc) and s.get("create_count")==creates and s.get("update_count")==updates,"summary operation counts must match the task")
    checks.append({"name":"candidate-code-execution","status":"unavailable_basic_tier","reason":"Basic Verifier inspects evidence only and does not execute candidate code"})
    failed=sum(x["status"]=="failed" for x in checks);passed=sum(x["status"]=="passed" for x in checks);unavailable=sum(x["status"]=="unavailable_basic_tier" for x in checks);status="rejected" if failed else "verified"
    return {"schema_version":"verification-report/v1","agent":{"role":"verifier","version":"1.0.0","service_tier":"basic"},"task_id":task_id,"plan_run_id":plan_id,"status":status,"checks":checks,"summary":{"change_count":len(tc),"passed":passed,"failed":failed,"unavailable":unavailable},"execution":{"repository_writes":0,"candidate_code_executions":0},"handoff":{"target":"reviewer","allowed":status=="verified","artifact":"verification-report/v1"}}

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--task",type=Path,required=True);p.add_argument("--change-set",type=Path,required=True);p.add_argument("--output",type=Path);a=p.parse_args();r=verify(json.loads(a.task.read_text()),json.loads(a.change_set.read_text()));text=json.dumps(r,indent=2,sort_keys=True)+"\n"
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text)
    else:print(text,end="")
    return 0 if r["status"]=="verified" else 1
if __name__=="__main__":raise SystemExit(main())
