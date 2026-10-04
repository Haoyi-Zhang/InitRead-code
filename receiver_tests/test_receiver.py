import ast
from pathlib import Path
import unittest
from receiver.producer import packet
from receiver.reference import decide

class RootTests(unittest.TestCase):
    def test_exact_type_before_deduplication(self):
        for C in (list, tuple):
            for xs in ([0,False],[False,0],[0,0.0],[0.0,0]):
                with self.subTest(container=C.__name__, values=xs):
                    with self.assertRaises(ValueError): packet([1],[-1],C(xs))
            for xs in ([0],[0,0],[0]*128):
                self.assertEqual(decide(packet([1],[-1],C(xs))[0])['status'],'ALLOW')
            with self.assertRaises(ValueError): packet([1],[-1],C([0]*129))
    def test_reference_import_separation(self):
        tree=ast.parse((Path(__file__).parents[1]/'receiver/reference.py').read_text())
        self.assertFalse(any(isinstance(x,(ast.Import,ast.ImportFrom)) for x in ast.walk(tree)))
    def test_fixed_semantics(self):
        self.assertEqual(decide(packet([1,0],[1,-1],[0])[0])['status'],'DENY_UNSAFE')
        self.assertEqual(decide(packet([1,0],[1,-1],[])[0])['status'],'ALLOW')
        self.assertEqual(decide(packet([1,1],[1,0],[0])[0])['status'],'ALLOW')
    def test_reference_no_equal_type_erasure(self):
        w,_=packet([1],[-1],[0]);w[6]=False
        self.assertEqual(decide(w)['status'],'INVALID_DATA')
    def test_data_source_bound_and_domain(self):
        for v,t,r in [([2],[-1],[0]),([0],[1],[0]),([0],[-1],[-1]),([],[],[])]:
            with self.assertRaises(ValueError): packet(v,t,r)
if __name__=='__main__': unittest.main()
