# Cloud Lab — authoritative technical handoff

## Purpose, current status and source hierarchy

The university assignment is **Lab 1: Resource Monitoring Dashboard for Cloud Applications**: monitor CPU, RAM and network use of VMs or containers in real time, using Prometheus, Grafana and Flask. This project implements the container option as a local Docker Desktop laboratory on Windows. It is not a public-cloud deployment, a Kubernetes installation, an IoT system or a GPU workload application.

Stages 1–5 are implemented. The revised Stage 5 produced the dark control interface, two improved Grafana dashboards, four single-run examples and practical repository/classroom guides. Subsequently, the Albanian university report was written chapter by chapter and completed with an abstract, numbered references and citations. The report is **25 pages**, has **16 image placeholders**, and still needs cover identities/logo and the actual image insertion. A formal repeated experiment study and PowerPoint presentation remain future work.

The package is a snapshot, not a live connection. Its manifest identifies the Git revision, working-tree state, build time and file hashes. Archived evidence was recorded on **1 November 2026**; it must not be presented as a new run. The current live deployment is deliberately not queried or changed by packaging.

Use current source/configuration to determine implementation, archived results for measured outcomes, and the current Word file for figure numbers and placement. Some stage records and the original master plan still say that university documentation is future work; those sentences describe their earlier milestone, not the report's current status. The three water-quality images influence appearance only. Earlier messages and the original water-quality Word template are not needed to understand this package.

## Implemented stages

| Stage | Delivered behaviour |
|---|---|
| 1 | Flask Compute, cAdvisor, Prometheus, Grafana; genuine per-container CPU/memory/network metrics; bounded demonstrations and readiness checks |
| 2 | Controller, Data and MongoDB; interactive workload controls, asynchronous execution/cancellation, history/export and restart recovery |
| 3 | Direct application metrics, optional Collector/Tempo, trace continuity through request threads and disposable processes |
| 4 | Deployment presets, durable maintenance/limit verification, fixed-work calculations, optional Compute-2 and per-instance aggregation |
| 5, revised | Improved interface/dashboard presentation; four baseline examples, archived evidence, results report and practical guides |
| Later documentation | Completed Albanian abstract and chapters I–V; 15 references, 22 cited paragraphs and sixteen documented image slots |

CPU comparison was introduced in Stage 4; the Stage 2 controller originally offered five choices. Six workload choices exist in the final application. Do not infer an unfinished stage from an endpoint's retained `stage: 4` health metadata or an image tag containing `stage4`.

## Host, services and deployment

The recorded host is Windows 11 Pro, AMD Ryzen 7 4800H (8 cores / 16 logical processors), about 16 GB RAM. Docker uses Linux containers. The inspected tools were Docker Engine 29.5.2, Compose 5.1.4 and PowerShell 7.6.5. Startup/verification/shutdown now also support Windows PowerShell 5.1. The JSON reader handles nested maps/arrays and writes UTF-8 without BOM; compatible cryptographic APIs generate the local Grafana password.

The Compose project is `cloud-lab1`. Seven services run without tracing; adding Collector and Tempo gives nine. Enabling Compute-2 gives eight or ten. The baseline uses one Compute instance. Distinct service identity is retained in metrics, traces, history and resource queries.

| Service | Responsibility | Baseline CPU / memory ceiling |
|---|---|---|
| controller | Flask UI/API; validation, one global run, worker coordination, persistence and export | 0.5 core / 256 MiB |
| compute | Timed CPU and fixed calculations; bounded binary payload endpoint | 1 core / 512 MiB |
| data | Memory, download, database and Combined workloads | 1 core / 512 MiB |
| mongodb | `lab.runs` history and `lab.workload_documents` temporary documents | 1 core / 768 MiB |
| cadvisor | Independently observes container CPU, memory and interfaces | 0.5 core / 256 MiB |
| prometheus | Scrapes cAdvisor, itself and Flask exporters; stores time series | 1 core / 768 MiB |
| grafana | Displays resource/application dashboards and Tempo traces | 0.5 core / 512 MiB |
| otel-collector | Optional `tracing` profile; receives/batches/forwards spans | 0.5 core / 256 MiB |
| tempo | Optional `tracing` profile; stores/query traces | 1 core / 768 MiB |
| compute-2 | Optional `replica` profile; separately identified Compute instance | 1 core / 512 MiB |

