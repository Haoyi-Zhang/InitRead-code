"""Separately written exact oracle: dense closure and eager relational checks.

No imports from producer/model/checker. This implementation separation is NOT
independent authorship or a machine-checked correctness proof.
"""
def exact(heap, roots):
    n = len(heap)
    closure = [[i == j or heap[i][2] == j for j in range(n)] for i in range(n)]
    for pivot in range(n):
        for start in range(n):
            if closure[start][pivot]:
                for end in range(n):
                    closure[start][end] |= closure[pivot][end]
    live = {j for j in range(n) if any(closure[i][j] for i in roots)}
    bad = []
    for obj in sorted(live):
        ready, value, target = heap[obj]
        if ready != 1 or (target >= 0 and value > heap[target][1]):
            bad.append(obj)
    return not bad, live, bad
