#!/usr/bin/env python3
"""Experimental trusted-local coordination for an explicitly authorized consumer run."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Standalone CLI and importlib-based test loaders both use these local modules.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import branch_preflight
import governed_execution
import engineering_run
import local_pre_pr_runner
from validate_agent_command import validate_command


class ExecutionLoopError(ValueError):
    pass


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def gh_json(arguments: list[str]) -> list[Any]:
    """Parse paginated JSON streams without depending on newer gh --slurp."""
    completed = subprocess.run(['gh', *arguments], capture_output=True, text=True, timeout=60, check=False)
    if completed.returncode:
        raise ExecutionLoopError(f'GitHub read failed with exit status {completed.returncode}')
    decoder, values, remaining = json.JSONDecoder(), [], completed.stdout.strip()
    while remaining:
        value, end = decoder.raw_decode(remaining)
        values.append(value)
        remaining = remaining[end:].strip()
    if not values:
        raise ExecutionLoopError('GitHub returned no evidence')
    return values


def github_preflight(envelope: dict[str, Any], expected_head: str) -> dict[str, Any]:
    """Fresh resume-only reconciliation; does not perform any GitHub writes."""
    repo = envelope['repository']
    identifier = repo['identifier']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', identifier):
        raise ExecutionLoopError('Invalid consumer repository identity')
    issue_match = re.search(r'(?:^|#|/issues/)([1-9][0-9]*)$', envelope['task']['issue'])
    if not issue_match:
        raise ExecutionLoopError('Task issue must resolve to a positive issue number')
    if repo['base_ref'] != 'develop' or repo['release_ref'] != 'main':
        raise ExecutionLoopError('This GitHub adapter supports main/develop; supply a compatible adapter for other branch names')

    def pages(endpoint: str) -> list[dict[str, Any]]:
        values = gh_json(['api', '--paginate', f'repos/{identifier}/{endpoint}'])
        if not all(isinstance(value, list) for value in values):
            raise ExecutionLoopError('Incomplete GitHub list response')
        return [item for value in values for item in value]

    issue = gh_json(['api', f'repos/{identifier}/issues/{issue_match.group(1)}'])[0]
    if issue.get('state') != 'open' or 'pull_request' in issue:
        raise ExecutionLoopError('The assigned issue is not an open task')
    refs = {item['name']: item['commit']['sha'] for item in pages('branches?per_page=100')}
    pulls = []
    for pr in pages('pulls?state=open&per_page=100'):
        source = pr['head']['repo']
        if not source or source['full_name'].lower() != identifier.lower():
            raise ExecutionLoopError('Fork PR requires explicit reconciliation')
        links = set(re.findall(r'(?im)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|progress(?:e[sd])?)\s+#([0-9]+)\b', pr.get('body') or ''))
        if len(links) != 1:
            raise ExecutionLoopError(f'PR #{pr["number"]} issue linkage is ambiguous')
        checks = gh_json(['pr', 'view', str(pr['number']), '--repo', identifier, '--json',
                          'headRefOid,statusCheckRollup,reviewDecision,mergeable'])[0]
        if checks['headRefOid'] != pr['head']['sha']:
            raise ExecutionLoopError('PR head changed during reconciliation')
        owner, name = identifier.split('/')
        query = 'query($owner:String!,$name:String!,$number:Int!,$endCursor:String){repository(owner:$owner,name:$name){pullRequest(number:$number){headRefOid reviewThreads(first:100,after:$endCursor){nodes{isResolved} pageInfo{hasNextPage endCursor}}}}}'
        thread_pages = gh_json(['api', 'graphql', '--paginate', '-f', 'query=' + query,
                               '-f', 'owner=' + owner, '-f', 'name=' + name, '-F', 'number=' + str(pr['number'])])
        unresolved = 0
        for page in thread_pages:
            if page.get('errors'):
                raise ExecutionLoopError('Incomplete review-thread evidence')
            details = page['data']['repository']['pullRequest']
            if details['headRefOid'] != pr['head']['sha']:
                raise ExecutionLoopError('PR head changed while reading reviews')
            unresolved += sum(thread['isResolved'] is False for thread in details['reviewThreads']['nodes'])
        if details['reviewThreads']['pageInfo']['hasNextPage']:
            raise ExecutionLoopError('Review-thread pagination is incomplete')
        pulls.append({'number': pr['number'], 'state': pr['state'], 'draft': pr['draft'],
                      'head': pr['head']['ref'], 'base': pr['base']['ref'], 'issue': int(next(iter(links))),
                      'head_sha': pr['head']['sha'], 'base_sha': pr['base']['sha'], 'checks_evidence': checks,
                      'unresolved_threads': unresolved})
    final_refs = {item['name']: item['commit']['sha'] for item in pages('branches?per_page=100')}
    if refs != final_refs or refs.get(repo['feature_branch']) != expected_head:
        raise ExecutionLoopError('Remote heads changed or differ from the assigned checkout')
    snapshot = {'verified': True, 'observed_at': datetime.now(timezone.utc).isoformat(), 'refs': refs,
                'pull_requests': pulls, 'request': {'operation': 'resume', 'issue': int(issue_match.group(1)),
                                                  'branch': repo['feature_branch']}}
    decision = branch_preflight.evaluate(snapshot)
    if decision['decision'] != 'ALLOW_RESUME':
        raise ExecutionLoopError(decision['reason'])
    return {'snapshot': snapshot, 'decision': decision}


def run_worker(command: list[str], root: Path, environment: dict[str, str], timeout: float) -> subprocess.CompletedProcess:
    """Terminate the worker process group on timeout; never replay it here."""
    process = subprocess.Popen(command, cwd=root, env=environment, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def checkout_identity(envelope: dict[str, Any], checkout: Path) -> dict[str, str]:
    repo = envelope['repository']
    git = lambda *args: local_pre_pr_runner._git(checkout, *args)
    if Path(git('rev-parse', '--show-toplevel')).resolve() != checkout:
        raise ExecutionLoopError('Checkout must be the actual Git root')
    identifier = repo['identifier']
    if git('remote', 'get-url', 'origin') not in (
        f'https://github.com/{identifier}', f'https://github.com/{identifier}.git',
        f'git@github.com:{identifier}.git', f'ssh://git@github.com/{identifier}.git',
    ):
        raise ExecutionLoopError('Checkout origin differs from the authorized consumer')
    if git('symbolic-ref', '--quiet', '--short', 'HEAD') != repo['feature_branch']:
        raise ExecutionLoopError('Checkout is not on the authorized feature branch')
    if git('status', '--porcelain', '--untracked-files=all'):
        raise ExecutionLoopError('Checkout must be clean')
    if subprocess.run(['git', '-C', str(checkout), 'merge-base', '--is-ancestor', repo['base_commit'], 'HEAD'],
                      capture_output=True, timeout=15, check=False).returncode:
        raise ExecutionLoopError('Authorized base is not an ancestor of HEAD')
    return {'head': git('rev-parse', 'HEAD'), 'branch': repo['feature_branch'], 'base': repo['base_commit']}


def execute(policy: dict[str, Any], request: dict[str, Any], checkout: Path, storage: Path,
            worker_command: list[str] | None = None, *, reconcile: Callable = github_preflight) -> dict[str, Any]:
    """Coordinate trusted worker, local checks and independent result verification.

    Trusted workers and repository checks are arbitrary host processes, not an
    OS sandbox. This function deliberately does not publish, merge, or promote.
    """
    envelope = governed_execution.authorize_execution(policy, request)
    if envelope['authorization']['allowed'] is not True:
        raise ExecutionLoopError('Execution not authorized: ' + '; '.join(envelope['authorization']['reasons']))
    if envelope['executor'] != {'adapter': 'local-checkout', 'provider': 'local'}:
        raise ExecutionLoopError('Executor must be the explicit trusted local-checkout adapter')
    root, outside = checkout.resolve(strict=True), storage.resolve()
    if outside == root or root in outside.parents:
        raise ExecutionLoopError('Run journal must remain outside the consumer checkout')
    if storage.is_symlink():
        raise ExecutionLoopError('Run storage symlinks are prohibited')
    run_id = envelope['run_id']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', run_id):
        raise ExecutionLoopError('Unsafe run identifier')
    run_dir = outside / run_id
    if run_dir.is_symlink():
        raise ExecutionLoopError('Run directory symlinks are prohibited')
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in ('journal.json', 'run.lock'):
        if (run_dir / name).is_symlink():
            raise ExecutionLoopError('Journal symlinks are prohibited')
    command = worker_command
    if command is not None and (not command or not all(isinstance(arg, str) and arg and '\x00' not in arg for arg in command)):
        raise ExecutionLoopError('Worker command must be a nonempty argument array')
    if command is not None and validate_command(command)['status'] != 'passed':
        raise ExecutionLoopError('Worker command attempts to bypass required validation')
    identity = fingerprint({'policy': policy, 'request': request, 'worker_command': command, 'checkout': str(root)})
    journal = run_dir / 'journal.json'
    with (run_dir / 'run.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ExecutionLoopError('Another executor owns this run') from exc
        if journal.exists():
            state = json.loads(journal.read_text())
            if state.get('identity') != identity:
                raise ExecutionLoopError('Run identity changed; do not reuse its evidence')
            if state['phase'] in ('worker_running', 'validating'):
                state.update(phase='blocked', reason='Interrupted subprocess requires reconciliation; it will not be replayed')
                write_json(journal, state)
                ledger_path = run_dir / 'engineering-run.json'
                if ledger_path.exists():
                    ledger = json.loads(ledger_path.read_text())
                    ledger['outcome']['status'] = 'blocked'
                    write_json(ledger_path, ledger)
                return state
            if state['phase'] in ('ready_for_pr', 'blocked'):
                if state['phase'] == 'ready_for_pr':
                    if checkout_identity(envelope, root)['head'] != state['head_commit']:
                        raise ExecutionLoopError('Validated head changed; obtain new execution evidence')
                    for name, checksum in state['artifacts'].items():
                        if fingerprint(json.loads((run_dir / name).read_text())) != checksum:
                            raise ExecutionLoopError('Stored execution evidence changed')
                    validation = json.loads((run_dir / 'validation.json').read_text())
                    for index, check in enumerate(validation['verification'], 1):
                        actual = hashlib.sha256((run_dir / 'validation' / f'check-{index}.log').read_bytes()).hexdigest()
                        if check['evidence'] != 'sha256:' + actual:
                            raise ExecutionLoopError('Stored validation log changed')
                    before = json.loads((run_dir / 'preflight.json').read_text())
                    current = reconcile(envelope, state['original_head'])
                    if current['snapshot']['refs'] != before['snapshot']['refs']:
                        raise ExecutionLoopError('Remote heads moved since this evidence was collected')
                return state
            raise ExecutionLoopError('Unknown or incomplete journal; inspect before resuming')
        state: dict[str, Any] = {'created_at': datetime.now(timezone.utc).isoformat(), 'identity': identity, 'run_id': run_id, 'phase': 'authorized', 'events': [],
                                 'delivery': {'pr_creation_allowed': False, 'merge_allowed': False}}

        def save(phase: str, **data: Any) -> None:
            state.update(data, phase=phase)
            state['events'].append({'phase': phase, 'at': datetime.now(timezone.utc).isoformat()})
            write_json(journal, state)
            names = {'worker_running': 'builder_assigned', 'validating': 'verification_started', 'ready_for_pr': 'verification_passed'}
            events = [{'name': names[event['phase']], 'at': event['at']} for event in state['events'] if event['phase'] in names]
            ledger = engineering_run.build_engineering_run(
                run_id=run_id, created_at=state['created_at'],
                task={'goal': envelope['task']['goal'], 'workflow': 'governed-consumer-execution', 'source': {'issue': envelope['task']['issue']}},
                dimensions={'repository': envelope['repository']['identifier'], 'task_class': envelope['task']['task_class'],
                            'worker': envelope['worker'], 'executor': envelope['executor'], 'service_tier': 'execution-prototype',
                            'autonomy': 'supervised', 'mode': 'production', 'trust_boundary': 'trusted-local-not-sandboxed'},
                events=events, reliability={'first_pass_verification': True if phase == 'ready_for_pr' else None,
                                           'eventual_verification': True if phase == 'ready_for_pr' else None, 'ci_passed': None},
                outcome={'status': 'verified' if phase == 'ready_for_pr' else 'blocked' if phase == 'blocked' else 'planned'},
            )
            # A local process is not an OS security monitor. Unknown safety and
            # human-effort telemetry must not become fabricated zeroes.
            ledger['safety'] = {key: None for key in ledger['safety']}
            ledger['autonomy']['human_interventions'] = None
            write_json(run_dir / 'engineering-run.json', ledger)

        started = time.monotonic()
        try:
            initial = checkout_identity(envelope, root)
            # This adapter cannot measure provider billing. Never invent a zero.
            budgets = envelope['budgets']
            if 'max_cost_usd' in budgets:
                raise ExecutionLoopError('A cost-bounded run needs a provider with authoritative cost telemetry')
            steps = budgets.get('max_steps')
            minutes = budgets.get('max_elapsed_minutes')
            required = local_pre_pr_runner._checks(envelope)
            if any(validate_command(check['command'])['status'] != 'passed' for check in required):
                raise ExecutionLoopError('Validation command attempts to bypass policy')
            if type(steps) is not int or steps < len(required) + int(command is not None):
                raise ExecutionLoopError('Step budget does not cover worker and mandatory validation')
            if type(minutes) not in (int, float) or minutes <= 0:
                raise ExecutionLoopError('A positive elapsed-time budget is required')
            # Validate all input before the worker is launched. Required command
            # bindings are consumer-owned, not supplied by worker output.
            before = reconcile(envelope, initial['head'])
            write_json(run_dir / 'preflight.json', before)
            write_json(run_dir / 'envelope.json', envelope)
            save('authorized', original_head=initial['head'])
            if command is not None:
                if not {'code.write', 'branch.write'}.issubset(envelope['authorization']['authorized_actions']):
                    raise ExecutionLoopError('Worker execution needs explicit code.write and branch.write authority')
                save('worker_running')
                child_env = dict(os.environ)
                child_env['ENGINEERING_EXECUTION_ENVELOPE'] = str(run_dir / 'envelope.json')
                remaining_seconds = minutes * 60 - (time.monotonic() - started)
                if remaining_seconds <= 0:
                    raise ExecutionLoopError('Preflight exhausted the elapsed-time budget')
                completed = run_worker(command, root, child_env, remaining_seconds)
                # Keep only a digest of potentially sensitive worker logs.
                state['worker'] = {'return_code': completed.returncode,
                                   'log_sha256': hashlib.sha256(completed.stdout + b'\n' + completed.stderr).hexdigest()}
                if completed.returncode:
                    raise ExecutionLoopError('Worker failed; inspect the trusted provider and reconcile before retrying')
            current = checkout_identity(envelope, root)
            if current['head'] == envelope['repository']['base_commit']:
                raise ExecutionLoopError('Worker did not produce a feature commit')
            # Observe local source facts independently of worker claims.
            git = lambda *args: local_pre_pr_runner._git(root, *args)
            commits = git('rev-list', '--reverse', envelope['repository']['base_commit'] + '..HEAD').splitlines()
            paths = subprocess.check_output(['git', '-C', str(root), 'diff', '--name-only', '-z', envelope['repository']['base_commit'], 'HEAD'], text=True).split('\0')
            paths = [path for path in paths if path]
            for path in paths:
                if not governed_execution._allowed(path, envelope['scope']['allowed_paths']) or governed_execution._allowed(path, envelope['scope']['protected_paths']):
                    raise ExecutionLoopError('Observed worker diff violates authorized scope')
            # A trusted worker may commit locally, but may not move remote refs.
            after = reconcile(envelope, initial['head'])
            if after['snapshot']['refs'] != before['snapshot']['refs']:
                raise ExecutionLoopError('Remote refs changed during worker execution')
            remaining = minutes - (time.monotonic() - started) / 60
            if remaining <= 0:
                raise ExecutionLoopError('Worker exhausted the elapsed-time budget')
            validation_envelope = json.loads(json.dumps(envelope))
            validation_envelope['budgets']['max_elapsed_minutes'] = remaining
            validation_envelope['budgets']['max_steps'] = steps - int(command is not None)
            save('validating', head_commit=current['head'])
            validation = local_pre_pr_runner.validate(validation_envelope, root, run_dir / 'validation')
            if validation['status'] != 'passed':
                raise ExecutionLoopError('Required pre-PR validation failed')
            # Preserve honest outcomes: zero-test output is not evidence of a suite.
            for log in (run_dir / 'validation').glob('check-*.log'):
                text = log.read_text(errors='replace')
                if re.search(r'\bRan 0 tests\b|(?m:^# tests 0$)', text):
                    raise ExecutionLoopError('A required suite executed zero tests')
            if checkout_identity(envelope, root)['head'] != current['head']:
                raise ExecutionLoopError('Worker head changed during verification')
            after_validation = reconcile(envelope, initial['head'])
            if after_validation['snapshot']['refs'] != before['snapshot']['refs']:
                raise ExecutionLoopError('Remote refs changed during validation')
            result = {'schema_version': 'worker-execution-result/v1', 'run_id': run_id,
                      'executor': {**envelope['executor'], 'execution_id': run_id + '-local'},
                      'repository': {'identifier': envelope['repository']['identifier'], 'base_commit': initial['base'],
                                     'branch': initial['branch'], 'head_commit': current['head'], 'commits': commits},
                      'actions': ['code.write', 'branch.write'] if command is not None else [], 'changed_paths': paths,
                      'verification': validation['verification'],
                      'budget': {'steps': validation['budget']['steps'] + int(command is not None),
                                 'elapsed_ms': int((time.monotonic() - started) * 1000), 'retries': 0, 'cost_usd': None},
                      'security': {'consequential_actions_attempted': [], 'consequential_actions_blocked': []},
                      'direct_shared_branch_writes': 0}
            verification = governed_execution.verify_worker_result(envelope, result)
            if verification['status'] != 'verified':
                raise ExecutionLoopError('Independent worker-result verification rejected this run')
            artifacts = {'preflight.json': fingerprint(before), 'envelope.json': fingerprint(envelope)}
            for name, value in (('validation.json', validation), ('worker-result.json', result), ('worker-verification.json', verification)):
                write_json(run_dir / name, value)
                artifacts[name] = fingerprint(value)
            # Readiness is evidence, not a persistent PR/merge permission token.
            save('ready_for_pr', artifacts=artifacts, human_gates=envelope['human_gates'],
                 next_action='Obtain fresh live delivery preflight before publishing a PR; honor human and CI gates')
        except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
            save('blocked', reason=str(exc) if isinstance(exc, (ExecutionLoopError, governed_execution.GovernedExecutionError, local_pre_pr_runner.RunnerError)) else type(exc).__name__)
        return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('policy', 'request', 'checkout', 'storage'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--worker-command', type=Path, help='Trusted operator-owned JSON argument array; never inferred from an image or issue body')
    args = parser.parse_args()
    try:
        policy, request = (json.loads(path.read_text()) for path in (args.policy, args.request))
        worker = json.loads(args.worker_command.read_text()) if args.worker_command else None
        report = execute(policy, request, args.checkout, args.storage, worker)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report['phase'] == 'ready_for_pr' else 1
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({'phase': 'blocked', 'reason': type(exc).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
