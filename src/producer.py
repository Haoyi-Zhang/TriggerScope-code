"""Certificate producer. Its search and matching code are not imported by checker.py."""
from __future__ import annotations
from collections import deque
from typing import Any


def guard(g: dict, e: dict) -> bool:
    return e[g["field"]] == g["equals"]


def formula(f: Any, values: tuple[int, ...]) -> bool:
    if type(f) is int:
        return bool(values[f])
    if f[0] == "not":
        return not formula(f[1], values)
    if f[0] == "and":
        return formula(f[1], values) and formula(f[2], values)
    return formula(f[1], values) or formula(f[2], values)


def initial(model: dict) -> tuple[int, ...]:
    return (-1, -1) + (0,) * len(model["monitors"])


def advance(model: dict, q: tuple[int, ...], event: dict) -> tuple[int, ...] | None:
    env = q[0]
    if model["environment_locked"]:
        if env >= 0 and env != event["context"]:
            return None
        env = event["context"]
    else:
        env = -1
    out = [env, event["bucket"]]
    for mon, s in zip(model["monitors"], q[2:]):
        op = mon["op"]
        a = guard(mon["guard"], event)
        if op == "ever": t = int(s or a)
        elif op == "last": t = int(a)
        elif op == "count": t = min(mon["threshold"], s + int(a))
        elif op == "before":
            # Strictly different positions: a simultaneous first A/B does not accept.
            t = 2 if s == 2 or (s == 1 and guard(mon["then"], event)) else int(s == 1 or a)
        else: raise ValueError("unsupported monitor")
        out.append(t)
    return tuple(out)


def signature(model: dict, q: tuple[int, ...]) -> tuple[int, ...]:
    v = tuple(int(s >= (m["threshold"] if m["op"] == "count" else 2 if m["op"] == "before" else 1))
              for s,m in zip(q[2:], model["monitors"]))
    return tuple(int(formula(f, v)) for f in model["triggers"])


def enumerate_model(model: dict) -> dict:
    """Build a bounded layered DAG, exact cell counts, and shortlex class order."""
    H = model["horizon"]
    layers = [{initial(model): (1, ())}]
    edge_count = 0
    for d in range(H):
        nxt: dict[tuple, tuple[int, tuple]] = {}
        for q,(count,word) in layers[-1].items():
            for a,event in enumerate(model["events"]):
                edge_count += 1
                t = advance(model,q,event)
                if t is None: continue
                candidate = word + (a,)
                old = nxt.get(t)
                nxt[t] = (count + (old[0] if old else 0), min(candidate,old[1]) if old else candidate)
        layers.append(nxt)
        if sum(map(len,layers)) > 8192:
            raise ValueError("proof-DAG budget exceeded")
    if len(set(q for L in layers for q in L)) > 96:
        raise ValueError("joint-state budget exceeded")
    cells: dict[tuple, dict[tuple,int]] = {}
    representatives: dict[tuple,tuple] = {}
    for d,L in enumerate(layers):
        if d < model["min_length"]: continue
        for q,(count,word) in L.items():
            s=signature(model,q); y=(q[1],d % model["report_modulus"])
            row=cells.setdefault(y,{})
            row[s]=row.get(s,0)+count
            if s not in representatives or (len(word),word)<(len(representatives[s]),representatives[s]):
                representatives[s]=word
    classes=sorted(representatives, key=lambda s:(len(representatives[s]),representatives[s]))
    buckets=sorted(cells)
    N=[[cells[y].get(s,0) for s in classes] for y in buckets]
    return {"layers":[[[list(q),count,list(word)] for q,(count,word) in sorted(L.items())] for L in layers],
            "classes":[list(s) for s in classes],"representatives":[list(representatives[s]) for s in classes],
            "buckets":[list(y) for y in buckets],"capacity":N,
            "producer_edge_checks":edge_count}


def matching_prefix(N: list[list[int]], n: list[int], limit: int | None=None) -> dict:
    """Incremental capacitated matching, stopping at the first infeasible prefix."""
    k=len(N[0]); b=len(N); limit=k if limit is None else limit
    assigned=[[] for _ in range(b)]
    support={}
    def neighbors(c: int) -> tuple[int, ...]:
        # Invocation-local index: preserve ascending bucket traversal exactly.
        if c not in support:
            support[c]=tuple(y for y in range(b) if N[y][c])
        return support[c]
    def augment(c: int, seen: set[int]) -> bool:
        for y in neighbors(c):
            if y in seen: continue
            seen.add(y)
            if len(assigned[y]) < n[y]:
                assigned[y].append(c); return True
            for old in list(assigned[y]):
                if augment(old,seen):
                    assigned[y].remove(old); assigned[y].append(c); return True
        return False
    p=limit
    for c in range(limit):
        if not augment(c,set()): p=c; break
    cut=[]
    if p<limit:
        # Alternating reachability yields a Hall-deficient set inside prefix p+1.
        left={p}; right=set(); queue=deque([p])
        while queue:
            c=queue.popleft()
            for y in neighbors(c):
                if y not in right:
                    right.add(y)
                    for old in assigned[y]:
                        if old not in left: left.add(old); queue.append(old)
        cut=sorted(left)
    matching=sorted([[c,y] for y,S in enumerate(assigned) for c in S])
    return {"prefix":p,"matching":matching,"cut":cut}


def spectrum(N: list[list[int]], n: list[int], p: int) -> list[int]:
    k=len(N[0]); totals=list(map(sum,N))
    return [c for c in range(k) if c<=p and all(n[y]<=totals[y]-N[y][c] for y in range(len(N)))] + ([k] if p==k else [])


def allocation_witness(N: list[list[int]], n: list[int], outcome: int) -> list[list[int]]:
    k=len(N[0]); m=matching_prefix(N,n,outcome)
    if m["prefix"] != outcome: raise ValueError("infeasible prefix")
    X=[[0]*k for _ in N]
    for c,y in m["matching"]: X[y][c]=1
    for y,row in enumerate(N):
        remaining=n[y]-sum(X[y])
        for c,cap in enumerate(row):
            if c==outcome: continue
            take=min(remaining,cap-X[y][c]); X[y][c]+=take; remaining-=take
        if remaining: raise ValueError("infeasible exclusion")
    return X


def certify(model: dict, n: list[int], dag: dict | None=None) -> dict:
    dag=enumerate_model(model) if dag is None else dag
    N=dag["capacity"]
    if len(n)!=len(N) or any(type(x) is not int or not 0<=x<=sum(row) for x,row in zip(n,N)):
        raise ValueError("inconsistent count report")
    pm=matching_prefix(N,n); outcomes=spectrum(N,n,pm["prefix"])
    if not outcomes: raise AssertionError("nonempty report family must have an outcome")
    k=len(N[0])
    verdict="forced-complete" if outcomes==[k] else "ambiguous" if k in outcomes else "forced-incomplete"
    selected=sorted({outcomes[0],outcomes[-1]})
    return {"semantics":{a:v for a,v in dag.items() if a!="producer_edge_checks"},
            "count_report":list(n), "prefix_proof":pm,"spectrum":outcomes,"verdict":verdict,
            "witnesses":[{"outcome":c,"allocation":allocation_witness(N,n,c)} for c in selected]}
