import ast
from pathlib import Path
import unittest

from receiver.producer import packet
from receiver.certificate_reference import classify


class SpecializationReferenceTests(unittest.TestCase):
    def test_no_production_imports(self):
        source = (Path(__file__).parents[1] / 'receiver/certificate_reference.py').read_text()
        self.assertFalse(any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(ast.parse(source))))

    def test_independent_reference_domains_and_denial(self):
        for v, p, roots, wanted in [([0], [-1], [0], 'ALLOW'),
                                   ([1, 0], [1, -1], [0], 'DENY_UNSAFE'),
                                   ([1, 0], [1, -1], [], 'ALLOW')]:
            self.assertEqual(classify(packet(v, p, roots)[0]), wanted)
        w = packet([0], [-1], [0])[0]
        for bad in (False, 0.0):
            z = w.copy(); z[6] = bad
            self.assertEqual(classify(z), 'INVALID_WORDS')

    def test_sharp_bound_attained_by_cycles(self):
        for n in (1, 2, 3, 7, 32, 128):
            for m in (0, 1, 2, 7, 128):
                with self.subTest(n=n, m=m):
                    w = packet([1] * n, list(range(1, n)) + [0], [0] * m)[0]
                    bound = 5 + 11*n if m == 0 else n*m + 26*n + 19*m - 10
                    self.assertEqual(len(w), bound)
                    self.assertEqual(classify(w), 'ALLOW')

    def test_every_certificate_cell_matters(self):
        for v, links, roots in [([0], [0], [0]), ([1, 1, 1], [1, 2, 0], [0, 0, 2])]:
            w = packet(v, links, roots)[0]
            offset = 4 + 2*len(v) + len(roots)
            for index in range(offset, len(w)):
                z = w.copy(); z[index] ^= 1
                self.assertNotEqual(classify(z), 'ALLOW')
            for end in range(offset, len(w)):
                self.assertNotEqual(classify(w[:end]), 'ALLOW')
            self.assertNotEqual(classify(w + [0]), 'ALLOW')

    def test_denial_is_a_prefix_not_a_tail_certificate(self):
        w = packet([1, 0], [1, -1], [0])[0]
        self.assertEqual(classify(w), 'DENY_UNSAFE')
        self.assertEqual(classify(w + [11, 22]), 'DENY_UNSAFE')
        safe = packet([1, 1], [1, -1], [0])[0]
        self.assertEqual(classify(safe + [11, 22]), 'INVALID_CERT')


if __name__ == '__main__':
    unittest.main()
