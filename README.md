# Regnskapsdashboard

Søk opp et selskap på Oslo Børs med navn eller ticker – eller skriv inn et hvilket som helst
norsk organisasjonsnummer – og få et dashboard med selskapsinfo,
hovedtall og nøkkeltall fra siste årsregnskap – hentet direkte fra
Brønnøysundregistrene. Appen bruker **ingen KI-tjenester** når den kjører;
alt er vanlig Python som regner på åpne data.

## Hva appen viser

- **Søk** – ett felt for navn, ticker eller org.nr. Selskapene på Oslo Børs, Euronext Expand og
  Euronext Growth (ca. 290) ligger lagret med org.nr i `data/oslo_bors.json` og foreslås mens du
  skriver – bare forslag som faktisk inneholder teksten (ticker først, så navn). Feltet er et vanlig
  tekstfelt med ×-knapp, piltaster, Enter og Esc. Alle andre selskaper søkes opp med org.nr.
  Passer et navn flere selskaper, vises valg.
  Selskaper som er notert i Oslo men registrert i utlandet (f.eks. Frontline), får en forklaring
  på hvorfor de ikke har årsregnskap i Regnskapsregisteret.
- **Selskapskort** – navn, org.nr, organisasjonsform, næring, adresse, ansatte,
  stiftelsesdato, aksjekapital, hjemmeside og varsel ved konkurs/avvikling.
- **Søk på alle norske selskaper** – finnes ikke navnet blant børsselskapene, søkes det i Enhetsregisteret
  (bare selskapsformer som leverer årsregnskap: AS, ASA, SA osv.). Treffene vises som knapper.
- **Nøkkeltall i vanlig språk** (`tolkning.py`) – hvert nøkkeltall får en vurdering (Sterk / Middels / Svak etter en
  tommelfingerregel) og én setning i kroner, f.eks. «Av hver 100 kr i inntekter satt selskapet igjen med 8,2 kr».
- **Beløp i kroner** (`valuta.py`) – for selskaper som rapporterer i USD, EUR o.l. vises hovedtallene også omtrent i
  NOK, omregnet med Norges Banks årlige snittkurs (åpent API). Feiler kurs-oppslaget, vises bare originalvalutaen.
- **Minisøyler** i hovedtallkortene viser utviklingen over årene (valgt år uthevet, underskudd rødt).
- **Faner** – Oversikt · Nøkkeltall · Grafer · Utvikling · Sammenlign · Detaljer, i stedet for én lang side.
  En sammenligningslenke (`?mot=`) åpner rett på Sammenlign.
- **Kort fortalt** – et sammendrag i klartekst øverst i Oversikt (`sammendrag.py`): en overskrift («Lønnsomt og
  solid i 2025») og 5–8 setninger om inntekter, resultat og største driver, margin, skatt, soliditet, likviditet og
  konkursrisiko. Fargede prikker viser retning. Regelbasert, ingen KI.
- **Konkursrisiko (Altman Z'')** – 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4 (arbeidskapital, opptjent egenkapital og
  driftsresultat delt på eiendeler, og egenkapital delt på gjeld). Over 2,6 er trygg sone, 1,1–2,6 er gråsone og
  under 1,1 er faresone. Vises som et kort med skala og bidraget fra hver del, og som nøkkeltall under Soliditet.
  Mangler opptjent egenkapital, regnes den som egenkapital minus innskutt. Når nesten alt er ført som innskutt
  (noen IFRS-konsern, f.eks. Equinor konsern), varsles det at scoren trolig er for lav.
- **Hovedtall** – driftsinntekter, driftsresultat, årsresultat, sum eiendeler og
  egenkapital, med endring fra året før.
- **Nøkkeltall** med formel, forklaring og tallene som er brukt:

  | Nøkkeltall | Formel |
  |---|---|
  | Driftsmargin | Driftsresultat ÷ Sum driftsinntekter |
  | Resultatmargin | Ordinært resultat før skatt ÷ Sum driftsinntekter |
  | Totalrentabilitet | (Resultat før skatt + Rentekostnader) ÷ Sum eiendeler – når rentekostnader er oppgitt; ellers (Driftsresultat + Finansinntekter) ÷ Sum eiendeler |
  | Egenkapitalrentabilitet | Årsresultat ÷ Sum egenkapital |
  | Effektiv skattesats | Skattekostnad ÷ Resultat før skatt («ikke meningsfull» ved resultat ≤ 0) |
  | Likviditetsgrad 1 | Omløpsmidler ÷ Kortsiktig gjeld |
  | Likviditetsgrad 2 | (Omløpsmidler − Varer) ÷ Kortsiktig gjeld. Mangler varer, men fordringer + investeringer + bank = omløpsmidler, er varelageret 0 |
  | Arbeidskapital | Omløpsmidler − Kortsiktig gjeld |
  | Egenkapitalandel | Sum egenkapital ÷ Sum egenkapital og gjeld |
  | Gjeldsgrad | Sum gjeld ÷ Sum egenkapital |
  | Rentedekningsgrad | (Resultat før skatt + Rentekostnader) ÷ Rentekostnader |
  | Konkursrisiko (Altman Z'') | Se over |

