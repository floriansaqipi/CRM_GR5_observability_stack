# Burimet për hartimin e raportit

Këto janë shënime burimore për kapitujt. Bibliografia e plotë është te [kapitulli-5.md](kapitulli-5.md), me burimin e strukturuar [referencat.json](referencat.json); numrat lidhen me citimet në dokumentin Word të plotë. Burimet e jashtme u konsultuan më **1 nëntor 2026**.

| Burimi zyrtar | Përdorimi në Kapitullin II |
|---|---|
| [Docker Compose](https://docs.docker.com/compose/) | Përgjegjësia e Compose për shërbimet, rrjetin dhe volumet |
| [Flask: Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/) | Shërbimi i aplikacioneve Flask brenda mjedisit Linux |
| [MongoDB: WiredTiger](https://www.mongodb.com/docs/manual/core/wiredtiger/) | Konteksti i motorit të ruajtjes; hollësitë e përdorimit analizohen në Kapitullin III |
| [Google cAdvisor](https://github.com/google/cadvisor) | Matja e burimeve të kontejnerëve |
| [Prometheus: Overview](https://prometheus.io/docs/introduction/overview/) | Mbledhja dhe ruajtja e metrikave si seri kohore |
| [Grafana: Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/) | Konfigurimi i dashboard-eve dhe burimeve nga skedarët |
| [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) | Pranimi, përpunimi dhe përcjellja e gjurmëve |
| [Grafana Tempo](https://grafana.com/docs/tempo/latest/) | Roli i ruajtjes dhe kërkimit të gjurmëve |

Për versionet dhe sjelljen e aplikacionit burim parësor është vetë projekti: `compose.yaml`, `services/Dockerfile`, `services/requirements.txt`, `services/gunicorn_conf.py`, konfigurimet e monitorimit, skriptat dhe evidenca e ruajtur. Versionet Docker Engine 29.5.2, Compose 5.1.4 dhe PowerShell 7.6.5, si dhe mjedisi Windows/CPU/RAM, u lexuan nga pajisja gjatë hartimit. Compose përshkruhet si plugin-i lokal i inspektuar; nuk pretendohet se versioni i tij fiksohet nga repository.

Repository: [CRM_GR5_observability_stack](https://github.com/floriansaqipi/CRM_GR5_observability_stack). Për matjet përdoren rekordet e ruajtura të fazave, jo vlera shembull nga dokumentacioni i teknologjive. Kontrolli i këtij kapitulli nuk rinisi kontejnerët e aplikacionit dhe nuk ekzekutoi eksperimente të reja.

## Burimet e Kapitullit III

Sjellja e implementuar u kontrollua drejtpërdrejt në kodin aktual dhe në evidencën lokale më **1 nëntor 2026**. Tabela më poshtë lidh pjesët e shpjegimit me burimin parësor. Rrugët në tekst janë relative ndaj rrënjës së repository-t.

| Pjesa | Burimi kryesor |
|---|---|
| API, pronësia e run-it, rikuperimi | `services/controller/app.py`, `coordinator.py`, `fixed_coordination.py` |
| Profilet, kufijtë dhe lidhjet e rekordit publik | `services/shared/model.py`, `deployment.py` |
| Proceset e përkohshme dhe ngarkesat | `services/shared/worker.py`, `workload_child.py`, `fixed_runner.py`, `fixed_child.py` |
| Algoritmi, caktimi dhe checksum-i | `services/shared/fixed_work.py` |
| Historiku, dokumentet e përkohshme dhe pastrimi | `services/controller/repository.py`, `services/shared/workload_child.py` |
| Bashkimi i progresit dhe histogramet | `services/shared/metrics.py` |
| Konteksti, përzgjedhja e cikleve dhe eksporti | `services/shared/tracing.py`, konfigurimet Collector/Tempo |
| Query-t, njësitë dhe dritaret e mostrimit | `monitoring/grafana/dashboards/`, konfigurimet Prometheus |
| Vendosja e verifikuar dhe mirëmbajtja | `compose.yaml`, `deployment/`, `scripts/start.ps1`, `scripts/apply-preset.ps1` |

Udhëzuesit ndihmës: [repository-guide.md](../repository-guide.md), [stage-4.md](../stage-4.md), [experiment-results.md](../experiment-results.md), [stage-5.md](../stage-5.md). Ekspozimi lokal i MongoDB për Compass u kontrollua nga Compose dhe porta e publikuar; shpjegimi i Kapitullit II u harmonizua me konfigurimin aktual. Ky përditësim i raportit nuk ndryshoi Compose.

### Rezultatet dhe identifikuesit

Për çdo rast u lexua objekti `run` brenda rekordit, së bashku me `resources`, `window` dhe kontrollet e ruajtura. Normat e numëruesve vijnë nga `rates`; matjet e burimeve vijnë nga mostrat Prometheus. Memoria përmblidhet si medianë baseline → kulm i mostrës → medianë e fundit të ftohjes.

| Shembulli | ID e run-it | Burimi |
|---|---|---|
| CPU | `8636fafc-6533-44c2-a330-1cce68f0841a` | [cpu/run.json](../evidence/stage5/cpu/run.json) |
| Memory | `5a804b0d-a5c2-481a-992b-4e1e96536c92` | [memory/run.json](../evidence/stage5/memory/run.json) |
| Network | `ead14011-9209-49a2-a061-9cb74ea41375` | [network/run.json](../evidence/stage5/network/run.json) |
| Combined | `2f24ccd5-bc82-483b-906c-14fe16c1f6a8` | [combined/run.json](../evidence/stage5/combined/run.json) |

- [experiments.json](../evidence/stage5/experiments.json) lidh katër run-et me imazhet e pandryshuara dhe snapshot-in e verifikuar. [experiment-history.csv](../evidence/stage5/experiment-history.csv) përmban përmbledhjet e eksportuara.
- [combined/trace.json](../evidence/stage5/combined/trace.json) ka **142 span-e** në gjurmën `1cdbe47bc835d1cd81c501ee55095ca0`; ID-ja binare në eksportin JSON dekodohet nga Base64 për krahasim me ID-në heksadecimale të run-it. Prindërit dhe pasardhësit u kontrolluan për vazhdimësi.
- [stage4/acceptance.json](../evidence/stage4/acceptance.json) përmban run-et, matjet CPU recent, mostrat Docker stats, kulmet e memories dhe anulimin me replika. Tabelat e fazës 4 përdorin këto matje verifikimi; nuk përdorin kulmet e mesatares 30-sekondëshe të fazës 5.
- [unit-tests.txt](../evidence/stage5/unit-tests.txt) dokumenton **31 teste**; [verification.json](../evidence/stage5/verification.json) ka **127 kontrolle** të fazës 5. Kohët e anulimit vijnë nga ky regjistër i fazës 4 dhe [browser-verification.json](../evidence/stage5/browser-verification.json).

Hartimi dhe kontrolli i Kapitullit III nuk nisën eksperimente të reja. Kontrolli i faqosjes ishte konvertim i izoluar në sfond; nuk u përdor desktopi aktiv. Rezultati i auditimit të dokumentit dhe hash-et e hyrjes/daljes ruhen te [verifikimi-kapitulli-3.json](verifikimi-kapitulli-3.json).

## Burimet e Kapitullit IV

Përfundimet përmbledhin vetëm implementimin dhe rezultatet e Kapitujve I–III. Kohët 68.643 s dhe 14.884 s vijnë përkatësisht nga run-et `cpu-05` dhe `cpu-2` në [stage4/acceptance.json](../evidence/stage4/acceptance.json). I njëjti regjistër mbështet punën/checksum-in e barabartë, dy proceset gjithsej dhe alokimin më të madh të rastit me dy instanca.

150 përgjigjet dhe 37.50 MiB payload vijnë nga [network/run.json](../evidence/stage5/network/run.json); 150 ciklet e databazës vijnë nga [combined/run.json](../evidence/stage5/combined/run.json). Përfundimi për memorien lidhet me shembullin Memory dhe me tri provat e kufijve në evidencën e fazës 4. Formulimi ruan kufizimet e mostrimit, overhead-it dhe vëzhgimeve individuale.

Studimi me përsëritje, ngarkesat reale, alarmet dhe vendosja jashtë laptopit paraqiten si zhvillim i ardhshëm, jo si funksione të realizuara. Burimet e kapitullit nuk kërkuan eksperimente ose matje të reja. Kontrollet e përmbajtjes, ruajtjes së draftit bazë dhe faqosjes gjenden te [verifikimi-kapitulli-4.json](verifikimi-kapitulli-4.json).

## Abstrakti dhe bibliografia e plotë

Abstrakti përmbledh qëllimin, arkitekturën, katër skenarët e ruajtur dhe kufizimet e interpretimit. Përfundimi pa gabime të raportuara u kontrollua në katër rekordet `run.json`; numri 142 i span-eve u kontrollua në eksportin e gjurmës Combined. Ai nuk shton rezultate ose eksperimente të reja.

Bibliografia ka 15 referenca: repository, dokumentacione zyrtare dhe arkivin e matjeve. U verifikuan burimet për Compose, Gunicorn, WiredTiger, cAdvisor, Prometheus, Grafana, OpenTelemetry dhe Tempo. Regjistri i konsultimit është te [verifikimi-burimeve.json](verifikimi-burimeve.json). Dosja publike `docs/evidence` u kontrollua me GitHub API, që ktheu HTTP 200 dhe listoi `stage4` e `stage5`, krahas kontrollit të skedarëve lokalë.

Mapimi i 22 paragrafëve me citimet është te [citimet.json](citimet.json). Referencat [1] dhe [15] mbështesin sjelljen dhe matjet specifike të projektit; burimet e tjera shpjegojnë mekanizmat e teknologjive. Formatimi dhe teksti bazë I–IV u ruajtën, me shtimin e citimeve dhe përditësimin e numrave të faqeve. Rezultatet e kontrollit përfundimtar janë te [verifikimi-raporti-plote.json](verifikimi-raporti-plote.json).
