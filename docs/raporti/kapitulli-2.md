# II. Teknologjitë e përdorura

## 2.1. Teknologjitë dhe përgjegjësitë

Laboratori përdor një grup teknologjish me përgjegjësi të ndara. Docker Compose përcakton shërbimet dhe mënyrën e lidhjes së tyre; aplikacionet Flask krijojnë dhe kontrollojnë aktivitetin; mjetet e observabilitetit e bëjnë atë të matshëm. Kjo ndarje lejon që një rezultat i raportuar nga aplikacioni të krahasohet me konsumin e vëzhguar të kontejnerit.

Tabela 1 përmbledh teknologjitë kryesore dhe versionet e konfigurimit ose të mjedisit të inspektuar. Për imazhet e infrastrukturës ruhen edhe identifikuesit digest në Docker Compose, ndërsa bibliotekat Python kanë versione të fiksuara. Këta identifikues ndihmojnë në riprodhimin e mjedisit dhe në dallimin e ndryshimit të kodit nga ndryshimi i burimeve të lejuara.

[[TABLE|1|Teknologjitë kryesore të laboratorit|1.55,1.35,3.6]]

| Teknologjia | Versioni në projekt | Përgjegjësia |
|---|---|---|
| Docker Compose | 5.1.4, plugin lokal | Nis dhe menaxhon shërbimet, rrjetin, volumet dhe profilet. |
| Python / Flask / Gunicorn | 3.13 / 3.1.3 / 26.2.0 | Ekzekutojnë Controller, Compute dhe Data; ndajnë kërkesat HTTP nga puna në sfond. |
| Jinja2 / HTML / CSS / JavaScript | Jinja2 3.1.6 | Ndërtojnë ndërfaqen dhe përditësimin periodik të progresit, pa framework tjetër frontend. |
| MongoDB / PyMongo | 8.0 / 4.19.0 | Ruajnë historikun dhe kryejnë operacionet e ngarkesave të databazës. |
| cAdvisor | 0.60.6 | Ekspozon konsumin real të CPU-së, memories dhe rrjetit të kontejnerëve. |
| Prometheus / klienti Python | 3.15.1 / 0.26.0 | Mbledhin e ruajnë metrikat e burimeve dhe të aplikacionit. |
| Grafana | 13.3.0 | Paraqet dashboard-et dhe hap gjurmët nga burimi Tempo. |
| OpenTelemetry SDK / Collector | 1.45.2 / 0.164.0 | Instrumentojnë operacionet dhe përcjellin gjurmët përmes OTLP/HTTP. |
| Grafana Tempo | 3.1.1 | Ruan gjurmët dhe i bën të kërkueshme nga Grafana. |

Flask shërben ndërfaqen dhe API-të, ndërsa Gunicorn e ekzekuton secilin aplikacion me një proces aplikativ dhe tetë fije për kërkesat. Proceset e përkohshme të ngarkesave janë të veçanta. Ky organizim ruan një pronar të vetëm për koordinimin në secilin shërbim, duke lejuar njëkohësisht kërkesa për gjendjen dhe ndalimin e punës.

MongoDB, Prometheus dhe Tempo ruajnë lloje të ndryshme informacioni: përmbledhjet e eksperimenteve, seritë kohore dhe gjurmët. Grafana i lexon burimet e veta të të dhënave, ndërsa historiku i eksperimenteve shfaqet nga Controller. Versionet në tabelë përshkruajnë konfigurimin e këtij laboratori dhe nuk paraqiten si rekomandim për versionet më të reja.

## 2.2. Konfigurimi i mjedisit punues

Mjedisi i inspektuar më 1 nëntor 2026 është një laptop me Windows 11 Pro dhe Docker Desktop me motor Linux. Kontejnerët ekzekutohen brenda mjedisit Linux të Docker-it; CPU-ja dhe memoria mbeten burime të përbashkëta të laptopit. Për nisjen dhe verifikimin përdoren skripta PowerShell nga rrënja e repository-t.

[[TABLE|2|Mjedisi punues i përdorur|2.0,4.5]]

| Elementi | Konfigurimi i inspektuar |
|---|---|
| Sistemi operativ | Windows 11 Pro, versioni 10.0.26200 |
| Procesori | AMD Ryzen 7 4800H; 8 bërthama, 16 procesorë logjikë |
| Memoria fizike | Rreth 16 GB RAM |
| Docker Engine / Compose | 29.5.2 / 5.1.4 |
| PowerShell | 7.6.5 |
| Mjedisi i aplikacionit | Imazh Python 3.13, slim-bookworm; varësitë instalohen brenda imazheve |

Kufijtë fillestarë të kontejnerëve paraqiten në Tabelën 3. Vlera CPU shpreh tavanin në bërthama, ndërsa memoria është kufi në MiB. Këto vlera nuk janë konsum i garantuar dhe nuk rezervojnë automatikisht të gjithë sasinë e shënuar.

[[TABLE|3|Kufijtë e burimeve për konfigurimin bazë|3.65,1.25,1.6]]

| Shërbimi | CPU | Memoria |
|---|---|---|
| Controller | 0.5 | 256 MiB |
| Compute | 1 | 512 MiB |
| Data | 1 | 512 MiB |
| MongoDB | 1 | 768 MiB |
| cAdvisor | 0.5 | 256 MiB |
| Prometheus | 1 | 768 MiB |
| Grafana | 0.5 | 512 MiB |
| Collector — vetëm profili tracing | 0.5 | 256 MiB |
| Tempo — vetëm profili tracing | 1 | 768 MiB |
| Compute-2 — vetëm preset-i replica-2 | 1 | 512 MiB |

