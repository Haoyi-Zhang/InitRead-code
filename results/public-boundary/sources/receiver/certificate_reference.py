"""Independent declarative oracle for integer certificate packets.

No imports, producer, production parser, cached dependency data, or Java code.
Reachability is recomputed as a set fixed point. Previous reads are recomputed
from the whole previous heap, not taken from a production cache. This validates
the integer packet, not Java's serialization format or the JDK implementation.
"""


def classify(words):
    if type(words) is not list or not 5 <= len(words) <= 24576:
        return 'INVALID_FRAME'
    if any(type(w) is not int or not -(1 << 31) <= w < (1 << 31) for w in words):
        return 'INVALID_WORDS'
    # Cursor/index logic intentionally independent of the production Cursor.
    at = 0

    def pull():
        nonlocal at
        if at == len(words):
            raise IndexError
        word = words[at]
        at += 1
        return word

    def expect(sequence):
        for item in sequence:
            if pull() != item:
                raise ValueError

    def reachable(heap, roots):
        result = set(roots)
        while True:
            expanded = result | {heap[i][2] for i in result if heap[i][2] != -1}
            if expanded == result:
                return result
            result = expanded

    def observe(heap, i):
        a, value, nxt = heap[i]
        records = [[i, 0, a]]
        if a == 0:
            return False, records
        records.append([i, 2, nxt])
        if nxt == -1:
            return True, records
        records.extend([[i, 1, value], [nxt, 1, heap[nxt][1]]])
        return value <= heap[nxt][1], records

    try:
        if (pull(), pull()) != (0x52434331, 1):
            return 'INVALID_DATA'
        n, m = pull(), pull()
        if not 1 <= n <= 128 or not 0 <= m <= 128:
            return 'INVALID_DATA'
        values = [pull() for _ in range(n)]
        if any(v not in (0, 1) for v in values):
            return 'INVALID_DATA'
        links = [pull() for _ in range(n)]
        if any(not -1 <= i < n for i in links):
            return 'INVALID_DATA'
        roots = [pull() for _ in range(m)]
        if any(not 0 <= i < n for i in roots):
            return 'INVALID_DATA'
        supplied = pull()
        if not 0 <= supplied <= 512:
            return 'INVALID_CERT'
        schedule = [(i, 1, v, -1) for i, v in enumerate(values)]
        schedule += [(i, 2, t, -1) for i, t in enumerate(links)]
        schedule += [(i, 0, 1, -1) for i in range(n)]
        schedule += [(r, 0, 1, r) for r in roots]
        heap, retained = [[0, 0, -1] for _ in range(n)], set()
        for step, (obj, field, value, root) in enumerate(schedule, 1):
            if step > supplied:
                return 'INVALID_CERT'
            old_live = reachable(heap, retained)
            old_reads = {i: observe(heap, i)[1] for i in old_live}
            candidate = [row[:] for row in heap]
            candidate[obj][field] = value
            new_roots = retained | ({root} if root >= 0 else set())
            live = reachable(candidate, new_roots)
            affected = sorted(i for i in live if i not in old_live or
                              any(r[:2] == [obj, field] for r in old_reads[i]))
            expected = [len(live), *sorted(live), len(affected)]
            decision = True
            for i in affected:
                ok, reads = observe(candidate, i)
                decision = decision and ok
                expected.extend([i, int(ok), len(reads)])
                for read in reads:
                    expected.extend(read)
            expected.append(int(decision))
            expect(expected)
            # Denial establishes an unsafe prefix, not a fully parsed tail.
            if not decision:
                return 'DENY_UNSAFE'
            heap, retained = candidate, new_roots
        if supplied != len(schedule) or at != len(words):
            return 'INVALID_CERT'
        return 'ALLOW'
    except (IndexError, ValueError):
        return 'INVALID_CERT'
