from __future__ import annotations

import base64
import fcntl
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('github_write_gateway', ROOT / 'scripts/github_write_gateway.py')
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)
B, H = 'b' * 40, 'c' * 40


def policy():
    return {'schema_version': 'engineering-policy/v1', 'branches': {'release': 'main', 'integration': 'develop', 'temporary_prefixes': ['feature/']},
            'review': {'required_checks': ['Consumer CI'], 'human_approval_for': ['security'], 'pull_requests_required': True},
            'delivery': {'implementation_target': 'integration', 'direct_release_writes': False},
            'permissions': {'read': {'actions': ['repository.read']}, 'bounded_write': {'actions': ['branch.write', 'code.write', 'draft.write', 'merge.integration']}, 'consequential_write': {'actions': ['release.write']}},
            'protected_paths': ['.github/**', 'engineering-policy.json'],
            'validation': {'stages': [{'id': 'tests', 'stage': 'completion_gate', 'capability': 'test.python', 'required': True, 'command': ['python', '-m', 'unittest']}]},
            'execution_budgets': {'max_steps': 20, 'max_elapsed_minutes': 1, 'max_retries': 0}}


class FakeGitHub:
    def __init__(self):
        self.refs = {'main': 'a' * 40, 'develop': B}
        self.pulls = []
        self.files = {}
        self.reviews = []
        self.policy = policy()
        self.writes = []
        self.branch_reads = 0
        self.move_on_branch_read = None
        self.fail_write = False
        self.queue = True
        self.issue_body = 'Accepted scope'

    def add_pr(self, number=10, issue=1, branch='feature/issue-1-demo', *, draft=False, files=None):
        self.refs[branch] = H
        self.files[number] = files if files is not None else ['src/value.py']
        pr = {'number': number, 'node_id': f'PR_{number}', 'state': 'open', 'draft': draft, 'body': f'Progresses #{issue}',
              'head': {'ref': branch, 'sha': H, 'repo': {'full_name': 'acme/widget'}}, 'base': {'ref': 'develop', 'sha': B}}
        self.pulls.append(pr)
        return pr

    def read(self, arguments):
        if arguments[0] == 'pr':
            number = int(arguments[2]); pr = next(p for p in self.pulls if p['number'] == number)
            return [{'headRefOid': pr['head']['sha'], 'reviewDecision': pr.get('reviewDecision', ''),
                     'mergeable': 'MERGEABLE', 'statusCheckRollup': pr.get('checks', [{'name': 'Consumer CI', 'status': 'COMPLETED', 'conclusion': 'SUCCESS'}])}]
        endpoint = arguments[-1]
        if len(arguments) > 1 and arguments[1] == 'graphql':
            number = int(next(arg.split('=', 1)[1] for arg in arguments if arg.startswith('number=')))
            pr = next(p for p in self.pulls if p['number'] == number)
            return [{'data': {'repository': {'pullRequest': {'headRefOid': pr['head']['sha'], 'baseRefOid': self.refs['develop'],
                    'reviewThreads': {'nodes': [{'isResolved': False}] if pr.get('unresolved') else [], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}}}]
        if 'branches?per_page' in endpoint:
            self.branch_reads += 1
            if self.move_on_branch_read == self.branch_reads: self.refs['develop'] = 'd' * 40
            return [[{'name': name, 'commit': {'sha': sha}} for name, sha in self.refs.items()]]
        if 'pulls?state=open' in endpoint: return [deepcopy(self.pulls)]
        if '/issues/' in endpoint: return [{'state': 'open', 'body': self.issue_body}]
        if '/contents/engineering-policy.json' in endpoint: return [{'encoding': 'base64', 'content': base64.b64encode(json.dumps(self.policy).encode()).decode()}]
        if '/files?' in endpoint:
            number = int(endpoint.split('/pulls/')[1].split('/')[0])
            return [[{'filename': path} for path in self.files[number]]]
        if '/reviews?' in endpoint: return [deepcopy(self.reviews)]
        if '/collaborators/' in endpoint: return [{'permission': 'write'}]
        if 'rules/branches' in endpoint:
            rules = [{'type': 'required_status_checks', 'parameters': {'required_status_checks': [{'context': 'Consumer CI'}]}}]
            if self.queue: rules.append({'type': 'merge_queue'})
            return [rules]
        raise AssertionError(f'Unexpected read: {arguments}')

    def write(self, method, endpoint, payload):
        self.writes.append((method, endpoint, deepcopy(payload)))
        if self.fail_write: raise module.GatewayBlocked('Uncertain external write')
        if endpoint.endswith('/git/refs'):
            branch = payload['ref'].removeprefix('refs/heads/')
            self.refs[branch] = payload['sha']
            return {'object': {'sha': payload['sha']}}
        if endpoint.endswith('/pulls'):
            return {'number': 10, 'html_url': 'https://github.com/acme/widget/pull/10', 'draft': True,
                    'head': {'sha': self.refs[payload['head']]}, 'base': {'sha': self.refs['develop']}}
        if endpoint == 'graphql':
            return {'data': {'enqueuePullRequest': {'mergeQueueEntry': {'id': 'queue-1'}}}}
        raise AssertionError(endpoint)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.api = FakeGitHub()
        self.work = {'repository': 'acme/widget', 'issue': 1, 'branch': 'feature/issue-1-demo', 'base_sha': B, 'head_sha': H,
                     'issue_body_sha256': hashlib.sha256(self.api.issue_body.encode()).hexdigest(), 'allowed_paths': ['src/'],
                     'relations': {}, 'change_classes': [], 'human_gates': []}
        self.run = self.root / 'run'

    def gateway(self):
        return module.Gateway(self.work, self.root / 'control', transport=self.api, run_directory=self.run if self.run.exists() else None)

    def ready(self):
        self.api.refs[self.work['branch']] = H
        self.run.mkdir(); (self.run / 'validation').mkdir()
        request = {'schema_version': 'governed-execution-request/v1', 'run_id': 'run-1',
                   'repository': {'identifier': 'acme/widget', 'base_ref': 'develop', 'target_ref': 'develop', 'base_commit': B, 'feature_branch': self.work['branch']},
                   'task': {'issue': '1', 'goal': 'Fixture', 'task_class': 'feature'}, 'worker': {'adapter': 'fixture', 'provider': 'fixture'}, 'executor': {'adapter': 'local-checkout', 'provider': 'local'},
                   'scope': {'allowed_paths': ['src/'], 'protected_paths': []}, 'requested_actions': ['code.write'], 'change_classes': [], 'human_gates': [], 'verification': {'pre_pr_checks': []}}
        envelope = module.governed_execution.authorize_execution(self.api.policy, request)
        log = b'Ran 2 tests\nOK\n'; (self.run / 'validation/check-1.log').write_bytes(log)
        result = {'schema_version': 'worker-execution-result/v1', 'run_id': 'run-1', 'executor': {'adapter': 'local-checkout', 'provider': 'local', 'execution_id': 'fixture'},
                  'repository': {'identifier': 'acme/widget', 'branch': self.work['branch'], 'base_commit': B, 'head_commit': H, 'commits': [H]},
                  'actions': ['code.write'], 'changed_paths': ['src/value.py'], 'verification': [{'name': 'tests', 'status': 'passed', 'exit_code': 0, 'duration_ms': 2, 'evidence': 'sha256:' + hashlib.sha256(log).hexdigest()}],
                  'budget': {'steps': 1, 'elapsed_ms': 2, 'retries': 0, 'cost_usd': None}, 'security': {'consequential_actions_attempted': [], 'consequential_actions_blocked': []}, 'direct_shared_branch_writes': 0}
        verification = module.governed_execution.verify_worker_result(envelope, result)
        artifacts = {}
        for name, value in [('envelope.json', envelope), ('worker-result.json', result), ('validation.json', {'verification': result['verification']}), ('worker-verification.json', verification)]:
            module.execution.write_json(self.run / name, value); artifacts[name] = module.execution.fingerprint(value)
        module.execution.write_json(self.run / 'journal.json', {'phase': 'ready_for_pr', 'policy_sha256': module.execution.fingerprint(self.api.policy), 'artifacts': artifacts})

    def assert_blocked(self, result):
        self.assertEqual(result['status'], 'blocked', result)
        self.assertEqual(self.api.writes, [])

    def test_branch_creation_uses_fresh_policy_and_two_live_snapshots(self):
        result = self.gateway().perform('create_branch')
        self.assertEqual(result['status'], 'applied', result)
        self.assertEqual(self.api.writes[0], ('POST', 'repos/acme/widget/git/refs', {'ref': 'refs/heads/feature/issue-1-demo', 'sha': B}))
        self.assertGreaterEqual(self.api.branch_reads, 5)

    def test_duplicate_issue_pr_is_never_recreated(self):
        self.api.add_pr()
        self.assert_blocked(self.gateway().perform('create_branch'))

    def test_existing_remote_branch_is_not_overwritten(self):
        self.api.refs[self.work['branch']] = H
        self.assert_blocked(self.gateway().perform('create_branch'))

    def test_two_existing_branches_prevent_a_third(self):
        for number in (2, 3):
            self.api.add_pr(number, number, f'feature/issue-{number}', files=[f'docs/{number}.md'])
            self.work['relations'][str(number)] = {'relationship': 'independent', 'waiting_on': 'human_review'}
        self.assert_blocked(self.gateway().perform('create_branch'))

    def test_unknown_semantic_independence_blocks_even_when_files_differ(self):
        self.api.add_pr(2, 2, 'feature/issue-2', files=['docs/other.md'])
        self.assert_blocked(self.gateway().perform('create_branch'))

    def test_actual_file_overlap_overrides_declared_independence(self):
        self.api.add_pr(2, 2, 'feature/issue-2')
        self.work['relations']['2'] = {'relationship': 'independent', 'waiting_on': 'human_review'}
        self.assert_blocked(self.gateway().perform('create_branch'))

    def test_second_independent_waiting_task_is_allowed(self):
        self.api.add_pr(2, 2, 'feature/issue-2', files=['docs/other.md'])
        self.work['relations']['2'] = {'relationship': 'independent', 'waiting_on': 'human_review'}
        self.assertEqual(self.gateway().perform('create_branch')['status'], 'applied')

    def test_ref_movement_during_collection_blocks_before_write(self):
        self.api.move_on_branch_read = 2
        self.assert_blocked(self.gateway().perform('create_branch'))

    def test_movement_at_second_snapshot_blocks_before_write(self):
        self.api.move_on_branch_read = 3
        self.assert_blocked(self.gateway().perform('create_branch'))

    def test_operator_assignment_is_pinned_to_current_issue_body(self):
        self.api.issue_body = 'Changed scope'
        self.assert_blocked(self.gateway().perform('create_branch'))

    def test_caller_authorization_boolean_cannot_grant_merge(self):
        self.api.add_pr(); self.api.policy['permissions']['bounded_write']['actions'].remove('merge.integration')
        self.work['merge_authorized_by_policy'] = True
        self.assert_blocked(self.gateway().perform('enqueue_merge', pr_number=10))

    def test_draft_merge_is_denied_at_actual_write_entrypoint(self):
        self.api.add_pr(draft=True)
        result = self.gateway().perform('enqueue_merge', pr_number=10)
        self.assert_blocked(result); self.assertIn('Draft', result['reason'])

    def test_new_head_cannot_reuse_old_approval_or_ci(self):
        pr = self.api.add_pr(); pr['head']['sha'] = 'd' * 40; self.api.refs[self.work['branch']] = 'd' * 40
        self.assert_blocked(self.gateway().perform('enqueue_merge', pr_number=10))

    def test_pending_ci_cannot_enqueue(self):
        pr = self.api.add_pr(); pr['checks'] = [{'name': 'Consumer CI', 'status': 'IN_PROGRESS', 'conclusion': None}]
        self.assert_blocked(self.gateway().perform('enqueue_merge', pr_number=10))

    def test_unresolved_threads_cannot_enqueue(self):
        self.api.add_pr()['unresolved'] = True
        self.assert_blocked(self.gateway().perform('enqueue_merge', pr_number=10))

    def test_missing_human_gate_cannot_enqueue(self):
        self.api.add_pr(); self.work['human_gates'] = ['visual_acceptance']
        self.assert_blocked(self.gateway().perform('enqueue_merge', pr_number=10))

    def test_approved_custom_gate_still_needs_server_enforcement(self):
        self.api.add_pr(); self.work['human_gates'] = ['visual_acceptance']
        self.api.reviews = [{'state': 'APPROVED', 'commit_id': H, 'user': {'login': 'maintainer'}, 'submitted_at': '2026-10-22T00:00:00Z', 'body': 'Engineering gate: visual_acceptance'}]
        self.assert_blocked(self.gateway().perform('enqueue_merge', pr_number=10))

    def test_no_queue_means_no_unsafe_direct_merge_fallback(self):
        self.api.add_pr(); self.api.queue = False
        result = self.gateway().perform('enqueue_merge', pr_number=10)
        self.assert_blocked(result); self.assertIn('atomic base lease', result['reason'])

    def test_queue_uses_expected_head_and_never_direct_merge_rest(self):
        self.api.add_pr(); result = self.gateway().perform('enqueue_merge', pr_number=10)
        self.assertEqual(result['status'], 'applied', result)
        self.assertEqual(self.api.writes[0][1], 'graphql')
        self.assertEqual(self.api.writes[0][2]['variables']['head'], H)
        self.assertIn('expectedHeadOid', self.api.writes[0][2]['query'])
        self.assertFalse(result['result']['merged'])

    def test_protected_policy_changes_do_not_enqueue(self):
        self.api.add_pr(files=['engineering-policy.json'])
        self.work['allowed_paths'].append('engineering-policy.json')
        self.assert_blocked(self.gateway().perform('enqueue_merge', pr_number=10))

    def test_opening_draft_requires_real_execution_artifacts(self):
        self.api.refs[self.work['branch']] = H
        self.assert_blocked(self.gateway().perform('open_draft_pr', title='Feature', body='Progresses #1'))

    def test_verified_artifacts_open_only_a_draft(self):
        self.ready(); result = self.gateway().perform('open_draft_pr', title='Feature', body='Progresses #1')
        self.assertEqual(result['status'], 'applied', result)
        self.assertIs(self.api.writes[0][2]['draft'], True)
        self.assertEqual(self.api.writes[0][2]['base'], 'develop')

    def test_ambiguous_issue_linkage_is_not_published(self):
        with self.assertRaisesRegex(module.GatewayBlocked, 'unambiguous'):
            self.gateway().perform('open_draft_pr', title='Feature', body='Progresses #1. Closes #2.')
        self.assertEqual(self.api.writes, [])

    def test_post_creation_race_retains_known_draft_for_reconciliation(self):
        self.ready()
        original = self.api.write
        def raced(method, endpoint, payload):
            response = original(method, endpoint, payload)
            response['head']['sha'] = 'd' * 40
            return response
        self.api.write = raced
        result = self.gateway().perform('open_draft_pr', title='Feature', body='Progresses #1')
        self.assertEqual(result['status'], 'write_pending')
        self.assertEqual(result['result']['pr_number'], 10)
        self.assertEqual(len(self.api.writes), 1)
        with self.assertRaisesRegex(module.GatewayBlocked, 'uncertain'):
            self.gateway().perform('open_draft_pr', title='Feature', body='Progresses #1')

    def test_invalid_check_data_blocks_before_any_write(self):
        pr = self.api.add_pr(); pr['checks'] = []
        self.assert_blocked(self.gateway().perform('enqueue_merge', pr_number=10))

    def test_log_tampering_blocks_draft_creation(self):
        self.ready(); (self.run / 'validation/check-1.log').write_text('invented evidence')
        self.assert_blocked(self.gateway().perform('open_draft_pr', title='Feature', body='Progresses #1'))

    def test_dry_run_never_writes(self):
        result = self.gateway().perform('create_branch', check_only=True)
        self.assertEqual(result['status'], 'checked', result); self.assertEqual(self.api.writes, [])

    def test_uncertain_external_write_is_not_replayed(self):
        self.api.fail_write = True
        self.assertEqual(self.gateway().perform('create_branch')['status'], 'write_pending')
        with self.assertRaisesRegex(module.GatewayBlocked, 'uncertain'):
            self.gateway().perform('create_branch')
        self.assertEqual(len(self.api.writes), 1)

    def test_repository_lock_prevents_concurrent_writers(self):
        gateway = self.gateway(); gateway.control.mkdir()
        name = hashlib.sha256(self.work['repository'].encode()).hexdigest() + '.lock'
        with (gateway.control / name).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(module.GatewayBlocked, 'Another gateway'):
                gateway.perform('create_branch')
        self.assertEqual(self.api.writes, [])

    def test_transport_sends_literal_json_without_a_shell(self):
        directory = self.root / 'bin'; directory.mkdir()
        executable = directory / 'gh'
        executable.write_text('#!' + sys.executable + "\nimport json,sys\nprint(json.dumps({'received':json.load(sys.stdin),'arguments':sys.argv[1:]}))\n")
        executable.chmod(0o755)
        sentinel = self.root / 'not-created'
        payload = {'title': 'literal $(touch ' + str(sentinel) + ')', 'body': 'backticks `and` newlines\nremain data'}
        with patch.dict(os.environ, {'PATH': str(directory) + os.pathsep + os.environ['PATH']}):
            response = module.GitHubTransport().write('POST', 'repos/acme/widget/pulls', payload)
        self.assertEqual(response['received'], payload)
        self.assertFalse(sentinel.exists())

    def test_repository_lock_excludes_a_second_os_process(self):
        gateway = self.gateway(); gateway.control.mkdir()
        name = hashlib.sha256(self.work['repository'].encode()).hexdigest() + '.lock'
        script = "import fcntl,sys; f=open(sys.argv[1],'a'); fcntl.flock(f,fcntl.LOCK_EX); print('locked',flush=True); sys.stdin.read()"
        process = subprocess.Popen([sys.executable, '-c', script, str(gateway.control / name)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'locked')
            with self.assertRaisesRegex(module.GatewayBlocked, 'Another gateway'):
                gateway.perform('create_branch')
            self.assertEqual(self.api.writes, [])
        finally:
            process.communicate(input='', timeout=10)

    def test_unlinked_pr_prevents_ambiguous_snapshot(self):
        self.api.add_pr(2, 2, 'feature/other', files=['docs/other.md'])['body'] = 'No authoritative issue'
        self.assert_blocked(self.gateway().perform('create_branch'))


if __name__ == '__main__': unittest.main()
