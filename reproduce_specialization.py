#!/usr/bin/env python3
"""Offline equivalence, independent certificate checking, size and timing study.

Runs only locally constructed primitive integer-array cases. Output must be
fresh. The inherited campaigns are read-only. Measurements are never compared
for byte identity or rewritten to agree with an earlier environment.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
from receiver.producer import packet
from receiver.certificate_reference import classify
from reproduce_trace_bridge import (environment_record, aggregate_summary,
                                    require_fresh, JVM_OPTIONS, JAVAC_OPTIONS,
                                    RUN_ENV_OVERRIDES, write_json)


def cpu():
    own, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return own.ru_utime + own.ru_stime + child.ru_utime + child.ru_stime


def load(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s]


def make_cases():
    # Exact incoming integer packets, not regenerated from a repaired producer.
    rows = [{'id': 'retained-' + r['id'], 'kind': 'retained', 'words': r['words']}
            for r in load(ROOT/'results/receiver-campaign/inputs.jsonl')]
    seeds = [([0], [0], [0]), ([0, 1, 1], [1, 2, -1], [0, 0, 2]),
             ([1, 1, 1], [1, 2, 0], [0, 0, 2]),
             ([1, 1, 0], [-1, 2, 1], [0]), ([1, 0, 1], [1, 2, 0], [])]
    for j, (v, p, r) in enumerate(seeds):
        w = packet(v, p, r)[0]
        rows.append({'id': f'seed-{j}', 'kind': 'seed', 'words': w})
        for k in range(4 + 2*len(v) + len(r), len(w)):
            z = w.copy(); z[k] ^= 1
            rows.append({'id': f'cell-{j}-{k}', 'kind': 'certificate-cell', 'words': z})
            rows.append({'id': f'prefix-{j}-{k}', 'kind': 'certificate-prefix', 'words': w[:k]})
        rows.append({'id': f'tail-{j}', 'kind': 'certificate-tail', 'words': w + [0]})
    for n in (1, 2, 3, 7, 32, 128):
        for m in (0, 1, 2, 7, 128):
            w = packet([1]*n, list(range(1, n)) + [0], [0]*m)[0]
            rows.append({'id': f'sharp-{n}-{m}', 'kind': 'sharp-bound', 'words': w})
    return rows


def as_tsv(rows):
    return ''.join(f"{r['id']}\t{r['kind']}\t" + ','.join(map(str, r['words'])) + '\n' for r in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--skip-benchmark', action='store_true')
    parser.add_argument('--verify-against', type=Path)
    args = parser.parse_args()
    out = args.out.resolve(); require_fresh(out); start_cpu = cpu()
    commands = []
    env = environment_record()
    env['schema'] = 'receiver-specialization-environment-v1'
    env['record_scope'] = 'This run only; prior environment records remain unchanged.'
    code = [ROOT/'java'/f for f in ('CertifiedReceiver.java', 'SpecializationHarness.java')]
    code += [ROOT/'baselines/GenericReceiver.java', Path(__file__)]
    code += list((ROOT/'receiver').glob('*.py')) + list((ROOT/'receiver_tests').glob('*.py'))
    code += list((ROOT/'src').glob('*.py')) + [ROOT/'reproduce_trace_bridge.py']
    env['code_input_summary'] = aggregate_summary(code)
    write_json(out/'environment.json', env)

    def run(argv, name, build=None, timeout=180):
        t0 = time.perf_counter()
        try:
            p = subprocess.run(argv, cwd=ROOT, env={**os.environ, **RUN_ENV_OVERRIDES},
                               text=True, capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as e:
            record = {'command': [str(x) for x in argv], 'returncode': None,
                      'timeout_seconds': timeout, 'outcome': 'TIMEOUT'}
            commands.append(record); write_json(out/'commands.json', commands)
            raise RuntimeError(f'{name} timed out; this is not a successful run') from e
        (out/name).write_text(p.stdout, encoding='utf-8')
        (out/(name + '.stderr')).write_text(p.stderr, encoding='utf-8')
        normal = [str(a).replace(str(ROOT), '<artifact>').replace(str(out), '<output>') for a in argv]
        if build:
            normal = [a.replace(build, '<build>') for a in normal]
        normal = ['python3' if a == sys.executable else a for a in normal]
        commands.append({'argv': normal, 'returncode': p.returncode, 'stdout': name,
                         'stderr': name + '.stderr', 'wall_seconds': time.perf_counter()-t0})
        write_json(out/'commands.json', commands)
        write_json(out/'progress.json', {'last_completed_command': name, 'aggregate_cpu_seconds': cpu()-start_cpu, 'completed_subcommands': len(commands)})
        if p.returncode:
            raise RuntimeError(f'{name} exited {p.returncode}; raw output retained')

    rows = make_cases()
    ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError('duplicate case id')
    for r in rows:
        r['reference'] = classify(r['words'])
    (out/'cases.tsv').write_text(as_tsv(rows), encoding='utf-8')
    with (out/'inputs.jsonl').open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, separators=(',', ':')) + '\n')
    env['exact_case_input_sha256'] = hashlib.sha256((out/'cases.tsv').read_bytes()).hexdigest()
    write_json(out/'environment.json', env)
    write_json(out/'progress.json', {'phase': 'input-reference-complete', 'aggregate_cpu_seconds': cpu()-start_cpu})
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'receiver_tests', '-v'], 'tests.txt')
    with tempfile.TemporaryDirectory(prefix='specialized-receiver-') as build:
        sources = [ROOT/'java/CertifiedReceiver.java', ROOT/'baselines/GenericReceiver.java', ROOT/'java/SpecializationHarness.java']
        run(['javac', *['-J'+s for s in JVM_OPTIONS], *JAVAC_OPTIONS, '-d', build, *map(str, sources)], 'compile.txt', build)
        run(['java', *JVM_OPTIONS, '-cp', build, 'SpecializationHarness', str(out/'cases.tsv')], 'comparison.jsonl', build)
        if not args.skip_benchmark:
            benchmark = []
            specifications = [('chain-one', list(range(1, 128)) + [-1], [0]),
                              ('cycle-one', list(range(1, 128)) + [0], [0]),
                              ('isolated-repeat', [-1]*128, [0]*128),
                              ('cycle-repeat', list(range(1, 128)) + [0], [0]*128)]
            for name, links, roots in specifications:
                benchmark.append({'id': name, 'kind': 'benchmark', 'words': packet([1]*128, links, roots)[0]})
            (out/'benchmark.tsv').write_text(as_tsv(benchmark), encoding='utf-8')
            for case in benchmark:
                for fork in range(7):
                    run(['java', *JVM_OPTIONS, '-cp', build, 'SpecializationHarness', '--benchmark',
                         str(out/'benchmark.tsv'), case['id'], str(fork)],
                        f"benchmark-{case['id']}-{fork}.jsonl", build)

    actual = load(out/'comparison.jsonl')
    lookup = {r['id']: r for r in actual}
    errors = []
    if len(actual) != len(rows) or set(lookup) != set(ids):
        errors.append('missing/extra/duplicate output cases')
    counts = {}; outcomes = {}; generic_errors = 0; oracle_errors = 0; bad_allowed = 0
    sharp = []
    for r in rows:
        a = lookup.get(r['id'])
        if a is None:
            continue
        counts[r['kind']] = counts.get(r['kind'], 0) + 1
        outcomes[a['specialized']] = outcomes.get(a['specialized'], 0) + 1
        generic_errors += not a['all_observations_equal']
        oracle_errors += a['specialized'] != r['reference']
        if r['kind'].startswith('certificate-') and a['graph']:
            bad_allowed += 1
        if r['kind'] == 'sharp-bound':
            n, m = r['words'][2:4]
            bound = 5 + 11*n if m == 0 else n*m + 26*n + 19*m - 10
            sharp.append({'n': n, 'm': m, 'words': len(r['words']), 'bound': bound,
                          'java_bytes': a['bytes'], 'equality': len(r['words']) == bound and a['bytes'] == 27+4*bound})
    if generic_errors or oracle_errors or bad_allowed or not all(r['equality'] for r in sharp):
        errors.append('differential, oracle, mutation, or exact-bound failure')
    summary = {'java_cases': len(actual), 'groups': counts, 'outcomes': outcomes,
               'generic_observation_disagreements': generic_errors,
               'independent_certificate_reference_disagreements': oracle_errors,
               'corrupt_certificates_accepted': bad_allowed,
               'sharp_bound_equalities': sum(r['equality'] for r in sharp),
               'errors': errors, 'pass': not errors}
    write_json(out/'summary.json', summary)
    write_json(out/'size-bound.json', {'rows': sharp, 'maximum_words': 22134, 'maximum_bytes': 88563,
                                     'scope': 'sharp maximum for honest safe packets in the fixed canonical schema'})
    if not args.skip_benchmark:
        perf = []
        for name in ('chain-one', 'cycle-one', 'isolated-repeat', 'cycle-repeat'):
            measurements = [r for f in range(7) for r in load(out/f'benchmark-{name}-{f}.jsonl')]
            modes = {}
            for mode, label in enumerate(('generic', 'specialized', 'eager')):
                values = [r['ns_total']/r['iterations']/1000 for r in measurements if r['mode']==mode]
                modes[label] = {'median_us': statistics.median(values), 'min_us': min(values),
                                'max_us': max(values), 'forks': len(values)}
            ratios = []
            for fork in range(7):
                sample = {r['mode']: r['ns_total']/r['iterations'] for r in measurements if r['fork']==fork}
                ratios.append({'fork': fork, 'generic_over_specialized': sample[0]/sample[1],
                               'specialized_over_eager': sample[1]/sample[2]})
            perf.append({'family': name, 'modes': modes, 'paired_ratios': ratios})
        write_json(out/'performance.json', {'scope': 'traced end-to-end receiving; paired JVM batch means, not per-call quantiles',
                                          'warmup': 1000, 'iterations': 500, 'rows': perf})
    usage = {'aggregate_cpu_seconds': cpu()-start_cpu,
             'self_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'child_peak_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
             'benchmark_skipped': args.skip_benchmark,
             'tested_shadow_steps': sum(r['checked_steps'] for r in actual)}
    write_json(out/'resources.json', usage)
    if args.verify_against:
        reports = [{'file': name, 'byte_equal': (out/name).read_bytes() == (args.verify_against/name).read_bytes()}
                   for name in ('cases.tsv', 'inputs.jsonl', 'comparison.jsonl', 'summary.json', 'size-bound.json')]
        write_json(out/'verification.json', {'files': reports, 'match': all(r['byte_equal'] for r in reports),
                                           'timings_compared': False})
        if not all(r['byte_equal'] for r in reports):
            errors.append('deterministic replay mismatch')
    print(json.dumps({'summary': summary, 'resources': usage}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
