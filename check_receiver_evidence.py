#!/usr/bin/env python3
"""Check exact packet-size evidence against saved, actually serialized inputs."""
import argparse
import json
from pathlib import Path

def check(results: Path):
    records = [json.loads(s) for s in (results/'inputs.jsonl').read_text().splitlines() if s]
    failures=[]; max_words=0; honest_safe=0
    for row in records:
        words=row['words']; raw=(results/'streams'/(row['id']+'.ser')).read_bytes()
        if len(raw) != 27+4*len(words): failures.append(row['id']+':canonical-length')
        if row['kind'] in ('exact','heldout','renamed','capacity') and row['reference']['status']=='ALLOW':
            honest_safe+=1; n,m=words[2:4]; bound=5+26*n+19*m+n*m
            if len(words)>bound or 27+4*bound>131072: failures.append(row['id']+':honest-bound')
            max_words=max(max_words,len(words))
    return {'integer_array_frames_checked':len(records),'honest_safe_frames_checked':honest_safe,
            'actual_max_honest_words':max_words,'general_honest_word_bound':22149,
            'general_honest_byte_bound_for_specified_writer':88623,
            'failures':failures,'pass':not failures,
            'scope':'finite evidence plus stated exact fresh primitive-array writer, not arbitrary Java stream overhead'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists(): raise SystemExit('Output file already exists; use a fresh path')
    r=check(a.results.resolve());a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
    raise SystemExit(0 if r['pass'] else 1)
