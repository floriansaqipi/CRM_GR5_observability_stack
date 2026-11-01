# Metric glossary

## Three independent measurement paths

- Container resources: cAdvisor → Prometheus → Grafana. CPU cores, memory working set, and real network bytes include application/telemetry overhead.
- Application metrics: each Flask parent process exposes `/metrics` → Prometheus → Grafana. Disposable children send cumulative counts and fixed latency buckets to their parent.
- Traces: Flask and children → Collector → Tempo → Grafana. Readable traces contain selected successful I/O cycles; metrics count all reported operations.

Prometheus adds fixed `project`, `service`, and `instance` target labels. Application labels have bounded values: route templates, method, status, workload, operation, and outcome. IDs, names, notes, URLs, and settings are not labels.

| Metric | Unit / meaning |
|---|---|
| `lab_http_requests_total` | Response count by method, route template, and status. Includes status polling; excludes health, scrapes and assets. Unmatched paths share `unmatched`. |
| `lab_http_request_duration_seconds` | Histogram from request entry until response headers are ready. CSV streaming time after headers is excluded. |
| `lab_runs_active` | Controller owns an experiment in starting/running/stopping state. Use the Controller series. Worker registries expose zero-valued controller gauges; do not sum them to infer worker counts. |
| `lab_runs_total` | Controller-observed terminal transitions by workload/outcome. History reads and save retries do not increase this count; previously completed recovered results are not counted again. |
| `lab_workload_active` | Worker owns a submitted child action. Use Compute/Data series. |
| `lab_workload_duration_seconds` | Worker histogram including child startup, execution and cleanup. Exact elapsed child work stays in run history. |
| `lab_workload_operations_total` | Successful CPU batches, full network responses, database writes/reads/completed cycles. Failed calls have outcome `error`; cycle failures use operation `cycle`. A cycle failure and a failed call can describe the same failure and must not be added together. |
| `lab_workload_network_bytes_total` | Bytes actually read by Data, including partial transfers. Excludes HTTP/TCP overhead. |
| `lab_workload_io_duration_seconds` | Full streamed transfer or database-call duration, grouped by operation and success/error. All calls contribute regardless of trace selection. |
| `lab_workload_elapsed_seconds` | Latest child elapsed time while active; zero after reaping the child. |
| `up{job="applications"}` | Prometheus can scrape an application exporter. Does not establish that MongoDB or a workload is healthy. |

HTTP histogram bounds: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5 seconds and infinity. I/O adds the same bounds. Workload-duration bounds: 1, 5, 15, 30, 60, 120, 180, 210 seconds and infinity.

Counts reset when the owning application process restarts. Prometheus `rate` handles resets; no metrics are rebuilt from history. A hard kill can lose the last unreported child interval. Compare exact before/after counters for verification: Prometheus `increase` extrapolates at range boundaries and can return fractional values.

p95 is an estimate from buckets. Sparse requests/jobs produce coarse estimates, and no observations produce unavailable values. Application dashboards use two-minute windows; resource dashboards use 30-second windows. A run's Grafana time window selects aggregate measurements, not an exclusive per-run time series, so preceding activity can contribute to rate calculations.

CPU busy time is an input setting, not a guaranteed measured CPU percentage. Network payload throughput differs from cAdvisor interface throughput because the latter includes protocol/other service traffic. MongoDB client spans measure driver calls, not server-internal execution phases.

## Stage 4 allocation and fixed-work measurements

`cpu_fixed` uses two calculation processes in total. Each worker aggregates cumulative snapshots from its own slots before merging new observations into its registry. Repeated progress/final messages do not add work twice. With two replicas, sum the two service series to obtain total throughput; the Controller counts the parent outcome once.

- `lab_workload_operations_total{workload="cpu_fixed",operation="cpu_batch",outcome="success"}` counts actual calculation units. The historical `cpu_batch` label is retained for compatibility; one fixed logical batch contains 2,500 units.
- `lab_workload_operations_total{workload="cpu_fixed",operation="logical_batch",outcome="success"}` counts completed logical batches. Partial units contribute to the first counter, but unfinished batches do not contribute to this counter.
- Checksums, batch assignments, IDs and exact deployment limits are saved in experiment history. They are not Prometheus labels.

Quota-relative CPU is consumed cores divided by the positive CPU quota/period ratio. Memory utilization is working-set bytes divided by a positive finite memory limit. Missing, zero or unlimited limits produce unavailable values. These ratios describe container allocation, not utilization of the entire laptop.

Throttled-period percentage divides the rate of throttled scheduling periods by the rate of all scheduling periods. Throttled seconds per second is a separate duration rate. Neither is a CPU-utilization percentage.

The underlying counters and resource gauges are documented in [cAdvisor's Prometheus metric reference](https://github.com/google/cadvisor/blob/master/docs/storage/prometheus.md).

The resource dashboard retains 30-second averages and adds a recent-CPU panel using the last two observations (`irate` within a 30-second lookback, normally about five seconds apart). A short two-core job can finish inside the averaging window, so its 30-second average may remain below one core even while it consumes more than one core. Live validation records recent CPU, the longer average, and an independent Docker statistics sample.

Expected application targets are generated from the selected preset. Collection health uses fresh `up` samples (less than 15 seconds old), excluding retired target samples left after recreation. Historical series remain available in earlier time ranges. Container-resource queries select recent cAdvisor series and exclude host/root aggregates.
