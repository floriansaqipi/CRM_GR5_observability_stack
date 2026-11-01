# III. Implementimi / Zhvillimi

## 3.1. Organizimi i kodit dhe koordinimi

Implementimi e ndan pranimin e kërkesës nga kryerja e punës. Controller merr parametrat nga ndërfaqja, i validon dhe krijon rekordin e eksperimentit. Compute ose Data e ekzekuton ngarkesën në procese të veçanta dhe raporton progresin. Kjo ndarje lejon që kërkesat për gjendjen dhe Stop të përpunohen edhe gjatë punës intensive.

[[TABLE|4|Blloqet kryesore të implementimit|2.5,4.0]]

| Moduli ose grupi | Përgjegjësia në rrjedhën e punës |
|---|---|
| controller: app.py | Faqja, API-të publike, filtrat e historikut dhe eksporti CSV. |
| coordinator.py / fixed_coordination.py | Pronësia e eksperimentit aktiv, shpërndarja, mbledhja e rezultateve dhe rikuperimi. |
| shared/model.py | Preset-et, validimi dhe paraqitja publike e rekordit me lidhjet për Grafana. |
| shared/worker.py / workload_child.py | Mbikëqyrja e procesit të përkohshëm dhe ngarkesat me kohëzgjatje. |
| fixed_work.py / fixed_runner.py / fixed_child.py | Caktimi i batch-eve, llogaritja deterministe dhe mbikëqyrja e disa proceseve. |
| repository.py / metrics.py / tracing.py | Ruajtja MongoDB, bashkimi i progresit në metrika dhe lidhja e gjurmëve. |

Kur përdoruesi zgjedh Start, vlerat e profilit bashkohen me ndryshimet e avancuara dhe ruhen si konfigurim i zgjidhur. Controller kontrollon gatishmërinë, kufijtë e memories dhe gjendjen e vendosjes brenda të njëjtit mekanizëm kyçjeje që mbron eksperimentin aktiv. Vetëm pas këtyre kontrolleve krijon ID-në dhe kthen përgjigjen HTTP 202; përgjigjja nuk pret përfundimin e ngarkesës.

[[TABLE|5|API-të kryesore të përdorura nga ndërfaqja|2.65,3.85]]

| Kërkesa | Sjellja kryesore |
|---|---|
| GET /api/workloads | Jep profilet, kufijtë dhe disponueshmërinë e ngarkesave. |
| POST /api/runs | Nis eksperimentin në mënyrë asinkrone; konfliktet aktive kthejnë 409. |
| GET /api/runs/active | Jep eksperimentin aktiv ose vlerë bosh. |
| POST /api/runs/<id>/stop | Kërkon anulimin; përsëritja nuk nis veprim tjetër. |
| GET /api/runs dhe /api/runs/export.csv | Lexojnë historikun dhe eksportojnë përmbledhjet sipas filtrave. |

Rekordi kalon starting → running → stopping kur kërkohet Stop; gjendjet përfundimtare janë completed, cancelled, failed dhe interrupted. Start-i i brendshëm me të njëjtën ID dhe parametra nuk nis proces tjetër; konfigurimi i ndryshuar refuzohet. Controller lidh progresin, përfundon gjurmën dhe ruan rezultatin. Puna me rezultat të paqartë nuk përsëritet automatikisht.

## 3.2. Ngarkesat Compute dhe Data

Compute trajton ngarkesat CPU, ndërsa Data trajton memorien, rrjetin dhe databazën. Profili Medium dhe kohëzgjatja 30 sekonda shërbejnë si pikënisje për ngarkesat me kohë. Profili Low ose High ndryshon intensitetin, jo kuotën e kontejnerit. Kuotat ndryshohen nga preset-et e vendosjes.

[[TABLE|6|Ngarkesat dhe konfigurimi fillestar Medium|1.15,2.65,2.7]]

