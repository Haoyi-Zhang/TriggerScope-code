"""Portable finite matching/index regressions, separate from retained results.

References enumerate cell allocations and bucket assignments, not an archived
matching implementation. No other test module, private path, timer or CLI is used.
"""
from copy import deepcopy
from itertools import product
import unittest

from src import producer
from src.baseline import exact_spectrum
from src.checker import InvalidCertificate, check
from src.oracle import enumerate_words


def matrices():
    """The two retained ternary shapes, with nonempty class columns."""
    for buckets, classes in ((2, 3), (3, 2)):
        for cells in product(range(3), repeat=buckets * classes):
            N = [list(cells[y * classes:(y + 1) * classes]) for y in range(buckets)]
            if all(any(row[c] for row in N) for c in range(classes)):
                yield N


def allocation_reference(N):
    """Enumerate every integer cell allocation, grouped by its row counts."""
    buckets, classes = len(N), len(N[0])
    result = {}
    for cells in product(*(range(cap + 1) for row in N for cap in row)):
        report = tuple(sum(cells[y * classes:(y + 1) * classes]) for y in range(buckets))
        omission = next((c for c in range(classes)
                         if not any(cells[y * classes + c] for y in range(buckets))), classes)
        result.setdefault(report, set()).add(omission)
    return result


def prefix_reference(N, n, limit):
    """Exhaust bucket choices for each prefix, with no augmenting-path logic."""
    longest = 0
    for length in range(1, limit + 1):
        feasible = any(
            all(N[y][c] for c, y in enumerate(choice))
            and all(choice.count(y) <= n[y] for y in range(len(N)))
            for choice in product(range(len(N)), repeat=length)
        )
        if not feasible:
            break
        longest = length
    return longest


def models():
    """Owned tiny sources cover every monitor, context, residue and epsilon."""
    for op, locked, modulus, horizon in product(
            ("ever", "last", "count", "before"), (False, True), (1, 2), (1, 2)):
        monitor = {"op": op, "guard": {"field": "kind", "equals": 0}}
        if op == "count":
            monitor["threshold"] = 2
        elif op == "before":
            monitor["then"] = {"field": "kind", "equals": 1}
        yield {
            "events": [{"kind": i, "value": i, "context": i, "bucket": i}
                       for i in (0, 1)],
            "monitors": [monitor, {"op": "ever", "guard": {"field": "context", "equals": 1}}],
            "triggers": [0, 1, ["or", 0, 1], ["not", 0]],
            "horizon": horizon, "min_length": 0, "environment_locked": locked,
            "report_modulus": modulus,
        }
    yield {"events": [{"kind": 0, "value": 0, "context": 0, "bucket": 0}],
           "monitors": [{"op": "ever", "guard": {"field": "kind", "equals": 0}}],
           "triggers": [["not", 0]], "horizon": 0, "min_length": 0,
           "environment_locked": False, "report_modulus": 1}
    yield {"events": [{"kind": i, "value": i % 2, "context": 0, "bucket": int(i >= 3)}
                      for i in range(6)],
           "monitors": [{"op": "ever", "guard": {"field": "kind", "equals": i}}
                        for i in range(3)],
           "triggers": [0, 1, 2], "horizon": 1, "min_length": 1,
           "environment_locked": False, "report_modulus": 1}


