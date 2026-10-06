# Trigger-language coverage certificates

This standalone artifact implements and validates the bounded evidence contract studied in *Certifying Trigger-Coverage Reports: Omission Spectra and a Tractability Boundary*.

## Result in one paragraph

For a finite ordered trigger language, exact distinct-trace counts in disjoint observation buckets generally do not identify the analyzer's actual covered classes. The artifact computes the exact **omission spectrum**: every possible earliest absent semantic class over all compatible selections, plus complete coverage when possible. A producer emits a source certificate, class/capacity summary, prefix matching/Hall obstruction, outcome spectrum, and compatible allocation witnesses. A separately implemented checker replays the source semantics and validates those obligations without importing the producer, generator, direct oracle, or circulation baseline. A separate theorem and executable reduction show that allowing arbitrary overlapping exact-count views makes even report consistency NP-complete.

## Requirements

- Python 3.10 or newer
- A Unix-like system providing the standard-library `resource` module
- One CPU worker
- No third-party Python packages, network access, GPU, model API, APK, emulator, or private data

All commands below are offline. Output directories must not already exist.

## Complete reproduction

From this repository root:

```sh
python reproduce.py --output /tmp/trigger-coverage-reproduction
```

The driver sequentially:

1. replays the immutable shipped certificate packet against frozen external count reports;
2. regenerates all 2,448 primary cases in bounded chunks;
3. compares the complete campaign column schema, every deterministic result row, and every deterministic aggregate-summary field;
4. runs the eight finite validation groups `capacity`, `source`, `mutations`, `controls`, `binding`, `overlap`, `stress`, and `androlog`;
5. replays every regenerated certificate through the isolated entry point and requires its deterministic replay summary to equal both the retained and shipped-packet replay summaries; and
6. writes `/tmp/trigger-coverage-reproduction/comparison.json`.

A successful run reports 2,448 equal deterministic rows, an equal deterministic campaign summary, successful shipped and regenerated certificate replays, equal finite-test result objects, and checker import isolation. Successful commands are reproduction evidence, not proof-assistant verification of the general mathematics.

The separate platform-independent regressions run with:

```sh
python -m unittest -v tests.test_overlap_totality tests.test_adapter_read_limits
```

The totality regression additionally checks the 2,106 uncovered-element X3C families excluded from the frozen overlap campaign. It does not change that campaign's 4,090-family denominator or its retained result file. Well-formed infeasible exact-count views return no compatible selections; malformed shapes, indices, and counts still raise `ValueError`.

`.github/workflows/scientific-checks.yml` runs these regressions and the full fresh-output reproduction on `ubuntu-latest` with Python 3.12 when this standalone artifact is the repository root. It keeps outputs under a newly created `$RUNNER_TEMP` directory, verifies frozen `data/` and `results/` are unchanged, and uploads the outputs, logs, exit codes, runner metadata, and GNU `time` measurements for 14 days. The job has a 15-minute hard limit, a 60-second regression timeout, a 600-second reproduction timeout, a 3 GiB per-process address-space limit, and a 600-second per-process CPU limit. The existing 45-second subprocess and 20-second per-case limits remain; the CPU limit is not an aggregate CPU quota. These are enforced ceilings, not predicted runtimes. The scientific workload uses one worker and only bounded local models and authored benign AndroLog fixtures; no secrets, model API, APK, exploitation, or network target is required. Checkout, Python setup, and artifact upload use GitHub infrastructure. The Linux resource-limited CLI is not a Windows test.

## Focused commands

```sh
python -m tests.validate --part capacity  --output /tmp/tlc-capacity
python -m tests.validate --part source    --output /tmp/tlc-source
python -m tests.validate --part mutations --output /tmp/tlc-mutations
python -m tests.validate --part controls  --output /tmp/tlc-controls
python -m tests.validate --part binding   --output /tmp/tlc-binding
python -m tests.validate --part overlap   --output /tmp/tlc-overlap
python -m tests.validate --part stress    --output /tmp/tlc-stress
python -m tests.validate --part androlog  --output /tmp/tlc-androlog
```

To certify one admitted model and count vector, use the Python API in `src/producer.py` and validate with `src/checker.py`. The checker API takes three separate inputs:

```python
check(model, expected_counts, certificate)
```

A certificate that is valid for another count vector is rejected against `expected_counts`. This binding is not cryptographic authentication.

## AndroLog-format bridge

`src/androlog_adapter.py` recognizes the public raw-probe labels `STATEMENT`, `METHOD`, `CLASS`, `ACTIVITY`, `SERVICE`, `BROADCASTRECEIVER`, and `CONTENTPROVIDER`. It requires an explicit injective probe map into one declared finite model, preserves probe order and repetition within a session, and deduplicates only identical complete normalized event traces before distinct-trace counting.

Run the authored benign fixture with:

