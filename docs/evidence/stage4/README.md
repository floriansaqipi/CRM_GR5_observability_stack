# Stage 4 evidence

Recorded against real Docker Desktop containers on 2026-11-01. Earlier Stage 1–3 evidence remains in its original location.

| File | Content |
|---|---|
| `acceptance.json` | 140 completed live checks, nine applied preset configurations, immutable run snapshots, assignments, batch results and measured peaks |
| `live-verification.txt` | Full live acceptance transcript |
| `unit-tests.txt` | All 31 automated tests, including retained Stage 2–3 tests |
| `dashboard-verification.json` | 22 historical resource/application query checks over actual CPU/replica experiment ranges |
| `lifecycle.json` | Exact per-instance metric deltas, one parent outcome, seven-service startup, existing Combined regression and normal stop/start persistence |
| `lifecycle-verification.txt` | Initial lifecycle transcript and resumed successful checks after fixing empty Docker-status output parsing |
| `browser-checks.json` | Verified browser interactions and visible results |
| `browser-runs.json` | Browser-started completed/cancelled experiments |
| `browser-export.csv` | Actual browser download using workload/name filters |
| `experiment-history.csv` | Full exported history at the end of the main acceptance suite |
| `batch-result-example.json` | Extracted replica assignment, deployment, results and checksum |
| `replica-trace.json` | Raw connected trace, both Compute identities and 32 batch spans |
| `combined-regression-trace.json` | Retained timed Combined path through Data, Compute and MongoDB client operations |
| `final-state.json` | Final verified baseline/tracing deployment, idle worker state and actual running container limits/images |
| `final-verification.txt` | Final readiness, dashboard and scrape checks |
| `verification-summary.json` | Counts of passing checks and recorded syntax/dependency verification |

Screenshots: `workload-laboratory-full.jpg` shows the live application; `workload-comparison.jpg` shows completed fixed work; `saved-run-details.jpg` shows stored configuration; `cpu-quota-panels.jpg`, `replica-resources.jpg`, `replica-throughput.jpg` and `replica-trace.jpg` show actual Grafana results. Traces expire independently of history; raw examples/screenshots remain here.

`first-attempt.json`, `sampling-attempt.json` and `lifecycle-first-attempt.json` retain earlier unsuccessful verification attempts. They are not the final acceptance result. Fixes and sampling limitations are explained in [the implementation record](../../stage-4.md). `smoke-run.json` is the initial four-batch check. Preset/build/startup transcripts are saved alongside these files.

Elapsed times are single acceptance observations, not a repeated benchmark. Formal repetitions and academic analysis remain Stage 5.
