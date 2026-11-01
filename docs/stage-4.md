# Stage 4 — Resource Allocation and Replica Experiments

**Status: implemented and verified on 2026-11-01. Final deployment: baseline with tracing enabled.**

## Implemented design

Nine named presets select source-controlled Compose overrides. CPU comparisons change Compute's CPU ceiling; memory comparisons change Data's memory ceiling. `compute-2` is an explicit optional replica using the primary Compute image. Other workloads keep their original routing and limits.

Deployment scripts share preset/profile selection. They retain the last successful configuration, support explicit tracing choices and offline/no-build startup, generate the expected application scrape targets, and preserve monitoring/database/trace volumes. Preset changes use existing images to keep comparison identity constant.

A durable read-only runtime configuration fences new Starts before deployment preparation checks the global active-run slot. Conflicting changes restore the prior state. A successfully prepared change stays fenced across recreation and failures. Docker inspection and worker cgroup readings must agree before monitoring verification and maintenance release. cgroups v1 and v2 are supported; the installed Docker Desktop uses v1.

The new `cpu_fixed` action uses algorithm `sum-squares-v1`: one unit evaluates `sum(n*n % 104729 for n in range(3000))`; one logical batch contains 2,500 units. Low/Medium/High select 16/32/64 batches, with advanced count 4–64. The default 32 batches mean 80,000 units with expected checksum 12,007,132,800,000. The action completes on work completion and has a fixed 180-second safety deadline.

Two direct subprocesses are used globally. One instance owns two slots; two instances own one slot each. The assignment is frozen before dispatch. Each slot handles its batch list sequentially, reporting cumulative counts and checksums plus bounded batch results. The parent aggregates child snapshots before updating metrics. Internal duplicate Starts compare the complete settings/assignment and do not spawn more processes.

The controller coordinates both participants as one experiment. Stop fans out concurrently; every direct calculation child is terminated/reaped. Failed, interrupted and cancelled runs retain known partial counters. An unavailable worker blocks new work until reconciled. A lost acknowledgement is never retried automatically. Controller recovery cancels orphan work, reconstructs available results and retains trace association without replay.

For the 256 MiB Data preset, Memory/Combined allocation is capped at 64 MiB; at larger limits the previous 128 MiB maximum remains. Resource changes stay in deployment scripts; application services have no Docker access.

## Application and monitoring

The read-only deployment card shows the preset, effective CPU/memory and verification/maintenance state. CPU comparison displays work amount, completed batches, actual units/checksum, and per-instance counts. Run details expose the saved deployment and batch results. Existing timed experiments remain available.

`GET /api/deployment` reports preset, expected/effective resources, identities, image IDs, tracing and verification status. `POST /api/deployment/prepare` requires a durable pending flag and rejects active/recovering experiments. Existing run endpoints handle the new workload. Public run representations remove private coordination/context fields.

New histories save deployment snapshots, target services, algorithm/version, assignment, batch results and per-instance results. CSV appends these JSON fields; old records have unknown deployment metadata. Prometheus labels remain bounded and contain no run/batch IDs.

Grafana adds quota-relative CPU, memory-limit utilization, throttled-period percentage, throttled duration, aggregate Compute CPU and aggregate calculation throughput. Existing resource/application dashboards and per-instance selectors remain provisioned. Targets are generated only for enabled instances. Traces include one span per logical batch and preserve context across both services and calculation processes.

## Verification and evidence

Run the isolated automated suite:

```powershell
docker compose run --rm --no-deps controller python -m unittest discover -s tests -v
```

After building images, run live acceptance with no active experiment:

```powershell
python scripts/verify-stage4.py
```

The script applies every preset, performs identical fixed-work and memory comparisons, exercises cancellation and maintenance conflicts, restarts the controller/second worker, checks tracing modes, validates graphs/history/CSV, and restores baseline with tracing enabled. Its final step runs `verify-stage4-dashboard.py` to validate provisioned queries over the actual CPU/replica experiment ranges. This catches query syntax and historical rendering failures as well as current-sample failures. Evidence is written to `docs/evidence/stage4` without replacing Stage 1–3 evidence.

### Verified measurements — 2026-11-01

The automated suite passed **31 tests**, including the retained Stage 2–3 regression tests. The full live suite passed **140 checks**, and historical dashboard verification passed **22 checks**. Browser verification covered Start, active-run refresh, Stop, completion, details, service/time links and a filtered CSV download.

A further **20 lifecycle checks** verified exact per-instance calculation/logical-batch counter deltas, one Controller outcome, responsive health, seven-service startup, the original timed Combined workload, temporary document cleanup, and persistence through normal shutdown/restart. The shutdown assertion initially treated Docker's empty output line as a service; the check now ignores blank lines. Every container had stopped correctly. The initial transcript and resumed checks are retained.