Configured memory ceilings total 3.5 GiB without tracing, 4.5 GiB for baseline with tracing and up to 5 GiB for the supported larger presets. These are ceilings, not current consumption or reserved RAM. Host/Docker overhead is additional.

The internal bridge network is named `lab` in Compose. Host publications are bound to IPv4 loopback: Controller 5000, Grafana 3000, Prometheus 9090 and MongoDB 27017. The latter was added for local Compass inspection using `mongodb://127.0.0.1:27017/lab`; no authentication is configured for this local MongoDB. Do not draw MongoDB as inaccessible from the host. Compute and Data have no published host port. All three Flask services listen on container port 5000. Collector uses internal OTLP/HTTP 4318 and health 13133; Tempo uses internal OTLP/HTTP 4318 and query/readiness HTTP 3200. cAdvisor is scraped internally on 8080.

Named volumes retain MongoDB history, Prometheus samples, Grafana state and Tempo data. Prometheus retains seven days or 1 GiB, whichever limit removes older data first; Tempo retention is approximately 24 hours. A saved trace screenshot/JSON survives independently of live Tempo retention. Monitoring configuration is mounted read-only. The applications do not receive the Docker socket; only scripts manage deployment. cAdvisor has the privileged host/runtime/cgroup access needed to measure the Linux containers.

MongoDB's WiredTiger cache is explicitly set to 0.25 GiB. This is not its total memory ceiling or total working set. Deleting workload documents does not promise an immediate return of MongoDB memory to its earlier baseline.

## Application graph and three telemetry graphs

Application: user/browser → Controller → Compute for CPU, or Controller → Data for data workloads. Data downloads bounded payloads from primary Compute and writes/reads temporary MongoDB documents. Controller separately saves run summaries to MongoDB. Network workloads keep using primary Compute even when Compute-2 is enabled.

Resource metrics: actual Linux containers → cAdvisor → Prometheus → Grafana Container Resources. cAdvisor observes resource activity; the application does not report its own CPU percentage as resource truth.

Application metrics: Controller/Compute/Data, and optional Compute-2 → their `/metrics` endpoints → the same Prometheus service → Grafana Application Performance. Prometheus adds fixed project/service/instance target labels. It does not send metrics into Collector in this implementation.

Traces: Flask application workers and disposable workload children → OpenTelemetry Collector → Tempo → Grafana trace exploration. The MongoDB client calls are PyMongo spans created in Data/Controller. MongoDB itself has no added tracing agent and no server-to-Collector arrow. Grafana queries Prometheus/Tempo; it does not scrape the applications directly.

Existing diagrams repeat Prometheus/Grafana in separate lanes to explain their roles. Those boxes are views of the same services, not multiple deployed instances. Keep the application-only Figure 1 distinct from the observability Figure 2.

## Run lifecycle, API and browser behaviour

Flask templates, CSS and lightweight JavaScript implement the UI. There is no React frontend. The browser polls run status about once a second; refresh/closing the browser does not cancel server work. Resource graphs stay in Grafana. The UI reports states through text as well as colour, including idle, running, stopping, interrupted, maintenance and connection loss.

Each Flask service uses **one Gunicorn application worker with eight request threads**. Work runs in disposable processes, not additional Gunicorn application workers. Gunicorn's master, container init and health probes mean a raw process count is not equal to calculation concurrency.

