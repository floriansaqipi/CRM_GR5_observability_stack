# Cloud Lab — Resource Monitoring and Workload Laboratory

A university lab using **Flask, Prometheus, Grafana, and Docker Compose**. The workload laboratory supports actual container measurements, application metrics, optional traces, resource-allocation presets, and one/two-Compute comparisons.

## Read this first

| Document | Use it for |
|---|---|
| [Repository guide](docs/repository-guide.md) | Understand the services, execution flow, source structure and implemented work |
| [Demo guide](docs/demo-guide.md) | Prepare and operate the approximately ten-minute live walkthrough, with optional comparisons and recovery steps |
| [Four example results](docs/experiment-results.md) | Inspect actual measurements, annotated plots, run IDs, CSV exports and the connected trace |
| [Albanian project report — Word](docs/Raporti_Projektit_Monitorimi_i_Burimeve_Plote.docx) | Read the illustrated report with the abstract, chapters I–V, references and all sixteen project figures |
| [Report sources and verification](docs/raporti/README.md) | Review chapter sources, citation mappings, historical document checks and editing guidance |
| [ChatGPT figure-context bundle](docs/chatgpt-image-bundle/README.md) | Prepare a portable Project handoff with the Word report, sixteen figure prompts, source/evidence library and style references |

Revised Stage 5 focuses on visual improvements, example results and practical guides. The Albanian Word report now includes all sixteen project figures; its cover identity and logo fields remain to be filled in. The formal repeated study and PowerPoint presentation remain future work.

## Start the application

Prerequisites: Docker Desktop with its Linux engine running, Docker Compose, and PowerShell. PowerShell 7 is recommended; startup, verification and shutdown also support Windows PowerShell 5.1. Baseline configured memory ceilings total 3.5 GiB without tracing and 4.5 GiB with tracing. The largest supported preset uses 5 GiB with tracing, plus Docker overhead. These are ceilings, not predicted consumption. The first image download/build needs internet.

```powershell
./scripts/start.ps1
# Include Collector + Tempo and enable tracing in all three Flask services:
./scripts/start.ps1 -Tracing
# Explicit first configuration:
./scripts/start.ps1 -Preset baseline -Tracing
```

| Page | Address |
|---|---|
| Workload control panel | http://localhost:5000 |
| Grafana resource dashboard | http://localhost:3000/d/cloud-lab1-resources |
| Grafana application dashboard | http://localhost:3000/d/cloud-lab1-application |
| Prometheus | http://localhost:9090 |

The startup script generates `.env` with a random Grafana password if it does not exist. Existing credentials and volumes are preserved. Sign in using the local `.env`; do not share or commit that file. Changing `.env` after Grafana's first initialization does not reset its stored password.

Startup now restores the last successfully applied preset and tracing mode. Use `-Tracing` or `-NoTracing` to choose explicitly; supplying both is invalid. First startup without saved state uses baseline without tracing. `-NoBuild` starts existing images without downloads/builds.

### Inspect history with MongoDB Compass

MongoDB is published only on local IPv4 loopback, port 27017. In Compass, add a connection using `mongodb://127.0.0.1:27017/lab`. This local instance has no authentication configured. Open the `lab` database: `runs` contains experiment history, and `workload_documents` contains temporary documents that are removed after workload cleanup.

## Run an experiment

1. Choose CPU, CPU comparison, Memory, Network, Database, or Combined Data.
2. Choose Low/Medium/High. Timed workloads accept 15–180 seconds (default 30); CPU comparison selects a fixed work amount instead.
3. Optionally expand Advanced settings, add a name, and record notes.
4. Start. The right panel shows actual operation counts and elapsed time.
5. Open resource graphs, application graphs, or **Open trace** for that run.
6. Stop early or allow automatic completion. Review Details and export CSV.

**CPU comparison** uses fixed calculation work: Low/Medium/High mean 16/32/64 batches, each containing 2,500 calculation units. Advanced batch count accepts 4–64. Runs finish when the work is complete, with a fixed 180-second safety deadline. Two calculation processes total are used under every CPU/replica comparison. Progress counts completed batches; history includes actual units, checksum, assignments and per-instance results.

## Compare resource configurations

Finish or stop the current experiment, then apply one preset:

