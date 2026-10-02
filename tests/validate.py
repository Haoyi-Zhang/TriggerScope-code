"""Finite validation suite with direct exhaustive oracles and benign mutations."""
from __future__ import annotations
import argparse,copy,itertools,json,os,random,resource,subprocess,sys,tempfile,time
from pathlib import Path
from src.producer import allocation_witness,enumerate_model,certify,matching_prefix,spectrum
from src.checker import check,InvalidCertificate
from src.oracle import enumerate_words,capacity_outcomes
from src.baseline import exact_spectrum
from src.generate import cases,report_for
from src.overlap_boundary import (compatible_selections, enumerate_six_element_families,
    x3c_exact_covers, x3c_to_overlapping_report)
import src.androlog_adapter as androlog_adapter
from src.androlog_adapter import InvalidLog, adapt_directory, adapt_sessions, parse_session

def controls():
    hall={"events":[{"kind":i,"value":i%2,"context":0,"bucket":int(i>=3)} for i in range(6)],
          "monitors":[{"op":"ever","guard":{"field":"kind","equals":i}} for i in range(3)],
          "triggers":[0,1,2],"horizon":1,"min_length":1,"environment_locked":False,"report_modulus":1}
    amb={"events":[{"kind":i,"value":i%2,"context":0,"bucket":i//2} for i in range(4)],
         "monitors":[{"op":"last","guard":{"field":"value","equals":1}}],
         "triggers":[0],"horizon":1,"min_length":1,"environment_locked":False,"report_modulus":1}
    return [("hall-bottleneck",hall,[2,2],[[1,1,1,0],[0,0,0,3]],[0,1,2]),
            ("indeterminate-report",amb,[1,1],[[1,1],[1,1]],[0,1,2])]

def capacity_suite():
    """Exhaust both 2x3 and 3x2 capacity shapes with cells in {0,1,2}.

    The transposed-shape companion prevents a test suite that only exercises
    more classes than buckets from silently missing row/class asymmetries.
    Every theorem outcome is also materialized as an allocation witness and
    checked against the direct labelled-token oracle.
    """
    totals={"matrices":0,"count_reports":0,"concrete_subsets":0,"witnesses_checked":0}
    shapes=[]
    for buckets,classes in ((2,3),(3,2)):
        matrices=reports=subsets=witnesses=0
        for values in itertools.product(range(3),repeat=buckets*classes):
            N=[list(values[y*classes:(y+1)*classes]) for y in range(buckets)]
            if any(sum(N[y][c] for y in range(buckets))==0 for c in range(classes)):
                continue
            truth=capacity_outcomes(N); matrices+=1; subsets+=2**sum(values)
            for n_tuple,outcomes in truth.items():
                n=list(n_tuple); expected=sorted(outcomes)
                prefix=matching_prefix(N,n)["prefix"]
                assert spectrum(N,n,prefix)==expected
                assert exact_spectrum(N,n)==expected
                for outcome in expected:
                    allocation=allocation_witness(N,n,outcome)
                    assert len(allocation)==buckets
                    assert all(len(allocation[y])==classes for y in range(buckets))
                    assert all(sum(allocation[y])==n[y] for y in range(buckets))
                    assert all(type(allocation[y][c]) is int and 0<=allocation[y][c]<=N[y][c]
                               for y in range(buckets) for c in range(classes))
                    covered=[sum(allocation[y][c] for y in range(buckets)) for c in range(classes)]
                    actual=next((c for c,value in enumerate(covered) if value==0),classes)
                    assert actual==outcome
                    witnesses+=1
                reports+=1
        shape={"buckets":buckets,"classes":classes,"cell_values":[0,1,2],
               "matrices":matrices,"count_reports":reports,
               "concrete_subsets":subsets,"witnesses_checked":witnesses}
        shapes.append(shape)
        for key in totals: totals[key]+=shape[key]
    return {**totals,"shapes":shapes,"disagreements":0,"witness_disagreements":0}

def tiny_models():
    g=lambda x:{"field":"kind","equals":x}
    primitive=[]
    for x in (0,1):
        for op in ("ever","last"): primitive.append({"op":op,"guard":g(x)})
        for t in (1,2): primitive.append({"op":"count","guard":g(x),"threshold":t})
        for y in (0,1): primitive.append({"op":"before","guard":g(x),"then":g(y)})
    grammars=[([p],[f]) for p in primitive for f in (0,["not",0])]
    for a in primitive:
        for b in primitive:
            for outputs in ([0,1],[["and",0,1]],[["or",0,1]],[["and",0,["not",1]]],[["not",["or",0,1]]]):
                grammars.append(([a,b],outputs))
    for M,F in grammars:
        for H in range(4):
            for low in (range(2) if H else (0,)):
                for env in (False,True):
                    for mod in (1,2):
                        yield {"events":[{"kind":i,"value":i,"context":i,"bucket":i} for i in (0,1)],
                               "monitors":M,"triggers":F,"horizon":H,"min_length":low,
                               "environment_locked":env,"report_modulus":mod}

def source_suite():
    count=words=nodes=steps=0
    for m in tiny_models():
        oracle=enumerate_words(m); dag=enumerate_model(m)
        for key in ("classes","representatives","buckets","capacity"): assert oracle[key]==dag[key],key
        n=[sum(row)//2 for row in dag["capacity"]]
        status=check(m,n,certify(m,n,dag))
        count+=1;words+=len(oracle["items"]); nodes+=status["nodes"];steps+=status["checker_steps"]
    return {"tiny_models":count,"legal_words_evaluated":words,"nodes_replayed":nodes,"checker_steps":steps,"disagreements":0,
            "scope":"12 primitives; each single with identity/negation; every ordered pair with five listed output forms; H=0..3; all valid low=0/1; context lock both; modulus 1/2; fixed binary alphabet"}

def mutation_suite():
    records=[]; accepted_controls=0; steps=nodes=0; rejected_steps=0
    selected=[c for c in cases() if c["origin"]=="generated" and c["index"] in (1,2,3,4,5,30,31,32,33,34,35)]
    for case in selected:
        m=case["model"]; d=enumerate_model(m); n,_,_=report_for(d["capacity"],case); original=certify(m,n,d)
        def trial(name,edit,edit_model=False):
            nonlocal rejected_steps
            meter={}
            c=copy.deepcopy(original); model=copy.deepcopy(m)
            edit(model if edit_model else c)
            try: check(model,n,c,meter=meter)
            except (InvalidCertificate,KeyError,TypeError,IndexError):
                rejected_steps+=meter.get("checker_steps",0)
                records.append({"case_id":case["case_id"],"mutation":name,"rejected":True,"checker_steps":meter.get("checker_steps",0)})
            else: raise AssertionError("accepted corrupted certificate: "+name+" "+case["case_id"])
        trial("count-plus-one",lambda c:c["semantics"]["layers"][1][0].__setitem__(1,c["semantics"]["layers"][1][0][1]+1))
        trial("missing-node",lambda c:c["semantics"]["layers"][-1].pop())
        trial("duplicate-node",lambda c:c["semantics"]["layers"][-1].append(copy.deepcopy(c["semantics"]["layers"][-1][0])))
        trial("predicate-confusion",lambda model:model["monitors"][0]["guard"].update({"field":"kind","equals":31}),True)
        trial("capacity-plus-one",lambda c:c["semantics"]["capacity"][0].__setitem__(0,c["semantics"]["capacity"][0][0]+1))
        trial("wrong-representative",lambda c:c["semantics"]["representatives"][0].append(0))
        if len(d["classes"])>1: trial("class-order",lambda c:c["semantics"]["classes"].reverse())
        k=len(d["classes"])
        trial("wrong-prefix",lambda c:c["prefix_proof"].__setitem__("prefix",(c["prefix_proof"]["prefix"]+1)%(k+1)))
        if original["prefix_proof"]["prefix"]<k: trial("missing-Hall-cut",lambda c:c["prefix_proof"].__setitem__("cut",[]))
        if original["prefix_proof"]["prefix"]>=2: trial("duplicate-matched-class",lambda c:c["prefix_proof"]["matching"][1].__setitem__(0,c["prefix_proof"]["matching"][0][0]))
        trial("wrong-spectrum",lambda c:c.__setitem__("spectrum",[0] if c["spectrum"]==[k] else [k]))
        trial("inconsistent-report",lambda c:c["count_report"].__setitem__(0,-1))
        trial("wrong-verdict",lambda c:c.__setitem__("verdict","forced-incomplete" if c["verdict"]!="forced-incomplete" else "forced-complete"))
        trial("wrong-allocation",lambda c:c["witnesses"][0]["allocation"][0].__setitem__(0,c["witnesses"][0]["allocation"][0][0]+1))
        control=copy.deepcopy(original)
        for L in control["semantics"]["layers"]: L.reverse()
        control["prefix_proof"]["matching"].reverse()
        s=check(m,n,control); accepted_controls+=1;nodes+=s["nodes"];steps+=s["checker_steps"]
    return {"rejected_mutations":len(records),"accepted_equivalent_controls":accepted_controls,"records":records,"valid_control_nodes":nodes,"valid_control_steps":steps,"rejected_checker_steps":rejected_steps}

def control_suite():
    result=[]
    for name,m,n,N,expected in controls():
        dag=enumerate_model(m); assert dag["capacity"]==N
        oracle=enumerate_words(m); assert oracle["capacity"]==N
        cert=certify(m,n,dag);status=check(m,n,cert)
        assert status["spectrum"]==expected
        assert exact_spectrum(N,n)==expected
        concrete=capacity_outcomes(N); assert sorted(concrete[tuple(n)])==expected
        result.append({"name":name,"model":m,"report":n,"certificate":cert,"check":status,
                       "compatible_subset_count":sum(1 for selection in itertools.product((0,1),repeat=sum(map(sum,N))) if tuple(sum(selection[sum(map(sum,N[:y])):sum(map(sum,N[:y+1]))]) for y in range(len(N)))==tuple(n))})
    return result

def binding_suite():
    records=[]
    for name,m,n,_,_ in controls():
        dag=enumerate_model(m)
        altered=[0]*len(n)
        cert=certify(m,altered,dag)
        accepted=check(m,altered,cert)
        meter={}
        try:
            check(m,n,cert,meter=meter)
        except InvalidCertificate as error:
            assert str(error)=="report binding"
        else:
            raise AssertionError("different valid report accepted against declared counts")
        records.append({"control":name,"expected_counts":n,"certificate_counts":altered,
                        "valid_for_own_report":True,"rejected_for_declared_report":True,
                        "own_report_checker_steps":accepted["checker_steps"],
                        "rejected_checker_steps":meter["checker_steps"],"nodes":accepted["nodes"]})
    return records


def _independent_overlap_readback(record):
    """Rebuild one serialized overlap record without normalize_x3c.

    Selection indices are interpreted only against the saved canonical token
    list.  This catches the prior class of errors where original input order was
    displayed beside canonical-index witnesses.
    """
    elements=record["elements"];tokens=record["tokens"];counts=record["counts"]
    input_elements=record["input_elements"]
    assert elements==sorted(elements) and len(elements)==len(set(elements))
    assert sorted(input_elements)==elements
    unordered_input=(input_elements!=elements)
    canonical=[tuple(token) for token in tokens]
    assert all(len(token)==3 and len(set(token))==3 and tuple(sorted(token))==token for token in canonical)
    assert canonical==sorted(canonical) and len(canonical)==len(set(canonical))
    assert all(element in set(elements) for token in canonical for element in token)
    rebuilt_views=[[index for index,token in enumerate(canonical) if element in token] for element in elements]
    assert rebuilt_views==record["views"] and len(counts)==len(elements)
    rebuilt=[]
    for bits in itertools.product((0,1),repeat=len(canonical)):
        if all(sum(bits[index] for index in view)==count for view,count in zip(rebuilt_views,counts)):
            rebuilt.append([index for index,bit in enumerate(bits) if bit])
    rebuilt=sorted(rebuilt)
    assert rebuilt==record["compatible_selections"]
    witness_counts=[]
    for selection in rebuilt:
        per_element=[sum(element in canonical[index] for index in selection) for element in elements]
        assert per_element==counts
        witness_counts.append(per_element)
    raw=[tuple(token) for token in record["input_triples"]]
    independently_canonicalized=[tuple(sorted(token)) for token in raw]
    lookup={token:index for index,token in enumerate(canonical)}
    input_to_canonical=[lookup[token] for token in independently_canonicalized]
    assert input_to_canonical==record["input_to_canonical"]
    inverse=[0]*len(canonical)
    for input_index,canonical_index in enumerate(input_to_canonical): inverse[canonical_index]=input_index
    assert inverse==record["canonical_to_input"]
    assert sorted(independently_canonicalized)==canonical
    return {"witness_counts":witness_counts,"unordered_input":unordered_input}

def overlap_suite():
    """Exhaustive validation of the X3C-to-overlapping-count reduction."""
    elements=tuple(range(6)); families=feasible=infeasible=selections=0
    max_tokens=max_views=positive_witnesses_rechecked=serialized_families_rechecked=0
    for triples in enumerate_six_element_families(4):
        report=x3c_to_overlapping_report(elements,triples)
        # Reconstruct incidence directly from canonical saved tokens.
        rebuilt_views=[[index for index,token in enumerate(report["tokens"]) if element in token]
                       for element in report["elements"]]
        assert report["elements"]==sorted(report["elements"])
        assert report["tokens"]==sorted(report["tokens"])
        assert rebuilt_views==report["views"]
        # Keep the locally admissible domain: every count-one view has capacity.
        if any(not view for view in report["views"]):
            continue
        by_views=compatible_selections(report["views"],report["counts"],len(report["tokens"]))
        by_x3c=x3c_exact_covers(elements,triples)
        assert by_views==by_x3c
        assert all(sum(token in view for view in report["views"])==3 for token in range(len(report["tokens"])))
        record={"input_elements":list(elements),"input_triples":[list(x) for x in triples],
                "elements":report["elements"],"tokens":report["tokens"],
                "input_to_canonical":report["input_to_canonical"],
                "canonical_to_input":report["canonical_to_input"],
                "views":report["views"],"counts":report["counts"],
                "compatible_selections":[list(x) for x in by_views]}
        # The retained JSON representation is read without normalize_x3c;
        # every compatible positive witness is checked element by element.
        readback=_independent_overlap_readback(json.loads(json.dumps(record)))
        assert readback["unordered_input"] is False
        positive_witnesses_rechecked+=len(readback["witness_counts"])
        serialized_families_rechecked+=1
        families+=1;selections+=len(by_views);max_tokens=max(max_tokens,len(triples));max_views=max(max_views,len(report["views"]))
        if by_views: feasible+=1
        else: infeasible+=1
    # Deliberately unordered elements, token order, and within-token order.
    unordered_elements=(5,3,1,4,2,0)
    positive=((5,4,3),(2,0,1),(4,3,0))
    negative=((2,1,0),(4,3,0),(5,1,3))
    controls=[];readback_witnesses=0
    for name,triples,want in (("exact-cover-unordered-input",positive,True),
                              ("locally-valid-no-cover-unordered-input",negative,False)):
        report=x3c_to_overlapping_report(unordered_elements,triples)
        choices=compatible_selections(report["views"],report["counts"],len(report["tokens"]))
        assert bool(choices) is want and choices==x3c_exact_covers(unordered_elements,triples)
        control={"name":name,"input_elements":list(unordered_elements),
                 "input_triples":[list(x) for x in triples],
                 "elements":report["elements"],"tokens":report["tokens"],
                 "input_to_canonical":report["input_to_canonical"],
                 "canonical_to_input":report["canonical_to_input"],
                 "views":report["views"],"counts":report["counts"],
                 "compatible_selections":[list(x) for x in choices]}
        # JSON round-trip is the same interpretation used for retained results.
        readback=_independent_overlap_readback(json.loads(json.dumps(control)))
        assert readback["unordered_input"] is True
        readback_witnesses+=len(readback["witness_counts"])
        controls.append(control)
    return {"ground_elements":6,"candidate_triples":20,"family_size_limit":4,
            "locally_admissible_families":families,"serialized_families_rechecked":serialized_families_rechecked,
            "feasible_families":feasible,
            "infeasible_families":infeasible,"compatible_selections":selections,
            "positive_witnesses_rechecked":positive_witnesses_rechecked,
            "serialized_control_witnesses_rechecked":readback_witnesses,
            "max_tokens":max_tokens,"views_per_instance":max_views,"disagreements":0,
            "token_view_degree":3,"canonical_serialization":True,
            "unordered_input_checked":True,"controls":controls}



def stress_suite():
    """Deterministic larger-dimension comparison with circulation and witnesses."""
    seed=9142026; rng=random.Random(seed); total_cases=20000
    witnesses=complete=ambiguous=incomplete=0; max_tokens=0; max_outcomes=0
    for index in range(total_cases):
        buckets=rng.randint(1,5); classes=rng.randint(1,8)
        N=[[rng.randint(0,5) for _ in range(classes)] for _ in range(buckets)]
        for c in range(classes):
            if sum(N[y][c] for y in range(buckets))==0:
                N[rng.randrange(buckets)][c]=1
        report=[]
        for row in N:
            total=sum(row); mode=index%5
            if mode==0: count=0
            elif mode==1: count=total
            elif mode==2: count=total//2
            elif mode==3: count=min(total,1)
            else: count=rng.randint(0,total)
            report.append(count)
        prefix=matching_prefix(N,report)["prefix"]
        observed=spectrum(N,report,prefix)
        expected=exact_spectrum(N,report)
        assert observed==expected
        max_tokens=max(max_tokens,sum(map(sum,N)));max_outcomes=max(max_outcomes,len(observed))
        if observed==[classes]: complete+=1
        elif classes in observed: ambiguous+=1
        else: incomplete+=1
        for outcome in observed:
            allocation=allocation_witness(N,report,outcome)
            assert [sum(row) for row in allocation]==report
            assert all(0<=allocation[y][c]<=N[y][c] for y in range(buckets) for c in range(classes))
            covered=[sum(allocation[y][c] for y in range(buckets)) for c in range(classes)]
            actual=next((c for c,value in enumerate(covered) if value==0),classes)
            assert actual==outcome
            witnesses+=1
    return {"seed":seed,"cases":total_cases,"bucket_range":[1,5],"class_range":[1,8],
            "cell_capacity_range":[0,5],"report_modes":["zero","full","half","one","uniform-random"],
            "witnesses_checked":witnesses,"max_total_tokens":max_tokens,"max_spectrum_size":max_outcomes,
            "forced_complete":complete,"ambiguous":ambiguous,"forced_incomplete":incomplete,
            "circulation_disagreements":0,"witness_disagreements":0}

def androlog_suite():
    """Format bridge using only authored, benign AndroLog-style text logs."""
    root=Path(__file__).resolve().parents[1]
    fixture=root/"data"/"androlog-format-fixture"
    model=json.loads((fixture/"model.json").read_text())
    probe_map=json.loads((fixture/"probe-map.json").read_text())
    sessions=fixture/"sessions"
    result=adapt_directory(model,sessions,"MY_SUPER_LOG",probe_map)
    assert result["input_sessions"]==7
    assert result["distinct_traces"]==6
    assert result["duplicate_sessions_removed"]==1
    # The duplicate control is intentionally byte-distinct: only its complete
    # normalized event trace is equal to session-01. This prevents the test
    # from accidentally validating file-byte deduplication instead.
    source_session=sessions/"session-01.log"
    duplicate_session=sessions/"session-03-duplicate.log"
    assert source_session.read_bytes()!=duplicate_session.read_bytes()
    source_trace=parse_session(source_session.read_text(encoding="utf-8").splitlines(keepends=True),"MY_SUPER_LOG",probe_map)
    duplicate_trace=parse_session(duplicate_session.read_text(encoding="utf-8").splitlines(keepends=True),"MY_SUPER_LOG",probe_map)
    assert source_trace==duplicate_trace
    dag=enumerate_model(model)
    cert=certify(model,result["count_report"],dag)
    status=check(model,result["count_report"],cert)
    actual=next((c for c in range(len(dag["classes"])) if not any(row[c] for row in result["allocation"])),len(dag["classes"]))
    assert actual in cert["spectrum"]
    # Probe normalization and fail-closed parsing controls.
    statement_key="STATEMENT=<com.example.MainActivity: void arm()>:$r0 = 1"
    assert parse_session(["I/MY_SUPER_LOG: "+statement_key+"|unit-index=99\n"],"MY_SUPER_LOG",probe_map)==(3,)
    # An unrelated assignment before the identifier must not capture the probe type.
    anchored="METHOD=outside I/MY_SUPER_LOG: METHOD=com.example.MainActivity.onCreate()\n"
    assert parse_session([anchored],"MY_SUPER_LOG",probe_map)==(0,)
    rejected=[]
    for name,lines in (
        ("unknown-probe",["I/MY_SUPER_LOG: METHOD=com.example.Unknown.x()\n"]),
        ("unsupported-type",["I/MY_SUPER_LOG: FIELD=com.example.X.y\n"]),
        ("malformed-identifier-line",["I/MY_SUPER_LOG: no assignment\n"]),
        ("nul-line",["I/MY_SUPER_LOG: CLASS=x\x00y\n"]),
    ):
        try: parse_session(lines,"MY_SUPER_LOG",probe_map)
        except InvalidLog: rejected.append(name)
        else: raise AssertionError("accepted malformed AndroLog fixture: "+name)
    try: parse_session([anchored],"BAD\nIDENTIFIER",probe_map)
    except InvalidLog: rejected.append("invalid-log-identifier")
    else: raise AssertionError("accepted invalid log identifier")
    try: adapt_sessions(model,[(0,1,2,3,4)])
    except InvalidLog: rejected.append("over-horizon")
    else: raise AssertionError("accepted over-horizon session")

    valid_line="I/MY_SUPER_LOG: METHOD=com.example.MainActivity.onCreate()\n"
    def reject_directory(name,prepare,probe_override=None,model_override=None):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);prepare(directory)
            try: adapt_directory(model if model_override is None else model_override,directory,"MY_SUPER_LOG",probe_map if probe_override is None else probe_override)
            except InvalidLog: rejected.append(name)
            else: raise AssertionError("accepted invalid session directory: "+name)
    reject_directory("empty-directory",lambda directory:None)
    def oversized(directory):
        with (directory/"oversized.log").open("wb") as handle: handle.truncate(androlog_adapter.MAX_SESSION_BYTES+1)
    reject_directory("oversized-session-file",oversized)
    def write_sized_valid_session(path,size):
        encoded=valid_line.encode("utf-8")
        if size<len(encoded)+1: raise AssertionError("test size too small")
        filler_size=size-len(encoded)
        payload=(b"#"*(filler_size-1)+b"\n")+encoded
        assert len(payload)==size and b"\x00" not in payload
        path.write_bytes(payload)
    aggregate_control={}
    with tempfile.TemporaryDirectory() as temporary:
        directory=Path(temporary)
        per_file_limit=256;aggregate_limit=400
        write_sized_valid_session(directory/"a.log",200)
        write_sized_valid_session(directory/"b.log",200)
        exact=adapt_directory(model,directory,"MY_SUPER_LOG",probe_map,
                              max_session_bytes=per_file_limit,max_session_files=2,
                              max_total_session_bytes=aggregate_limit)
        assert exact["input_bytes"]==aggregate_limit
        write_sized_valid_session(directory/"b.log",201)
        for path,expected_size in ((directory/"a.log",200),(directory/"b.log",201)):
            trace,size=androlog_adapter._parse_session_file_with_size(
                path,"MY_SUPER_LOG",probe_map,max_bytes=per_file_limit)
            assert trace==(0,) and size==expected_size
        raised=adapt_directory(model,directory,"MY_SUPER_LOG",probe_map,
                               max_session_bytes=per_file_limit,max_session_files=2,
                               max_total_session_bytes=aggregate_limit+1)
        assert raised["input_bytes"]==aggregate_limit+1
        expected_error=f"session directory aggregate input exceeds {aggregate_limit} bytes"
        try:
            adapt_directory(model,directory,"MY_SUPER_LOG",probe_map,
                            max_session_bytes=per_file_limit,max_session_files=2,
                            max_total_session_bytes=aggregate_limit)
        except InvalidLog as error:
            assert str(error)==expected_error
            rejected.append("aggregate-byte-limit")
        else:
            raise AssertionError("aggregate guard removal was not detected")
        aggregate_control={"per_file_limit_bytes":per_file_limit,
                           "aggregate_limit_bytes":aggregate_limit,
                           "exact_limit_file_sizes":[200,200],
                           "over_limit_file_sizes":[200,201],
                           "exact_limit_accepted":True,"over_one_byte_rejected":True,
                           "same_input_accepted_at_raised_limit":True,
                           "individual_files_parse_as_valid_traces":True,
                           "aggregate_error":expected_error,
                           "aggregate_guard_removal_would_fail_test":True}
    def symlink_entry(directory):
        target=directory/"target.log";target.write_text(valid_line,encoding="utf-8")
        os.symlink(target.name,directory/"link.log")
    reject_directory("symlink-entry",symlink_entry)
    def nested_entry(directory):
        (directory/"nested").mkdir()
    reject_directory("non-regular-entry",nested_entry)
    def excessive_entries(directory):
        for index in range(androlog_adapter.MAX_SESSION_FILES+1): (directory/f"{index:04d}.log").touch()
    reject_directory("excessive-file-count",excessive_entries)
    reject_directory("invalid-utf8",lambda directory:(directory/"bad.log").write_bytes(b"\xff"))
    reject_directory("non-injective-probe-map",lambda directory:(directory/"ok.log").write_text(valid_line,encoding="utf-8"),
                     {**probe_map,"METHOD=com.example.Other()":0})
    reject_directory("undeclared-event-map",lambda directory:(directory/"ok.log").write_text(valid_line,encoding="utf-8"),
                     {**probe_map,"METHOD=com.example.Other()":len(model["events"])})
    reject_directory("noninteger-probe-map-value",lambda directory:(directory/"ok.log").write_text(valid_line,encoding="utf-8"),
                     {**probe_map,"METHOD=com.example.Other()":True})
    reject_directory("unnormalized-probe-map-key",lambda directory:(directory/"ok.log").write_text(valid_line,encoding="utf-8"),
                     {**probe_map,"STATEMENT=<x>|metadata":7})
    bad_model=copy.deepcopy(model);bad_model.pop("events")
    reject_directory("invalid-model-schema",lambda directory:(directory/"ok.log").write_text(valid_line,encoding="utf-8"),
                     model_override=bad_model)

    def reject_config(name,prepare):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"config.json";prepare(path)
            try: androlog_adapter._load_json_object(path,"test configuration")
            except InvalidLog: rejected.append(name)
            else: raise AssertionError("accepted invalid adapter configuration: "+name)
    def oversized_config(path):
        with path.open("wb") as handle: handle.truncate(androlog_adapter.MAX_CONFIG_BYTES+1)
    reject_config("oversized-config-file",oversized_config)
    def symlink_config(path):
        target=path.with_name("target.json");target.write_text("{}",encoding="utf-8")
        os.symlink(target.name,path)
    reject_config("symlink-config-file",symlink_config)
    reject_config("nonobject-config",lambda path:path.write_text("[]",encoding="utf-8"))
    reject_config("invalid-json-config",lambda path:path.write_text("{",encoding="utf-8"))

    fifo_controls={"supported":False,"subprocess_timeout_seconds":2}
    if os.name=="posix" and hasattr(os,"mkfifo") and hasattr(os,"O_NONBLOCK"):
        def fifo_subprocess(mode):
            with tempfile.TemporaryDirectory() as temporary:
                base=Path(temporary);session_dir=base/"sessions";session_dir.mkdir()
                fifo_path=(session_dir/"session.fifo") if mode=="session" else (base/"config.fifo")
                os.mkfifo(fifo_path)
                script='''
from pathlib import Path
import json,sys
from src.androlog_adapter import InvalidLog,adapt_directory,_load_json_object
root=Path(sys.argv[1]);base=Path(sys.argv[2]);mode=sys.argv[3]
fixture=root/"data"/"androlog-format-fixture"
model=json.loads((fixture/"model.json").read_text())
probe=json.loads((fixture/"probe-map.json").read_text())
fd_dir=Path("/proc/self/fd")
before=len(list(fd_dir.iterdir())) if fd_dir.is_dir() else None
try:
    if mode=="session":
        adapt_directory(model,base/"sessions","MY_SUPER_LOG",probe)
    else:
        _load_json_object(base/"config.fifo","test configuration")
except InvalidLog as error:
    after=len(list(fd_dir.iterdir())) if fd_dir.is_dir() else None
    unchanged=(before is None or after==before)
    print(json.dumps({"status":"InvalidLog","message":str(error),
                      "descriptor_count_unchanged":unchanged},sort_keys=True))
    raise SystemExit(0 if unchanged else 4)
raise SystemExit(3)
'''
                try:
                    completed=subprocess.run([sys.executable,"-c",script,str(root),str(base),mode],
                                             cwd=root,capture_output=True,text=True,timeout=2,check=False)
                except subprocess.TimeoutExpired as error:
                    raise AssertionError(mode+" FIFO path blocked until external timeout") from error
                if completed.returncode!=0:
                    raise AssertionError(mode+" FIFO path did not reject with InvalidLog: "+completed.stderr)
                payload=json.loads(completed.stdout)
                assert payload["status"]=="InvalidLog" and payload["descriptor_count_unchanged"] is True
                expected_label="session file" if mode=="session" else "test configuration"
                assert payload["message"]==expected_label+" must be a regular, non-symlink file"
                return payload
        fifo_controls={"supported":True,"subprocess_timeout_seconds":2,
                       "session_path":fifo_subprocess("session"),
                       "configuration_path":fifo_subprocess("configuration"),
                       "passed_by_explicit_invalidlog_not_timeout":True}
    # A changed distinct session changes the declared report; the old proof is bound to the old report.
    changed=[tuple(x) for x in result["distinct_words"]]
    changed.append((1,))
    altered=adapt_sessions(model,changed)
    assert altered["count_report"]!=result["count_report"]
    meter={}
    try: check(model,altered["count_report"],cert,meter=meter)
    except InvalidCertificate as error: assert str(error)=="report binding"
    else: raise AssertionError("certificate accepted for changed adapter report")
    assert len(rejected)==22, rejected
    return {"upstream_format":"AndroLog raw probe labels","fixture_origin":"authored synthetic text; no APK/device execution",
            "input_sessions":result["input_sessions"],"distinct_traces":result["distinct_traces"],
            "duplicate_sessions_removed":result["duplicate_sessions_removed"],
            "count_report":result["count_report"],"classes":len(result["classes"]),
            "spectrum":cert["spectrum"],"verdict":cert["verdict"],"actual_outcome":actual,
            "probe_types":list(("STATEMENT","METHOD","CLASS","ACTIVITY","SERVICE","BROADCASTRECEIVER","CONTENTPROVIDER")),
            "rejected_controls":rejected,"portable_rejected_control_count":len(rejected),
            "aggregate_limit_control":aggregate_control,"fifo_path_controls":fifo_controls,
            "accepted_anchoring_control":True,"changed_report_binding_rejected":True,
            "byte_distinct_duplicate_files":True,"normalized_duplicate_trace_equal":True,
            "checker_steps":status["checker_steps"],"nodes":status["nodes"],
            "changed_report_rejected_steps":meter.get("checker_steps",0)}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--part",choices=("capacity","source","mutations","controls","binding","overlap","stress","androlog"),required=True);p.add_argument("--output",type=Path,default=Path("reproduction-tests"));a=p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3)); start=time.process_time();wall=time.perf_counter()
    value={"capacity":capacity_suite,"source":source_suite,"mutations":mutation_suite,"controls":control_suite,"binding":binding_suite,"overlap":overlap_suite,"stress":stress_suite,"androlog":androlog_suite}[a.part]()
    result={"part":a.part,"result":value,"cpu_seconds":time.process_time()-start,"wall_seconds":time.perf_counter()-wall,"peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"workers":1}
    a.output.mkdir(parents=True,exist_ok=True);(a.output/(a.part+".json")).write_text(json.dumps(result,indent=2)+"\n")
    small={k:v for k,v in result.items() if k!="result"};small["summary"]={k:v for k,v in value.items() if k!="records"} if type(value)is dict else "2 source-grounded checks"
    print(json.dumps(small))
