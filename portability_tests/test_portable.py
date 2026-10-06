"""Benign portability checks; temporary files only, no JVM or network."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import reproduce
import reproduce_receiver
import reproduce_specialization
import reproduce_portable
import runtime_resources


class PortableTests(unittest.TestCase):
    def test_unavailable_resource_is_null(self):
        with patch.object(runtime_resources, '_resource', None):
            self.assertIsNone(runtime_resources.self_peak_rss_kib())

    def test_windows_does_not_relabel_linux_rss(self):
        resource = Mock()
        with patch.object(runtime_resources, '_resource', resource), \
             patch.object(runtime_resources.sys, 'platform', 'win32'):
            self.assertIsNone(runtime_resources.self_peak_rss_kib())
        resource.getrusage.assert_not_called()

    def test_linux_returns_the_measured_kib(self):
        resource = Mock(); resource.getrusage.return_value.ru_maxrss = 123
        with patch.object(runtime_resources, '_resource', resource), \
             patch.object(runtime_resources.sys, 'platform', 'linux'):
            self.assertEqual(runtime_resources.self_peak_rss_kib(), 123)
        resource.getrusage.assert_called_once_with(resource.RUSAGE_SELF)

    def test_full_finite_is_not_silently_python_only(self):
        with tempfile.TemporaryDirectory(prefix='portable-guard-') as temp:
            out = Path(temp)/'full'
            with patch.object(reproduce, 'resource', None), self.assertRaises(SystemExit) as error:
                reproduce.main(['--out', str(out)])
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(out.exists())

    def test_full_jvm_drivers_keep_the_resource_requirement(self):
        for module in (reproduce_receiver, reproduce_specialization):
            with self.subTest(module=module.__name__), patch.object(module, 'resource', None):
                with self.assertRaisesRegex(RuntimeError, 'Full JVM campaign requires POSIX'):
                    module.main()

    def test_python_subset_compares_six_json_and_four_bytes(self):
        with tempfile.TemporaryDirectory(prefix='portable-comparison-') as temp:
            expected, actual = Path(temp)/'expected', Path(temp)/'actual'
            expected.mkdir(); actual.mkdir()
            for name in reproduce.SCIENTIFIC_JSON_FILES:
                reproduce_portable.write_json(expected/name, {'count':7,'cpu_seconds':1,'peak_rss_kib':100})
                if name != 'java-summary.json':
                    reproduce_portable.write_json(actual/name, {'count':7,'cpu_seconds':2,'peak_rss_kib':None})
            for name in reproduce.DETERMINISTIC_DATA_FILES:
                (expected/name).write_bytes(b'owned fixture\n')
                if name != 'java-observations.jsonl':
                    (actual/name).write_bytes(b'owned fixture\n')
            answer = reproduce.compare(expected, actual, python_only=True)
            self.assertEqual(answer['status'], 'MATCH')
            self.assertEqual((answer['scientific_total'], answer['deterministic_total']), (6,4))
            # A scientific field difference must not be excluded as telemetry.
            reproduce_portable.write_json(actual/'capacity.json', {'count':8})
            self.assertEqual(reproduce.compare(expected, actual, python_only=True)['status'], 'MISMATCH')

    def test_generated_jsonl_is_canonical_lf_utf8(self):
        with tempfile.TemporaryDirectory(prefix='portable-jsonl-') as temp:
            out = Path(temp)/'rows.jsonl'
            reproduce_portable.write_rows(out, [{'b':2,'a':1}])
            self.assertEqual(out.read_bytes(), b'{"a":1,"b":2}\n')
            self.assertEqual(json.loads(out.read_text(encoding='utf-8')), {'a':1,'b':2})

    def test_nonempty_output_is_never_reused(self):
        with tempfile.TemporaryDirectory(prefix='portable-fresh-') as temp:
            out = Path(temp)/'result'; out.mkdir()
            (out/'existing').write_bytes(b'preserved')
            with self.assertRaisesRegex(ValueError, 'must not exist or must be empty'):
                reproduce_portable.main(['--out', str(out)])
            self.assertEqual((out/'existing').read_bytes(), b'preserved')


if __name__ == '__main__':
    unittest.main()
