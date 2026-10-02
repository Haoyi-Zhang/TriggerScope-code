"""Replay shipped certificates without importing producer, generator, or oracle."""
from __future__ import annotations
import argparse,gzip,json,resource,time
from pathlib import Path
from .checker import check,InvalidCertificate

def strict_pairs(pairs):
    obj={}
    for k,v in pairs:
        if k in obj: raise ValueError("duplicate JSON key")
        obj[k]=v
    return obj

def parse(line):
    if len(line)>16*1024**2: raise ValueError("record size bound")
    return json.loads(line,object_pairs_hook=strict_pairs)

def replay(inputs: Path,reports: Path,certdir: Path):
    start=time.process_time(); resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    models={}
    for line in inputs.open():
        c=parse(line)
        if c["case_id"] in models: raise ValueError("duplicate input case")
        models[c["case_id"]]=c["model"]
    counts={}
    for line in reports.open():
        r=parse(line)
        if type(r) is not dict or set(r)!={"case_id","count_report"} or r["case_id"] in counts:
            raise ValueError("report schema or duplicate case")
        counts[r["case_id"]]=r["count_report"]
    if set(counts)!=set(models): raise ValueError("report/input case set mismatch")
    seen=set();steps=nodes=0
    for p in sorted(certdir.glob("cases-*.jsonl.gz")):
        with gzip.open(p,"rt") as f:
            for line in f:
                record=parse(line);key=record["case_id"]
                if key in seen or key not in models: raise ValueError("duplicate or unknown certificate")
                cert=record["certificate"]; status=check(models[key],counts[key],cert)
                N=cert["semantics"]["capacity"]; X=record["actual_allocation"]; n=cert["count_report"]
                if len(X)!=len(N): raise ValueError("ground-truth allocation shape")
                for y,row in enumerate(X):
                    if len(row)!=len(N[y]) or sum(row)!=n[y] or any(type(v)is not int or v<0 or v>N[y][c] for c,v in enumerate(row)):
                        raise ValueError("ground-truth allocation contract")
                actual=next((c for c in range(len(N[0])) if not any(row[c] for row in X)),len(N[0]))
                if actual not in cert["spectrum"]: raise ValueError("ground truth contradicts spectrum")
                seen.add(key);steps+=status["checker_steps"];nodes+=status["nodes"]
    if seen!=set(models): raise ValueError("missing certificate")
    return {"certificates_replayed":len(seen),"checker_steps":steps,"nodes_replayed":nodes,"cpu_seconds":time.process_time()-start,"peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"producer_imported":False,"failures":0}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,default=Path("data/cases.jsonl"));p.add_argument("--reports",type=Path,default=Path("data/reports.jsonl"));p.add_argument("--certificates",type=Path,default=Path("results/campaign"));p.add_argument("--output",type=Path);a=p.parse_args()
    try: result=replay(a.inputs,a.reports,a.certificates)
    except (ValueError,KeyError,TypeError,IndexError,OverflowError) as error: raise SystemExit("REJECT: "+str(error))
    text=json.dumps(result,indent=2)+"\n"
    if a.output: a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text)
    print(text,end="")
