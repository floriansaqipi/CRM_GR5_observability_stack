# Stage 5 evidence index

This folder contains real observations recorded on 1 November 2026. Read the [short results report](../../experiment-results.md), [repository guide](../../repository-guide.md), and [demo guide](../../demo-guide.md) first. Saved measurements and verification records retain their original identifiers and values; document paths within older verification records reflect the names used at collection time.

## Four examples

`experiments.json` is the main record: it contains the four run IDs/results, verified deployment, actual windows, source/image identities and 36 passing collection checks. Application images stayed fixed across all four cases. Each run had at least 30 seconds of idle observation and 30 seconds of cooldown; manual preparation sometimes added idle time. The plots show the final 30 seconds before Start and the following workload/cooldown.

| Scenario folder | Contents |
|---|---|
| `cpu/` | Medium 50% busy CPU for 30 seconds |
| `memory/` | Touched 64 MiB held for 30 seconds |
| `network/` | 256 KiB downloads at requested 5/s for 30 seconds |
| `combined/` | 64 MiB, 256 KiB network, 16 KiB database documents, requested 5 cycles/s for 30 seconds |

Each folder contains `run.json`, `export.csv`, `measurements.json`, `resources.png`, `resources.svg`, `application.jpg` and `grafana.jpg`. Measurement files preserve the Prometheus expressions and returned sample matrices. Run files preserve exact settings, timestamps, counters, achieved rates, deployment and trace association.

Combined additionally includes the raw `trace.json`, the actual Grafana `trace.jpg`, and `application-performance.jpg`. Its connected trace has 142 spans. `experiment-history.csv` contains only the four selected run IDs, exported with the application's CSV columns.

## Verification and visuals

| File | Purpose |
|---|---|
| `unit-tests.txt` | All 31 retained regression tests passed |
| `dashboard-before.json` | Original dashboard models, allowing verification that IDs, selectors, queries and windows remain unchanged |
| `preflight-verification.json` | Readiness and historical query checks before collecting examples |
| `browser-verification.json` | Actual form, responsive layout, refresh, Stop, history/export, details, maintenance and connection recovery checks |
| `browser-filtered-export.csv` | Browser-downloaded cancelled-run filter example |
| `browser-example-export.csv` | Browser-downloaded four-example history filter |
| `ui-runs.json` | Separate live fixed-work, Database and cancellation checks; these are not the four reported examples |
| `mobile-layout.jpg` | Narrow viewport with stacked controls/results and contained table scrolling |
| `laboratory.jpg` | Finished laptop interface showing the four-example Combined result |
| `details.jpg` | Structured saved settings, deployment and results |
| `maintenance.jpg`, `connection-lost.jpg` | Genuine maintenance/outage states observed with no active workload |
| `verification.json` | Final Stage 5 checks, including every historical resource query, saved evidence and document links |
| `final-state.json` | Final verified baseline/tracing deployment, containers, idle worker state and cleanup |
| `rehearsal.json` | Operator workflow verification and recorded four-run rehearsal window |

Build, startup, plotting-install, rendering and verification transcripts are also preserved. The source diagrams in `docs/assets` have Mermaid definitions and rendered PNG/SVG versions. Normal graph/trace retention still applies to server data; saved evidence files remain available after that retention window.

The service-colour regex syntax was corrected after measurement collection. This changed presentation only. The main record preserves both the original source fingerprints and final dashboard fingerprints; no measurement expression or application image changed during the examples.

## Repeat the examples without replacing these files

Start verified baseline with tracing enabled and ensure there is no active experiment. Use a new output directory:

```powershell
python ./scripts/measure-stage5.py --out docs/evidence/stage5-repeat-001
```

That command starts the four examples through the existing API. To start them yourself through the browser, add `--manual`. Follow `progress.json`: wait until `awaiting_start`, choose the indicated workload with Medium intensity and 30 seconds, then Start. The operator has three minutes to start each prepared scenario. No failed or uncertain workload is automatically replayed. A new collection refuses to overwrite an existing `experiments.json`.

## Rebuild the saved Stage 5 figures

Plotting is an optional host tool, separate from application dependencies. The tested environment uses Python 3.12 and pinned Matplotlib 3.10.7 plus dependencies:

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r scripts/plot-requirements.txt
./.venv/Scripts/python.exe scripts/render-stage5.py
```

The renderer uses saved measurements only. It regenerates the original Stage 5 figures, diagrams and Markdown results report; it does not run workloads or alter database/monitoring data. Copy the script and change its evidence/report paths if preparing a separate future report.

Read-only final verification:

```powershell
python ./scripts/verify-stage5.py
```

Historical server-data checks require the original samples still to be within Prometheus retention. Archived JSON/CSV/figures remain readable independently of Prometheus or Tempo. Older Stage 1–4 live acceptance scripts remain available, but rerunning them replaces their own evidence; Stage 5 did not rerun those mutating suites.
