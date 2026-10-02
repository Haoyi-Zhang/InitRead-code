"""Deterministic tests of certificate admission, revalidation, and state isolation."""
import copy
import unittest
from checker import Checker
from model import evaluate, successor, validate
from oracle import exact
from producer import initial_cache, produce

class CertificateTests(unittest.TestCase):
    def check_case(self, heap, roots, event):
        roots = frozenset(roots)
        cert = produce(heap, roots, initial_cache(heap, roots), event)
        check = Checker(heap, roots)
        newheap, newroots = successor(heap, roots, event)
        truth, _, _ = exact(newheap, newroots)
        self.assertEqual(check.inspect(event, cert), "ALLOW" if truth else "DENY_UNSAFE")
        return cert

    def test_cross_object_write(self):
        heap = ((1, 1, 1), (1, 1, -1))
        event = (1, 1, 0, -1)
        cert = self.check_case(heap, {0}, event)
        self.assertEqual(cert["decision"], "DENY_UNSAFE")
        # The modified object itself is still safe; its predecessor is not.
        newheap, _ = successor(heap, frozenset({0}), event)
        self.assertTrue(evaluate(newheap, 1)[0])
        self.assertFalse(evaluate(newheap, 0)[0])

    def test_cycle_and_alias(self):
        self.check_case(((1, 1, 1), (1, 1, 0)), {0}, (1, 1, 0, -1))
        self.check_case(((1, 1, 2), (1, 1, 2), (1, 1, -1)), {0, 1}, (2, 1, 0, -1))

    def test_new_reachable_raw(self):
        cert = self.check_case(((1, 0, -1), (0, 0, -1)), {0}, (0, 2, 1, -1))
        self.assertEqual(cert["decision"], "DENY_UNSAFE")

    def test_unreachable_mutation(self):
        cert = self.check_case(((1, 0, -1), (0, 1, -1)), {0}, (1, 1, 0, -1))
        self.assertEqual(cert["checks"], [])

    def test_remove_branch_replaces_footprint(self):
        h = ((1, 0, 1), (1, 1, -1)); roots = frozenset({0})
        checker = Checker(h, roots)
        event = (0, 2, -1, -1)
        self.assertEqual(checker.inspect(event, produce(h, roots, initial_cache(h, roots), event)), "ALLOW")
        self.assertEqual(checker.cache, {0: ((0, 0, 1), (0, 2, -1))})
        event2 = (1, 1, 0, -1)
        cert = produce(checker.heap, checker.roots, checker.cache, event2)
        self.assertEqual(cert["checks"], [])
        self.assertEqual(checker.inspect(event2, cert), "ALLOW")

    def test_deny_and_invalid_do_not_commit(self):
        h = ((1, 1, 1), (1, 1, -1)); roots = frozenset({0}); event = (1, 1, 0, -1)
        c = Checker(h, roots); before = c.snapshot()
        cert = produce(h, roots, initial_cache(h, roots), event)
        self.assertEqual(c.inspect(event, cert), "DENY_UNSAFE")
        self.assertEqual(c.snapshot(), before)
        cert["checks"] = []
        self.assertEqual(c.inspect(event, cert), "INVALID_CERT")
        self.assertEqual(c.snapshot(), before)

    def test_mutation_matrix(self):
        h = ((1, 0, 1), (1, 1, -1)); roots = frozenset({0}); event = (1, 1, 1, -1)
        cert = produce(h, roots, initial_cache(h, roots), event)
        changes = []
        def mutate(fn):
            copycert = copy.deepcopy(cert); fn(copycert); changes.append(copycert)
        mutate(lambda d: d["reachable"].pop())
        mutate(lambda d: d["reachable"].append(0))
        mutate(lambda d: d["reachable"].reverse())
        mutate(lambda d: d["checks"].clear())
        mutate(lambda d: d["checks"].append(copy.deepcopy(d["checks"][0])))
        mutate(lambda d: d["checks"][0].__setitem__("object", True))
        mutate(lambda d: d["checks"][0].__setitem__("object", 1))
        mutate(lambda d: d["checks"][0].__setitem__("result", 1))
        mutate(lambda d: d["checks"][0].__setitem__("result", False))
        mutate(lambda d: d["checks"][0]["reads"].pop())
        mutate(lambda d: d["checks"][0]["reads"][0].__setitem__(2, 0))
        mutate(lambda d: d["checks"][0]["reads"][0].__setitem__(0, True))
        mutate(lambda d: d.__setitem__("decision", "DENY_UNSAFE"))
        mutate(lambda d: d.__setitem__("extra", 1))
        for malformed in changes + [None, [], {}, {"reachable": []}]:
            c = Checker(h, roots); before = c.snapshot()
            self.assertEqual(c.inspect(event, malformed), "INVALID_CERT")
            self.assertEqual(c.snapshot(), before)

    def test_admission(self):
        for h, r in [((), []), (((1, 0, 1),), [0]), (((1, 2, -1),), [0]),
                     (((1, 0, -1),), [True]), (((0, 0, -1),), [0])]:
            with self.assertRaises(ValueError):
                Checker(h, r)
        heap = ((1, 0, -1),)
        for roots in ([0, False], [False, 0], [0, 0.0], [0.0, 0],
                      (0, False), (False, 0), (0, 0.0), (0.0, 0)):
            with self.subTest(roots=roots):
                with self.assertRaises(ValueError):
                    Checker(heap, roots)
        for roots in ([0, 0], (0, 0)):
            with self.subTest(duplicate_roots=roots):
                self.assertEqual(Checker(heap, roots).roots, frozenset({0}))
        c = Checker(heap, [0])
        for event in [(0, 9, 0, -1), (0, 1, 2, -1), (True, 1, 0, -1), None]:
            self.assertEqual(c.inspect(event, {}), "INVALID_CERT")

    def test_external_retention_must_be_observed(self):
        # A retained external alias is a root even after the original link is cut.
        h = ((1, 0, 1), (1, 0, -1)); roots = frozenset({0})
        c = Checker(h, roots)
        events = [(0, 1, 0, 1), (0, 2, -1, -1)]
        for event in events:
            cert = produce(c.heap, c.roots, c.cache, event)
            self.assertEqual(c.inspect(event, cert), "ALLOW")
        event = (1, 0, 0, -1)
        self.assertEqual(c.inspect(event, produce(c.heap, c.roots, c.cache, event)), "DENY_UNSAFE")
        # Omit the retention event: the observer's heap has no visible root to object 1.
        # This is a different, incomplete observation, not a counterexample to the
        # model theorem under its complete-root assumption.
        hidden = Checker(h, roots)
        for event in [(0, 2, -1, -1), (1, 0, 0, -1)]:
            cert = produce(hidden.heap, hidden.roots, hidden.cache, event)
            self.assertEqual(hidden.inspect(event, cert), "ALLOW")
        self.assertFalse(exact(hidden.heap, frozenset({0,1}))[0])

    def test_bounded_admission(self):
        for h, roots in [(iter([(1, 0, -1)]), []), ([(1, 0, -1)], [0]*129),
                         ([(1, 0, -1, 0)], []), ([(1, 0, -1)]*129, [])]:
            with self.assertRaises(ValueError):
                Checker(h, roots)
        self.assertEqual(Checker([(1, 0, -1)], [0]*128).roots, frozenset({0}))

    def test_bound_128(self):
        heap = tuple((1, 1, (i + 1) % 128) for i in range(128))
        roots = frozenset({0})
        cert = produce(heap, roots, initial_cache(heap, roots), (127, 1, 0, -1))
        c = Checker(heap, roots)
        self.assertEqual(c.inspect((127, 1, 0, -1), cert), "DENY_UNSAFE")
        with self.assertRaises(ValueError):
            Checker(heap + ((1, 0, -1),), roots)

    def test_claimed_declared_policy_not_constructor_history(self):
        # Ready is supplied metadata: admission is deliberately not constructor attestation.
        c = Checker(((1, 1, -1),), [0])
        self.assertEqual(len(c.cache), 1)

if __name__ == "__main__":
    unittest.main()
