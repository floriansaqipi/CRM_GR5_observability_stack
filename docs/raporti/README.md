# Dokumentimi në Word — plani dhe statusi

Dokumenti aktual është [Raporti_Projektit_Monitorimi_i_Burimeve_Plote.docx](../Raporti_Projektit_Monitorimi_i_Burimeve_Plote.docx). Ai ka **25 faqe** dhe përfshin ballinën, përmbajtjen automatike, abstraktin dhe **kapitujt I–V**. Teksti i strukturës së miratuar është plotësuar në shqip. Mbeten të plotësohen të dhënat identifikuese dhe logoja në ballinë, si dhe 16 vendet për figura.

Emri i planifikuar fillimisht ishte `Raporti_Projektit_Monitorimi_i_Burimeve.docx`. Draftet e mëparshme ishin të hapura në Word dhe u ruajtën të paprekura. Dorëzimi i plotë ka prapashtesën **Plote**; përdorni këtë version për plotësimet manuale. Mos e zëvendësoni me draftin e vjetër me emrin fillestar. Emri mund të harmonizohet pasi të mbyllen versionet e vjetra dhe të ruhen ndryshimet e përdoruesit.

## Versioni aktual

- Ballina me vende të redaktueshme për lëndën, profesorin/asistentin, grupin, anëtarët, email-et dhe logon.
- Përmbajtje automatike që përdor titujt semantikë të Word-it dhe shënues të brendshëm.
- Abstrakti në faqen 3: qëllimi, metoda, gjetjet dhe kufizimet; fjalë kyçe në shqip.
- Kapitulli I: problemi dhe motivimi; qëllimi dhe objektivat; kufijtë e implementimit.
- Kapitulli II: teknologjitë/versionet, mjedisi, arkitektura dhe Docker Compose; tri tabela dhe katër korniza për figura.
- Kapitulli III: organizimi/API-të, gjashtë ngarkesat, historiku/ndërfaqja, metrikat, gjurmimi, alokimi/replikat, katër eksperimentet dhe testimi/kufizimet. Në versionin e plotë zë faqet 10–22; tabelat 4–15 dhe figurat 5–16.
- Kapitulli IV: arritjet kryesore, gjetjet/kufizimet dhe zhvillimi i ardhshëm; faqja 23, pa figura ose tabela të reja.
- Kapitulli V: 15 referenca të numëruara me lidhje të klikueshme, në faqet 24–25; 22 paragrafë të kapitujve lidhen me burimet përkatëse.
- Tekstet burimore: [abstrakti.md](abstrakti.md), [kapitulli-1.md](kapitulli-1.md), [kapitulli-2.md](kapitulli-2.md), [kapitulli-3.md](kapitulli-3.md), [kapitulli-4.md](kapitulli-4.md), [kapitulli-5.md](kapitulli-5.md). Burimet teknike janë shënuar te [burimet.md](burimet.md).

Shtimi i abstraktit i zhvendosi kapitujt ekzistues për një faqe: Kapitulli I është në faqet 4–5 dhe Kapitulli II në faqet 6–9. Përmbajtja automatike ka 24 hyrje me numra të verifikuar. Figurat 1–4 mbeten në Kapitullin II dhe 5–16 në Kapitullin III; asnjë imazh nuk është futur. Pas zëvendësimit të kornizave me pamjet reale, përditësoni fushat dhe kontrolloni sërish faqosjen.

## Struktura e miratuar

1. **I. Përshkrimi i problemit** — problemi, motivimi, objektivat dhe kufijtë.
2. **II. Teknologjitë e përdorura** — teknologjitë/versionet, mjedisi punues, arkitektura, Docker Compose dhe vendosja.
3. **III. Implementimi / Zhvillimi** — organizimi dhe koordinimi; Compute/Data; MongoDB/historiku/ndërfaqja; monitorimi/Grafana; gjurmimi; alokimi/replikat; katër eksperimentet dhe rezultatet; testimi/sfidat/kufizimet.
4. **IV. Përfundime** — gjetjet, arritjet dhe puna e ardhshme.
5. **V. Referencat** — dokumentacione zyrtare dhe repository, me citime të numëruara.

Abstrakti u shkrua pas kapitujve dhe u vendos pas përmbajtjes. Implementimi shpjegohet me tekst dhe tabela, pa listime kodi të futura në raport.

