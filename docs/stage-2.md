# Stage 2 — Interactive Workloads and Experiment History

**Status: implemented, verified, and running locally.**

## Purpose and architecture

Extend the verified Stage 1 monitoring stack with a Flask controller, Data worker, and MongoDB. The controller serves the application at port 5000. Compute and Data are internal services. All seven containers use the existing cAdvisor → Prometheus → Grafana monitoring path.

The browser requests experiments; it does not own their lifetime. The controller owns one global active-run slot and polls worker state. Each worker owns one child process with progress messages, a deadline, and explicit cleanup. MongoDB stores summaries separately from temporary workload documents.

## Implementation guide

- `services/shared/model.py`: presets, validation, and Grafana links.
- `services/shared/worker.py`: asynchronous execution, idempotent run IDs, bounded results, stop, and shutdown.
- `services/shared/workload_child.py`: actual CPU, memory, network, and MongoDB operations. Each process creates its own clients and releases resources on exit.
- `services/controller/coordinator.py`: global run ownership, worker reconciliation, progress, and persistence retry.
- `services/controller/repository.py`: short-deadline MongoDB operations and document cleanup.
- `services/controller/app.py`: public JSON API, filtered history, and CSV export.
- `services/controller/templates` and `static`: Flask HTML, plain JavaScript, and CSS.
- `services/compute/app.py` and `services/data/app.py`: small entry points using the same worker application.
- `services/gunicorn_conf.py`: one application process and eight request threads per service; supervisor startup/shutdown happens once.

## Workloads and limits

| Setting | Low | Medium | High | Allowed advanced range |
|---|---:|---:|---:|---|
| CPU busy time | 25% | 50% | 90% | 10–95% |
| Memory | 32 MiB | 64 MiB | 128 MiB | 1–128 MiB |
| Network payload | 64 KiB | 256 KiB | 1,024 KiB | 1–1,024 KiB |
| Request / cycle rate | 2/s | 5/s | 10/s | 1–20/s |
| Database payload | 4 KiB | 16 KiB | 64 KiB | 1–64 KiB |

Default duration is 30 seconds; accepted durations are 15–180 seconds. CPU uses 100 ms busy/idle cycles and one calculation process. Memory pages are touched rather than merely reserved. Network work downloads payloads from Compute into Data, so Data receive traffic is the main graph. A database cycle performs a write and matching read. Combined Data performs memory, network, and database work together.

The MongoDB workload reuses at most 128 document slots per run. Child cleanup removes them at completion/cancellation. Controller persistence also retries cleanup for terminal runs; a one-hour expiry and TTL index provide a fallback when MongoDB is unavailable during cleanup.

## Run and recovery behaviour

States: `starting`, `running`, `stopping`, `completed`, `cancelled`, `failed`, and `interrupted`.

- Starting a second run returns 409. Internal duplicate starts for the same ID/settings return the existing run; conflicting settings are rejected.
- Stop is idempotent. Workers terminate a child gracefully, then kill it if it has not exited within two seconds. The independent runtime deadline is the configured duration plus three seconds.
- Final and partial counters describe actual work reported by the child. Progress is elapsed time, not an invented completion estimate.
- Controller restart cancels leftover worker activity, reconciles the last outcome, and marks interrupted runs. Worker restart is detected through the absence of the dispatched ID; no automatic work retry occurs.
- Unreachable worker state prevents new starts until reconciled. HTTP liveness remains available.
- MongoDB outage disables Database/Combined but leaves CPU/Memory/Network available. Up to 100 unsaved summaries stay in memory; a full pending buffer rejects further starts. Unsaved summaries can be exported, but may be lost if the controller restarts before recovery.
- Persistence writes occur at state transitions and completion, rather than on every live progress update. History remains bounded in controller memory; older saved runs are paginated from MongoDB.

## Deployment

All previous Stage 1 CPU/RAM limits remain. Controller adds 0.5 CPU / 256 MiB, Data 1 CPU / 512 MiB, MongoDB 1 CPU / 768 MiB. Total configured memory is 3,456 MiB. MongoDB's WiredTiger cache is explicitly 0.25 GiB; this is a cache limit, not total process memory.

