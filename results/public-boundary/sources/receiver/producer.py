"""Untrusted data-only certificate producer. No runtime authority is exported.

Uses the inherited producer on a locally determined restoration schedule. The
receiver independently derives that schedule from the separately parsed data.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from producer import produce
from model import successor, evaluate, reachable

MAGIC = 0x52434331
MAX_WORDS = 24576

def admit(values, links, roots):
    if type(values) not in (list, tuple) or not 1 <= len(values) <= 128:
        raise ValueError('values container')
    n = len(values)
    if type(links) not in (list, tuple) or len(links) != n:
        raise ValueError('links container')
    if type(roots) not in (list, tuple) or len(roots) > 128:
        raise ValueError('roots container')
    if any(type(v) is not int or v not in (0, 1) for v in values):
        raise ValueError('value type/domain')
    if any(type(t) is not int or not -1 <= t < n for t in links):
        raise ValueError('link type/domain')
    # MUST precede any operation that collapses equal bool/float/int values.
    if any(type(r) is not int or not 0 <= r < n for r in roots):
        raise ValueError('root type/domain')


def packet(values, links, roots):
    admit(values, links, roots)
    n = len(values)
    words = [MAGIC, 1, n, len(roots), *values, *links, *roots]
    events = [(i, 1, v, -1) for i, v in enumerate(values)]
    events += [(i, 2, t, -1) for i, t in enumerate(links)]
    events += [(i, 0, 1, -1) for i in range(n)]
    # A same-value write plus root addition uses the original event language.
    events += [(r, 0, 1, r) for r in roots]
    heap, retained, cache = tuple((0, 0, -1) for _ in values), frozenset(), {}
    proofs, semantic = [], []
    for e in events:
        cert = produce(heap, retained, cache, e)
        proofs.append(cert)
        semantic.append({'event': list(e), 'certificate': cert})
        if cert['decision'] != 'ALLOW':
            break
        heap, retained = successor(heap, retained, e)
        cache = {o: evaluate(heap, o)[1] for o in reachable(heap, retained)}
    words.append(len(proofs))
    for c in proofs:
        words.extend([len(c['reachable']), *c['reachable'], len(c['checks'])])
        for entry in c['checks']:
            words.extend([entry['object'], int(entry['result']), len(entry['reads'])])
            for read in entry['reads']:
                words.extend(read)
        words.append(int(c['decision'] == 'ALLOW'))
    if len(words) > MAX_WORDS:
        raise ValueError('certificate word bound')
    return words, semantic
