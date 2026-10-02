#!/usr/bin/env python3
"""Export small LaTeX tables from the recorded scientific results, without TeX dependencies."""
import argparse
import json
from pathlib import Path

def export(results, output):
    output.mkdir(parents=True, exist_ok=True)
    small=json.loads((results/'exhaustive-2.json').read_text())['counts']
    large=json.loads((results/'exhaustive-3.json').read_text())['counts']
    j=json.loads((results/'java-summary.json').read_text())
    m=json.loads((results/'measurements.json').read_text())
    cap=json.loads((results/'capacity.json').read_text())
    def number(v): return f'{v:,}'
    def table(name, header, rows, spec='lrr'):
        body='\\begin{tabular}{'+spec+'}\n\\toprule\n'+' & '.join(header)+' \\\\\n\\midrule\n'
        body+=''.join(' & '.join(map(str,row))+' \\\\\n' for row in rows)
        body+='\\bottomrule\n\\end{tabular}\n'
        (output/name).write_text(body)
    table('states.tex',['Measure','$n=2$','$n=3$'],[
        (title,number(small[key]),number(large[key])) for title,key in [
            ('Heap/root states','states'),('Safe pre-states','safe_states'),
            ('Changing-write candidates','transitions'),('Checker replays','checker_replays'),
            ('Frontier disagreements','frontier_mismatches'),('Checker disagreements','checker_mismatches')]])
    table('controls.tex',['Policy checked','$n=2$','$n=3$'],[
        (title,number(small[key]),number(large[key])) for title,key in [
            ('Exact read frontier','frontier_mismatches'),('Written object + newly reachable','direct_false_accepts'),
            ('Newly reachable only','stale_false_accepts'),('Roots only','root_false_accepts'),
            ('Ready bits only','phase_false_accepts'),('Well-formedness only','annotation_false_accepts')]])
    table('work.tex',['Measure','$n=2$','$n=3$'],[
        (title,number(small[key]),number(large[key])) for title,key in [
            ('Full predicate obligations','full_obligations'),('Frontier predicate obligations','frontier_obligations'),
            ('Checker steps','checker_steps')]])
    observations=[json.loads(x) for x in (results/'java-observations.jsonl').read_text().splitlines()]
    shapes=['Null edge','Self-loop','Two-node chain','Three-node chain','Two-node cycle','Three-node cycle','Shared tail','Tail into cycle']
    rows=[]
    for shape,name in enumerate(shapes):
        xs=[x for x in observations if x['shape']==shape]
        rows.append((name,max(len(x['heap']) for x in xs),sum(x['callbacks'] for x in xs),
            sum(x['incomplete_callbacks'] for x in xs),sum(x['valid'] for x in xs)))
    table('java.tex',['Shape','$n$','Calls','Partial','Valid'],rows,spec='lrrrr')
    values={'CandidateCount':number(small['transitions']+large['transitions']),
            'DirectMissCount':number(small['direct_false_accepts']+large['direct_false_accepts']),
            'MeasuredCPU':f"{m['cpu_seconds']:.2f}",'AggregateRSS':f"{m['aggregate_rss_upper_kib']/1024:.2f}",
            'CertificateBytes':str(cap['utf8_bytes_with_newline']),
            'CallbackCount':str(j['callback_snapshots']),'InvalidCallbacks':str(j['invalid_callback_snapshots'])}
    (output/'metrics.tex').write_text(''.join('\\newcommand{\\'+key+'}{'+value+'}\n' for key,value in values.items()))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();export(a.results.resolve(),a.out.resolve())