MongoDB 8.0.34 uses a pinned image digest. PyMongo 4.19.0 and Requests 2.34.2 and their installed dependencies are pinned in the shared requirements file. MongoDB has a named volume and no published host port. It is an unauthenticated, trusted local-lab database on the Compose network. The web application has no Docker daemon control.

The existing Grafana dashboard discovers the new services by labels. Run links select Compute for CPU, Data for Memory/Network, and Data plus MongoDB for Database/Combined. Links include the run time range. No application-performance metrics or tracing are introduced in Stage 2.

## Verification record

Automated tests: **10 pass**, including boundary validation, immutable resolved settings, global start races, idempotence, cancellation races, deadlines, process reaping, shutdown interruption, pending-buffer limits, database failure recovery, and CSV quoting/formula handling. Final run: 23.308 seconds; transcript in `evidence/stage2/unit-tests.txt`.

Browser verification: a Combined Data run started through the UI, survived browser refresh with the same ID and growing counters, and was stopped through the UI. Its screenshot is saved under `docs/evidence/stage2/control-panel-active.jpg`.

Live acceptance: **38 of 38 checks passed** in `evidence/stage2/acceptance.json`. The sequence exercises every workload, cancellation, duplicate commands, responsive health, controller/Data restart, MongoDB outage and reconnection, export during outage, blocking starts when a worker is unreachable, full stop/start persistence, CSV values, and seven-service monitoring.

Additional recovery: **5 of 5 checks passed** in `evidence/stage2/recovery.json`. An abrupt SIGKILL of the controller left work for startup reconciliation, which correctly recorded interruption. A 300-cycle database run reached but never exceeded 128 simultaneous temporary documents and removed them on completion.

| Observed result | Measurement |
|---|---|
| Low CPU, average of final three sampled rates | 0.289 cores |
| High CPU, average of final three sampled rates | 0.709 cores |
| Data idle working set | 43.87 MiB |
| Memory workload sampled maximum | 136.80 MiB, with a 64 MiB buffer plus child-process overhead |
| Data memory after cooldown | 43.98 MiB |
| Network workload | 75 responses / 19,660,800 payload bytes in 15 seconds, 5.0 requests/s |
| Database workload | 300 writes plus 300 reads in 15.006 seconds, 19.991 cycles/s |
| Combined Data workload | 64 MiB buffer, 75 network responses, and 75 database cycles in 15.007 seconds |
| Operation failures in completed workloads | 0 |

These are actual acceptance measurements on this laptop. The CPU figures use 30-second rate windows and are not promises that configured duty cycles equal measured utilization. Stage 5 will perform repeated controlled comparisons.

The first acceptance attempt exposed an incorrect cancelled/interrupted classification during graceful worker shutdown. The worker now records an interruption reason before stopping its child, with a regression test. The initial record remains in `first-attempt.json`; the complete successful rerun is `acceptance.json`. Final checks also verified that original Stage 1 historical Prometheus samples remain readable.

Browser verification additionally covered saved Details, name filtering, actual filtered CSV download, and automatic clearing of a temporary connection error after controller recovery without page refresh. A database-outage check verified that the current result changes from pending to saved automatically. Finally, a 15-second memory experiment using the advanced 96 MiB override completed and saved correctly; its full response is `browser-completed-run.json`. All nine browser checks passed in `browser-checks.json`; the downloaded filtered CSV is `browser-filtered-history.csv`.

Evidence includes `control-panel-active.jpg`, `control-panel-completed.jpg`, the compact `control-panel-overview.jpg`, `run-details.jpg`, `grafana-combined.jpg`, exported `experiment-history.csv`, dependency versions, and the final seven-service deployment snapshot. All seven services are healthy with no OOM kills. The PowerShell network demo also completed with 75 responses and 18.75 MiB transferred; its result is `powershell-demo.json`. Original Stage 1 evidence stays in `docs/evidence`; Stage 2 writes its own subfolder.

## Reproduce verification

```powershell
./scripts/start.ps1
docker compose exec -T controller python -m unittest discover -s tests -v
python ./scripts/verify-stage2.py
# Additional abrupt-loss / document-cap checks:
python ./scripts/verify-recovery.py
```

The live script intentionally restarts containers and must run without another experiment active. It records actual metrics and results, exercises MongoDB/controller/worker outages, and checks full restart persistence. The old Stage 1 measurement and lifecycle command names now forward to this updated workflow.
