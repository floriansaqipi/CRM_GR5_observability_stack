# Udhëzuesi i raportit të projektit

Raporti i projektit është [Raporti_Projektit_Monitorimi_i_Burimeve_Plote.docx](../Raporti_Projektit_Monitorimi_i_Burimeve_Plote.docx). Ai përmban ballinën, përmbajtjen automatike, abstraktin, kapitujt I–V, bibliografinë dhe gjashtëmbëdhjetë figurat teknike. Teksti është në shqip; pamjet e aplikacionit mund të ruajnë etiketat origjinale në anglisht.

Dokumenti Word është versioni autoritativ për tekstin e redaktuar dhe vendosjen e figurave. Skedarët Markdown në këtë dosje ruajnë burimet e kapitujve dhe mund të mos përfshijnë ndryshimet manuale të mëvonshme në Word. Numrat e faqeve varen nga faqosja aktuale; pas redaktimit përditësoni përmbajtjen dhe kontrolloni dokumentin në Word.

## Përmbajtja e raportit

| Pjesa | Përmbajtja |
|---|---|
| Ballina | Institucioni, lënda, titulli, grupi, anëtarët, profesori/asistenti dhe logoja |
| Abstrakti | Qëllimi, arkitektura, rezultatet kryesore dhe kufizimet |
| I. Përshkrimi i problemit | Problemi, motivimi, objektivat dhe kufijtë |
| II. Teknologjitë e përdorura | Teknologjitë, mjedisi punues, arkitektura dhe vendosja me Docker Compose |
| III. Implementimi / Zhvillimi | Koordinimi, ngarkesat, historiku, metrikat, gjurmimi, alokimi, replikat, eksperimentet dhe testimi |
| IV. Përfundime | Arritjet, gjetjet, kufizimet dhe zhvillimi i ardhshëm |
| V. Referencat | Dokumentacionet zyrtare, kodi dhe evidenca e rezultateve |

Raporti përdor format Letter me margjina 2.54 cm, tekst Palatino Linotype dhe tituj blu sipas formatimit të dokumentit. Implementimi shpjegohet me tekst, tabela dhe figura. Përmbajtja dhe numërimet përdorin fusha të Word-it.

## Organizimi i burimeve

| Burimi | Përgjegjësia |
|---|---|
| [abstrakti.md](abstrakti.md) | Teksti burimor i abstraktit |
| [kapitulli-1.md](kapitulli-1.md), [kapitulli-2.md](kapitulli-2.md) | Problemi, teknologjitë dhe arkitektura |
| [kapitulli-3.md](kapitulli-3.md) | Implementimi, eksperimentet dhe vlerësimi |
| [kapitulli-4.md](kapitulli-4.md), [kapitulli-5.md](kapitulli-5.md) | Përfundimet dhe bibliografia |
| [referencat.json](referencat.json) | Bibliografia e strukturuar me 15 referenca |
| [citimet.json](citimet.json) | Mapimi fillestar i paragrafëve me numrat e referencave |
| [burimet.md](burimet.md) | Lidhja e fakteve teknike me kodin, konfigurimet dhe evidencën |
| [build-word-report.py](../../scripts/build-word-report.py) | Gjenerimi historik i draftit sipas kapitujve |

## Figurat dhe evidenca

Numrat e figurave ndjekin rendin e paraqitjes në Word. Tabela përmbledh përmbajtjen dhe burimet përkatëse; imazhet e përfshira në dokument janë pjesë e versionit aktual.

| Figura | Përmbajtja | Burimi ose konfigurimi përkatës |
|---|---|---|
| 1 | Arkitektura e shërbimeve | Diagrami i përfshirë në Word; konfigurimi aktual në `compose.yaml` |
| 2 | Rrjedhat e metrikave dhe gjurmëve | Diagrami i përfshirë në Word; burimet teknike në `docs/assets/telemetry-paths.*` |
| 3 | Konfigurimi Docker Compose | Pamje e kodit të konfigurimit |
| 4 | Kontejnerët me gjurmim dhe Compute-2 | Pamje e Docker Desktop me instancën opsionale aktive |
| 5 | Paneli i eksperimentit | Pamja e ndërfaqes e përfshirë në Word |
| 6 | Parametrat dhe rezultati i ruajtur | `docs/evidence/stage5/details.jpg` |
| 7 | Dashboard-i i burimeve | `docs/evidence/stage5/combined/grafana.jpg` |
| 8 | Dashboard-i i aplikacionit | `docs/evidence/stage5/combined/application-performance.jpg` |
| 9 | Gjurma Combined | `docs/evidence/stage5/combined/trace.jpg` |
| 10 | Shpërndarja e batch-eve | Pamje nga `services/shared/fixed_work.py` |
| 11 | CPU-ja kundrejt kuotës | `docs/evidence/stage4/cpu-quota-panels.jpg` |
| 12 | Instancat Compute dhe Compute-2 | `docs/evidence/stage4/replica-resources.jpg` |
| 13–16 | Eksperimentet CPU, Memory, Network dhe Combined | `resources.png` në nënfolderët përkatës të `docs/evidence/stage5/` |

