# Stage 3 — Application Metrics and Distributed Tracing

**Status: implemented, verified, and running with tracing enabled on 2026-11-01.**

## Implementation

Stage 3 adds direct Prometheus application metrics, a provisioned Application Performance dashboard, asynchronous OpenTelemetry tracing, Collector and single-instance Tempo. It retains the existing Stage 2 workloads, limits, history, global run slot, and recovery model.

The Combined trace follows Controller → Data parent → Data child; the child calls Compute over HTTP and MongoDB through PyMongo. MongoDB client spans belong to Data. No extra agent runs in MongoDB.

The shared metrics module owns one registry per parent process. Children use fixed-size cumulative I/O buckets and counts in the existing JSON progress stream. Parent-side delta merging counts each observation once, including the final message. Worker duration includes startup/cleanup; HTTP duration stays separate. See `metrics.md` for labels, units and limits.

Gunicorn initializes the tracing SDK after fork; workload subprocesses initialize their own provider. The run span outlives the short Start request. W3C context is captured before thread dispatch and passed explicitly to subprocesses. Context is private in internal/persisted records and removed from public responses.

Every experiment/main phase is traced. Successful I/O detail is limited to the first cycle and at most one cycle per second. Other calls carry an unsampled context, preventing Compute from generating unrelated traces. Failed omitted cycles get an explicit error span. Memory allocation, hold and release, CPU calculation, and database cleanup have named spans.

Health checks, scrapes, static assets, periodic status reads and MongoDB availability pings are excluded. PyMongo's `capture_statement=False` prevents query/document capture; this driver version still emits bare command names (`find`, `update`, etc.) in `db.statement`. Request/response bodies are not captured.

Exporter queues are limited to 512 spans per application process with 0.5-second export timeouts. Collector applies a 192 MiB memory limit, batches up to 512 spans, and has a 64-request sending queue with 30-second maximum retry duration. Missing tracing backends can lose spans; they never become workload failures. Child stderr remains separate from JSON progress.

## Deployment

```powershell
./scripts/start.ps1          # seven services, metrics enabled
./scripts/start.ps1 -Tracing # nine services, metrics and traces
./scripts/stop.ps1           # all profiles, preserves named volumes
```

Collector: `otel/opentelemetry-collector-contrib:0.164.0`; Tempo: `grafana/tempo:3.1.1`. Both images are pinned by digest in Compose. Python 3.13 uses Prometheus client 0.26.0, OpenTelemetry SDK/exporter 1.45.2, and instrumentation 0.66b2; transitive dependencies are pinned too.

OTLP/HTTP ports and Tempo's query port are internal. Collector/Tempo readiness is checked from the existing Python container, avoiding health probes that assume utilities in minimal images. Grafana's built-in Tempo source has UID `tempo` and remains provisioned when tracing is disabled.

Tempo uses the `tempo-data` volume, local blocks/WAL, and 24-hour block retention in both scheduler and worker compaction configuration. Retention is asynchronous, not an exact deletion deadline. Prometheus retains seven days or 1 GiB. Grafana's ceiling is 512 MiB; Collector 256 MiB/0.5 CPU and Tempo 768 MiB/1 CPU. Combined configured ceilings are 4.5 GiB.

Normal startup restarts Grafana/Prometheus to load changed provisioning/scrape files. Switching modes recreates affected app containers: finish or stop a run first. Destructive reset explicitly deletes the Tempo volume along with metrics, Grafana and MongoDB data; it is never part of normal shutdown.

## Interface additions

- `/metrics` on all three Flask services; Compute/Data stay internal.
- `/api/workloads`: `observability.tracing_enabled` describes configuration, not delivery assurance.
- Run/history responses: `application_grafana_url`, nullable `trace_id`, nullable `trace_url`.
- CSV: appended `trace_id`; older summaries export an empty value.
- UI current-run/details links select services and experiment time ranges. Trace links require the current tracing mode and a recorded ID. Traces can expire while history remains.

