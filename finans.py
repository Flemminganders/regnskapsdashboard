"""Banker og forsikringsselskaper.

Brønnøysundregistrenes regnskaps-API leverer ikke tall for banker og forsikringsselskaper
(«oppstillingsplan som ikke er støttet (BANK)»). Børsnoterte selskaper leverer derimot
årsrapporten i det maskinlesbare ESEF-formatet (XBRL), og den samles åpent på filings.xbrl.org.

Veien: org.nr -> LEI-kode (GLEIF) -> ESEF-rapportene (filings.xbrl.org) -> tallene, merket med
standard IFRS-navn. Tallene er for konsernet (fakta uten ekstra dimensjoner).

Henting og tolking er skilt, så tolkingen kan testes uten nettverk.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

import formatering as fmt
from beregninger import Nokkeltall, del_, minus

GLEIF_URL = "https://api.gleif.org/api/v1/lei-records"
FILINGS_URL = "https://filings.xbrl.org/api/filings"
FILINGS_BASE = "https://filings.xbrl.org"
TIMEOUT = 30

# Felt -> IFRS-begreper i prioritert rekkefølge (det første som finnes brukes).
KONSEPTER: Dict[str, List[str]] = {
    "renteinntekter": ["ifrs-full:InterestRevenueCalculatedUsingEffectiveInterestMethod", "ifrs-full:RevenueFromInterest"],
    "netto_renteinntekter": ["ifrs-full:InterestRevenueExpense"],
    "provisjonsinntekter": ["ifrs-full:FeeAndCommissionIncome"],
    "provisjonskostnader": ["ifrs-full:FeeAndCommissionExpense"],
    "sum_inntekter": ["ifrs-full:RevenueAndOperatingIncome", "ifrs-full:Revenue"],
    "driftskostnader": ["ifrs-full:OperatingExpense"],
    "tap_utlan": ["ifrs-full:ImpairmentLossImpairmentGainAndReversalOfImpairmentLossDeterminedInAccordanceWithIFRS9"],
    "forsikringsinntekter": ["ifrs-full:InsuranceRevenue"],
    "forsikringsresultat": ["ifrs-full:InsuranceServiceResult"],
    "resultat_for_skatt": ["ifrs-full:ProfitLossBeforeTax"],
    "skattekostnad": ["ifrs-full:IncomeTaxExpenseContinuingOperations", "ifrs-full:IncomeTaxExpense"],
    "aarsresultat": ["ifrs-full:ProfitLoss"],
    "sum_eiendeler": ["ifrs-full:Assets"],
    "utlan": ["ifrs-full:LoansAndAdvancesToCustomers"],
    "innskudd": ["ifrs-full:DepositsFromCustomers"],
    "egenkapital": ["ifrs-full:Equity"],
    "sum_gjeld": ["ifrs-full:Liabilities"],
}

ETIKETTER = {
    "renteinntekter": "Renteinntekter", "netto_renteinntekter": "Netto renteinntekter",
    "provisjonsinntekter": "Provisjonsinntekter", "provisjonskostnader": "Provisjonskostnader",
    "sum_inntekter": "Sum inntekter", "driftskostnader": "Driftskostnader", "tap_utlan": "Tap på utlån",
    "forsikringsinntekter": "Forsikringsinntekter", "forsikringsresultat": "Forsikringsresultat",
    "resultat_for_skatt": "Resultat før skatt", "skattekostnad": "Skattekostnad", "aarsresultat": "Årsresultat",
    "sum_eiendeler": "Sum eiendeler", "utlan": "Utlån til kunder", "innskudd": "Innskudd fra kunder",
    "egenkapital": "Egenkapital", "sum_gjeld": "Sum gjeld",
}


class IngenFinansdata(Exception):
    """Fant ingen ESEF-rapport for selskapet (f.eks. ikke børsnotert)."""


# ---------------------------------------------------------------------------
# Tolking (ren, uten nettverk)
# ---------------------------------------------------------------------------
def _aar_for_periode(periode: str) -> Optional[Tuple[int, bool]]:
    """«2025-01-01T00:00:00/2026-01-01T00:00:00» -> (2025, True) for et helt år;
    «2026-01-01T00:00:00» (balansedag) -> (2025, False). None for perioder som ikke er et år."""
    def dato(x: str) -> date:
        return date.fromisoformat(x[:10])
    try:
        if "/" in periode:
            fra, til = (dato(x) for x in periode.split("/"))
            if not 330 <= (til - fra).days <= 400:
                return None
            return (til - timedelta(days=1)).year, True
        return (dato(periode) - timedelta(days=1)).year, False
    except ValueError:
        return None


def tolk_esef(raa: Dict[str, Any]) -> Tuple[Dict[int, Dict[str, Optional[float]]], str]:
    """xBRL-JSON -> ({år: {felt: verdi}}, valuta). Bare fakta uten ekstra dimensjoner (= konsernet)."""
    funnet: Dict[int, Dict[str, float]] = {}
    valuta = "NOK"
    for fakta in raa.get("facts", {}).values():
        dim = fakta.get("dimensions", {})
        if set(dim) - {"concept", "entity", "period", "unit", "language"} or not dim.get("unit"):
            continue
        periode = _aar_for_periode(dim.get("period", ""))
        if periode is None:
            continue
        try:
            verdi = float(fakta["value"])
        except (TypeError, ValueError, KeyError):
            continue
        aar = periode[0]
        enhet = dim["unit"]
        if "/" in enhet:                       # per aksje o.l. – ikke beløp
            continue
        if enhet.startswith("iso4217:"):
            valuta = enhet.split(":")[1]
        funnet.setdefault(aar, {}).setdefault(dim["concept"], verdi)
    tall: Dict[int, Dict[str, Optional[float]]] = {}
    for aar, begreper in funnet.items():
        rad = {felt: next((begreper[k] for k in kandidater if k in begreper), None)
               for felt, kandidater in KONSEPTER.items()}
        if any(v is not None for v in rad.values()):
            tall[aar] = rad
    return tall, valuta


def slaa_sammen(rapporter: List[Tuple[Dict[int, Dict[str, Optional[float]]], str]]) -> Dict[int, Dict[str, Optional[float]]]:
    """Slår sammen flere rapporter (nyeste først). Nyeste rapport vinner (kan ha omarbeidede tall)."""
    ut: Dict[int, Dict[str, Optional[float]]] = {}
    for tall, _ in rapporter:
        for aar, rad in tall.items():
            if aar not in ut:
                ut[aar] = dict(rad)
            else:
                for k, v in rad.items():
                    if ut[aar].get(k) is None and v is not None:
                        ut[aar][k] = v
    return ut


def selskapstype(t: Dict[str, Optional[float]]) -> str:
    """«bank» (utlån og innskudd), «forsikring» (forsikringsinntekter) eller «finans»."""
    if t.get("utlan") is not None and t.get("innskudd") is not None:
        return "bank"
    if t.get("forsikringsinntekter") is not None:
        return "forsikring"
    return "finans"


def inntekter(t: Dict[str, Optional[float]]) -> Optional[float]:
    """Sum inntekter: oppgitt total, ellers forsikringsinntekter."""
    return t.get("sum_inntekter") if t.get("sum_inntekter") is not None else t.get("forsikringsinntekter")


# ---------------------------------------------------------------------------
# Nøkkeltall
# ---------------------------------------------------------------------------
def nokkeltall(t: Dict[str, Optional[float]]) -> List[Nokkeltall]:
    typ = selskapstype(t)
    ek = t.get("egenkapital")
    ut: List[Nokkeltall] = []
    ekr = Nokkeltall(
        kode="egenkapitalrentabilitet", navn="Egenkapitalrentabilitet", gruppe="Lønnsomhet", enhet="prosent",
        verdi=del_(t.get("aarsresultat"), ek), formel="Årsresultat ÷ Egenkapital",
        forklaring="Avkastningen eierne får på pengene de har i selskapet, etter skatt. Banker oppgir ofte et "
                   "litt annet tall i årsrapporten (snittet gjennom året, uten hybridkapital).",
        merknad="Regnet på egenkapital ved årets slutt.", inndata=["aarsresultat", "egenkapital"])
    if ek is not None and ek < 0:
        ekr.verdi, ekr.merknad = None, "Ikke meningsfull fordi egenkapitalen er negativ."
    ut.append(ekr)
    if typ == "bank":
        ut.append(Nokkeltall(
            kode="kostnadsgrad", navn="Kostnadsgrad", gruppe="Lønnsomhet", enhet="prosent",
            verdi=del_(t.get("driftskostnader"), t.get("sum_inntekter")),
            formel="Driftskostnader ÷ Sum inntekter",
            forklaring="Hvor mye av inntektene som går med til å drive banken (lønn, IT, lokaler). Lavere er mer "
                       "effektivt.", inndata=["driftskostnader", "sum_inntekter"]))
        ut.append(Nokkeltall(
            kode="rentemargin", navn="Netto renteinntekter i % av eiendeler", gruppe="Lønnsomhet", enhet="prosent",
            verdi=del_(t.get("netto_renteinntekter"), t.get("sum_eiendeler")),
            formel="Netto renteinntekter ÷ Sum eiendeler",
            forklaring="Hva banken tjener på forskjellen mellom renten den tar for utlån og renten den betaler for "
                       "innskudd og lån, sett mot hvor stor banken er.",
            merknad="Regnet på eiendeler ved årets slutt.", inndata=["netto_renteinntekter", "sum_eiendeler"]))
        ut.append(Nokkeltall(
            kode="tap_utlan", navn="Tap i % av utlån", gruppe="Risiko", enhet="prosent",
            verdi=del_(t.get("tap_utlan"), t.get("utlan")), formel="Tap på utlån ÷ Utlån til kunder",
            forklaring="Hvor mye av utlånene banken regner med å ikke få tilbake i år. Lavere er bedre. "
                       "Et negativt tall betyr at tidligere tap ble mindre enn fryktet.",
            inndata=["tap_utlan", "utlan"]))
        ut.append(Nokkeltall(
            kode="innskuddsdekning", navn="Innskuddsdekning", gruppe="Risiko", enhet="prosent",
            verdi=del_(t.get("innskudd"), t.get("utlan")), formel="Innskudd fra kunder ÷ Utlån til kunder",
            forklaring="Hvor mye av utlånene som er finansiert med kundenes innskudd. Resten lånes i markedet, "
                       "som er dyrere og mindre stabilt. Høyere er tryggere.",
            inndata=["innskudd", "utlan"]))
    if typ == "forsikring":
        fi, fr = t.get("forsikringsinntekter"), t.get("forsikringsresultat")
        ut.append(Nokkeltall(
            kode="combined_ratio", navn="Combined ratio (omtrentlig)", gruppe="Lønnsomhet", enhet="prosent",
            verdi=del_(minus(fi, fr), fi), formel="(Forsikringsinntekter − Forsikringsresultat) ÷ Forsikringsinntekter",
            forklaring="Hvor mye av premiene som går til erstatninger og kostnader. Under 100 % betyr at selskapet "
                       "tjener penger på selve forsikringen, før avkastningen på investeringene.",
            merknad="Omtrentlig: selskapets egen combined ratio kan være regnet litt annerledes (f.eks. etter "
                    "gjenforsikring).", inndata=["forsikringsinntekter", "forsikringsresultat"]))
    ut.append(Nokkeltall(
        kode="egenkapitalandel_finans", navn="Egenkapitalandel", gruppe="Soliditet", enhet="prosent",
        verdi=del_(ek, t.get("sum_eiendeler")), formel="Egenkapital ÷ Sum eiendeler",
        forklaring="Hvor stor del av eiendelene som er finansiert av eierne. Banker og forsikringsselskaper har "
                   "naturlig lav egenkapitalandel (ofte 5–10 % for banker). Myndighetenes krav måles med "
                   "kapitaldekning, som står i årsrapporten.",
        inndata=["egenkapital", "sum_eiendeler"]))
    return ut


# ---------------------------------------------------------------------------
# Sammendrag
# ---------------------------------------------------------------------------
def sammendrag(t: Dict[str, Optional[float]], f: Optional[Dict[str, Optional[float]]], aar: int,
               valuta: str) -> Tuple[Optional[str], List[Tuple[str, str]]]:
    """(overskrift, [(tekst, tone)]) for en bank eller et forsikringsselskap."""
    typ = selskapstype(t)
    punkter: List[Tuple[str, str]] = []
    inn, inn_for = inntekter(t), inntekter(f) if f else None
    if inn is not None:
        if inn_for and inn_for > 0:
            endr = (inn - inn_for) / inn_for
            ord_ = "økte" if endr > 0 else "falt"
            punkter.append((f"Inntektene {ord_} {fmt.prosent(abs(endr))} til {fmt.belop(inn, valuta)}.",
                            "ok" if endr > 0 else "adv"))
        else:
            punkter.append((f"Inntektene var {fmt.belop(inn, valuta)}.", "noytral"))
    ar, ar_for = t.get("aarsresultat"), (f or {}).get("aarsresultat")
    if ar is not None:
        if ar_for is not None and ar_for > 0 and ar >= 0:
            ord_ = "økte" if ar > ar_for else "falt"
            punkter.append((f"Årsresultatet {ord_} fra {fmt.belop(ar_for, valuta)} til {fmt.belop(ar, valuta)}.",
                            "ok" if ar > ar_for else "adv"))
        else:
            punkter.append((f"Årsresultatet ble {'et overskudd' if ar >= 0 else 'et underskudd'} på "
                            f"{fmt.belop(abs(ar), valuta)}.", "ok" if ar >= 0 else "feil"))
    nt = {n.kode: n for n in nokkeltall(t)}
    ekr = nt["egenkapitalrentabilitet"].verdi
    if ekr is not None:
        punkter.append((f"Eierne fikk {fmt.prosent(ekr)} avkastning på egenkapitalen.",
                        "ok" if ekr >= 0.12 else "adv" if ekr < 0.05 else "noytral"))
    if typ == "bank":
        kg, tap, dekn = nt["kostnadsgrad"].verdi, nt["tap_utlan"].verdi, nt["innskuddsdekning"].verdi
        if kg is not None:
            punkter.append((f"Av hver 100 kr i inntekter gikk {fmt.ganger(kg * 100, 0)} kr til å drive banken "
                            f"(kostnadsgrad {fmt.prosent(kg)}).", "ok" if kg <= 0.40 else "adv" if kg > 0.60 else "noytral"))
        if tap is not None:
            punkter.append((f"Tap på utlån var {fmt.prosent(tap, 2)} av utlånene.",
                            "ok" if tap <= 0.001 else "adv" if tap > 0.005 else "noytral"))
        if dekn is not None:
            punkter.append((f"Kundenes innskudd dekker {fmt.prosent(dekn, 0)} av utlånene. Resten er lånt i markedet.",
                            "ok" if dekn >= 0.7 else "adv" if dekn < 0.5 else "noytral"))
    if typ == "forsikring":
        cr = nt["combined_ratio"].verdi
        if cr is not None:
            punkter.append((f"Av hver 100 kr i premie gikk om lag {fmt.ganger(cr * 100, 0)} kr til erstatninger og "
                            f"kostnader (combined ratio {fmt.prosent(cr)}).",
                            "ok" if cr < 0.9 else "adv" if cr > 1 else "noytral"))
    navn = {"bank": "Banken", "forsikring": "Forsikringsselskapet"}.get(typ, "Selskapet")
    if ar is None:
        overskrift = None
    elif ar < 0:
        overskrift = f"{navn} gikk med underskudd i {aar}"
    elif ekr is not None and ekr >= 0.12:
        overskrift = f"{navn} tjente godt i {aar}"
    else:
        overskrift = f"{navn} gikk med overskudd i {aar}"
    return overskrift, punkter


# ---------------------------------------------------------------------------
# Henting
# ---------------------------------------------------------------------------
def hent_lei(orgnr: str) -> Optional[str]:
    """LEI-koden for et norsk org.nr (GLEIF lagrer det med mellomrom: «984 851 006»)."""
    registrert = f"{orgnr[:3]} {orgnr[3:6]} {orgnr[6:]}"
    for verdi in (registrert, orgnr):
        svar = requests.get(GLEIF_URL, params={"filter[entity.registeredAs]": verdi}, timeout=TIMEOUT)
        if svar.status_code == 200:
            data = svar.json().get("data") or []
            norske = [d for d in data if (d["attributes"]["entity"].get("jurisdiction") or
                                          d["attributes"]["entity"].get("legalJurisdiction") or "NO").startswith("NO")]
            if norske:
                return norske[0]["id"]
    return None


def hent_rapportlenker(lei: str, antall: int = 2) -> List[str]:
    """JSON-lenkene til de nyeste ESEF-rapportene (én per år, nyeste først)."""
    filt = f'[{{"name":"entity.identifier","op":"eq","val":"{lei}"}}]'
    svar = requests.get(FILINGS_URL, params={"filter": filt, "sort": "-period_end"},
                        headers={"Accept": "application/vnd.api+json"}, timeout=TIMEOUT)
    if svar.status_code != 200:
        return []
    lenker, sett = [], set()
    for f in svar.json().get("data", []):
        a = f.get("attributes", {})
        if a.get("json_url") and a.get("period_end") not in sett:
            sett.add(a.get("period_end"))
            lenker.append(FILINGS_BASE + a["json_url"])
    return lenker[:antall]


def hent(orgnr: str) -> Tuple[Dict[int, Dict[str, Optional[float]]], str]:
    """({år: tall}, valuta) for et børsnotert finansselskap. Kaster IngenFinansdata hvis ingenting finnes."""
    try:
        lei = hent_lei(orgnr)
        if not lei:
            raise IngenFinansdata("Fant ingen LEI-kode for selskapet.")
        rapporter = []
        for lenke in hent_rapportlenker(lei):
            svar = requests.get(lenke, timeout=TIMEOUT)
            if svar.status_code == 200:
                rapporter.append(tolk_esef(svar.json()))
    except (requests.RequestException, ValueError) as e:
        raise IngenFinansdata("Fikk ikke hentet årsrapporten.") from e
    tall = slaa_sammen(rapporter)
    if not tall:
        raise IngenFinansdata("Fant ingen maskinlesbar årsrapport (ESEF) for selskapet.")
    return tall, rapporter[0][1]