| Ngarkesa | Puna e kryer dhe vlera fillestare | Kufizimi ose rezultati kryesor |
|---|---|---|
| CPU | Një proces alternon punë dhe pushim; 50% kohë aktive, 30 s. | Raporton ciklet llogaritëse dhe kohën reale. |
| CPU comparison | 32 batch-e me nga 2 500 njësi; dy procese gjithsej. | Përfundon me punën e caktuar; afat sigurie 180 s. |
| Memory | Alokon e prek 64 MiB dhe e mban buffer-in për 30 s. | Dalja e procesit liron buffer-in. |
| Network | Data shkarkon përgjigje 256 KiB nga Compute, me synim 5/s. | Numëron përgjigjet e plota dhe byte-t e lexuar. |
| Database | Shkruan dhe lexon dokument 16 KiB; synimi 5 cikle/s. | Një cikël ka një shkrim dhe një lexim të suksesshëm. |
| Combined Data | Mban 64 MiB dhe kryen punën Network dhe Database, me synim 5 cikle/s. | Raporton veçmas memorien, rrjetin, databazën dhe gabimet. |

Për CPU-në me kohë, një cikël i shkurtër ndan intervalin aktiv nga pushimi. Numëruesi cpu_batches tregon sa herë u krye llogaritja elementare; ai nuk është numri i batch-eve logjike të krahasimit fiks. Për Memory, buffer-i preket në hapa 4 KiB gjatë alokimit, që memoria të përdoret realisht dhe jo vetëm të kërkohet si hapësirë virtuale.

Network lexon përmbajtjen e përgjigjes në pjesë dhe e hedh poshtë. Byte-t e transferimit të pjesshëm ruhen në numërues, por kërkesa numërohet e suksesshme vetëm kur plotësohet payload-i. Database ripërdor deri në 128 pozicione dokumentesh për run dhe verifikon që leximi përputhet me shkrimin. Combined mban buffer-in ndërsa kryen të dy llojet e I/O-së.

Validimi pranon 15–180 sekonda për ngarkesat me kohë, 10–95% për CPU, 1–128 MiB për memorie, payload rrjeti 1–1 024 KiB dhe 1–20 kërkesa ose cikle/s. Dokumentet janë 1–64 KiB. Te preset-i Data 256 MiB, alokimi kufizohet në 64 MiB. Kërkesat jashtë kufijve refuzohen përpara ekzekutimit.

Procesi prind lexon progresin kumulativ rreth çdo sekondë. Afatet mbikëqyren edhe në shërbimin që kryen punën, jo vetëm në Controller. Gjatë Stop dërgohet sinjali i ndalimit, pastaj zbatohet përfundimi i detyruar nëse nevojitet dhe procesi mblidhet. Ruhen numëruesit e njohur deri në ndërprerje; nuk pretendohet punë që nuk është raportuar.

## 3.3. MongoDB, historiku dhe ndërfaqja

MongoDB përdor databazën lab me koleksione të ndara: runs për përmbledhjet dhe workload_documents për ngarkesat e përkohshme. Rekordi ruan ID-në, emrin/shënimet, parametrat e zgjidhur, shërbimet, kohët, gjendjen, numëruesit, gabimin, lidhjen e gjurmës dhe snapshot-in e vendosjes. Indeksi sipas kohës ndihmon historikun; për dokumentet e përkohshme ekziston edhe indeks skadimi si mekanizëm ndihmës. Pastrimi normal bëhet shprehimisht pas punës.

[[FIGURE|5|Paneli për konfigurimin dhe ndjekjen e eksperimentit|docs/evidence/stage5/laboratory.jpg|Përdorni segmentin me konfigurimin dhe rezultatin aktiv; të duken Start/Stop, njësitë dhe gjendja e eksperimentit.|3.4]]

Ndërfaqja përdor template Flask, CSS dhe JavaScript të lehtë. Ajo pyet gjendjen një herë në sekondë; rifreskimi ose mbyllja e shfletuesit nuk e anulon punën në server. CPU comparison paraqet sasinë e punës dhe batch-et, ndërsa ngarkesat e tjera paraqesin kohëzgjatjen. Ngjyrat shoqërohen me tekst për gjendjen, mirëmbajtjen dhe humbjen e lidhjes.

