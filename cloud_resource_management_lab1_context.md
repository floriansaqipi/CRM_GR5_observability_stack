# Cloud Resource Management — Lab 1 Project Context & Handoff

> **Purpose:** This document transfers the context, ideas, requirements, and decisions from an earlier ChatGPT planning conversation to another coding assistant (e.g., Codex or Astra). It is a **project brief and working plan**, not a statement that the system has already been implemented.
>
> **Project status as of 2026-11-01:** Planning/discovery only. **No project files, services, dashboards, experimental results, or deployment have been created or verified yet.**

## 1. Academic context

- **Degree:** Master's in computer / software engineering.
- **Course:** *Resource Management in Cloud Computing*.
- **Assignment:** Lab 1, a group project.
- **Professor's original assignment description (verbatim):**

  > **Lab 1: Resource Monitoring Dashboard for Cloud Applications**  
  > **Description:** Build a dashboard to monitor CPU, RAM, and network usage of VMs or containers in real-time.  
  > **Subject:** Monitoring, visualization.  
  > **Tools:** Prometheus, Grafana, Flask.

- **Evaluation/deliverables reported by the student:**
  1. A practical working solution, with a clearly stated problem and explanation of how it was solved.
  2. An MS Word document describing the work (including the problem, implementation, results, and structure).
  3. A classroom presentation based on the document.
  4. Ability to answer questions and discuss the implementation.

### Explicit assignment scope vs. assumptions

**Required by the professor's written text:**
- Monitor actual **CPU, RAM, and network** usage.
- Monitor **VMs or containers**.
- Show measurements on a dashboard, updating in **near-real-time**.
- Address **monitoring and visualization**.
- Use the named tools: **Prometheus, Grafana, Flask** (the professor did not specify the precise responsibilities of each).

**NOT explicitly required:**
- Hosting on AWS/Azure/GCP.
- Kubernetes, autoscaling, orchestration, or real cloud billing.
- Multiple monitored targets (though multiple containers make a stronger demonstration).
- Database, distributed traces, OpenTelemetry, or alerts.
- Any specific dashboard refresh interval, metric thresholds, workload size, or report outline.

The student asked whether to use Azure or local resources. The selected direction is **build entirely locally with Docker**, while designing it to resemble a small cloud application environment. Azure was discussed as an optional later deployment but is **not part of the current plan**. Do not assert that local Docker equals a real public cloud deployment.

## 2. What the student wants to build

**Working title:** *Cloud Resource Monitoring and Workload Simulation Platform*.

Rather than showing arbitrary CPU/RAM graphs, build a **functional local application** in which a user can:
- Select between **two kinds of simulated applications/workloads**, each with different resource profiles.
- Start, stop, and configure **bounded background workloads**.
- Choose workload intensity and experiment with **different CPU/memory container limits**.
- Observe how **CPU, RAM, and network** usage changes on real containers.
- Observe **HTTP latency, throughput, errors, custom job metrics**, and optionally distributed traces.
- Compare repeatable experiments and explain results in the master's report/presentation.
- Demonstrate a noticeable change live in class (e.g., CPU load, memory growth, MongoDB calls, network traffic, resource throttling).

**Primary design principle:** Meet the professor's simple monitoring requirement first, then add features that make resource-management experiments scientifically meaningful. Avoid an elaborate stack that interferes with reliability or the classroom demo.

## 3. Local hardware and deployment assumptions

- **Student's available laptop:** AMD **Ryzen 7 4800H**, **16 GB RAM**.
- **Deployment:** Local **Docker Compose** environment with containers; no public cloud needed.
- Host operating system **not confirmed**. A previous discussion mentioned the possibility of Windows + Docker Desktop + WSL2, but do **not** assume that is the student's OS. Ask/check before providing host-specific commands.
- Aim for a modest memory footprint. Earlier rough planning suggested budgeting approximately **6–8 GB for the lab containers**, subject to actual measurement and tuning; this is an estimate, **not** a hard requirement or measured footprint.
- If using Windows/Docker Desktop/WSL2, note that monitoring cgroups and cAdvisor behavior can differ from native Linux. **Validate per-container metrics early**. The measured Linux container environment is not necessarily the Windows host's overall CPU/RAM usage.
- Keep the demo robust, safe, offline-capable once images are pulled, and possible to restart quickly.

