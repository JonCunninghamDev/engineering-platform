# Branch and pull-request reconciliation

Status: proposed for Engineering Platform issue #76. This is a conservative, consumer-agnostic clarification to the existing two-long-lived-branch model and human decision gates.

## When to reconcile

Before selecting/resuming a task, creating a temporary branch, opening a PR, pushing potentially conflicting work, and **immediately before integration merge**, obtain fresh GitHub-backed evidence of:

- Repository identity, integration and release head SHAs, all remote temporary branch heads;
- Every open PR **including drafts**, its head/base, linked issue, review state and waiting/blocking status;
- Related issue ownership, overlap and dependencies, CI/check results on the exact PR head SHA, unresolved review threads, and any required human acceptance;
- Whether existing PR/branch operations already completed during a previous interrupted run.

Treat inaccessible state, unknown linkage/overlap, stale SHAs, or incomplete lists as a failed reconciliation. Do not infer GitHub state from conversation memory, a prior tool result, or a successful check on a different commit.

## Deterministic action table

| Situation | Decision |
| --- | --- |
| Same issue or feature already has a branch or draft/open PR | Resume existing issue branch/PR; no duplicate |
| Defect discovered inside unaccepted feature | Fix on same branch/PR unless human explicitly separates |
| One implementation waits exclusively on CI/review/human acceptance and next is independently scoped | Second temporary implementation branch is allowed if total remains <= 2 |
| Existing work overlaps, dependencies are unknown, or two temporary branches exist | No competing/third branch; reconcile or ask for narrow decision |
| Integration advanced after published feature branch was created | Reassess dependencies; normally merge integration into shared feature and rerun full checks |
| Unpublished, private feature branch needs alignment | Local rebase may be used; never force-push a shared branch |
| Separate features have dependent behavior or overlapping changes | Record upstream-first merge order, synchronize dependent work after upstream merges, rerun CI |
| Current PR is draft, pending/failed, stale, conflicted, or awaits acceptance | Do not merge |
| Exact current PR head checks green and all policy/review/human gates satisfied | Merge only when policy explicitly authorizes the agent for that class |

A reviewed/merged PR is not a license to start a new PR that duplicates its still-active feature effort. Integration is not a staging area for agent convenience.

## Machine-readable preflight

`scripts/branch_preflight.py` is a small deterministic decision helper. It **does not** query GitHub, interpret natural-language requirements, authorize repository writes, or prove freshness. The caller must fetch an authoritative complete GitHub snapshot immediately before acting, assess issue overlap and independence, and populate the required fields. It must refuse the write if evidence is uncertain or the result is `BLOCK`.

Example for creating a *second independent* implementation branch:

```json
{
  "verified": true,
  "observed_at": "2026-10-15T16:00:00Z",
  "refs": {
    "main": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "develop": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "feature/issue-74-scorecards": "cccccccccccccccccccccccccccccccccccccccc"
  },
  "pull_requests": [
    {
      "number": 75,
      "state": "open",
      "draft": true,
      "head": "feature/issue-74-scorecards",
      "base": "develop",
      "issue": 74,
      "waiting": true,
      "overlaps_requested": false
    }
  ],
  "request": {
    "operation": "create",
    "issue": 76,
    "branch": "feature/issue-76-branch-reconciliation",
    "independent_of_active_work": true
  }
}
```

The SHAs and timestamp above are **illustrative fixtures**, not evidence of a current repository state. `waiting`, `overlaps_requested`, and `independent_of_active_work` must be established from actual issue, diff, review and dependency evidence. A guessed `false` overlap is unacceptable. The two-branch limit counts remote temporary implementation branches, including unreviewed work without an open PR. Descriptive consumer branches such as `feature/studio-earth-engine` are valid; issue ownership may be established from a linked PR or authoritative work record rather than branch naming. Resuming a branch without a linked open PR requires `request.branch_issue_verified=true` established from that record. The helper never interprets branch naming as sufficient evidence of ownership.

Run `python scripts/branch_preflight.py /path/to/verified-snapshot.json`. Results are `ALLOW_CREATE`, `ALLOW_RESUME`, `ALLOW_MERGE`, or `BLOCK` (nonzero exit). The decision applies **only** to the requested operation and the observed state; it is not a reusable permission token. For merge, there must be exactly one open PR for the issue; `request.pr_number` must identify it. The non-draft PR must target `develop` and provide `base_sha` and `head_sha` matching the live remote refs. The caller must provide matching `request.checked_base_sha` and `request.checked_head_sha` so an advanced integration branch or newly pushed head cannot silently reuse stale checks. CI checks must be green on that exact validated state; review threads resolved; the PR mergeable; human gate satisfied where applicable; no unresolved overlapping PRs; and explicit repository merge authority provided. Re-fetch and repeat if head or dependency state changes.

## Handoff and enforcement boundary

Record the live repo and refs, issue and PR IDs, dependency decision, head/check evidence, decision and next safe action in the issue/PR. No agent may convert a `BLOCK` into a new branch, forced rebase, silent branch deletion or direct integration write.

This helper is **not yet wired into a live GitHub adapter or CI merge authority**. A consumer adapter must enforce preflight at actual write points, prevent races between snapshot and action, and respect host-specific branch protections. Existing CI and human review gates remain authoritative. A future integration must be separately scoped, tested and approved; do not claim operational enforcement merely because this deterministic helper passes unit tests.

## Compatibility

No public policy schema or reusable workflow inputs change. This addition narrows ambiguous agent behavior without granting new authority. Consumers continue to use their verified pinned platform release; adopt any published update through the normal versioned consumer-upgrade PR.
