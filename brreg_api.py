"""Henting av data fra Brønnøysundregistrene.

Denne fila har ansvar for tre ting:
1. Sjekke at et organisasjonsnummer er gyldig (format + kontrollsiffer).
2. Hente selskapsinfo (Enhetsregisteret) og årsregnskap (Regnskapsregisteret).
3. Oversette API-svaret til en flat, forutsigbar struktur der manglende
   felter er ``None`` – aldri 0.

Fila bruker ingen Streamlit-kode, slik at den kan testes og gjenbrukes alene.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

import requests

ENHET_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}"
ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller"
REGNSKAP_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}"
# Kopi av innsendt årsregnskap som PDF. Finnes langt bakover i tid (ofte fra 2011),
# mens tallene i JSON-API-et bare dekker de tre siste årene.
PDF_AAR_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{orgnr}/aar"
PDF_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{orgnr}/{aar}"
TIMEOUT_SEKUNDER = 15

# Vekttall for modulus 11-kontroll av norske organisasjonsnumre.
_VEKTER = (3, 2, 7, 6, 5, 4, 3, 2)


# ---------------------------------------------------------------------------
# Egne feiltyper – appen viser en tydelig melding for hver av dem.
# ---------------------------------------------------------------------------
class BrregFeil(Exception):
    """Felles basisklasse. ``str(feil)`` er en melding som kan vises til brukeren."""


class UgyldigOrgnr(BrregFeil):
    pass


class FantIkkeSelskap(BrregFeil):
    pass


class IngenRegnskap(BrregFeil):
    pass


class TjenesteFeil(BrregFeil):
    pass


# ---------------------------------------------------------------------------
# Validering
# ---------------------------------------------------------------------------
def rens_orgnr(tekst: str) -> str:
    """Fjerner mellomrom, punktum og bindestrek: '923 609 016' -> '923609016'."""
    return re.sub(r"[\s.\-]", "", tekst or "")


def valider_orgnr(tekst: str) -> str:
    """Returnerer et renset org.nr eller kaster ``UgyldigOrgnr`` med forklaring."""
    orgnr = rens_orgnr(tekst)
    if not orgnr:
        raise UgyldigOrgnr("Skriv inn et organisasjonsnummer.")
    if not orgnr.isdigit():
        raise UgyldigOrgnr(f"«{tekst}» inneholder tegn som ikke er siffer. Et org.nr består av 9 siffer.")
    if len(orgnr) != 9:
        raise UgyldigOrgnr(f"Et org.nr har 9 siffer – du skrev {len(orgnr)}.")

    sum_ = sum(int(s) * v for s, v in zip(orgnr[:8], _VEKTER))
    rest = sum_ % 11
    kontroll = 0 if rest == 0 else 11 - rest
    if kontroll == 10 or kontroll != int(orgnr[8]):
        raise UgyldigOrgnr(
            f"{orgnr} er ikke et gyldig org.nr – kontrollsifferet (siste siffer) stemmer ikke. "
            "Sjekk at du har skrevet riktig."
        )
    return orgnr


# ---------------------------------------------------------------------------
# Henting
# ---------------------------------------------------------------------------
def _get_json(url: str) -> requests.Response:
    try:
        return requests.get(url, headers={"Accept": "application/json"}, timeout=TIMEOUT_SEKUNDER)
    except requests.RequestException as e:
        raise TjenesteFeil(
            "Fikk ikke kontakt med Brønnøysundregistrene. Sjekk nettforbindelsen og prøv igjen."
        ) from e


def _feilmelding(svar: requests.Response) -> str:
    """Henter «message» fra et feilsvar, hvis det finnes."""
    try:
        data = svar.json()
    except ValueError:
        return ""
    return str(data.get("message", "")) if isinstance(data, dict) else ""


def hent_enhet(orgnr: str) -> Dict[str, Any]:
    """Henter selskapsinfo fra Enhetsregisteret."""
    svar = _get_json(ENHET_URL.format(orgnr=orgnr))
    if svar.status_code == 404:
        raise FantIkkeSelskap(f"Fant ingen enhet med org.nr {orgnr} i Enhetsregisteret.")
    if svar.status_code == 410:
        raise FantIkkeSelskap(f"Enheten med org.nr {orgnr} er slettet fra Enhetsregisteret.")
    if svar.status_code == 400:
        raise UgyldigOrgnr(f"Enhetsregisteret godtok ikke {orgnr} som org.nr.")
    if svar.status_code != 200:
        raise TjenesteFeil(f"Enhetsregisteret svarte med feilkode {svar.status_code}. Prøv igjen senere.")
    return svar.json()


def hent_regnskap(orgnr: str) -> List[Dict[str, Any]]:
    """Henter alle årsregnskap API-et har for org.nr (rå liste)."""
    svar = _get_json(REGNSKAP_URL.format(orgnr=orgnr))
    if svar.status_code == 404:
        raise IngenRegnskap(
            f"Regnskapsregisteret har ikke noe årsregnskap for {orgnr}. "
            "Det er vanlig for enkeltpersonforetak, nystartede selskaper og foreninger, "
            "som ikke har plikt til å sende inn årsregnskap."
        )
    if svar.status_code != 200:
        melding = _feilmelding(svar)
        if "oppstillingsplan" in melding.lower():
            # Skjer f.eks. for banker og forsikringsselskap (egne regnskapsoppstillinger).
            plan = melding.rsplit("(", 1)[-1].rstrip(")") if "(" in melding else "ukjent"
            raise IngenRegnskap(
                f"Selskapet har levert årsregnskap, men Regnskapsregisterets åpne API støtter ikke "
                f"denne typen regnskapsoppstilling ({plan}). Det gjelder blant annet banker og "
                "forsikringsselskap. Regnskapet kan ses på www.brreg.no."
            )
        raise TjenesteFeil(f"Regnskapsregisteret svarte med feilkode {svar.status_code}. Prøv igjen senere.")
    data = svar.json()
    if not isinstance(data, list) or not data:
        raise IngenRegnskap(f"Regnskapsregisteret returnerte ingen årsregnskap for {orgnr}.")
    return data


def hent_pdf_aar(orgnr: str) -> List[int]:
    """År det finnes kopi av årsregnskapet (PDF) for, nyeste først. Tom liste ved feil –
    dette er en tilleggsfunksjon, så feil her skal ikke stoppe dashboardet."""
    try:
        svar = _get_json(PDF_AAR_URL.format(orgnr=orgnr))
        data = svar.json() if svar.status_code == 200 else []
    except (BrregFeil, ValueError):
        return []
    return sorted({int(a) for a in data if str(a).isdigit()}, reverse=True)


def pdf_lenke(orgnr: str, aar: int) -> str:
    return PDF_URL.format(orgnr=orgnr, aar=aar)


def hent_roller(orgnr: str) -> Dict[str, Any]:
    """Roller (daglig leder, styre, revisor …). Tom dict ved feil (tilleggsfunksjon)."""
    try:
        svar = _get_json(ROLLER_URL.format(orgnr=orgnr))
        return svar.json() if svar.status_code == 200 else {}
    except (BrregFeil, ValueError):
        return {}


# ---------------------------------------------------------------------------
# Tolking av API-svaret
# ---------------------------------------------------------------------------
def _finn(d: Any, *sti: str) -> Any:
    """Går nedover i nøstede dicts. Returnerer None hvis noe på veien mangler."""
    for nokkel in sti:
        if not isinstance(d, dict) or nokkel not in d:
            return None
        d = d[nokkel]
    return d


def _tall(d: Any, *sti: str) -> Optional[float]:
    verdi = _finn(d, *sti)
    if isinstance(verdi, bool) or not isinstance(verdi, (int, float)):
        return None
    return float(verdi)


# Kartet fra våre feltnavn til stien i API-svaret.
# NB: «sumInnskuttEgenkaptial» er feilstavet i API-et og må skrives slik.
FELT_STIER = {
    # Resultatregnskap
    "salgsinntekter": ("resultatregnskapResultat", "driftsresultat", "driftsinntekter", "salgsinntekter"),
    "sum_driftsinntekter": ("resultatregnskapResultat", "driftsresultat", "driftsinntekter", "sumDriftsinntekter"),
    "sum_driftskostnad": ("resultatregnskapResultat", "driftsresultat", "driftskostnad", "sumDriftskostnad"),
    "driftsresultat": ("resultatregnskapResultat", "driftsresultat", "driftsresultat"),
    "finansinntekter": ("resultatregnskapResultat", "finansresultat", "finansinntekt", "sumFinansinntekter"),
    "finanskostnader": ("resultatregnskapResultat", "finansresultat", "finanskostnad", "sumFinanskostnad"),
    # Rentekostnader oppgis bare av noen selskaper (underposter av finanskostnad).
    "annen_rentekostnad": ("resultatregnskapResultat", "finansresultat", "finanskostnad", "annenRentekostnad"),
    "rentekostnad_konsern": ("resultatregnskapResultat", "finansresultat", "finanskostnad",
                             "rentekostnadSammeKonsern"),
    "netto_finans": ("resultatregnskapResultat", "finansresultat", "nettoFinans"),
    "resultat_for_skatt": ("resultatregnskapResultat", "ordinaertResultatFoerSkattekostnad"),
    "skattekostnad": ("resultatregnskapResultat", "ordinaertResultatSkattekostnad"),
    "aarsresultat": ("resultatregnskapResultat", "aarsresultat"),
    # Eiendeler
    "anleggsmidler": ("eiendeler", "anleggsmidler", "sumAnleggsmidler"),
    "omlopsmidler": ("eiendeler", "omloepsmidler", "sumOmloepsmidler"),
    "varer": ("eiendeler", "sumVarer"),
    "fordringer": ("eiendeler", "sumFordringer"),
    "investeringer": ("eiendeler", "sumInvesteringer"),
    "bankinnskudd": ("eiendeler", "sumBankinnskuddOgKontanter"),
    "sum_eiendeler": ("eiendeler", "sumEiendeler"),
    # Egenkapital og gjeld
    "egenkapital": ("egenkapitalGjeld", "egenkapital", "sumEgenkapital"),
    "innskutt_egenkapital": ("egenkapitalGjeld", "egenkapital", "innskuttEgenkapital", "sumInnskuttEgenkaptial"),
    "opptjent_egenkapital": ("egenkapitalGjeld", "egenkapital", "opptjentEgenkapital", "sumOpptjentEgenkapital"),
    "langsiktig_gjeld": ("egenkapitalGjeld", "gjeldOversikt", "langsiktigGjeld", "sumLangsiktigGjeld"),
    "kortsiktig_gjeld": ("egenkapitalGjeld", "gjeldOversikt", "kortsiktigGjeld", "sumKortsiktigGjeld"),
    "sum_gjeld": ("egenkapitalGjeld", "gjeldOversikt", "sumGjeld"),
    "sum_egenkapital_gjeld": ("egenkapitalGjeld", "sumEgenkapitalGjeld"),
}


def tolk_regnskap(raa: Dict[str, Any]) -> Dict[str, Any]:
    """Gjør ett årsregnskap fra API-et om til en flat dict.

    Alle tallfelt i ``FELT_STIER`` finnes alltid som nøkkel; verdien er ``None``
    når API-et ikke oppgir tallet.
    """
    tall = {navn: _tall(raa, *sti) for navn, sti in FELT_STIER.items()}
    til_dato = _finn(raa, "regnskapsperiode", "tilDato")
    return {
        "aar": int(til_dato[:4]) if isinstance(til_dato, str) and len(til_dato) >= 4 else None,
        "fra_dato": _finn(raa, "regnskapsperiode", "fraDato"),
        "til_dato": til_dato,
        "regnskapstype": raa.get("regnskapstype"),
        "valuta": raa.get("valuta") or "NOK",
        # NB: «regnkapsprinsipper» er feilstavet i API-et.
        "regnskapsregler": _finn(raa, "regnkapsprinsipper", "regnskapsregler"),
        "smaa_foretak": _finn(raa, "regnkapsprinsipper", "smaaForetak"),
        "ikke_revidert": _finn(raa, "revisjon", "ikkeRevidertAarsregnskap"),
        "tall": tall,
    }


def tilgjengelige_typer(regnskaper: List[Dict[str, Any]]) -> List[str]:
    """Hvilke regnskapstyper (SELSKAP/KONSERN) som finnes. SELSKAP først."""
    typer = {r.get("regnskapstype") for r in regnskaper if r.get("regnskapstype")}
    return sorted(typer, key=lambda t: (t != "SELSKAP", t))


def velg_regnskap(regnskaper: List[Dict[str, Any]], regnskapstype: str) -> List[Dict[str, Any]]:
    """Tolkede regnskap av valgt type, nyeste år først."""
    valgte = [tolk_regnskap(r) for r in regnskaper if r.get("regnskapstype") == regnskapstype]
    return sorted(valgte, key=lambda r: r["til_dato"] or "", reverse=True)


def tolk_enhet(raa: Dict[str, Any]) -> Dict[str, Any]:
    """Plukker ut feltene selskapskortet trenger. Manglende felt blir None."""
    adr = raa.get("forretningsadresse") or raa.get("postadresse") or {}
    gate = ", ".join(adr.get("adresse") or [])
    sted = " ".join(x for x in (adr.get("postnummer"), adr.get("poststed")) if x)
    adresse = ", ".join(x for x in (gate, sted) if x) or None

    varsler = []
    if raa.get("konkurs"):
        varsler.append("Selskapet er registrert konkurs.")
    if raa.get("underAvvikling"):
        varsler.append("Selskapet er under avvikling.")
    if raa.get("underTvangsavviklingEllerTvangsopplosning"):
        varsler.append("Selskapet er under tvangsavvikling eller tvangsoppløsning.")

    return {
        "navn": raa.get("navn"),
        "orgnr": raa.get("organisasjonsnummer"),
        "organisasjonsform": _finn(raa, "organisasjonsform", "beskrivelse"),
        "naering_kode": _finn(raa, "naeringskode1", "kode"),
        "naering": _finn(raa, "naeringskode1", "beskrivelse"),
        "adresse": adresse,
        "kommune": adr.get("kommune"),
        "ansatte": raa.get("antallAnsatte") if raa.get("harRegistrertAntallAnsatte", True) else None,
        "stiftet": raa.get("stiftelsesdato"),
        "hjemmeside": raa.get("hjemmeside"),
        "aksjekapital": _tall(raa, "kapital", "belop"),
        "aksjekapital_valuta": _finn(raa, "kapital", "valuta"),
        "siste_aarsregnskap": raa.get("sisteInnsendteAarsregnskap"),
        "i_konsern": raa.get("erIKonsern"),
        "varsler": varsler,
    }


# ---------------------------------------------------------------------------
# Hendelser fra registrene
# ---------------------------------------------------------------------------
def _dato(tekst: Any) -> Optional[date]:
    if not isinstance(tekst, str) or len(tekst) < 10:
        return None
    try:
        return date.fromisoformat(tekst[:10])
    except ValueError:
        return None


def _personnavn(rolle: Dict[str, Any]) -> Optional[str]:
    navn = _finn(rolle, "person", "navn")
    if isinstance(navn, dict):
        deler = [navn.get("fornavn"), navn.get("mellomnavn"), navn.get("etternavn")]
        return " ".join(d for d in deler if d) or None
    enhet_navn = _finn(rolle, "enhet", "navn")
    if isinstance(enhet_navn, list):
        return " ".join(enhet_navn) or None
    return None


_ROLLEGRUPPER = {
    "DAGL": ("Daglig leder", "Daglig leder"),
    "STYR": ("Styret", "Styreleder"),
    "REVI": ("Revisor", "Revisor"),
}


def tolk_hendelser(enhet_raa: Dict[str, Any], roller_raa: Dict[str, Any],
                   i_dag: Optional[date] = None, maaneder: int = 24) -> List[Dict[str, Any]]:
    """Daterte hendelser fra Enhetsregisteret, nyeste først.

    Kilder: når rollegrupper (daglig leder, styre, revisor) sist ble endret,
    når kapitalen sist ble endret, nye vedtekter og navneendringer. Bare
    hendelser innenfor de siste ``maaneder`` månedene tas med. Ingen fødselsdatoer.
    """
    i_dag = i_dag or date.today()
    m = i_dag.year * 12 + (i_dag.month - 1) - maaneder        # måned-nummer for grensen
    grense = date(m // 12, m % 12 + 1, 1)
    hendelser: List[Dict[str, Any]] = []

    for gruppe in (roller_raa or {}).get("rollegrupper", []) or []:
        kode = _finn(gruppe, "type", "kode")
        if kode not in _ROLLEGRUPPER:
            continue
        dato = _dato(gruppe.get("sistEndret"))
        tittel, rollenavn = _ROLLEGRUPPER[kode]
        aktive = [r for r in gruppe.get("roller", []) or []
                  if not r.get("fratraadt") and not r.get("avregistrert")]
        hoved = next((r for r in aktive if _finn(r, "type", "kode") in ("LEDE", "DAGL", "REVI")), None) \
            or (aktive[0] if aktive else None)
        navn = _personnavn(hoved) if hoved else None
        if kode == "STYR":
            detalj = f"{len(aktive)} medlemmer" + (f" · styreleder {navn}" if navn else "")
        else:
            detalj = f"{rollenavn}: {navn}" if navn else None
        hendelser.append({"dato": dato, "tittel": f"{tittel} endret", "detalj": detalj, "kilde": "Roller"})

    kap_dato = _dato(_finn(enhet_raa, "kapital", "innfortDato"))
    if kap_dato:
        belop = _tall(enhet_raa, "kapital", "belop")
        valuta = _finn(enhet_raa, "kapital", "valuta") or "NOK"
        detalj = None
        if belop is not None:
            detalj = f"Aksjekapital {belop:,.0f} {valuta}".replace(",", " ")
        hendelser.append({"dato": kap_dato, "tittel": "Kapitalendring registrert", "detalj": detalj,
                          "kilde": "Enhetsregisteret"})

    vedt = _dato(enhet_raa.get("vedtektsdato"))
    if vedt:
        hendelser.append({"dato": vedt, "tittel": "Nye vedtekter", "detalj": None, "kilde": "Enhetsregisteret"})

    for h in enhet_raa.get("historiskeNavn", []) or []:
        til = _dato(h.get("tilDato"))
        if til:
            hendelser.append({"dato": til, "tittel": "Navneendring",
                              "detalj": f"Tidligere navn: {h.get('navn')}" if h.get("navn") else None,
                              "kilde": "Enhetsregisteret"})

    aktuelle = [h for h in hendelser if h["dato"] and grense <= h["dato"] <= i_dag]
    return sorted(aktuelle, key=lambda h: h["dato"], reverse=True)
