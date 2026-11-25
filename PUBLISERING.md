# Slik publiserer du Regnskapsdashboard

Den enkleste måten er **Streamlit Community Cloud**. Det er gratis, krever ingen
server, og appen får en egen nettadresse (f.eks.
`https://regnskapsdashboard.streamlit.app`). Appen trenger ingen API-nøkler eller
hemmeligheter, fordi Brreg-dataene er åpne.

Du trenger:
- en GitHub-konto (gratis): https://github.com/signup
- Git på Mac-en (finnes allerede – sjekk med `git --version` i Terminal)

---

## Steg 1 – Legg koden i et Git-repo (lokalt)

Åpne Terminal og kjør:

```bash
cd ~/ClaudeC/regnskapsdashboard
git init
git add .
git commit -m "Første versjon av regnskapsdashboard"
```

`.gitignore` sørger for at `.venv/` (de installerte pakkene) og andre lokale filer
ikke blir med.

## Steg 2 – Lag et repo på GitHub og last opp

1. Gå til https://github.com/new
2. **Repository name:** `regnskapsdashboard`
3. Velg **Public** (Community Cloud krever offentlig repo på gratisplanen –
   koden inneholder ingen hemmeligheter, så det er trygt).
4. **Ikke** huk av for README, .gitignore eller lisens (de finnes allerede).
5. Trykk **Create repository**.

GitHub viser deretter noen kommandoer. Bruk disse (bytt ut `DITT-BRUKERNAVN`):

```bash
git remote add origin https://github.com/DITT-BRUKERNAVN/regnskapsdashboard.git
git branch -M main
git push -u origin main
```

Spør Git om passord, bruker du et *Personal access token* i stedet for passordet
ditt: GitHub → Settings → Developer settings → Personal access tokens → Tokens
(classic) → Generate new token, med tilgang `repo`.

> Har du GitHub CLI (`gh`), kan steg 2 gjøres i én kommando:
> `gh repo create regnskapsdashboard --public --source=. --push`

## Steg 3 – Publiser på Streamlit Community Cloud

1. Gå til https://share.streamlit.io og logg inn med GitHub-kontoen.
2. Trykk **Create app** → **Deploy a public app from GitHub**.
3. Fyll inn:
   - **Repository:** `DITT-BRUKERNAVN/regnskapsdashboard`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** velg et navn, f.eks. `regnskapsdashboard`
4. Åpne **Advanced settings** og velg **Python 3.12**.
5. Trykk **Deploy**.

Første oppstart tar et par minutter mens pakkene i `requirements.txt` installeres.
Deretter er appen live på adressen du valgte.

## Steg 4 – Oppdatere appen senere

Gjør endringene lokalt, kjør testene, og send dem til GitHub:

```bash
.venv/bin/python -m pytest
git add .
git commit -m "Beskriv endringen"
git push
```

Streamlit Cloud oppdager endringen og oppdaterer appen automatisk i løpet av et
minutt.

---

## Greit å vite

- **Søvn:** Gratisapper sover etter en periode uten besøk. Den som åpner appen
  da, trykker «Yes, get this app back up» og venter ca. 30 sekunder.
- **Deling:** Lenken kan deles med hvem som helst. Lenk gjerne direkte til et
  selskap: `https://DIN-APP.streamlit.app/?orgnr=923609016`.
- **Privat app:** Vil du begrense hvem som ser appen, kan du under
  *Settings → Sharing* i Streamlit Cloud velge at bare inviterte e-postadresser
  har tilgang.
- **Feilsøking:** Går noe galt, trykk **Manage app** nede til høyre i appen for å
  se loggen. Den vanligste feilen er en manglende pakke i `requirements.txt`.
- **Belastning på Brreg:** Svar mellomlagres i én time, så samme selskap hentes
  ikke på nytt hver gang noen laster siden.

## Alternativer

| Tjeneste | Passer når | Merknad |
|---|---|---|
| Streamlit Community Cloud | Du vil ha det enkelt og gratis | Anbefalt |
| Render.com / Railway | Du vil ha privat repo eller eget domene | Startkommando: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` |
| Hugging Face Spaces | Du har allerede HF-konto | Velg «Streamlit» som SDK ved oppretting |
