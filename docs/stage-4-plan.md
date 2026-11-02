# Stage 4 — Resource Allocation and Replica Experiments

**Status: historical implementation proposal.** This plan was prepared after Stages 1–3 and describes the intended Stage 4 work. Stage 4 is now implemented and verified; use [stage-4.md](stage-4.md) for the delivered behaviour and results.

## 1. Finished result and confirmed decisions

Apply a named deployment preset, see its verified limits in the web application, run a controlled experiment, and inspect per-container and aggregate behaviour in Grafana. Save the deployment settings and results together so Stage 5 can repeat the comparisons.

Confirmed: the new fixed-work CPU experiment supports up to two calculation processes per Compute container. Comparisons use **two calculation processes total**, with the same total calculation work in every configuration.

- CPU allocation: both processes run in the primary Compute container under 0.5, 1, or 2 cores.
- Replicas: two processes in one 1-core container versus one process in each of two 1-core containers.
- Memory allocation: run the same 64 MiB, 30-second Memory workload in Data under each memory ceiling.

The replica comparison increases total CPU allocation from one to two cores and Compute memory ceilings from 512 to 1,024 MiB. Its results describe that change in allocation; no speedup is assumed.

Retain one active experiment globally, existing timed workloads, history, cancellation, metrics and optional tracing. Keep one Gunicorn application process per service. Calculation processes are separate supervised subprocesses, not additional Gunicorn workers.

## 2. Deployment presets and verification

Use small, source-controlled Compose overrides selected through PowerShell. Select one preset at a time.

| Preset | Compute configuration | Data configuration |
|---|---|---|
| `baseline` | One instance, 1 CPU / 512 MiB | 1 CPU / 512 MiB |
| `cpu-05` | One instance, 0.5 CPU / 512 MiB | Baseline |
| `cpu-1` | Same as baseline | Baseline |
| `cpu-2` | One instance, 2 CPUs / 512 MiB | Baseline |
| `memory-256` | Baseline | 1 CPU / 256 MiB |
| `memory-512` | Baseline | 1 CPU / 512 MiB |
| `memory-1024` | Baseline | 1 CPU / 1,024 MiB |
| `replica-1` | Same as baseline | Baseline |
| `replica-2` | Two instances, each 1 CPU / 512 MiB | Baseline |

Declare `compute-2` explicitly under a `replica` profile, sharing the Compute image and internal API. Give it its own identity for cAdvisor, Prometheus, traces and history. Network workloads continue using the primary Compute payload endpoint.

Example interfaces:

```powershell
./scripts/start.ps1 -Preset baseline -Tracing
./scripts/apply-preset.ps1 -Preset cpu-2
./scripts/apply-preset.ps1 -Preset replica-2
./scripts/apply-preset.ps1 -Preset baseline
```

The apply script preserves the current tracing mode. First startup defaults to baseline with tracing disabled; subsequent startup restores the last successfully selected configuration unless explicitly overridden. Support explicit tracing enable/disable options. Store the selected deployment state separately from the existing Grafana credentials in an ignored local runtime directory.

Before changing containers, validate the merged Compose configuration and atomically put the controller into deployment maintenance only if no experiment is active. Reject a conflicting preset change. While maintenance is active, reject new Starts. After applying the preset, verify the actual containers, worker availability and effective limits before restoring readiness. If validation fails, retain a clear maintenance/error state with a documented recovery command.

The application receives no Docker socket or host filesystem control. Scripts use Docker inspection; each worker exposes its own effective limits through an internal configuration response. Support the installed cgroups v1 files and a cgroups v2 fallback. Record expected and verified limits, instance identities, image identity, preset and tracing mode. New runs require the expected deployment to be verified.

Generate Prometheus application targets from the enabled instance list in an ignored runtime file, mounted read-only as a directory. Disabled replicas must not appear as failed expected targets. Centralize Compose-file/profile selection for startup, shutdown, apply and verification scripts. Stop disabled optional services explicitly, and preserve all named volumes.

Seven/eight services run without tracing; nine/ten with tracing. The largest supported presets have configured ceilings of approximately **5 GiB with tracing**, below the original 6 GiB budget. Measure actual use during validation.

## 3. Fixed-work CPU execution and failure handling

Add a `cpu_fixed` workload named **CPU comparison** in the interface. Preserve the existing CPU duration/intensity action.

Use a versioned deterministic algorithm based on the existing calculation: one calculation unit evaluates `sum(n*n % 104729 for n in range(3000))`. A logical batch contains 2,500 calculation units.

- Low: 16 batches; Medium/default: 32; High: 64.
- Advanced batch count: integer 4–64. Batch size and algorithm version are fixed and saved.
- Two calculation processes total in every allocation/replica comparison.
- Independent 180-second safety deadline. Completing the fixed work ends a run immediately; the deadline is not a target duration. Timeout preserves partial results and reports failure.
- Report logical batches, actual calculation units, elapsed time and deterministic checksums. Work amount must never adapt between comparison cases.

