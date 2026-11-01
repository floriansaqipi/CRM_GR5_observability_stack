# Abstrakti

Ky projekt paraqet një laborator lokal për monitorimin e burimeve dhe observabilitetin e aplikacioneve në kontejnerë. Qëllimi është që ndryshimet në përdorimin e CPU-së, memories dhe rrjetit të lidhen me veprime të kontrolluara të aplikacionit dhe me rezultatet e tyre të ruajtura.

Sistemi ndërtohet me Docker Compose dhe shërbimet Flask Controller, Compute dhe Data. Controller koordinon një eksperiment aktiv, ndërsa ngarkesat ekzekutohen në procese të veçanta me kufij, afate dhe mundësi anulimi. MongoDB ruan historikun dhe mbështet ngarkesat e databazës. cAdvisor mbledh matjet e kontejnerëve; Prometheus ruan metrikat e burimeve dhe të aplikacionit; Grafana ofron dy dashboard-e për interpretimin e tyre. Gjurmimi opsional përmes OpenTelemetry Collector dhe Tempo lidh operacionet ndërmjet shërbimeve. Konfigurimet e verifikuara të burimeve dhe caktimi determinist i llogaritjeve mundësojnë edhe krahasime me sasi fikse pune dhe një ose dy instanca Compute.

Katër eksperimentet shembull për CPU, memorie, rrjet dhe punë të kombinuar përfunduan dhe u ruajtën pa gabime operacionale të raportuara. Matjet treguan aktivitetin CPU, rritjen dhe lirimin e memories, drejtimin e trafikut dhe lidhjen me operacionet e databazës. Gjurma Combined e ruajtur përmban 142 span-e të lidhura. Historiku dhe eksporti CSV ruajnë parametrat dhe numëruesit realë, duke mundësuar kontrollimin e interpretimit të grafikëve.

Rezultatet demonstrojnë funksionimin e laboratorit në mjedisin lokal. Meqë skenarët janë ekzekutime individuale me ngarkesa sintetike, ato nuk përbëjnë studim statistikor të performancës. Përsëritja e eksperimenteve dhe vlerësimi i ndryshueshmërisë mbeten zhvillime të ardhshme.

Fjalë kyçe: monitorimi i burimeve, kontejnerë, Docker Compose, Prometheus, Grafana, gjurmim i shpërndarë.