Diagramet përshkruajnë arkitekturën; screenshot-et tregojnë gjendjen e kapur në kohën përkatëse. Numrat e rezultateve merren nga rekordet JSON/CSV dhe matjet e ruajtura. Etiketat e portave dhe kufijtë teknikë kontrollohen kundrejt konfigurimit aktual. Figurat zëvendësohen pa ndryshuar raportin e përmasave ose vlerat e matjeve.

Për shpjegimin e sistemit përdorni [udhëzuesin e repository-t](../repository-guide.md). [Udhëzuesi i demonstrimit](../demo-guide.md) përshkruan veprimet e demonstrimit, ndërsa [raporti i rezultateve](../experiment-results.md) lidh numrat me eksperimentet e ruajtura.

## Rezultatet dhe kufizimet

Raporti mbështetet në kodin, konfigurimet dhe evidencën e fazave 4–5. Katër shembujt janë ekzekutime individuale; studimi formal me përsëritje mbetet punë e ardhshme. Krahasimi replica-2 rrit alokimin total të Compute, ndaj nuk përfaqëson shkallëzim me burime totale të barabarta.

31 testet automatike të aplikacionit dallohen nga 127 kontrollet përfundimtare të fazës 5 dhe nga kontrollet e dokumentit Word. Matjet e intervalit të fundit dallohen nga mesataret 30-sekondëshe. Historiku i eksperimenteve, metrikat dhe gjurmët kanë role dhe afate ruajtjeje të ndryshme.

## Regjistrat historikë të verifikimit

Regjistrat më poshtë dokumentojnë versionet e kontrolluara gjatë hartimit. Numrat e faqeve dhe hash-et në këta skedarë i përkasin atyre versioneve; ata nuk përditësohen duke zëvendësuar rezultatet historike pas redaktimeve manuale.

- [Kapitulli II](verifikimi-kapitulli-2.json): 23 kontrolle.
- [Kapitulli III](verifikimi-kapitulli-3.json): 62 kontrolle të dokumentit dhe të burimeve numerike.
- [Kapitulli IV](verifikimi-kapitulli-4.json): 38 kontrolle.
- [Raporti i plotë para figurave](verifikimi-raporti-plote.json): 46 kontrolle për versionin fillestar me 25 faqe dhe korniza për figura.
- [Burimet teknike](verifikimi-burimeve.json): regjistri i kontrollit të referencave dhe evidencës.

Parapamjet `parapamje-*.png` tregojnë versionet historike të kontrolluara. Dokumenti Word i lidhur në krye përmban redaktimet dhe figurat e mëvonshme.

## Gjenerimi i një drafti të ri

Skripta përdor Python dhe `python-docx` 1.2.0; këto janë mjete për dokumentin dhe nuk shtojnë varësi në aplikacion. Nga rrënja e repository-t, shfaqni opsionet me:

```powershell
python ./scripts/build-word-report.py --help
```

Për një draft fillestar, argumenti `--template` lexon dokumentin model. Për zgjerimin e një drafti përdoren `--base`, `--chapter 3`, `--chapter 4` ose `--finish`, sipas gjendjes së bazës. Argumenti `--output` përcakton një skedar të ri.

```powershell
python ./scripts/build-word-report.py --base docs/Raporti_Projektit_Monitorimi_i_Burimeve_Kapitulli_IV.docx --finish --output RAPORTI_I_RI.docx
```

Gjeneruesi kontrollon kapitujt ekzistues dhe refuzon shtimet e dyfishta. Ai nuk bashkon automatikisht ndryshimet manuale nga raporti i ilustruar. Ruajeni daljen me emër të ri, harmonizoni burimet dhe kontrolloni faqosjen përpara se ta përdorni si version autoritativ.

## Kontrolli pas redaktimit

1. Plotësoni ose kontrolloni të dhënat e ballinës dhe logon e miratuar.
2. Përditësoni përmbajtjen me **Update Field / Update entire table**.
3. Kontrolloni titrat, rendin e figurave dhe referencat në tekst.
4. Inspektoni faqet për tabela të prera, figura të shtrembëruara, titra të ndarë nga imazhet dhe hapësira të panevojshme.
5. Krahasoni çdo ndryshim numerik me rekordin përkatës të eksperimentit dhe ruani një regjistër të ri verifikimi kur kërkohet.
