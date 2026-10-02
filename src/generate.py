"""Deterministic benign finite-record models, not Android applications or malware."""
from __future__ import annotations
import random
from .producer import matching_prefix, allocation_witness

SEED=9142026
FAMILIES=("balanced","rare-event","compound","temporal","environment")
TAXONOMY=("time","location","sms","network","build","camera","addition","music","is_screen_on","is_screen_off")

def g(field,value): return {"field":field,"equals":value}
def mon(op,field,value,**extra): return {"op":op,"guard":g(field,value),**extra}

def make_model(family: str,index: int,fixture: bool=False) -> dict:
    r=random.Random(SEED+10000*FAMILIES.index(family)+index+(1000000 if fixture else 0))
    kinds=list(range(4)); r.shuffle(kinds)
    # Event order is the declared alphabet order; it is semantically significant.
    events=[{"kind":a,"value":a%2,"context":(a//2)%2,"bucket":a%2} for a in kinds]
    a,b,c,d=kinds
    if family=="balanced":
        monitors=[mon("ever","kind",x) for x in kinds]
        triggers=[0,1,2,3]
    elif family=="rare-event":
        threshold=(2,3,5)[index%3]
        monitors=[mon("count","kind",a,threshold=threshold),mon("ever","kind",b)]
        triggers=[0,1,["and",0,1]]
    elif family=="compound":
        monitors=[mon("ever","kind",x) for x in kinds[:3]]
        triggers=[["and",0,1],["or",1,2],["and",2,["not",0]]]
        if index%2: triggers.append(["or",0,["not",2]])
    elif family=="temporal":
        monitors=[mon("before","kind",a,then=g("kind",b)),mon("ever","kind",c),mon("last","value",1)]
        triggers=[0,1,2,["and",0,2]]
    elif family=="environment":
        events=[{"kind":a,"value":a%2,"context":ctx,"bucket":a%2} for ctx in (0,1) for a in kinds]
        monitors=[mon("before","kind",a,then=g("kind",b)),mon("ever","context",1)]
        triggers=[0,1,["and",0,1]]
    else: raise ValueError("unknown family")
    # Variations affect predicates, Boolean polarity, legal length, and reporting.
    if index%3==1: triggers=[ ["not",f] if j==0 else f for j,f in enumerate(triggers)]
    if index%4==2:
        for e in events: e["bucket"]=0
    H=(3,4,6,8,12,24)[(index//6)%6]
    if fixture: H=1+(index%6)
    return {"events":events,"monitors":monitors,"triggers":triggers,"horizon":H,
            "min_length":0 if index%7==0 else 1,"environment_locked":family=="environment",
            "report_modulus":1+(index%2)}


def report_for(N: list[list[int]],case: dict) -> tuple[list[int],list[list[int]],str]:
    """Produce a simulated distinct-trace subset via a cell allocation.

    X selects the lexicographically first X[y][c] trace tokens in each cell.
    No enumerated device execution or real analyzer is implied by this encoding.
    """
    k=len(N[0]); mode=case["report_mode"]; j=case["index"]
    X=[[0]*k for _ in N]
    if mode==0: pass
    elif mode in (1,2):
        for c in range(k):
            if mode==2 and c==j%k: continue
            rows=[y for y in range(len(N)) if N[y][c]]
            y=rows[(j+c)%len(rows)]; X[y][c]=1
    elif mode==3: X=[list(row) for row in N]
    elif mode==4:
        for y,row in enumerate(N):
            live=[c for c,v in enumerate(row) if v]
            if live: X[y][live[(j+y)%len(live)]]=1
    elif mode==5: X=[[v if c!=j%k else 0 for c,v in enumerate(row)] for row in N]
    else: raise ValueError("unknown report mode")
    n=list(map(sum,X))
    return n,X,("empty","class-complete","seeded-omission","census","one-per-bucket","class-exclusion")[mode]


def cases():
    for f in FAMILIES:
        for j in range(480):
            yield {"case_id":f"generated-{FAMILIES.index(f)*480+j:04d}","family":f,"index":j,"report_mode":j%6,
                   "origin":"generated","model":make_model(f,j)}
    for j in range(48):
        f=FAMILIES[j%5]
        yield {"case_id":f"fixture-{j:02d}","family":f,"index":j,"report_mode":j%6,
               "origin":"author-constructed schema fixture","schema_motivation":TAXONOMY[j%10],
               "model":make_model(f,j,True)}
