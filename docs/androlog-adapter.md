# AndroLog-format adapter

This adapter connects a public Android coverage-log syntax to the finite report contract without importing or modifying upstream code.

## Inputs

1. A finite trigger model accepted by `src/checker.py`.
2. An injective JSON object mapping exact normalized probe keys to event indices.
3. A directory whose regular non-symlink strict-UTF-8 files are bounded sessions, one file per session. Each file is at most 4 MiB; the directory has at most 4,096 files and 64 MiB total. The final component is opened with no-follow and, on POSIX, nonblocking flags before descriptor-level `fstat`; this rejects a no-writer FIFO without waiting for an external timeout while retaining the regular-file and replacement-race check.
4. A nonempty log identifier of at most 256 characters that marks relevant lines. The assignment is parsed only after this identifier.

Recognized keys begin with `STATEMENT=`, `METHOD=`, `CLASS=`, `ACTIVITY=`, `SERVICE=`, `BROADCASTRECEIVER=`, or `CONTENTPROVIDER=`.  For statements, only the payload before the first `|` is identity-bearing.

## Output and guarantee

The command derives distinct source words, bucket counts, and a class allocation from the declared model, then generates and replays an omission-spectrum certificate.  Acceptance means that the text sessions, probe map, model, counts, allocation, and certificate are mutually consistent under this repository's bounded semantics.

Acceptance does **not** authenticate the files, prove that instrumentation executed, establish a faithful APK-to-model abstraction, or infer that a probe has the supplied event meaning. The adapter validates model syntax and probe-map normalization, declared-event range, integer typing, and injectivity, but the map’s semantic meaning and acquisition provenance remain trusted. Unknown or malformed identifier-bearing probes cause rejection rather than being silently ignored. Configuration files are regular non-symlink strict-UTF-8 JSON objects capped at 4 MiB.

## Fixture

`data/androlog-format-fixture/` is authored synthetic text. It exercises all seven label kinds, statement-pipe normalization, assignment anchoring after the identifier, session order, normalized-trace deduplication across byte-distinct files, certificate construction, 22 portable fail-closed negative controls, a parameterized exact/over-one aggregate boundary, two POSIX no-writer FIFO subprocess controls when supported, and report binding. The aggregate fixture contains valid text traces and reaches no other rejection branch; the FIFO controls pass only on explicit `InvalidLog`, not timeout. No APK, Android device, emulator, private dataset, or upstream executable is included.
