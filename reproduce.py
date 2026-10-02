#!/usr/bin/env python3
"""Reproduce the owned bounded experiment, without downloading or contacting anything.

Python 3.9 or newer with its standard library, Linux, and a local JDK are
sufficient. One experiment worker is used; javac/java run sequentially, never
concurrently with enumeration. Output is written only into a fresh directory
selected with --out.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
if sys.version_info < (3, 9):
    raise RuntimeError('Python 3.9 or newer is required by runtime built-in generic aliases')
sys.path.insert(0, str(ROOT / 'src'))
from checker import Checker
from exhaustive import run as exhaustive_run
from oracle import exact
from producer import initial_cache, produce
from redundant_control import run as redundant_run
from witness import bfs, enumerated_oracle

MEASUREMENT_KEYS = {'cpu_seconds', 'wall_seconds', 'peak_rss_kib',
                    'parent_peak_rss_kib', 'child_peak_rss_kib', 'aggregate_rss_upper_kib'}
SCIENTIFIC_JSON_FILES = ['exhaustive-2.json', 'exhaustive-3.json', 'witnesses.json',
                         'java-summary.json', 'capacity.json', 'redundant-predicate.json',
                         'unit-summary.json']
DETERMINISTIC_DATA_FILES = ['exhaustive-2-states.csv', 'exhaustive-3-states.csv',
                            'java-observations.jsonl', 'certificate-128.json', 'summary.csv']
RUN_ENV_OVERRIDES = {'OMP_NUM_THREADS':'1', 'OPENBLAS_NUM_THREADS':'1',
                     'MKL_NUM_THREADS':'1', 'JAVA_TOOL_OPTIONS':''}
JVM_OPTIONS = ['-XX:ActiveProcessorCount=1', '-XX:+UseSerialGC', '-Xmx256m']
JAVAC_OPTIONS = ['-proc:none']

def semantic(x):
    if isinstance(x, dict):
        return {k: semantic(v) for k, v in x.items() if k not in MEASUREMENT_KEYS}
    if isinstance(x, list):
        return [semantic(v) for v in x]
    return x

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def aggregate_summary(paths):
    """Bind one run to a compact, targeted code/input summary."""
    digest=hashlib.sha256(); total=0; names=[]
    for path in sorted(paths):
        relative=path.relative_to(ROOT).as_posix(); content=path.read_bytes()
        names.append(relative); total += len(content)
        digest.update(relative.encode('utf-8')); digest.update(b'\0')
        digest.update(content); digest.update(b'\0')
    return {'sha256':digest.hexdigest(), 'file_count':len(names),
            'bytes':total, 'files':names}

def code_input_summary():
    code=[]
    for pattern in ('src/*.py', 'tests/*.py', '*.py', 'java/*.java'):
        code.extend(ROOT.glob(pattern))
    return {'code':aggregate_summary(set(code)),
            'inputs':aggregate_summary(ROOT.glob('inputs/*.json'))}

def probe(command):
    try:
        proc=subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=10, check=False,
                            env={**os.environ, **RUN_ENV_OVERRIDES})
        return {'available':True, 'returncode':proc.returncode, 'output':proc.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'available':False, 'error':f'{type(exc).__name__}: {exc}'}

def selected_java_properties(output):
    wanted={'java.vendor', 'java.version', 'java.runtime.version', 'java.vm.name',
            'java.vm.vendor', 'java.vm.version', 'java.specification.version', 'os.arch'}
    values={}
    for line in output.splitlines():
        if '=' not in line:
            continue
        key,value=(part.strip() for part in line.split('=',1))
        if key in wanted:
            values[key]=value
    return values

def compact_probe(probe_result):
    """Retain version-identifying output while omitting cwd/home/temp paths."""
    if not probe_result.get('available'):
        return dict(probe_result)
    lines=[]
    for line in str(probe_result.get('output','')).splitlines():
        stripped=line.strip()
        if (stripped.startswith('openjdk version') or stripped.startswith('java version') or
                stripped.startswith('OpenJDK Runtime Environment') or
                stripped.startswith('OpenJDK 64-Bit Server VM') or
                stripped.startswith('javac ')):
            lines.append(stripped)
    return {'available':True, 'returncode':probe_result.get('returncode'),
            'version_output':'\n'.join(lines)}

def os_release():
    path=Path('/etc/os-release')
    if not path.exists():
        return {}
    values={}
    for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
        if '=' not in line or line.startswith('#'):
            continue
        key,value=line.split('=',1)
        if key in {'ID','NAME','VERSION','VERSION_ID'}:
            values[key]=value.strip().strip('"')
    return values

def environment_record():
    java=probe(['java','-XshowSettings:properties','-version'])
    javac=probe(['javac','-version'])
    return {
        'schema':'bounded-replay-environment-v1',
        'record_scope':'this replay only; not a reconstruction of the archived campaign environment',
        'captured_utc':datetime.now(timezone.utc).isoformat(),
        'platform':{
            'system':platform.system(), 'release':platform.release(),
            'machine':platform.machine(), 'pointer_bits':8*struct.calcsize('P'),
            'sys_platform':sys.platform, 'os_release':os_release()},
        'python':{
            'implementation':platform.python_implementation(),
            'version':platform.python_version(), 'version_string':sys.version,
            'cache_tag':getattr(sys.implementation,'cache_tag',None),
            'minimum_required':'3.9'},
        'java':{
            'version_probe':compact_probe(java),
            'selected_properties':selected_java_properties(java.get('output','')),
            'javac_probe':compact_probe(javac)},
        'execution':{
            'workers':1, 'jvm_options':JVM_OPTIONS, 'javac_options':JAVAC_OPTIONS,
            'environment_overrides':RUN_ENV_OVERRIDES,
            'java_children_sequential':True},
        'code_input_summary':code_input_summary()
    }

def root_validation_evidence():
    heap=((1,0,-1),)
    cases=[]
    invalid=[('list',[0,False]),('list',[False,0]),('list',[0,0.0]),('list',[0.0,0]),
             ('tuple',(0,False)),('tuple',(False,0)),('tuple',(0,0.0)),('tuple',(0.0,0))]
    valid=[('list',[0,0]),('tuple',(0,0)),('list',[0]*128)]
    for container,roots in invalid:
        try:
            Checker(heap,roots); actual='ACCEPT'
        except ValueError:
            actual='REJECT'
        cases.append({'container':container,'roots':list(roots),'expected':'REJECT','actual':actual})
    for container,roots in valid:
        try:
            normalized=sorted(Checker(heap,roots).roots); actual='ACCEPT'
        except ValueError:
            normalized=None; actual='REJECT'
        cases.append({'container':container,'root_count':len(roots),
                      'roots':list(roots) if len(roots)<=2 else '[0 repeated 128 times]',
                      'expected':'ACCEPT','actual':actual,'normalized_roots':normalized})
    try:
        Checker(heap,[0]*129); oversized='ACCEPT'
    except ValueError:
        oversized='REJECT'
    cases.append({'container':'list','root_count':129,'roots':'[0 repeated 129 times]',
                  'expected':'REJECT','actual':oversized})
    if any(case['actual'] != case['expected'] for case in cases):
        raise AssertionError('root validation regression failed')
    return {'heap':[list(heap[0])], 'strict_type_check_precedes_deduplication':True,
            'cases':cases, 'status':'PASS'}

def measured_process(command, timeout, output):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    with output.open('w', encoding='utf-8') as stream:
        proc = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.PIPE,
                              text=True, timeout=timeout, check=False,
                              env={**os.environ, **RUN_ENV_OVERRIDES})
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if proc.returncode:
        raise RuntimeError(f'command failed (exit {proc.returncode}): {proc.stderr[-4000:]}')
    return {'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
            'wall_seconds': time.perf_counter()-start,
            # Linux maximum over children seen so far, NOT an isolated per-stage measurement.
            'child_peak_rss_kib': after.ru_maxrss}

def compare(reference, actual):
    scientific=[]; deterministic=[]
    for name in SCIENTIFIC_JSON_FILES:
        expected=json.loads((reference/name).read_text())
        obtained=json.loads((actual/name).read_text())
        scientific.append({'file':name,
                           'comparison':'semantic JSON excluding measurement fields',
                           'status':'MATCH' if semantic(expected)==semantic(obtained) else 'MISMATCH'})
    for name in DETERMINISTIC_DATA_FILES:
        expected=(reference/name).read_bytes(); obtained=(actual/name).read_bytes()
        deterministic.append({'file':name, 'comparison':'exact bytes',
                              'expected_bytes':len(expected), 'actual_bytes':len(obtained),
                              'status':'MATCH' if expected==obtained else 'MISMATCH'})
    all_results=scientific+deterministic
    return {'status':'MATCH' if all(item['status']=='MATCH' for item in all_results) else 'MISMATCH',
            'scientific_json':scientific, 'deterministic_data':deterministic,
            'scientific_matches':sum(item['status']=='MATCH' for item in scientific),
            'scientific_total':len(scientific),
            'deterministic_matches':sum(item['status']=='MATCH' for item in deterministic),
            'deterministic_total':len(deterministic),
            'excluded_fields':sorted(MEASUREMENT_KEYS), 'independent_review':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path, help='fresh or empty output directory')
    parser.add_argument('--verify-against', type=Path, help='compare scientific results, not timing/RSS')
    args=parser.parse_args()
    out=args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('--out must be empty; archived evidence is not overwritten')
    out.mkdir(parents=True,exist_ok=True)
    write_json(out/'environment.json',environment_record())
    write_json(out/'root-validation.json',root_validation_evidence())
    contract=json.loads((ROOT/'inputs/domain.json').read_text())
    if contract['object_counts'] != [2,3] or contract['checker_sampling_stride'] != 1:
        raise ValueError('the implemented audit and input contract do not match')
    begin=time.perf_counter(); own_begin=time.process_time()
    children_begin=resource.getrusage(resource.RUSAGE_CHILDREN)
    stages=[]
    unit_cpu, unit_wall = time.process_time(), time.perf_counter()
    import unittest
    unit_counts={'inspect_calls':0,'checker_steps':0}
    original_inspect=Checker.inspect
    def counted_inspect(self, event, certificate):
        previous=self.steps
        decision=original_inspect(self,event,certificate)
        unit_counts['inspect_calls']+=1
        unit_counts['checker_steps']+=self.steps-previous
        return decision
    Checker.inspect=counted_inspect
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    with (out/'unit-tests.txt').open('w') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    Checker.inspect=original_inspect
    if not result.wasSuccessful(): raise AssertionError('unit tests failed')
    write_json(out/'unit-summary.json', {'tests':result.testsRun,'failures':len(result.failures),
                                       'errors':len(result.errors),'status':'PASS',**unit_counts})
    stages.append({'stage':'unit-tests','cpu_seconds':time.process_time()-unit_cpu,
                   'wall_seconds':time.perf_counter()-unit_wall})
    redundant=redundant_run(2,out/'redundant-predicate.json')
    totals={}
    for n in contract['object_counts']:
        value=exhaustive_run(n,out,stride=1)
        stages.append({'stage':f'exhaustive-{n}','cpu_seconds':value['cpu_seconds'],
                       'wall_seconds':value['wall_seconds'],'peak_rss_kib':value['peak_rss_kib']})
        for key,v in value['counts'].items(): totals[key]=totals.get(key,0)+v
    programs=json.loads((ROOT/'inputs/witness-programs.json').read_text())
    witnesses=[]
    for program in programs:
        answer=bfs(program)
        oracle=enumerated_oracle(program)
        if answer['status']=='VIOLATION' and (oracle['status'],oracle['trace']) != ('VIOLATION',answer['trace']):
            raise AssertionError('least trace disagrees with whole-path oracle')
        witnesses.append({'case':program['case'],'bfs':answer,'path_oracle':oracle})
    negative={'phase_erasure':bfs(programs[3],key_mode='erase-ready'),
              'ghost_epoch_retention':bfs(programs[4],cap=64,key_mode='retain-epoch'),
              'capacity_cutoff':bfs(programs[2],cap=1)}
    if negative['phase_erasure']['status']!='SAFE' or negative['ghost_epoch_retention']['status']!='UNKNOWN':
        raise AssertionError('witness negative controls did not discriminate')
    write_json(out/'witnesses.json',{'cases':witnesses,'negative_controls':negative})
    # Certificate size is a deterministic representation size, not a compression optimum.
    heap=tuple((1,1,(i+1)%128) for i in range(128)); roots=frozenset({0})
    event=(127,1,0,-1); cert=produce(heap,roots,initial_cache(heap,roots),event)
    encoded=(json.dumps(cert,separators=(',',':'))+'\n').encode('utf-8')
    (out/'certificate-128.json').write_bytes(encoded)
    checker=Checker(heap,roots)
    capacity={'objects':128,'decision':checker.inspect(event,cert),'utf8_bytes_with_newline':len(encoded),
              'obligations':len(cert['checks']),'checker_steps':checker.steps}
    if capacity['decision']!='DENY_UNSAFE': raise AssertionError('capacity fixture did not deny')
    write_json(out/'capacity.json',capacity)
    for binary in ('javac','java'):
        if shutil.which(binary) is None: raise RuntimeError('a local JDK is required; nothing is downloaded')
    with tempfile.TemporaryDirectory(prefix='initialization-classes-') as temporary:
        compile_stats=measured_process(['javac', *['-J'+flag for flag in JVM_OPTIONS], *JAVAC_OPTIONS,'-d',temporary,
                                         str(ROOT/'java/BenignGraphs.java')],30,out/'java-compile.txt')
        java_stats=measured_process(['java',*JVM_OPTIONS,'-cp',temporary,'BenignGraphs'],30,out/'java-observations.jsonl')
    stages.extend([{'stage':'java-compile',**compile_stats},{'stage':'java-observe',**java_stats}])
    observations=[json.loads(line) for line in (out/'java-observations.jsonl').read_text().splitlines()]
    if [x['case'] for x in observations] != [f'J{i:02d}' for i in range(24)]:
        raise AssertionError('Java fixture inclusion changed')
    callback_invalid=0
    for obs in observations:
        if obs['input_valid'] != obs['valid']:
            raise AssertionError('a round trip changed the selected final invariant')
        if obs['constructors_during_read'] != 0:
            raise AssertionError('the owned Serializable constructor ran during read')
        if len(obs['callback_states']) != obs['callbacks']:
            raise AssertionError('callback snapshot count mismatch')
        for callback in obs['callback_states']:
            bh=tuple(tuple(r) for r in callback['heap']); br=frozenset(callback['roots'])
            okay, live, _=exact(bh,br)
            if okay != callback['valid'] or all(bh[i][0] for i in live) != callback['all_ready']:
                raise AssertionError('callback snapshot disagrees with dense oracle')
            callback_invalid += not okay
        truth,_,_=exact(tuple(tuple(r) for r in obs['heap']),frozenset(obs['roots']))
        if truth!=obs['valid']: raise AssertionError('Java snapshot policy disagrees with dense oracle')
        try:
            Checker(obs['heap'],obs['roots']); admitted=True
        except ValueError: admitted=False
        if admitted != truth: raise AssertionError('checker admission disagrees with Java snapshot')
    java_summary={'cases':len(observations),'valid_final_snapshots':sum(x['valid'] for x in observations),
        'invalid_final_snapshots':sum(not x['valid'] for x in observations),
        'callbacks':sum(x['callbacks'] for x in observations),
        'callbacks_with_nonready_reachable_objects':sum(x['incomplete_callbacks'] for x in observations),
        'cases_with_nonready_callback_observation':sum(x['incomplete_callbacks']>0 for x in observations),
        'max_objects':max(len(x['heap']) for x in observations),'snapshot_mismatches':0,
        'callback_snapshots':sum(x['callbacks'] for x in observations),
        'invalid_callback_snapshots':callback_invalid,
        'constructors_during_read':sum(x['constructors_during_read'] for x in observations),
        'round_trip_validity_changes':sum(x['input_valid']!=x['valid'] for x in observations),
        'interpretation':'passive owned round trips; no JVM monitor or constructor-history refinement'}
    write_json(out/'java-summary.json',java_summary)
    with (out/'summary.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['measure','value'])
        writer.writerows(sorted(totals.items()))
    children=resource.getrusage(resource.RUSAGE_CHILDREN)
    parent=resource.getrusage(resource.RUSAGE_SELF)
    elapsed={'cpu_seconds':time.process_time()-own_begin+children.ru_utime+children.ru_stime-
              children_begin.ru_utime-children_begin.ru_stime,'wall_seconds':time.perf_counter()-begin,
             'parent_peak_rss_kib':parent.ru_maxrss,'child_peak_rss_kib':children.ru_maxrss,
             'aggregate_rss_upper_kib':parent.ru_maxrss+children.ru_maxrss,
             'stages':stages,'workers':1,'scientific_status':'FINITE_CHECKED_NOT_RESEARCH_LOCKED',
             'semantic_transitions':totals['transitions']+redundant['counts']['transitions']+
                  sum(x['bfs']['transitions']+x['path_oracle']['transitions'] for x in witnesses)+
                  sum(x['transitions'] for x in negative.values()),
             'checker_steps_exhaustive':totals['checker_steps'],
             'checker_steps_unit':unit_counts['checker_steps'],
             'checker_steps_capacity':capacity['checker_steps'],
             'unit_inspect_calls':unit_counts['inspect_calls'],
             'limitations':'RSS is a Linux parent/child maximum sum, not a simultaneous profiler. '
                  'No performance comparison with a production JVM monitor. Unit work is included in CPU, '
                  'unit inspect calls are reported separately from exhaustive candidate transitions.'}
    write_json(out/'measurements.json',elapsed)
    if args.verify_against:
        comparison=compare(args.verify_against.resolve(),out)
        write_json(out/'replay-verification.json',comparison)
        if comparison['status']!='MATCH':
            raise AssertionError('replay comparison mismatch; see replay-verification.json')
    print(json.dumps({'status':'PASS','totals':totals,'java':java_summary,'measured_cpu_seconds':elapsed['cpu_seconds']},indent=2))

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError,AssertionError,subprocess.TimeoutExpired) as exc:
        print(f'FAILED/UNKNOWN: {exc}',file=sys.stderr)
        raise SystemExit(2)
