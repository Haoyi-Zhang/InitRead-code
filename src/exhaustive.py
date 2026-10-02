"""Deterministic exhaustive repair pilot; bounded single worker, exact small oracle."""
from __future__ import annotations
import csv
import itertools
import json
import resource
import time
from pathlib import Path
from model import evaluate, reachable, successor
from oracle import exact
from producer import initial_cache, produce
from checker import Checker

COUNTERS = ("states", "safe_states", "transitions", "frontier_mismatches", "direct_false_accepts",
            "stale_false_accepts", "root_false_accepts", "phase_false_accepts", "annotation_false_accepts",
            "full_obligations", "frontier_obligations", "checker_replays", "checker_mismatches", "checker_steps")

def run(n: int, out: Path, stride: int = 1):
    if n not in (2, 3) or stride < 1:
        raise ValueError("only the frozen two- and three-object campaigns are supported")
    begin_cpu, begin_wall = time.process_time(), time.perf_counter()
    totals = dict.fromkeys(COUNTERS, 0)
    examples = {}
    domain = tuple(itertools.product((0, 1), (0, 1), range(-1, n)))
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"exhaustive-{n}-states.csv").open("w", newline="") as f:
        fields = ["heap_index", "root_mask"] + list(COUNTERS)[2:]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for heap_index, heap in enumerate(itertools.product(domain, repeat=n)):
            if time.perf_counter() - begin_wall > 120:
                raise RuntimeError("bounded exhaustive run timed out: UNKNOWN")
            for mask in range(1 << n):
                totals["states"] += 1
                roots = frozenset(i for i in range(n) if (mask >> i) & 1)
                safe, oldlive, _ = exact(heap, roots)
                if not safe:
                    continue
                totals["safe_states"] += 1
                cache = initial_cache(heap, roots)
                local = dict.fromkeys(COUNTERS[2:], 0)
                for obj in range(n):
                    for field, values in enumerate(((0, 1), (0, 1), range(-1, n))):
                        for value in values:
                            if value == heap[obj][field]:
                                continue
                            for add in (-1, *range(n)):
                                event = (obj, field, value, add)
                                newheap, newroots = successor(heap, roots, event)
                                truth, newlive, bad = exact(newheap, newroots)
                                frontier = (newlive - oldlive) | {
                                    k for k in newlive & oldlive
                                    if any(a == obj and b == field for a, b, _ in cache[k])}
                                evaluations = {k: evaluate(newheap, k)[0] for k in newlive}
                                selected = all(evaluations[k] for k in frontier)
                                direct = all(evaluations[k] for k in ((newlive - oldlive) | ({obj} & newlive)))
                                stale = all(evaluations[k] for k in (newlive - oldlive))
                                rootonly = all(evaluations[k] for k in newroots)
                                phaseonly = all(newheap[k][0] == 1 for k in newlive)
                                local["transitions"] += 1
                                local["full_obligations"] += len(newlive)
                                local["frontier_obligations"] += len(frontier)
                                local["frontier_mismatches"] += (selected != truth)
                                options = {"direct": direct, "stale": stale, "root": rootonly,
                                           "phase": phaseonly, "annotation": True}
                                for label, decision in options.items():
                                    if decision and not truth:
                                        local[f"{label}_false_accepts"] += 1
                                        examples.setdefault(label, {"heap": heap, "roots": sorted(roots),
                                            "event": event, "post_heap": newheap, "post_roots": sorted(newroots),
                                            "violating_objects": bad, "frontier": sorted(frontier)})
                                # stride=1 checks every transition; the recorded repair pilot used stride=127.
                                absolute_index = totals["transitions"] + local["transitions"] - 1
                                if absolute_index % stride == 0:
                                    checker = Checker(heap, roots)
                                    certificate = produce(heap, roots, cache, event)
                                    before = checker.snapshot()
                                    decision = checker.inspect(event, certificate)
                                    local["checker_replays"] += 1
                                    local["checker_steps"] += checker.steps
                                    local["checker_mismatches"] += (decision != ("ALLOW" if truth else "DENY_UNSAFE"))
                                    if not truth and before != checker.snapshot():
                                        raise AssertionError("denial changed trusted checker state")
                                if totals["transitions"] + local["transitions"] > 2_000_000:
                                    raise RuntimeError("frozen transition budget exhausted: UNKNOWN")
                writer.writerow({"heap_index": heap_index, "root_mask": mask, **local})
                for key, value in local.items():
                    totals[key] += value
    result = {"n": n, "policy": "ready and (next is null or value<=next.value)",
              "counts": totals, "examples": examples, "sampling_stride": stride,
              "cpu_seconds": time.process_time() - begin_cpu,
              "wall_seconds": time.perf_counter() - begin_wall,
              "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "status": "FINITE_CHECKED"}
    (out / f"exhaustive-{n}.json").write_text(json.dumps(result, indent=2) + "\n")
    assert totals["frontier_mismatches"] == totals["checker_mismatches"] == 0
    assert totals["direct_false_accepts"] > 0
    return result
