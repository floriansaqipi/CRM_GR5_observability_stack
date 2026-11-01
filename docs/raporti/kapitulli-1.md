# I. Përshkrimi i problemit

## 1.1. Problemi dhe motivimi

Aplikacionet e ndara në disa kontejnerë përdorin burime të përbashkëta të pajisjes ku ekzekutohen. Një shërbim mund të kryejë llogaritje, një tjetër të mbajë të dhëna në memorie, ndërsa një i tretë të lexojë nga databaza ose të dërgojë të dhëna përmes rrjetit. Edhe kur aplikacioni përgjigjet saktë, vetëm përgjigjja e tij nuk tregon sa CPU, memorie apo trafik rrjeti ka kërkuar për ta përfunduar punën. Për këtë arsye, funksionimi i aplikacionit duhet të shoqërohet me matje të burimeve që ai përdor.

Problemi i trajtuar në këtë projekt është ndërtimi i një mjedisi ku aktiviteti i kontrolluar i aplikacionit mund të lidhet me matjet reale të kontejnerëve. Kërkesa fillestare e laboratorit është një panel për monitorimin e CPU-së, RAM-it dhe rrjetit, duke përdorur Prometheus, Grafana dhe Flask. Për ta bërë këtë kërkesë të demonstrueshme, projekti përfshin edhe shërbime që gjenerojnë ngarkesa të kufizuara. Kështu, ndryshimi në grafik mund të lidhet me një veprim të njohur, si kryerja e llogaritjeve ose mbajtja e një buffer-i në memorie.

Në një sistem me disa shërbime, interpretimi i matjeve kërkon të dihet edhe ku kryhet puna. Për shembull, gjatë një eksperimenti rrjeti, Data kërkon të dhëna nga Compute. Trafiku i pranuar pritet të rritet te Data, ndërsa trafiku i dërguar te Compute. Një grafik i vetëm, pa dallimin e shërbimit dhe drejtimit të trafikut, do ta bënte më të vështirë shpjegimin e këtij aktiviteti. E njëjta nevojë paraqitet kur memoria e kontejnerit krahasohet me madhësinë e buffer-it të kërkuar ose kur përdorimi i CPU-së krahasohet me kuotën e lejuar.

Përveç matjeve të burimeve, është e dobishme të shihet çfarë po bën vetë aplikacioni. Numri i operacioneve, koha e ekzekutimit dhe gabimet ndihmojnë në interpretimin e ngarkesës. Gjurmimi i shpërndarë e plotëson këtë pamje duke lidhur operacionet e një eksperimenti ndërmjet shërbimeve. Në këtë raport, observabiliteti nënkupton pikërisht këtë mundësi për të kuptuar sjelljen e sistemit përmes matjeve dhe gjurmëve që ai prodhon.

## 1.2. Qëllimi dhe objektivat

Qëllimi kryesor është të ndërtohet një laborator lokal, i riprodhueshëm dhe i kuptueshëm, ku përdoruesi nis një eksperiment, vëzhgon ndikimin e tij në burime dhe shqyrton rezultatin e ruajtur. Flask ofron ndërfaqen dhe koordinimin e punës, Prometheus mbledh e ruan metrikat, ndërsa Grafana i paraqet ato në kohë. cAdvisor siguron matjet e burimeve të kontejnerëve. Këto përgjegjësi mbeten të ndara, në mënyrë që gjenerimi i ngarkesës të mos ngatërrohet me matjen e saj.

Objektivat konkrete të projektit janë:

- Të maten CPU-ja, memoria dhe trafiku i rrjetit për secilin shërbim dhe të paraqiten në Grafana me njësi dhe filtra të qartë.
- Të ofrohen ngarkesa për CPU, memorie, rrjet, databazë dhe punë të kombinuar, si dhe një ngarkesë CPU me sasi fikse llogaritjesh për krahasime.
- Të mbahet ndërfaqja e përdorshme gjatë ekzekutimit, me një eksperiment aktiv në të njëjtën kohë, kufij të përcaktuar dhe mundësi ndalimi e pastrimi.
- Të ruhen parametrat, konfigurimi i verifikuar i vendosjes dhe rezultatet reale, duke mundësuar shqyrtimin e historikut dhe eksportin CSV.
- Të lidhen matjet e burimeve me metrikat e aplikacionit dhe me gjurmët e operacioneve ndërmjet shërbimeve.
- Të mundësohen krahasime të kontrolluara të kufijve CPU, memories dhe një ose dy instancave Compute, me sasi pune të njohur.

Një rezultat i vlefshëm për laboratorin nuk është vetëm shfaqja e një grafiku. Duhet të mund të shpjegohet cili veprim e shkaktoi ndryshimin, në cilin shërbim u krye puna, cilët parametra u përdorën dhe çfarë rezultati u raportua. Ruajtja e këtyre të dhënave e bën demonstrimin të kontrollueshëm edhe pasi eksperimenti ka përfunduar.

## 1.3. Kufijtë e implementimit

Sistemi ekzekutohet në një laptop me Docker Desktop dhe kontejnerë Linux. Ai ilustron koncepte të menaxhimit të burimeve në cloud, por vendosja e realizuar është lokale. Matjet lidhen me kontejnerët e projektit; ato nuk përfaqësojnë të gjithë përdorimin e pajisjes Windows. Konfigurimi bazë ka shtatë shërbime pa gjurmim dhe nëntë kur aktivizohen OpenTelemetry Collector dhe Tempo. Instanca opsionale Compute-2 shton një kontejner për krahasimet me replika.

Puna është zhvilluar në pesë faza. Fillimisht u realizua monitorimi i burimeve, pastaj kontrolli ndërveprues dhe historiku i eksperimenteve. Më tej u shtuan metrikat e aplikacionit dhe gjurmimi, konfigurimet e alokimit dhe krahasimet me replika. Faza e pestë përmirësoi ndërfaqen dhe dashboard-et, ruajti katër eksperimente shembull dhe përgatiti udhëzuesit praktikë. Raporti dokumenton këtë gjendje të implementuar.

Ngarkesat janë sintetike dhe kanë kufij të përcaktuar. Ato shërbejnë për të krijuar aktivitet të dallueshëm, jo për të përfaqësuar një aplikacion prodhimi ose trafik real përdoruesish. Vlerat e kërkuara, si intensiteti CPU apo numri i kërkesave për sekondë, janë hyrje të eksperimentit. Konsumi i matur dhe ritmi i arritur janë rezultate që mund të ndikohen nga sistemi operativ, kufijtë e kontejnerit dhe puna shtesë e shërbimeve të monitorimit.

Katër eksperimentet e ruajtura për CPU, memorie, rrjet dhe punë të kombinuar janë shembuj me nga një ekzekutim për skenar. Edhe krahasimet e alokimit dhe replikave trajtohen si matje verifikimi. Ato tregojnë sjelljen e sistemit në kushtet e regjistruara, por nuk mjaftojnë për përfundime statistikore ose garanci për përshpejtim. Një studim formal me përsëritje mbetet punë e ardhshme. Në kapitujt vijues shpjegohen teknologjitë, implementimi dhe rezultatet mbi bazën e evidencës së ruajtur.
