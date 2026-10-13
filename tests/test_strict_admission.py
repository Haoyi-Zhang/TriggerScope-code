"""Owned decoded-JSON and normalized-session admission regressions, offline.

No application, device, upstream execution, or offensive input is involved.
The CLI records every tested encoding; it is not a larger workload benchmark.
"""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import unittest

from src.androlog_adapter import InvalidLog, adapt_sessions
from src.checker import InvalidCertificate, check
from src.oracle import evaluate
from src.producer import certify


def owned_model():
    return {'events': [dict(kind=i, value=i, context=0, bucket=i) for i in (0, 1)],
            'monitors': [dict(op='last', guard=dict(field='value', equals=1))],
            'triggers': [0], 'horizon': 1, 'min_length': 1,
            'environment_locked': False, 'report_modulus': 1}


def leaves(value, path=()):
    if type(value) is int:
        yield path, value
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from leaves(child, path + (index,))


def replaced(certificate, path, value):
    changed = deepcopy(certificate)
    parent = changed
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    # These are ordinary decoded JSON scalars, not Python subclasses.
    return json.loads(json.dumps(changed))


def certificate_observations(model, counts, certificate):
    records = []
    for field in ('classes', 'representatives', 'buckets', 'capacity'):
        for path, original in leaves(certificate['semantics'][field]):
            alternatives = [float(original)] + ([bool(original)] if original in (0, 1) else [])
            for value in alternatives:
                full_path = ('semantics', field) + path
                malformed = replaced(certificate, full_path, value)
                record = dict(path=list(full_path), original=original,
                              replacement=value, replacement_type=type(value).__name__)
                try:
                    result = check(model, counts, malformed)
                    record.update(accepted=True, spectrum=result['spectrum'])
                except (InvalidCertificate, TypeError, IndexError) as error:
                    record.update(accepted=False, exception_type=type(error).__name__, reason=str(error))
                records.append(record)
    for index, original in enumerate(certificate['spectrum']):
        alternatives = [float(original)] + ([bool(original)] if original in (0, 1) else [])
        for value in alternatives:
            malformed = replaced(certificate, ('spectrum', index), value)
            record = dict(path=['spectrum', index], original=original,
                          replacement=value, replacement_type=type(value).__name__)
            try:
                result = check(model, counts, malformed)
                record.update(accepted=True, spectrum=result['spectrum'])
            except (InvalidCertificate, TypeError, IndexError) as error:
                record.update(accepted=False, exception_type=type(error).__name__, reason=str(error))
            records.append(record)
    return records


def session_observations(model):
    records = []
    for index in (0, 1):
        for value in (bool(index), float(index)):
            for good_first in (True, False):
                sessions = [[index], [value]] if good_first else [[value], [index]]
                record = dict(sessions=sessions, replacement_type=type(value).__name__, good_first=good_first)
                try:
                    result = adapt_sessions(model, sessions)
                    record.update(accepted=True, distinct_words=result['distinct_words'],
                                  count_report=result['count_report'])
                except (InvalidLog, TypeError, ValueError) as error:
                    record.update(accepted=False, exception_type=type(error).__name__, reason=str(error))
                records.append(record)
    return records


def observation():
    model = owned_model()
    counts = [0, 0]
    certificate = certify(model, counts)
    checked = check(model, counts, certificate)
    certificate_rows = certificate_observations(model, counts, certificate)
    session_rows = session_observations(model)
    shape_rows = []
    for malformed_layer in (None, 0, False, 0.0, 'not-a-layer'):
        malformed = deepcopy(certificate)
        malformed['semantics']['layers'][1] = malformed_layer
        record = dict(layer=malformed_layer, layer_type=type(malformed_layer).__name__)
        try:
            check(model, counts, malformed)
            record.update(accepted=True)
        except (InvalidCertificate, TypeError, IndexError) as error:
            record.update(accepted=False, exception_type=type(error).__name__, reason=str(error))
        shape_rows.append(record)
    valid_sessions = [[0], [0], [1]]
    valid = adapt_sessions(model, valid_sessions)
    return dict(scope='owned schema/session admission; no Android execution or performance claim',
                model=model, count_report=counts, valid_certificate=certificate,
                valid_checker_result=checked, certificate_substitutions=certificate_rows,
                session_alias_cases=session_rows, malformed_layer_cases=shape_rows,
                valid_duplicate_control=dict(sessions=valid_sessions, adapted_report=valid),
                summary=dict(certificate_cases=len(certificate_rows),
                             certificate_invalid_accepted=sum(row['accepted'] for row in certificate_rows),
                             session_cases=len(session_rows),
                             session_invalid_accepted=sum(row['accepted'] for row in session_rows),
                             malformed_layers=len(shape_rows),
                             malformed_layer_unexpected_exceptions=sum(
                                 row.get('exception_type') != 'InvalidCertificate' for row in shape_rows)))