class MatchingIndexTests(unittest.TestCase):
    def assert_proof(self, N, n, proof, limit):
        p = proof["prefix"]
        self.assertEqual(p, prefix_reference(N, n, limit))
        pairs = proof["matching"]
        self.assertEqual(pairs, sorted(pairs))
        self.assertEqual([c for c, _ in pairs], list(range(p)))
        self.assertTrue(all(N[y][c] > 0 for c, y in pairs))
        self.assertTrue(all(sum(v == y for _, v in pairs) <= n[y] for y in range(len(N))))
        cut = proof["cut"]
        self.assertEqual(cut, sorted(set(cut)))
        if p == limit:
            self.assertEqual(cut, [])
        else:
            neighbors = {y for y, row in enumerate(N) if any(row[c] for c in cut)}
            self.assertTrue(cut and all(0 <= c <= p for c in cut))
            self.assertGreater(len(cut), sum(n[y] for y in neighbors))

    def test_complete_ternary_capacity_domains(self):
        matrices_checked = reports = allocations = 0
        for N in matrices():
            matrices_checked += 1
            for counts, outcomes in allocation_reference(N).items():
                n = list(counts)
                proof = producer.matching_prefix(N, n)
                self.assert_proof(N, n, proof, len(N[0]))
                self.assertEqual(producer.spectrum(N, n, proof["prefix"]), sorted(outcomes))
                self.assertEqual(exact_spectrum(N, n), sorted(outcomes))
                for outcome in sorted(outcomes):
                    X = producer.allocation_witness(N, n, outcome)
                    self.assertEqual(list(map(sum, X)), n)
                    self.assertTrue(all(type(v) is int and 0 <= v <= N[y][c]
                                        for y, row in enumerate(X) for c, v in enumerate(row)))
                    first = next((c for c in range(len(N[0])) if not any(row[c] for row in X)), len(N[0]))
                    self.assertEqual(first, outcome)
                    allocations += 1
                reports += 1
        self.assertEqual((matrices_checked, reports, allocations), (1188, 28836, 45944))

    def test_source_replay_and_direct_word_reference(self):
        for model in models():
            dag = producer.enumerate_model(model)
            words = enumerate_words(model)
            for key in ("classes", "representatives", "buckets", "capacity"):
                self.assertEqual(dag[key], words[key])
            N = dag["capacity"]
            for counts, outcomes in allocation_reference(N).items():
                n = list(counts)
                cert = producer.certify(model, n, dag)
                status = check(model, n, cert)
                self.assertEqual(status["spectrum"], sorted(outcomes))
                transitions = sum(len(L) * len(model["events"]) for L in dag["layers"][:-1])
                self.assertEqual(dag["producer_edge_checks"], transitions)
                self.assertEqual(status["checker_steps"], transitions + len(N) * len(N[0]))
                self.assertEqual(cert["witnesses"], sorted(cert["witnesses"], key=lambda w: w["outcome"]))

    def test_limits_and_allocation_errors(self):
        for N, n in (([[1, 1, 1], [0, 0, 0]], [2, 0]),
                     ([[1, 0], [1, 1]], [1, 1]), ([[0, 1]], [0])):
            for limit in range(len(N[0]) + 1):
                self.assert_proof(N, n, producer.matching_prefix(N, n, limit), limit)
        with self.assertRaisesRegex(ValueError, "^infeasible prefix$"):
            producer.allocation_witness([[1, 1, 1]], [1], 2)
        with self.assertRaisesRegex(ValueError, "^infeasible exclusion$"):
            producer.allocation_witness([[1, 1]], [2], 1)

    def test_index_is_local_and_inputs_are_not_mutated(self):
        N, n = [[1, 0], [1, 1]], [1, 1]
        original = deepcopy((N, n))
        proof = producer.matching_prefix(N, n)
        self.assertEqual(proof, {"prefix": 2, "matching": [[0, 0], [1, 1]], "cut": []})
        self.assertEqual((N, n), original)
        N[1][1] = 0
        self.assertEqual(producer.matching_prefix(N, n)["prefix"], 1)
        self.assertEqual(producer.matching_prefix(N, [0, 0])["prefix"], 0)

    def test_bucket_and_augmenting_path_order(self):
        N, n = [[1, 1, 0], [1, 0, 1]], [1, 1]
        self.assertEqual(producer.matching_prefix(N, n, 1),
                         {"prefix": 1, "matching": [[0, 0]], "cut": []})
        self.assertEqual(producer.matching_prefix(N, n),
                         {"prefix": 2, "matching": [[0, 1], [1, 0]], "cut": [0, 1, 2]})
        self.assertEqual(producer.allocation_witness(N, n, 2), [[0, 1, 0], [1, 0, 0]])

    def test_support_cells_are_indexed_once_per_search(self):
        class CountedRow(list):
            def __getitem__(self, column):
                reads[column] = reads.get(column, 0) + 1
                return super().__getitem__(column)

        reads = {}
        N = [CountedRow([1, 1, 0]), CountedRow([1, 0, 1])]
        producer.matching_prefix(N, [1, 1])
        self.assertEqual(reads, {0: 2, 1: 2, 2: 2})
        reads.clear()
        producer.matching_prefix(N, [1, 1], 0)
        self.assertEqual(reads, {})

    def test_report_binding_and_fail_closed_controls(self):
        model = next(models())
        dag = producer.enumerate_model(model)
        zero = [0] * len(dag["capacity"])
        cert = producer.certify(model, zero, dag)
        changed = zero.copy()
        changed[-1] = 1
        with self.assertRaisesRegex(InvalidCertificate, "^report binding$"):
            check(model, changed, cert)
        malformed = deepcopy(cert)
        malformed["prefix_proof"]["cut"] = []
        with self.assertRaises(InvalidCertificate):
            check(model, zero, malformed)
        for bad in ([True] * len(zero), [-1] * len(zero), [], [99] * len(zero)):
            with self.assertRaisesRegex(ValueError, "^inconsistent count report$"):
                producer.certify(model, bad, dag)
        oversized = deepcopy(model)
        oversized["horizon"] = 25
        with self.assertRaisesRegex(InvalidCertificate, "^horizon$"):
            check(oversized, zero, cert)


if __name__ == "__main__":
    unittest.main()
