"""Omregning til norske kroner for selskaper som rapporterer i en annen valuta (f.eks. USD).

Bruker Norges Banks åpne API for valutakurser: gjennomsnittskursen for hele året
(«A» = årlig). Det er en tilnærming – balansen gjelder 31. desember – men den gir en
god pekepinn på størrelsen i kroner.
"""
from __future__ import annotations

from typing import Dict, Optional

import requests

KURS_URL = "https://data.norges-bank.no/api/data/EXR/A.{valuta}.NOK.SP"
TIMEOUT_SEKUNDER = 10


def tolk_kurser(raa: dict) -> Dict[int, float]:
    """SDMX-JSON fra Norges Bank -> {år: kroner per enhet}. Tar hensyn til enhetsmultiplikator
    (noen valutaer, som JPY og SEK, oppgis per 100)."""
    data = raa["data"]
    serie = next(iter(data["dataSets"][0]["series"].values()))
    perioder = [v["id"] for v in data["structure"]["dimensions"]["observation"][0]["values"]]
    multiplikator = 0
    for attr in data["structure"].get("attributes", {}).get("series", []):
        if attr.get("id") == "UNIT_MULT":
            idx = serie.get("attributes", [0])[data["structure"]["attributes"]["series"].index(attr)]
            multiplikator = int(attr["values"][idx]["id"]) if idx is not None else 0
    faktor = 10 ** multiplikator
    return {int(perioder[int(i)][:4]): float(v[0]) / faktor for i, v in serie["observations"].items()}


def hent_kurser(valuta: str) -> Dict[int, float]:
    """Årlige snittkurser mot NOK. Tom dict ved feil – omregning er et tillegg, ikke nødvendig."""
    if not valuta or valuta == "NOK" or not valuta.isalpha():
        return {}
    try:
        svar = requests.get(KURS_URL.format(valuta=valuta.upper()),
                            params={"format": "sdmx-json", "startPeriod": "2005", "locale": "no"},
                            timeout=TIMEOUT_SEKUNDER)
        if svar.status_code != 200:
            return {}
        return tolk_kurser(svar.json())
    except (requests.RequestException, ValueError, KeyError, IndexError, StopIteration):
        return {}


def til_nok(belop: Optional[float], aar: int, kurser: Dict[int, float]) -> Optional[float]:
    """Beløpet i kroner med årets snittkurs, eller None hvis beløp eller kurs mangler."""
    kurs = kurser.get(aar)
    if belop is None or kurs is None:
        return None
    return belop * kurs
