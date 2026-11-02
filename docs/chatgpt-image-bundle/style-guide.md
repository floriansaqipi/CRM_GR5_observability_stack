# Visual style and output rules

The three supplied images come from another university project. Preserve their useful visual grammar: white canvas, grouped rounded rectangles, clear technology/service icons, restrained colour and labelled arrows. Do not transfer their architecture, component names, ports, measurements or claims.

| Role | Diagram colour | Examples in this project |
|---|---|---|
| User/application flow | Blue `#1D4ED8` | Browser, Controller, Compute, Data, internal HTTP |
| Persistent application storage | Green `#15803D` | MongoDB, history and temporary documents |
| Resource/application metrics | Orange `#EA580C` | cAdvisor, Prometheus, metric collection |
| Distributed traces | Purple `#7E22CE` | OpenTelemetry Collector, Tempo, span export |
| Optional or explanatory boundaries | Grey `#64748B` | Optional profile, host boundary, explanatory note |

Grafana is the presentation destination for both metrics and traces. Use a single Grafana box or clearly label repeated views as the same service. The two Prometheus appearances in the existing three-lane diagram are also one service, not two deployed servers. Similarly, MongoDB client spans do not imply that the MongoDB server exports OTLP.

Use solid directional arrows for data/requests. Label arrows with their actual purpose, such as `Kërkesa HTTP`, `Shkrim / lexim`, `Metrika` or `Gjurmë OTLP/HTTP`. If dashed outlines indicate optional services, include a short legend. Do not reuse dashed arrows to mean several conflicting things.

For Figure 1 show the application flow, leaving detailed observability to Figure 2. For Figure 2 separate the three telemetry paths without turning every dependency into a criss-crossing line. A picture should explain one idea at a time; full API descriptions belong in the report/context.

## Albanian wording

Prefer short labels: `Përdoruesi`, `Paneli i kontrollit`, `Llogaritjet CPU`, `Ngarkesat e të dhënave`, `Historiku`, `Metrikat e burimeve`, `Metrikat e aplikacionit`, `Gjurmët e shpërndara`, `Marrje` and `Dërgim`. Retain Controller, Compute, Data, MongoDB, cAdvisor, Prometheus, Grafana, Collector and Tempo as identifiable service/technology names. Preserve `ë` and `ç`.

## Size and files

- Return PNG with a white background for conceptual diagrams. Prefer a vector master rendered near 2,000–3,000 pixels wide when diagram tools support it; retain the editable source. An image-generation tool may have different native dimensions, so report the actual output rather than inventing resolution.
- Preserve native screenshot pixels. Do not repaint text, states or numeric panels to make a screenshot look more polished.
- Keep complete measured axes, legends and relevant time/service selectors. For a replot, retain the original samples and provide the plotting source.
- Use the catalog filename. Keep the Word caption separate from the pixels.
- The usable Word width is 6.5 inches (about 16.51 cm). Existing frame heights are placeholders, not permission to stretch an image. The placement guide gives an aspect-preserving fit. If labels are too small, recommend a larger image and repagination rather than removing evidence or distorting it. The existing report is 25 pages before image insertion.

The university logo and cover identities are not among these sixteen technical figures. Do not invent them.