## Verification

```powershell
docker compose run --rm --no-deps controller python -m unittest discover -s tests -v
./scripts/start.ps1 -Tracing
python scripts/verify-stage3.py
python scripts/verify-stage3-recovery.py
```

The live script deliberately stops dependencies and switches modes. Evidence is saved under `docs/evidence/stage3`; Stage 1–2 evidence stays untouched. It checks exact metric deltas, a connected Combined trace, failed dependency calls, tracing outages, cleanup, persistence, CSV, both startup modes, and resource/OOM state. Browser checks cover graph/trace links and the visible Grafana result.

Unit tests use a disposable container so their additional coordinator, registries and children do not compete with the live Gunicorn service inside its 256 MiB ceiling. An initial run inside the live controller hit a child-start timing failure; the isolated command above preserves the original test deadlines and passes under the same service limits.

| Evidence | Result |
|---|---|
| `unit-tests.txt` | 17 automated tests passed, including all 10 Stage 2 tests; 27.8 seconds in an isolated disposable container. |
| `acceptance.json` | 47 live checks passed: metrics, connected traces, failures, outages, cleanup, persistence, CSV and both startup modes. |
| `recovery.json` | 10 checks passed: controller SIGKILL, Data restart, retained trace IDs, interrupted outcomes, released workers, and an original Stage 1 Prometheus sample still readable. |
| `final-workloads.json` | Four checks passed against the final image: Combined counter/history agreement, successful CPU work, exact CPU batch count, and calculation span. |
| `browser-checks.json` | Seven checks passed: form Start, refresh, saved run details, application graphs, connected trace, span inspection, and real filtered CSV download. |

The measured 30-second Combined run completed **150 network transfers (39,321,600 bytes)** and **150 MongoDB write/read cycles**, with zero operation errors. Its trace contained **142 spans**, including 26 selected I/O cycles across three Flask services plus MongoDB client calls. A separate browser-started run reproduced 150 transfers/cycles and a connected trace.

Start returned in **0.0053 seconds** during the acceptance run. Stop completed in **3.15 seconds with Collector unavailable** and **1.06 seconds with Tempo unavailable**, preserving partial counters and cleaning temporary documents. The controlled Compute outage produced three failed network operations, a failed run, and error spans.

The final CPU check completed **38,736 calculation batches** in 15 seconds; the metric delta matched saved history exactly and the trace contained `cpu.calculate`. These are observed results on this laptop, not performance guarantees.

Both startup modes were exercised. Trace/history data survived a full down/start cycle without volume deletion. The tracing configuration's effective retention values were read back as 24 hours. All nine services remained within their configured ceilings, with no recorded container OOM kills; `memory-snapshot.txt` records a final observed snapshot rather than a peak-memory guarantee.

Screenshots include `control-panel-active.jpg`, `control-panel-completed.jpg`, `run-details.jpg`, `application-dashboard.jpg`, `connected-trace.jpg`, and `trace-compute-span.jpg`. Raw connected/error/recovery/CPU traces, `browser-run.json`, exported history and the browser's filtered CSV are saved beside them under `docs/evidence/stage3`.

`first-attempt.json` preserves an initial overly strict verification assertion: the driver emits harmless bare command names in `db.statement` even when document capture is disabled. The corrected check verifies those values contain only command names, and the full live suite passed afterward. `unit-tests-in-running-controller.txt` records the resource-contention timing failure described above; the final isolated test log passes without changing test deadlines.

## Limitations

Counters are process-local and reset on restart. Child hard termination can lose the last progress interval. A hard crash may leave unfinished spans missing; recovery adds an interruption span using the stored association rather than inventing missing execution. Tracing is best-effort, and a trace ID does not guarantee storage. Trace detail intentionally omits most successful repeated cycles; operation metrics remain comprehensive for reported work.

No replica routing, allocation comparisons, log storage, alerts, or cloud deployment is introduced in this stage.
