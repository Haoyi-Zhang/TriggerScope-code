"""Exact-count reports over overlapping views and the X3C boundary.

The omission-spectrum checker deliberately accepts only a partition of the
trace universe.  This module is not part of that checker.  It provides a small,
independent executable witness for the complexity boundary used in the paper:
with arbitrary overlapping exact-count views, even report consistency is the
0-1 feasibility problem underlying Exact Cover by 3-Sets (X3C).
"""
from __future__ import annotations

from itertools import combinations, product
from typing import Iterable, Sequence


def normalize_x3c(
    elements: Sequence[int], triples: Sequence[Sequence[int]]
) -> tuple[tuple[int, ...], tuple[tuple[int, int, int], ...]]:
    """Validate and canonicalize a finite X3C instance.

    Elements must be distinct and their number a multiple of three.  Each set
    must contain exactly three distinct declared elements.  Duplicate triples
    are rejected because the reduction uses one token per declared set.
    """
    raw_universe = tuple(elements)
    if len(raw_universe) == 0 or len(raw_universe) % 3:
        raise ValueError("X3C ground-set size must be a positive multiple of three")
    if any(type(element) is not int for element in raw_universe):
        raise ValueError("ground elements must be integers")
    if len(set(raw_universe)) != len(raw_universe):
        raise ValueError("duplicate ground element")
    universe = tuple(sorted(raw_universe))
    allowed = set(universe)
    normalized: list[tuple[int, int, int]] = []
    for raw in triples:
        if len(raw) != 3 or len(set(raw)) != 3 or not set(raw) <= allowed:
            raise ValueError("each declared set must contain three distinct ground elements")
        normalized.append(tuple(sorted(raw)))
    if len(set(normalized)) != len(normalized):
        raise ValueError("duplicate triple")
    return universe, tuple(sorted(normalized))


def x3c_exact_covers(
    elements: Sequence[int], triples: Sequence[Sequence[int]]
) -> list[tuple[int, ...]]:
    """Direct X3C oracle: indices of every exact-cover subfamily."""
    universe, sets = normalize_x3c(elements, triples)
    q = len(universe) // 3
    target = set(universe)
    covers: list[tuple[int, ...]] = []
    for chosen in combinations(range(len(sets)), q):
        union: set[int] = set()
        disjoint = True
        for i in chosen:
            if union.intersection(sets[i]):
                disjoint = False
                break
            union.update(sets[i])
        if disjoint and union == target:
            covers.append(chosen)
    return covers


def x3c_to_overlapping_report(
    elements: Sequence[int], triples: Sequence[Sequence[int]]
) -> dict:
    """Map X3C to exact counts over overlapping views.

    One selectable token is created per triple. Elements and tokens are stored
    in canonical sorted order; explicit input/canonical permutations preserve
    how any unordered input was reindexed. For every ground element e, the
    corresponding view contains exactly the tokens whose triples contain e,
    and its reported count is one. A token is therefore in exactly three views.
    A compatible selection is precisely an exact cover.
    """
    raw_tokens = tuple(tuple(raw) for raw in triples)
    universe, sets = normalize_x3c(elements, raw_tokens)
    canonical_index = {token: index for index, token in enumerate(sets)}
    input_to_canonical = [canonical_index[tuple(sorted(token))] for token in raw_tokens]
    canonical_to_input = [0] * len(sets)
    for input_index, canonical_index_value in enumerate(input_to_canonical):
        canonical_to_input[canonical_index_value] = input_index
    views = [[i for i, triple in enumerate(sets) if element in triple]
             for element in universe]
    return {
        "elements": list(universe),
        "tokens": [list(triple) for triple in sets],
        "input_to_canonical": input_to_canonical,
        "canonical_to_input": canonical_to_input,
        "views": views,
        "counts": [1] * len(universe),
    }


def compatible_selections(views: Sequence[Sequence[int]], counts: Sequence[int], token_count: int) -> list[tuple[int, ...]]:
    """Brute-force exact-count view oracle, independent of X3C logic."""
    if token_count < 0 or len(views) != len(counts):
        raise ValueError("shape")
    canonical_views: list[tuple[int, ...]] = []
    for view, count in zip(views, counts):
        v = tuple(view)
        if len(set(v)) != len(v) or any(type(i) is not int or not 0 <= i < token_count for i in v):
            raise ValueError("view")
        if type(count) is not int or not 0 <= count <= len(v):
            raise ValueError("count")
        canonical_views.append(v)
    out: list[tuple[int, ...]] = []
    for bits in product((0, 1), repeat=token_count):
        if all(sum(bits[i] for i in view) == count
               for view, count in zip(canonical_views, counts)):
            out.append(tuple(i for i, bit in enumerate(bits) if bit))
    return sorted(out)


def reduction_agrees(elements: Sequence[int], triples: Sequence[Sequence[int]]) -> bool:
    report = x3c_to_overlapping_report(elements, triples)
    by_views = compatible_selections(report["views"], report["counts"], len(report["tokens"]))
    by_x3c = x3c_exact_covers(elements, triples)
    return by_views == by_x3c


def enumerate_six_element_families(max_family_size: int = 4) -> Iterable[tuple[tuple[int, int, int], ...]]:
    """All subfamilies of the twenty 3-sets on six elements up to a size bound."""
    if not 0 <= max_family_size <= 20:
        raise ValueError("family-size bound")
    all_triples = tuple(combinations(range(6), 3))
    for size in range(max_family_size + 1):
        yield from combinations(all_triples, size)