Start validates workload, profile, duration, overrides, optional name and notes. It resolves and saves the complete settings, checks dependency availability/effective memory cap, and acquires the global experiment slot. `POST /api/runs` returns HTTP 202 promptly with the run ID; the run proceeds asynchronously. A concurrent Start returns 409. Invalid input is 400; unavailable prerequisites are 503. State/detail reads do not replay a job.

States are `starting`, `running`, `stopping`, then `completed`, `cancelled`, `failed` or `interrupted`. A run need not pass through stopping when it finishes normally. Internal Start is idempotent only for the same run ID and matching work/settings/assignment; conflicting reuse is rejected. Work with ambiguous acknowledgement is not automatically retried.

Public APIs expose workload catalog, verified deployment, active run, run detail, Start, Stop, paginated/filterable history and CSV. The exact routes and CSV fields are extracted into the generated facts section. Internal worker endpoints expose state/configuration and Start/Stop. The internal bounded payload endpoint is `GET /workloads/network?size_kib=...`; Stage 1's public synchronous workload endpoints were retired.

Stop is idempotent. For fixed work, participating workers are cancelled concurrently. Workers enforce their own deadlines, use bounded dependency timeouts, terminate stubborn children and reap them. The requirement is cleanup within five seconds; the records demonstrate specific tested cases, not an unconditional timing claim for every possible host failure. Preserve known partial counters/batches; hard termination can lose the final unreported progress interval. A deadline is failed; worker restart is interrupted.

## Workloads, profiles and fixed calculations

Timed workloads default to 30 seconds, range 15–180. Low/Medium/High resolve CPU busy time to 25/50/90%, memory to 32/64/128 MiB, network payload to 64/256/1024 KiB, rate to 2/5/10 per second and database payload to 4/16/64 KiB. Applicable advanced overrides replace preset values before saving.

Limits: CPU busy time 10–95%; memory 1–128 MiB; network payload 1–1024 KiB; rate 1–20 requests/cycles per second; database payload 1–64 KiB. If Data's ceiling is 256 MiB, Memory and Combined allocations are capped at 64 MiB; larger ceilings permit the normal 128 MiB maximum.

- **CPU:** one child alternates short busy/idle cycles. `cpu_batches` counts elementary repeated calculations, not the fixed comparison's logical batches. Requested busy time is an input; measured CPU includes scheduling and service/telemetry overhead.
- **Memory:** Data allocates/touches the buffer in 4 KiB steps during allocation, holds it, and releases it by child exit. Container working set includes the interpreter and libraries, not just the requested buffer.
- **Network:** Data streams bounded responses from primary Compute and discards them. Count successful full responses and all bytes actually read, including partial failed transfers. Data receives; Compute transmits. Interface counters also include protocol/control traffic.
- **Database:** Data performs paced writes and matching reads. A successful cycle contains one write and one read; keep their counters separate. At most 128 reusable temporary document slots per run bound document count.
- **Combined:** Data holds its memory buffer while performing the paced network and database work. It reports counters separately and cleans temporary documents at the end.
- **CPU comparison (`cpu_fixed`):** fixed calculation work rather than editable duration. Low/Medium/High means 16/32/64 logical batches; advanced count 4–64. The API accepts omitted duration or exactly 180 seconds as a safety deadline.

The fixed algorithm is `sum-squares-v1`: one unit evaluates `sum(n*n % 104729 for n in range(3000))`, checksum 150,089,160. A logical batch is 2,500 units. Medium is 32 batches / 80,000 units / completed checksum **12,007,132,800,000**.

There are **two calculation processes total**. With one Compute, both slots receive alternating batch lists. With two instances, each runs one slot; numbered batches alternate between Compute and Compute-2 (16 each for Medium). Batch IDs are zero-based: Medium has IDs 0–31; primary Compute receives the even IDs and Compute-2 the odd IDs. With one Compute, its first slot receives the evens and its second the odds. Assignment is resolved/saved before dispatch; slots process assigned lists sequentially. Per-child cumulative checkpoints are aggregated before registry updates. Accept each batch once; preserve partial units and completed batches after failure/cancellation; do not redistribute work automatically.