[[FIGURE|6|Parametrat dhe rezultatet e ruajtura të eksperimentit|docs/evidence/stage5/details.jpg|Përzgjidhni pjesën me settings, deployment dhe rezultatin. JSON-i i plotë mbetet seksion i avancuar në aplikacion.|3.4]]

Historiku filtrohet sipas ngarkesës, gjendjes dhe emrit, me faqe të ndara. Eksporti CSV përdor të njëjtët filtra dhe ruan vlerat reale, jo vlerësime nga grafiku. Lidhjet për Grafana zgjedhin shërbimet dhe intervalin kohor; trace_id ruhet edhe kur gjurma ka skaduar nga Tempo. Në konfigurimin aktual, historiku mund të inspektohet lokalisht me Compass në 127.0.0.1:27017.

Kur MongoDB mungon, CPU, Memory dhe Network mbeten të përdorshme. Database dhe Combined bëhen të padisponueshme. Controller mban deri në 100 përmbledhje të paruajtura në memorie dhe provon përsëri ruajtjen; ato mund të eksportohen ndërkohë. Një restart përpara ruajtjes mund t'i humbë këto përmbledhje, prandaj ndërfaqja dallon saved nga pending.

## 3.4. Monitorimi dhe Grafana

Dashboard-i Container Resources përdor të dhënat e cAdvisor, të mbledhura çdo pesë sekonda. Etiketat e Compose identifikojnë projektin dhe shërbimin. Query-t kufizohen te cloud-lab1, përjashtojnë agregatet e host-it dhe kontejnerët e vjetër, si dhe shmangin numërimin e ndërfaqeve të dyfishta.

[[TABLE|7|Kuptimi i matjeve të burimeve|1.6,1.05,3.85]]

| Matja | Njësia | Interpretimi |
|---|---|---|
| CPU e konsumuar | Bërthama | Norma e kohës CPU; vlera 1 përfaqëson një bërthamë të konsumuar. |
| Memory working set | MiB | Përdorimi i kontejnerit, përfshirë prindin, procesin e punës dhe bibliotekat. |
| Receive / transmit | Byte/s | Trafiku i ndërfaqes; përfshin overhead dhe aktivitet tjetër të shërbimit. |
| CPU / memory ndaj kufirit | % | Raporti me kuotën pozitive CPU ose kufirin e vlefshëm të memories. |
| Periudha të throttling | % | Pjesa e periudhave të planifikimit ku kufizimi CPU është zbatuar. |
| Kohë throttling | s/s | Normë kohëzgjatjeje; nuk është përqindje përdorimi CPU. |

[[FIGURE|7|Dashboard-i i burimeve të kontejnerëve|docs/evidence/stage5/combined/grafana.jpg|Të duken shërbimi dhe intervali kohor, CPU-ja, memoria dhe trafiku. Titrat duhet të dallojnë bërthamat nga përqindjet ndaj kuotës.|5.0]]

CPU dhe trafiku përdorin dritare 30-sekondëshe për llogaritjen e normës. Prandaj ndryshimi shfaqet gradualisht dhe mund të vazhdojë të duket pas përfundimit të punës. Paneli recent CPU përdor dy mostrat e fundit të disponueshme, zakonisht rreth pesë sekonda larg, dhe është i dobishëm për punë të shkurtra. Këto dy pamje nuk duhen trajtuar si e njëjta matje kulmi.

CPU-ja ndaj kuotës dhe memoria ndaj kufirit shfaqen si të padisponueshme kur emëruesi mungon ose është i pakufizuar. Një zero reale ruhet si zero. Collection health tregon nëse Prometheus mund ta lexojë exporter-in; nuk provon që ngarkesa ose databaza është funksionale. Për rrjetin, Data është pranuesi i payload-eve dhe Compute dërguesi.

[[PAGE]]

