# GitHub write gateway

Experimental implementation under issue #78. This is an optional **single-control-plane** adapter, not an installed global restriction on agent tools. It composes the existing live GitHub reader, branch-preflight decision helper, consumer execution evidence and repository policy.

## Trusted host boundary

A deployed tool host must freeze the accepted work record, retain its own GitHub writer credential, route every permitted writer through the same gateway and repository lock, and deny workers direct GitHub write credentials and raw write tools. The model-facing API should select an already accepted work ID and operation, not supply arbitrary configuration, policies, snapshots, approval booleans, endpoints or credentials.

The CLI is an operator/development entrypoint. Do not expose arbitrary `--work` or `--control-directory` values to an untrusted coding worker. The accepted work file and control directory must be operator-owned, outside consumer workspaces, shared by all gateway processes and inaccessible for worker edits. A Python adapter cannot prevent a different program from using independent credentials or a different host. Multi-host distributed locking and deployment of this boundary remain acceptance work; they are not claimed by passing local tests.

## Accepted work record

The operator record supplies repository, issue, implementation branch, exact accepted base/head, SHA-256 of the accepted issue body, allowed file scope, declared change classes, explicit human gates and dependency assessments for other PRs. `head_sha` is required for publishing or queueing a specific implementation. The gateway itself reads current policy from `engineering-policy.json` at the integration commit; a feature branch cannot grant itself authority by changing policy.

Example fields (SHAs are illustrative, not authorization):

```json
{
  "repository": "acme/widget",
  "issue": 1,
  "branch": "feature/issue-1-example",
  "base_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "head_sha": "cccccccccccccccccccccccccccccccccccccccc",
  "issue_body_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  "allowed_paths": ["src/", "tests/"],
  "change_classes": ["bounded_implementation"],
  "human_gates": [],
  "relations": {
    "2": {"relationship": "independent", "waiting_on": "human_review"}
  }
}
```

Independence is a trusted task decision, not something inferred merely from different files. The gateway additionally inspects actual PR file lists and refuses a conflicting diff even when the record declares independence. Missing relationships and ambiguous issue ownership fail closed.

## Write paths

Every supported write acquires an exclusive per-repository process lock, gathers all live branches/open/draft PRs, selected issue state/body hash, PR files, current heads, CI/review evidence and paginated review threads, checks base policy, and applies branch preflight. It then repeats the collection at the write boundary. Moved or incomplete evidence blocks the request. No caller-provided snapshot or `merge_authorized_by_policy` boolean is accepted as authority.

- **Create branch:** requires `branch.write`; creates a unique GitHub ref at the accepted integration SHA, never overwriting a branch. Duplicate work, unknown ownership and a third implementation branch are blocked. Post-write ref/quota checks quarantine detected external races; the gateway does not blindly delete a branch that another actor may have changed.
- **Open draft PR:** requires `draft.write` or `pr.create`, exact verified external execution artifacts, matching base policy/head/scope, required repository-owned commands, successful independent worker verification and intact check logs. The body must link unambiguously to the accepted issue. Only a draft is created. If the creation response reveals a head/base race, its known PR number is retained for reconciliation and no delivery permission is granted.
- **Queue integration:** requires explicit `merge.integration` authority, exact head/base/checks, non-draft mergeability, resolved threads and no overlapping/unknown PRs. Review requests and applicable human gates are checked. Custom human gates are **not automatically queued**: a review snapshot alone is not server-enforced gate integration. Such work requires its existing human integration route. Ungated automation additionally requires active server merge-queue rules and every configured required status check. The mutation uses `expectedHeadOid`; the queue revalidates integration changes. An enqueue result is not a merged result.

There is no direct REST merge fallback, force push, branch deletion, production write or release operation. In particular, checking a base SHA locally and then calling the ordinary merge endpoint is insufficient because that endpoint only leases the head. Repositories without server-enforced queue/check support fail closed for automated integration.

GitHub does not offer an atomic "all repository branches and PRs unchanged" transaction for every operation. The shared control-plane lock serializes cooperating writers. Unique ref creation, draft-only PR creation, post-response checks, expected-head queueing and server rules constrain remaining races. Unmanaged external writers and distributed hosts are not made safe by a local lock; quarantine and reconciliation remain necessary.

## Journal and recovery

The control directory retains per-operation evidence records and status events plus the latest repository journal. Write intent is persisted before calling GitHub. An uncertain external write remains `write_pending` and is not retried automatically. The operator must reconcile actual GitHub state and record recovery before another repository write. This prevents a failed response from becoming a duplicated successful side effect. Logs and credentials are not copied into the journal.

The trusted-local execution coordinator now records its policy fingerprint. Older receipts without that binding cannot authorize a new gateway draft: rerun verification under a reconciled new run ID. Existing Basic contracts and policy schemas do not change. The gateway and work-record format are experimental, not a published stable compatibility surface.

## Operator invocation

```bash
python scripts/github_write_gateway.py \
  --work /private/control-plane/accepted-work.json \
  --control-directory /private/control-plane/github-journal \
  --run-directory /private/control-plane/execution-run \
  --operation open_draft_pr \
  --title "Implement accepted task" \
  --body-file /private/control-plane/pr-body.md
```

Default invocation checks only; guarded writes require `--execute`. Queueing accepts `--operation enqueue_merge --pr <number>`. Exit zero means an applied operation or successful check, not a merged/released product. The service integration must preserve the fixed task/credential boundary described above.

## Evidence and remaining acceptance

Tests exercise the actual gateway entrypoints and live reader with a deterministic GitHub transport, covering allowed writes and negative duplicate, concurrent, stale, review, CI, human-gate and tampered-evidence cases. A real read-only GitHub proof passed: a live draft PR was rejected as draft at the enqueue entrypoint before any write-transport call. Its independent read-only transport also prohibited mutation; the unrelated draft was not changed.

This proves the adapter's boundary, not deployment across all existing tools. Before closing #78: human review of shared connector authority; deployment with writer credentials withheld from workers; cross-host coordination if needed; and a real authorized consumer delivery proof through the deployed host. No customer pin or production settings are silently changed by this feature.