```powershell
./scripts/apply-preset.ps1 -Preset cpu-05
./scripts/apply-preset.ps1 -Preset cpu-1
./scripts/apply-preset.ps1 -Preset cpu-2
./scripts/apply-preset.ps1 -Preset memory-256
./scripts/apply-preset.ps1 -Preset memory-512
./scripts/apply-preset.ps1 -Preset memory-1024
./scripts/apply-preset.ps1 -Preset replica-1
./scripts/apply-preset.ps1 -Preset replica-2
# Restore baseline with tracing enabled:
./scripts/start.ps1 -Preset baseline -Tracing -NoBuild
```

CPU presets change primary Compute's CPU ceiling (0.5/1/2), keeping its memory at 512 MiB. Memory presets change Data's ceiling (256/512/1,024 MiB), keeping its CPU at one core. Replica presets use one/two Compute containers, each with one core and 512 MiB. Other services keep their limits.

Use **the same CPU comparison work amount** for CPU/replica cases. Use **64 MiB for 30 seconds** for all three memory cases. The 256 MiB Data preset accepts at most 64 MiB of Memory/Combined allocation; larger Data presets retain the 128 MiB maximum. The UI shows applicable limits and the API rejects excessive settings.

The replica comparison keeps two calculation processes total: two in one container, or one in each container. Adding the second instance doubles Compute CPU/memory allocation; measured speedup is not guaranteed. Original timed CPU work and Data network downloads continue using the primary Compute instance.

Preset application preserves tracing mode and uses existing images (`--no-build`), keeping image identity constant across comparisons. Startup can rebuild after code changes. The scripts verify Docker's applied ceilings and worker-reported cgroup limits before enabling Start. The UI displays limits read-only; resource changes are deployment operations.

Deployment changes reject active experiments. A durable maintenance flag blocks new Starts during recreation, including after a controller restart. Failed deployments remain visibly pending. Recover using `./scripts/start.ps1 -Preset baseline -Tracing`; a successfully prepared deployment can resume safely. No named volumes are deleted.

One experiment runs at a time. Refreshing or closing the browser does not cancel it. Cancellation preserves partial counters. History records starting/running/stopping and completed/cancelled/failed/interrupted outcomes.

Combined Data holds memory while downloading payloads from Compute and performing MongoDB write/read cycles. Network experiments create container-to-container traffic: Data receives and Compute transmits. Achieved operation rates are recorded separately from configured target rates.

The control panel shows workload settings/results; resource graphs are in Grafana. Collection/refresh happens every five seconds, with 30-second CPU/network rate windows. Allow 10–30 seconds for changes. CPU is in cores, memory in MiB, traffic in bytes/second. Collection health describes the cAdvisor scrape, not every application's health.

Application graphs use two-minute rate/latency windows. Short Start requests and long background execution have separate duration measurements. Status polling is visible by route; health checks, scrapes, and assets are excluded. Run IDs are stored in history/traces, never metric labels. See [metric definitions](docs/metrics.md).

Tracing follows **Controller → Data child → Compute and MongoDB** for Combined workloads. It records the whole experiment and selected I/O cycles (at most one per second), plus every failed cycle. All operations still contribute to metrics. Traces take a few seconds to appear and are retained for about 24 hours; history and trace IDs last longer. An old or interrupted trace may be missing or partial. Tracing status means configuration is enabled, not proof that every span reached storage.

## Demonstrate from PowerShell

```powershell
./scripts/demo.ps1 -Workload cpu -Profile high -DurationSeconds 30
./scripts/demo.ps1 -Workload memory
./scripts/demo.ps1 -Workload network
./scripts/demo.ps1 -Workload database
./scripts/demo.ps1 -Workload combined
# All five, sequentially with cooldowns:
./scripts/demo.ps1 -Workload all
```

## Architecture and source guide

```text
Browser → Flask Controller → Compute / Data → MongoDB
                                ↓ actual container resources
                              cAdvisor → Prometheus → Grafana
Flask / child operation metrics ──────────→ Prometheus → Grafana
Flask / child traces → OTel Collector → Tempo → Grafana
```