## Regjistri i figurave

Rrugët më poshtë janë relative ndaj rrënjës së repository-t. Në Word vendosen korniza dhe titra në shqip, me burimin ose udhëzimin e përgatitjes; imazhet nuk futen gjatë hartimit. Numrat vijojnë sipas paraqitjes në dokument.

| Figura | Titulli / qëllimi | Burimi ose përgatitja |
|---|---|---|
| 1 | Arkitektura e shërbimeve të aplikacionit | `docs/assets/application-architecture.png`; monitorimi paraqitet veçmas në Figurën 2 |
| 2 | Rrjedhat e metrikave dhe gjurmëve | `docs/assets/telemetry-paths.png` |
| 3 | Konfigurimi i shërbimeve në Docker Compose | Pamje e re nga `compose.yaml`, me kufijtë/rrjetin/volumet; pa `.env` ose kredenciale |
| 4 | Nëntë kontejnerët e konfigurimit bazë me gjurmim | Pamje e re në Docker Desktop; të duken emrat dhe gjendjet e shërbimeve |
| 5 | Paneli për konfigurimin dhe ndjekjen e eksperimentit | `docs/evidence/stage5/laboratory.jpg` |
| 6 | Parametrat dhe rezultatet e ruajtura të eksperimentit | `docs/evidence/stage5/details.jpg` |
| 7 | Dashboard-i i burimeve të kontejnerëve | `docs/evidence/stage5/combined/grafana.jpg` |
| 8 | Dashboard-i i performancës së aplikacionit | `docs/evidence/stage5/combined/application-performance.jpg` |
| 9 | Gjurma e lidhur e eksperimentit Combined | `docs/evidence/stage5/combined/trace.jpg` |
| 10 | Shpërndarja deterministe e batch-eve | Pamje e re nga `services/shared/fixed_work.py`; të duken algoritmi dhe caktimi i punës |
| 11 | Përdorimi i CPU-së kundrejt kuotës | `docs/evidence/stage4/cpu-quota-panels.jpg` |
| 12 | Burimet e instancave Compute dhe Compute-2 | `docs/evidence/stage4/replica-resources.jpg` |
| 13 | Matjet e eksperimentit CPU | `docs/evidence/stage5/cpu/resources.png` |
| 14 | Matjet e eksperimentit Memory | `docs/evidence/stage5/memory/resources.png` |
| 15 | Matjet e eksperimentit Network | `docs/evidence/stage5/network/resources.png` |
| 16 | Matjet e eksperimentit Combined | `docs/evidence/stage5/combined/resources.png` |

Për çdo figurë shpjegohet çfarë duhet të dëshmojë. Pamjet e aplikacionit mund të ruajnë etiketat origjinale në anglisht; titrat dhe interpretimi shkruhen në shqip.

## Burimet e fakteve dhe kujdesi në interpretim

Përmbajtja mbështetet në kodin/konfigurimet aktuale dhe në evidencën ekzistuese, jo në rezultatet e projektit të ujit. Përdorni [udhëzuesin e repository-t](../repository-guide.md), [rezultatet e fazës 4](../stage-4.md), [katër shembujt](../experiment-results.md) dhe [rekordin e fazës 5](../stage-5.md).

31 testet automatike dallohen nga 127 kontrollet përfundimtare. Katër shembujt janë ekzekutime individuale; studimi formal me përsëritje mbetet punë e ardhshme. Matjet e intervalit të fundit dallohen nga mesataret 30-sekondëshe. Replica-2 rrit alokimin total, prandaj nuk është krahasim shkallëzimi me burime totale të barabarta.

## Rindërtimi i draftit fillestar

`scripts/build-word-report.py` përdor Python dhe `python-docx` 1.2.0 si mjete për dokumentin; këto nuk janë varësi të aplikacionit. Argumenti `--template` merr rrugën e dokumentit shembull të dhënë nga përdoruesi. Skripta e lexon atë pa e ndryshuar dhe krijon një dokument të pastër, pa media ose tekst të projektit të vjetër.

```powershell
python ./scripts/build-word-report.py --template "RRUGA_E_DOKUMENTIT_SHEMBULL.docx"
```

Për t'i shtuar Kapitullin II një baze që përmban vetëm Kapitullin I:

```powershell
python ./scripts/build-word-report.py --base docs/Raporti_Projektit_Monitorimi_i_Burimeve_Kontrolluar.docx --output RAPORTI_I_RI.docx
```