Shuma e tavaneve të memories është 3.5 GiB pa gjurmim dhe 4.5 GiB me gjurmim, pa instancën Compute-2. Preset-et më të mëdha arrijnë 5 GiB me gjurmim. Përveç këtyre tavaneve nevojitet hapësirë për Windows-in dhe Docker-in. Shkarkimi dhe ndërtimi i parë kërkojnë internet; më pas mund të përdoren imazhet lokale. Kredencialet e Grafana-s ruhen në skedarin lokal .env, i cili përjashtohet nga Git.

## 2.3. Infrastruktura dhe arkitektura

Controller është pika hyrëse e përdoruesit: shfaq ndërfaqen, pranon parametrat, koordinon një eksperiment aktiv dhe ruan përmbledhjen në MongoDB. Compute kryen llogaritjet CPU dhe shërben përgjigjet binare për eksperimentet e rrjetit. Data mban buffer-in e memories, kërkon payload-e nga Compute dhe kryen ciklet shkrim/lexim në MongoDB. Compute-2 përdor të njëjtin imazh si Compute, por identifikohet veçmas kur aktivizohet krahasimi me dy instanca.

[[FIGURE|1|Arkitektura e shërbimeve të aplikacionit|docs/assets/application-architecture.png|Të duken rrjedha Controller → Compute/Data dhe lidhjet me MongoDB. Monitorimi shpjegohet në Figurën 2.|3.8]]

Arkitektura ka tri rrugë të veçanta vëzhgimi. Për burimet, cAdvisor vëzhgon kontejnerët dhe Prometheus e lexon çdo pesë sekonda. Për metrikat e aplikacionit, Prometheus lexon drejtpërdrejt endpoint-in /metrics të Controller, Compute dhe Data. Për gjurmët, aplikacionet dërgojnë span-e te Collector, i cili i përcjell te Tempo; Grafana i hap ato për eksperimentin përkatës.

[[FIGURE|2|Rrjedhat e metrikave dhe gjurmëve|docs/assets/telemetry-paths.png|Të dallohen burimet → cAdvisor → Prometheus, aplikacionet → Prometheus dhe gjurmët → Collector → Tempo; Grafana shërben për vëzhgim.|3.8]]

Pa gjurmim ka shtatë kontejnerë; me profilin tracing ka nëntë. Preset-i replica-2 aktivizon edhe Compute-2, duke dhënë përkatësisht tetë ose dhjetë kontejnerë. cAdvisor ka qasje të privilegjuar në mjedisin Linux të Docker-it për matjet. Aplikacionet Flask nuk marrin Docker socket dhe nuk ndryshojnë vetë alokimin e burimeve. Ndryshimet e vendosjes kryhen nga skriptat e projektit.

## 2.4. Docker Compose dhe vendosja

Docker Compose bashkon shërbimet në rrjetin bridge të projektit. Brenda tij përdoren emrat e shërbimeve, si compute ose mongodb. Në pajisje publikohen Controller në portën 5000, Grafana në 3000, Prometheus në 9090 dhe MongoDB në 27017 për inspektim lokal me Compass. Të katër portat lidhen me 127.0.0.1; endpoint-et e punës së Compute dhe Data nuk publikohen në host.

[[FIGURE|3|Konfigurimi i shërbimeve në Docker Compose|Pamje e re nga compose.yaml|Të paraqiten pjesët e Compute dhe Data me cpus, mem_limit dhe networks. Mos përfshini përmbajtjen e .env ose kredenciale.|2.6]]

Nisja bëhet me skriptën e projektit, sepse ajo zgjedh preset-in dhe profilin, kontrollon konfigurimin, pret gatishmërinë dhe verifikon kufijtë efektivë. Ndryshimi i vendosjes bllokohet gjatë një eksperimenti aktiv. Shërbimet me healthcheck kontrollohen nga Docker; për Collector dhe Tempo skriptat kontrollojnë endpoint-et e gatishmërisë. Një scrape i suksesshëm nuk provon vetvetiu suksesin e eksperimentit.

Për konfigurimin bazë me gjurmim përdoren komandat:

[[COMMAND|./scripts/start.ps1 -Preset baseline -Tracing]]

[[COMMAND|./scripts/verify.ps1]]

[[FIGURE|4|Nëntë kontejnerët e konfigurimit bazë me gjurmim|Pamje e re nga Docker Desktop, grupi cloud-lab1|Të duken nëntë emrat dhe gjendjet Running. Shënimi Healthy paraqitet vetëm për shërbimet që kanë healthcheck.|2.6]]

Volumet e emërtuara ruajnë historikun MongoDB, metrikat Prometheus, konfigurimin Grafana dhe gjurmët Tempo gjatë ndalimit normal. Prometheus ka kufi ruajtjeje shtatë ditë ose 1 GiB; gjurmët Tempo ruhen rreth 24 orë. Konfigurimet e monitorimit montohen vetëm për lexim. Mbyllja normale bëhet me ./scripts/stop.ps1 dhe nuk fshin këto volume; fshirja e të dhënave është operacion i veçantë.
