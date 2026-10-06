#!/usr/bin/env python3
"""Offline, single-worker receiver experiment; writes only a fresh directory.

All bytes tested by Java are created by ObjectOutputStream from owned fixtures.
No external serialized file, network, model API, or downloaded dependency is used.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
try:
    import resource
except ImportError:
    resource = None
import statistics
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent
if sys.version_info < (3,9): raise RuntimeError('Python >=3.9 required')
sys.path.insert(0,str(ROOT))
from receiver.producer import packet
from receiver.reference import decide
from reproduce_trace_bridge import (environment_record, aggregate_summary, require_fresh,
    JVM_OPTIONS, JAVAC_OPTIONS, RUN_ENV_OVERRIDES, write_json)

def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]

def cases():
    out=[]
    def add(name,kind,values,links,roots):
        w,_=packet(values,links,roots)
        out.append({'id':name,'kind':kind,'words':w,'reference':decide(w)})
    # First case is safe: the Java failure/truncation controls use this frame.
    counter=0
    for n in (1,2,3):
        for values in itertools.product((0,1),repeat=n):
            for links in itertools.product(range(-1,n),repeat=n):
                for mask in range(1<<n):
                    roots=[i for i in range(n) if mask & (1<<i)]
                    add(f'exact-{counter:04d}','exact',list(values),list(links),roots); counter+=1
    for family in ('lollipop','shared-tail','disconnected-cycle'):
        for i in range(32):
            n=(16,32,64,128)[i%4]
            values=[(k+i)%2 if i%2 else 1 for k in range(n)]
            if family=='lollipop':
                links=list(range(1,n))+[n//2]; roots=[0]
            elif family=='shared-tail':
                links=[n//2]*(n//2)+list(range(n//2+1,n))+[-1]; roots=[0,1,1]
            else:
                links=list(range(1,n//2))+[0]+list(range(n//2+1,n))+[n//2]
                roots=[0] if i%3 else [0,n//2]
            name=f'{family}-{i:02d}'
            add(name,'heldout',values,links,roots)
            rev=lambda k:n-1-k
            vv=list(reversed(values)); tt=[-1 if links[rev(k)]==-1 else rev(links[rev(k)]) for k in range(n)]
            add(name+'-renamed','renamed',vv,tt,[rev(r) for r in roots])
    for n,m in [(1,128),(128,128),(128,0)]:
        add(f'bound-n{n}-m{m}','capacity',[1]*n,list(range(1,n))+[-1],[0]*m)
    seed,_=packet([0,1],[1,-1],[0]); start=4+4+1
    for k in range(start,len(seed)):
        w=seed.copy();w[k]^=1
        out.append({'id':f'cert-flip-{k:03d}','kind':'certificate-control','words':w,'reference':decide(w)})
    for k in range(start,len(seed)):
        w=seed[:k]
        out.append({'id':f'cert-short-{k:03d}','kind':'certificate-control','words':w,'reference':decide(w)})
    w=seed+[0];out.append({'id':'cert-extra','kind':'certificate-control','words':w,'reference':decide(w)})
    mutations=[(0,0),(1,2),(2,0),(2,129),(3,-1),(3,129),(4,-1),(4,2),(6,-2),(6,2),(8,-1),(8,2)]
    for k,(index,value) in enumerate(mutations):
        w=seed.copy();w[index]=value
        out.append({'id':f'data-bad-{k:02d}','kind':'data-control','words':w,'reference':decide(w)})
    return out

def tsv(rows):
    return ''.join(f"{r['id']}\t{r['kind']}\t"+','.join(map(str,r['words']))+'\n' for r in rows)

def cpu():
    a=resource.getrusage(resource.RUSAGE_SELF);b=resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime+a.ru_stime+b.ru_utime+b.ru_stime

def main():
    if resource is None:
        raise RuntimeError('Full JVM campaign requires POSIX resource telemetry; '
                           'reproduce_portable.py runs only the Python reference scope')
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--verify-against',type=Path);ap.add_argument('--skip-benchmark',action='store_true')
    args=ap.parse_args();out=args.out.resolve();require_fresh(out);started=cpu()
    command_records=[]; build_path=None
    def run(cmd,file,timeout=120):
        t=time.perf_counter()
        p=subprocess.run(cmd,cwd=ROOT,env={**os.environ,**RUN_ENV_OVERRIDES},text=True,capture_output=True,timeout=timeout)
        (out/file).write_text(p.stdout,encoding='utf-8');(out/(file+'.stderr')).write_text(p.stderr,encoding='utf-8')
        normalized=[str(x).replace(str(ROOT),'<artifact>').replace(str(out),'<output>') for x in cmd]
        normalized=[x.replace(build_path,'<build>') for x in normalized] if build_path else normalized
        normalized=['python3' if x==sys.executable else x for x in normalized]
        command_records.append({'argv':normalized,'returncode':p.returncode,'wall_seconds':time.perf_counter()-t,'stdout':file,'stderr':file+'.stderr'})
        write_json(out/'commands.json',command_records)
        if p.returncode:raise RuntimeError(f'command returned {p.returncode}; see {file}.stderr')
    env=environment_record();env['schema']='bounded-receiver-environment-v1'
    env['record_scope']='only this data-only receiver run; historical environments unchanged'
    code=list((ROOT/'receiver').glob('*.py'))+list((ROOT/'receiver_tests').glob('*.py'))
    code+=list((ROOT/'src').glob('*.py'))+[ROOT/'reproduce_receiver.py',ROOT/'reproduce_trace_bridge.py']
    code += [ROOT/'java'/s for s in ('CertifiedReceiver.java','ReceiverHarness.java','ObservationPair.java')]
    env['code_input_summary']=aggregate_summary(code)
    write_json(out/'environment.json',env)
    rows=cases();(out/'cases.tsv').write_text(tsv(rows))
    with (out/'inputs.jsonl').open('w') as f:
        for r in rows:f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
    env['exact_case_input_sha256']=hashlib.sha256((out/'cases.tsv').read_bytes()).hexdigest();write_json(out/'environment.json',env)
    run([sys.executable,'-m','unittest','discover','-s','receiver_tests','-v'],'unit-tests.txt')
    with tempfile.TemporaryDirectory(prefix='receiver-build-') as temp:
        build_path=temp
        run(['javac',*['-J'+x for x in JVM_OPTIONS],*JAVAC_OPTIONS,'-d',temp,
             *[str(ROOT/'java'/s) for s in ('CertifiedReceiver.java','ReceiverHarness.java','ObservationPair.java')]],'compile.txt')
        run(['java',*JVM_OPTIONS,'-cp',temp,'ReceiverHarness',str(out/'cases.tsv'),str(out/'streams')],'java-results.jsonl')
        run(['java',*JVM_OPTIONS,'-cp',temp,'ObservationPair'],'observation-pair.jsonl')
        if not args.skip_benchmark:
            bench=[]
            for n in (1,4,16,32,64,128):
                w,_=packet([1]*n,list(range(1,n))+[-1],[0]);bench.append({'id':f'n{n}','kind':'benchmark','words':w})
            (out/'benchmark.tsv').write_text(tsv(bench))
            for n in (1,4,16,32,64,128):
                for fork in range(7):
                    run(['java',*JVM_OPTIONS,'-cp',temp,'ReceiverHarness','--benchmark',str(out/'benchmark.tsv'),str(fork),f'n{n}'],f'benchmark-n{n}-{fork}.jsonl')
    actual=lines(out/'java-results.jsonl'); lookup={r['id']:r for r in actual};errors=[]
    summary={'input_cases':len(rows),'actual_java_cases':len(actual),'counts':{},'outcomes':{},'oracle_disagreements':0,
        'eager_disagreements':0,'shape_unsafe_accepts':0,'corrupt_certificates_accepted':0,
        'callbacks_executed':0,'failure_publications':0,'alias_or_freeze_errors':0,
        'mapped_heap_errors':0,'metamorphic_errors':0,'max_serialized_bytes_including_negative_controls':0,'max_accepted_bytes':0,'max_shadow_steps':0}
    for r in actual:
        for key,field in [('counts','kind'),('outcomes','status')]:summary[key][r[field]]=summary[key].get(r[field],0)+1
        summary['callbacks_executed']+=r['callback_count']
        summary['max_serialized_bytes_including_negative_controls']=max(summary['max_serialized_bytes_including_negative_controls'],r['bytes'])
        if r['status']=='ALLOW':summary['max_accepted_bytes']=max(summary['max_accepted_bytes'],r['bytes'])
        summary['max_shadow_steps']=max(summary['max_shadow_steps'],r['steps'])
        if not r['frozen_alias_ok']:summary['alias_or_freeze_errors']+=1
        if r['status']!='ALLOW' and (r['has_graph'] or 'PUBLISH' in r['trace']):summary['failure_publications']+=1
    for r in rows:
        a=lookup[r['id']];kind=r['kind'];oracle=r['reference']
        if kind in ('exact','heldout','renamed','capacity'):
            if a['status']!=oracle['status']:summary['oracle_disagreements']+=1
            if a['eager']!=oracle['status']:summary['eager_disagreements']+=1
            if oracle['status']=='DENY_UNSAFE' and a['shape']=='ALLOW':summary['shape_unsafe_accepts']+=1
            if a['status']=='ALLOW':
                expected=[[1,v,t] for v,t in zip(oracle['values'],oracle['links'])]
                if a['heap']!=expected or a['roots']!=oracle['roots']:summary['mapped_heap_errors']+=1
        elif kind=='certificate-control' and a['has_graph']:summary['corrupt_certificates_accepted']+=1
        elif kind=='data-control' and a['has_graph']:errors.append(r['id']+':invalid-data-accepted')
        if kind=='renamed' and a['status']!=lookup[r['id'].removesuffix('-renamed')]['status']:summary['metamorphic_errors']+=1
    for r in actual:
        if r['kind'] in ('wire-control','fault-control') and r['has_graph']:errors.append(r['id']+':control-published')
    pair=lines(out/'observation-pair.jsonl')
    summary['observation_pair']={'same_wire':all(r['same_wire'] for r in pair),
        'same_public_projection':pair[0]['public_events']==pair[1]['public_events'],
        'unready_read_outcomes':[r['observed_unready'] for r in pair]}
    if not summary['observation_pair']['same_public_projection'] or summary['observation_pair']['unready_read_outcomes']!=[False,True]:errors.append('observation-pair')
    for field in ('oracle_disagreements','eager_disagreements','corrupt_certificates_accepted','callbacks_executed','failure_publications','alias_or_freeze_errors','mapped_heap_errors','metamorphic_errors'):
        if summary[field]:errors.append(field)
    summary['errors']=errors;summary['pass']=not errors
    write_json(out/'summary.json',summary)
    if not args.skip_benchmark:
        samples=[r for n in (1,4,16,32,64,128) for k in range(7) for r in lines(out/f'benchmark-n{n}-{k}.jsonl')]
        perf=[]
        for n in (1,4,16,32,64,128):
            item={'n':n,'modes':{}}
            for mode,name in [(0,'shape'),(1,'eager'),(2,'certificate')]:
                arr=[r['ns_total']/r['iterations']/1000 for r in samples if r['id']==f'n{n}' and r['mode']==mode]
                item['modes'][name]={'median_us':statistics.median(arr),'min_us':min(arr),'max_us':max(arr),'forks':len(arr)}
            item['certificate_over_eager']=item['modes']['certificate']['median_us']/item['modes']['eager']['median_us']
            ratios=[]
            for k in range(7):
                paired={r['mode']:r['ns_total']/r['iterations'] for r in samples if r['id']==f'n{n}' and r['fork']==k}
                ratios.append(paired[2]/paired[1])
            item['paired_ratio']={'median':statistics.median(ratios),'min':min(ratios),'max':max(ratios)}
            perf.append(item)
        write_json(out/'performance.json',{'measurement':'traced implementation; seven independent size-specific JVM forks; 500 warmups, 200 timed calls/mode, order rotated by fork','rows':perf})
    usage={'aggregate_cpu_seconds':cpu()-started,'self_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'child_peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'benchmark_skipped':args.skip_benchmark}
    write_json(out/'resources.json',usage)
    if args.verify_against:
        base=args.verify_against.resolve();reports=[]
        for name in ('summary.json','cases.tsv','inputs.jsonl','java-results.jsonl','observation-pair.jsonl'):
            same=(out/name).read_bytes()==(base/name).read_bytes();reports.append({'file':name,'byte_equal':same})
        # Serialized .ser inputs are actual generated bytes, not only abstract data.
        original={p.name:p.read_bytes() for p in (base/'streams').glob('*.ser')}
        replay={p.name:p.read_bytes() for p in (out/'streams').glob('*.ser')}
        reports.append({'file':'streams/*.ser','files':len(replay),'byte_equal':original==replay})
        write_json(out/'verification.json',{'files':reports,'match':all(r['byte_equal'] for r in reports),'performance_compared':False})
        if not all(r['byte_equal'] for r in reports):raise AssertionError('receiver replay mismatch; reports saved without changing baseline')
    print(json.dumps({'summary':summary,'resources':usage},indent=2))
    if errors:raise AssertionError(errors)
if __name__=='__main__':main()
