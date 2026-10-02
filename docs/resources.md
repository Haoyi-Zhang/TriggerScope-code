# Scientific resource accounting

`results/resource_budget.json` separates retained evidence from the final cache-free one-command reproduction. Retained result files contain 30.553218 instrumented CPU seconds. The final clean workflow contains 27.457745 instrumented group CPU seconds; outer GNU `time`, including startup and child processes, observed 52.87 user-plus-system CPU seconds, 43.66 elapsed seconds, and 108,072 KiB maximum RSS. These CPU figures overlap and are not added together.

The final workflow performs 4,298,131 declared checker steps, explores 401,504 producer-layered nodes, and replays 562,208 already-produced nodes across the shipped and regenerated packets. It stays below the frozen ceilings of 8,000,000 checker steps and 2,500,000 producer nodes. A conservative cumulative charge of 600 CPU seconds covers prior retained accounting, repair validation, successful clean reproductions, interrupted observation windows, focused controls, manuscript rebuilds, and diagnostics; it remains far below the 25,200-second ceiling.

All eight validation groups run sequentially with one worker. Source code applies a 3 GiB address-space limit and a 20-second per-case timer; the reproduction driver applies 45-second subprocess timeouts. No GPU, model API, external compute, APK, real device, emulator, or network service is used by the scientific workflow. Public literature retrieval is workflow evidence and was not byte-instrumented.

The semantic pilot remains in `results/semantic_pilot.json`; its source models are identified by case IDs in the exact primary input. Pilot evidence does not replace final source-bound replay.
