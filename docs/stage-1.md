# Stage 1 — Implementation and Verification

**Status: complete and running locally.**

## Goal

Run four containers and show real CPU, RAM, and network measurements in a provisioned Grafana dashboard. This is the minimum working assignment deliverable; later services are intentionally deferred.

## Implemented architecture

The compute service runs bounded child processes. cAdvisor collects Linux container counters and gauges. Prometheus scrapes every five seconds and preserves project/service labels. Grafana displays the same expressions used by the acceptance measurement script.

The Docker Desktop compatibility gate required explicitly disabling per-core CPU metrics (`--disable_metrics=percpu`) so the selected `cpu="total"` series exists. Network metrics use the verified `eth0` interface. Freshness filtering prevents old containers from contributing current values after recreation.

The first recorded workload sequence passed CPU and memory checks but failed the network-rate threshold. Investigation found that three new Python HTTP connections to `localhost` took 6.146 seconds, compared with 0.011 seconds to `127.0.0.1`. Scripts now use the explicit IPv4 loopback address matching the published bindings. The initial run is retained as `evidence/initial-localhost-run.json`; the final `measurements.json` is collected after this correction.

## Tested versions

| Component | Version |
|---|---|
| Docker Engine | 29.5.2 |
| Docker Compose | 5.1.4 |
| Python image runtime | 3.13.18, Debian Bookworm slim |
| Flask | 3.1.3 |
| Gunicorn | 26.2.0 |
| cAdvisor | 0.60.6 |
| Prometheus | 3.15.1 |
| Grafana | 13.3.0 |

Image digests are pinned in Compose and the Dockerfile. All installed Python application dependencies are pinned in `requirements.txt`. No moving `latest` image tags are used.

## Verification checklist

- [x] Compose configuration validates; all four services deploy.
- [x] Real CPU, RAM, receive, and transmit series exist for compute.
- [x] All four services are individually identifiable by Compose labels.
- [x] Grafana data source and five-panel dashboard are provisioned.
- [x] Invalid inputs and payload limits are covered by automated tests.
- [x] Concurrent workload rejection, deadline termination, shutdown cleanup, and normal child reaping are covered by automated tests.
- [x] Live CPU, memory, and network rise/recovery checks recorded: all six checks pass.
- [x] Live Gunicorn shutdown during work verified: interrupted request returns 503, container exits normally in 1.724 seconds, no OOM kill.
- [x] Normal stop/start persistence verified: historical sample unchanged; Grafana login and dashboard survive.
- [x] Baseline, complete workload sequence, all-service view, and Flask screenshots visually inspected.

## Evidence

Final workload sequence recorded on **2026-11-01**, completing at **02:08:10 Europe/Budapest** (01:08:10 UTC). The run used the default one-core / 512 MiB compute limit and 30-second workloads with baseline/cooldown intervals. This is one acceptance run, not the repeated comparative experiment planned for Stage 5.

| Measurement | Recorded result |
|---|---|
| Baseline CPU, last sample | 0.057 cores |
| CPU workload sampled peak | 1.000 cores |
| CPU after cooldown | 0.068 cores |
| Baseline memory, last sample | 55.71 MiB |
| Memory workload sampled peak | 120.98 MiB with a requested 64 MiB buffer |
| Memory after cooldown | 46.73 MiB |
| Network transmit sampled peak | 1,060,867 bytes/s, approximately 1.06 MB/s |
| Network after cooldown | 0 bytes/s |
| Network workload | 140 responses, 36,700,160 payload bytes in 30.161 seconds; approximately 4.64 requests/s |

The CPU action completed 25,908 calculation batches in 30.001 seconds. The memory action touched 16,384 pages and completed in 30.038 seconds. These are observed results on this laptop, not guaranteed performance targets.

Grafana's more finely spaced historical query shows a network maximum of **1.22 MB/s** in the saved screenshot. The host acceptance script's more widely spaced samples captured a 1.06 MB/s maximum; both query the same underlying metric, at different evaluation times.

Docker statistics independently showed **99.84% CPU** during computation and **120.4 MiB** during the memory hold. Network counters increased from approximately 3 kB to 36.9 MB over the network demonstration. Idle CPU/memory samples sometimes include the short Python health-check process; this explains small baseline spikes and why memory can recover below the initial baseline. CPU sampling windows and cache accounting differ between Docker statistics and Grafana.

Evidence files:

- `evidence/measurements.json`: timestamped values, exact dashboard queries, workload summaries, Docker statistics, and all six successful assertions.
- `evidence/measurements.csv`: the same sampled resource values in tabular form.
- `evidence/lifecycle.json`: seven successful live checks and the historical sample before/after restart.
- `evidence/deployment.json`: all four healthy services, enforced CPU/RAM limits, and no OOM kills.
- `evidence/initial-localhost-run.json`: retained first-run failure and measurements before the connection fix.
- `evidence/grafana-baseline.jpg`: Grafana restricted to the final run's baseline interval.
- `evidence/grafana-workloads.jpg`: Grafana showing the complete final acceptance sequence.
- `evidence/grafana-all-services.jpg`: all four monitored services selected.
- `evidence/flask-home.jpg`: verified Flask landing page.

Automated tests: five passed after the pinned-dependency build (5.494 seconds). Prometheus configuration passed `promtool check config`. PowerShell scripts passed syntax parsing. The live lifecycle test recorded seven successful checks in `evidence/lifecycle.json`. The full restart used `--no-build --pull never`; internet connectivity itself was not disabled during testing.

The PowerShell network demo was also exercised separately for three seconds: 14 successful responses, 3,670,016 payload bytes, and 4.58 achieved requests/s. The final verification script passed after the workload run.

## Operating boundaries

One active CPU/memory workload, one Gunicorn process, maximum 60 seconds, maximum 128 MiB allocation, maximum 1 MiB network response. There is no background job database, distributed queue, web workload-control panel, tracing, or autoscaling in this stage.

Normal shutdown preserves named volumes. A separate reset script requires an explicit deletion switch. Credentials remain in ignored `.env`, not in evidence files.
