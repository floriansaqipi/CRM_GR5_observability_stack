# Cloud Resource Monitoring and Workload Laboratory — Master Plan

## Purpose

Meet the professor's Lab 1 requirement: monitor actual CPU, RAM, and network use of containers using Prometheus, Grafana, and Flask. Extend the verified foundation into a small, understandable resource-management laboratory.

Deployment is local Docker Desktop/WSL2 on a Ryzen 7 4800H laptop with approximately 16 GB RAM. It is not a public cloud deployment. GPU workloads, Kubernetes, autoscaling, and a separate React frontend are outside the agreed scope.

**Current status:** Stages 1–5 implemented and verified on 2026-11-01, with Stage 5 revised to focus on visual improvements, four example experiments and practical guides. The final deployment is verified baseline with tracing enabled. Start with the [repository guide](repository-guide.md), [classroom demo guide](classroom-demo.md) and [example results](experiment-results.md). The [Stage 5 record](stage-5.md) links the verification evidence.

## Five stages

1. **Working container monitoring:** Flask compute container, cAdvisor, Prometheus, provisioned Grafana dashboard, bounded demonstrations, startup/shutdown scripts, and measured acceptance evidence. See `stage-1.md`.
2. **Interactive workload application:** standalone Flask HTML controller, Data service, MongoDB, CPU/memory/network/database workloads, asynchronous run states, cancellation, bounded concurrency, and stored experiment summaries.
3. **Application metrics and traces (complete):** HTTP/job metrics directly scraped by Prometheus; OpenTelemetry Flask/Requests/PyMongo instrumentation and explicit workload spans; Collector and Tempo through a tracing profile; connected Controller → Data → Compute/MongoDB trace. See `stage-3.md`.
4. **Resource limits and replicas (complete):** repeatable Compose presets, one-variable-at-a-time CPU/memory allocation comparisons, optional second compute container, round-robin batch routing, per-instance and aggregate monitoring. The detailed proposal is in `stage-4-plan.md`, and the implemented/verified record is in `stage-4.md`. Two calculation processes per Compute container are supported, with two processes total held constant across comparisons.
5. **Visual improvements, examples and practical guides (complete):** polished dark Flask interface and grouped Grafana dashboards; four single-run CPU/Memory/Network/Combined examples with saved measurements, annotated plots and a connected trace; an understandable repository guide and approximately ten-minute classroom walkthrough. See [Stage 5](stage-5.md).

## Architectural boundaries

- Flask controls workloads; Grafana owns monitoring and visualization.
- cAdvisor → Prometheus supplies actual container resources.
- Flask → Prometheus supplies application metrics in Stage 3.
- Flask → OpenTelemetry Collector → Tempo supplies traces in Stage 3.
- MongoDB stores workload documents and experiment summaries; it is not the metrics or trace store.
- Keep code small and explainable. Add dependencies only for a demonstrated requirement.
- Resource allocations are deployment settings; the web application does not receive Docker daemon control.

## Grafana commitment

The Stage 1 dashboard is a core deliverable, not a placeholder. It provides CPU cores, memory working set, receive/transmit rates, service filtering, and collection health. Its detailed design and later application/experiment panels will be refined in subsequent stages.

## Stage gates

Complete and verify each stage before adding the next. Document real measurements and limitations; never substitute fabricated graphs or performance claims. Stage 1–5 implementation records are complete. The four Stage 5 examples demonstrate observable behaviour and do not establish statistical performance conclusions.

## Remaining work outside the revised Stage 5

- A formal repeated experiment study, including three repetitions per comparison, controlled conditions and analysis.
- The official university Word report and PowerPoint presentation, following the professor's submission requirements.

The Markdown guides and short results report are practical project materials. Academic submission documents will be prepared separately when requested.

