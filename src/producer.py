"""Untrusted certificate producer for one abstract candidate transition."""
from model import evaluate, reachable, successor, validate

def initial_cache(heap, roots):
    validate(heap, roots)
    out = {}
    for obj in sorted(reachable(heap, roots)):
        ok, reads = evaluate(heap, obj)
        if not ok:
            raise ValueError("initial exposed state is not safe")
        out[obj] = reads
    return out

def produce(heap, roots, cache, event):
    newheap, newroots = successor(heap, roots, event)
    oldreach = reachable(heap, roots)
    newreach = reachable(newheap, newroots)
    changed = (event[0], event[1])
    frontier = (newreach - oldreach) | {
        obj for obj in newreach & oldreach
        if changed in {(a, b) for a, b, _ in cache[obj]}
    }
    checks = []
    alltrue = True
    for obj in sorted(frontier):
        ok, reads = evaluate(newheap, obj)
        alltrue &= ok
        checks.append({"object": obj, "result": ok, "reads": [list(t) for t in reads]})
    return {"reachable": sorted(newreach), "checks": checks,
            "decision": "ALLOW" if alltrue else "DENY_UNSAFE"}