| Service | Responsibility | CPU limit | RAM limit |
|---|---|---:|---:|
| controller | UI, global run slot, history/export | 0.5 | 256 MiB |
| compute | CPU work and internal payload endpoint | 1 | 512 MiB |
| data | Memory, network, database, combined | 1 | 512 MiB |
| mongodb | Summaries and temporary documents | 1 | 768 MiB |
| cadvisor | Resource collection | 0.5 | 256 MiB |
| prometheus | Metric storage | 1 | 768 MiB |
| grafana | Resource/application dashboards and traces | 0.5 | 512 MiB |
| otel-collector (tracing) | Bounded trace buffering/export | 0.5 | 256 MiB |
| tempo (tracing) | Single-instance local trace storage | 1 | 768 MiB |
| compute-2 (replica) | Explicit second calculation instance | 1 | 512 MiB |

- `services/shared`: presets, validation, worker lifecycle, actual workloads, internal endpoints.
- `services/controller`: coordinator, MongoDB repository, public API, HTML, JavaScript, and CSS.
- `services/compute` and `services/data`: small worker entry points.
- `services/tests`: automated tests; run inside the controller container.
- `services/Dockerfile`, `requirements.txt`, `gunicorn_conf.py`: shared build/dependencies/server settings.
- `monitoring`: Prometheus and provisioned Grafana resources.
- `scripts`: deployment, demonstrations, verification, and evidence collection.
- `docs/master-plan.md` and the five stage records: roadmap and verified implementation history.
- `docs/evidence`: original Stage 1 evidence; `stage2` through `stage5` subfolders preserve subsequent evidence.

Each Flask service runs one Gunicorn application process with eight request threads. Supervisors start once in that process. Do not increase application worker counts: coordination and locks are process-local. Disposable workload processes have independent deadlines and explicit cleanup.

CPU presets use 25/50/90% busy time; memory 32/64/128 MiB; network payloads 64/256/1024 KiB; rates 2/5/10 per second; database payloads 4/16/64 KiB. A database cycle is one write plus one read. At most 128 temporary document slots are reused per run and cleaned afterward. Advanced limits are available from `/api/workloads`.

## HTTP API

Example Start body:

```json
{"workload":"memory","profile":"medium","duration_seconds":30,"overrides":{"memory_mib":96},"name":"Memory comparison","notes":"Same duration, larger buffer"}
```

| Method/path | Behaviour |
|---|---|
| `GET /health` | Controller liveness, independent of MongoDB |
| `GET /metrics` | Prometheus metrics; also internal on Compute and Data |
| `GET /api/workloads` | Presets, limits, availability, active run |
| `GET /api/deployment` | Selected preset, expected/effective limits, instance/image identities, tracing and verification status |
| `POST /api/deployment/prepare` | Script maintenance coordination; durable flag required, active experiments rejected |
| `POST /api/runs` | Validate/start asynchronously; HTTP 202 and ID |
| `GET /api/runs/active` | Active run or null |
| `GET /api/runs/<id>` | Configuration, progress, outcome, Grafana URL |
| `POST /api/runs/<id>/stop` | Idempotent cancellation |
| `GET /api/runs` | History with page/page_size and workload/state/q name filters |
| `GET /api/runs/export.csv` | All summaries matching the same filters |

The synchronous public Stage 1 workload interface is retired. Scripts now use this run API. Compute's bounded payload endpoint is internal.

Run responses additionally contain `application_grafana_url`, nullable `trace_id`, and nullable `trace_url`. CSV appends `trace_id`. Existing records without traces remain readable/exportable. `/api/workloads` includes `observability.tracing_enabled`. Private W3C context is retained for recovery but omitted from public run records and CSV.

Stage 4 adds `target_services`, an immutable `deployment` snapshot, and fixed-work algorithm/assignment/batch/instance results. CSV appends those JSON fields. Old records have unknown deployment metadata; no history migration is required. CPU comparison example: `{"workload":"cpu_fixed","profile":"medium"}`. Omit `duration_seconds` or set it to 180; other values are rejected.

## Outages and persistence

MongoDB stores summaries at state transitions and completion. Live progress is served from workers/controller, not written every second. Normal stop/start preserves history, metrics, Grafana settings, and Tempo traces.

During a MongoDB outage, Database/Combined are unavailable. CPU/Memory/Network remain usable; up to 100 unsaved summaries remain in memory. The UI marks pending history. CSV includes pending summaries, which are retried when MongoDB reconnects. They can be lost if the controller restarts before persistence.

