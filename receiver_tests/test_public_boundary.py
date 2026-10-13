import copy
import json
from pathlib import Path
import unittest

from reproduce_public_boundary import eager_words, verify_public
from receiver.producer import packet
from receiver.reference import decide
from receiver.certificate_reference import classify


class PublicBoundaryTests(unittest.TestCase):
    @staticmethod
    def prefix_cases():
        path = Path(__file__).parents[1] / 'inputs/data-prefix-regressions.json'
        return json.loads(path.read_text(encoding='utf-8'))['cases']

    def test_six_named_complete_data_prefixes(self):
        cases = self.prefix_cases()
        self.assertEqual(len(cases), 6)
        self.assertEqual(len({case['id'] for case in cases}), 6)
        retained = {}
        path = Path(__file__).parents[1] / 'results/specialization-campaign/cases.tsv'
        for line in path.read_text(encoding='utf-8').splitlines():
            ident, _, text = line.split('\t')
            retained[ident] = [int(cell) for cell in text.split(',')]
        for case in cases:
            with self.subTest(case=case['id']):
                words = case['words']
                self.assertEqual(words, retained[case['id']])
                n, m = words[2:4]
                self.assertEqual(len(words), 4 + 2*n + m)
                truth = decide(words)
                self.assertEqual(truth['status'], case['data'])
                self.assertEqual(classify(words), case['certificate'])
                simple = eager_words(truth['values'], truth['links'], truth['roots'])
                self.assertEqual(simple, words + [0])
                self.assertEqual(decide(simple), truth)

    def test_truly_incomplete_data_prefixes_are_rejected(self):
        for case in self.prefix_cases():
            for end in range(len(case['words'])):
                with self.subTest(case=case['id'], end=end):
                    self.assertEqual(decide(case['words'][:end])['status'], 'INVALID_DATA')

    def test_complete_prefix_preserves_type_and_domain_checks(self):
        words = self.prefix_cases()[0]['words']
        for index, value in ((4, False), (4, 0.0), (4, 2), (6, 2), (8, -1)):
            with self.subTest(index=index, value=value):
                changed = words.copy()
                changed[index] = value
                self.assertEqual(decide(changed)['status'], 'INVALID_DATA')

    def test_complete_unsafe_prefix_is_denied_without_proof(self):
        words = packet([1, 0], [1, -1], [0])[0]
        prefix = words[:4 + 2*2 + 1]
        self.assertEqual(decide(prefix)['status'], 'DENY_UNSAFE')
        self.assertEqual(classify(prefix), 'INVALID_CERT')

    def test_same_information_without_proof(self):
        for values, links, roots in [([1, 0], [1, -1], [0]), ([1, 0], [1, -1], []),
                                     ([1, 1], [1, 0], [0, 0]), ([0], [0], [0])]:
            certified = packet(values, links, roots)[0]
            simple = eager_words(values, links, roots)
            self.assertEqual(decide(certified), decide(simple))
            self.assertEqual(classify(certified), decide(simple)['status'])
            self.assertLess(len(simple), len(certified))

    def test_public_only_binding_rejects_wrong_navigation(self):
        truth = decide(eager_words([1, 1, 1, 0], [1, 0, 3, -1], [0, 0]))
        row = {'status': 'ALLOW', 'has_graph': True, 'canonical_aliases': True, 'frozen': True,
               'roots': [0, 0], 'nodes': [[0, 1, 1], [1, 1, 0]], 'words': 15, 'bytes': 87}
        verify_public(row, truth, 'ALLOW')
        for key, bad in [('nodes', [[0, 1, 1]]), ('nodes', [[0, 0, 1], [1, 1, 0]]),
                         ('nodes', row['nodes'] + [[2, 1, 3]]), ('roots', [0]),
                         ('canonical_aliases', False), ('frozen', False), ('bytes', 88)]:
            changed = copy.deepcopy(row)
            changed[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(AssertionError):
                verify_public(changed, truth, 'ALLOW')

    def test_denial_has_no_public_nodes(self):
        truth = decide(eager_words([1, 0], [1, -1], [0]))
        row = {'status': 'DENY_UNSAFE', 'has_graph': False, 'roots': None, 'nodes': [],
               'canonical_aliases': True, 'frozen': True, 'words': 10, 'bytes': 67}
        verify_public(row, truth, 'DENY_UNSAFE')
        row['nodes'] = [[0, 1, 1]]
        with self.assertRaises(AssertionError):
            verify_public(row, truth, 'DENY_UNSAFE')


if __name__ == '__main__':
    unittest.main()