### Metrikat e aplikacionit dhe bashkimi i progresit

Dashboard-i Application Performance shpjegon punën e kryer krahas burimeve të kontejnerit. Çdo shërbim Flask mban registry-n në procesin prind. Proceset e përkohshme dërgojnë numërues dhe bucket-e kumulative; prindi shton vetëm diferencën ndaj vlerës së fundit. Mesazhet e përsëritura ose përfundimtare nuk e numërojnë të njëjtën punë dy herë.

[[TABLE|8|Familjet kryesore të metrikave të aplikacionit|2.5,4.0]]

| Familja e metrikave | Çfarë shpjegon |
|---|---|
| HTTP requests / HTTP duration | Numrin dhe latencën sipas metodës, modelit të route-it dhe statusit. |
| Runs active / runs total | Eksperimentin aktiv dhe përfundimet e vëzhguara nga Controller. |
| Workload duration / elapsed | Kohën e ekzekutimit të worker-it dhe progresin gjatë punës. |
| Workload operations | Ciklet CPU, përgjigjet e rrjetit, shkrimet/leximet dhe gabimet. |
| Network bytes | Byte-t e payload-it të lexuar nga Data, edhe kur transferimi ndërpritet. |
| I/O duration | Histogramet e kohës së transferimit ose operacionit të databazës. |

[[FIGURE|8|Dashboard-i i performancës së aplikacionit|docs/evidence/stage5/combined/application-performance.jpg|Të duken shërbimet, normat e operacioneve dhe throughput-i i payload-it; ruani emrat e route-ve për të dalluar polling nga Start.|4.7]]

Query-t për kërkesat dhe latencën përdorin dritare dyminutëshe. p95 është vlerësim nga bucket-et e histogramit, jo koha e saktë e një kërkese individuale. Pa vëzhgime shfaqet mungesë të dhënash. Kërkesat /health, /metrics dhe skedarët statikë përjashtohen nga matjet HTTP; pyetjet e zakonshme për statusin mbeten të dallueshme nga route-i.

ID-të, emrat e eksperimenteve dhe URL-të e papërpunuara nuk përdoren si etiketa. Përdoren modele si /api/runs/<run_id>, me vlera të kufizuara për llojin e punës, operacionin dhe rezultatin. Numëruesit rifillojnë pas restart-it; historiku MongoDB është rekordi afatgjatë. Përfundimi i eksperimentit numërohet një herë nga Controller, jo gjatë leximit të historikut ose përsëritjes së ruajtjes.

Te cpu_fixed, etiketa historike cpu_batch numëron njësi llogaritëse, ndërsa logical_batch numëron batch-e të përfunduara prej 2 500 njësish. Me dy instanca, normat mblidhen për Compute dhe Compute-2. Matjet e Grafana-s i përkasin shërbimit në intervalin e zgjedhur; ato nuk janë seri të izoluara për çdo run dhe mund të përfshijnë aktivitet paraprak.

## 3.5. Gjurmimi i shpërndarë

Gjurmimi aktivizohet me profilin tracing. OpenTelemetry instrumenton Flask, Requests dhe PyMongo, ndërsa span-et e shprehura në kod përshkruajnë eksperimentin dhe fazat kryesore. Inicializimi bëhet pas fork-ut të Gunicorn dhe veçmas brenda proceseve të punës. Konteksti W3C kalon ndërmjet kërkesave HTTP, fijeve koordinuese dhe nisjes së procesit të përkohshëm.

Kërkesa Start është e shkurtër. Span-i experiment.run mbetet i hapur derisa të vëzhgohet një gjendje përfundimtare, ndërsa worker.execute dhe workload.run përshkruajnë punën në Data ose Compute. Për Combined, pasardhësit përfshijnë alokimin/mbajtjen e memories, kërkesat HTTP te Compute dhe thirrjet MongoDB nga klienti PyMongo.

