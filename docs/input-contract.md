# Exact source and report contract

## Typed source

An alphabet is an ordered list of 1--32 distinct event records. A record contains `kind` in 0..31, `value` and `context` in 0..1, and `bucket` in 0..7. Word order refers to indices in this declared list, not to a reordered dictionary or a platform API name. Guards compare one of kind, value, or context to a typed constant.

There are 1--12 primitive monitors: `ever(g)`, `last(g)`, `count_t(g)` with 1 <= t <= 24, and `before(g,h)`. The latter requires strictly different positions i < j; an initial event satisfying both guards does not suffice. A count is saturated at its threshold. Empty words make primitive outputs false, although a negated trigger formula can be true on the empty word.

There are 1--12 final trigger formulas. An integer refers to a monitor; nested lists encode not, binary and, or binary or, with depth at most 12. Minimum trace length is between zero and H, and H <= 24. When context locking is enabled, all events WITHIN ONE TRACE must have the same context. It does not require different traces in a report to share a context.

The observation bucket is (final event bucket, length modulo m), with 1 <= m <= 4; epsilon has final bucket -1. The legal universe is nonempty. Classes are the nonempty fibers of the final trigger vector, including the all-false vector when reachable. Their order is that of their least shortlex representative. This equivalence is not a future-behavior bisimulation.

## Admission and representation

The joint monitor/context/final-bucket state set is limited to 96; the layered DAG to 8,192 nodes; counts to 256 bits. Although the format checks an additional 2,048-class ceiling, the final vector is a function of the joint state and therefore at most 96 classes can occur. The campaign reaches at most 25 states, 16 classes, and 49-bit counts. Declared maxima are not observed workload dimensions. Checking rejects unsupported or oversized models; a rejection is not a coverage verdict.

Each supplied node is (state, positive word count, least word). The checker verifies the unique initial node, all legal outgoing transitions, exact incoming counts, minimal words, and absence of unsupported nodes. Buckets and class capacities are re-derived from those nodes. The capacity matrix is not trusted input from an analyzer.

## Reports

A report records the exact number of DISTINCT selected traces per bucket. For cell capacities N_yc, its compatible allocations are exactly integer matrices 0 <= X_yc <= N_yc with row sums n_y. Counts of repeat executions, lower bounds, overlapping buckets, shared-device constraints across a whole report, and unverified program abstractions are different contracts. The present theorem cannot silently be used for them.

## Primary input selection

The generator uses seed 9142026, fixed family order, and 480 indices per family. Balanced instances use event-occurrence monitors; rare-event instances use thresholds; compound instances combine Boolean outputs; temporal instances use strict order and final-event observations; environment instances lock a binary context per trace. Deterministic variations change alphabet ordering, Boolean polarity, bucket merging, trace horizon, minimum length, and length residue. The exact serialized inputs are authoritative, and reproduction does not regenerate them.

The six report modes are empty, one trace per class, one class omitted from a one-per-class selection, census, one trace per bucket, and all traces except one class. A compact allocation X denotes selecting the first X_yc shortlex tokens in each cell, not executing a device or analyzer. Every primary result includes this allocation so it can be checked against the hidden-outcome spectrum.

The 48 fixtures are authored from the same finite operators. Their ten motivation labels (time, location, sms, network, build, camera, addition, music, is_screen_on, is_screen_off) follow vocabulary in TriggerZoo, arXiv:2203.04448v1. There is no extraction from the released applications, no faithful Android schema implementation, and no separate empirical independence implied by these labels. No authenticated application access occurred.

The checker receives the expected count vector separately from the certificate and requires equality after validating both. Primary frozen vectors are in `data/reports.jsonl`; source models are in `data/cases.jsonl`. These inputs were authored for the experiment, not collected from a device.

## AndroLog-format interoperability adapter

`src/androlog_adapter.py` is a fail-closed format bridge, not an Android analyzer. It recognizes the public raw-probe labels `STATEMENT`, `METHOD`, `CLASS`, `ACTIVITY`, `SERVICE`, `BROADCASTRECEIVER`, and `CONTENTPROVIDER`. One regular non-symlink UTF-8 text file denotes one bounded execution session. A caller supplies an exact, injective JSON map from normalized probe keys to event indices in the declared finite model. The adapter preserves order and repeated probes inside a session, deduplicates only identical complete normalized event traces before distinct-trace counting, and rejects unknown probes, unsupported labels, malformed identifier-bearing lines, NULs, invalid model/map schemas, undeclared events, over-horizon traces, and context-lock violations. Session and configuration files are capped at 4 MiB; a directory is capped at 4,096 entries and 64 MiB in aggregate. File opening uses no-follow and descriptor `fstat` checks and adds nonblocking open on supported POSIX systems, so no-writer FIFOs are rejected as nonregular inputs rather than blocking.

For statements, metadata after the first pipe is excluded from the probe identity, matching the public AndroLog parser's statement treatment. Other probe payloads are retained after surrounding whitespace is removed, and the type assignment is searched only after the declared log identifier. The adapter validates model syntax and probe-map key normalization, value type/range, and injectivity; this syntactic validation does not establish that a probe denotes the claimed event. The adapter then evaluates each distinct session in the declared source model, derives the exact bucket-count report and class allocation, produces the ordinary certificate, and invokes the separate checker. It does not establish that a log came from AndroLog, authenticate logcat, instrument an APK, infer source-level trigger semantics, or validate semantic faithfulness of the user-supplied map. Those provenance and abstraction obligations remain outside the theorem.

The shipped `data/androlog-format-fixture/` contains authored benign text only.  It exists to test syntax-to-contract interoperability and all seven public label kinds; it is not a captured device trace or a TriggerZoo application.  Run the complete fixture conversion with:

```sh
python -m src.androlog_adapter \
  --model data/androlog-format-fixture/model.json \
  --probe-map data/androlog-format-fixture/probe-map.json \
  --sessions data/androlog-format-fixture/sessions \
  --log-identifier MY_SUPER_LOG \
  --output /tmp/androlog-report.json
```

The output path must not already exist.  The result includes the adapted report, exact allocation, certificate, checker decision, input filenames, and an explicit statement that authentication was not established.

## Overlapping views are a different input language

A trace must map to one and only one bucket in the admitted report.  Exact counts over arbitrary overlapping views are rejected rather than reinterpreted as rows.  `docs/proofs.md` proves that consistency for such unrestricted views is NP-complete even when all counts are one and each token belongs to exactly three views.  A caller needing overlapping telemetry must either disclose a disjoint refinement with exact distinct-trace counts or use a different checker and theorem.
