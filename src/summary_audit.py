"""Summary-only diagnostic routing and two same-information references.

Inputs contain ordered cell capacities and exact distinct-trace bucket counts,
never the hidden selected allocation. A diagnostic candidate is a possible first
omission, not an observed omission or a promise that one extra test closes coverage.
"""
from collections import deque


def validate_summary(N, n):
    if (type(N) is not list or not N or type(N[0]) is not list or not N[0]
            or type(n) is not list or len(n) != len(N)):
        raise ValueError("summary shape")
    k = len(N[0])
    for row, count in zip(N, n):
        if (type(row) is not list or len(row) != k
                or any(type(v) is not int or v < 0 for v in row)):
            raise ValueError("capacity row")
        if type(count) is not int or not 0 <= count <= sum(row):
            raise ValueError("distinct-trace count")
    if any(not any(row[c] for row in N) for c in range(k)):
        raise ValueError("empty semantic class")
    return k


def cardinality_spectrum(N, n):
    """Relax simultaneous prefix support to its total-count necessary condition.

Retain exact individual avoidance using the same N,n as the exact methods.
This is an outcome superset, not an exact solver or a universal-coverage proxy.
"""
    k = validate_summary(N, n)
    q = min(k, sum(n))
    totals = list(map(sum, N))
    return [c for c in range(k) if c <= q
            and all(n[y] <= totals[y] - N[y][c] for y in range(len(N)))] + ([k] if q == k else [])


def _prefix_feasible(N, n, length):
    """Fresh unit-demand maximum flow for one prefix; no producer calls/cache.

Vertices are source, required classes, buckets, sink. Every support edge has
unit capacity, and each bucket has capacity min(n_y, length). Integer residual
augmentation tests whether all required classes can be reserved simultaneously.
"""
    b = len(N)
    source, sink = 0, 1 + length + b
    residual = [{} for _ in range(sink + 1)]

    def edge(u, v, cap):
        residual[u][v] = cap
        residual[v][u] = 0

    for c in range(length):
        edge(source, 1 + c, 1)
        for y in range(b):
            if N[y][c] > 0:
                edge(1 + c, 1 + length + y, 1)
    for y in range(b):
        edge(1 + length + y, sink, min(n[y], length))
    flow = 0
    while flow < length:
        parent = {source: None}
        queue = deque([source])
        while queue and sink not in parent:
            u = queue.popleft()
            for v, cap in residual[u].items():
                if cap > 0 and v not in parent:
                    parent[v] = u
                    queue.append(v)
        if sink not in parent:
            return False
        v = sink
        while parent[v] is not None:
            u = parent[v]
            residual[u][v] -= 1
            residual[v][u] += 1
            v = u
        flow += 1
    return True


def matching_spectrum(N, n):
    """Ordinary per-candidate matching plus avoidance, using the filling lemma.

This deliberately shares the mathematical characterization, but not search
code, with the producer. The circulation comparator is a different formulation.
No asymptotic or timing advantage is inferred from agreement.
"""
    k = validate_summary(N, n)
    totals = list(map(sum, N))
    return [c for c in range(k + 1)
            if (c == k or all(n[y] <= totals[y] - N[y][c] for y in range(len(N))))
            and _prefix_feasible(N, n, c)]


def audit_decision(k, outcomes, available):
    """Route all possible earliest-omission branches to a diagnostic catalogue.

The catalogue is a set of class indices with owned, benign diagnostics. Return
the minimal exact branch list, its uncovered branches, and the least available
candidate. Catalogue sufficiency means first-omission routing only, not full
coverage after executing the diagnostics. COMPLETE is not a diagnostic class.
The caller must supply an exact checked spectrum for exact decisions.
"""
    if type(k) is not int or k < 1:
        raise ValueError("class count")
    if (type(outcomes) is not list or not outcomes
            or any(type(c) is not int or not 0 <= c <= k for c in outcomes)
            or outcomes != sorted(set(outcomes))):
        raise ValueError("ordered outcomes")
    if (type(available) is not list or any(type(c) is not int or not 0 <= c < k for c in available)
            or len(available) != len(set(available))):
        raise ValueError("diagnostic catalogue")
    branches = [c for c in outcomes if c < k]
    catalogue = set(available)
    unsupported = [c for c in branches if c not in catalogue]
    ready = [c for c in branches if c in catalogue]
    return {"first_omission_branches": branches,
            "complete_possible": k in outcomes,
            "catalogue_sufficient": not unsupported,
            "unsupported_branches": unsupported,
            "next_test_candidate": ready[0] if ready else None}