Deployment CPU presets change Compute to 0.5/1/2 cores while holding 512 MiB. Memory presets change Data to 256/512/1024 MiB with one core. Replica-2 gives each Compute one core and 512 MiB, increasing total Compute allocation from 1 core/512 MiB to 2 cores/1024 MiB. Constant calculation concurrency does not make it an equal-resource scaling experiment.

## Deployment maintenance, recovery and history

Use the existing PowerShell scripts to merge the base Compose file and one preset override. They preserve tracing mode during apply, restore the last successful configuration at ordinary startup, generate only the enabled application scrape targets, and stop disabled optional services. First startup defaults to baseline without tracing.

A durable pending-maintenance file fences new Starts. Preparation checks the active run under the controller's lock; a conflict rejects the change. Scripts apply containers, inspect Docker limits, compare worker-reported effective cgroups limits and verify monitoring before releasing maintenance. The installed environment uses cgroups v1; the reader supports v2 as a fallback. A failed deployment remains visibly fenced with an error and recovery command. No application has Docker daemon control.

MongoDB keeps `runs` separate from `workload_documents`, with timestamps/indexes and normal explicit cleanup plus an auxiliary TTL index. Saved records include resolved settings, immutable deployment snapshot, target service(s), timestamps, state, counters, rates, errors, trace association, and fixed-work assignment/checksums/per-instance results. CSV appends structured JSON fields while retaining old fields. Older records remain readable with unknown deployment/empty trace metadata.

If MongoDB is unavailable, CPU, Memory and Network remain available. Database and Combined do not. Controller keeps up to 100 unsaved summaries in memory, permits their export and retries persistence; a restart may lose unsaved summaries. `saved` and `pending` must remain distinguishable. On restart, Controller reconciles enabled workers, recovers completed results where possible and cancels previous-session activity as interrupted without repeating work. An unreachable participant blocks new experiments until its state is established.

Normal shutdown preserves volumes. Destructive reset is a separately named command. Do not run operational/reset commands merely because they appear in the source appendix. Preparing this image bundle performs no deployment or workload operations.

## Metrics, Grafana and tracing interpretation

Prometheus scrapes every five seconds, timeout four seconds. cAdvisor collection is also five seconds. Resource CPU/network rates use 30-second windows; the recent CPU panel uses the last two observations (`irate` within a 30-second lookback). A short two-core job can consume more than a core even if its 30-second average stays below one. Application rates and p95 panels use two-minute windows. Both dashboards refresh every five seconds and default to the last fifteen minutes.

Resource panels show CPU cores, working-set MiB and directional byte rates; allocation panels show CPU/quota and working-set/limit ratios, throttled-period percentage and throttled seconds per second. Throttling is not CPU utilization. Missing/unlimited denominators and absent observations are unavailable; valid zero remains zero. Queries select this Compose project, fresh/current container series and appropriate interfaces, excluding host aggregates, retired targets and duplicates. Historical observations remain available for their earlier windows.

Application HTTP metrics exclude `/health`, `/metrics` and static assets but include status polling by normalized route template. Prometheus labels do not contain run IDs, names, notes or raw URLs. Parent registries merge only the delta in cumulative child counters/histogram buckets. Repeated progress/final messages must not duplicate work. Controller counts each observed parent terminal outcome once; history reads and persistence retries do not count outcomes. Counters reset at process restart; saved history is the durable run record. The full glossary and exact dashboard expressions are included below.

For `cpu_fixed`, metric operation `cpu_batch` retains its historical name but counts actual calculation units; `logical_batch` counts completed 2,500-unit batches. Sum Compute and Compute-2 for aggregate fixed-work throughput. Do not sum error-call and error-cycle counters as though they were unrelated failures. p95 comes from histogram buckets and is approximate, especially with sparse observations.