[[FIGURE|9|Gjurma e lidhur e eksperimentit Combined|docs/evidence/stage5/combined/trace.jpg|Përzgjidhni degët Controller, Data, Compute dhe thirrjet MongoDB. Të duken trace_id dhe span-et e para I/O, jo vetëm lista e shërbimeve.|7.0]]

Për lexueshmëri, detajet e cikleve të suksesshme regjistrohen në ciklin e parë dhe më pas jo më shumë se një herë në sekondë. Ciklet e tjera ruajnë kontekst jo-regjistrues, që Compute të mos krijojë gjurmë të palidhura. Çdo cikël i dështuar merr span gabimi, edhe kur nuk ishte përzgjedhur për detaje. Metrikat mbledhin të gjitha operacionet e raportuara pavarësisht këtij përzgjedhimi.

Gjendja failed ose interrupted shënohet si gabim; cancelled merr ngjarje anulimi. Kontrollet e shëndetit, ping-et e disponueshmërisë dhe polling-u rutinë përjashtohen. Nuk kapen trupat e kërkesave/përgjigjeve ose përmbajtja e statement-eve MongoDB. Span-et MongoDB tregojnë kohën e thirrjeve të driver-it, jo fazat e brendshme të serverit.

Gjurma Combined e ruajtur ka 142 span-e të lidhura. Radhët dhe timeout-et e eksportit janë të kufizuara; një Collector ose Tempo i padisponueshëm nuk duhet të ndryshojë rezultatin e ngarkesës. Një ndalim i fortë mund të humbë span-e dhe të lërë gjurmë jo të plotë. Skadimi i gjurmës pas rreth 24 orësh është i pavarur nga ruajtja e historikut.

[[NOTE|ID e gjurmës: 1cdbe47bc835d1cd81c501ee55095ca0]]

## 3.6. Alokimi i burimeve dhe replikat

Preset-et ndryshojnë kufijtë e vendosjes, ndërsa CPU comparison mban të njëjtën sasi pune. Një njësi kryen të njëjtën llogaritje deterministe mbi 3 000 numra; një batch logjik ka 2 500 njësi. Medium përdor 32 batch-e, pra 80 000 njësi, me checksum të përfunduar 12 007 132 800 000. Versioni i algoritmit është sum-squares-v1; afati i sigurisë është 180 sekonda.

[[FIGURE|10|Shpërndarja deterministe e batch-eve|Pamje e re nga services/shared/fixed_work.py|Të duken calculate_unit dhe assign_batches. Pamja të tregojë dy procese gjithsej dhe caktimin round-robin, pa paraqitur kode nga module të tjera.|4.0]]

Me një Compute, dy procese marrin lista të alternuara batch-esh. Me dy instanca, secila ka një proces dhe merr 16 nga 32 batch-et. Caktimi ruhet përpara shpërndarjes. Worker-i refuzon caktime të ndryshuara për të njëjtën ID; Controller pranon një përfundim për secilin batch dhe nuk e rishpërndan automatikisht punën e dështuar ose të paqartë.

[[FIGURE|11|Përdorimi i CPU-së kundrejt kuotës|docs/evidence/stage4/cpu-quota-panels.jpg|Të duken preset-i, CPU-ja ndaj kuotës dhe throttling si madhësi të ndara. Pamja është evidencë e verifikimit të fazës 4.|4.0]]

Skriptat vendosin një flamur të qëndrueshëm mirëmbajtjeje dhe verifikojnë mungesën e një eksperimenti aktiv. Pas ndryshimit, krahasojnë kufijtë e Docker-it me leximet cgroups v1/v2 të worker-ëve. Start lejohet vetëm pas verifikimit. Një dështim lë gjendje të dukshme mirëmbajtjeje. Snapshot-i i verifikuar ruhet me run-in dhe nuk ndryshohet kur aplikohet një preset tjetër më vonë.

[[PAGE]]

### Rezultatet e verifikimit të alokimit

