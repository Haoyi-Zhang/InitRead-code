import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from java_trace_bridge import BLOCKING_FEATURES, map_observation


def observation(*, heap=None, roots=None, success=True, feature=None):
    features = {name: False for name in BLOCKING_FEATURES}
    if feature is not None:
        features[feature] = True
    value = {
        "case": "synthetic",
        "success": success,
        "features": features,
        "snapshot": {
            "heap": heap if heap is not None else [[1, 0, -1]],
            "roots": roots if roots is not None else [0],
            "ready_provenance": "owned_readObject_callback_exit",
        },
    }
    return value


class JavaTraceBridgeTests(unittest.TestCase):
    def test_maps_narrow_owned_snapshot(self):
        result = map_observation(observation(heap=[[1, 0, 1], [1, 1, -1]], roots=[0]))
        self.assertEqual(result.status, "MAPPED")
        self.assertEqual(result.heap, ((1, 0, 1), (1, 1, -1)))
        self.assertEqual(result.roots, frozenset({0}))
        self.assertIn("not constructor", result.ready_meaning)

    def test_root_types_checked_before_deduplication(self):
        for roots in ([0, False], [False, 0], [0, 0.0], [0.0, 0],
                      (0, False), (False, 0), (0, 0.0), (0.0, 0)):
            with self.subTest(roots=roots):
                self.assertEqual(map_observation(observation(roots=roots)).status, "UNKNOWN")
        self.assertEqual(map_observation(observation(roots=[0])).status, "MAPPED")
        self.assertEqual(map_observation(observation(roots=[0, 0])).roots, frozenset({0}))

    def test_special_callbacks_and_observation_gaps_are_unknown(self):
        for feature in BLOCKING_FEATURES:
            with self.subTest(feature=feature):
                result = map_observation(observation(feature=feature))
                self.assertEqual(result.status, "UNKNOWN")
                self.assertIn(feature, result.reason)

    def test_exception_is_unknown(self):
        self.assertEqual(map_observation(observation(success=False)).status, "UNKNOWN")

    def test_malformed_records_are_unknown(self):
        bad = [
            None,
            {},
            observation(heap=[[True, 0, -1]]),
            observation(heap=[[1, 2, -1]]),
            observation(heap=[[1, 0, 1]]),
            observation(roots=[]),
            observation(roots=[0] * 129),
        ]
        for item in bad:
            with self.subTest(item=item):
                self.assertEqual(map_observation(item).status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
