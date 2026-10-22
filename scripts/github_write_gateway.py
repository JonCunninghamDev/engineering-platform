#!/usr/bin/env python3
"""Experimental single-control-plane GitHub write adapter; not a global tool sandbox."""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import branch_preflight
import consumer_execution_loop as execution
import governed_execution


class GatewayBlocked(ValueError):
    pass


class GitHubTransport:
    def read(self, arguments: list[str]) -> list[Any]:
        return execution.gh_json(arguments)

    def write(self, method: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = subprocess.run(['gh', 'api', '--method', method, endpoint, '--input', '-'],
                                input=json.dumps(payload), capture_output=True, text=True, timeout=60, check=False)
        if result.returncode:
            # Do not retry an uncertain external write or echo credential-bearing output.
            raise GatewayBlocked(f'GitHub write failed or is uncertain (exit {result.returncode}); reconcile before retrying')
        response = json.loads(result.stdout)
        if response.get('errors'):
            raise GatewayBlocked('GitHub rejected the mutation; reconcile before retrying')
        return response


class ReadOnlyTransport(GitHubTransport):
    """Live negative proofs may read GitHub but cannot mutate any repository."""
    def write(self, method: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise GatewayBlocked('Read-only transport refused a write')


class Gateway:
    def __init__(self, work: dict[str, Any], control_directory: Path, *, transport=None, run_directory: Path | None = None):
        """work is trusted, operator-owned task configuration, never agent payload.

        A deployed host must freeze this configuration, share the same lock/store
        for all writers, and withhold direct write credentials from workers.
        """
        self.work = json.loads(json.dumps(work))
        self.control = control_directory.resolve()
        self.transport = transport or GitHubTransport()
        self.run_directory = run_directory
        self.repo = work.get('repository', '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.repo):
            raise GatewayBlocked('Invalid repository identity')
        if type(work.get('issue')) is not int or work['issue'] <= 0:
            raise GatewayBlocked('An accepted issue is required')
        if not isinstance(work.get('branch'), str) or not work['branch'].startswith(('feature/', 'agent/', 'fix/')):
            raise GatewayBlocked('A temporary implementation branch is required')
        for name in ('base_sha', 'issue_body_sha256'):
            size = 40 if name == 'base_sha' else 64
            if not re.fullmatch('[0-9a-f]{' + str(size) + '}', str(work.get(name, ''))):
                raise GatewayBlocked(f'Trusted work record needs {name}')
        for name in ('allowed_paths', 'change_classes', 'human_gates'):
            value = work.get(name)
            if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                raise GatewayBlocked(f'Trusted work record needs explicit {name}')
        if not work['allowed_paths']:
            raise GatewayBlocked('Accepted file scope must not be empty')
        for path in work['allowed_paths']:
            governed_execution._safe_repo_path(path, 'accepted scope')
        if not isinstance(work.get('relations'), dict):
            raise GatewayBlocked('Explicit active-work dependency assessment is required')

    def _pages(self, endpoint: str) -> list[dict[str, Any]]:
        values = self.transport.read(['api', '--paginate', f'repos/{self.repo}/{endpoint}'])
        if not all(isinstance(value, list) for value in values):
            raise GatewayBlocked('Incomplete paginated GitHub evidence')
        return [item for value in values for item in value]

    def _policy(self, base: str) -> dict[str, Any]:
        contents = self.transport.read(['api', f'repos/{self.repo}/contents/engineering-policy.json?ref={base}'])[0]
        if contents.get('encoding') != 'base64':
            raise GatewayBlocked('Cannot read trusted base-commit policy')
        policy = json.loads(base64.b64decode(contents['content']).decode())
        governed_execution._validate_policy(policy)
        if policy['branches']['integration'] != 'develop' or policy['branches']['release'] != 'main':
            raise GatewayBlocked('This adapter requires the existing main/develop preflight contract')
        if policy['delivery'].get('direct_release_writes') is not False:
            raise GatewayBlocked('Direct release writes must remain prohibited')
        return policy

    def _human_approval(self, pr: dict[str, Any], gates: list[str]) -> bool:
        latest = {}
        reviews = self._pages(f'pulls/{pr["number"]}/reviews?per_page=100')
        for review in sorted(reviews, key=lambda value: value.get('submitted_at') or ''):
            if review['state'] in ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'):
                latest[review['user']['login']] = review
        if any(review['state'] == 'CHANGES_REQUESTED' for review in latest.values()):
            raise GatewayBlocked('Unresolved changes-requested review blocks integration')
        satisfied = set()
        for login, review in latest.items():
            if review['state'] != 'APPROVED' or review.get('commit_id') != pr['head_sha']:
                continue
            permission = self.transport.read(['api', f'repos/{self.repo}/collaborators/{quote(login, safe="")}/permission'])[0]
            if permission.get('permission') not in ('write', 'maintain', 'admin'):
                continue
            for gate in gates:
                if re.search(r'(?im)^Engineering gate:\s*' + re.escape(gate) + r'\s*$', review.get('body') or ''):
                    satisfied.add(gate)
        return set(gates).issubset(satisfied)

    def _readiness(self, policy: dict[str, Any], snapshot: dict[str, Any]) -> None:
        if self.run_directory is None:
            raise GatewayBlocked('Opening a PR requires trusted external pre-PR execution evidence')
        directory = self.run_directory.resolve(strict=True)
        state = json.loads((directory / 'journal.json').read_text())
        if state.get('phase') != 'ready_for_pr' or state.get('policy_sha256') != execution.fingerprint(policy):
            raise GatewayBlocked('Execution readiness is missing or belongs to a different base policy')
        envelope = json.loads((directory / 'envelope.json').read_text())
        result = json.loads((directory / 'worker-result.json').read_text())
        for name, checksum in state.get('artifacts', {}).items():
            if '/' in name or '\\' in name or name.startswith('.'):
                raise GatewayBlocked('Unsafe evidence artifact name')
            if execution.fingerprint(json.loads((directory / name).read_text())) != checksum:
                raise GatewayBlocked('Stored pre-PR evidence changed')
        if not {'envelope.json', 'worker-result.json', 'validation.json', 'worker-verification.json'}.issubset(state.get('artifacts', {})):
            raise GatewayBlocked('Required execution artifacts are missing')
        expected = (self.repo, self.work['branch'], self.work['base_sha'], self.work['head_sha'])
        actual = result.get('repository', {})
        if (actual.get('identifier'), actual.get('branch'), actual.get('base_commit'), actual.get('head_commit')) != expected:
            raise GatewayBlocked('Pre-PR evidence does not match the exact accepted repository/head/base')
        required = [entry for entry in policy.get('validation', {}).get('stages', []) if entry.get('required') is True]
        commands = {entry['id']: entry['command'] for entry in envelope['verification']['pre_pr_commands']}
        if not required or any(not entry.get('command') or commands.get(entry['id']) != entry['command'] for entry in required):
            raise GatewayBlocked('Pre-PR checks are not bound to current repository-owned commands')
        if any(not governed_execution._allowed(path, self.work['allowed_paths']) or governed_execution._allowed(path, policy['protected_paths']) for path in result['changed_paths']):
            raise GatewayBlocked('Worker result exceeds the accepted publication scope')
        allowed_actions = set(policy['permissions']['read']['actions'] + policy['permissions']['bounded_write']['actions'])
        if not set(result['actions']).issubset(allowed_actions):
            raise GatewayBlocked('Worker actions exceed current base-policy authority')
        verification = governed_execution.verify_worker_result(envelope, result)
        if verification != json.loads((directory / 'worker-verification.json').read_text()):
            raise GatewayBlocked('Stored verification does not match independently recomputed evidence')
        if verification['status'] != 'verified':
            raise GatewayBlocked('Independent worker-result verification failed')
        reported = {entry['name']: entry for entry in result['verification']}
        for index, entry in enumerate(result['verification'], 1):
            checksum = 'sha256:' + hashlib.sha256((directory / 'validation' / f'check-{index}.log').read_bytes()).hexdigest()
            if entry.get('evidence') != checksum:
                raise GatewayBlocked('Pre-PR check log digest changed')
        if any(reported.get(entry['id'], {}).get('status') != 'passed' for entry in required):
            raise GatewayBlocked('A required consumer check did not execute successfully')
        if actual['head_commit'] != snapshot['refs'].get(self.work['branch']):
            raise GatewayBlocked('Remote head advanced after pre-PR verification')

    def _prepare(self, operation: str, pr_number: int | None) -> tuple[dict, dict, dict]:
        envelope = {'repository': {'identifier': self.repo, 'base_ref': 'develop', 'release_ref': 'main',
                                   'feature_branch': self.work['branch']}, 'task': {'issue': str(self.work['issue'])}}
        snapshot = execution.github_snapshot(envelope, reader=self.transport.read)
        if snapshot['refs']['develop'] != self.work['base_sha'] or snapshot['issue_body_sha256'] != self.work['issue_body_sha256']:
            raise GatewayBlocked('Accepted base or task scope changed; reconcile the assignment')
        policy = self._policy(snapshot['refs']['develop'])
        actions = policy['permissions']['bounded_write']['actions']
        required_action = {'create_branch': 'branch.write', 'open_draft_pr': 'draft.write', 'enqueue_merge': 'merge.integration'}[operation]
        # pr.create also authorizes draft creation, never bypassing any gate.
        permitted = required_action in actions or operation == 'open_draft_pr' and 'pr.create' in actions
        if operation != 'create_branch' and snapshot['refs'].get(self.work['branch']) != self.work.get('head_sha'):
            raise GatewayBlocked('Accepted head changed; old CI/review evidence cannot authorize it')
        for pr in snapshot['pull_requests']:
            relation = self.work['relations'].get(str(pr['number']), {})
            overlapping = any(governed_execution._allowed(path, self.work['allowed_paths']) for path in pr['file_paths'])
            pr['overlaps_requested'] = not (relation.get('relationship') == 'independent' and not overlapping)
            statuses = pr['checks_evidence']['statusCheckRollup']
            good = bool(statuses) and all(self._success(check) for check in statuses)
            waiting = relation.get('waiting_on')
            pr['waiting'] = waiting == 'human_review' and good and pr['checks_evidence'].get('reviewDecision') != 'CHANGES_REQUESTED'
            if waiting == 'ci':
                pr['waiting'] = bool(statuses) and any(check.get('status') != 'COMPLETED' for check in statuses) and not any(check.get('conclusion') in ('FAILURE', 'CANCELLED', 'TIMED_OUT') for check in statuses)
        request = snapshot['request']
        request.update(operation='create' if operation == 'create_branch' else 'merge' if operation == 'enqueue_merge' else 'resume',
                       independent_of_active_work=all(pr['overlaps_requested'] is False and pr['waiting'] for pr in snapshot['pull_requests'] if pr['issue'] != self.work['issue']))
        if operation == 'open_draft_pr':
            if any(pr['issue'] == self.work['issue'] or pr['head'] == self.work['branch'] for pr in snapshot['pull_requests']):
                raise GatewayBlocked('Resume the existing PR instead of opening a duplicate')
            # Ownership comes from the frozen operator task record plus exact
            # live issue body hash, not from a model-supplied true/false flag.
            request['branch_issue_verified'] = True
            self._readiness(policy, snapshot)
        if operation == 'enqueue_merge':
            selected = [pr for pr in snapshot['pull_requests'] if pr['number'] == pr_number and pr['issue'] == self.work['issue']]
            if len(selected) != 1:
                raise GatewayBlocked('The selected PR does not match the accepted task')
            pr = selected[0]
            if any(not governed_execution._allowed(path, self.work['allowed_paths']) or governed_execution._allowed(path, policy['protected_paths']) for path in pr['file_paths']):
                raise GatewayBlocked('Selected PR exceeds accepted scope or changes protected policy')
            required_checks = policy['review']['required_checks']
            pr['checks'] = 'success' if all(any(self._name(check) == name and self._success(check) for check in pr['checks_evidence']['statusCheckRollup']) and
                                               not any(self._name(check) == name and not self._success(check) for check in pr['checks_evidence']['statusCheckRollup']) for name in required_checks) else 'pending'
            pr['mergeable'] = pr['checks_evidence'].get('mergeable') == 'MERGEABLE'
            gates = list(dict.fromkeys(self.work['human_gates'] + [gate for gate in policy['review']['human_approval_for'] if gate in self.work['change_classes']]))
            pr['human_gate'] = bool(gates)
            pr['human_accepted'] = self._human_approval(pr, gates)
            request.update(pr_number=pr_number, checked_base_sha=self.work['base_sha'], checked_head_sha=self.work['head_sha'], merge_authorized_by_policy=permitted)
        if not permitted and operation != 'enqueue_merge':
            raise GatewayBlocked('Repository base policy does not authorize this operation')
        decision = branch_preflight.evaluate(snapshot)
        if decision['decision'] == 'BLOCK':
            raise GatewayBlocked(decision['reason'])
        if operation == 'enqueue_merge':
            if gates:
                raise GatewayBlocked('Custom human gates require server-enforced gate integration; this adapter will not queue them from a review snapshot alone')
            rules = self._pages('rules/branches/develop')
            checks = {check['context'] for rule in rules if rule['type'] == 'required_status_checks'
                      for check in rule.get('parameters', {}).get('required_status_checks', [])}
            if not any(rule['type'] == 'merge_queue' for rule in rules) or not set(policy['review']['required_checks']).issubset(checks):
                raise GatewayBlocked('A server-enforced merge queue and required checks are necessary; direct merge has no atomic base lease')
        return snapshot, policy, decision

    @staticmethod
    def _name(check: dict) -> str:
        return check.get('name') or check.get('context') or ''

    @staticmethod
    def _success(check: dict) -> bool:
        return check.get('status') == 'COMPLETED' and check.get('conclusion') == 'SUCCESS' or check.get('state') == 'SUCCESS'

    def perform(self, operation: str, *, title: str = '', body: str = '', pr_number: int | None = None, check_only: bool = False) -> dict[str, Any]:
        if operation not in ('create_branch', 'open_draft_pr', 'enqueue_merge'):
            raise GatewayBlocked('Unsupported operation; direct merge and release writes are unavailable')
        if operation == 'open_draft_pr':
            links = set(re.findall(r'(?im)\b(?:progress(?:e[sd])?|close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#([0-9]+)\b', body))
            if not title.strip() or links != {str(self.work['issue'])}:
                raise GatewayBlocked('Draft title and unambiguous accepted-issue linkage are required')
        self.control.mkdir(mode=0o700, parents=True, exist_ok=True)
        prefix = hashlib.sha256(self.repo.encode()).hexdigest()
        lock_path, journal = self.control / (prefix + '.lock'), self.control / (prefix + '.json')
        if lock_path.is_symlink() or journal.is_symlink():
            raise GatewayBlocked('Control-plane symlinks are prohibited')
        with lock_path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise GatewayBlocked('Another gateway write owns this repository lock') from exc
            if journal.exists() and json.loads(journal.read_text()).get('status') == 'write_pending':
                raise GatewayBlocked('An earlier write outcome is uncertain; reconcile it before another write')
            record = {'id': uuid.uuid4().hex, 'events': [], 'operation': operation, 'repository': self.repo, 'issue': self.work['issue'],
                      'branch': self.work['branch'], 'at': datetime.now(timezone.utc).isoformat(), 'status': 'checking'}
            def persist():
                record['events'].append({'status': record['status'], 'at': datetime.now(timezone.utc).isoformat()})
                execution.write_json(self.control / (prefix + '.' + record['id'] + '.json'), record)
                execution.write_json(journal, record)

            try:
                snapshot, policy, decision = self._prepare(operation, pr_number)
                # Re-fetch at the actual write boundary. No caller snapshot or
                # caller-provided merge/approval boolean is accepted by this API.
                refreshed, refreshed_policy, _ = self._prepare(operation, pr_number)
                first = {key: value for key, value in snapshot.items() if key != 'observed_at'}
                second = {key: value for key, value in refreshed.items() if key != 'observed_at'}
                if first != second or policy != refreshed_policy:
                    raise GatewayBlocked('GitHub evidence changed at the write boundary')
                if check_only:
                    return {**record, 'status': 'checked', 'decision': decision, 'writes': 0}
                record.update(status='write_pending', head_sha=self.work.get('head_sha'), base_sha=self.work['base_sha'])
                persist()
                if operation == 'create_branch':
                    response = self.transport.write('POST', f'repos/{self.repo}/git/refs', {'ref': 'refs/heads/' + self.work['branch'], 'sha': self.work['base_sha']})
                    if response['object']['sha'] != self.work['base_sha']:
                        raise GatewayBlocked('Branch creation returned an unexpected commit')
                    record['result'] = {'branch': self.work['branch'], 'sha': response['object']['sha']}
                    refs = {entry['name']: entry['commit']['sha'] for entry in self._pages('branches?per_page=100')}
                    if refs.get('develop') != self.work['base_sha'] or refs.get(self.work['branch']) != self.work['base_sha'] or sum(name.startswith(branch_preflight.TEMPORARY) for name in refs) > 2:
                        raise GatewayBlocked('External branch movement raced with creation; reconcile the created branch without blind deletion')
                elif operation == 'open_draft_pr':
                    if not title.strip():
                        raise GatewayBlocked('A draft PR title is required')
                    response = self.transport.write('POST', f'repos/{self.repo}/pulls', {'title': title, 'body': body,
                        'head': self.work['branch'], 'base': 'develop', 'draft': True})
                    record['result'] = {'pr_number': response.get('number'), 'url': response.get('html_url')}
                    if not response.get('draft') or response['head']['sha'] != self.work['head_sha'] or response['base']['sha'] != self.work['base_sha']:
                        raise GatewayBlocked('Draft creation raced with head/base movement; reconcile the created draft before proceeding')
                    record['result'] = {'pr_number': response['number'], 'url': response['html_url']}
                else:
                    selected = next(pr for pr in refreshed['pull_requests'] if pr['number'] == pr_number)
                    mutation = 'mutation($id:ID!,$head:GitObjectID!){enqueuePullRequest(input:{pullRequestId:$id,expectedHeadOid:$head}){mergeQueueEntry{id}}}'
                    response = self.transport.write('POST', 'graphql', {'query': mutation, 'variables': {'id': selected['node_id'], 'head': self.work['head_sha']}})
                    record['result'] = {'queue_entry': response['data']['enqueuePullRequest']['mergeQueueEntry']['id'], 'merged': False}
                record['status'] = 'applied'
                persist()
                return record
            except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
                # A network failure after write intent is deliberately left
                # pending: a retry could duplicate a side effect that succeeded.
                pending = record['status'] == 'write_pending'
                record.update(status='write_pending' if pending else 'blocked', reason=str(exc) if isinstance(exc, (GatewayBlocked, execution.ExecutionLoopError, governed_execution.GovernedExecutionError)) else type(exc).__name__)
                persist()
                return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True, help='Operator-owned frozen accepted-task configuration')
    parser.add_argument('--control-directory', type=Path, required=True)
    parser.add_argument('--run-directory', type=Path)
    parser.add_argument('--operation', choices=('create_branch', 'open_draft_pr', 'enqueue_merge'), required=True)
    parser.add_argument('--pr', type=int)
    parser.add_argument('--title', default='')
    parser.add_argument('--body-file', type=Path)
    parser.add_argument('--execute', action='store_true', help='Perform guarded writes; default is read-only checking')
    args = parser.parse_args()
    try:
        gateway = Gateway(json.loads(args.work.read_text()), args.control_directory, run_directory=args.run_directory)
        result = gateway.perform(args.operation, title=args.title, body=args.body_file.read_text() if args.body_file else '',
                                 pr_number=args.pr, check_only=not args.execute)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result['status'] in ('applied', 'checked') else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'blocked', 'reason': type(exc).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
