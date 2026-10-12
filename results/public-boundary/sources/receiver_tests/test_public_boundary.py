import copy
import unittest

from reproduce_public_boundary import eager_words, verify_public
from receiver.producer import packet
from receiver.reference import decide
from receiver.certificate_reference import classify


class PublicBoundaryTests(unittest.TestCase):
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
