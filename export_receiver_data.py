#!/usr/bin/env python3
"""Generate receiver manuscript tables from recorded results (standard library)."""
import argparse
import json
from pathlib import Path


def export(results: Path, output: Path) -> None:
    s = json.loads((results / 'summary.json').read_text(encoding='utf-8'))
    p = json.loads((results / 'performance.json').read_text(encoding='utf-8'))
    if not s.get('pass'):
        raise ValueError('Refusing to export a failing campaign as accepted evidence')
    output.mkdir(parents=True, exist_ok=True)
    def table(name, spec, header, rows):
        body = '\\begin{tabular}{' + spec + '}\n\\toprule\n'
        body += ' & '.join(header) + ' \\\\\n\\midrule\n'
        body += ''.join(' & '.join(map(str, row)) + ' \\\\\n' for row in rows)
        body += '\\bottomrule\n\\end{tabular}\n'
        (output / name).write_text(body, encoding='utf-8')
    names = [('exact','Exact data, $n=1,2,3$'),('heldout','Larger structure cases'),
             ('renamed','Identity-renamed cases'),('capacity','Capacity cases'),
             ('certificate-control','Certificate controls'),('data-control','Data controls'),
             ('wire-control','Wire controls'),('fault-control','Construction-failure control')]
    rows = [(title,f"{s['counts'][key]:,}") for key,title in names]
    rows += [('Total actual Java cases',f"{s['actual_java_cases']:,}")]
    table('receiver-cases.tex','lr',['Case family','Count'],rows)
    rows=[]
    for r in p['rows']:
        c,e = r['modes']['certificate'],r['modes']['eager']
        rows.append((r['n'],f"{c['median_us']:.2f}",f"{c['min_us']:.2f}--{c['max_us']:.2f}",
                     f"{e['median_us']:.2f}",f"{e['min_us']:.2f}--{e['max_us']:.2f}",
                     f"{r['certificate_over_eager']:.2f}"))
    table('receiver-performance.tex','rrrrrr',
          ['$n$','Certificate median','Certificate range','Eager median','Eager range','Ratio'],rows)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    export(args.results.resolve(),args.out.resolve())