## 4. Proposed system architecture

Two distinct concerns:

1. **Application/workload control:** A small Flask-based control panel and two monitored services to generate predictable resource consumption.
2. **Observability:** Container resource metrics via cAdvisor/Prometheus, application metrics, and optional OpenTelemetry traces via Collector/Tempo, all visualized in Grafana.

```text
                          STUDENT / DEMO OPERATOR
                                     |
                                     v
                         Flask workload-control UI
                           (start / stop / profiles)
                                     |
                      +--------------+--------------+
                      |                             |
                      v                             v
                Application A                  Application B
                CPU-intensive                 Data / IO-intensive
             calculations, jobs            memory, network, MongoDB
                      |                             |
                      |                         MongoDB container
                      |                             |
                      +------------+----------------+
                                   |
                   +---------------+----------------+
                   |                                |
                   v                                v
              Container metrics              App telemetry
             (CPU, RAM, network)       (HTTP, custom metrics, traces)
                   |                                |
                cAdvisor                OpenTelemetry SDK / libraries
                   |                                |
                Prometheus                  OTLP -> OTel Collector
                   |                                |
                   |                       +--------+---------+
                   |                       |                  |
                   |                 metric export      traces export
                   |                       |                  |
                   +----------------> Prometheus           Tempo
                                           |                  |
                                           +--------+---------+
                                                    |
                                                  Grafana
                                          (dashboards & traces)
```

**Architecture notes:**
- The exact metric ingestion path is still a design choice. A clean **initial implementation** is:
  - **cAdvisor → Prometheus scrape** for actual per-container CPU/RAM/network.
  - **Flask Prometheus `/metrics` → Prometheus scrape** for custom app/HTTP/job metrics.
  - **Flask OpenTelemetry traces → OTLP → Collector → Tempo** for distributed tracing.
- An **advanced optional path** is to export OTel application metrics via OTLP through the Collector and ingest them into Prometheus with compatible receiver/export settings. Do not assume this works automatically without configuration.
- **MongoDB is an application workload database**, not the Prometheus metrics database and not the Tempo trace store.
- Avoid duplicating charts in the Flask UI: Flask primarily controls experiments; **Grafana is the real monitoring dashboard**.
- Do not expose Docker daemon control or unauthenticated Prometheus/Grafana services on the public network. Prefer localhost bindings or SSH tunnel where relevant.

## 5. Proposed applications and simulated workloads

### Application A — CPU-intensive Flask service

- Offers HTTP endpoints for compute operations (e.g., prime calculations, matrix calculations, synthetic CPU work).
- Supports bounded, controlled background jobs (asynchronous from the HTTP request lifecycle).
- Profiles: low/medium/high intensity, adjustable duration and concurrency.
- Use **separate worker processes** / multiprocessing for parallel CPU-bound Python tasks when needed, not a naive assumption that extra Python threads automatically use all cores.
- Observable effects: CPU utilization, throttling under cgroup limits, throughput, execution duration, request latency.

### Application B — Data-intensive Flask service

- Runs bounded jobs involving memory allocation, network calls/transfers, and MongoDB read/write operations.
- Supports low/medium/high intensity and a defined duration.
- Can call another Flask service for **cross-service trace propagation** (one realistic distributed request chain).
- Observable effects: memory growth, network transmitted/received bytes, database latency, request rate, and traces.
- Safeguard against uncontrolled memory usage or indefinite allocations; include automatic cleanup on stop/timeout.

### Example demonstration workload profiles (illustrative only)

| Profile | CPU work | Memory work | Incoming request rate |
|---|---|---|---|
| Low | 1 worker/job | ~64 MB | ~5 requests/s |
| Medium | 2 workers/jobs | ~128 MB | ~20 requests/s |
| High | 4 workers/jobs | ~256 MB | ~50 requests/s |

These are **starting examples**, not guaranteed CPU percentages, actual throughput, or required values. The system needs to **measure the actual outcomes**. Set hard safety caps based on the laptop's available resources.