Resolve the full batch assignment before starting: distribute numbered batches round-robin across enabled Compute instances, then across each instance's assigned calculation slots. One instance receives two slots; two instances receive one each. Each supervised subprocess handles its assigned list sequentially, avoiding process/exporter startup for every batch.

Extend the runner to own and reap all assigned subprocesses. Aggregate their cumulative progress before updating the service metrics registry, keeping separate checkpoints for each child. Report progress approximately once per second. Use stable batch identities beneath the parent run ID; never place those identities in metric labels.

Repeated internal Starts with the same ID and complete assignment return the existing experiment. A different assignment/settings under the same ID returns 409. Accept completion for each batch once. Never retry or redistribute failed or ambiguously acknowledged work automatically.

On Stop, stop scheduling new batches and cancel all participating workers concurrently. Terminate and reap every calculation subprocess within five seconds. On failure, stop remaining work and preserve completed batches and partial counters. A worker restart interrupts the parent experiment; an unreachable participant keeps new Starts blocked until reconciliation establishes its state. Controller recovery inspects all enabled instances and cancels leftover work without replaying batches.

For `memory-256`, limit Memory and Combined allocations to **64 MiB**, leaving room for Python and telemetry. Reject larger allocations before dispatch and show the applicable maximum in the interface. Keep the existing 128 MiB allocation maximum at Data ceilings of 512 MiB or higher. The acceptance comparison always uses 64 MiB, independent of the ceiling.

## 4. Application, history and Grafana changes

- Add `GET /api/deployment` for the selected preset, effective limits, enabled instances, tracing mode and verification status. Add a bounded maintenance interface used by deployment scripts to coordinate changes with Start requests.
- Extend `/api/workloads` with CPU comparison presets, limits and deployment availability. Existing Start/status/Stop/history endpoints remain the public workflow.
- New run records include an immutable deployment snapshot, `target_services`, algorithm/version, process distribution, batch assignments/results and aggregate result. Preserve the existing `target_service` field for compatibility. Append deployment and batch-result JSON columns to CSV; old records remain readable with unknown deployment metadata.
- Show the current deployment read-only on the main page. CPU comparison shows completed/total batches and per-instance counts. History/details show the saved configuration and relevant graph/trace links. Resource settings remain deployment actions.
- Propagate the parent trace into every calculation process. Add readable batch spans carrying batch and instance attributes. Count the global run outcome once in Controller; aggregate operation metrics per worker and keep instance series separate.

Extend the resource dashboard with:

- CPU cores and CPU usage relative to the verified quota.
- Working-set memory relative to the container memory limit.
- Percentage of scheduling periods throttled and throttled seconds per second.
- Per-instance and aggregate Compute CPU/operation throughput.

Use cAdvisor's existing quota, period, memory-limit and throttling series, excluding stale containers and root aggregates. Unlimited/absent denominators and missing measurements display unavailable. Throttled time is not labelled as CPU utilization. Update the application dashboard, scrape-health checks and run links for both Compute instances.

## 5. Implementation sequence and completion gate

1. Add presets, deployment state/verification and maintenance coordination.
2. Implement the fixed-work algorithm and supervised two-process execution.
3. Add explicit replica routing, aggregation and recovery.
4. Extend UI, history/CSV, metrics, traces and dashboard panels.
5. Run verification, save evidence, and restore baseline with tracing enabled.

Automated tests cover preset resolution, cgroups v1/v2 parsing, fixed-work validation/checksums, deterministic assignments, duplicate Starts/results, child aggregation, cancellation/deadlines, failure/restart reconciliation, maintenance/Start races, and older history/CSV compatibility. Keep the existing Stage 2–3 regression suite.

Live acceptance must demonstrate:

- Effective Docker/cgroup limits match every supported preset.
- Identical total calculation work/checksum completes at 0.5, 1 and 2 CPUs; two processes can use more than one core in the 2-CPU case when host capacity permits.
- One/two-replica runs keep total work and calculation concurrency constant, with each enabled instance receiving its assigned batches exactly once.
- The same 64 MiB workload completes safely at all three Data memory ceilings.
- Start/health remain responsive; Stop cleans every subprocess within five seconds.
- Worker/controller failures yield accurate interrupted/partial outcomes without replay.
- The UI, saved history, CSV, metrics and trace agree about configuration and actual results.
- Enabled targets/panels work after recreation, and tracing-enabled/disabled configurations both work.
- Existing monitoring/history/trace volumes and Stage 1–3 evidence remain available.

Save a Stage 4 implementation record, preset guide, verification JSON, batch-result examples, CSV and screenshots under a new Stage 4 evidence directory. Use one acceptance run per comparison condition here; the formal three repetitions, analysis, report and presentation remain Stage 5.

Stage 4 is complete when a user can apply a verified preset, run the same work, compare one/two instances in Grafana, and review/export the exact deployment and results.

## References

- [Docker Compose overrides](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Docker Compose service resource settings](https://docs.docker.com/reference/compose-file/services/)
- [Python process-based parallelism](https://docs.python.org/3.13/library/multiprocessing.html)
