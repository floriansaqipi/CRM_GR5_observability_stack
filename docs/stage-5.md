# Stage 5 — Visual Improvements, Example Experiments, and Practical Guides

**Status: complete and verified on 1 November 2026.**

## Delivered scope

The revised stage prioritizes a usable laboratory and understandable handoff. It adds a polished dark Flask interface, clearer Grafana layouts, four illustrative measurements, a teammate-oriented repository guide and a classroom operator's guide. The official university Word report, PowerPoint and formal three-repetition study remain future work.

The [repository guide](repository-guide.md), [classroom demo](classroom-demo.md), and [short results report](experiment-results.md) are the main human-facing deliverables. The [evidence index](evidence/stage5/README.md) explains the raw records and reproduction commands.

## Interface and dashboards

The application now uses a compact environment/deployment overview and a two-column laptop workspace, stacked below 900 pixels. Configuration keeps all six workload choices, with duration hidden for fixed work. Name/notes and advanced controls are collapsible. Result cards retain exact units/counters; large checksums span the card width. History uses readable outcome badges, filters, clear/export actions and pagination.

Details now separate the run summary, settings, verified deployment table, counters, per-instance results and batch table. The complete public JSON remains available in a collapsed advanced section. Older history without deployment snapshots remains readable. Loading, active, completed, cancelled, interrupted, maintenance and disconnection states retain explicit text; keyboard focus and narrow layouts are supported.

Both provisioned Grafana dashboards keep their original UIDs, panel IDs, data sources, selectors, measurement expressions and rate windows. Three section rows organize each dashboard. The resource view separates container activity, allocation/throttling and Compute comparisons. The application view separates HTTP, workload activity and execution/outcomes. Native panel settings improve spacing and legends, with stable service colours: Compute cyan, Compute-2 purple, Data amber and MongoDB green. Missing data remains unavailable; valid zero samples remain visible.

Public APIs, server-side workload execution, resource limits, cancellation and trace behaviour were not changed. No application dependencies, containers, external font services or frontend framework were added. Plotting uses a separate ignored host environment.

## Four measured examples

All cases used baseline with tracing enabled and frozen application/monitoring image IDs. Each Medium workload ran for 30 seconds, with at least 30 seconds of baseline and cooldown. The runs were started through the actual browser interface and tracked by the evidence collector.

| Case | Actual result |
|---|---|
| CPU | 44,953 calculation batches; sampled 30-second-average peak 0.558 Compute cores |
| Memory | 64 MiB allocated/touched; Data working set about 65.8 → 169.1 → 66.0 MiB |
| Network | 150 downloads / 37.50 MiB payload; achieved 5.000 requests/s |
| Combined | 64 MiB, 150 network responses, 150 writes and reads / 150 database cycles; achieved approximately 4.999 cycles/s |

All four completed with zero reported operation errors and saved summaries. Thirty-six collection checks passed, covering frozen images, exact settings, cleanup, resource availability, persistence, credentials and the connected trace. The Combined trace has 142 connected spans across Controller, Data and Compute, with MongoDB client operations.

Figures annotate baseline, the Controller lifecycle and cooldown, and include run IDs and sampling/averaging labels. Work elapsed is reported separately from dispatch/cleanup. Manual preparation sometimes extended idle periods; exact timestamps are preserved and the figures show the last 30 idle seconds. These observations do not establish statistical performance or scaling conclusions.

## Guides and rehearsal

The repository guide explains every service, the three observation paths, a Combined run lifecycle, fixed-work assignment, important source modules, operations, persistence and common questions. Two diagrams have Mermaid sources plus local PNG/SVG renderings.

The classroom guide provides advance/offline preparation, exact UI actions, service/panel selection, suggested explanations, observation delays, troubleshooting, export and shutdown. Its main schedule is approximately ten minutes; optional CPU/replica comparisons are separate extensions. Saved fallback views are explicitly labelled.

The four-scenario browser rehearsal/evidence window took **9.54 minutes**, including baseline, work, cooldown and operator preparation. Trace exploration, details and CSV interactions were additionally exercised. This was an operator rehearsal rather than a stopwatch measurement of a spoken presentation. Explanations can overlap the waiting intervals in the guide's ten-minute schedule.

## Verification

- All **31 existing automated tests** passed in an isolated container.
- Preflight checks confirmed preserved dashboard queries, historical numeric resource data, baseline/tracing readiness, three healthy application scrapes, Stage 1 metric history and Stage 4 saved batches.
- All six forms were checked; separate fixed-work and Database actions completed through the revised browser UI. Refresh preserved active work. A Memory action cancelled in **1.958 seconds** through the UI and released the workload.
- Laptop and narrow layouts were inspected. An absolute hidden table label initially caused page overflow; the scrolling table now contains it. The tested narrow viewport had page/content width 375/375 pixels; the laptop had 1265/1265.
- Genuine maintenance blocked Start. A controlled Controller stop, with no active run or pending result, showed connection loss and labelled the last result stale. Recovery uses the normal baseline/tracing startup procedure.
- Saved measurements, annotated plots, guide diagrams and actual Grafana screenshots were visually inspected. Plot spacing and diagram routing were corrected where labels initially overlapped.

All **127 final verification checks** passed, including historical dashboard queries, saved observations, browser exports and local document links. Eighteen browser checks passed; the browser console reported no errors or warnings at the final inspection. The [verification results](evidence/stage5/verification.json), [browser record](evidence/stage5/browser-verification.json) and [rehearsal record](evidence/stage5/rehearsal.json) preserve the details.

The [final state](evidence/stage5/final-state.json) confirms nine running services on verified baseline with tracing enabled, the same frozen image IDs, no OOM kills, idle/reaped workers, zero temporary documents and no active or unsaved result. The configured memory ceilings total 4.5 GiB. All eight final-state checks passed. Earlier data, credentials, volumes and Stage 1–4 evidence are preserved.

The official university Word report, PowerPoint and formal repeated experiment study remain outstanding outside this revised stage, as recorded in the [master plan](master-plan.md).