Tabela 9 përmban ekzekutimet individuale të pranimit nga faza 4. Të gjitha rastet përfunduan 32 batch-e me të njëjtin checksum dhe dy procese llogaritëse gjithsej. Koha është ajo e raportuar nga worker-i; kulmi CPU përdor mostrat recent dhe nuk është maksimumi i mesatares 30-sekondëshe të shembujve të fazës 5.

[[TABLE|9|Krahasimet CPU dhe një/dy instanca Compute|1.1,1.0,1.55,2.85]]

| Preset-i | Koha (s) | Kulmi recent CPU | Batch-et / proceset |
|---|---|---|---|
| cpu-05 | 68.643 | 0.502 bërthama | 32 në Compute; dy procese. |
| cpu-1 | 31.064 | 1.003 bërthama | 32 në Compute; dy procese. |
| cpu-2 | 14.884 | 1.929 bërthama | 32 në Compute; dy procese. |
| replica-1 | 31.922 | 1.001 bërthama | 32 në Compute; dy procese. |
| replica-2 | 15.664 | 0.998 / 1.000 | 16 për instancë; një proces secila. |

[[FIGURE|12|Burimet e instancave Compute dhe Compute-2|docs/evidence/stage4/replica-resources.jpg|Të duken të dy identitetet dhe ngarkesa e shpërndarë. Alokimi total është dy CPU dhe 1 024 MiB, jo i barabartë me rastin me një instancë.|3.8]]

Te replica-2 rritet alokimi total nga një CPU/512 MiB në dy CPU/1 024 MiB. Rënia e kohës nuk përbën provë shkallëzimi me burime totale të barabarta. Mostra e pavarur Docker stats arriti 1.971 bërthama në rastin cpu-2, duke konfirmuar se konfigurimi mund të përdorë më shumë se një bërthamë kur pajisja e lejon.

[[TABLE|10|E njëjta ngarkesë Memory nën tre kufij|2.2,2.2,2.1]]

| Kufiri Data | Alokimi / koha reale | Kulmi working set |
|---|---|---|
| 256 MiB | 64 MiB / 30.001 s | 164.5 MiB |
| 512 MiB | 64 MiB / 30.001 s | 171.0 MiB |
| 1 024 MiB | 64 MiB / 30.001 s | 166.5 MiB |

Asnjë nga kontejnerët e vëzhguar nuk u vra nga mungesa e memories. Kulmet nuk priten të jenë identike, sepse përfshijnë overhead dhe mostrim. Burimi i këtyre krahasimeve është docs/evidence/stage4/acceptance.json, bashkë me matjet dhe rekordet e veçanta për secilin preset.

## 3.7. Eksperimentet dhe analiza e rezultateve

Katër shembujt e fazës 5 u kryen njëri pas tjetrit në baseline me gjurmim, me imazhe të pandryshuara. Secili kishte të paktën 30 sekonda gjendje të qetë përpara dhe 30 sekonda ftohje pas punës. Mostrat Prometheus janë pesë sekonda larg; normat e burimeve janë mesatare 30-sekondëshe. Numëruesit e punës merren nga rezultati i ruajtur, jo nga forma e grafikut.

### Eksperimenti CPU

[[NOTE|ID e run-it: 8636fafc-6533-44c2-a330-1cce68f0841a]]

[[TABLE|11|Parametrat dhe rezultati i eksperimentit CPU|2.0,4.5]]

| Elementi | Vlera e ruajtur |
|---|---|
| Profili / koha reale | Medium, 50% kohë aktive / 30.000 s |
| Puna / ritmi real | 44 953 cikle llogaritëse / 1 498.415 cikle/s |
| CPU Compute | Kulmi i mesatares 30 s: 0.558 bërthama |
| Gjendja / gabimet | completed, saved / 0 gabime |

[[FIGURE|13|Matjet e eksperimentit CPU|docs/evidence/stage5/cpu/resources.png|Të dallohen baseline, puna dhe ftohja; CPU-ja në grafik është mesatare 30-sekondëshe. Ruani ID-në dhe njësitë në figurë.|9.8]]

