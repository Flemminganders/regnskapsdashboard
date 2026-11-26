"""Nøkkeltall forklart for folk flest: en vurdering (sterk / middels / svak) og én setning
som sier hva tallet betyr i kroner og øre for akkurat dette selskapet.

Grensene er tommelfingerregler for et «vanlig» selskap. Normalt nivå varierer mye mellom
bransjer (en dagligvarekjede har lave marginer, et programvareselskap høye), så appen sier
alltid at det er en tommelfingerregel. Rene funksjoner – enkle å teste.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import formatering as fmt

# kode -> (svak under, sterk fra, høyere er bedre). For gjeldsgrad er lavere bedre.
GRENSER: Dict[str, Tuple[float, float, bool]] = {
    "driftsmargin": (0.03, 0.10, True),
    "resultatmargin": (0.03, 0.10, True),
    "totalrentabilitet": (0.03, 0.08, True),
    "egenkapitalrentabilitet": (0.05, 0.12, True),
    "likviditetsgrad1": (1.0, 2.0, True),
    "likviditetsgrad2": (0.7, 1.0, True),
    "egenkapitalandel": (0.15, 0.35, True),
    "gjeldsgrad": (5.0, 2.0, False),
    "rentedekningsgrad": (1.0, 3.0, True),
    # Banker og forsikring (finans.py)
    "kostnadsgrad": (0.60, 0.40, False),
    "tap_utlan": (0.005, 0.001, False),
    "innskuddsdekning": (0.5, 0.7, True),
    "combined_ratio": (1.0, 0.9, False),
}

NIVA_TEKST = {"sterk": "Sterk", "middels": "Middels", "svak": "Svak"}


@dataclass
class Vurdering:
    niva: str            # «sterk», «middels» eller «svak»
    regel: str           # tommelfingerregelen i ord


def _tall(x: float, prosent: bool) -> str:
    if prosent:
        return fmt.prosent(x, 1 if abs(x) < 0.01 else 0)
    return fmt.ganger(x, 1)


def vurder(kode: str, verdi: Optional[float]) -> Optional[Vurdering]:
    """Sterk / middels / svak etter tommelfingerregelen, eller None når det ikke finnes en fasit."""
    if verdi is None or kode not in GRENSER:
        return None
    svak, sterk, hoyere = GRENSER[kode]
    prosent = kode in ("driftsmargin", "resultatmargin", "totalrentabilitet", "egenkapitalrentabilitet",
                       "egenkapitalandel", "kostnadsgrad", "tap_utlan", "innskuddsdekning", "combined_ratio")
    if hoyere:
        niva = "sterk" if verdi >= sterk else "svak" if verdi < svak else "middels"
        regel = f"Tommelfingerregel: {_tall(sterk, prosent)} eller mer er sterkt, under {_tall(svak, prosent)} er svakt."
    else:
        niva = "sterk" if verdi <= sterk else "svak" if verdi > svak else "middels"
        regel = f"Tommelfingerregel: {_tall(sterk, prosent)} eller lavere er sterkt, over {_tall(svak, prosent)} er svakt."
    return Vurdering(niva, regel)


def _kr(andel: float) -> str:
    """0.082 -> «8 kr», 0.0049 -> «0,49 kr» (av hver 100 kr)."""
    x = abs(andel) * 100
    return f"{fmt.ganger(x, 0 if x >= 10 else 1)} kr"


def klartekst(kode: str, verdi: Optional[float], valuta: str = "NOK") -> Optional[str]:
    """Én setning som forklarer tallet med selskapets egne tall. None hvis verdien mangler."""
    if verdi is None:
        return None
    if kode == "driftsmargin":
        if verdi >= 0:
            return f"Av hver 100 kr i inntekter satt selskapet igjen med {_kr(verdi)} etter å ha betalt for driften."
        return f"Driften gikk med tap: for hver 100 kr i inntekter tapte selskapet {_kr(verdi)}."
    if kode == "resultatmargin":
        if verdi >= 0:
            return f"Av hver 100 kr i inntekter ble {_kr(verdi)} igjen før skatt, etter renter og andre finansposter."
        return f"Etter renter og finansposter gikk selskapet med tap: {_kr(verdi)} for hver 100 kr i inntekter."
    if kode == "totalrentabilitet":
        if verdi >= 0:
            return f"Hver 100 kr som er bundet i selskapets eiendeler, ga {_kr(verdi)} i avkastning i løpet av året."
        return f"Eiendelene ga negativ avkastning: et tap på {_kr(verdi)} for hver 100 kr."
    if kode == "egenkapitalrentabilitet":
        if verdi >= 0:
            return f"Eierne tjente {_kr(verdi)} etter skatt for hver 100 kr de har i selskapet. Til sammenligning gir sparekonto noen få prosent."
        return f"Eierne tapte {_kr(verdi)} for hver 100 kr de har i selskapet."
    if kode == "skattesats":
        return f"Av hver 100 kr i resultat før skatt gikk {_kr(verdi)} til skatt. Vanlig norsk selskapsskatt er 22 kr."
    if kode == "likviditetsgrad1":
        return (f"Selskapet har {fmt.ganger(verdi)} kr i penger, kundefordringer og varer for hver krone det må betale "
                f"innen ett år.")
    if kode == "likviditetsgrad2":
        return (f"Uten varelageret har selskapet {fmt.ganger(verdi)} kr i lett tilgjengelige midler for hver krone det "
                f"må betale innen ett år.")
    if kode == "arbeidskapital":
        if verdi >= 0:
            return (f"Selskapet har {fmt.belop(verdi, valuta)} mer i omløpsmidler enn det skylder innen ett år. "
                    "Det er en buffer.")
        return (f"Selskapet skylder {fmt.belop(abs(verdi), valuta)} mer innen ett år enn det har i omløpsmidler. "
                "Det må dekkes av inntekter eller nye lån.")
    if kode == "egenkapitalandel":
        if verdi >= 0:
            return f"Av hver 100 kr selskapet eier, er {_kr(verdi)} betalt av eierne. Resten er lånt."
        return "Gjelden er større enn alt selskapet eier, så eierne har i praksis ingenting igjen."
    if kode == "gjeldsgrad":
        return f"Selskapet har {fmt.ganger(verdi)} kr i gjeld for hver krone eierne har i selskapet."
    if kode == "kostnadsgrad":
        return f"Av hver 100 kr i inntekter gikk {_kr(verdi)} til å drive banken: lønn, IT, lokaler og annet."
    if kode == "rentemargin":
        return f"Banken tjente netto {_kr(verdi)} i renter for hver 100 kr den har i eiendeler."
    if kode == "tap_utlan":
        if verdi >= 0:
            return f"For hver 100 kr banken har lånt ut, regnet den med å tape {fmt.ganger(verdi * 100, 2)} kr i år."
        return "Banken fikk tilbake mer enn den fryktet å tape på utlån: tidligere avsetninger ble løst opp."
    if kode == "innskuddsdekning":
        return (f"For hver 100 kr banken har lånt ut, har kundene {_kr(verdi)} stående på konto i banken. "
                "Resten er lånt i markedet.")
    if kode == "combined_ratio":
        return (f"Av hver 100 kr i forsikringspremie gikk om lag {_kr(verdi)} til erstatninger og kostnader. "
                "Under 100 kr betyr overskudd på selve forsikringen.")
    if kode == "egenkapitalandel_finans":
        return f"Av hver 100 kr selskapet har i eiendeler, er {_kr(verdi)} eiernes egne penger. Resten er lånt eller innskudd."
    if kode == "rentedekningsgrad":
        return f"Overskuddet før renter var {fmt.ganger(verdi, 1)} ganger så stort som rentene selskapet måtte betale."
    return None