class StrictAdmissionTests(unittest.TestCase):
    def test_reconstructed_json_integer_leaves(self):
        model = owned_model()
        counts = [0, 0]
        certificate = certify(model, counts)
        for row in certificate_observations(model, counts, certificate):
            with self.subTest(path=row['path'], scalar_type=row['replacement_type']):
                self.assertFalse(row['accepted'])
                self.assertEqual(row['exception_type'], 'InvalidCertificate')

    def test_spectrum_one_is_not_boolean_true_or_real(self):
        model = owned_model()
        counts = [1, 0]
        certificate = certify(model, counts)
        self.assertEqual(certificate['spectrum'], [1])
        for value in (True, 1.0):
            with self.subTest(value=value), self.assertRaises(InvalidCertificate):
                check(model, counts, replaced(certificate, ('spectrum', 0), value))

    def test_every_session_is_validated_before_deduplication(self):
        for row in session_observations(owned_model()):
            with self.subTest(sessions=row['sessions'], scalar_type=row['replacement_type']):
                self.assertFalse(row['accepted'])
                self.assertEqual(row['exception_type'], 'InvalidLog')

    def test_malformed_layer_containers_raise_declared_exception(self):
        for row in observation()['malformed_layer_cases']:
            with self.subTest(layer=row['layer']):
                self.assertFalse(row['accepted'])
                self.assertEqual(row['exception_type'], 'InvalidCertificate')

    def test_valid_complete_trace_duplicates_and_within_trace_repetition(self):
        model = owned_model()
        result = adapt_sessions(model, [[0], [0], [1]])
        self.assertEqual(result['distinct_words'], [[0], [1]])
        self.assertEqual(result['count_report'], [1, 1])
        self.assertEqual(result['duplicate_sessions_removed'], 1)
        temporal = deepcopy(model)
        temporal.update(horizon=2, min_length=0,
            monitors=[dict(op='count', threshold=2, guard=dict(field='kind', equals=0)),
                      dict(op='before', guard=dict(field='kind', equals=0),
                           then=dict(field='kind', equals=0))], triggers=[0, 1])
        sessions = [[], [0], [0, 0], [0, 0], [1, 0]]
        adapted = adapt_sessions(temporal, sessions)
        self.assertEqual(adapted['distinct_traces'], 4)
        self.assertEqual(adapted['duplicate_sessions_removed'], 1)
        self.assertEqual(evaluate(temporal, (0,)), (0, 0))
        self.assertEqual(evaluate(temporal, (0, 0)), (1, 1))
        expected = {}
        for word in {tuple(s) for s in sessions}:
            signature = evaluate(temporal, word)
            bucket = (temporal['events'][word[-1]]['bucket'] if word else -1, 0)
            expected[bucket, signature] = expected.get((bucket, signature), 0) + 1
        for y, bucket in enumerate(adapted['buckets']):
            for c, signature in enumerate(adapted['classes']):
                self.assertEqual(adapted['allocation'][y][c], expected.get((tuple(bucket), tuple(signature)), 0))

    def test_session_shape_and_model_legality_are_explicit_errors(self):
        for sessions in (None, '0', [None], [0], [[[]]], [[-1]], [[2]], [[0, 1]]):
            with self.subTest(sessions=sessions), self.assertRaises(InvalidLog):
                adapt_sessions(owned_model(), sessions)
        self.assertEqual(adapt_sessions(owned_model(), [(0,), (0,), (1,)])['count_report'], [1, 1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-rejection', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('use a new output file')
    report = observation()
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps(report['summary'], indent=2, sort_keys=True))
    bad = report['summary']
    return int(args.require_rejection and any(bad[k] for k in (
        'certificate_invalid_accepted', 'session_invalid_accepted', 'malformed_layer_unexpected_exceptions')))


if __name__ == '__main__':
    raise SystemExit(main())