Compute tregon rritje të aktivitetit dhe rënie gjatë ftohjes. Vlera 0.558 përfshin punën e shërbimit dhe observabilitetit, prandaj nuk është verifikim i një përqindjeje ekzakte 50%. Ciklet e kësaj ngarkese janë llogaritje elementare; nuk janë batch-et logjike prej 2 500 njësish të CPU comparison.

[[PAGE]]

### Eksperimenti Memory

[[NOTE|ID e run-it: 5a804b0d-a5c2-481a-992b-4e1e96536c92]]

[[TABLE|12|Parametrat dhe rezultati i eksperimentit Memory|2.0,4.5]]

| Elementi | Vlera e ruajtur |
|---|---|
| Buffer-i / koha reale | 64 MiB / 30.003 s |
| Faqet e prekura | 16 384 faqe prej 4 KiB |
| Working set Data | 65.8 → 169.1 → 66.0 MiB |
| Gjendja / gabimet | completed, saved / 0 gabime |

[[FIGURE|14|Matjet e eksperimentit Memory|docs/evidence/stage5/memory/resources.png|Të duken rritja e working set dhe lirimi pas përfundimit; buffer-i 64 MiB nuk është i barabartë me memorien totale të kontejnerit.|11.0]]

Vlerat përmbledhin medianën e baseline-it, kulmin e mostrës së ruajtur dhe medianën e fundit të ftohjes. Rritja prej rreth 103 MiB është më e madhe se buffer-i 64 MiB: bashkë me të niset interpreteri i procesit dhe bibliotekat e nevojshme. Kthimi afër 66 MiB mbështet lirimin e buffer-it pas daljes së procesit; nuk premtohet rikthim në të njëjtin numër byte-sh.

[[PAGE]]

### Eksperimenti Network

[[NOTE|ID e run-it: ead14011-9209-49a2-a061-9cb74ea41375]]

[[TABLE|13|Parametrat dhe rezultati i eksperimentit Network|2.0,4.5]]

| Elementi | Vlera e ruajtur |
|---|---|
| Payload-i / synimi | 256 KiB për përgjigje / 5 kërkesa/s |
| Koha / përgjigjet e plota | 30.000 s / 150 |
| Payload-i i lexuar / ritmi | 37.50 MiB / 5.000 kërkesa/s |
| Kulmi receive Data | 1.202 MiB/s, mesatare 30 s |
| Gjendja / gabimet | completed, saved / 0 gabime |

[[FIGURE|15|Matjet e eksperimentit Network|docs/evidence/stage5/network/resources.png|Të shihen së bashku Data receive dhe Compute transmit. Përfshini dritaren e ftohjes, ku norma vazhdon për shkak të mesatarizimit.|10.5]]

Numri 150 dhe sasia 37.50 MiB vijnë nga run-i. Synimi i payload-it është 1.25 MiB/s, por kulmi i ndërfaqes në një grafik të mesatarizuar nuk është kontroll ekzakt i kësaj vlere. Trafiku përfshin protokollet dhe kërkesa të tjera, ndërsa dritarja 30-sekondëshe mund të kapë edhe intervale para ose pas punës. Data pranon të dhëna; Compute i transmeton ato.

[[PAGE]]

### Eksperimenti Combined Data

[[NOTE|ID e run-it: 2f24ccd5-bc82-483b-906c-14fe16c1f6a8]]

[[TABLE|14|Parametrat dhe rezultati i eksperimentit Combined|2.0,4.5]]

| Elementi | Vlera e ruajtur |
|---|---|
| Memoria / payload-et | 64 MiB; rrjet 256 KiB; databazë 16 KiB |
| Synimi / koha reale | 5 cikle/s / 30.005 s |
| Rrjeti | 150 përgjigje, 37.50 MiB, 4.999 kërkesa/s |
| Databaza | 150 shkrime, 150 lexime, 150 cikle; 4.999 cikle/s |
| Working set Data / gabimet | 66.3 → 170.0 → 66.4 MiB / 0 gabime |

