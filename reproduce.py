"""Clean, offline, one-worker reproduction using exact shipped scientific inputs."""
from __future__ import annotations
import argparse,ast,csv,json,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TEST_PARTS=("capacity","source","mutations","controls","binding","overlap","stress","androlog")
NONDETERMINISTIC={"cpu_seconds","wall_seconds","peak_rss_kib","max_case_cpu_seconds",
                  "producer_certificate_cpu_seconds","checker_cpu_seconds",
                  "per_outcome_flow_cpu_seconds"}

def call(*args):
    subprocess.run([sys.executable,*args],cwd=ROOT,check=True,timeout=45)

def compare(reference: Path,reproduced: Path):
    with reference.open() as expected_handle, reproduced.open() as actual_handle:
        expected_reader=csv.DictReader(expected_handle); actual_reader=csv.DictReader(actual_handle)
        if expected_reader.fieldnames!=actual_reader.fieldnames:
            raise AssertionError("campaign column schema differs")
        old=list(expected_reader); new=list(actual_reader)
    if len(old)!=len(new): raise AssertionError("case count differs")
    keys=[k for k in old[0] if not k.endswith("_cpu_s")]
    for a,b in zip(old,new):
        if any(a[k]!=b[k] for k in keys): raise AssertionError("deterministic scientific result differs: "+a["case_id"])
    return len(old)

def deterministic(value):
    """Remove only explicitly descriptive timing/RSS fields, recursively."""
    if isinstance(value,dict):
        return {k:deterministic(v) for k,v in value.items() if k not in NONDETERMINISTIC}
    if isinstance(value,list): return [deterministic(v) for v in value]
    return value

def compare_json(reference: Path,reproduced: Path,label: str):
    expected=deterministic(json.loads(reference.read_text()))
    actual=deterministic(json.loads(reproduced.read_text()))
    if expected!=actual: raise AssertionError(label+" deterministic summary differs")
    return True

def isolation():
    for name in ("checker.py","verify.py"):
        tree=ast.parse((ROOT/"src"/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and any(x in (node.module or "") for x in ("producer","generate","oracle","baseline")):
                raise AssertionError("checker imports producer-side code")
            if isinstance(node,ast.Import) and any(any(x in a.name for x in ("producer","generate","oracle","baseline")) for a in node.names):
                raise AssertionError("checker imports producer-side code")
    return True

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=Path("reproduction"));p.add_argument("--chunk-size",type=int,default=200);a=p.parse_args()
    out=a.output.resolve()
    if out.exists(): raise SystemExit("output must be a new directory")
    if not 1<=a.chunk_size<=400: raise SystemExit("chunk size must be 1..400")
    out.mkdir(parents=True); start=time.perf_counter(); isolation()
    # Replay the immutable shipped packet first, then independently regenerate it.
    call("-m","src.verify","--output",str(out/"shipped-replay.json"))
    for lo in range(0,2448,a.chunk_size):
        call("-m","src.run","--output",str(out/"campaign"),"--start",str(lo),"--stop",str(min(lo+a.chunk_size,2448)))
    call("-m","src.run","--output",str(out/"campaign"),"--aggregate")
    for part in TEST_PARTS:
        call("-m","tests.validate","--part",part,"--output",str(out/"tests"))
    call("-m","src.verify","--certificates",str(out/"campaign"),"--output",str(out/"replay.json"))
    compared=compare(ROOT/"results/campaign/all_cases.csv",out/"campaign/all_cases.csv")
    campaign_summary=compare_json(ROOT/"results/campaign/summary.json",out/"campaign/summary.json","campaign")
    shipped_replay=compare_json(ROOT/"results/replay.json",out/"shipped-replay.json","shipped replay")
    regenerated_replay=compare_json(ROOT/"results/replay.json",out/"replay.json","regenerated replay")
    replay_agreement=(deterministic(json.loads((out/"shipped-replay.json").read_text()))==
                      deterministic(json.loads((out/"replay.json").read_text())))
    if not replay_agreement: raise AssertionError("shipped and regenerated replay summaries differ")
    for part in TEST_PARTS:
        expected=json.loads((ROOT/"results/tests"/(part+".json")).read_text())["result"]
        actual=json.loads((out/"tests"/(part+".json")).read_text())["result"]
        if expected!=actual: raise AssertionError("test result differs: "+part)
    record={"deterministic_case_rows_equal":compared,"campaign_summary_equal":campaign_summary,
            "shipped_certificates_replayed":shipped_replay,"regenerated_certificates_replayed":regenerated_replay,
            "shipped_and_regenerated_replay_equal":replay_agreement,
            "finite_test_results_equal":True,"finite_test_groups_equal":len(TEST_PARTS),
            "finite_test_groups":list(TEST_PARTS),"checker_import_isolation":True,"chunk_size":a.chunk_size,
            "wall_seconds_including_process_startup":time.perf_counter()-start,
            "status":"commands-and-scientific-results-reproduced; not a mechanized general proof"}
    (out/"comparison.json").write_text(json.dumps(record,indent=2)+"\n");print(json.dumps(record,indent=2))