- **Balansekontroll** – sjekker at eiendeler = egenkapital + gjeld, og at
  delsummene stemmer. Små avvik (≤ 0,01 % eller ≤ 1 000) merkes som avrunding.
- **Grafer** – balansen (eiendeler mot egenkapital og gjeld) og veien fra
  driftsinntekter til årsresultat.
- **Forklaringer («i»-knapper)** – hvert kort har en liten, dempet «i». Trykk for en kort forklaring i
  vanlig språk (f.eks. selskap vs. konsern, hva driftsresultat er). Trykk utenfor eller Esc lukker; på mobil
  vises forklaringen som et ark nederst. Alle forklaringene finnes også samlet i **Ordliste** under Detaljer.
  Tekstene ligger i `forklaringer.py`.
- **Velg regnskapsår** – de årene Regnskapsregisterets API har tall for (vanligvis de tre siste).
  Eldre år finnes som **PDF-kopi av årsregnskapet** (ofte helt tilbake til 2011), lenket nederst på siden.
- **Hva endret seg?** – de **tre resultatpostene som flyttet årsresultatet mest** fra året før
  (driftsinntekter, driftskostnader, netto finans, skatt; resten som «Andre poster»). Bidragene
  summerer seg til hele endringen. Ved siden av: **hendelser i registrene** de siste 24 månedene
  (styre/daglig leder/revisor endret, kapitalendring, nye vedtekter, navneendring). Alt er regelbasert –
  ingen KI. Nyheter, oppkjøp og kontrakter finnes ikke i de åpne registrene.
- **Hva endret seg i balansen?** – postene som flyttet seg mest på hver side av balansen (anleggsmidler,
  varer, fordringer, investeringer, bank / egenkapital, langsiktig og kortsiktig gjeld). Nøytrale farger,
  fordi en økning i f.eks. gjeld verken er god eller dårlig i seg selv. Summerer til hele endringen.
- **Rentedekningsgrad** – (resultat før skatt + rentekostnader) ÷ rentekostnader, under Soliditet. Vises som
  «mangler» når selskapet ikke har oppgitt rentekostnader.
- **Utvikling** – inntekter og resultat per år, og alle hovedtall og nøkkeltall i en tabell over år.
- **Sammenlign** – søk opp et annet selskap (navn, ticker eller org.nr) og se hovedtall og nøkkeltall side om side, med det sterkeste
  nøkkeltallet uthevet og en graf over marginer og rentabilitet. Samme år og regnskapstype brukes når det
  finnes. Er ett av selskapene et eierselskap, vises begge som konsern. Lenke: `?orgnr=923609016&mot=914778271`.
- **Advarsel ved feil i registerdata** – går balansen ikke opp (f.eks. Telenor ASA og Yara ASA 2024,
  der én side av balansen er registrert feil i API-et), forklares det og lenkes til PDF-en for året.
- **Excel-nedlasting** – regnskapstallene og nøkkeltallene som ekte Excel-formler,
  med formelteksten synlig i en egen kolonne.

## Viktige valg

- **Eierselskaper vises som konsern først.** Er morselskapets finansinntekter større enn
  driftsinntektene (typisk for Hydro, Telenor, Orkla, Yara og Kongsberg, der driften ligger i
  datterselskapene og morselskapet lever av utbytte, konsernbidrag og renter), åpner appen på
  konsernregnskapet og forklarer hvorfor. Selskap kan fortsatt velges.
- **Rentekostnader:** API-et har `annenRentekostnad` og `rentekostnadSammeKonsern` for noen
  selskaper (12 av 36 regnskap i testutvalget). Da brukes lærebokformelen for totalrentabilitet.
- **Nettoførte finansposter:** Mangler finanskostnader og «finansinntekter» er lik netto finans,
  har selskapet trolig rapportert finansposter netto på én linje. Appen sier fra om det.
- **Manglende tall vises som «mangler»**, aldri som 0. Et nøkkeltall som bygger
  på et manglende tall blir også «mangler». Det samme gjelder i Excel.
- **Selskap eller konsern:** For konsern finnes ofte begge. Selskap vises først,
  og du kan bytte.
- **Valuta:** Noen selskap (f.eks. Equinor) rapporterer i USD. Appen viser alltid
  valutaen fra regnskapet.
- **Rentabilitet** er regnet på balansen ved årets slutt (ikke snitt).
- **Negativ egenkapital:** Egenkapitalrentabilitet og gjeldsgrad vises da som
  «ikke meningsfull».
