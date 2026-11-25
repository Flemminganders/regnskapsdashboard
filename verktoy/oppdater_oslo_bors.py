"""Lager ``data/oslo_bors.json``: aksjene på Oslo Børs med org.nr, så de kan søkes opp med navn.

Kjør fra prosjektmappa:  .venv/bin/python verktoy/oppdater_oslo_bors.py

1. Henter lista over aksjer fra Euronext (Oslo Børs, Euronext Expand og Euronext Growth).
   Den har navn, ticker og ISIN, men ikke org.nr.
2. Slår opp hvert norsk selskap (ISIN som starter med «NO») i Enhetsregisteret på navn.
   Euronext forkorter navn til 18 tegn, så treff på starten av navnet godtas også.
3. Selskaper registrert i utlandet har ikke årsregnskap i Regnskapsregisteret. De lagres
   uten org.nr, så appen kan forklare hvorfor.

Treff som ikke er sikre skrives ut til slutt. Rett dem i ``MANUELT`` under og kjør på nytt.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

MAPPE = Path(__file__).resolve().parent.parent
UT = MAPPE / "data" / "oslo_bors.json"
EURONEXT = "https://live.euronext.com/en/pd_es/data/stocks/download?mics=XOSL%2CMERK%2CXOAS"
BRREG_SOK = "https://data.brreg.no/enhetsregisteret/api/enheter"

# Ticker -> org.nr (eller None) for selskaper navnesøket ikke finner riktig.
# Sjekket for hånd 2026-11-25. None = registrert i utlandet / ikke i Enhetsregisteret.
MANUELT: Dict[str, Optional[str]] = {
    "ODF": "930192503", "ODFB": "930192503",      # Odfjell SE
    "NORDH": "926978209",                         # Nordhealth AS
    "NTG": "926789759",                           # Nordic Technology Group AS
    "ENDUR": "991279539",                         # Endúr ASA (navnesøket tåler ikke aksenten)
    "IOX": "988247006",                           # Interoil Exploration and Production ASA
    "SB68": "937905378",                          # Sparebank 68 Grader Nord
    "BRUT": None, "OMC": None, "COSH": None,      # Bruton, OMC Tankers, Constellation Oil Services
}

# Rangering av organisasjonsform når flere har samme navn.
FORM_RANG = {"ASA": 0, "SPA": 1, "SE": 1, "AS": 2, "SA": 3}


def hent_euronext() -> List[Dict[str, str]]:
    data = {"args[fe_type]": "csv", "args[fe_decimal]": ".", "args[fe_date_format]": "d/m/Y",
            "args[initialLetter]": "", "iDisplayLength": "3000", "iDisplayStart": "0"}
    svar = requests.post(EURONEXT, data=data, timeout=60)
    svar.raise_for_status()
    rader = list(csv.reader(io.StringIO(svar.content.decode("utf-8-sig")), delimiter=";"))
    hode = rader[0]
    ut = []
    for rad in rader[1:]:
        if len(rad) < 4 or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", rad[1] or ""):
            continue  # topptekst-linjer
        d = dict(zip(hode, rad))
        ut.append({"navn": d["Name"], "isin": d["ISIN"], "ticker": d["Symbol"], "marked": d["Market"]})
    return ut


def normaliser(navn: str) -> str:
    # Fjern aksenter (Ú -> U), men behold Æ, Ø og Å.
    n = "".join(c for c in unicodedata.normalize("NFKD", navn.upper().replace("Å", "\0"))
                if not unicodedata.combining(c)).replace("\0", "Å")
    n = n.replace("&", " OG ")
    n = re.sub(r"[^A-Z0-9ÆØÅ ]", " ", n)
    n = re.sub(r"\s+(ASA|AS|SA|LTD|LIMITED|PLC|AB|NUF|SE)$", "", n.strip())
    return re.sub(r"\s+", " ", n).strip()


# Euronext-forkortelser -> fullt ord (brukes i reservesøket).
FORKORTELSER = {"SPBK": "SPAREBANK", "SPBK1": "SPAREBANK 1", "SPB": "SPAREBANK", "SPAREBK": "SPAREBANK",
                "SPAREB": "SPAREBANK", "SPARBNK": "SPAREBANK", "GP": "GROUP", "GRP": "GROUP", "GR": "GROUP",
                "FORSIKRG": "FORSIKRING", "EXPL": "EXPLORATION", "PROD": "PRODUCTION", "HOLD": "HOLDING",
                "OGLAND": "OG LANDMANDSBANK", "AKE": "AKERSHUS"}
STOPP = {"A", "B", "SER", "A AKSJE", "AKSJE"}


def tokens(navn: str) -> List[str]:
    t = normaliser(navn).replace("A AKSJE", "").split()
    ut: List[str] = []
    for x in t:
        ut.extend(FORKORTELSER.get(x, x).split())
    while ut and ut[-1] in ("A", "B", "SER"):
        ut.pop()
    return [x for x in ut if x != "SER"]


def token_treff(euronavn: str, brregnavn: str) -> bool:
    """Hvert ord i Euronext-navnet er starten på tilsvarende ord i Brreg-navnet."""
    e, b = tokens(euronavn), normaliser(brregnavn).split()
    return bool(e) and len(b) >= len(e) and all(bb.startswith(ee) for ee, bb in zip(e, b))


def reservesok(euronavn: str) -> tuple:
    t = tokens(euronavn)
    for n in (min(2, len(t)), 1):
        kandidater = [k for k in sok_brreg(" ".join(t[:n]))
                      if not k.get("konkurs") and not k.get("underAvvikling")
                      and k.get("organisasjonsform", {}).get("kode") in FORM_RANG
                      and token_treff(euronavn, k["navn"])]
        if kandidater:
            kandidater.sort(key=lambda k: (FORM_RANG[k["organisasjonsform"]["kode"]], len(k["navn"])))
            beste = kandidater[0]
            # Godta bare når valget er entydig blant ASA/sparebanker.
            topp = [k for k in kandidater if FORM_RANG[k["organisasjonsform"]["kode"]] ==
                    FORM_RANG[beste["organisasjonsform"]["kode"]]]
            return beste, ("ord" if len(topp) == 1 else "flertydig")
    return None, None


def sok_brreg(navn: str) -> List[Dict[str, Any]]:
    svar = requests.get(BRREG_SOK, params={"navn": navn, "size": 50}, timeout=30)
    if svar.status_code != 200:
        return []
    return svar.json().get("_embedded", {}).get("enheter", [])


def velg(kandidater: List[Dict[str, Any]], euronavn: str) -> tuple:
    """(enhet, sikkerhet) der sikkerhet er «eksakt», «start» eller None."""
    mal = normaliser(euronavn)
    aktuelle = [k for k in kandidater if not k.get("konkurs") and not k.get("underAvvikling")
                and k.get("organisasjonsform", {}).get("kode") in FORM_RANG]
    def rang(k):
        return (FORM_RANG[k["organisasjonsform"]["kode"]], -(k.get("antallAnsatte") or 0))
    eksakt = [k for k in aktuelle if normaliser(k["navn"]) == mal]
    if eksakt:
        return sorted(eksakt, key=rang)[0], "eksakt"
    start = [k for k in aktuelle if normaliser(k["navn"]).startswith(mal)]
    asa = [k for k in start if k["organisasjonsform"]["kode"] in ("ASA", "SPA")]
    if len(asa) == 1:
        return asa[0], "start"
    if len(start) == 1:
        return start[0], "start"
    return None, None


def main() -> None:
    aksjer = hent_euronext()
    print(f"{len(aksjer)} aksjer fra Euronext")
    selskaper: Dict[str, Dict[str, Any]] = {}   # nøkkel: org.nr, eller «isin:…» for utenlandske
    usikre = []
    for a in aksjer:
        orgnr: Optional[str] = None
        brregnavn = None
        if a["ticker"] in MANUELT:
            orgnr = MANUELT[a["ticker"]]
            sikkerhet = "manuell"
            if orgnr:
                brregnavn = requests.get(f"{BRREG_SOK}/{orgnr}", timeout=30).json()["navn"]
        elif a["isin"].startswith("NO"):
            enhet, sikkerhet = velg(sok_brreg(normaliser(a["navn"])), a["navn"])
            if enhet is None:
                enhet, sikkerhet = reservesok(a["navn"])
            time.sleep(0.1)
            if enhet and sikkerhet != "flertydig":      # flertydige lagres ikke – legg dem i MANUELT
                orgnr, brregnavn = enhet["organisasjonsnummer"], enhet["navn"]
            if sikkerhet not in ("eksakt", "start"):
                usikre.append((a["ticker"], a["navn"], brregnavn, orgnr, sikkerhet))
        else:
            sikkerhet = "utenlandsk"
        nokkel = orgnr or f"isin:{a['isin']}"
        if nokkel in selskaper:            # flere aksjeklasser i samme selskap
            selskaper[nokkel]["tickere"].append(a["ticker"])
            continue
        selskaper[nokkel] = {
            "navn": brregnavn or a["navn"].title(), "kortnavn": a["navn"].title(), "orgnr": orgnr,
            "tickere": [a["ticker"]], "isin": a["isin"], "marked": a["marked"],
            "utenlandsk": not a["isin"].startswith("NO"),
        }
    liste = sorted(selskaper.values(), key=lambda s: s["kortnavn"])
    UT.parent.mkdir(exist_ok=True)
    UT.write_text(json.dumps({"oppdatert": date.today().isoformat(), "kilde": "Euronext + Enhetsregisteret",
                              "selskaper": liste}, ensure_ascii=False, indent=1))
    med = sum(1 for s in liste if s["orgnr"])
    print(f"Lagret {len(liste)} selskaper ({med} med org.nr) i {UT}")
    if usikre:
        print("\nIkke eksakte treff – sjekk og legg evt. inn i MANUELT:")
        for t in usikre:
            print("  ", t)


if __name__ == "__main__":
    sys.exit(main())