```sh
python -m src.androlog_adapter \
  --model data/androlog-format-fixture/model.json \
  --probe-map data/androlog-format-fixture/probe-map.json \
  --sessions data/androlog-format-fixture/sessions \
  --log-identifier MY_SUPER_LOG \
  --output /tmp/androlog-report.json
```

The bridge accepts only strict UTF-8 regular non-symlink files, caps each session and configuration at 4 MiB, caps a session directory at 4,096 files and 64 MiB, anchors the probe assignment after the log identifier, validates model syntax and probe-map normalization/range/injectivity, and fails closed on unknown probes, unsupported labels, malformed lines, NULs, undeclared events, horizon violations, and context-lock violations. Supported POSIX opens add `O_NONBLOCK` and `O_NOFOLLOW` before descriptor `fstat`, so a no-writer FIFO is rejected immediately without weakening final-component race or symlink checks. It does not instrument an APK, authenticate logcat, prove that a normalized probe denotes the claimed semantic event, or prove that upstream instrumentation is complete.

## Repository map

- `src/producer.py` - semantic DAG construction and certificate production
- `src/checker.py` - independently written semantic and certificate replay
- `src/verify.py` - batch replay against frozen expected reports
- `src/baseline.py` - independently coded circulation comparator
- `src/oracle.py` - direct whole-word and labelled-token finite oracles
- `src/overlap_boundary.py` - X3C reduction and tiny overlap-consistency oracle
- `src/androlog_adapter.py` - public-label syntax bridge
- `tests/validate.py` - eight finite validation groups and negative controls
- `data/cases.jsonl` and `data/reports.jsonl` - exact frozen primary inputs
- `data/androlog-format-fixture/` - authored benign adapter fixture
- `results/campaign/` - primary per-case rows, chunks, certificates, and summary
- `results/tests/` - exact finite-domain results
- `results/replay.json` - standalone checker replay record
- `results/clean_reproduction.json` - retained clean-extraction comparison
- `docs/proofs.md` - complete ordinary mathematical arguments
- `docs/input-contract.md` - admitted source/report language and exclusions
- `docs/validation.md` - frozen validation design and interpretation
- `claim_evidence_ledger.csv` - claim-to-proof/check/result mapping
- `external_resources.csv` - literature, official-rule, format, and license record

## Retained results

The primary suite has 2,400 generated cases and 48 authored schema-motivated fixtures, comprising 1,944 structural JSON models. Verdicts are 409 forced complete, 817 ambiguous, and 1,222 forced incomplete. Every case agrees with the independent circulation implementation and contains a constructed allocation whose actual outcome lies in the certified spectrum.

The finite capacity domain contains 1,188 matrices across complementary 2-by-3 and 3-by-2 shapes, 28,836 count reports, 227,556 labelled-token subsets, and 45,944 checked outcome-specific allocations. The source domain contains 20,832 precisely named source instances and 113,088 directly evaluated legal words. The deterministic stress group checks 20,000 larger random capacity/report instances and 54,276 allocation witnesses, with zero circulation or witness disagreements. The mutation suite rejects 729 non-equivalent changes and accepts 55 reordered equivalents. The overlap group checks 4,090 locally admissible X3C families with no disagreement between exact-cover and overlapping-view feasibility; all 4,090 retained records are independently read back from canonical saved tokens, all 1,720 positive selections are rechecked, and unordered-input controls retain explicit reindexing permutations. The AndroLog fixture converts seven byte-level files to six distinct normalized traces, proves that two byte-distinct files can normalize to one trace, accepts a probe-anchoring control, retains 22 portable malformed/resource/schema rejections, isolates the aggregate exact/over-one-byte branch, rejects POSIX session/configuration FIFOs by explicit `InvalidLog` in bounded child processes, and rejects a certificate after the derived report changes.

The count-threshold proxy and existential full-cover feasibility coincide on every primary case. A separate Hall-bottleneck control distinguishes them. This negative primary result is retained; it is not replaced by a favorable interpretation.

## Scope and interpretation

Counts denote distinct selected traces in a partition. Exact source capacities, fixed class order, independent selections, and truthful counts are assumptions. Repeated executions, lower bounds, arbitrary overlapping views, cross-trace constraints, changed horizons or predicates, spurious/omitted concrete behavior, and unauthenticated logs require different evidence and often a different theorem.

The generated inputs and authored fixtures validate the bounded theorem and implementations. They are not 2,448 independent Android applications, not TriggerZoo samples, and not estimates of malware prevalence or detector accuracy. The public-label bridge is format interoperability, not a verified APK-to-model extraction.

## Authorship and disclosure


## License

Original artifact code, authored models, proof notes, and result files are provided under the MIT license in `LICENSE`. No APK, upstream analyzer implementation, or scholarly PDF is redistributed. The separate paper package preserves the upstream IEEE class/style license notices and is not covered by this artifact's MIT license.