### Proposed UI

A small custom web application with:
- Service selector: Compute service / Data service.
- Workload intensity: Low / Medium / High (possibly manual tuning later).
- Run duration (e.g., 15–180 seconds for classroom demo).
- Start/Stop controls and current run status.
- Workload profile / selected resource-limit preset.
- Link/shortcut to Grafana dashboards.
- The UI is a **control panel**. Grafana handles time-series exploration and dashboards.

A design mockup was discussed but **no actual frontend has been implemented**.

## 6. Container resources and experiments

The student wants the project to cover **resource management**, not only passive monitoring. A strong way to do that while staying within scope is to **compare workloads under different resource allocations**, using Docker resource constraints.

Suggested experimental matrix:

| Experiment | Container CPU limit | Container RAM limit | Target workload |
|---|---|---|---|
| A | 0.5 vCPU | 256 MB | Same fixed load |
| B | 1.0 vCPU | 512 MB | Same fixed load |
| C | 2.0 vCPU | 1 GB | Same fixed load |

**Measure:**
- Actual container CPU usage/utilization.
- CPU throttling (`container_cpu_cfs_throttled_*` or equivalent available cAdvisor metrics).
- Memory working set / usage and container memory limit.
- Network receive/transmit bytes or per-second throughput.
- Request throughput and response-time distributions (including p95).
- Job execution duration and success/failure counts.
- Any OOM kills or resource-limit failures.

**Experimental cautions:**
- Experiment configurations are proposals, not finalized hardware-safe settings.
- Hold workload and other experimental conditions constant where comparing resource limits.
- Repeat runs and collect actual results; **never present invented measurements**.
- Some Docker Compose CPU/memory limit changes require containers to be recreated; a Flask control UI should not promise seamless live changes to these settings. Use preset Compose configurations or a controlled orchestration layer for recreations.
- Compare simple metrics to sensible units/denominators: CPU percent relative to quota vs host, memory bytes vs limit, network bytes/sec, not raw cumulative byte counters.
- Do not accidentally create a denial-of-service against the laptop. Use limited concurrency, deadlines, memory caps, and safe cancellation.

**Illustrative classroom demo:**
1. Start low-intensity baseline and show stable Grafana CPU/RAM/network graphs.
2. Increase CPU workload; verify CPU rises.
3. Compare the same workload at 0.5 vs 2.0 vCPU and show job completion time / throttling differences.
4. Trigger a data-intensive workload to produce memory/network/MongoDB activity.
5. Select a distributed trace to show Flask → Flask → MongoDB latency attribution.

## 7. Planned technology stack and responsibilities

| Technology | Responsibility | Priority |
|---|---|---|
| Docker + Docker Compose | Local infrastructure / resource limits | Core |
| Flask (Python) | Control panel, workload services, API | Core — professor named it |
| cAdvisor | Real per-container CPU/RAM/network metrics endpoint | Core supporting tool |
| Prometheus | Scrape and store time-series metrics | Core — professor named it |
| Grafana | Dashboards and resource visualization | Core — professor named it |
| MongoDB | Realistic database/IO workload for service B | Extension |
| OpenTelemetry Python SDK + instrumentations | HTTP metrics/traces, outgoing calls, PyMongo spans | Extension |
| OpenTelemetry Collector | Receive OTLP, route telemetry | Extension |
| Grafana Tempo | Distributed trace backend | Extension |

The student **does not currently want** to add unrelated Kubernetes, Kafka, Redis, paid cloud hosting, or extra services without a compelling reason.

## 8. OpenTelemetry details discussed

The student specifically asked: **"What metrics does OpenTelemetry provide by default, and what traces does it provide by default?"**

The crucial answer: **The base OTel SDK alone does not automatically collect everything.** What is available depends on the particular instrumentation packages, semantic-convention version, enabled metrics, exporters, and runtime environment.

### Instrumentation and what to expect

