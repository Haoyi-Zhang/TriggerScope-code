"""Bounded one-worker campaign. Run from the standalone repository root."""
from __future__ import annotations
import argparse,csv,gzip,json,os,resource,signal,time
from pathlib import Path
from .producer import enumerate_model,certify
from .checker import check
from .generate import cases,report_for
from .baseline import exact_spectrum

BUDGET_NODES=2500000
BUDGET_STEPS=8000000

def dump(obj): return json.dumps(obj,separators=(",",":"),sort_keys=True)

def build_inputs(path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w") as f:
        for case in cases(): f.write(dump(case)+"\n")

def timeout(*_): raise TimeoutError("20-second case bound")

def run(inputs: Path,out: Path,start: int,stop: int):
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    signal.signal(signal.SIGALRM,timeout)
    out.mkdir(parents=True,exist_ok=True)
    stem=f"cases-{start:04d}-{stop:04d}"
    paths=[out/(stem+suffix) for suffix in (".jsonl.gz",".csv",".resources.json")]
    if any(p.exists() for p in paths): raise FileExistsError("range already exists; use a new output directory or resume a missing range")
    begin=time.process_time(); wall=time.perf_counter(); rows=[]; nodes=steps=0; maxcase=0.
    with gzip.open(paths[0],"wt",compresslevel=6) as certfile:
        for i,line in enumerate(inputs.open()):
            if i<start: continue
            if i>=stop: break
            case=json.loads(line); model=case["model"]
            signal.setitimer(signal.ITIMER_REAL,20)
            tick=time.process_time()
            dag=enumerate_model(model)
            n,X,mode=report_for(dag["capacity"],case)
            t=time.process_time(); cert=certify(model,n,dag); produce=time.process_time()-t
            t=time.process_time(); stats=check(model,n,cert); replay=time.process_time()-t
            N=dag["capacity"]; k=len(N[0]); b=len(N)
            t=time.process_time(); reference=exact_spectrum(N,n); flowtime=time.process_time()-t
            if reference!=cert["spectrum"]: raise AssertionError("circulation baseline disagreement")
            covered=[sum(row[c] for row in X)>0 for c in range(k)]
            actual=next((c for c,v in enumerate(covered) if not v),k)
            if actual not in cert["spectrum"]: raise AssertionError("actual report outside spectrum")
            avoid=[c for c in range(k) if all(n[y]<=sum(N[y])-N[y][c] for y in range(b))]
            no_hall=avoid+[k]
            no_exclusion=list(range(min(cert["prefix_proof"]["prefix"],k-1)+1))+([k] if cert["prefix_proof"]["prefix"]==k else [])
            marginals=all(any(n[y]>0 and N[y][c]>0 for y in range(b)) for c in range(k))
            elapsed=time.process_time()-tick; maxcase=max(maxcase,elapsed)
            row={"case_id":case["case_id"],"origin":case["origin"],"family":case["family"],"report_mode":mode,
                 "horizon":model["horizon"],"alphabet":len(model["events"]),**stats,
                 "spectrum_size":len(cert["spectrum"]),"actual_outcome":actual,"actual_complete":int(actual==k),
                 "bucket_full":int(all(v>0 for v in n)),"count_threshold":int(sum(n)>=k),
                 "marginal_possible":int(marginals),"full_possible":int(k in cert["spectrum"]),
                 "no_hall_disagreement":int(no_hall!=cert["spectrum"]),"no_exclusion_disagreement":int(no_exclusion!=cert["spectrum"]),
                 "producer_edges":dag["producer_edge_checks"],"universe_size":sum(map(sum,N)),"reported_traces":sum(n),
                 "produce_certificate_cpu_s":produce,"checker_cpu_s":replay,"per_outcome_flow_cpu_s":flowtime,"case_cpu_s":elapsed,
                 "certificate_bytes":len(dump(cert).encode())}
            row.pop("spectrum")
            rows.append(row); nodes+=stats["nodes"]; steps+=stats["checker_steps"]
            certfile.write(dump({"case_id":case["case_id"],"actual_allocation":X,"certificate":cert})+"\n")
            signal.setitimer(signal.ITIMER_REAL,0)
    if len(rows)!=stop-start: raise ValueError("input range not present")
    with paths[1].open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    info={"start":start,"stop":stop,"cases":len(rows),"workers":1,"cpu_seconds":time.process_time()-begin,
          "wall_seconds":time.perf_counter()-wall,"max_case_cpu_seconds":maxcase,"peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          "layered_nodes":nodes,"checker_steps":steps,"failures":0}
    paths[2].write_text(json.dumps(info,indent=2)+"\n")
    print(json.dumps(info))

def aggregate(out: Path,inputs: Path):
    rows=[]
    for p in sorted(out.glob("cases-*.csv")): rows.extend(csv.DictReader(p.open()))
    if len(rows)!=2448 or len({r["case_id"] for r in rows})!=2448: raise ValueError("expected exactly 2448 unique case IDs")
    counters=[json.loads(p.read_text()) for p in sorted(out.glob("cases-*.resources.json"))]
    def num(key): return [float(r[key]) for r in rows]
    def distribution(group):
        return {g:{v:sum(r[group]==g and r["verdict"]==v for r in rows) for v in ("forced-complete","ambiguous","forced-incomplete")} for g in sorted({r[group] for r in rows})}
    baselines={}
    for key in ("bucket_full","count_threshold","marginal_possible","full_possible"):
        yes=[r for r in rows if int(r[key])]
        baselines[key]={"assertions":len(yes),"not_entailed":sum(r["verdict"]!="forced-complete" for r in yes),"false_for_constructed_report":sum(not int(r["actual_complete"]) for r in yes)}
    models=[json.loads(line)["model"] for line in inputs.open()]
    metrics={"cases":len(rows),"generated_instances":2400,"authored_fixtures":48,
             "distinct_structural_models":len({dump(m) for m in models}),
             "verdicts":{v:sum(r["verdict"]==v for r in rows) for v in ("forced-complete","ambiguous","forced-incomplete")},
             "by_family":distribution("family"),"by_origin":distribution("origin"),"by_report_mode":distribution("report_mode"),
             "baselines":baselines,"ablation_disagreements":{key:int(sum(num(key))) for key in ("no_hall_disagreement","no_exclusion_disagreement")},
             "layered_nodes":sum(c["layered_nodes"] for c in counters),"checker_steps":sum(c["checker_steps"] for c in counters),
             "cpu_seconds":sum(c["cpu_seconds"] for c in counters),"wall_seconds":sum(c["wall_seconds"] for c in counters),
             "peak_rss_kib":max(c["peak_rss_kib"] for c in counters),"max_case_cpu_seconds":max(num("case_cpu_s")),
             "max_nodes":int(max(num("nodes"))),"max_states":int(max(num("states"))),"max_classes":int(max(num("classes"))),
             "max_count_bits":int(max(num("max_count_bits"))),"max_certificate_bytes":int(max(num("certificate_bytes"))),
             "total_certificate_bytes":int(sum(num("certificate_bytes"))),
             "producer_certificate_cpu_seconds":sum(num("produce_certificate_cpu_s")),"checker_cpu_seconds":sum(num("checker_cpu_s")),
             "per_outcome_flow_cpu_seconds":sum(num("per_outcome_flow_cpu_s")),
             "circulation_disagreements":0,"actual_outcome_exclusions":0,"failures":sum(c["failures"] for c in counters)}
    if metrics["layered_nodes"]>BUDGET_NODES or metrics["checker_steps"]>BUDGET_STEPS: raise ValueError("aggregate campaign counter budget exceeded")
    (out/"summary.json").write_text(json.dumps(metrics,indent=2)+"\n")
    with (out/"all_cases.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(metrics,indent=2))

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--inputs",type=Path,default=Path("data/cases.jsonl"));a.add_argument("--output",type=Path,default=Path("reproduction"));a.add_argument("--start",type=int,default=0);a.add_argument("--stop",type=int,default=2448);a.add_argument("--build-inputs",action="store_true");a.add_argument("--aggregate",action="store_true");args=a.parse_args()
    if args.build_inputs: build_inputs(args.inputs)
    elif args.aggregate: aggregate(args.output,args.inputs)
    else: run(args.inputs,args.output,args.start,args.stop)
