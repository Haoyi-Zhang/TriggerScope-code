"""Totality regressions outside the frozen 4,090-family overlap campaign."""
from __future__ import annotations

import unittest

from src.overlap_boundary import (
    compatible_selections,
    enumerate_six_element_families,
    reduction_agrees,
    x3c_exact_covers,
    x3c_to_overlapping_report,
)


class OverlapTotalityTests(unittest.TestCase):
    def test_uncovered_ground_elements(self):
        triples = [(0, 1, 2)]
        report = x3c_to_overlapping_report(range(6), triples)
        self.assertEqual(x3c_exact_covers(range(6), triples), [])
        self.assertEqual(compatible_selections(report["views"], report["counts"], 1), [])
        self.assertTrue(reduction_agrees(range(6), triples))

    def test_empty_x3c_family(self):
        self.assertEqual(x3c_exact_covers(range(6), []), [])
        self.assertTrue(reduction_agrees(range(6), []))

    def test_feasible_and_locally_admissible_infeasible_controls(self):
        feasible = [(0, 1, 2), (3, 4, 5)]
        infeasible = [(0, 1, 2), (0, 3, 4), (1, 3, 5)]
        self.assertEqual(x3c_exact_covers(range(6), feasible), [(0, 1)])
        self.assertEqual(x3c_exact_covers(range(6), infeasible), [])
        self.assertTrue(reduction_agrees(range(6), feasible))
        self.assertTrue(reduction_agrees(range(6), infeasible))

    def test_zero_count_empty_view(self):
        self.assertEqual(compatible_selections([[]], [0], 0), [()])
        self.assertEqual(compatible_selections([[]], [0], 1), [(), (0,)])

    def test_count_above_view_capacity_is_infeasible(self):
        self.assertEqual(compatible_selections([[]], [1], 0), [])
        self.assertEqual(compatible_selections([[0]], [2], 1), [])

    def test_invalid_counts_are_rejected(self):
        for count in (-1, True, 1.0, "1"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                compatible_selections([[0]], [count], 1)

    def test_invalid_views_are_rejected(self):
        for view in ([0, 0], [-1], [1], [True], [0.0]):
            with self.subTest(view=view), self.assertRaises(ValueError):
                compatible_selections([view], [0], 1)

    def test_invalid_shapes_are_rejected(self):
        for token_count in (-1, True, 1.0, "1"):
            with self.subTest(token_count=token_count), self.assertRaises(ValueError):
                compatible_selections([], [], token_count)
        with self.assertRaises(ValueError):
            compatible_selections([[]], [], 0)

    def test_infeasibility_does_not_mask_later_malformed_rows(self):
        with self.assertRaises(ValueError):
            compatible_selections([[], [1]], [1, 0], 1)
        with self.assertRaises(ValueError):
            compatible_selections([[], [0]], [1, -1], 1)

    def test_uncovered_family_complement_separately(self):
        # The original campaign retains only the 4,090 families whose union is
        # all six elements. This regression covers its 2,106-family complement;
        # it does not change that campaign's denominator or saved records.
        checked = 0
        for triples in enumerate_six_element_families(4):
            if set().union(*(set(triple) for triple in triples)) == set(range(6)):
                continue
            report = x3c_to_overlapping_report(range(6), triples)
            with self.subTest(triples=triples):
                self.assertEqual(x3c_exact_covers(range(6), triples), [])
                self.assertEqual(
                    compatible_selections(report["views"], report["counts"], len(triples)),
                    [],
                )
                self.assertTrue(reduction_agrees(range(6), triples))
            checked += 1
        self.assertEqual(checked, 2106)


if __name__ == "__main__":
    unittest.main()
