# Deployment presets

Build once with `./scripts/start.ps1 -Preset baseline -Tracing`. Apply subsequent configurations with `./scripts/apply-preset.ps1 -Preset NAME`. Apply preserves tracing and image identities; changes require an idle experiment slot. One preset is active at a time.

The scripts merge the base Compose file and one named override in that order, following [Docker's Compose merge rules](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/). Use the scripts so the saved configuration, enabled profiles and expected monitoring targets stay consistent.

| Name | Primary Compute CPU / memory | Data CPU / memory | Compute instances |
|---|---|---|---:|
| baseline | 1 / 512 MiB | 1 / 512 MiB | 1 |
| cpu-05 | 0.5 / 512 MiB | 1 / 512 MiB | 1 |
| cpu-1 | 1 / 512 MiB | 1 / 512 MiB | 1 |
| cpu-2 | 2 / 512 MiB | 1 / 512 MiB | 1 |
| memory-256 | 1 / 512 MiB | 1 / 256 MiB | 1 |
| memory-512 | 1 / 512 MiB | 1 / 512 MiB | 1 |
| memory-1024 | 1 / 512 MiB | 1 / 1,024 MiB | 1 |
| replica-1 | 1 / 512 MiB | 1 / 512 MiB | 1 |
| replica-2 | 1 / 512 MiB each | 1 / 512 MiB | 2 |

CPU comparison always uses two direct supervised calculation subprocesses total. A single Compute container receives both slots. Two Compute containers receive one slot each. Numbered batches are assigned round-robin and never automatically retried or redistributed. The second instance has a separate `compute-2` identity in Prometheus, cAdvisor, traces and history.

For the allocation/replica comparison, leave the work amount at Medium: 32 logical batches, 2,500 calculation units each, 80,000 units total. Each unit evaluates the existing 3,000-value sum-of-squares calculation. The expected completed checksum is 12,007,132,800,000. The CPU ceiling controls available time; the work amount never adapts to the ceiling. A 180-second independent deadline bounds execution.

For memory comparisons, select Memory, Medium (64 MiB), 30 seconds. Keep the same settings at 256/512/1,024 MiB ceilings. Smaller allocations are permitted; the 256 MiB preset rejects allocations above 64 MiB in Memory and Combined modes. A higher ceiling alone does not cause an application to allocate more memory.

The UI records verified limits at Start. `/api/deployment` reports expected and effective worker resources, cgroup version, enabled targets, preset, generation and image IDs. Scripts independently inspect Docker's NanoCpus and memory ceilings. This machine uses cgroups v1; the reader also supports cgroups v2.

CPU graphs retain usage in cores and add quota-relative utilization. Memory utilization uses working set divided by the container ceiling. The throttled-period percentage describes scheduling periods affected, not CPU utilization; throttled seconds per second is a separate quantity. Missing/zero/unlimited denominators are unavailable. Aggregate Compute panels combine current instances and exclude stale container IDs.

Deployment preparation writes a durable pending flag before requesting the controller's global lock. An active experiment rejects the operation and restores the old state. Successfully prepared changes remain fenced across restarts until Docker, cgroups, scrape targets and dashboards verify. On failure the UI shows maintenance/error details. Run `./scripts/start.ps1 -Preset baseline -Tracing` to recover. A concurrent deployment process is rejected through an exclusive file lock.

`./scripts/start.ps1 -NoBuild` restores the last successful configuration offline. `-Tracing` enables tracing and `-NoTracing` disables it explicitly. Normal shutdown stops every profile and preserves volumes. Destructive reset is a separate command and deletes history, metrics, Grafana state and traces.

Stage 4 provides acceptance examples. The revised Stage 5 adds four single-run baseline examples, clearer visuals and practical guides; see [the results](experiment-results.md). A formal three-repetition allocation/replica study remains future work. Keep tracing constant and capture baselines/cooldowns for that study. Replica-2 increases total allocation, so its findings must not be described as equal-resource scaling efficiency.