Each CPU/replica acceptance case completed 32 batches / 80,000 calculation units with checksum **12,007,132,800,000**, using two calculation processes total and the same Compute image ID.

| Preset | Reported worker elapsed | Peak recent cores per instance | Batch distribution |
|---|---:|---:|---|
| cpu-05 | 68.643 s | 0.502 | 32 on primary, two slots |
| cpu-1 | 31.064 s | 1.003 | 32 on primary, two slots |
| cpu-2 | 14.884 s | 1.929 | 32 on primary, two slots |
| replica-1 | 31.922 s | 1.001 | 32 on primary, two slots |
| replica-2 | 15.664 s | 0.998 primary / 1.000 second | 16 on each instance, one slot each |

Docker statistics independently measured **1.971 cores** during the two-core case. These are single acceptance runs on this laptop, with tracing enabled, and are not formal benchmark estimates. The replica case increases total Compute allocation from one core/512 MiB to two cores/1,024 MiB.

All memory cases held **64 MiB for 30.001 seconds**. The sampled Data working-set peaks were 164.5 / 171.0 / 166.5 MiB at the 256 / 512 / 1,024 MiB ceilings respectively. Working set includes the application, child interpreter and telemetry; it is not just the requested buffer. No observed container was OOM-killed.

Replica Stop completed in **1.054 seconds**, with zero remaining calculation processes and accurate partial counters. Active experiments rejected preset changes. Controller and second-worker restarts produced interrupted outcomes, retained trace IDs and did not replay work. The replica trace contains **42 connected spans**, including **32 batch spans** and distinct `compute` / `compute-2` identities.

Both tracing modes passed, as did generated target counts, actual Docker/cgroup limits for all nine presets, immutable saved configuration, old-history compatibility and CSV contents. Earlier Stage 1 measurements, Stage 2 history and Stage 3 traces remain available. Baseline tracing configures **4.5 GiB** of memory ceilings; the largest supported preset configures **5 GiB**.

The final readiness check passed with **nine running containers**, three healthy application scrape targets, verified baseline limits, zero active or unsaved runs, zero calculation processes and zero temporary workload documents. Python dependency consistency and JavaScript/PowerShell syntax checks passed. Saved Stage 4 batch results, traces and application metrics survived the normal stop/start.

Validation exposed and corrected three monitoring issues: retired `up` samples after target recreation, a grouping modifier syntax error in the new ratio queries, and use of a 30-second average to detect a job shorter than that window. Fresh-target checks, explicit grouping syntax and recent-CPU/Docker samples now cover those cases. Earlier failed attempts are retained separately; `acceptance.json` is the completed run.

### Saved deliverables

- [Live results and complete saved runs](evidence/stage4/acceptance.json), [automated test output](evidence/stage4/unit-tests.txt), [historical query checks](evidence/stage4/dashboard-verification.json).
- [Preset guide](presets.md), [metric glossary](metrics.md), [setup guide](../README.md).
- [Browser comparison](evidence/stage4/workload-comparison.jpg), [full application](evidence/stage4/workload-laboratory-full.jpg), [quota panels](evidence/stage4/cpu-quota-panels.jpg), [connected replica trace](evidence/stage4/replica-trace.jpg).
- [Full experiment CSV](evidence/stage4/experiment-history.csv), [filtered browser CSV](evidence/stage4/browser-export.csv), [browser checks](evidence/stage4/browser-checks.json), [browser runs](evidence/stage4/browser-runs.json).
- [Raw connected replica trace](evidence/stage4/replica-trace.json), containing every recorded batch span.
- [Final lifecycle checks](evidence/stage4/lifecycle.json), [verified final state](evidence/stage4/final-state.json), [batch-result example](evidence/stage4/batch-result-example.json).

See the [evidence index](evidence/stage4/README.md) for final lifecycle results and batch-result examples.

## Boundaries

CPU/memory ceilings are allocation settings, not predicted usage. Replica-2 doubles Compute's allocated cores and memory. Resource samples and latencies include Python, telemetry and scheduling overhead. A hard-killed process may lose its last unreported interval; partial results do not invent missing work. A higher limit or second instance is not a guarantee of speedup.

The subsequent Stage 5 revision focuses on visuals, four example runs and practical guides; see [its implementation record](stage-5.md). Formal repetitions, statistical analysis, the official Word report and presentation remain future work. See `presets.md` for the operational guide and `stage-4-plan.md` for the original proposal.