- **Banker og forsikringsselskap:** Regnskapsregisterets åpne API støtter ikke
  deres regnskapsoppstilling. Appen sier fra om det.

## Filstruktur

```
regnskapsdashboard/
├── app.py              # Visning (Streamlit) – kun skjermbilde og grafer
├── brreg_api.py        # Henting fra Brreg, org.nr-validering, tolking av JSON
├── borsliste.py        # Søk på navn/ticker blant selskapene på Oslo Børs
├── komponenter/sok/    # Eget søkefelt (HTML/JS-komponent uten byggesteg): søker i nettleseren, kan tømmes
├── data/oslo_bors.json # Oslo Børs-selskapene med org.nr (lages av verktoy/oppdater_oslo_bors.py)
├── verktoy/            # oppdater_oslo_bors.py: henter Euronext-lista og slår opp org.nr
├── beregninger.py      # Nøkkeltall, Altman Z'', balansekontroll, resultatbro, resultatdrivere (rene funksjoner)
├── sammendrag.py       # «Kort fortalt»: regelbasert sammendrag i klartekst
├── tolkning.py         # Vurdering (sterk/middels/svak) og klartekst per nøkkeltall
├── valuta.py           # Norges Banks valutakurser og omregning til NOK
├── excel_eksport.py    # Lager Excel-fila med formler
├── formatering.py      # Norsk tallformat og «mangler»
├── forklaringer.py     # Enkle forklaringer (i-knapper og ordliste)
├── stil.py             # Utseende i Apple-stil: fargetokens, CSS, HTML-byggesteiner
├── static/             # App-ikon (favicon, apple-touch-icon, 512 px)
├── launchd/            # LaunchAgent som holder appen i gang på port 8766 (lokal, ikke i git: har stier til din Mac)
├── .streamlit/config.toml
├── requirements.txt
├── tests/
│   ├── test_beregninger.py   # Nøkkeltall, manglende tall, kontroll, validering, API-feil
│   ├── test_excel.py         # Formler i Excel-fila
│   ├── test_sammendrag.py    # Sammendraget i klartekst
│   ├── test_skatt_likviditet2_altman.py
│   └── data/                 # Lagret API-svar for Equinor (testdata)
├── utforsking/         # Råsvarene fra første utforsking av API-et
├── README.md
└── PUBLISERING.md      # Slik publiserer du appen på nett
```

## Kjør lokalt

```bash
cd ~/ClaudeC/regnskapsdashboard
python3 -m venv .venv                 # bare første gang
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Appen åpner seg på http://localhost:8501. Du kan også lenke direkte til et
selskap: `http://localhost:8501/?orgnr=923609016`.

## Alltid på, som en app i Dock (Mac)

Som Fondsdashboardet kan appen kjøre i bakgrunnen hele tiden på
**http://localhost:8766**, startet av macOS ved innlogging og restartet hvis den krasjer.

```bash
cp ~/ClaudeC/regnskapsdashboard/launchd/no.regnskapsdashboard.server.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/no.regnskapsdashboard.server.plist
```

Åpne så http://localhost:8766 i Safari → **Arkiv → Legg til i Dock**. Appen får
eget ikon (`static/apple-touch-icon.png`) og åpner i sitt eget vindu.

- Logg: `logg/server.log`
- Stoppe: `launchctl unload ~/Library/LaunchAgents/no.regnskapsdashboard.server.plist`
- Etter kodeendringer: Streamlit laster `app.py` på nytt selv; endringer i de andre
  modulene krever omstart (`unload` + `load`).

## Kjør testene

```bash
.venv/bin/python -m pytest
```

Testene går uten nettverk. De sjekker blant annet hvert nøkkeltall mot et
håndregnet fasitsvar, at manglende tall gir «mangler» og ikke 0, deling på null,
negativ egenkapital, balansekontroll (inkludert et ekte avrundingsavvik hos
Equinor), org.nr-kontrollsiffer, feilkoder fra API-et og at Excel-formlene peker
på riktige celler.

## Datakilder

- Enhetsregisteret: `https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}`
- Regnskapsregisteret: `https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}`

Begge er åpne og gratis, uten innlogging (lisens NLOD). Svar mellomlagres i én
time i appen.

## Oppdatere lista over Oslo Børs-selskaper

Lista endrer seg når selskaper børsnoteres eller tas av børs. Kjør av og til:

```bash
.venv/bin/python verktoy/oppdater_oslo_bors.py
launchctl kickstart -k gui/$(id -u)/no.regnskapsdashboard.server
```

Skriptet henter aksjelista fra Euronext og slår opp org.nr i Enhetsregisteret på navn. Treff det ikke
er sikkert på, skrives ut til slutt. Rett dem i `MANUELT` øverst i skriptet og kjør på nytt.
