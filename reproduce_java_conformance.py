"""Current-only, standard-library, finite owned-case Java conformance replay.

No timing mode, download, external serialization input or before-copy lookup.
All generated classes, serialized inputs, references and receipts stay in --out.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VM = ['-XX:ActiveProcessorCount=1', '-XX:+UseSerialGC', '-Xmx256m']
SOURCES = ['java/CertifiedReceiver.java', 'baselines/GenericReceiver.java',
           'java/ReceiverHarness.java', 'java/SpecializationHarness.java',
           'java/CapacityObservationHarness.java']


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def rows(path, keys=('id',)):
    result = {}
    with path.open(encoding='utf-8') as source:
        for line in source:
            value = json.loads(line)
            key = tuple(value[k] for k in keys)
            if key in result:
                raise ValueError('duplicate result key: ' + repr(key))
            result[key] = value
    return result


def packets(path, expected_count, expected_digest):
    if digest(path) != expected_digest:
        raise ValueError('included case-table binding changed: ' + str(path))
    result = {}
    with path.open(encoding='utf-8') as source:
        for line in source:
            ident, kind, text = line.rstrip('\r\n').split('\t')
            words = [int(cell) for cell in text.split(',')]
            if not re.fullmatch('[a-zA-Z0-9_-]+', ident) or ident in result:
                raise ValueError('owned case identity')
            if not 5 <= len(words) <= 24576 or any(not -(1 << 31) <= w < (1 << 31) for w in words):
                raise ValueError('owned integer bounds')
            result[ident] = (kind, words)
    if len(result) != expected_count:
        raise ValueError('owned case count')
    return result


def tools(home):
    home = home or os.environ.get('JAVA_HOME')
    suffix = '.exe' if os.name == 'nt' else ''
    if home:
        found = [Path(home).expanduser().resolve() / 'bin' / (name + suffix)
                 for name in ('java', 'javac')]
    else:
        found = [Path(shutil.which(name) or '') for name in ('java', 'javac')]
    if not all(p.is_file() for p in found):
        raise ValueError('JDK 17+ required: use --java-home, JAVA_HOME, or java/javac on PATH')
    return [str(p.resolve()) for p in found]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', help='Local JDK 17+ directory (otherwise JAVA_HOME or PATH)')
    parser.add_argument('--out', required=True, type=Path, help='New output directory outside the artifact')
    args = parser.parse_args()
    out = args.out.expanduser().resolve()
    if out == ROOT or ROOT in out.parents or out in ROOT.parents or out.exists():
        parser.error('--out must be a new directory outside, and not containing, this artifact')
    java, javac = tools(args.java_home)
    contract = json.loads((ROOT / 'java-conformance-contract.json').read_text(encoding='utf-8'))
    receiver_path = ROOT / 'results/current/receiver/cases.tsv'
    integer_path = ROOT / 'results/current/specialization/cases.tsv'
    receiver_inputs = packets(receiver_path, contract['receiver_cases'], contract['receiver_cases_sha256'])
    integer_inputs = packets(integer_path, contract['integer_cases'], contract['integer_cases_sha256'])
    out.mkdir(parents=True)
    (out / 'classes').mkdir()
    (out / 'streams').mkdir()
    commands = []
    env = dict(os.environ)
    for name in ('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'CLASSPATH'):
        env.pop(name, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    summary = {'scope': contract['scope'], 'started_utc': stamp(), 'status': 'RUNNING',
               'benchmark_runs': 0, 'commands': commands}

    def run(label, command, timeout):
        record = {'label': label, 'argv': command, 'cwd': str(ROOT),
                  'timeout_seconds': timeout, 'started_utc': stamp()}
        commands.append(record)
        save(out / 'commands.json', commands)
        with (out / (label + '.stdout.txt')).open('wb') as stdout, (out / (label + '.stderr.txt')).open('wb') as stderr:
            try:
                child = subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                                       timeout=timeout, check=False)
                record['exit_code'] = child.returncode
            except subprocess.TimeoutExpired:
                record['timed_out'] = True
                raise
            finally:
                record['ended_utc'] = stamp()
                save(out / 'commands.json', commands)
        if child.returncode:
            raise RuntimeError(label + ' exited ' + str(child.returncode))

    try:
        bindings = SOURCES + ['reproduce_java_conformance.py', 'java-conformance-contract.json',
                              'receiver/reference.py', 'receiver/certificate_reference.py',
                              'results/current/receiver/cases.tsv', 'results/current/receiver/java-results.jsonl',
                              'results/current/specialization/cases.tsv', 'results/current/specialization/comparison.jsonl']
        save(out / 'environment.json', {'python': sys.version, 'platform': sys.platform,
             'java': java, 'javac': javac, 'jvm_options': VM,
             'bindings_sha256': {p: digest(ROOT / p) for p in bindings},
             'injected_java_environment_cleared': True})
        run('java-version', [java, '-version'], 20)
        run('javac-version', [javac, '-version'], 20)
        run('python-receiver-tests', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'receiver_tests', '-v'], 60)
        run('compile', [javac] + ['-J' + option for option in VM] +
            ['-proc:none', '--release', '17', '-encoding', 'UTF-8', '-d', str(out / 'classes')] +
            [str(ROOT / p) for p in SOURCES], 60)
        prefix = [java] + VM + ['-cp', str(out / 'classes')]
        run('receiver', prefix + ['ReceiverHarness', str(receiver_path), str(out / 'streams')], 180)
        run('integer', prefix + ['SpecializationHarness', str(integer_path)], 180)
        run('full-observations', prefix + ['CapacityObservationHarness', str(integer_path)], 180)

        actual = rows(out / 'receiver.stdout.txt')
        retained = rows(ROOT / 'results/current/receiver/java-results.jsonl')
        if actual != retained or len(actual) != contract['receiver_observations']:
            raise AssertionError('receiver full retained observations differ')
        integers = rows(out / 'integer.stdout.txt')
        if integers != rows(ROOT / 'results/current/specialization/comparison.jsonl') or len(integers) != len(integer_inputs):
            raise AssertionError('integer retained observations differ')
        full = rows(out / 'full-observations.stdout.txt', ('id', 'mode'))
        if len(full) != contract['full_observations']:
            raise AssertionError('six-mode observation count')
        h = hashlib.sha256()
        with (out / 'full-observations.stdout.txt').open(encoding='utf-8') as source:
            for line in source:
                h.update((json.dumps(json.loads(line), sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii'))
        if h.hexdigest() != contract['full_observations_canonical_sha256']:
            raise AssertionError('full retained-observation fingerprint differs')

        old_streams = ROOT / 'results/receiver-campaign/streams'
        current_set = {p.name for p in (out / 'streams').iterdir() if p.is_file()}
        retained_set = {p.name for p in old_streams.iterdir() if p.is_file()}
        if current_set != retained_set or len(current_set) != contract['receiver_observations']:
            raise AssertionError('serialized input set differs')
        with (out / 'stream-comparison.jsonl').open('w', encoding='utf-8') as receipt:
            for name in sorted(current_set):
                current, old = out / 'streams' / name, old_streams / name
                equal = current.read_bytes() == old.read_bytes()
                receipt.write(json.dumps({'file': name, 'equal': equal, 'sha256': digest(current)}) + '\n')
                if not equal:
                    raise AssertionError('serialized input differs: ' + name)

        # These references import no receiver/producer/Java code. Recompute now,
        # rather than trusting the stored inputs.jsonl reference labels.
        from receiver.certificate_reference import classify
        from receiver.reference import decide
        dense_checked = 0
        with (out / 'python-reference.jsonl').open('w', encoding='utf-8') as receipt:
            for ident, (kind, words) in integer_inputs.items():
                certificate, data = classify(words), decide(words)
                receipt.write(json.dumps({'id': ident, 'certificate': certificate, 'data': data}, sort_keys=True) + '\n')
                if integers[(ident,)]['specialized'] != certificate or integers[(ident,)]['generic'] != certificate:
                    raise AssertionError('fresh certificate reference: ' + ident)
                for a, b in ((0, 1), (2, 3), (4, 5)):
                    left, right = dict(full[(ident, a)]), dict(full[(ident, b)])
                    left.pop('mode'); right.pop('mode')
                    if left != right or not left['frozen_alias_ok']:
                        raise AssertionError('matched full observations/freeze: ' + ident)
                if data['status'] in ('ALLOW', 'DENY_UNSAFE'):
                    dense_checked += 1
                    if full[(ident, 2)]['status'] != data['status'] or full[(ident, 4)]['status'] != 'ALLOW':
                        raise AssertionError('fresh final-data policy: ' + ident)
                    heap = [[1, value, link] for value, link in zip(data['values'], data['links'])]
                    for mode in range(6):
                        observed = full[(ident, mode)]
                        if observed['status'] == 'ALLOW' and (observed['heap'] != heap or observed['roots'] != data['roots']):
                            raise AssertionError('independent representation: ' + ident)
                for mode in range(6):
                    observed = full[(ident, mode)]
                    if observed['status'] != 'ALLOW' and (observed['heap'] is not None or observed['roots'] is not None):
                        raise AssertionError('rejection publication: ' + ident)
        for (ident,), observed in actual.items():
            if not observed['frozen_alias_ok'] or observed['callback_count'] != 0 or observed['has_graph'] != (observed['status'] == 'ALLOW'):
                raise AssertionError('receiver publication/callback/freeze: ' + ident)
            if ident in receiver_inputs and observed['status'] != classify(receiver_inputs[ident][1]):
                raise AssertionError('fresh receiver reference: ' + ident)
        summary.update(status='PASS', receiver_observations=len(actual), integer_cases=len(integers),
                       full_observations=len(full), serialized_byte_equalities=len(current_set),
                       fresh_certificate_reference_cases=len(integer_inputs),
                       fresh_receiver_reference_cases=len(receiver_inputs),
                       fresh_dense_data_reference_cases=dense_checked,
                       full_observations_canonical_sha256=h.hexdigest(),
                       limits='Finite included cases only; Python references do not model Java stream decoding; dense representation comparison only for reference-valid complete data; no performance or universal correctness claim')
    except Exception as error:
        summary.update(status='FAIL', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        summary['ended_utc'] = stamp()
        save(out / 'summary.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'commands'}, sort_keys=True))


if __name__ == '__main__':
    main()
