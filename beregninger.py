"""Beregninger: nøkkeltall, balansekontroll og veien fra inntekter til årsresultat.

Alle funksjoner her er «rene»: de tar inn en dict med tall (fra
``brreg_api.tolk_regnskap(...)["tall"]``) og returnerer resultater. Ingen
nettverk, ingen Streamlit. Derfor er de enkle å teste.

Prinsipp: et tall som mangler er ``None``. Et nøkkeltall som bygger på et
manglende tall blir også ``None`` – det blir aldri stille regnet som 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

Tall = Dict[str, Optional[float]]


# ---------------------------------------------------------------------------
# Hjelpefunksjoner
# ---------------------------------------------------------------------------
def del_(teller: Optional[float], nevner: Optional[float]) -> Optional[float]:
    """Trygg divisjon: None hvis et tall mangler eller nevneren er 0."""
    if teller is None or nevner is None or nevner == 0:
        return None
    return teller / nevner


def pluss(*ledd: Optional[float]) -> Optional[float]:
    """Summerer – men bare hvis ingen ledd mangler."""
    if any(x is None for x in ledd):
        return None
    return float(sum(ledd))  # type: ignore[arg-type]


def minus(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


# ---------------------------------------------------------------------------
# Nøkkeltall
# ---------------------------------------------------------------------------
@dataclass
class Nokkeltall:
    kode: str            # kort id, brukes også i Excel
    navn: str
    verdi: Optional[float]
    enhet: str           # "prosent", "ganger" eller "belop"
    formel: str          # formelen i ord
    forklaring: str      # hva tallet forteller
    gruppe: str          # "Lønnsomhet", "Likviditet" eller "Soliditet"
    merknad: Optional[str] = None   # f.eks. «ikke meningsfull ved negativ egenkapital»
    inndata: List[str] = field(default_factory=list)  # hvilke felt formelen bruker


def rentekostnader(t: Tall) -> Optional[float]:
    """Sum av oppgitte rentekostnader (eksterne + til konsernselskaper).

    None hvis ingen av dem er oppgitt – mange selskaper viser bare sum finanskostnader.
    """
    deler = [t.get("annen_rentekostnad"), t.get("rentekostnad_konsern")]
    if all(d is None for d in deler):
        return None
    return float(sum(d for d in deler if d is not None))


def finans_er_netto(t: Tall) -> bool:
    """True når finanskostnader mangler og «finansinntekter» er lik netto finans –
    da har selskapet trolig rapportert finansposter netto på én linje."""
    fi, netto = t.get("finansinntekter"), t.get("netto_finans")
    if t.get("finanskostnader") is not None or fi is None or netto is None:
        return False
    return abs(fi - netto) <= max(ABSOLUTT_TOLERANSE, RELATIV_TOLERANSE * abs(fi))


def er_eierselskap(t: Tall) -> bool:
    """True når finansinntektene er større enn driftsinntektene – typisk for et
    morselskap der driften ligger i datterselskapene (inntekter = utbytte, konsernbidrag, renter)."""
    fi, di = t.get("finansinntekter"), t.get("sum_driftsinntekter")
    if fi is None:
        return False
    return di is None or fi > di


def beregn_nokkeltall(t: Tall) -> List[Nokkeltall]:
    ek = t.get("egenkapital")
    driftsinntekter = t.get("sum_driftsinntekter")
    totalkapital = t.get("sum_eiendeler")

    resultat: List[Nokkeltall] = []

    # --- Lønnsomhet -------------------------------------------------------
    resultat.append(Nokkeltall(
        kode="driftsmargin", navn="Driftsmargin", gruppe="Lønnsomhet", enhet="prosent",
        verdi=del_(t.get("driftsresultat"), driftsinntekter),
        formel="Driftsresultat ÷ Sum driftsinntekter",
        forklaring="Hvor mye av hver krone i inntekt som blir igjen etter driftskostnadene, "
                   "før finansposter og skatt.",
        inndata=["driftsresultat", "sum_driftsinntekter"],
    ))
    resultat.append(Nokkeltall(
        kode="resultatmargin", navn="Resultatmargin", gruppe="Lønnsomhet", enhet="prosent",
        verdi=del_(t.get("resultat_for_skatt"), driftsinntekter),
        formel="Ordinært resultat før skatt ÷ Sum driftsinntekter",
        forklaring="Resultat før skatt som andel av inntektene: som driftsmargin, men etter at "
                   "finansinntekter og -kostnader er tatt med. Regnes før skatt, så ulike skattesatser "
                   "ikke påvirker sammenligningen mellom år og selskaper.",
        inndata=["resultat_for_skatt", "sum_driftsinntekter"],
    ))
    forklaring_tr = ("Avkastning på all kapital i selskapet, uansett om den er finansiert med "
                     "egenkapital eller gjeld. Brukes ofte til å sammenligne med lånerenten.")
    renter = rentekostnader(t)
    if renter is not None:
        # Lærebokformelen – brukes når selskapet har oppgitt rentekostnader.
        resultat.append(Nokkeltall(
            kode="totalrentabilitet", navn="Totalrentabilitet", gruppe="Lønnsomhet", enhet="prosent",
            verdi=del_(pluss(t.get("resultat_for_skatt"), renter), totalkapital),
            formel="(Resultat før skatt + Rentekostnader) ÷ Sum eiendeler",
            forklaring=forklaring_tr,
            merknad="Regnet på eiendeler ved årets slutt, ikke snittet gjennom året.",
            inndata=["resultat_for_skatt", "annen_rentekostnad", "rentekostnad_konsern", "sum_eiendeler"],
        ))
    else:
        merknad_tr = ("Selskapet har ikke oppgitt rentekostnader, så tilnærmingen driftsresultat + "
                      "finansinntekter brukes. Regnet på eiendeler ved årets slutt.")
        if finans_er_netto(t):
            merknad_tr += (" Finanskostnader er ikke oppgitt, og finansinntektene ser ut til å være "
                           "et nettotall (inntekter minus kostnader).")
        resultat.append(Nokkeltall(
            kode="totalrentabilitet", navn="Totalrentabilitet", gruppe="Lønnsomhet", enhet="prosent",
            verdi=del_(pluss(t.get("driftsresultat"), t.get("finansinntekter")), totalkapital),
            formel="(Driftsresultat + Finansinntekter) ÷ Sum eiendeler",
            forklaring=forklaring_tr,
            merknad=merknad_tr,
            inndata=["driftsresultat", "finansinntekter", "sum_eiendeler"],
        ))
    ekr = Nokkeltall(
        kode="egenkapitalrentabilitet", navn="Egenkapitalrentabilitet", gruppe="Lønnsomhet",
        enhet="prosent",
        verdi=del_(t.get("aarsresultat"), ek),
        formel="Årsresultat ÷ Sum egenkapital",
        forklaring="Avkastningen eierne får på pengene de har i selskapet (etter skatt).",
        merknad="Regnet på egenkapital ved årets slutt, ikke snittet gjennom året.",
        inndata=["aarsresultat", "egenkapital"],
    )
    if ek is not None and ek < 0:
        ekr.verdi = None
        ekr.merknad = "Ikke meningsfull fordi egenkapitalen er negativ."
    resultat.append(ekr)

    # --- Likviditet -------------------------------------------------------
    resultat.append(Nokkeltall(
        kode="likviditetsgrad1", navn="Likviditetsgrad 1", gruppe="Likviditet", enhet="ganger",
        verdi=del_(t.get("omlopsmidler"), t.get("kortsiktig_gjeld")),
        formel="Omløpsmidler ÷ Kortsiktig gjeld",
        forklaring="Evnen til å betale regninger som forfaller innen ett år. "
                   "Over 2 regnes tradisjonelt som godt, under 1 som svakt.",
        inndata=["omlopsmidler", "kortsiktig_gjeld"],
    ))
    resultat.append(Nokkeltall(
        kode="arbeidskapital", navn="Arbeidskapital", gruppe="Likviditet", enhet="belop",
        verdi=minus(t.get("omlopsmidler"), t.get("kortsiktig_gjeld")),
        formel="Omløpsmidler − Kortsiktig gjeld",
        forklaring="Den delen av omløpsmidlene som er finansiert med langsiktig kapital. "
                   "Positiv arbeidskapital gir en buffer.",
        inndata=["omlopsmidler", "kortsiktig_gjeld"],
    ))

    # --- Soliditet --------------------------------------------------------
    resultat.append(Nokkeltall(
        kode="egenkapitalandel", navn="Egenkapitalandel", gruppe="Soliditet", enhet="prosent",
        verdi=del_(ek, t.get("sum_egenkapital_gjeld")),
        formel="Sum egenkapital ÷ Sum egenkapital og gjeld",
        forklaring="Hvor stor del av eiendelene som er finansiert av eierne. "
                   "Høyere andel betyr mer motstandskraft mot tap.",
        inndata=["egenkapital", "sum_egenkapital_gjeld"],
    ))
    gg = Nokkeltall(
        kode="gjeldsgrad", navn="Gjeldsgrad", gruppe="Soliditet", enhet="ganger",
        verdi=del_(t.get("sum_gjeld"), ek),
        formel="Sum gjeld ÷ Sum egenkapital",
        forklaring="Hvor mange kroner gjeld selskapet har per krone egenkapital. "
                   "Lavere er mer solid.",
        inndata=["sum_gjeld", "egenkapital"],
    )
    if ek is not None and ek < 0:
        gg.verdi = None
        gg.merknad = "Ikke meningsfull fordi egenkapitalen er negativ."
    resultat.append(gg)

    rdg = Nokkeltall(
        kode="rentedekningsgrad", navn="Rentedekningsgrad", gruppe="Soliditet", enhet="ganger",
        verdi=None if not renter else del_(pluss(t.get("resultat_for_skatt"), renter), renter),
        formel="(Resultat før skatt + Rentekostnader) ÷ Rentekostnader",
        forklaring="Hvor mange ganger resultatet før renter dekker rentekostnadene. Under 1 betyr at "
                   "selskapet ikke tjente nok til å betale rentene. Over 3 regnes ofte som trygt.",
        inndata=["resultat_for_skatt", "annen_rentekostnad", "rentekostnad_konsern"],
    )
    if renter is None:
        rdg.merknad = "Selskapet har ikke oppgitt rentekostnader, så tallet kan ikke regnes ut."
    elif renter == 0:
        rdg.merknad = "Selskapet har ingen rentekostnader, så det er ingen renter å dekke."
    resultat.append(rdg)

    return resultat


# ---------------------------------------------------------------------------
# Balansekontroll
# ---------------------------------------------------------------------------
@dataclass
class Kontroll:
    navn: str
    status: str                  # "ok", "avrunding", "avvik" eller "mangler"
    venstre: Optional[float]
    hoyre: Optional[float]
    differanse: Optional[float]
    tekst: str


# Regnskapstall rapporteres ofte avrundet (f.eks. til hele millioner for
# store selskaper). Et avvik på inntil 0,01 % av totalen eller 1 000 kr
# regnes derfor som avrunding.
RELATIV_TOLERANSE = 0.0001
ABSOLUTT_TOLERANSE = 1000.0


def _kontroller(navn: str, venstre_navn: str, venstre: Optional[float],
                hoyre_navn: str, hoyre: Optional[float]) -> Kontroll:
    if venstre is None or hoyre is None:
        return Kontroll(navn, "mangler", venstre, hoyre, None,
                        f"Kan ikke kontrolleres – {venstre_navn if venstre is None else hoyre_navn} mangler.")
    diff = venstre - hoyre
    if diff == 0:
        return Kontroll(navn, "ok", venstre, hoyre, 0.0, f"{venstre_navn} = {hoyre_navn}.")
    toleranse = max(ABSOLUTT_TOLERANSE, RELATIV_TOLERANSE * max(abs(venstre), abs(hoyre)))
    if abs(diff) <= toleranse:
        return Kontroll(navn, "avrunding", venstre, hoyre, diff,
                        "Lite avvik som mest sannsynlig skyldes avrunding i det innsendte regnskapet.")
    return Kontroll(navn, "avvik", venstre, hoyre, diff,
                    f"{venstre_navn} og {hoyre_navn} er ikke like. Tallene bør sjekkes mot originalregnskapet.")


def balansekontroll(t: Tall) -> List[Kontroll]:
    """Sjekker at balansen går opp, og at delsummene stemmer."""
    return [
        _kontroller("Eiendeler = Egenkapital + gjeld",
                    "Sum eiendeler", t.get("sum_eiendeler"),
                    "Sum egenkapital og gjeld", t.get("sum_egenkapital_gjeld")),
        _kontroller("Anleggsmidler + omløpsmidler = Sum eiendeler",
                    "Anleggsmidler + omløpsmidler", pluss(t.get("anleggsmidler"), t.get("omlopsmidler")),
                    "Sum eiendeler", t.get("sum_eiendeler")),
        _kontroller("Egenkapital + gjeld = Sum egenkapital og gjeld",
                    "Egenkapital + gjeld", pluss(t.get("egenkapital"), t.get("sum_gjeld")),
                    "Sum egenkapital og gjeld", t.get("sum_egenkapital_gjeld")),
        _kontroller("Langsiktig + kortsiktig gjeld = Sum gjeld",
                    "Langsiktig + kortsiktig gjeld", pluss(t.get("langsiktig_gjeld"), t.get("kortsiktig_gjeld")),
                    "Sum gjeld", t.get("sum_gjeld")),
    ]


def samlet_status(kontroller: List[Kontroll]) -> str:
    """Den verste statusen blant kontrollene."""
    rang = {"ok": 0, "avrunding": 1, "mangler": 2, "avvik": 3}
    return max((k.status for k in kontroller), key=lambda s: rang[s], default="mangler")


# ---------------------------------------------------------------------------
# Veien fra inntekter til årsresultat
# ---------------------------------------------------------------------------
@dataclass
class Steg:
    navn: str
    verdi: Optional[float]
    type: str   # "start", "endring" eller "sum"


def resultatbro(t: Tall) -> List[Steg]:
    """Stegene i fossefallsgrafen. Kostnader og skatt er negative endringer."""
    def neg(x: Optional[float]) -> Optional[float]:
        return None if x is None else -x

    return [
        Steg("Driftsinntekter", t.get("sum_driftsinntekter"), "start"),
        Steg("Driftskostnader", neg(t.get("sum_driftskostnad")), "endring"),
        Steg("Driftsresultat", t.get("driftsresultat"), "sum"),
        Steg("Netto finans", t.get("netto_finans"), "endring"),
        Steg("Resultat før skatt", t.get("resultat_for_skatt"), "sum"),
        Steg("Skattekostnad", neg(t.get("skattekostnad")), "endring"),
        Steg("Årsresultat", t.get("aarsresultat"), "sum"),
    ]


# ---------------------------------------------------------------------------
# Drivere: hva forklarer endringen i årsresultatet fra året før?
# ---------------------------------------------------------------------------
@dataclass
class Driver:
    kode: str
    navn: str                 # «Driftsinntekter»
    fra: float                # postens verdi året før
    til: float                # postens verdi i år
    effekt: float             # hvor mye posten endret årsresultatet (+ = trakk opp)

    @property
    def endring(self) -> float:
        return self.til - self.fra

    @property
    def endring_pst(self) -> Optional[float]:
        return del_(self.endring, abs(self.fra)) if self.fra else None


@dataclass
class Driveranalyse:
    resultat_fra: float
    resultat_til: float
    drivere: List[Driver]     # alle bidrag, størst effekt først (inkl. evt. «Andre poster»)

    @property
    def endring(self) -> float:
        return self.resultat_til - self.resultat_fra

    def topp(self, n: int = 3) -> List[Driver]:
        return [d for d in self.drivere if d.effekt != 0][:n]


# (kode, navn, felt, fortegn): fortegn -1 betyr at en økning i posten trekker resultatet ned.
_RESULTATPOSTER = [
    ("inntekter", "Driftsinntekter", "sum_driftsinntekter", +1),
    ("kostnader", "Driftskostnader", "sum_driftskostnad", -1),
    ("finans", "Netto finans", "netto_finans", +1),
    ("skatt", "Skattekostnad", "skattekostnad", -1),
]


def _netto_finans(t: Tall) -> Optional[float]:
    if t.get("netto_finans") is not None:
        return t["netto_finans"]
    return minus(t.get("finansinntekter"), t.get("finanskostnader"))


def resultatdrivere(na: Tall, for_: Tall) -> Optional[Driveranalyse]:
    """Dekomponerer endringen i årsresultatet i bidrag fra hver resultatpost.

    Årsresultat = driftsinntekter − driftskostnader + netto finans − skatt, så
    Δårsresultat = Δinntekter − Δkostnader + Δfinans − Δskatt. Det som ikke
    forklares av disse (f.eks. avrunding eller poster API-et ikke har) blir
    «Andre poster». Poster som mangler ett av årene hoppes over (og havner da i
    «Andre poster»). Returnerer None hvis årsresultatet mangler.
    """
    r_til, r_fra = na.get("aarsresultat"), for_.get("aarsresultat")
    if r_til is None or r_fra is None:
        return None
    drivere: List[Driver] = []
    manglet_post = False
    for kode, navn, felt, fortegn in _RESULTATPOSTER:
        hent = _netto_finans if kode == "finans" else (lambda t, f=felt: t.get(f))
        a, b = hent(for_), hent(na)
        if a is None or b is None:
            manglet_post = True
            continue
        drivere.append(Driver(kode, navn, a, b, fortegn * (b - a)))
    forklart = sum(d.effekt for d in drivere)
    rest = (r_til - r_fra) - forklart
    # Rest under 0,5 % av resultatendringen (eller 1 000) regnes som avrunding – men ikke
    # når en post manglet, for da er resten (delvis) den manglende posten.
    if (manglet_post and rest != 0) or abs(rest) > max(ABSOLUTT_TOLERANSE, 0.005 * abs(r_til - r_fra)):
        drivere.append(Driver("andre", "Andre poster", 0.0, rest, rest))
    drivere.sort(key=lambda d: abs(d.effekt), reverse=True)
    return Driveranalyse(r_fra, r_til, drivere)


# ---------------------------------------------------------------------------
# Balansedrivere: hva flyttet seg i eiendelene og i finansieringen?
# ---------------------------------------------------------------------------
@dataclass
class Balanseside:
    navn: str                 # «Eiendeler» eller «Egenkapital og gjeld»
    fra: float
    til: float
    poster: List[Driver]      # effekt = endring i posten, størst først (inkl. evt. «Andre poster»)

    @property
    def endring(self) -> float:
        return self.til - self.fra

    def topp(self, n: int = 4) -> List[Driver]:
        return [d for d in self.poster if d.effekt != 0][:n]


_OMLOP_DELER = [
    ("varer", "Varer", "varer"),
    ("fordringer", "Fordringer", "fordringer"),
    ("investeringer", "Investeringer", "investeringer"),
    ("bank", "Bankinnskudd og kontanter", "bankinnskudd"),
]


def _rest_toleranse(endring: float) -> float:
    return max(ABSOLUTT_TOLERANSE, 0.005 * abs(endring))


def _side(navn: str, totalfelt: str, deler: List[tuple], na: Tall, for_: Tall) -> Optional[Balanseside]:
    """Én side av balansen. ``deler`` er (kode, navn, felt, underdeler) der underdeler er en
    liste i samme form som brukes i stedet for posten når de finnes."""
    fra, til = for_.get(totalfelt), na.get(totalfelt)
    if fra is None or til is None:
        return None
    poster: List[Driver] = []
    forklart = 0.0
    manglet = False
    for kode, postnavn, felt, underdeler in deler:
        a, b = for_.get(felt), na.get(felt)
        if a is None or b is None:
            manglet = True
            continue
        forklart += b - a
        if underdeler:
            # Del opp posten i underposter der begge år finnes; resten blir «Andre …».
            under = [(k, n, for_.get(f), na.get(f)) for k, n, f in underdeler]
            under = [(k, n, x, y) for k, n, x, y in under if x is not None and y is not None]
            if under:
                for k, n, x, y in under:
                    poster.append(Driver(k, n, x, y, y - x))
                rest = (b - a) - sum(y - x for _, _, x, y in under)
                if abs(rest) > _rest_toleranse(b - a):
                    poster.append(Driver(f"andre_{kode}", f"Andre {postnavn.lower()}", 0.0, rest, rest))
                continue
        poster.append(Driver(kode, postnavn, a, b, b - a))
    rest = (til - fra) - forklart
    if (manglet and rest != 0) or abs(rest) > _rest_toleranse(til - fra):
        poster.append(Driver("andre", "Andre poster", 0.0, rest, rest))
    poster.sort(key=lambda d: abs(d.effekt), reverse=True)
    return Balanseside(navn, fra, til, poster)


def balansedrivere(na: Tall, for_: Tall) -> Dict[str, Optional[Balanseside]]:
    """Dekomponerer endringen i sum eiendeler og i sum egenkapital og gjeld.

    Eiendeler: anleggsmidler + omløpsmidler (omløpsmidlene delt i varer, fordringer,
    investeringer og bank når tallene finnes). Finansiering: egenkapital + langsiktig
    + kortsiktig gjeld. Det som ikke forklares (f.eks. poster API-et ikke viser, eller
    feil i registerets tall) blir «Andre poster». Bidragene summerer til hele endringen.
    """
    return {
        "eiendeler": _side("Eiendeler", "sum_eiendeler", [
            ("anlegg", "Anleggsmidler", "anleggsmidler", None),
            ("omlop", "Omløpsmidler", "omlopsmidler", _OMLOP_DELER),
        ], na, for_),
        "finansiering": _side("Egenkapital og gjeld", "sum_egenkapital_gjeld", [
            ("ek", "Egenkapital", "egenkapital", None),
            ("lang", "Langsiktig gjeld", "langsiktig_gjeld", None),
            ("kort", "Kortsiktig gjeld", "kortsiktig_gjeld", None),
        ], na, for_),
    }


# ---------------------------------------------------------------------------
# Sammenligning av to selskaper
# ---------------------------------------------------------------------------
# True = høyere er sterkere, False = lavere er sterkere, None = ingen fasit
# (arbeidskapital er et beløp og avhenger av størrelsen på selskapet).
HOYERE_ER_BEDRE: Dict[str, Optional[bool]] = {
    "driftsmargin": True, "resultatmargin": True, "totalrentabilitet": True,
    "egenkapitalrentabilitet": True, "likviditetsgrad1": True, "arbeidskapital": None,
    "egenkapitalandel": True, "gjeldsgrad": False, "rentedekningsgrad": True,
}


def sterkest(kode: str, a: Optional[float], b: Optional[float]) -> Optional[int]:
    """0 hvis a er sterkest, 1 hvis b, None hvis likt, ukjent eller uten fasit."""
    retning = HOYERE_ER_BEDRE.get(kode)
    if retning is None or a is None or b is None or a == b:
        return None
    return 0 if (a > b) == retning else 1


def sammenligningstyper(type_a: str, typer_a: List[str], eier_a: bool,
                        typer_b: List[str], standard_b: str, eier_b: bool) -> tuple:
    """Hvilken regnskapstype (SELSKAP/KONSERN) hvert selskap skal vises med i sammenligningen.

    Er ett av dem et eierselskap, sier bare konsernet noe om driften – da brukes konsern for
    begge når begge har det, så tallene er sammenlignbare. Ellers samme type som hovedvisningen.
    Returnerer (type_a, type_b).
    """
    if (eier_a or eier_b) and "KONSERN" in typer_a and "KONSERN" in typer_b:
        return "KONSERN", "KONSERN"
    if type_a in typer_b and not eier_b:
        return type_a, type_a
    return type_a, standard_b
