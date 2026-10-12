"""New summary-only comparison on retained inputs, not campaign regeneration.

Recheck source/report binding before using N,n. Never pass actual_allocation to
the routing methods. Output is separate from the frozen campaign and its timers.
"""
import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path

from src.baseline import exact_spectrum
from src.checker import check
from src.oracle import capacity_outcomes
from src.summary_audit import audit_decision, cardinality_spectrum, matching_spectrum

ROOT = Path(__file__).resolve().parents[1]


def unique_records(path, value_key):
    result = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            key = record["case_id"]
            if key in result:
                raise ValueError("duplicate input ID")
            result[key] = record[value_key]
    return result


def compare_one(N, n, expected):
    matching = matching_spectrum(N, n)
    circulation = exact_spectrum(N, n)
    relaxed = cardinality_spectrum(N, n)
    if matching != expected or circulation != expected:
        raise AssertionError("exact summary reference disagreement")
    if not set(expected) <= set(relaxed):
        raise AssertionError("cardinality relaxation lost an exact outcome")
    k = len(N[0])
    catalogues = [[], list(range(k)), list(range(0, k, 2)), list(range(k // 2))]
    exact_decisions = [audit_decision(k, expected, Q) for Q in catalogues]
    relaxed_decisions = [audit_decision(k, relaxed, Q) for Q in catalogues]
    return {"spectrum": expected, "cardinality_spectrum": relaxed,
            "matching_spectrum": matching, "circulation_spectrum": circulation,
            "cardinality_extra_finite_branches": len((set(relaxed) - set(expected)) - {k}),
            "cardinality_extra_complete": int(k in relaxed and k not in expected),
            "cardinality_routing_disagreements": sum(a != b for a, b in zip(exact_decisions, relaxed_decisions)),
            "cardinality_catalogue_sufficiency_disagreements": sum(
                a["catalogue_sufficient"] != b["catalogue_sufficient"]
                for a, b in zip(exact_decisions, relaxed_decisions)),
            "cardinality_next_candidate_disagreements": sum(
                a["next_test_candidate"] != b["next_test_candidate"]
                for a, b in zip(exact_decisions, relaxed_decisions)),
            "catalogues": catalogues, "exact_decisions": exact_decisions}


def source_control(name, model, n):
    # Source construction is confined to the new authored controls.
    from src.oracle import enumerate_words
    from src.producer import certify, enumerate_model
    dag = enumerate_model(model)
    direct = enumerate_words(model)
    for field in ("capacity", "classes", "representatives", "buckets"):
        if dag[field] != direct[field]:
            raise AssertionError("control source mismatch")
    cert = certify(model, n, dag)
    status = check(model, n, cert)
    truth = sorted(capacity_outcomes(dag["capacity"])[tuple(n)])
    if status["spectrum"] != truth:
        raise AssertionError("control subset mismatch")
    return {"name": name, "origin": "authored one-event source; outside primary suite",
            "model": model, "count_report": n, "capacity": dag["capacity"],
            "representatives": dag["representatives"], "certificate": cert,
            **compare_one(dag["capacity"], n, truth)}


def extra_controls():
    # A partial Hall prefix and a noncontiguous spectrum, with trace-derived cells.
    frontier = {"events": [{"kind": i, "value": i % 2, "context": 0,
                             "bucket": int(i >= 2)} for i in range(4)],
                "monitors": [{"op": "ever", "guard": {"field": "kind", "equals": i}}
                             for i in range(3)], "triggers": [0, 1, 2],
                "horizon": 1, "min_length": 1, "environment_locked": False, "report_modulus": 1}
    holes = {"events": [{"kind": kind, "value": 0, "context": 0, "bucket": bucket}
                         for kind, bucket in ((0, 0), (1, 1), (2, 0), (2, 2))],
             "monitors": [{"op": "ever", "guard": {"field": "kind", "equals": i}}
                          for i in range(2)], "triggers": [0, 1],
             "horizon": 1, "min_length": 1, "environment_locked": False, "report_modulus": 1}
    return [source_control("partial-prefix-Hall", frontier, [1, 1]),
            source_control("noncontiguous-spectrum", holes, [1, 1, 1])]


def comparison():
    models = unique_records(ROOT / "data/cases.jsonl", "model")
    counts = unique_records(ROOT / "data/reports.jsonl", "count_report")
    if set(models) != set(counts) or len(models) != 2448:
        raise ValueError("expected frozen 2448 input/report IDs")
    rows, seen, verdicts = [], set(), Counter()
    # Streaming decompression of known local JSON data; no archive execution.
    for path in sorted((ROOT / "results/campaign").glob("cases-*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                key = record["case_id"]
                if key in seen or key not in models:
                    raise ValueError("certificate ID mismatch")
                cert = record["certificate"]
                status = check(models[key], counts[key], cert)
                N, n = cert["semantics"]["capacity"], counts[key]
                result = compare_one(N, n, status["spectrum"])
                rows.append({"case_id": key, "classes": len(N[0]), "count_report": n,
                             "verdict": status["verdict"], **result})
                verdicts[status["verdict"]] += 1
                seen.add(key)
    if seen != set(models):
        raise ValueError("missing certificate")
    with (ROOT / "results/campaign/all_cases.csv").open(encoding="utf-8") as handle:
        csv_rows = {row["case_id"]: row for row in csv.DictReader(handle)}
    if set(csv_rows) != seen:
        raise ValueError("campaign row IDs mismatch")
    for row in rows:
        stored = csv_rows[row["case_id"]]
        if (stored["verdict"] != row["verdict"]
                or int(stored["count_threshold"]) != int(sum(row["count_report"]) >= row["classes"])
                or int(stored["full_possible"]) != int(row["classes"] in row["spectrum"])):
            raise AssertionError("stored campaign summary field mismatch")
    retained = json.loads((ROOT / "results/campaign/summary.json").read_text(encoding="utf-8"))
    if dict(verdicts) != retained["verdicts"]:
        raise AssertionError("stored verdict totals mismatch")
    controls = []
    for record in json.loads((ROOT / "results/tests/controls.json").read_text(encoding="utf-8"))["result"]:
        status = check(record["model"], record["report"], record["certificate"])
        N = record["certificate"]["semantics"]["capacity"]
        truth = sorted(capacity_outcomes(N)[tuple(record["report"])])
        if status["spectrum"] != truth:
            raise AssertionError("retained control mismatch")
        controls.append({"name": record["name"], "origin": "retained control; outside primary suite",
                         **compare_one(N, record["report"], truth)})
    controls.extend(extra_controls())
    by_verdict = {v: {"cases": verdicts[v],
                     "distinct_spectra": len({(r["classes"], tuple(r["spectrum"])) for r in rows if r["verdict"] == v})}
                  for v in sorted(verdicts)}
    summary = {"primary_cases": len(rows), "verdicts": dict(verdicts),
               "cardinality_complete_vs_matching_disagreements": sum(
                   int(sum(r["count_report"]) >= r["classes"]) != (r["classes"] in r["spectrum"]) for r in rows),
               "cardinality_spectrum_disagreement_cases": sum(r["cardinality_spectrum"] != r["spectrum"] for r in rows),
               "cardinality_extra_finite_branches": sum(r["cardinality_extra_finite_branches"] for r in rows),
               "cardinality_extra_complete_cases": sum(r["cardinality_extra_complete"] for r in rows),
               "catalogue_queries": 4 * len(rows),
               "cardinality_routing_disagreements": sum(r["cardinality_routing_disagreements"] for r in rows),
               "cardinality_catalogue_sufficiency_disagreements": sum(
                   r["cardinality_catalogue_sufficiency_disagreements"] for r in rows),
               "cardinality_next_candidate_disagreements": sum(
                   r["cardinality_next_candidate_disagreements"] for r in rows),
               "matching_spectrum_disagreements": 0, "circulation_spectrum_disagreements": 0,
               "by_verdict": by_verdict, "controls_outside_primary": len(controls)}
    return {"contract": "ordered source capacities and exact distinct-trace partition counts only",
            "task": "minimal possible-first-omission routing; catalogue sufficiency; least available candidate",
            "catalogue_policy": "empty, all classes, even class indices, first floor(k/2) classes; fixed without tuning",
            "hidden_allocation_used_by_decision": False, "summary": summary,
            "controls": controls, "primary_rows": rows,
            "limits": "diagnostic routing only; no closure, speedup, device, field prevalence or detector claim"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output must be new")
    result = comparison()
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result["summary"], indent=2))