| Source | Typical automatic telemetry when enabled | Not automatic / caveats |
|---|---|---|
| Flask server instrumentation | Incoming HTTP server spans; standard HTTP server metrics supported by the installed version | Endpoint timings are not custom job timings |
| Instrumented HTTP client (e.g., Requests) | Outgoing HTTP client spans, often client timing metrics depending on instrumentor/version | Need to instrument whichever HTTP client is actually used |
| PyMongo instrumentation | MongoDB client operation spans | Do not assume DB latency **metrics** come by default; some need custom histograms |
| System metrics instrumentation | CPU, memory, disk, network measurements | Must explicitly enable/configure; in Docker, scopes and cgroup visibility can vary |
| cAdvisor | Actual container resource metrics | Independent of OTel, ideal for professor's CPU/RAM/network requirement |
| Custom SDK instrumentation | Job count, active jobs, job duration, selected span attributes/events | Must be explicitly coded |

**Examples of metric names:** Standardized HTTP metrics may include `http.server.request.duration`; older instrumentation/semantic convention settings may use `http.server.duration`. System metrics in some Python instrumentation versions include `system.cpu.time`, `system.cpu.utilization`, `system.memory.usage`, `system.network.io`, etc. **Check the exact versions and actual emitted names when implementing; do not hardcode these as universal default outputs.**

### Distributed tracing example

```text
Flask A: POST /execute-job                   [SERVER span]
  -> HTTP client: POST http://flask-b/process [CLIENT span]
      -> Flask B: POST /process                [SERVER span]
          -> MongoDB: insert/find             [CLIENT DB span]
```

Successful propagation across services requires correct trace context propagation, typically W3C Trace Context through HTTP headers. All spans should share a trace ID with appropriate parent-child relationships. The trace can include durations, service names, status, and database operation details where supported.

**Not automatically traced:** Arbitrary Python functions, CPU calculations, memory allocations, or background-job lifecycle. Explicitly create custom spans (and ensure context handling) for meaningful job stages; do not treat traces as a CPU profiler or memory profiler.

### Recommended observability coverage

1. **Infrastructure:** container CPU/RAM/network + throttling via cAdvisor/Prometheus.
2. **Application performance:** HTTP rate/latency/errors; active jobs; job duration/outcomes via Flask instrumentation + custom Prometheus metrics.
3. **Tracing:** Flask A ↔ Flask B, HTTP client and MongoDB spans, plus custom workload job spans via OTel Collector → Tempo.

In other words: **Prometheus answers "what resource behavior changed?" and tracing helps investigate "where time was spent?"**

## 9. Suggested implementation sequence

The student wanted a plan; the proposed sequence was:

### Phase 1 — Must-have lab solution
- Create a reproducible Docker Compose environment.
- Run one Flask service, cAdvisor, Prometheus, Grafana.
- Confirm real per-container CPU, RAM, network series and near-real-time Grafana refresh.
- Demonstrate real resource changes, not fake data.

### Phase 2 — Interactive workload platform
- Add two example workload services (CPU and data/IO).
- Implement bounded low/medium/high profiles with start/stop and status controls.
- Add easy-to-use Flask control UI.

### Phase 3 — Application metrics + MongoDB
- Add request/active-job/job-duration metrics and representative MongoDB operations.
- Build dashboard panels for application performance as well as resource metrics.

### Phase 4 — Distributed observability
- Instrument Flask, outbound HTTP client, PyMongo, custom background jobs.
- Add OTel Collector + Tempo, configure OTLP, verify cross-service traces in Grafana.

### Phase 5 — Experiments and report/presentation
- Compare resource limits at fixed workload; document repeatable methodology.
- Capture charts, configurations, logs, and real findings.
- Prepare a well-structured Word document and a presentation.
- Plan class demonstration and possible questions/discussion.

**Do not block Phase 1 on advanced instrumentation.** A smaller, reliable implementation is preferable to an incomplete stack.

## 10. Suggested reporting/research framing

**Proposed research / investigation question:**

> How do different workload intensities and container CPU/memory resource allocations affect utilization, network traffic, application throughput, response latency, and reliability in a containerized environment?

Possible report sections (suggested, not professor-mandated):
1. Problem statement and objectives.
2. Background: containers, monitoring, Prometheus/Grafana/Flask, and optionally OTel.
3. Requirements and system architecture.
4. Implementation details, Docker Compose, metrics, tracing, workload generation.
5. Experimental design and controlled scenarios.
6. Measured results: screenshots, tables, charts, differences and limitations.
7. Discussion: effects of resource contention/limits, local vs cloud limitations.
8. Conclusion and possible future work.

