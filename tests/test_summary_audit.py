"""Portable owned audit-routing checks; no devices, targets or hidden allocations."""
from itertools import product
import unittest

from src.oracle import capacity_outcomes
from src.summary_audit import audit_decision, cardinality_spectrum, matching_spectrum


class SummaryAuditTests(unittest.TestCase):
    def test_binary_ternary_cells_against_labelled_subsets(self):
        matrices = reports = 0
        for cells in product(range(3), repeat=4):
            N = [list(cells[:2]), list(cells[2:])]
            if not all(any(row[c] for row in N) for c in range(2)):
                continue
            matrices += 1
            for report, truth in capacity_outcomes(N).items():
                exact = sorted(truth)
                self.assertEqual(matching_spectrum(N, list(report)), exact)
                self.assertTrue(truth <= set(cardinality_spectrum(N, list(report))))
                for bits in product((False, True), repeat=2):
                    available = [c for c, bit in enumerate(bits) if bit]
                    decision = audit_decision(2, exact, available)
                    branches = sorted(truth - {2})
                    unsupported = [c for c in branches if c not in available]
                    ready = [c for c in branches if c in available]
                    self.assertEqual(decision["first_omission_branches"], branches)
                    self.assertEqual(decision["unsupported_branches"], unsupported)
                    self.assertEqual(decision["catalogue_sufficient"], not unsupported)
                    self.assertEqual(decision["next_test_candidate"], ready[0] if ready else None)
                reports += 1
        self.assertEqual(matrices, 64)
        self.assertEqual(reports, 658)

    def test_hall_and_noncontiguous_controls(self):
        hall, n = [[1, 1, 1, 0], [0, 0, 0, 3]], [2, 2]
        self.assertEqual(matching_spectrum(hall, n), [0, 1, 2])
        self.assertEqual(cardinality_spectrum(hall, n), [0, 1, 2, 4])
        # Count-only relaxation can add a finite branch, not merely COMPLETE.
        hall_frontier, n = [[1, 1, 0, 0], [0, 0, 1, 1]], [1, 1]
        self.assertEqual(matching_spectrum(hall_frontier, n), [0, 1])
        self.assertEqual(cardinality_spectrum(hall_frontier, n), [0, 1, 2])
        holes, n = [[1, 0, 1], [0, 1, 0], [0, 0, 1]], [1, 1, 1]
        self.assertEqual(matching_spectrum(holes, n), [0, 3])
        self.assertEqual(audit_decision(3, [0, 3], [0])["first_omission_branches"], [0])

    def test_status_does_not_determine_next_candidate(self):
        N = [[1, 1], [1, 1]]
        first = matching_spectrum(N, [0, 0])
        second = matching_spectrum([[1, 0], [0, 1]], [1, 0])
        self.assertEqual(first, [0])
        self.assertEqual(second, [1])
        self.assertNotIn(2, first)
        self.assertNotIn(2, second)  # Both forced-incomplete, different routing.
        self.assertEqual(audit_decision(2, first, [0, 1])["next_test_candidate"], 0)
        self.assertEqual(audit_decision(2, second, [0, 1])["next_test_candidate"], 1)

    def test_reject_invalid_contracts(self):
        for N, n in (([], []), ([[0]], [0]), ([[1]], [True]), ([[1]], [2]),
                     ([[1], [1, 2]], [0, 0]), ([[True]], [0]), ([[1]], [-1])):
            with self.assertRaises(ValueError):
                matching_spectrum(N, n)
            with self.assertRaises(ValueError):
                cardinality_spectrum(N, n)
        for outcomes, available in (([], []), ([1, 0], []), ([0, 0], []),
                                    ([True], []), ([0], [2]), ([0], [0, 0])):
            with self.assertRaises(ValueError):
                audit_decision(2, outcomes, available)


if __name__ == "__main__":
    unittest.main()
