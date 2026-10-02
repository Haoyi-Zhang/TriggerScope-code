"""Exponential, direct-trace oracle. No producer or checker imports."""
from __future__ import annotations
from itertools import product


def evaluate(model: dict, word: tuple[int,...]) -> tuple[int,...] | None:
    events=[model["events"][i] for i in word]
    if model["environment_locked"] and len({e["context"] for e in events})>1: return None
    atom=[]
    for m in model["monitors"]:
        g=m["guard"]
        hit=[e[g["field"]]==g["equals"] for e in events]
        if m["op"]=="ever": v=any(hit)
        elif m["op"]=="last": v=bool(hit and hit[-1])
        elif m["op"]=="count": v=sum(hit)>=m["threshold"]
        else:
            h=m["then"]
            v=any(hit[i] and events[j][h["field"]]==h["equals"]
                  for i in range(len(events)) for j in range(i+1,len(events)))
        atom.append(bool(v))
    def f(x):
        if isinstance(x,int): return atom[x]
        values=[f(i) for i in x[1:]]
        return not values[0] if x[0]=="not" else all(values) if x[0]=="and" else any(values)
    return tuple(int(f(t)) for t in model["triggers"])


def enumerate_words(model: dict, word_limit: int=250000) -> dict:
    H=model["horizon"]; a=len(model["events"])
    if sum(a**d for d in range(model["min_length"],H+1))>word_limit: raise ValueError("oracle word budget")
    rep={}; cells={}; items=[]
    for d in range(model["min_length"],H+1):
        for word in product(range(a),repeat=d):
            sig=evaluate(model,word)
            if sig is None: continue
            y=(model["events"][word[-1]]["bucket"] if word else -1,d%model["report_modulus"])
            if sig not in rep: rep[sig]=word
            cells[(y,sig)]=cells.get((y,sig),0)+1
            items.append((word,y,sig))
    C=sorted(rep,key=lambda s:(len(rep[s]),rep[s])); Y=sorted({y for y,s in cells})
    return {"classes":[list(s) for s in C],"representatives":[list(rep[s]) for s in C],
            "buckets":[list(y) for y in Y],"capacity":[[cells.get((y,s),0) for s in C] for y in Y],
            "items":items}


def capacity_outcomes(N: list[list[int]]) -> dict:
    """All distinct subsets of labelled tokens, grouped by count report."""
    tokens=[(y,c) for y,row in enumerate(N) for c,v in enumerate(row) for _ in range(v)]
    if len(tokens)>16: raise ValueError("subset oracle budget")
    k=len(N[0]); result={}
    for selection in product((False,True),repeat=len(tokens)):
        counts=[0]*len(N); covered=set()
        for take,(y,c) in zip(selection,tokens):
            if take: counts[y]+=1; covered.add(c)
        first=next((c for c in range(k) if c not in covered),k)
        result.setdefault(tuple(counts),set()).add(first)
    return result
