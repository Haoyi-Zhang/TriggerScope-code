"""Fail-closed semantic replay checker; imports neither producer nor oracle.

This is executable certificate checking, not a proof assistant or a second author.
"""
from __future__ import annotations
from collections import Counter
from typing import Any

class InvalidCertificate(ValueError):
    pass

def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidCertificate(message)

def integer(x: Any, lo: int, hi: int) -> bool:
    return type(x) is int and lo <= x <= hi

def validate_model(m: dict) -> None:
    require(type(m) is dict, "model must be an object")
    require(set(m)=={"events","monitors","triggers","horizon","min_length","environment_locked","report_modulus"},"model keys")
    require(integer(m["horizon"],0,24),"horizon")
    require(integer(m["min_length"],0,m["horizon"]),"minimum length")
    require(type(m["environment_locked"]) is bool,"environment flag")
    require(integer(m["report_modulus"],1,4),"report modulus")
    E=m["events"]; M=m["monitors"]; F=m["triggers"]
    require(type(E) is list and 1<=len(E)<=32,"alphabet size")
    for e in E:
        require(type(e) is dict and set(e)=={"kind","value","context","bucket"},"event schema")
        require(integer(e["kind"],0,31) and integer(e["value"],0,1) and integer(e["context"],0,1) and integer(e["bucket"],0,7),"event field bounds")
    require(len({tuple(e[x] for x in ("kind","value","context","bucket")) for e in E})==len(E),"duplicate event values")
    require(type(M) is list and 1<=len(M)<=12,"monitor count")
    def guard(g):
        require(type(g) is dict and set(g)=={"field","equals"},"guard schema")
        require(g["field"] in ("kind","value","context"),"guard field")
        require(integer(g["equals"],0,31 if g["field"]=="kind" else 1),"guard constant")
    for mon in M:
        require(type(mon) is dict and mon.get("op") in ("ever","last","count","before"),"monitor operator")
        op=mon["op"]; expected={"op","guard"}|({"threshold"} if op=="count" else {"then"} if op=="before" else set())
        require(set(mon)==expected,"monitor keys"); guard(mon["guard"])
        if op=="count": require(integer(mon["threshold"],1,24),"count threshold")
        if op=="before": guard(mon["then"])
    require(type(F) is list and 1<=len(F)<=12,"trigger count")
    def expression(f,depth=0):
        require(depth<=12,"expression depth")
        if type(f) is int:
            require(0<=f<len(M),"atom index"); return
        require(type(f) is list and len(f) in (2,3),"expression shape")
        require((f[0]=="not" and len(f)==2) or (f[0] in ("and","or") and len(f)==3),"expression operator")
        for sub in f[1:]: expression(sub,depth+1)
    for f in F: expression(f)


