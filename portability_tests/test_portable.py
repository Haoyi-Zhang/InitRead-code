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
from receiver.reference import decide


class PortableTests(unittest.TestCase):
    def test_owned_subprocesses_disable_bytecode_writes(self):
        self.assertEqual(reproduce.RUN_ENV_OVERRIDES['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(reproduce_receiver.RUN_ENV_OVERRIDES['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(reproduce_specialization.RUN_ENV_OVERRIDES['PYTHONDONTWRITEBYTECODE'], '1')

    def receiver_inputs(self, directory):
        words = [1380139825, 1, 2, 1, 0, 1, 1, -1, 0]
        old = {'id': 'cert-short-009', 'kind': 'certificate-control', 'words': words,
               'reference': {'status': 'INVALID_DATA', 'reason': 'dimensions'}}
        new = {**old, 'reference': decide(words)}
        before, after = Path(directory)/'before.jsonl', Path(directory)/'after.jsonl'
        reproduce_portable.write_rows(before, [old])
        reproduce_portable.write_rows(after, [new])
        return before, after, new

    def test_named_reference_correction_keeps_input_words_exact(self):
        with tempfile.TemporaryDirectory(prefix='prefix-label-') as temp:
            before, after, _ = self.receiver_inputs(temp)
            result = reproduce_receiver.compare_receiver_inputs(after, before)
            self.assertFalse(result['byte_equal'])
            self.assertTrue(result['match'])
            self.assertTrue(result['data_words_equal'])
            self.assertEqual(result['reference_corrections'], ['cert-short-009'])

    def test_reference_correction_does_not_hide_other_changes(self):
        with tempfile.TemporaryDirectory(prefix='prefix-label-guard-') as temp:
            before, after, new = self.receiver_inputs(temp)
            for changed in ({**new, 'words': new['words'][:-1] + [1]},
                            {**new, 'words': new['words'][:4] + [False] + new['words'][5:]},
                            {**new, 'id': 'other-case'},
                            {**new, 'reference': {'status': 'ALLOW'}}):
                reproduce_portable.write_rows(after, [changed])
                self.assertFalse(reproduce_receiver.compare_receiver_inputs(after, before)['match'])

    def test_named_correction_rejects_equal_bool_and_float_references(self):
        with tempfile.TemporaryDirectory(prefix='prefix-reference-types-') as temp:
            before, after, new = self.receiver_inputs(temp)
            for field, value in (('values', False), ('reachable', 0.0),
                                 ('links', 1.0), ('roots', False)):
                with self.subTest(field=field, value=value):
                    changed = json.loads(json.dumps(new))
                    changed['reference'][field][0] = value
                    reproduce_portable.write_rows(after, [changed])
                    self.assertFalse(reproduce_receiver.compare_receiver_inputs(after, before)['match'])

    def test_unchanged_reference_shortcut_keeps_exact_scalar_types(self):
        with tempfile.TemporaryDirectory(prefix='unchanged-reference-types-') as temp:
            before, after, new = self.receiver_inputs(temp)
            reproduce_portable.write_rows(before, [new])
            self.assertTrue(reproduce_receiver.compare_receiver_inputs(after, before)['match'])
            for field, value in (('values', False), ('reachable', 0.0),
                                 ('links', 1.0), ('roots', False)):
                with self.subTest(field=field, value=value):
                    changed = json.loads(json.dumps(new))
                    changed['reference'][field][0] = value
                    reproduce_portable.write_rows(after, [changed])
                    self.assertFalse(reproduce_receiver.compare_receiver_inputs(after, before)['match'])

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
