"""Separate exact baseline: lower-bound feasible circulation, rebuilt per outcome.

No prefix theorem, matching implementation, or checker is imported.
"""
from collections import deque

def feasible(N,n,outcome):
    b=len(N); k=len(N[0]); S=0; T=b+k+1; SS=T+1; TT=T+2
    size=TT+1; residual=[{} for _ in range(size)]; balance=[0]*size
    def edge(u,v,capacity):
        residual[u][v]=residual[u].get(v,0)+capacity
        residual[v].setdefault(u,0)
    def bounded(u,v,lo,hi):
        if hi<lo: raise ValueError("inconsistent lower bound")
        edge(u,v,hi-lo); balance[u]-=lo; balance[v]+=lo
    total=sum(n)
    for y,row in enumerate(N):
        bounded(S,1+y,n[y],n[y])
        for c,v in enumerate(row): bounded(1+y,1+b+c,0,0 if c==outcome else v)
    for c in range(k):
        lo=1 if c<outcome else 0
        hi=sum(row[c] for row in N)
        bounded(1+b+c,T,lo,hi)
    bounded(T,S,0,total)
    required=0
    for v in range(T+1):
        if balance[v]>0: edge(SS,v,balance[v]); required+=balance[v]
        elif balance[v]<0: edge(v,TT,-balance[v])
    flow=0
    while flow<required:
        previous={SS:None}; q=deque([SS])
        while q and TT not in previous:
            u=q.popleft()
            for v,cap in residual[u].items():
                if cap>0 and v not in previous: previous[v]=u; q.append(v)
        if TT not in previous: return False
        push=required-flow; v=TT
        while previous[v] is not None:
            u=previous[v]; push=min(push,residual[u][v]); v=u
        v=TT
        while previous[v] is not None:
            u=previous[v]; residual[u][v]-=push; residual[v][u]+=push; v=u
        flow+=push
    return True

def exact_spectrum(N,n):
    return [c for c in range(len(N[0])+1) if feasible(N,n,c)]
