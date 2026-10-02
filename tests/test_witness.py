import json
import unittest
from pathlib import Path
from witness import bfs, enumerated_oracle

class WitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.programs=json.loads((Path(__file__).resolve().parents[1]/'inputs'/'witness-programs.json').read_text())
    def test_shortlex_matches_full_path_oracle(self):
        for p in self.programs:
            a,b=bfs(p),enumerated_oracle(p)
            if a['status']=='VIOLATION':
                self.assertEqual(a['trace'], b['trace'])
                self.assertEqual(b['status'], 'VIOLATION')
    def test_phase_erasure_loses_bad_trace(self):
        self.assertEqual(bfs(self.programs[3])['trace'], [0,1])
        self.assertEqual(bfs(self.programs[3],key_mode='erase-ready')['status'], 'SAFE')
    def test_epoch_retention_prevents_closure(self):
        self.assertEqual(bfs(self.programs[4])['status'], 'SAFE')
        self.assertEqual(bfs(self.programs[4],cap=64,key_mode='retain-epoch')['status'], 'UNKNOWN')
    def test_budget_is_unknown_not_safe(self):
        self.assertEqual(bfs(self.programs[4],cap=1)['status'],'UNKNOWN')
    def test_bad_initial_state_is_empty_witness(self):
        p={'heap':[[0,0,-1]],'roots':[0],'start':0,'edges':[]}
        self.assertEqual(bfs(p)['trace'],[])
