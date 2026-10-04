#!/usr/bin/env python3
"""Generate manuscript tables directly from the retained specialization run."""
import argparse
import json
import statistics
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    summary = json.loads((args.results/'summary.json').read_text())
    if not summary['pass']:
        raise SystemExit('Refusing to export a failed study.')
    perf = json.loads((args.results/'performance.json').read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    names = {'chain-one':'Chain / one root','cycle-one':'Cycle / one root',
             'isolated-repeat':'Isolated / repeated root','cycle-repeat':'Cycle / repeated root'}
    rows = [r'\begin{tabular}{lrrr}',r'\toprule',r'Family & Generic & Specialized & Eager \\',r'\midrule']
    ratios = [r'\begin{tabular}{lrr}',r'\toprule',r'Family & Generic / specialized & Specialized / eager \\',r'\midrule']
    for row in perf['rows']:
        modes=row['modes']
        cells=[f"{modes[m]['median_us']:.2f} [{modes[m]['min_us']:.2f}, {modes[m]['max_us']:.2f}]" for m in ('generic','specialized','eager')]
        rows.append(names[row['family']]+' & '+' & '.join(cells)+r' \\')
        ratio_cells=[]
        for k in ('generic_over_specialized','specialized_over_eager'):
            v=[r[k] for r in row['paired_ratios']]
            ratio_cells.append(f"{statistics.median(v):.2f} [{min(v):.2f}, {max(v):.2f}]")
        ratios.append(names[row['family']]+' & '+' & '.join(ratio_cells)+r' \\')
    for name,lines in [('specialization-performance.tex',rows),('specialization-ratios.tex',ratios)]:
        lines.extend([r'\bottomrule',r'\end{tabular}'])
        (args.out/name).write_text('\n'.join(lines)+'\n')
    print(json.dumps({'tables':2,'cases':summary['java_cases'],'source':'specialization-campaign'},sort_keys=True))

if __name__ == '__main__':
    main()
