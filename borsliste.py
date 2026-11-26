"""Selskaper på Oslo Børs: søk på navn eller ticker i stedet for org.nr.

Lista ligger i ``data/oslo_bors.json`` og lages av ``verktoy/oppdater_oslo_bors.py``
(Euronext-lista + oppslag i Enhetsregisteret). Søk på org.nr fungerer for alle selskaper –
lista er bare en snarvei for de børsnoterte.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from stil import pent_navn

FIL = Path(__file__).parent / "data" / "oslo_bors.json"

# Landkode i ISIN -> land, for selskaper registrert i utlandet.
LAND = {"BM": "Bermuda", "CY": "Kypros", "SE": "Sverige", "SG": "Singapore", "NL": "Nederland",
        "DK": "Danmark", "CA": "Canada", "GB": "Storbritannia", "MH": "Marshalløyene", "KY": "Caymanøyene",
        "MT": "Malta", "FO": "Færøyene", "BE": "Belgia", "DE": "Tyskland", "CH": "Sveits", "LU": "Luxembourg",
        "US": "USA", "FI": "Finland", "IS": "Island", "JE": "Jersey", "GG": "Guernsey", "IE": "Irland"}


def land(s: Dict[str, Any]) -> str:
    return LAND.get(s["isin"][:2], "utlandet")


@lru_cache(maxsize=1)
def _data() -> Dict[str, Any]:
    if not FIL.exists():
        return {"oppdatert": None, "selskaper": []}
    return json.loads(FIL.read_text(encoding="utf-8"))


def selskaper() -> List[Dict[str, Any]]:
    return _data()["selskaper"]


def oppdatert() -> Optional[str]:
    return _data().get("oppdatert")


def visningsnavn(s: Dict[str, Any]) -> str:
    """«Equinor» – uten ASA/AS, men ellers slik det står i Enhetsregisteret."""
    navn = pent_navn(s["navn"]) if s.get("orgnr") else s["kortnavn"]
    return re.sub(r"\s+(ASA|AS|SE)$", "", navn)


def etikett(s: Dict[str, Any]) -> str:
    """Teksten i søkelista. Org.nr er med, så det også kan søkes på."""
    tickere = ", ".join(s["tickere"])
    bak = s["orgnr"] if s.get("orgnr") else "registrert i utlandet" if s.get("utenlandsk") else "uten org.nr"
    return f"{visningsnavn(s)} · {tickere} · {bak}"


@lru_cache(maxsize=1)
def _etiketter() -> Dict[str, Dict[str, Any]]:
    return {etikett(s): s for s in sorted(selskaper(), key=lambda s: visningsnavn(s).lower())}


def etiketter() -> List[str]:
    return list(_etiketter())


def etikett_for_orgnr(orgnr: str) -> Optional[str]:
    return next((e for e, s in _etiketter().items() if s.get("orgnr") == orgnr), None)


def _norm(tekst: str) -> str:
    return re.sub(r"[^a-z0-9æøå]", "", tekst.lower())


def tolk(tekst: Optional[str]) -> Tuple[str, Any]:
    """Hva brukeren mente. Returnerer ett av:

    («orgnr», «923609016») – et selskap i lista, eller noe som ser ut som et org.nr
    («utenlandsk», selskap) – børsnotert, men uten norsk org.nr
    («flere», [selskap, …]) – navnet passer flere selskaper
    («ukjent», tekst)       – fant ikke noe
    («tom», None)
    """
    tekst = (tekst or "").strip()
    if not tekst:
        return "tom", None
    s = _etiketter().get(tekst)
    valgt = re.search(r"·\s*(\d{9})\s*$", tekst)       # «Rema 1000 Norge AS · 982254604» fra navnesøket
    if s is None and valgt:
        return "orgnr", valgt.group(1)
    if s is None:
        if re.fullmatch(r"[\d\s.\-]+", tekst):
            return "orgnr", tekst          # valideres av brreg_api.valider_orgnr
        n = _norm(tekst)
        alle = selskaper()
        treff = [x for x in alle if any(_norm(t) == n for t in x["tickere"])]
        treff = treff or [x for x in alle if _norm(visningsnavn(x)) == n]
        treff = treff or [x for x in alle if _norm(visningsnavn(x)).startswith(n)
                          or _norm(x["kortnavn"]).startswith(n)]
        if not treff:
            return "ukjent", tekst
        if len(treff) > 1:
            return "flere", treff
        s = treff[0]
    if s.get("orgnr"):
        return "orgnr", s["orgnr"]
    return "utenlandsk", s


@lru_cache(maxsize=1)
def forslag() -> List[Dict[str, str]]:
    """Kompakt liste til søkefeltet i nettleseren: etikett, navn, tickere, org.nr og marked/land."""
    ut = []
    for e, s in _etiketter().items():
        if s.get("orgnr"):
            m = s["marked"]
        elif s.get("utenlandsk"):
            m = f"registrert i {land(s)}"
        else:
            m = "uten org.nr"
        ut.append({"e": e, "n": visningsnavn(s), "t": ", ".join(s["tickere"]), "o": s.get("orgnr") or "", "m": m})
    return ut
