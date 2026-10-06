#!/usr/bin/env python3
"""Finite Python/references only. Never claims fresh Java decoding or performance."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
import unittest

import reproduce as finite
from reproduce_receiver import cases, tsv
from reproduce_specialization import make_cases, as_tsv
from reproduce_trace_bridge import require_fresh, aggregate_summary, EXPECTED
from receiver.certificate_reference import classify
from java_trace_bridge import map_observation
from checker import Checker
from oracle import exact
from runtime_resources import self_peak_rss_kib

ROOT = Path(__file__).resolve().parent


def write_json(path, data):
    path.write_bytes((json.dumps(data, indent=2, sort_keys=True) + '\n').encode('utf-8'))


def write_rows(path, rows):
    path.write_bytes(''.join(json.dumps(r, sort_keys=True, separators=(',', ':')) + '\n'
                             for r in rows).encode('utf-8'))


def compare_bytes(actual, expected, names):
    records = [{'file': name, 'byte_equal': (actual/name).read_bytes() == (expected/name).read_bytes()}
               for name in names]
    write_json(actual/'verification.json', {'scope':'Python input generation only', 'files':records,
                                          'match':all(r['byte_equal'] for r in records)})
    if not all(r['byte_equal'] for r in records):
        raise AssertionError('generated input mismatch; baseline unchanged')


def receiver_reference(out):
    require_fresh(out)
    rows = cases()
    (out/'cases.tsv').write_bytes(tsv(rows).encode('utf-8'))
    write_rows(out/'inputs.jsonl', rows)
    compare_bytes(out, ROOT/'results/receiver-campaign', ('cases.tsv','inputs.jsonl'))
    statuses = Counter()
    for row in rows:
        status = classify(row['words']); statuses[status] += 1
        if row['kind'] in ('exact','heldout','renamed','capacity'):
            if status != row['reference']['status']:
                raise AssertionError('independent integer and dense data references disagree')
        elif status == 'ALLOW':
            raise AssertionError('corrupted certificate/data unexpectedly allowed')
    summary = {'scope':'Python-generated integer packets; no fresh Java frames',
               'cases':len(rows),'outcomes':dict(statuses),'java_executed':False,
               'pass_within_scope':True}
    write_json(out/'summary.json', summary)
    return summary


def specialization_reference(out):
    require_fresh(out)
    rows = make_cases()
    if len({r['id'] for r in rows}) != len(rows):
        raise AssertionError('duplicate case IDs')
    for row in rows:
        row['reference'] = classify(row['words'])
    (out/'cases.tsv').write_bytes(as_tsv(rows).encode('utf-8'))
    write_rows(out/'inputs.jsonl', rows)
    compare_bytes(out, ROOT/'results/specialization-campaign', ('cases.tsv','inputs.jsonl'))
    sharp = []
    for row in rows:
        if row['kind'] == 'sharp-bound':
            n, m = row['words'][2:4]
            bound = 5+11*n if m == 0 else n*m+26*n+19*m-10
            sharp.append({'n':n,'m':m,'words':len(row['words']),'bound':bound,
                          'word_equality':len(row['words']) == bound,
                          'java_serialized_bytes_measured':None})
    if not all(r['word_equality'] for r in sharp):
        raise AssertionError('sharp word bound mismatch')
    write_json(out/'word-bound.json', {'rows':sharp,'maximum_words':max(r['words'] for r in sharp),
                                     'java_serialized_bytes_measured':None})
    summary = {'scope':'Independent integer-certificate reference; no JVM differential or timing',
               'cases':len(rows),'outcomes':dict(Counter(r['reference'] for r in rows)),
               'sharp_word_equalities':len(sharp),'java_executed':False,'pass_within_scope':True}
    write_json(out/'summary.json', summary)
    return summary


def passive_reference(out):
    require_fresh(out)
    source = ROOT/'results/bridge-campaign/java-traces.jsonl'
    observations = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines() if s]
    if [r['case'] for r in observations] != list(EXPECTED):
        raise AssertionError('archived passive cases changed')
    results = []; safe = unsafe = 0
    for row in observations:
        bridge = map_observation(row)
        if bridge.status != EXPECTED[row['case']]:
            raise AssertionError('passive mapping changed')
        entry = {'case':row['case'],'bridge':bridge.as_json()}
        if bridge.status == 'MAPPED':
            truth, live, _ = exact(bridge.heap, bridge.roots)
            try:
                Checker(bridge.heap, list(bridge.roots)); admitted = True
            except ValueError:
                admitted = False
            if admitted != truth:
                raise AssertionError('passive snapshot references disagree')
            safe += truth; unsafe += not truth
            entry.update({'dense_oracle_safe':truth,'reachable':sorted(live),
                          'checker_initial_admission':'ACCEPT' if admitted else 'REJECT'})
        results.append(entry)
    expected = json.loads((ROOT/'results/bridge-campaign/bridge-results.json').read_text(encoding='utf-8'))
    if results != expected:
        raise AssertionError('passive record reinterpretation mismatch')
    write_json(out/'bridge-results.json', results)
    summary = {'scope':'Reinterpretation of archived passive observations, not fresh Java observations',
               'cases':len(results),'mapped':safe+unsafe,'unknown':len(results)-safe-unsafe,
               'mapped_safe':safe,'mapped_unsafe':unsafe,'java_executed':False,
               'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'pass_within_scope':True}
    write_json(out/'summary.json', summary)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    out = ap.parse_args(argv).out.resolve(); require_fresh(out)
    cpu, wall = time.process_time(), time.perf_counter()
    bindings = list(ROOT.glob('*.py')) + list((ROOT/'src').glob('*.py'))
    for folder in ('receiver','tests','bridge_tests','receiver_tests','portability_tests'):
        bindings += list((ROOT/folder).glob('*.py'))
    inputs = list((ROOT/'inputs').glob('*.json')) + [
        ROOT/'results/receiver-campaign/inputs.jsonl', ROOT/'results/bridge-campaign/java-traces.jsonl']
    write_json(out/'bindings.json', {'code':aggregate_summary(bindings),
                                   'scientific_inputs':aggregate_summary(inputs)})
    finite.main(['--out',str(out/'finite'),'--verify-against',str(ROOT/'results/campaign'),'--python-only'])
    summary = {'status':'PASS_WITHIN_PYTHON_SCOPE_ONLY','java_executed':False}
    suite = unittest.TestSuite()
    for directory in ('bridge_tests','receiver_tests'):
        suite.addTests(unittest.TestLoader().discover(str(ROOT/directory)))
    with (out/'reference-tests.txt').open('w', encoding='utf-8', newline='\n') as stream:
        tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if not tests.wasSuccessful():
        raise AssertionError('reference tests failed')
    summary['additional_reference_tests'] = tests.testsRun
    summary['receiver_reference'] = receiver_reference(out/'receiver-reference')
    summary['specialization_reference'] = specialization_reference(out/'specialization-reference')
    summary['passive_reinterpretation'] = passive_reference(out/'passive-reference')
    summary['resources'] = {'python_cpu_seconds':time.process_time()-cpu,
                            'wall_seconds':time.perf_counter()-wall,
                            'self_peak_rss_kib':self_peak_rss_kib(),
                            'jvm_cpu_seconds':None,'child_peak_rss_kib':None,
                            'rss_note':'Linux self maximum only; unavailable elsewhere'}
    write_json(out/'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