def check(model: dict, count_report: list[int], certificate: dict, *, meter: dict | None = None) -> dict:
    """Validate source semantics, exact counts/order, and the matching/cut proof.

    No optimization or reachability search is called. Every transition must land
    at an explicitly supplied next-layer node. Counters are replayed over those
    nodes; a missing, spurious, or incorrectly weighted node is rejected.
    """
    if meter is not None: meter["checker_steps"] = 0
    validate_model(model)
    require(type(certificate) is dict and set(certificate)=={"semantics","count_report","prefix_proof","spectrum","verdict","witnesses"},"certificate keys")
    s=certificate["semantics"]
    require(type(s) is dict and set(s)=={"layers","classes","representatives","buckets","capacity"},"semantic certificate keys")
    layers=s["layers"]; H=model["horizon"]; M=model["monitors"]
    require(type(layers) is list and len(layers)==H+1,"layer count")
    require(sum(len(L) for L in layers)<=8192,"DAG size")
    maps=[]; seen=set(); steps=0
    for depth,L in enumerate(layers):
        require(type(L) is list and 1<=len(L)<=96,"layer size")
        index={}
        for record in L:
            require(type(record) is list and len(record)==3,"node record")
            q,count,word=record
            require(type(q) is list and len(q)==2+len(M),"state dimension")
            require(integer(q[0],-1,1) and integer(q[1],-1,7),"state header")
            for mon,a in zip(M,q[2:]):
                require(integer(a,0,mon.get("threshold",2 if mon["op"]=="before" else 1)),"monitor state")
            require(type(count) is int and 1<=count and count.bit_length()<=256,"positive bounded count")
            require(type(word) is list and len(word)==depth and all(integer(a,0,len(model["events"])-1) for a in word),"word encoding")
            key=tuple(q); require(key not in index,"duplicate state")
            index[key]=(count,tuple(word)); seen.add(key)
        maps.append(index)
    require(len(seen)<=96,"joint-state bound")
    start=(-1,-1)+(0,)*len(M)
    require(maps[0]=={start:(1,())},"initial state/count/word")
    for depth in range(H):
        target=maps[depth+1]
        incoming={q:0 for q in target}; least={q:None for q in target}
        for q,(multiplicity,word) in maps[depth].items():
            for a,e in enumerate(model["events"]):
                steps+=1
                if meter is not None: meter["checker_steps"] = steps
                if model["environment_locked"] and q[0]!=-1 and q[0]!=e["context"]:
                    continue
                values=[e["context"] if model["environment_locked"] else -1,e["bucket"]]
                for mon,old in zip(M,q[2:]):
                    g=mon["guard"]; hit=(e[g["field"]]==g["equals"])
                    if mon["op"]=="last": new=1 if hit else 0
                    elif mon["op"]=="ever": new=max(old,1 if hit else 0)
                    elif mon["op"]=="count": new=min(old+(1 if hit else 0),mon["threshold"])
                    else:
                        b=mon["then"]; later=(e[b["field"]]==b["equals"])
                        if old==2: new=2
                        elif old==1: new=2 if later else 1
                        else: new=1 if hit else 0
                    values.append(new)
                t=tuple(values)
                require(t in target,"transition closure")
                incoming[t]+=multiplicity
                w=word+(a,)
                if least[t] is None or w<least[t]: least[t]=w
        for q,(multiplicity,word) in target.items():
            require(incoming[q]==multiplicity and least[q]==word,"count/shortlex recurrence or spurious node")
    table={}; reps={}
    def truth(f,v):
        if type(f) is int: return v[f]
        if f[0]=="not": return not truth(f[1],v)
        if f[0]=="and": return all(truth(g,v) for g in f[1:])
        return any(truth(g,v) for g in f[1:])
    for depth,L in enumerate(maps):
        if depth<model["min_length"]: continue
        for q,(count,word) in L.items():
            values=[]
            for mon,a in zip(M,q[2:]):
                threshold=mon.get("threshold",2 if mon["op"]=="before" else 1)
                values.append(a==threshold)
            sig=tuple(int(truth(f,values)) for f in model["triggers"])
            y=(q[1],depth % model["report_modulus"])
            table.setdefault(y,Counter())[sig]+=count
            if sig not in reps or (len(word),word)<(len(reps[sig]),reps[sig]): reps[sig]=word
    classes=sorted(reps,key=lambda c:(len(reps[c]),reps[c])); buckets=sorted(table)
    N=[[table[y][c] for c in classes] for y in buckets]
    require(1<=len(classes)<=2048,"class count")
    require(s["classes"]==[list(c) for c in classes],"class identity/order")
    require(s["representatives"]==[list(reps[c]) for c in classes],"canonical class representative")
    require(s["buckets"]==[list(y) for y in buckets] and s["capacity"]==N,"semantic capacity table")
    require(all(v.bit_length()<=256 for row in N for v in row),"capacity width")
    n=certificate["count_report"]; k=len(classes); b=len(N)
    require(type(n) is list and len(n)==b and all(type(v) is int and 0<=v<=sum(N[y]) for y,v in enumerate(n)),"inconsistent count report")
    require(type(count_report) is list and all(type(v) is int for v in count_report) and n==count_report,"report binding")
    proof=certificate["prefix_proof"]
    require(type(proof) is dict and set(proof)=={"prefix","matching","cut"},"prefix proof keys")
    p=proof["prefix"]; require(integer(p,0,k),"prefix bound")
    pairs=proof["matching"]
    require(type(pairs) is list and len(pairs)==p,"matching size")
    matched=set(); usage=[0]*b
    for pair in pairs:
        require(type(pair) is list and len(pair)==2,"matching edge format")
        c,y=pair
        require(integer(c,0,p-1) and integer(y,0,b-1) and c not in matched and N[y][c]>0,"matching edge")
        matched.add(c); usage[y]+=1
    require(matched==set(range(p)) and all(v<=n[y] for y,v in enumerate(usage)),"matching saturation/capacity")
    cut=proof["cut"]
    require(type(cut) is list,"cut format")
    if p==k: require(cut==[],"unnecessary cut")
    else:
        require(len(cut)>0 and all(integer(c,0,p) for c in cut) and len(set(cut))==len(cut),"cut vertex set")
        neighbors={y for y in range(b) for c in cut if N[y][c]>0}
        require(len(cut)>sum(n[y] for y in neighbors),"Hall deficiency")
    totals=[sum(row) for row in N]
    expected=[]
    for c in range(k):
        steps+=b
        if meter is not None: meter["checker_steps"] = steps
        if c<=p and all(n[y]<=totals[y]-N[y][c] for y in range(b)):
            expected.append(c)
    if p==k: expected.append(k)
    require(expected and certificate["spectrum"]==expected,"omission spectrum")
    verdict="forced-complete" if expected==[k] else "ambiguous" if k in expected else "forced-incomplete"
    require(certificate["verdict"]==verdict,"verdict")
    witnesses=certificate["witnesses"]
    require(type(witnesses) is list and len(witnesses)==len(set((expected[0],expected[-1]))),"witness count")
    outcomes=[]
    for w in witnesses:
        require(type(w) is dict and set(w)=={"outcome","allocation"},"witness keys")
        X=w["allocation"]; o=w["outcome"]
        require(integer(o,0,k) and o in expected,"witness outcome")
        require(type(X) is list and len(X)==b,"allocation rows")
        for y,row in enumerate(X):
            require(type(row) is list and len(row)==k,"allocation width")
            require(all(type(v) is int and 0<=v<=N[y][c] for c,v in enumerate(row)) and sum(row)==n[y],"allocation capacity/count")
        covered=[sum(X[y][c] for y in range(b))>0 for c in range(k)]
        actual=next((c for c in range(k) if not covered[c]),k)
        require(actual==o,"witness first omission")
        outcomes.append(o)
    require(outcomes==sorted(set((expected[0],expected[-1]))),"extreme witness outcomes")
    return {"verdict":verdict,"spectrum":expected,"nodes":sum(map(len,layers)),"states":len(seen),"classes":k,"buckets":b,"checker_steps":steps,"max_count_bits":max(v.bit_length() for row in N for v in row)}