Kjo mënyrë ruan ballinën dhe përmbajtjen e bazës, shton Kapitullin II dhe rindërton indeksin. Refuzohet shtimi i dyfishtë i Kapitullit II. Mos e përdorni versionin me dy kapituj si bazë për këtë komandë.

Për t'i shtuar Kapitullin III versionit të kontrolluar me kapitujt I–II:

```powershell
python ./scripts/build-word-report.py --base docs/Raporti_Projektit_Monitorimi_i_Burimeve_Kapitulli_II.docx --chapter 3 --output RAPORTI_I_RI.docx
```

Gjeneruesi verifikon që baza përmban Kapitullin II dhe refuzon shtimin e dyfishtë të Kapitullit III. Ai ruan bazën dhe zgjeron përmbajtjen automatike. Një korrigjim i kufizuar në paragrafin e portave të Kapitullit II përfshin tani MongoDB në `127.0.0.1:27017` për Compass, sipas ndryshimit ekzistues të përdoruesit në Compose. Çdo ndryshim tjetër manual në atë paragraf kërkon harmonizim përpara rindërtimit; nuk mbishkruhet në heshtje.

Për t'i shtuar Kapitullin IV versionit të kontrolluar me kapitujt I–III:

```powershell
python ./scripts/build-word-report.py --base docs/Raporti_Projektit_Monitorimi_i_Burimeve_Kapitulli_III.docx --chapter 4 --output RAPORTI_I_RI.docx
```

Kjo mënyrë ruan të gjithë kapitujt ekzistues dhe shton përfundimet me tri nënndarje. Refuzohet baza pa kapitujt I–III dhe një dokument që përmban tashmë Kapitullin IV ose V. Për këtë shtim ndryshohen vetëm trupi i dokumentit, përmbajtja automatike dhe metadata për përshkrimin e draftit; stilet dhe pjesët e tjera të paketës Word ruhen.

Për të plotësuar një bazë I–IV me abstraktin, referencat dhe citimet:

```powershell
python ./scripts/build-word-report.py --base docs/Raporti_Projektit_Monitorimi_i_Burimeve_Kapitulli_IV.docx --finish --output RAPORTI_I_PLOTE.docx
```

`--finish` përdoret pa `--chapter`. Burimi i strukturuar i bibliografisë është [referencat.json](referencat.json); [kapitulli-5.md](kapitulli-5.md) është kopja për lexim. [citimet.json](citimet.json) përcakton paragrafët dhe numrat e referencave. Nëse një paragraf i përzgjedhur mungon ose nuk është unik, gjeneruesi ndalet për harmonizim. Refuzohet shtimi i dyfishtë i abstraktit ose i referencave. Numrat në tekst lidhen me shënuesit e bibliografisë, ndërsa URL-të përdorin lidhje native të Word-it.

Skripta refuzon të zëvendësojë një dalje ekzistuese pa `--overwrite` dhe nuk lejon të njëjtën rrugë hyrjeje/daljeje. Mos përdorni këtë opsion mbi ndryshime manuale në Word që nuk janë përfshirë në burimin e raportit.

Pas ndërhyrjes së përdoruesit, kontrolli vizual kaloi në konvertim lokal pa dritare, në një kontejner të veçantë. Materialet e përkohshme të kontrollit ruhen në `.runtime/word-review/`, jashtë dokumentit dhe konfigurimit të aplikacionit.

Versioni i parë i kontrolluar ka **katër faqe**: ballina, përmbajtja dhe dy faqe të Kapitullit I. U përdor LibreOffice Writer 7.4.7.2 pa ndërfaqe, me fontet Palatino Linotype të instaluara në pajisje. U korrigjua struktura e fushës TOC; konvertuesi e njeh si indeks dhe i përditëson hyrjet. U inspektuan të katër faqet e konvertuara. Ky është kontroll me konvertim në sfond, jo verifikim përfundimtar në motorin e Microsoft Word-it.

Përmbajtja ruan fushat TOC/PAGEREF dhe numrat e kontrolluar. Përditësimi në hapje është çaktivizuar për të shmangur dialogun e panevojshëm të Word-it; përdoruesi mund ta përditësojë indeksin me komandën **Update Field / Update entire table** pas shtimit të kapitujve.

