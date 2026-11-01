# IV. Përfundime

## 4.1. Arritjet kryesore

Projekti realizoi kërkesën për monitorimin e CPU-së, memories dhe rrjetit të kontejnerëve përmes Prometheus dhe Grafana. Aplikacionet Flask krijojnë ngarkesa të kufizuara, ndërsa cAdvisor mat ndikimin e tyre real. Përdoruesi konfiguron eksperimentin, ndjek progresin dhe ndalon punën ose shqyrton rezultatin pas përfundimit. Aktiviteti në grafik lidhet kështu me parametrat dhe veprimin që e shkaktuan.

Numëruesit e aplikacionit tregojnë punën e kryer dhe gabimet; gjurma Combined lidh Controller, Data, Compute dhe thirrjet e klientit MongoDB. Historiku, eksporti CSV dhe konfigurimi i ruajtur i vendosjes mundësojnë kontrollimin e rezultateve. Kontrollet e dokumentuara mbështesin funksionimin e anulimit, pastrimit dhe rikuperimit brenda rasteve të verifikuara.

## 4.2. Gjetjet dhe kufizimet

Katër shembujt treguan ndryshime të dallueshme në burimet përkatëse. CPU e rriti aktivitetin e Compute; alokimi 64 MiB e rriti memorien e Data-s dhe dalja e procesit e afroi atë me nivelin fillestar. Network përfundoi 150 përgjigje, me 37.50 MiB payload, ndërsa Combined përfundoi edhe 150 cikle shkrim/leximi në databazë, pa gabime të raportuara. Memoria totale e kontejnerit përfshin edhe proceset dhe bibliotekat, prandaj nuk barazohet me buffer-in e kërkuar. Pastrimi i dokumenteve nuk garanton lirimin e menjëhershëm të cache-it MongoDB.

Krahasimet CPU me të njëjtën punë dhe checksum treguan kohë më të shkurtër kur u rrit kuota: nga 68.643 sekonda me 0.5 CPU në 14.884 sekonda me 2 CPU. Me dy instanca Compute, puna u nda duke mbajtur dy procese llogaritëse gjithsej. U rritën edhe CPU-ja dhe memoria totale e lejuar; ky rezultat nuk provon efikasitet shkallëzimi me burime të barabarta. Buffer-i 64 MiB u përdor me sukses nën të tre kufijtë e memories të testuar.

Këto janë vëzhgime individuale në një laptop me ngarkesa sintetike. Mostrimi pesësekondësh dhe mesatarizimi mund të zbusin kulmet dhe ta vonojnë paraqitjen e ndryshimit. Matjet përfshijnë punën shtesë të aplikacionit dhe observabilitetit. Rezultatet demonstrojnë mekanizmat e realizuar, pa garanci statistikore për performancën ose përgjithësim në mjedise prodhimi.

## 4.3. Zhvillimi i ardhshëm

Hapi vijues është një studim me përsëritje, rend të kontrolluar të konfigurimeve dhe intervale të njëjta qetësimi. Ai do të lejonte krahasimin e ndryshueshmërisë së kohëve dhe ndikimit të gjurmimit. Zgjerimet mund të përfshijnë ngarkesa nga aplikacione reale, alarme dhe vendosje në makina virtuale ose cloud publik. Parametrat dhe rezultatet e ruajtura ofrojnë bazën për këto prova të kontrolluara.