The presentation should explain what was built, why each service exists, live monitoring under load, experiments and results, limitations, and practical takeaways.

## 11. Decisions made vs. remaining design decisions

### Settled direction
- **Locally hosted** on the Ryzen 7 4800H / 16 GB laptop with **Docker containers**.
- The monitoring platform should have an actual **application and workload simulation**, not just static graphs.
- Monitor **CPU, RAM, network** at minimum, with Prometheus + Grafana + Flask.
- Two contrasting example application workloads, with different configurations.
- Add realistic resource experiments under varying container CPU/memory limits.
- Interested in **MongoDB and OTel/OTLP tracing**, as useful extensions.

### Proposed, not yet finalized
- Whether the Flask UI is served by a standalone controller container or one of the two example services.
- Exact source structure and number of containers.
- Whether workloads are launched as multiprocessing jobs, a worker pool, or dedicated job containers.
- Whether to allow dynamic resource-limit adjustments or choose redeployable preset Compose profiles.
- How to generate load deterministically and whether a separate load-generator service is helpful.
- Which application metrics come via OTel vs direct Prometheus client instrumentation (avoid duplicate metrics).
- Exact OTel Collector configuration (receivers/processors/exporters), metric routing, and Tempo configuration.
- Operating system, Docker runtime specifics, resource reservation, memory safety limits.
- Graph layouts, refresh interval, sampling, retention, and expected thresholds.
- Final set of report experiments and acceptance criteria.

### Do NOT invent or assume
- That the professor requires Azure, AWS, Kubernetes, autoscaling, or real cloud infrastructure.
- That everything in this plan is already implemented.
- That OpenTelemetry instruments arbitrary code or cgroups automatically.
- That a simulated workload's target RPS is its actual achieved RPS.
- That container CPU percentages equal whole-machine CPU percentages.
- That there are preexisting experimental results, code repository, or finalized architecture decisions.

## 12. Guidance for a coding assistant continuing this project

When continuing with this brief:

1. Treat this as **context for an upcoming implementation**, not a command to silently create everything without discussion.
2. Help choose a **minimal viable architecture first** and explain tradeoffs when needed.
3. Start with the professor's mandatory components and verify every data path end to end.
4. Prefer **reproducible Docker Compose**, small Python services, simple UI, readable configuration, sensible naming, and minimal operational overhead.
5. Preserve **separation of concerns**: control plane vs workload services vs collection/storage/visualization.
6. Use **real measured metrics** and reproducible experiments, not synthetic numbers shown as monitoring results.
7. Place safety guardrails around CPU stress, memory allocation, number of workers, runtime, and container limits.
8. Provide clear startup/shutdown/reset instructions and troubleshoot on Windows/WSL2 vs Linux when relevant.
9. Keep the whole solution feasible on **16 GB RAM**.
10. Make it easy to document and demo academically; every extra service should have a clear educational purpose.
11. At the beginning of an implementation session, confirm the host OS and any other genuinely blocking information, but avoid repeatedly asking for requirements already captured here.
12. If the student requests code, aim for an **end-to-end runnable MVP** first before layering MongoDB/OTel/Tempo.

## 13. Suggested immediate continuation

A good next step with Codex/Astra is:

> "Using this project brief, propose the final MVP architecture, repository structure, Docker Compose services and resource budgets for my 16 GB laptop. Prioritize the professor's CPU/RAM/network monitoring requirements, and show how we can incrementally add two workload applications, MongoDB, custom metrics, OTel Collector, and Tempo. Then help implement Phase 1 as a fully runnable local environment with verification steps."

---

**Bottom line:** This is a master's lab on **real-time monitoring of VM/container CPU, RAM, and network metrics**. The chosen project extends it into a **local Docker-based workload simulator** to study how resource constraints affect application behavior, with **Prometheus/Grafana/Flask as the core** and **MongoDB/OpenTelemetry/Tempo as deliberate optional enhancements**.
