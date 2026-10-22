from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import jsonschema
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('consumer_execution_loop', ROOT / 'scripts/consumer_execution_loop.py')
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL, text=True).strip()


class ConsumerExecutionLoopTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.root, self.storage = self.home / 'consumer', self.home / 'runs'
        self.root.mkdir()
        git(self.root, 'init', '-q', '-b', 'develop')
        git(self.root, 'config', 'user.name', 'Executor Test')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'remote', 'add', 'origin', 'https://github.com/acme/widget.git')
        (self.root / '.gitignore').write_text('__pycache__/\n')
        (self.root / 'value.py').write_text('def value(): return 1\n')
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_value.py').write_text('import unittest\nfrom value import value\nclass Values(unittest.TestCase):\n def test_value(self): self.assertEqual(value(), 2)\n def test_type(self): self.assertIsInstance(value(), int)\n')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-qm', 'base')
        self.base = git(self.root, 'rev-parse', 'HEAD')
        self.branch = 'feature/issue-1-value'
        git(self.root, 'switch', '-qc', self.branch)
        self.policy = {'schema_version': 'engineering-policy/v1',
                       'branches': {'release': 'main', 'integration': 'develop', 'temporary_prefixes': ['feature/']},
                       'review': {'pull_requests_required': True, 'required_checks': ['Consumer CI'], 'human_approval_for': ['release']},
                       'delivery': {'implementation_target': 'integration', 'direct_release_writes': False},
                       'permissions': {'read': {'actions': ['repository.read']}, 'bounded_write': {'actions': ['branch.write', 'code.write', 'pr.create']}, 'consequential_write': {'actions': ['release.write']}},
                       'protected_paths': ['engineering-policy.json', '.github/**'],
                       'validation': {'stages': [{'id': 'tests', 'stage': 'completion_gate', 'capability': 'test.python', 'required': True,
                                                  'command': [Path(sys.executable).name, '-m', 'unittest', 'discover', '-s', 'tests']}]},
                       'execution_budgets': {'max_steps': 5, 'max_elapsed_minutes': 1, 'max_retries': 0}}
        self.request = {'schema_version': 'governed-execution-request/v1', 'run_id': 'run-1',
                        'repository': {'identifier': 'acme/widget', 'base_ref': 'develop', 'target_ref': 'develop', 'base_commit': self.base, 'feature_branch': self.branch},
                        'task': {'issue': '1', 'goal': 'Fix value', 'task_class': 'feature'},
                        'worker': {'adapter': 'test-builder', 'provider': 'fixture'}, 'executor': {'adapter': 'local-checkout', 'provider': 'local'},
                        'requested_actions': ['repository.read', 'code.write', 'branch.write', 'pr.create'],
                        'scope': {'allowed_paths': ['value.py'], 'protected_paths': []}, 'human_gates': ['visual_acceptance'], 'change_classes': []}
        self.worker = [sys.executable, '-c', "from pathlib import Path; import subprocess; Path('value.py').write_text('def value(): return 2\\n'); subprocess.run(['git','add','value.py'],check=True); subprocess.run(['git','commit','-qm','fix'],check=True)"]
        self.calls = 0

    def reconcile(self, envelope, expected_head):
        self.calls += 1
        return {'snapshot': {'refs': {'main': self.base, 'develop': self.base, self.branch: self.base}}, 'decision': {'decision': 'ALLOW_RESUME'}}

    def run_loop(self, worker=True, **kwargs):
        return module.execute(self.policy, self.request, self.root, self.storage,
                              self.worker if worker else None, reconcile=kwargs.get('reconcile', self.reconcile))

    @property
    def journal(self): return self.storage / 'run-1/journal.json'

    def test_real_worker_commits_real_tests_verify_and_remain_outside_checkout(self):
        state = self.run_loop()
        self.assertEqual(state['phase'], 'ready_for_pr', state)
        self.assertNotEqual(git(self.root, 'rev-parse', 'HEAD'), self.base)
        self.assertEqual(git(self.root, 'status', '--porcelain'), '')
        self.assertEqual(self.calls, 3)
        result = json.loads((self.storage / 'run-1/worker-result.json').read_text())
        self.assertEqual(result['changed_paths'], ['value.py'])
        self.assertEqual(result['verification'][0]['exit_code'], 0)
        self.assertIsNone(result['budget']['cost_usd'])
        self.assertFalse(state['delivery']['merge_allowed'])
        self.assertIn('visual_acceptance', state['human_gates'])
        ledger = json.loads((self.storage / 'run-1/engineering-run.json').read_text())
        self.assertEqual(ledger['schema_version'], 'engineering-run/v1')
        self.assertEqual(ledger['outcome']['status'], 'verified')
        self.assertIsNone(ledger['safety']['safe'])
        self.assertIsNone(ledger['reliability']['ci_passed'])
        jsonschema.validate(result, json.loads((ROOT / 'schemas/worker-execution-result-v1.schema.json').read_text()))
        jsonschema.validate(ledger, json.loads((ROOT / 'schemas/engineering-run-v1.schema.json').read_text()))

    def test_completed_run_does_not_repeat_worker_or_validation(self):
        first = self.run_loop()
        self.assertEqual(first['phase'], 'ready_for_pr', first)
        head = git(self.root, 'rev-parse', 'HEAD')
        with patch.object(module.local_pre_pr_runner, 'validate', side_effect=AssertionError('must not rerun')):
            self.assertEqual(self.run_loop()['phase'], 'ready_for_pr')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), head)

    def test_denied_live_preflight_prevents_worker_execution(self):
        def denied(*args): raise module.ExecutionLoopError('Live state unavailable')
        state = self.run_loop(reconcile=denied)
        self.assertEqual(state['phase'], 'blocked')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), self.base)

    def test_missing_consumer_command_binding_fails_before_worker(self):
        del self.policy['validation']['stages'][0]['command']
        with self.assertRaisesRegex(module.ExecutionLoopError, 'not authorized'):
            self.run_loop()
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), self.base)

    def test_wrong_branch_is_rejected_before_worker_dispatch(self):
        git(self.root, 'switch', '-q', 'develop')
        state = self.run_loop()
        self.assertEqual(state['phase'], 'blocked')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), self.base)
        self.assertIn('feature branch', state['reason'])

    def test_dirty_checkout_is_preserved_without_worker_dispatch(self):
        (self.root / 'notes.txt').write_text('user work')
        state = self.run_loop()
        self.assertEqual(state['phase'], 'blocked')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), self.base)
        self.assertEqual((self.root / 'notes.txt').read_text(), 'user work')

    def test_missing_worker_authority_blocks_before_dispatch(self):
        self.request['requested_actions'].remove('code.write')
        state = self.run_loop()
        self.assertEqual(state['phase'], 'blocked')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), self.base)

    def test_unauthorized_release_action_fails_closed(self):
        self.request['requested_actions'].append('release.write')
        with self.assertRaisesRegex(module.ExecutionLoopError, 'not authorized'):
            self.run_loop()

    def test_local_scope_violation_is_rejected_before_checks(self):
        self.request['scope']['allowed_paths'] = ['other.py']
        state = self.run_loop()
        self.assertEqual(state['phase'], 'blocked')
        self.assertIn('scope', state['reason'])
        self.assertFalse((self.storage / 'run-1/validation.json').exists())

    def test_failed_worker_preserves_blocked_journal_and_is_not_replayed(self):
        self.worker = [sys.executable, '-c', 'raise SystemExit(9)']
        state = self.run_loop()
        self.assertEqual(state['phase'], 'blocked')
        self.assertEqual(self.run_loop()['worker']['return_code'], 9)

    def test_test_failure_does_not_create_verified_evidence(self):
        self.worker = [sys.executable, '-c', "from pathlib import Path; import subprocess; Path('value.py').write_text('def value(): return 9\\n'); subprocess.run(['git','add','.'],check=True); subprocess.run(['git','commit','-qm','bad'],check=True)"]
        state = self.run_loop()
        self.assertEqual(state['phase'], 'blocked')
        self.assertIn('validation failed', state['reason'])
        self.assertFalse((self.storage / 'run-1/worker-verification.json').exists())

    def test_zero_test_check_is_not_success(self):
        self.policy['validation']['stages'][0]['command'] = [Path(sys.executable).name, '-c', "import sys; print('Ran 0 tests',file=sys.stderr)"]
        self.assertIn('zero tests', self.run_loop()['reason'])

    def test_unknown_cost_blocks_cost_bounded_execution_before_worker(self):
        self.policy['execution_budgets']['max_cost_usd'] = 0
        state = self.run_loop()
        self.assertIn('cost telemetry', state['reason'])
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), self.base)

    def test_step_budget_reserves_mandatory_checks(self):
        self.policy['execution_budgets']['max_steps'] = 1
        state = self.run_loop()
        self.assertIn('Step budget', state['reason'])
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), self.base)

    def test_changed_assignment_cannot_reuse_journal(self):
        self.run_loop()
        self.request['task']['goal'] = 'Different goal'
        with self.assertRaisesRegex(module.ExecutionLoopError, 'identity changed'):
            self.run_loop()

    def test_interrupted_worker_is_not_replayed(self):
        self.run_loop()
        state = json.loads(self.journal.read_text())
        state['phase'] = 'worker_running'
        module.write_json(self.journal, state)
        head = git(self.root, 'rev-parse', 'HEAD')
        result = self.run_loop()
        self.assertIn('will not be replayed', result['reason'])
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), head)

    def test_concurrent_run_is_excluded(self):
        directory = self.storage / 'run-1'
        directory.mkdir(parents=True)
        with (directory / 'run.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(module.ExecutionLoopError, 'Another executor'):
                self.run_loop()

    def test_evidence_cannot_live_on_consumer_feature_branch(self):
        self.storage = self.root / 'state'
        with self.assertRaisesRegex(module.ExecutionLoopError, 'outside'):
            self.run_loop()

    def test_evidence_tampering_is_rejected_on_resume(self):
        self.run_loop()
        path = self.storage / 'run-1/worker-verification.json'
        value = json.loads(path.read_text()); value['status'] = 'rejected'; module.write_json(path, value)
        with self.assertRaisesRegex(module.ExecutionLoopError, 'evidence changed'):
            self.run_loop()

    def test_new_commit_cannot_reuse_previous_head_evidence(self):
        self.run_loop()
        (self.root / 'value.py').write_text('def value(): return 3\n')
        git(self.root, 'commit', '-qam', 'later')
        with self.assertRaisesRegex(module.ExecutionLoopError, 'head changed'):
            self.run_loop()

    def test_remote_movement_blocks_verified_result(self):
        def moved(envelope, head):
            snapshot = self.reconcile(envelope, head)
            if self.calls > 1: snapshot['snapshot']['refs']['develop'] = 'f' * 40
            return snapshot
        self.assertIn('Remote refs changed', self.run_loop(reconcile=moved)['reason'])

    def test_no_worker_mode_validates_existing_commits(self):
        subprocess.run(self.worker, cwd=self.root, check=True)
        self.assertEqual(self.run_loop(worker=False)['phase'], 'ready_for_pr')

    def test_direct_hook_bypass_is_not_dispatched(self):
        self.worker = ['git', 'commit', '--no-verify']
        with self.assertRaisesRegex(module.ExecutionLoopError, 'bypass'):
            self.run_loop()
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), self.base)

    def test_tampered_log_invalidates_resume(self):
        self.run_loop()
        (self.storage / 'run-1/validation/check-1.log').write_text('fabricated pass')
        with self.assertRaisesRegex(module.ExecutionLoopError, 'log changed'):
            self.run_loop()

    def test_remote_movement_invalidates_cached_readiness(self):
        self.run_loop()
        def moved(envelope, head):
            receipt = self.reconcile(envelope, head)
            receipt['snapshot']['refs']['develop'] = 'f' * 40
            return receipt
        with self.assertRaisesRegex(module.ExecutionLoopError, 'Remote heads moved'):
            self.run_loop(reconcile=moved)

    def test_worker_timeout_terminates_process_and_leaves_no_readiness(self):
        original = module.run_worker
        def limited(command, root, environment, timeout):
            return original(command, root, environment, min(timeout, 0.05))
        self.worker = [sys.executable, '-c', 'import time; time.sleep(30)']
        with patch.object(module, 'run_worker', side_effect=limited):
            state = self.run_loop()
        self.assertEqual(state['phase'], 'blocked')
        self.assertEqual(state['reason'], 'TimeoutExpired')
        self.assertFalse((self.storage / 'run-1/worker-verification.json').exists())

    def test_paginated_json_works_with_old_gh_versions(self):
        response = subprocess.CompletedProcess(['gh'], 0, '[{"name":"one"}]\n[{"name":"two"}]\n', '')
        with patch.object(module.subprocess, 'run', return_value=response):
            self.assertEqual(module.gh_json(['api', '--paginate', 'fixture']), [[{'name': 'one'}], [{'name': 'two'}]])


if __name__ == '__main__': unittest.main()