Kapitulli II u kontrollua me të njëjtin proces në sfond. Ai zë faqet **5–8**; nëntë hyrjet e përmbajtjes përputhen me faqet e titujve. Teksti i ballinës dhe i Kapitullit I u verifikua i pandryshuar. Kaluan **23 kontrolle** të ruajtura te [verifikimi-kapitulli-2.json](verifikimi-kapitulli-2.json); u inspektuan pamjet e katër faqeve të reja dhe indeksi i përditësuar. Parapamja e arkitekturës është te [parapamje-kapitulli-2.png](parapamje-kapitulli-2.png). Nuk u futën imazhe, nuk u përdor desktopi aktiv dhe nuk u krye push në GitHub.

Kapitulli III u kontrollua në sfond me **21 faqe gjithsej** dhe 18 hyrje në përmbajtjen automatike. U inspektuan të gjitha faqet e konvertuara. Kaluan **62 kontrolle të dokumentit dhe burimeve numerike**, të ruajtura te [verifikimi-kapitulli-3.json](verifikimi-kapitulli-3.json). Këto janë kontrolle të këtij dorëzimi Word, të ndara nga 31 testet e aplikacionit dhe 127 kontrollet historike të fazës 5. Matjet u krahasuan me rekordet JSON, CSV dhe gjurmën e ruajtur; eksperimentet nuk u përsëritën.

Përveç indeksit dhe paragrafit të dokumentuar të Compass në Kapitullin II, përmbajtja e bazës mbeti e pandryshuar gjatë shtimit të Kapitullit III. Drafti i mëparshëm Word, kredencialet, konfigurimi i aplikacionit dhe evidenca nuk u ndryshuan. Parapamja e një faqeje të rezultateve është te [parapamje-kapitulli-3.png](parapamje-kapitulli-3.png).

Kapitulli IV u shtua pas rishikimit, duke e çuar dokumentin në **22 faqe**. Përmbajtja automatike ka 22 hyrje me numra të verifikuar. Kaluan **38 kontrolle të dokumentit**, të regjistruara te [verifikimi-kapitulli-4.json](verifikimi-kapitulli-4.json). U inspektuan indeksi dhe faqja e përfundimeve; 20 faqet e tjera dolën identike piksel për piksel me konvertimin e kontrolluar të Kapitullit III. Të gjithë paragrafët, tabelat dhe kornizat e kapitujve I–III mbetën të pandryshuara. Parapamja është te [parapamje-kapitulli-4.png](parapamje-kapitulli-4.png).

Përfundimet mbështeten në rezultatet e ruajtura dhe nuk paraqesin eksperimente të reja. Dokumenti i hapur i mëparshëm u lexua pa ndryshime dhe dorëzimi ka emër të ri. Nuk u përdor desktopi aktiv dhe nuk u krye push në GitHub.

## Kontrolli i versionit të plotë

Kaluan **46 kontrolle të dokumentit**, të regjistruara te [verifikimi-raporti-plote.json](verifikimi-raporti-plote.json). U kontrolluan 25 faqet, përmbajtja automatike, shënuesit, citimet, URL-të e bibliografisë, figurat/tabelat dhe përputhja me bazën I–IV. Teksti i mëparshëm është ruajtur; ndryshimet brenda tij janë vetëm 22 shtesa citimesh. Të gjitha tabelat dhe kornizat mbetën të pandryshuara.

Kontrolli i burimeve është te [verifikimi-burimeve.json](verifikimi-burimeve.json). U lexuan dokumentacionet zyrtare dhe faqja e repository-t; dosja e evidencës u verifikua edhe me GitHub API dhe skedarët lokalë. Gjurma e ruajtur mbështet numrin 142 në abstrakt, ndërsa katër rekordet mbështesin përfundimet për ekzekutimet e ruajtura pa gabime të raportuara. Nuk u nisën ngarkesa të reja.

Parapamjet e kontrollit janë [abstrakti](parapamje-abstrakti.png) dhe [referencat](parapamje-referencat.png). Ato janë materiale të kontrollit, ndërsa dorëzimi është dokumenti Word i lidhur në krye. Konvertimi u bë në sfond dhe mbetet i dallueshëm nga një kontroll përfundimtar në motorin e Microsoft Word-it. Nuk u përdor desktopi aktiv, nuk u zëvendësuan draftet e hapura dhe nuk u krye push në GitHub.