Controller restart cancels leftover activity and reconciles outcomes. Worker restart marks its affected experiment interrupted; work is never automatically replayed. If either worker cannot be reached, new starts are blocked until its state is known.

Collector/Tempo outages do not stop workloads. Export queues and timeouts are bounded; some spans can be lost. Exporter diagnostics go to service logs separately from child result messages, preserving workload outcomes. Metrics counters reset with a service process; they are not reconstructed from MongoDB history. Hard-killed children may lose their last unreported interval (normally approximately one second).

## Stop, restart, reset

```powershell
./scripts/stop.ps1
./scripts/start.ps1
# Or restore the nine-service baseline configuration:
./scripts/start.ps1 -Tracing
```

Offline startup after building images:

```powershell
./scripts/start.ps1 -NoBuild
./scripts/verify.ps1
# Explicit offline configuration:
./scripts/start.ps1 -Preset replica-2 -Tracing -NoBuild
```

A deliberate reset deletes metrics, Grafana data/accounts/settings, MongoDB experiment history, and Tempo traces:

```powershell
./scripts/reset-data.ps1 -ConfirmDataDeletion
```

Source files and `.env` remain. Reset is not normal shutdown.

## Verification

```powershell
./scripts/verify.ps1
docker compose run --rm --no-deps controller python -m unittest discover -s tests -v
python ./scripts/verify-stage3.py
# Resource/replica acceptance (applies presets and restarts services):
python ./scripts/verify-stage4.py
# Read-only checks for the visual revision, guides and saved examples:
python ./scripts/verify-stage5.py
```

Live scripts require host Python 3.10+, existing built images, and no experiment active. Stage 4 acceptance takes several minutes, exercises all named presets, temporarily restarts workers/controller, verifies both tracing modes, and finishes on baseline with tracing. Its results go to `docs/evidence/stage4`; previous evidence is preserved. Older live scripts remain available, but rerunning one overwrites its own evidence directory.

Stage 5 collection refuses to overwrite an existing experiment set. See the [evidence index](docs/evidence/stage5/README.md) for repeat commands and the optional local plotting environment. The application itself needs no plotting packages, external fonts or new containers.

## Troubleshooting and local-lab boundaries

- Inspect failures with `docker compose ps --all` and `docker compose logs --tail 80 SERVICE`.
- Only Controller/Grafana/Prometheus publish ports, on IPv4 loopback. Scripts use `127.0.0.1` to avoid the measured Windows localhost connection delay.
- cAdvisor needs privileged host/runtime access. Application containers have no Docker socket or host filesystem access. Keep the deployment local and trusted.
- MongoDB has no host port and uses no authentication on this local Compose network. Do not publish its port. Its 0.25 GiB cache is not a total process-memory limit.
- For missing graphs, inspect Prometheus Targets and cAdvisor logs. A healthy exporter alone does not prove per-container data. CPU queries require `cpu="total"`; cAdvisor disables per-core series deliberately.
- Idle traffic can correctly be zero. Watch Data receive traffic during network experiments. Root aggregates, loopback, and stale containers are excluded.
- Reload Grafana after restart. Edit provisioned dashboard JSON for permanent changes.
- Selected deployment state, the last successful configuration and generated scrape targets live in ignored `.runtime/`. It contains no Grafana credentials. Scripts mount runtime configuration read-only into Controller/Prometheus. Do not manually edit it during experiments.
- Raw `docker compose up` does not select the saved override/profile state. Prefer startup/apply scripts; `scripts/common.ps1` and Python verification helpers centralize that selection.
- Normal startup reloads Prometheus/Grafana configuration because edits inside bind mounts do not trigger Compose recreation. Switching tracing modes can recreate app containers; finish/stop an experiment first.
- If a trace is missing, check Collector and Tempo logs and retry after ingestion. The Tempo data source remains provisioned in metrics-only mode, but trace storage is stopped and the application hides trace buttons.
- Docker statistics and Grafana differ in cache accounting and sampling. Short health-check processes can cause baseline CPU/memory spikes.
- Grafana optional plugin downloads/updates are disabled; the dashboard uses built-in Prometheus support.

See [Stage 3 evidence](docs/stage-3.md), [Stage 4 implementation](docs/stage-4.md), [revised Stage 5](docs/stage-5.md), and the [preset guide](docs/presets.md).
