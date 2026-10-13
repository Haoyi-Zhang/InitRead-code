"""Benign public Java-to-data regression and separately scoped pipeline costs.

No external serialized input, downloads, exploit cases or historical rewrites.
The independent dense reference supplies exactly the data information available
to every receiving mode. Output must be a fresh directory outside the artifact.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from reproduce_java_conformance import tools, VM
from receiver.producer import admit, packet, MAGIC
from receiver.reference import decide
from receiver.certificate_reference import classify

ROOT = Path(__file__).resolve().parent
MODES = ('certificate', 'eager_same_frame', 'eager_data_only')
SOURCES = ('java/CertifiedReceiver.java', 'java/PublicBoundaryHarness.java',
           'java/DeserializationTraceHarness.java', 'java/ObservationPair.java')


def eager_words(values, links, roots):
    """Same domain checks and final data; zero placeholder, no certificate."""
    admit(values, links, roots)
    return [MAGIC, 1, len(values), len(roots), *values, *links, *roots, 0]


def verify_public(row, truth, wanted):
    """Bind public scalar navigation to dense closure, not a private snapshot."""
    if row['status'] != wanted or row['has_graph'] != (wanted == 'ALLOW'):
        raise AssertionError('decision/publication mismatch')
    if not row['canonical_aliases'] or not row['frozen']:
        raise AssertionError('alias/root-copy mismatch')
    if wanted != 'ALLOW':
        if row['roots'] is not None or row['nodes']:
            raise AssertionError('rejection exposed a node')
    else:
        expected = [[i, truth['values'][i], truth['links'][i]] for i in truth['reachable']]
        if row['roots'] != truth['roots'] or row['nodes'] != expected:
            raise AssertionError('public representation/closure mismatch')
    if row['bytes'] != 27 + 4*row['words']:
        raise AssertionError('actual canonical size mismatch')


def stats(values):
    return {'median': statistics.median(values), 'minimum': min(values), 'maximum': max(values)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--java-home')
    parser.add_argument('--skip-costs', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() or out == ROOT or ROOT in out.parents or out in ROOT.parents:
        parser.error('--out must be absent, outside and not containing this artifact')
    java, javac = tools(args.java_home)
    out.mkdir(parents=True)
    (out / 'classes').mkdir()
    env = dict(os.environ)
    for name in ('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'CLASSPATH'):
        env.pop(name, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(ROOT / 'src')
    commands = []
    summary = {'status': 'RUNNING', 'started_utc': datetime.now(timezone.utc).isoformat(),
               'historical_results_modified': False}

    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    def run(label, argv, timeout=60):
        receipt = {'label': label, 'argv': argv, 'cwd': str(ROOT), 'timeout_seconds': timeout,
                   'started_utc': datetime.now(timezone.utc).isoformat()}
        commands.append(receipt)
        save('commands.json', commands)
        started = time.perf_counter()
        with (out / (label + '.stdout.txt')).open('wb') as stdout, (out / (label + '.stderr.txt')).open('wb') as stderr:
            try:
                child = subprocess.run(argv, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                                       timeout=timeout, check=False)
                receipt['exit_code'] = child.returncode
            except subprocess.TimeoutExpired:
                receipt['timed_out'] = True
                raise
            finally:
                receipt['wall_seconds'] = time.perf_counter() - started
                save('commands.json', commands)
        if child.returncode:
            raise RuntimeError(label + ' nonzero exit')
        return (out / (label + '.stdout.txt')).read_text(encoding='utf-8')

    try:
        bindings = list(SOURCES) + ['reproduce_public_boundary.py', 'reproduce_java_conformance.py',
                    'reproduce_trace_bridge.py', 'receiver_tests/test_public_boundary.py',
                    'receiver/producer.py', 'receiver/reference.py', 'receiver/certificate_reference.py',
                    'src/model.py', 'src/producer.py', 'src/checker.py', 'src/oracle.py',
                    'src/witness.py', 'inputs/witness-programs.json',
                    'src/java_trace_bridge.py', 'results/specialization-campaign/cases.tsv',
                    'inputs/data-prefix-regressions.json']
        bindings += [str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT / 'java/evolution').rglob('*.java')]
        bindings += [str(p.relative_to(ROOT)).replace('\\', '/') for folder in ('tests', 'receiver_tests', 'bridge_tests')
                     for p in (ROOT / folder).glob('*.py') if str(p.relative_to(ROOT)).replace('\\', '/') not in bindings]
        save('environment.json', {'python': sys.version, 'platform': platform.platform(),
             'machine': platform.machine(), 'java': java, 'javac': javac, 'jvm_options': VM,
             'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in bindings},
             'cleared_injected_java_environment': True})
        run('java-version', [java, '-version'])
        run('javac-version', [javac, '-version'])
        for folder in ('tests', 'receiver_tests', 'bridge_tests'):
            run('python-' + folder, [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', folder, '-v'])
        run('compile', [javac, *['-J' + x for x in VM], '-proc:none', '--release', '17',
            '-encoding', 'UTF-8', '-d', str(out / 'classes'), *[str(ROOT / p) for p in SOURCES]])
        prefix = [java, *VM, '-cp', str(out / 'classes')]
        passive = run('passive', prefix + ['DeserializationTraceHarness'])
        pair = [json.loads(line) for line in run('observation-pair', prefix + ['ObservationPair']).splitlines()]
        if len(pair) != 2 or pair[0]['public_events'] != pair[1]['public_events'] or \
                [r['observed_unready'] for r in pair] != [False, True]:
            raise AssertionError('passive observation pair')
        for version, main in (('v1', 'WriteOld'), ('v2', 'ReadNew')):
            classes = out / version
            classes.mkdir()
            sources = [ROOT / 'java/evolution' / version / (main + '.java'),
                       ROOT / 'java/evolution' / version / 'evolution/EvolvingNode.java']
            run('evolution-compile-' + version, [javac, '-proc:none', '--release', '17', '-d', str(classes),
                                              *map(str, sources)])
            text = run('evolution-' + version, [java, *VM, '-cp', str(classes), main, str(out / 'owned-evolution.ser')])
        from reproduce_trace_bridge import missing_field_observation, EXPECTED
        from src.java_trace_bridge import map_observation
        from src.oracle import exact
        from src.checker import Checker
        passive_rows = [json.loads(line) for line in passive.splitlines()] + [missing_field_observation(json.loads(text))]
        mapped = unknown = 0
        for row in passive_rows:
            bridge = map_observation(row)
            if bridge.status != EXPECTED[row['case']]:
                raise AssertionError('passive status changed')
            if bridge.status == 'MAPPED':
                mapped += 1
                safe = exact(bridge.heap, bridge.roots)[0]
                try:
                    Checker(bridge.heap, list(bridge.roots))
                    admitted = True
                except ValueError:
                    admitted = False
                if safe != admitted:
                    raise AssertionError('passive admission/dense disagreement')
            else:
                unknown += 1
        if len(passive_rows) != 11 or (mapped, unknown) != (3, 8):
            raise AssertionError('passive case coverage')
        save('passive-results.json', passive_rows)

        prefix_cases = json.loads((ROOT / 'inputs/data-prefix-regressions.json').read_text(encoding='utf-8'))['cases']
        named = {case['id']: case for case in prefix_cases}
        if len(prefix_cases) != 6 or len(named) != 6:
            raise AssertionError('named data-prefix fixture count')
        cases, expectations = [], {}
        for line in (ROOT / 'results/specialization-campaign/cases.tsv').read_text(encoding='utf-8').splitlines():
            ident, kind, text = line.split('\t')
            words = [int(cell) for cell in text.split(',')]
            if ident in named and words != named[ident]['words']:
                raise AssertionError('named data-prefix fixture changed')
            truth = decide(words)
            if truth['status'] not in ('ALLOW', 'DENY_UNSAFE'):
                continue
            cases.append(line)
            expectations[ident] = (truth, classify(words))
        if not set(named) <= set(expectations):
            raise AssertionError('complete data-prefix cases omitted')
        (out / 'valid-data-cases.tsv').write_text('\n'.join(cases) + '\n', encoding='utf-8')
        raw = run('public-boundary', prefix + ['PublicBoundaryHarness', str(out / 'valid-data-cases.tsv')])
        rows = [json.loads(line) for line in raw.splitlines()]
        seen = set()
        for row in rows:
            key = row['id'], row['mode']
            if key in seen or row['mode'] not in MODES:
                raise AssertionError('duplicate/unknown public case')
            seen.add(key)
            truth, certificate = expectations[row['id']]
            verify_public(row, truth, certificate if row['mode'] == 'certificate' else truth['status'])
        if seen != {(ident, mode) for ident in expectations for mode in MODES}:
            raise AssertionError('public case coverage')
        regressions = []
        for ident, case in named.items():
            truth, certificate = expectations[ident]
            if truth['status'] != case['data'] or certificate != case['certificate']:
                raise AssertionError('data-prefix/certificate policy separation')
            regressions.append({'id': ident, 'name': case['name'], 'data': truth,
                                'certificate': certificate,
                                'observations': [row for row in rows if row['id'] == ident]})
        save('data-prefix-regressions-results.json', regressions)
        mode_outcomes = {mode: {} for mode in MODES}
        for row in rows:
            counts = mode_outcomes[row['mode']]
            counts[row['status']] = counts.get(row['status'], 0) + 1
        summary.update(public_data_cases=len(expectations), public_observations=len(rows),
                       public_mismatches=0, passive_mapped=mapped, passive_unknown=unknown,
                       unsafe_data_cases=sum(truth['status'] == 'DENY_UNSAFE' for truth, _ in expectations.values()),
                       observation_pair_equal_projection=True, mode_outcomes=mode_outcomes,
                       named_data_prefix_regressions=len(regressions), costs_skipped=args.skip_costs)

        if not args.skip_costs:
            # Four inherited contrasting families, fixed before this new run.
            families = {'chain-one': ([1]*128, list(range(1, 128))+[-1], [0]),
                        'cycle-one': ([1]*128, list(range(1, 128))+[0], [0]),
                        'isolated-repeat': ([1]*128, [-1]*128, [0]*128),
                        'cycle-repeat': ([1]*128, list(range(1, 128))+[0], [0]*128)}
            cost_lines, prep_rows = [], []
            for ident, data in families.items():
                words = packet(*data)[0]
                cost_lines.append(ident + '\tcost\t' + ','.join(map(str, words)))
                for mode, prepare in (('certificate', lambda: packet(*data)),
                                      ('eager_data_only', lambda: eager_words(*data))):
                    for _ in range(10): prepare()
                    for batch in range(7):
                        started = time.perf_counter_ns()
                        for _ in range(5): prepare()
                        prep_rows.append({'id': ident, 'mode': mode, 'batch': batch, 'iterations': 5,
                                          'python_preparation_ns': time.perf_counter_ns() - started})
            save('python-preparation.json', prep_rows)
            (out / 'cost-cases.tsv').write_text('\n'.join(cost_lines) + '\n', encoding='utf-8')
            timing = []
            for ident in families:
                for fork in range(7):
                    timing.extend(json.loads(line) for line in run('cost-' + ident + '-' + str(fork),
                        prefix + ['PublicBoundaryHarness', '--cost', str(out / 'cost-cases.tsv'), ident, str(fork)]).splitlines())
            save('java-costs.json', timing)
            costs = {}
            for ident in families:
                costs[ident] = {}
                for mode in MODES:
                    group = [r for r in timing if r['id'] == ident and r['mode'] == mode]
                    if len(group) != 7:
                        raise AssertionError('timing coverage')
                    costs[ident][mode] = {k.replace('_ns', '_us'): stats([r[k]/r['iterations']/1000 for r in group])
                        for k in ('sender_framing_ns', 'receiving_ns', 'java_pipeline_ns')}
                    costs[ident][mode].update(words=group[0]['words'], bytes=group[0]['bytes'])
                for mode in ('certificate', 'eager_data_only'):
                    costs[ident][mode]['python_preparation_us'] = stats([r['python_preparation_ns']/r['iterations']/1000
                        for r in prep_rows if r['id'] == ident and r['mode'] == mode])
            save('cost-summary.json', {'families': costs, 'units': 'microseconds per call, median/min/max of batch means',
                'java_forks_per_family': 7, 'jvm_warmups_per_mode': 300, 'jvm_iterations_per_metric': 200,
                'python_batches': 7, 'python_iterations_per_batch': 5,
                'includes': 'Python domain validation and word/proof production separately; Java sender framing; receiver copying/decoding/canonical validation/graph construction and diagnostics; actual transmitted bytes',
                'excludes': 'common application data creation; process startup from per-call timing (command wall times recorded); network latency/bandwidth; cross-language transfer and caller use',
                'not_end_to_end': 'Separate Python and JVM measurements are not a measured combined deployment latency; Java pipeline is measured jointly, not summed from component medians; no RSS claim'})
            summary['cost_forks'] = 28
        summary['status'] = 'PASS'
    except Exception as error:
        summary.update(status='FAIL', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        summary['ended_utc'] = datetime.now(timezone.utc).isoformat()
        save('summary.json', summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