Tracing is optional, while application metrics are always enabled. OpenTelemetry initializes after Gunicorn forks and independently inside each workload child. W3C context is carried across controller threads, internal HTTP and process startup. A short Start request contains an `experiment.run` span that remains open through the terminal outcome; worker/process spans connect the background execution. Representative successful I/O is detailed for the first cycle and at most one per second afterward. Omitted cycles carry non-recording context; all failed cycles get error spans. Metrics still count every reported operation.

Health/scrape/routine status/ping activity is excluded from traces; request/response bodies and database statement contents are not captured. MongoDB client spans measure driver calls, not server-internal phases. Collector batching, memory limits, queues, retry and exporter timeouts are bounded; telemetry outages must not change workload results or extend Stop. A crash can leave an incomplete trace; do not fabricate missing spans. The saved Combined JSON/screenshot is independent of whether its live trace has expired.

## Saved observations and limits of the conclusions

The generated facts section contains exact records and calculated display values for all four Stage 5 scenarios and the Stage 4 comparisons. Each Stage 5 scenario ran once on verified baseline with tracing, unchanged application images, at least 30 seconds idle observation and at least 30 seconds cooldown. Query samples are five seconds apart. CPU/interface peaks from those plots are **30-second averages**, unlike Stage 4's recent-CPU peaks. Memory summaries are baseline median → sampled peak → final cooldown median.

CPU completed 44,953 elementary calculation cycles. Memory held 64 MiB and touched 16,384 pages; Data working set rose beyond the buffer size because the child runtime/telemetry also uses memory, and then fell near baseline. Network received 150 responses / 39,321,600 payload bytes (37.50 MiB). Combined received the same payload total and completed 150 database cycles (150 writes and 150 reads). All four were completed/saved with zero reported operation errors. The saved Combined trace has 142 connected spans.

Stage 4 verified identical fixed work/checksum at 0.5, 1 and 2 CPU and with one/two instances. Memory comparisons held the same 64 MiB buffer for 30 seconds across three ceilings. These are acceptance observations, not a repeated statistical performance study. Different ceilings do not force additional consumption. A larger aggregate replica allocation can reduce observed time without proving equal-resource scaling efficiency.

Thirty-one automated regression tests are distinct from 140 Stage 4 live checks, 22 historical dashboard checks, 20 lifecycle checks, 127 final Stage 5 checks, and 46 document checks. The package reads their archived results; it does not rerun these suites. No claimed uncertainty interval, guaranteed speedup or production performance conclusion follows from the single-run examples.

## Repository map and independent use

Read the Controller app/coordinators for the public API, lock/state machine, dispatch, multi-instance results and recovery. Read `shared/model.py` for validation/public run links; `worker.py` and `workload_child.py` for timed execution; `fixed_work.py`, `fixed_runner.py` and `fixed_child.py` for deterministic assignment and supervision. `metrics.py`, `io_stats.py` and `tracing.py` implement the three application telemetry concerns. `deployment.py` reads limits/configuration without controlling Docker.

Compose/preset files define services and allocations. Monitoring files provision scraping, dashboards, Collector and Tempo. Tests document edge cases. Operating scripts handle startup, presets, verification and demonstrations. The saved plotting script uses archived measurements, but its original default output paths rewrite evidence/Markdown when run: a future redraw must use a separate working copy/output and must not overwrite originals.

The package's `source/` snapshot preserves relative repository paths and complete application/configuration/tooling files. Original evidence, PNG/SVG diagrams and CSV/JSON samples are there. The master context includes full source/configuration and document-text appendices so initial Project uploads remain useful without attaching hundreds of files. For pixel-level work, attach the specific original image/data paths listed in the relevant figure entry. Historical absolute paths inside old logs are provenance, not required locations on the new computer.
