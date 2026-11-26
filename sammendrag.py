"""Kort sammendrag i vanlig språk øverst i dashboardet.

Regelbasert (ingen KI): setningene bygges av de samme tallene og nøkkeltallene som
resten av appen viser. Teksten sier *hva* tallene viser, ikke *hvorfor*.
Rene funksjoner – ingen Streamlit – så de er enkle å teste.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import formatering as fmt
from beregninger import beregn_nokkeltall, resultatdrivere

# Grenser for ordene som brukes om egenkapitalandelen.
EK_SOLID = 0.35
EK_LAV = 0.15


@dataclass
class Punkt:
    tekst: str
    tone: str          # "ok", "adv", "feil" eller "noytral"


@dataclass
class Sammendrag:
    overskrift: Optional[str]
    punkter: List[Punkt]


def _pst(x: Optional[float]) -> str:
    return fmt.prosent(x)


_DRIVERTEKST = {
    "inntekter": ("høyere driftsinntekter", "lavere driftsinntekter"),
    "kostnader": ("høyere driftskostnader", "lavere driftskostnader"),
    "finans": ("et bedre finansresultat", "et svakere finansresultat"),
    "skatt": ("høyere skattekostnad", "lavere skattekostnad"),
}


def lag_sammendrag(r: Dict[str, Any], forrige: Optional[Dict[str, Any]], eierselskap_alene: bool = False,
                   balanse_avvik: bool = False, kurs: Optional[float] = None) -> Sammendrag:
    """``r`` og ``forrige`` er tolkede regnskap (fra ``brreg_api``). ``eierselskap_alene`` er True når
    morselskapet er et eierselskap og vises alene (da sier marginene lite)."""
    t, valuta, aar = r["tall"], r["valuta"], r["aar"]
    f = forrige["tall"] if forrige and forrige.get("valuta") == valuta else None
    nt = {n.kode: n for n in beregn_nokkeltall(t)}
    nt_for = {n.kode: n for n in beregn_nokkeltall(f)} if f else {}
    punkter: List[Punkt] = []

    if balanse_avvik:
        punkter.append(Punkt(f"Balansen i registerets tall for {aar} går ikke opp, så nøkkeltall som bygger på "
                             "balansen kan være misvisende.", "feil"))

    # --- Inntekter ---------------------------------------------------------
    di, di_for = t.get("sum_driftsinntekter"), (f or {}).get("sum_driftsinntekter")
    start = len(punkter)
    if di is not None:
        if di_for and di_for > 0 and di >= 0:
            endr = (di - di_for) / di_for
            if abs(endr) < 0.005:
                punkter.append(Punkt(f"Driftsinntektene var omtrent uendret på {fmt.belop(di, valuta)}.", "noytral"))
            else:
                ord_ = "økte" if endr > 0 else "falt"
                punkter.append(Punkt(f"Driftsinntektene {ord_} {_pst(abs(endr))} til {fmt.belop(di, valuta)}.",
                                     "ok" if endr > 0 else "adv"))
        else:
            punkter.append(Punkt(f"Driftsinntektene var {fmt.belop(di, valuta)}.", "noytral"))
        if kurs and valuta != "NOK" and len(punkter) > start:
            p = punkter[start]
            p.tekst = p.tekst[:-1] + f" (om lag {fmt.belop(di * kurs, 'kr')})."

    # --- Resultat og største driver -------------------------------------
    ar, ar_for = t.get("aarsresultat"), (f or {}).get("aarsresultat")
    if ar is not None:
        if ar_for is not None:
            if ar == ar_for:
                tekst, tone = f"Årsresultatet var uendret på {fmt.belop(ar, valuta)}", "noytral"
            elif ar >= 0 and ar_for >= 0:
                ord_ = "økte" if ar > ar_for else "falt"
                tekst = f"Årsresultatet {ord_} fra {fmt.belop(ar_for, valuta)} til {fmt.belop(ar, valuta)}"
                tone = "ok" if ar > ar_for else "adv"
            elif ar < 0 <= ar_for:
                tekst = (f"Selskapet gikk fra overskudd på {fmt.belop(ar_for, valuta)} til underskudd på "
                         f"{fmt.belop(abs(ar), valuta)}")
                tone = "feil"
            elif ar >= 0 > ar_for:
                tekst = (f"Selskapet snudde underskuddet på {fmt.belop(abs(ar_for), valuta)} til et overskudd på "
                         f"{fmt.belop(ar, valuta)}")
                tone = "ok"
            else:
                ord_ = "mindre" if ar > ar_for else "større"
                tekst = (f"Underskuddet ble {ord_}: fra {fmt.belop(abs(ar_for), valuta)} til "
                         f"{fmt.belop(abs(ar), valuta)}")
                tone = "adv" if ar > ar_for else "feil"
            analyse = resultatdrivere(t, f) if f else None
            stor = next((d for d in (analyse.topp(3) if analyse else []) if d.kode in _DRIVERTEKST), None)
            if stor is not None and ar != ar_for and abs(stor.effekt) >= 0.25 * abs(ar - ar_for):
                beskr = _DRIVERTEKST[stor.kode][0 if stor.endring >= 0 else 1]
                retning = "løftet" if stor.effekt > 0 else "trakk ned"
                tekst += f". Størst utslag ga {beskr}, som {retning} resultatet med {fmt.belop(abs(stor.effekt), valuta)}"
            punkter.append(Punkt(tekst + ".", tone))
        else:
            if ar >= 0:
                punkter.append(Punkt(f"Årsresultatet ble et overskudd på {fmt.belop(ar, valuta)}.", "ok"))
            else:
                punkter.append(Punkt(f"Årsresultatet ble et underskudd på {fmt.belop(abs(ar), valuta)}.", "feil"))

    # --- Margin --------------------------------------------------------------
    if eierselskap_alene:
        punkter.append(Punkt("Morselskapet er et eierselskap, så marginene sier lite om driften. Se konsernet "
                             "for det.", "noytral"))
    else:
        dm = nt["driftsmargin"].verdi
        dm_for = nt_for["driftsmargin"].verdi if "driftsmargin" in nt_for else None
        if dm is not None:
            tillegg = f" ({_pst(dm_for)} i {forrige['aar']})" if dm_for is not None and forrige else ""
            punkter.append(Punkt(f"Driftsmarginen var {_pst(dm)}{tillegg}.", "noytral" if dm >= 0 else "adv"))

    # --- Skatt (bare når den skiller seg tydelig ut) -------------------------
    ss = nt["skattesats"].verdi
    if ss is not None and (ss > 0.35 or ss < 0.12):
        hva = "langt over" if ss > 0.35 else "langt under"
        punkter.append(Punkt(f"Effektiv skattesats var {_pst(ss)}, {hva} den ordinære selskapsskatten på 22 %.",
                             "noytral"))

    # --- Soliditet -------------------------------------------------------------
    ek, eka = t.get("egenkapital"), nt["egenkapitalandel"].verdi
    if ek is not None and ek < 0:
        punkter.append(Punkt("Egenkapitalen er negativ: gjelden er større enn eiendelene.", "feil"))
    elif eka is not None:
        if eka >= EK_SOLID:
            punkter.append(Punkt(f"Egenkapitalandelen er {_pst(eka)}, som er solid.", "ok"))
        elif eka >= EK_LAV:
            punkter.append(Punkt(f"Egenkapitalandelen er {_pst(eka)}, et middels nivå.", "noytral"))
        else:
            punkter.append(Punkt(f"Egenkapitalandelen er lav, {_pst(eka)}.", "adv"))

    # --- Likviditet ------------------------------------------------------------
    lg1 = nt["likviditetsgrad1"].verdi
    if lg1 is not None:
        tall = fmt.ganger(lg1)
        if lg1 < 1:
            punkter.append(Punkt(f"Den kortsiktige gjelden er større enn omløpsmidlene (likviditetsgrad 1: {tall}).",
                                 "adv"))
        elif lg1 >= 2:
            punkter.append(Punkt(f"Omløpsmidlene dekker den kortsiktige gjelden godt (likviditetsgrad 1: {tall}).",
                                 "ok"))
        else:
            punkter.append(Punkt(f"Omløpsmidlene dekker den kortsiktige gjelden (likviditetsgrad 1: {tall}).",
                                 "noytral"))

    return Sammendrag(_overskrift(ar, ek, eka, aar, lg1), punkter)


def _overskrift(ar: Optional[float], ek: Optional[float], eka: Optional[float], aar: int,
                lg1: Optional[float] = None) -> Optional[str]:
    """Én linje som oppsummerer: lønnsomt eller ikke, solid eller ikke, og de viktigste svakhetene."""
    if ar is None:
        return None
    negativ_ek = ek is not None and ek < 0
    solid = None if (eka is None or negativ_ek) else eka >= EK_SOLID
    if ar >= 0:
        if solid:
            hoved = "Lønnsomt og solid"
        elif negativ_ek:
            hoved = "Overskudd, men negativ egenkapital"
        elif solid is False:
            hoved = "Overskudd, men " + ("lav" if eka < EK_LAV else "moderat") + " egenkapital"
        else:
            hoved = "Overskudd"
    else:
        if solid:
            hoved = "Underskudd, men solid egenkapital"
        elif negativ_ek:
            hoved = "Underskudd og negativ egenkapital"
        else:
            hoved = "Underskudd"
    svakheter = []
    if lg1 is not None and lg1 < 1:
        svakheter.append("stram likviditet")
    if svakheter:
        bindeord = " og " if ("men" in hoved or hoved.startswith("Underskudd og")) else ", men "
        hoved += bindeord + " og ".join(svakheter)
    return f"{hoved} i {aar}"