[[FIGURE|16|Matjet e eksperimentit Combined|docs/evidence/stage5/combined/resources.png|Të duken Data, Compute dhe MongoDB me të njëjtin interval kohor. Lidhja me aplikacionin dhe gjurmën shpjegohet në tekst.|10.2]]

Run-i përfundoi completed dhe u ruajt. Aktiviteti lidh memorien e Data-s, trafikun me Compute dhe shkrim/leximin MongoDB. Dokumentet e përkohshme u pastruan, ndërsa përmbledhja mbeti në historik. Pastrimi nuk garanton që cache-i i MongoDB të rikthejë menjëherë memorien në nivelin fillestar. Ritmi 4.999 pasqyron numëruesin dhe kohën reale, jo një dështim kundrejt synimit 5/s. Gjurma e këtij run-i është ajo e Figurës 9.

## 3.8. Testimi, sfidat dhe kufizimet

Evidenca dallon testet automatike nga kontrollet e pranimit në mjedisin e punës. 31 testet ekzistuese mbulojnë validimin, konfliktet, idempotencën, afatet, anulimin, proceset, rikuperimin dhe pjesët e observabilitetit. 127 kontrollet përfundimtare të fazës 5 përfshijnë query-t, CSV-në, gjendjet e ndërfaqes dhe materialet e ruajtura; nuk janë 127 teste të tjera unitare.

[[TABLE|15|Përmbledhje e verifikimeve të ruajtura|2.25,4.25]]

| Kontrolli | Rezultati i vëzhguar |
|---|---|
| Regresioni automatik | 31 teste të kaluara në kontejner të izoluar. |
| Kontrollet përfundimtare të fazës 5 | 127 kontrolle të kaluara; të dhënat e mëparshme mbetën të disponueshme. |
| Katër shembujt | Të përfunduar, të ruajtur, pa gabime operacionale të raportuara. |
| Stop nga ndërfaqja, Memory | cancelled brenda 1.958 s në rastin e testuar. |
| Stop me replika, faza 4 | 1.054 s; pa procese llogaritëse të mbetura. |
| Gjendja përfundimtare e fazës 5 | Baseline me gjurmim; nëntë shërbime; asnjë run aktiv, rezultat pending ose dokument i përkohshëm. |

Rifreskimi i shfletuesit ruajti dukshmërinë e punës aktive. Mirëmbajtja dhe humbja e lidhjes e bllokuan Start me mesazh shpjegues. Restart-et e Controller ose worker-it shënuan interrupted dhe nuk e përsëritën punën. Worker-i i paarritshëm e mban sistemin të bllokuar derisa të përcaktohet gjendja e tij; përndryshe një eksperiment i ri mund të mbivendosej me punë të panjohur.

Gjatë implementimit u korrigjuan query që përfshinin seri të vjetra pas rikrijimit të kontejnerëve, sintaksa e bashkimit të raporteve dhe përdorimi i mesatares 30-sekondëshe për punë që zgjat më pak. U shtuan kontrolle për mostrat e freskëta dhe krahasim me Docker stats. Këto hapa tregojnë pse një dashboard bosh ose një exporter i arritshëm nuk mjafton si provë e monitorimit korrekt.

Matjet përfshijnë Python-in, kontrollet e shëndetit dhe observabilitetin. Mostrimi pesësekondësh mund të humbë kulme të shkurtra; dritaret 30-sekondëshe dhe dyminutëshe e zbusin sinjalin. p95 me pak vëzhgime është i përafërt. Numëruesit resetohen në restart dhe një proces i vrarë fort mund të humbë intervalin e fundit të progresit. Gjurmët kanë kohë ruajtjeje më të shkurtër se historiku.

Katër skenarët dhe krahasimet e alokimit janë vëzhgime individuale në një laptop, me ngarkesa sintetike. Nuk japin interval besueshmërie, performancë të garantuar ose efikasitet shkallëzimi me burime të barabarta. Burimet dhe ID-të e run-eve lejojnë kontrollimin e numrave pa i vlerësuar nga screenshot-et.
