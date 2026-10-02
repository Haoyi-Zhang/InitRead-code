"""Small stateful checker, separately implemented from producer and oracle.

Trusts caller-supplied complete events and its admitted initial state; it does
not attest a JVM. Invalid certificates leave heap, roots, and cache unchanged; diagnostic step counts may change.
No producer/model/oracle code is imported here.
"""
from copy import deepcopy

class Checker:
    def __init__(self, heap, roots):
        if type(heap) not in (tuple, list) or not 1 <= len(heap) <= 128:
            raise ValueError("heap must be a bounded record sequence")
        if any(type(row) not in (tuple, list) or len(row) != 3 for row in heap):
            raise ValueError("bounded three-field records required")
        if type(roots) not in (tuple, list, set, frozenset) or len(roots) > 128:
            raise ValueError("bounded root collection required")
        # Validate every supplied root before set conversion.  Python considers
        # 0 == False == 0.0, so deduplicating first could hide an invalid value.
        self.heap = tuple(tuple(row) for row in heap)
        self._admit(self.heap, roots)
        self.roots = frozenset(roots)
        self.cache = {}
        for obj in self._closure(self.heap, self.roots):
            result, reads = self._policy(self.heap, obj)
            if not result:
                raise ValueError("unsafe initial exposure")
            self.cache[obj] = reads
        self.steps = 0

    @staticmethod
    def _admit(heap, roots):
        n = len(heap)
        if not 1 <= n <= 128:
            raise ValueError("heap size outside 1..128")
        for row in heap:
            if len(row) != 3 or any(type(v) is not int for v in row):
                raise ValueError("invalid record")
            if row[0] not in (0, 1) or row[1] not in (0, 1) or not -1 <= row[2] < n:
                raise ValueError("invalid field domain")
        if any(type(r) is not int or not 0 <= r < n for r in roots):
            raise ValueError("invalid root")

    @staticmethod
    def _closure(heap, roots):
        current = set(roots)
        while True:
            following = current | {heap[i][2] for i in current if heap[i][2] != -1}
            if following == current:
                return current
            current = following

    @staticmethod
    def _policy(heap, obj):
        # Explicit branch cases, rather than the producer's nested read evaluator.
        transcript = [(obj, 0, heap[obj][0])]
        if heap[obj][0] == 0:
            return False, tuple(transcript)
        target = heap[obj][2]
        transcript.append((obj, 2, target))
        if target == -1:
            return True, tuple(transcript)
        transcript += [(obj, 1, heap[obj][1]), (target, 1, heap[target][1])]
        return heap[obj][1] <= heap[target][1], tuple(transcript)

    def inspect(self, event, cert):
        """ALLOW commits, DENY_UNSAFE/INVALID_CERT never commit.

        step count: one per frontier membership/coverage/read validation plus
        decision validation. Resource exhaustion by an enclosing runner is UNKNOWN.
        """
        try:
            if type(event) not in (list, tuple) or len(event) != 4 or any(type(v) is not int for v in event):
                raise ValueError("bad event")
            obj, field, value, add = event
            if not (0 <= obj < len(self.heap) and 0 <= field < 3 and -1 <= add < len(self.heap)):
                raise ValueError("bad event domain")
            rows = [list(r) for r in self.heap]
            rows[obj][field] = value
            candidate = tuple(tuple(r) for r in rows)
            roots = self.roots | ({add} if add != -1 else set())
            self._admit(candidate, roots)
            if type(cert) is not dict or len(cert) != 3 or set(cert) != {"reachable", "checks", "decision"}:
                raise ValueError("bad certificate envelope")
            live = self._closure(candidate, roots)
            claimed = cert["reachable"]
            if type(claimed) is not list or len(claimed) > 128 or any(type(x) is not int for x in claimed) or claimed != sorted(live):
                raise ValueError("closure not exact")
            self.steps += len(live)
            needed = []
            for current in sorted(live):
                self.steps += 1
                previous = self.cache.get(current)
                if previous is None or any(a == obj and b == field for a, b, _ in previous):
                    needed.append(current)
            checks = cert["checks"]
            if type(checks) is not list or len(checks) != len(needed):
                raise ValueError("missing/extra obligation")
            alltrue = True
            updated = {i: self.cache[i] for i in live if i in self.cache and i not in needed}
            for current, entry in zip(needed, checks):
                if type(entry) is not dict or len(entry) != 3 or set(entry) != {"object", "result", "reads"}:
                    raise ValueError("bad proof entry")
                if type(entry["object"]) is not int or entry["object"] != current or type(entry["result"]) is not bool:
                    raise ValueError("bad proof object/result")
                correct, reads = self._policy(candidate, current)
                claimed_reads = entry["reads"]
                if type(claimed_reads) is not list or len(claimed_reads) > 4 or any(
                    type(t) is not list or len(t) != 3 or any(type(v) is not int for v in t)
                    for t in claimed_reads):
                    raise ValueError("bad read records")
                if tuple(tuple(t) for t in claimed_reads) != reads or entry["result"] is not correct:
                    raise ValueError("invalid read transcript")
                self.steps += len(reads)
                alltrue &= correct
                updated[current] = reads
            expected = "ALLOW" if alltrue else "DENY_UNSAFE"
            self.steps += 1
            if type(cert["decision"]) is not str or cert["decision"] != expected:
                raise ValueError("unjustified decision")
            if alltrue:
                self.heap, self.roots, self.cache = candidate, frozenset(roots), updated
            return expected
        except (ValueError, TypeError, KeyError, IndexError):
            return "INVALID_CERT"

    def snapshot(self):
        return deepcopy((self.heap, self.roots, self.cache))
