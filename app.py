"""Regnskapsdashboard – visning (Streamlit).

Start med:  streamlit run app.py

Denne fila inneholder kun visning. Henting ligger i ``brreg_api.py``,
utregninger i ``beregninger.py``, Excel-eksport i ``excel_eksport.py`` og
utseendet (CSS og HTML-byggesteiner i Apple-stil) i ``stil.py``.
Appen bruker ingen KI-tjenester – bare åpne data fra Brønnøysundregistrene.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import borsliste
import brreg_api as api
import formatering as fmt
import forklaringer
import stil
from beregninger import (ALTMAN_FARE, ALTMAN_TRYGG, altman_z, balansedrivere, balansekontroll, beregn_nokkeltall,
                         er_eierselskap, finans_er_netto, resultatbro, resultatdrivere, samlet_status,
                         sammenligningstyper, sterkest)
from sammendrag import lag_sammendrag
from excel_eksport import POSTER, lag_excel

MAPPE = Path(__file__).parent
st.set_page_config(page_title="Regnskapsdashboard", page_icon=str(MAPPE / "static" / "favicon.png"),
                   layout="wide")

# Lenke til app-ikonet i <head>, så Safari bruker det ved «Legg til i Dock»
# og iPhone ved «Legg til på Hjem-skjerm». Komponenten er usynlig (høyde 0).
components.html("""<script>
const d = window.parent.document;
// Ikonet ligger relativt til app-dokumentet: /app/static/ lokalt, /~/+/app/static/ på Streamlit Cloud.
const ikon = new URL('app/static/apple-touch-icon.png', window.parent.location.href.split('?')[0]).href;
// På Streamlit Cloud kjører appen i en iframe, og det ytre dokumentet (samme origin) har Streamlits
// eget ikon. Sett vårt i begge, og erstatt det som finnes.
const dokumenter = [d];
try { if (window.top.document !== d) dokumenter.push(window.top.document); } catch (e) {}
for (const doc of dokumenter) {
  let l = doc.querySelector('link[rel="apple-touch-icon"]');
  if (!l) { l = doc.createElement('link'); l.rel = 'apple-touch-icon'; doc.head.appendChild(l); }
  if (l.href !== ikon) l.href = ikon;
  if (!doc.querySelector('meta[name="apple-mobile-web-app-title"]')) {
    const m = doc.createElement('meta'); m.name = 'apple-mobile-web-app-title'; m.content = 'Regnskap';
    doc.head.appendChild(m);
  }
}
// Forklaringsbobler («i»): lukk ved klikk utenfor eller Esc, og bare én åpen om gangen.
if (!d.rdInfo) {
  d.rdInfo = true;
  const lukk = (unntak) => d.querySelectorAll('details.rd-info[open]').forEach(el => { if (el !== unntak) el.open = false; });
  d.addEventListener('click', (e) => { const egen = e.target.closest && e.target.closest('details.rd-info'); lukk(egen); });
  d.addEventListener('keydown', (e) => { if (e.key === 'Escape') lukk(null); });
  d.addEventListener('toggle', (e) => { if (e.target.matches && e.target.matches('details.rd-info') && e.target.open) lukk(e.target); }, true);
}
</script>""", height=0)


def forklar(nokkel: str, side: str = "hoyre") -> str:
    """HTML for en «i»-knapp med forklaringen ``nokkel`` fra forklaringer.py."""
    tittel, avsnitt = forklaringer.hent(nokkel)
    return stil.info(tittel, avsnitt, side)

ETIKETT = {felt: navn.strip() for navn, felt in POSTER if felt}

EKSEMPLER = [("Equinor", "923609016"), ("Norsk Hydro", "914778271"), ("Kongsberg Gruppen", "943753709"),
             ("Telenor", "982463718"), ("Orkla", "910747711"), ("Yara", "986228608")]

REGNSKAPSREGLER = {"IFRS": "IFRS", "forenkletAnvendelseIFRS": "Forenklet IFRS",
                   "regnskapsloven": "Regnskapsloven", "god regnskapsskikk": "God regnskapsskikk",
                   "regnskapslovenAlminneligRegler": "Regnskapsloven (alminnelige regler)"}


def regnskapsregler_tekst(kode: str) -> str:
    """Kjente koder får pent navn; ukjente «camelCase»-koder deles opp i ord."""
    if kode in REGNSKAPSREGLER:
        return REGNSKAPSREGLER[kode]
    ord_ = re.sub(r"(?<=[a-zæøå])(?=[A-ZÆØÅ])", " ", kode).split()
    return " ".join([ord_[0].capitalize()] + [o.lower() if o != "IFRS" else o for o in ord_[1:]]) if ord_ else kode


def modus() -> str:
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        return "light"


# ---------------------------------------------------------------------------
# Henting (mellomlagres i en time så samme selskap ikke hentes på nytt)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def hent_enhet(orgnr: str) -> Dict[str, Any]:
    return api.hent_enhet(orgnr)


@st.cache_data(ttl=3600, show_spinner=False)
def hent_regnskap(orgnr: str) -> List[Dict[str, Any]]:
    return api.hent_regnskap(orgnr)


@st.cache_data(ttl=3600, show_spinner=False)
def hent_roller(orgnr: str) -> Dict[str, Any]:
    return api.hent_roller(orgnr)


@st.cache_data(ttl=3600, show_spinner=False)
def hent_pdf_aar(orgnr: str) -> List[int]:
    return api.hent_pdf_aar(orgnr)


# ---------------------------------------------------------------------------
# Små hjelpere for visning
# ---------------------------------------------------------------------------
def skala(verdier: List[Optional[float]]) -> tuple:
    """Velger enhet for grafaksen: (divisor, tekst)."""
    storst = max((abs(v) for v in verdier if v is not None), default=0)
    if storst >= 1e10:
        return 1e9, "mrd."
    if storst >= 1e7:
        return 1e6, "mill."
    if storst >= 1e4:
        return 1e3, "tusen"
    return 1, ""


def delt_belop(verdi: Optional[float], valuta: str) -> Tuple[str, str]:
    """68 000 000 000 -> («68,0», «mrd. USD»). Brukes i KPI-kortene."""
    tekst = fmt.belop(verdi, valuta)
    if tekst == fmt.MANGLER:
        return tekst, ""
    tall = tekst.removesuffix(f" {valuta}")
    for skalatekst in (" mrd.", " mill."):
        if tall.endswith(skalatekst):
            return tall.removesuffix(skalatekst), f"{skalatekst.strip()} {valuta}"
    return tall, valuta


def endring(na: Optional[float], for_: Optional[float]) -> Optional[float]:
    if na is None or for_ is None or for_ == 0:
        return None
    return (na - for_) / abs(for_) * 100


def grafoppsett(fig: go.Figure, f: Dict[str, Any], y_tittel: str, hoyde: int = 400) -> None:
    fig.update_layout(
        height=hoyde, margin=dict(l=56, r=8, t=36, b=48),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=f["font"], color=f["tekst"], size=13),
        hoverlabel=dict(font=dict(family=f["font"], size=13), bgcolor=f["flate"],
                        bordercolor=f["akse"], font_color=f["tekst"]),
        separators=", ",  # norsk desimal- og tusenskille
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0, traceorder="normal",
                    font=dict(size=12, color=f["dempet"]), itemclick=False, itemdoubleclick=False),
        uniformtext=dict(minsize=11, mode="show"),
    )
    fig.update_yaxes(title=y_tittel, automargin=True, gridcolor=f["rutenett"], zerolinecolor=f["akse"],
                     tickfont=dict(color=f["dempet"], size=12), title_font=dict(color=f["dempet"], size=12))
    fig.update_xaxes(automargin=True, showgrid=False, linecolor=f["akse"], tickfont=dict(color=f["tekst"]))


# ---------------------------------------------------------------------------
# Seksjoner
# ---------------------------------------------------------------------------
def vis_selskapskort(e: Dict[str, Any]) -> None:
    undertittel = " · ".join(x for x in (e.get("organisasjonsform"), e.get("naering"), (e.get("kommune") or "").title())
                             if x)
    hjem = e.get("hjemmeside")
    lenke = None
    if hjem:
        ren = hjem.removeprefix("https://").removeprefix("http://")
        lenke = f'<a href="https://{stil.e(ren)}" target="_blank" rel="noopener">{stil.e(ren)}</a>'
    kap = fmt.belop(e.get("aksjekapital"), e.get("aksjekapital_valuta") or "NOK", kort=False) \
        if e.get("aksjekapital") is not None else None
    naering = " ".join(x for x in (e.get("naering_kode"), e.get("naering")) if x) or None
    fakta = stil.fakta([
        ("Org.nr", e.get("orgnr"), False),
        ("Næring", naering, False),
        ("Adresse", e.get("adresse"), False),
        ("Ansatte", None if e.get("ansatte") is None else fmt.heltall(e.get("ansatte")), False),
        ("Stiftet", e.get("stiftet"), False),
        ("Aksjekapital", kap, False),
        ("Hjemmeside", lenke, True),
        ("Siste innsendte årsregnskap", e.get("siste_aarsregnskap"), False),
    ])
    varsler = "".join(stil.pille(v, "feil", "utrop") for v in e["varsler"])
    varsler = f'<div class="rd-piller rd-varsel">{varsler}</div>' if varsler else ""
    st.html(f"""<div class="rd-kort">
      <div class="rd-selskap"><div class="rd-monogram" aria-hidden="true">{stil.e(stil.monogram(e.get('navn')))}</div>
        <div><h2 class="rd-navn">{stil.e(stil.pent_navn(e.get('navn')))}</h2>
        <p class="rd-undertittel">{stil.e(undertittel)}</p></div>{forklar("selskapskort")}</div>
      {varsler}{fakta}</div>""")


def vis_statuslinje(r: Dict[str, Any], status: str) -> None:
    regler = r.get("regnskapsregler")
    piller = [
        stil.pille(f"Regnskapsår {r['aar']}", ikon="kalender", tittel=f"{r['fra_dato']} – {r['til_dato']}"),
        stil.pille(f"Beløp i {r['valuta']}", "adv" if r["valuta"] != "NOK" else "", "valuta",
                   tittel="Selskapet rapporterer i denne valutaen" if r["valuta"] != "NOK" else None),
    ]
    if regler:
        piller.append(stil.pille(regnskapsregler_tekst(regler), ikon="bok"))
    piller.append({
        "ok": stil.pille("Balansen går opp", "ok", "sjekk"),
        "avrunding": stil.pille("Balansen går opp (avrunding)", "ok", "sjekk",
                                "Små avvik som skyldes avrunding i det innsendte regnskapet"),
        "mangler": stil.pille("Balansen kan ikke kontrolleres", "adv", "utrop", "Noen tall mangler"),
        "avvik": stil.pille("Balansen går ikke opp", "feil", "kryss"),
    }[status])
    if r.get("ikke_revidert"):
        piller.append(stil.pille("Ikke revidert", "adv", "utrop"))
    st.html(f'<div class="rd-piller" style="margin:12px 0 0">{"".join(piller)}{forklar("status", "venstre")}</div>')


def vis_balansedetaljer(r: Dict[str, Any], kontroller: list, status: str) -> None:
    with st.expander("Detaljer om balansekontrollen", expanded=(status == "avvik")):
        ikon = {"ok": "✓ OK", "avrunding": "✓ Avrunding", "mangler": "! Mangler", "avvik": "✕ Avvik"}
        df = pd.DataFrame([{
            "Kontroll": k.navn,
            "Venstre side": fmt.belop(k.venstre, r["valuta"], kort=False),
            "Høyre side": fmt.belop(k.hoyre, r["valuta"], kort=False),
            "Differanse": fmt.belop(k.differanse, r["valuta"], kort=False),
            "Status": ikon[k.status],
            "Kommentar": k.tekst,
        } for k in kontroller])
        st.dataframe(df, hide_index=True, width="stretch")


def vis_hovedtall(r: Dict[str, Any], forrige: Optional[Dict[str, Any]]) -> None:
    under = f"Beløp i {r['valuta']}" + (f" · endring fra {forrige['aar']}" if forrige else "")
    st.html(stil.seksjon("Hovedtall", under))
    t, valuta = r["tall"], r["valuta"]
    felt = [("Driftsinntekter", "sum_driftsinntekter"), ("Driftsresultat", "driftsresultat"),
            ("Årsresultat", "aarsresultat"), ("Sum eiendeler", "sum_eiendeler"),
            ("Egenkapital", "egenkapital")]
    kort = []
    for navn, nokkel in felt:
        tall, enhet = delt_belop(t.get(nokkel), valuta)
        pst = endring(t.get(nokkel), forrige["tall"].get(nokkel)) if forrige else None
        delta = (pst, str(forrige["aar"])) if pst is not None else None
        kort.append(stil.kpi(navn, tall, enhet, delta, f"Nøyaktig: {fmt.belop(t.get(nokkel), valuta, kort=False)}",
                             forklar(nokkel)))
    st.html(f'<div class="rd-kpier">{"".join(kort)}</div>')


def vis_oversikt(r: Dict[str, Any], forrige: Optional[Dict[str, Any]], eierselskap_alene: bool,
                 balanse_avvik: bool) -> None:
    """«Kort fortalt» (sammendrag i klartekst) og konkursrisiko side om side."""
    sam = lag_sammendrag(r, forrige, eierselskap_alene, balanse_avvik)
    venstre = stil.sammendrag(sam.overskrift, [(p.tekst, p.tone) for p in sam.punkter], forklar("sammendrag"))

    az = altman_z(r["tall"])
    ledd = [(navn, fmt.ganger(x), "mangler" if b is None else f"{'+' if b >= 0 else '−'}{fmt.ganger(abs(b))}")
            for _, navn, x, _, b in az.ledd]
    merknader = []
    if eierselskap_alene:
        merknader.append("Scoren er laget for selskaper med egen drift. For et eierselskap gir konsernet et bedre bilde.")
    if balanse_avvik:
        merknader.append("Balansen i registerets tall går ikke opp, så scoren kan være misvisende.")
    if az.merknad:
        merknader.append(az.merknad)
    hoyre = stil.konkursrisiko(az.score, fmt.ganger(az.score), az.sone, (ALTMAN_FARE, ALTMAN_TRYGG), ledd,
                               merknader, forklar("altman"))
    st.html(f'<div class="rd-to" style="margin-top:6px">{venstre}{hoyre}</div>')


def vis_nokkeltall(r: Dict[str, Any], forrige: Optional[Dict[str, Any]]) -> None:
    st.html(stil.seksjon("Nøkkeltall", "Trykk på et nøkkeltall for å se formelen og tallene bak."))
    t, valuta = r["tall"], r["valuta"]
    na = beregn_nokkeltall(t)
    for_ = {n.kode: n for n in beregn_nokkeltall(forrige["tall"])} if forrige else {}
    grupper = []
    for gruppenavn in ("Lønnsomhet", "Likviditet", "Soliditet"):
        rader = []
        for n in (x for x in na if x.gruppe == gruppenavn):
            verdi = fmt.nokkeltall(n.verdi, n.enhet, valuta)
            if n.verdi is None and n.merknad and "meningsfull" in n.merknad:
                verdi = "ikke meningsfull"
            tidligere = for_.get(n.kode)
            forrige_tekst = f"{forrige['aar']}: {fmt.nokkeltall(tidligere.verdi, n.enhet, valuta)}" \
                if tidligere else None
            inndata = [(ETIKETT.get(f, f), fmt.belop(t.get(f), valuta, kort=False)) for f in n.inndata]
            enhet = ""
            if n.enhet == "belop" and n.verdi is not None:
                verdi, enhet = delt_belop(n.verdi, valuta)
            rader.append(stil.nokkeltall_rad(n.navn, verdi, forrige_tekst, n.formel, n.forklaring,
                                             inndata, n.merknad, enhet))
        nokkel = gruppenavn.lower().replace("ø", "o")
        grupper.append(stil.gruppe(gruppenavn, rader, forklar(nokkel)))
    st.html(f'<div class="rd-grupper">{"".join(grupper)}</div>')


def graf_balanse(r: Dict[str, Any], f: Dict[str, Any]) -> None:
    st.html(stil.tittelrad("Balansen", "Hva selskapet eier, og hvordan det er finansiert", forklar("graf_balanse")))
    t = r["tall"]
    segmenter = [
        ("Anleggsmidler", "anleggsmidler", 0), ("Omløpsmidler", "omlopsmidler", 0),
        ("Egenkapital", "egenkapital", 1), ("Langsiktig gjeld", "langsiktig_gjeld", 1),
        ("Kortsiktig gjeld", "kortsiktig_gjeld", 1),
    ]
    mangler = [navn for navn, felt, _ in segmenter if t.get(felt) is None]
    div, enhet = skala([t.get(felt) for _, felt, _ in segmenter])
    stolper = ["Eiendeler", "Egenkapital og gjeld"]
    fig = go.Figure()
    for i, (navn, felt, stolpe) in enumerate(segmenter):
        v = t.get(felt)
        if v is None:
            continue
        y = [None, None]
        y[stolpe] = v / div
        andel = fmt.prosent(v / t["sum_eiendeler"], 0) if t.get("sum_eiendeler") else ""
        fig.add_bar(
            name=navn, x=stolper, y=y, marker_color=f["serie"][i],
            marker_line=dict(color=f["flate"], width=2),
            text=[f"{navn}<br>{andel}" if j == stolpe else None for j in range(2)],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#0b0b0b" if f["serie"][i] in ("#eda100",) else "#ffffff", size=12),
            customdata=[fmt.belop(v, r["valuta"], kort=False)] * 2,
            hovertemplate=f"<b>{navn}</b><br>%{{customdata}}<extra></extra>",
        )
    fig.update_layout(barmode="stack", bargap=0.38, barcornerradius=6)
    grafoppsett(fig, f, f"{enhet} {r['valuta']}".strip())
    st.plotly_chart(fig, theme=None, config={"displayModeBar": False})
    if mangler:
        st.caption(f"Ikke vist fordi tallet mangler: {', '.join(mangler)}.")


def graf_resultat(r: Dict[str, Any], f: Dict[str, Any]) -> None:
    st.html(stil.tittelrad("Fra inntekter til årsresultat", "Grå er summer · blå legger til · rød trekker fra",
                           forklar("graf_resultat")))
    steg = resultatbro(r["tall"])
    mangler = [s.navn for s in steg if s.verdi is None]
    if mangler:
        st.info(f"Grafen kan ikke tegnes fordi disse tallene mangler: {', '.join(mangler)}.")
        return
    div, enhet = skala([s.verdi for s in steg])
    # Bygges som vanlige stolper med «base», så summene vises nøyaktig slik
    # de er rapportert (ikke regnet ut på nytt av grafen).
    basis, hoyde, farge = [], [], []
    lopende = 0.0
    for s in steg:
        if s.type == "endring":
            basis.append(lopende / div)
            hoyde.append(s.verdi / div)
            farge.append(f["opp"] if s.verdi >= 0 else f["ned"])
            lopende += s.verdi
        else:
            basis.append(0)
            hoyde.append(s.verdi / div)
            farge.append(f["sum"])
            lopende = s.verdi
    # Små endringer (ofte netto finans) blir nesten usynlige. Vis dem med en minstehøyde på
    # 1,5 % av aksen; etiketten og hover-teksten viser fortsatt det nøyaktige tallet.
    spenn = max(max(b, b + h) for b, h in zip(basis, hoyde)) - min(0, min(min(b, b + h) for b, h in zip(basis, hoyde)))
    minst = 0.015 * spenn
    for j, s in enumerate(steg):
        if s.type == "endring" and s.verdi != 0 and abs(hoyde[j]) < minst:
            hoyde[j] = minst if s.verdi >= 0 else -minst
    fig = go.Figure(go.Bar(
        x=[s.navn for s in steg], y=hoyde, base=basis,
        marker=dict(color=farge, line=dict(color=f["flate"], width=2), cornerradius=6),
        customdata=[fmt.belop(s.verdi, r["valuta"], kort=False) for s in steg],
        hovertemplate="<b>%{x}</b><br>%{customdata}<extra></extra>",
    ))
    # Etikett over toppen av hver søyle (også for negative endringer), så de ikke kolliderer.
    desimaler = 1 if div > 1 else 0
    for s, b, h in zip(steg, basis, hoyde):
        fig.add_annotation(x=s.navn, y=max(b, b + h), text=fmt.ganger(s.verdi / div, desimaler),
                           showarrow=False, yanchor="bottom", yshift=3,
                           font=dict(color=f["tekst"], size=12))
    topp = max(max(b, b + h) for b, h in zip(basis, hoyde))
    bunn = min(0, min(min(b, b + h) for b, h in zip(basis, hoyde)))
    grafoppsett(fig, f, f"{enhet} {r['valuta']}".strip())
    fig.update_layout(showlegend=False, bargap=0.3)
    fig.update_yaxes(range=[bunn * 1.1, topp * 1.12])
    st.plotly_chart(fig, theme=None, config={"displayModeBar": False})


def vis_tabell(regnskaper: List[Dict[str, Any]]) -> None:
    with st.expander("Alle regnskapstall i tabell"):
        rader = []
        for etikett, felt in POSTER:
            if felt is None:
                rader.append({"Post": etikett.upper(), **{str(r["aar"]): "" for r in regnskaper}})
                continue
            rader.append({"Post": etikett,
                          **{str(r["aar"]): fmt.belop(r["tall"].get(felt), r["valuta"], kort=False)
                             for r in regnskaper}})
        st.dataframe(pd.DataFrame(rader), hide_index=True, width="stretch", height=600)
        netto_aar = [str(r["aar"]) for r in regnskaper if finans_er_netto(r["tall"])]
        if netto_aar:
            st.caption(f"Finanskostnader er ikke oppgitt for {', '.join(netto_aar)}, og finansinntektene er lik "
                       "netto finans. Selskapet har trolig rapportert finansposter netto på én linje, så "
                       "«Finansinntekter» er da et nettotall.")


_DRIVER_TITTEL = {
    "inntekter": ("Driftsinntektene økte", "Driftsinntektene falt"),
    "kostnader": ("Driftskostnadene økte", "Driftskostnadene falt"),
    "finans": ("Finansresultatet ble bedre", "Finansresultatet ble svakere"),
    "skatt": ("Skattekostnaden økte", "Skattekostnaden falt"),
    "andre": ("Andre poster", "Andre poster"),
}


def html_drivere(r: Dict[str, Any], forrige: Optional[Dict[str, Any]]) -> str:
    """Kort: topp 3 drivere bak endringen i årsresultatet."""
    valuta = r["valuta"]
    hode = stil.tittelrad("Hva drev endringen i resultatet?",
                          "De tre resultatpostene som endret årsresultatet mest", forklar("drivere"), luft_under=True)
    if not forrige:
        return (f'<div class="rd-kort">{hode}<p class="rd-tom">Ingen sammenligning: regnskapet for '
                f'{r["aar"] - 1} finnes ikke i Regnskapsregisterets API.</p></div>')
    if forrige["valuta"] != valuta:
        return (f'<div class="rd-kort">{hode}<p class="rd-tom">Kan ikke sammenligne fordi valutaen endret seg '
                f'({stil.e(forrige["valuta"])} → {stil.e(valuta)}).</p></div>')
    analyse = resultatdrivere(r["tall"], forrige["tall"])
    if analyse is None:
        return f'<div class="rd-kort">{hode}<p class="rd-tom">Årsresultatet mangler for et av årene.</p></div>'

    pst = endring(analyse.resultat_til, analyse.resultat_fra)
    retning = "økte" if analyse.endring > 0 else "falt" if analyse.endring < 0 else "var uendret"
    topp_ = (f'<div class="rd-drivere-topp"><span class="fra-til">{stil.e(fmt.belop(analyse.resultat_fra, valuta))}'
             f' <span>→</span> {stil.e(fmt.belop(analyse.resultat_til, valuta))}</span>'
             + stil.pille(f"Årsresultatet {retning} {fmt.fortegn_belop(analyse.endring, valuta)}"
                          + (f" ({fmt.fortegn_prosent(pst / 100)})" if pst is not None else ""),
                          "ok" if analyse.endring >= 0 else "feil") + "</div>")
    drivere = analyse.topp(3)
    storst = max((abs(d.effekt) for d in drivere), default=1) or 1
    rader = []
    for nr, d in enumerate(drivere, start=1):
        opp = d.effekt > 0
        if d.kode == "andre":
            tekst = ("Det som ikke forklares av postene over, f.eks. poster API-et ikke viser hver for seg "
                     "eller avrunding.")
        else:
            # Prosentendring gir bare mening når posten var positiv året før og ikke skiftet fortegn.
            endr_pst = d.endring_pst if d.fra > 0 and d.til >= 0 else None
            tekst = (f"Fra {fmt.belop(d.fra, valuta)} i {forrige['aar']} til {fmt.belop(d.til, valuta)} i {r['aar']}"
                     + (f" ({fmt.fortegn_prosent(endr_pst)})" if endr_pst is not None else "")
                     + f". {'Løftet' if opp else 'Trakk ned'} årsresultatet med {fmt.belop(abs(d.effekt), valuta)}.")
        tittel = _DRIVER_TITTEL[d.kode][0 if d.endring >= 0 else 1] if d.kode != "andre" else "Andre poster"
        rader.append(stil.driver_rad(nr, tittel, tekst, fmt.fortegn_belop(d.effekt, valuta), opp,
                                     abs(d.effekt) / storst * 100))
    merk = ('<p class="rd-merk">Regnet ut fra tallene: endringen i hver resultatpost og hvor mye den flyttet '
            'årsresultatet. Bidragene summerer seg til hele endringen. Tallene viser <i>hva</i> som endret seg, '
            'ikke <i>hvorfor</i>.</p>')
    return f'<div class="rd-kort">{hode}{topp_}{"".join(rader)}{merk}</div>'


def html_hendelser(hendelser: List[Dict[str, Any]]) -> str:
    hode = stil.tittelrad("Hendelser i registrene", "Siste endringer i ledelse, styre, kapital og vedtekter (24 mnd.)",
                          forklar("hendelser"), luft_under=True)
    if not hendelser:
        innhold = ('<p class="rd-tom">Ingen registrerte endringer i roller, kapital eller vedtekter de '
                   'siste 24 månedene.</p>')
    else:
        innhold = "".join(stil.hendelse_rad(fmt.dato_kort(h["dato"]), h["tittel"], h["detalj"])
                          for h in hendelser[:3])
    merk = ('<p class="rd-merk">Fra Enhetsregisteret. Nyheter, oppkjøp og kontrakter finnes ikke i de '
            'åpne registrene.</p>')
    return f'<div class="rd-kort">{hode}{innhold}{merk}</div>'


_BALANSE_TEKST = {
    "anlegg": "Bygg, maskiner, aksjer i andre selskaper og andre eiendeler som skal brukes lenge.",
    "varer": "Varelager.", "fordringer": "Penger kunder og andre skylder selskapet.",
    "investeringer": "Kortsiktige plasseringer, f.eks. aksjer og fond som lett kan selges.",
    "bank": "Bankinnskudd og kontanter.", "omlop": "Varer, fordringer, investeringer og bank samlet.",
    "andre_omlop": "Den delen av omløpsmidlene API-et ikke viser hver for seg.",
    "ek": "Eiernes andel: innskutt kapital og tilbakeholdt overskudd.",
    "lang": "Gjeld som forfaller om mer enn ett år, f.eks. obligasjoner og banklån.",
    "kort": "Gjeld som forfaller innen ett år, f.eks. leverandørgjeld, skatt og utbytte.",
    "andre": "Det som ikke forklares av postene over, f.eks. poster API-et ikke viser eller feil i registerets tall.",
}


def html_balansedrivere(r: Dict[str, Any], forrige: Optional[Dict[str, Any]]) -> str:
    """Kort: hvilke poster som flyttet seg mest i eiendelene og i finansieringen."""
    valuta = r["valuta"]
    hode = stil.tittelrad("Hva endret seg i balansen?", "Postene som flyttet seg mest på hver side av balansen",
                          forklar("balansedrivere"), luft_under=True)
    if not forrige or forrige["valuta"] != valuta:
        return ""
    sider = balansedrivere(r["tall"], forrige["tall"])
    blokker = []
    for side in sider.values():
        if side is None:
            continue
        poster = side.topp(4)
        storst = max((abs(d.effekt) for d in poster), default=1) or 1
        rader = []
        for nr, d in enumerate(poster, start=1):
            tekst = _BALANSE_TEKST.get(d.kode, "")
            if not d.kode.startswith("andre"):
                tekst = f"Fra {fmt.belop(d.fra, valuta)} til {fmt.belop(d.til, valuta)}. " + tekst
            rader.append(stil.driver_rad(nr, d.navn, tekst, fmt.fortegn_belop(d.effekt, valuta), d.effekt > 0,
                                         abs(d.effekt) / storst * 100, noytral=True))
        pst = endring(side.til, side.fra)
        tittel = (f'<h4>{stil.e(side.navn)}<span>{stil.e(fmt.belop(side.fra, valuta))} → '
                  f'{stil.e(fmt.belop(side.til, valuta))} · {stil.e(fmt.fortegn_belop(side.endring, valuta))}'
                  + (f" ({stil.e(fmt.fortegn_prosent(pst / 100))})" if pst is not None else "") + "</span></h4>")
        innhold = "".join(rader) or '<p class="rd-tom">Ingen endring.</p>'
        blokker.append(f'<div class="rd-balside">{tittel}{innhold}</div>')
    if not blokker:
        return ""
    merk = ('<p class="rd-merk">Blå er en økning, grå en nedgang. Fargene sier ikke om endringen er god eller '
            'dårlig: mer gjeld kan for eksempel bety at selskapet investerer.</p>')
    return f'<div class="rd-kort" style="margin-top:14px">{hode}<div class="rd-balsider">{"".join(blokker)}</div>{merk}</div>'


def vis_endringer(r: Dict[str, Any], forrige: Optional[Dict[str, Any]], hendelser: List[Dict[str, Any]]) -> None:
    under = f"{forrige['aar']} → {r['aar']}" if forrige else f"Regnskapsår {r['aar']}"
    st.html(stil.seksjon("Hva endret seg?", under))
    st.html(f'<div class="rd-to">{html_drivere(r, forrige)}{html_hendelser(hendelser)}</div>'
            + html_balansedrivere(r, forrige))


def vis_utvikling(regnskaper: List[Dict[str, Any]], valgt_aar: int, f: Dict[str, Any]) -> None:
    """Hovedtall og nøkkeltall for alle år API-et har (vanligvis tre)."""
    aarene = sorted(regnskaper, key=lambda r: r["aar"])            # eldst først, som en tidslinje
    if len(aarene) < 2:
        return
    valuta = aarene[-1]["valuta"]
    st.html(stil.seksjon("Utvikling", f"{aarene[0]['aar']}–{aarene[-1]['aar']} · alle år Regnskapsregisteret har"))

    with st.container(key="kort-utvikling"):
        st.html(stil.tittelrad("Inntekter og resultat", f"Per år, i {valuta}", forklar("utvikling")))
        serier = [("Driftsinntekter", "sum_driftsinntekter"), ("Driftsresultat", "driftsresultat"),
                  ("Årsresultat", "aarsresultat")]
        div, enhet = skala([r["tall"].get(felt) for r in aarene for _, felt in serier])
        fig = go.Figure()
        for i, (navn, felt) in enumerate(serier):
            verdier = [r["tall"].get(felt) for r in aarene]
            fig.add_bar(name=navn, x=[str(r["aar"]) for r in aarene],
                        y=[None if v is None else v / div for v in verdier],
                        marker=dict(color=f["serie"][i], line=dict(color=f["flate"], width=2), cornerradius=5),
                        customdata=[fmt.belop(v, r["valuta"], kort=False) for v, r in zip(verdier, aarene)],
                        hovertemplate=f"<b>{navn}</b> %{{x}}<br>%{{customdata}}<extra></extra>")
        fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
        grafoppsett(fig, f, f"{enhet} {valuta}".strip(), hoyde=340)
        alle = [r["tall"].get(felt) for r in aarene for _, felt in serier if r["tall"].get(felt) is not None]
        if alle:
            fig.update_yaxes(range=[min(0, min(alle) / div * 1.12), max(0, max(alle)) / div * 1.12])
        st.plotly_chart(fig, theme=None, config={"displayModeBar": False})

    with st.container(key="kort-utviklingstabell"):
        st.html(stil.tittelrad("Tall og nøkkeltall per år", "Valgt år er uthevet", forklar("utvikling"), luft_under=True))
        overskrift = [""] + [str(r["aar"]) for r in aarene]
        valgt_kol = 1 + next(i for i, r in enumerate(aarene) if r["aar"] == valgt_aar)
        rader: List[List[str]] = [["Hovedtall"]]
        for navn, felt in [("Driftsinntekter", "sum_driftsinntekter"), ("Driftsresultat", "driftsresultat"),
                           ("Årsresultat", "aarsresultat"), ("Sum eiendeler", "sum_eiendeler"),
                           ("Egenkapital", "egenkapital")]:
            rader.append([navn] + [fmt.belop(r["tall"].get(felt), r["valuta"]) for r in aarene])
        nt_per_aar = [{n.kode: n for n in beregn_nokkeltall(r["tall"])} for r in aarene]
        gruppe = None
        for n in beregn_nokkeltall(aarene[-1]["tall"]):
            if n.gruppe != gruppe:
                gruppe = n.gruppe
                rader.append([gruppe])
            celler = []
            for nt, r in zip(nt_per_aar, aarene):
                x = nt[n.kode]
                tekst = fmt.nokkeltall(x.verdi, x.enhet, r["valuta"])
                if x.verdi is None and x.merknad and "meningsfull" in x.merknad:
                    tekst = "ikke meningsfull"
                celler.append(tekst)
            rader.append([n.navn] + celler)
        grupperader = [i for i, rad in enumerate(rader) if len(rad) == 1]
        st.html(stil.tabell(overskrift, rader, valgt_kol, grupperader))


def standard_regnskap(raa: List[Dict[str, Any]]) -> Tuple[Optional[str], List[str], bool]:
    """(standardtype, tilgjengelige typer, er eierselskap).

    Er morselskapet i hovedsak et eierselskap (inntektene er utbytte o.l. fra datterselskaper),
    gir konsernregnskapet det riktige bildet av driften, så det vises først.
    """
    typer = api.tilgjengelige_typer(raa)
    if not typer:
        return None, typer, False
    selskap_siste = api.velg_regnskap(raa, "SELSKAP")[:1]
    eierselskap = bool(selskap_siste) and er_eierselskap(selskap_siste[0]["tall"]) and "KONSERN" in typer
    return ("KONSERN" if eierselskap else typer[0]), typer, eierselskap


def kortnavn(navn: Optional[str]) -> str:
    """«EQUINOR ASA» -> «Equinor». Brukes i smale tabellhoder."""
    pent = stil.pent_navn(navn) or "Selskap"
    return re.sub(r"\s+(ASA|AS|SA|ANS|DA|NUF)$", "", pent)


SAMMENLIGN_PROSENT = ["driftsmargin", "resultatmargin", "totalrentabilitet", "egenkapitalrentabilitet",
                      "egenkapitalandel"]


def vis_sammenligning(enhet_a: Dict[str, Any], raa_a: List[Dict[str, Any]], valgt_type: str, valgt_aar: int,
                      f: Dict[str, Any]) -> None:
    """Valgt selskap side om side med et annet org.nr."""
    st.html(stil.seksjon("Sammenlign", "Se selskapet side om side med et annet"))
    with st.container(key="kort-sammenlign"):
        st.html(stil.tittelrad("Sammenlign med et annet selskap",
                               "Søk på navn, ticker eller org.nr. Samme regnskapsår og regnskapstype brukes når "
                               "det finnes.", forklar("sammenlign"), luft_under=True))
        tekst = sokefelt("mot_inn", "mot", "Sammenlign med … (navn, ticker eller org.nr)")
        if not tekst:
            if "mot" in st.query_params:
                del st.query_params["mot"]
            return
        try:
            orgnr_b = api.valider_orgnr(tekst)
        except api.UgyldigOrgnr as feil:
            st.error(str(feil), icon=":material/pin:")
            return
        if orgnr_b == enhet_a.get("orgnr"):
            st.info("Det er det samme selskapet. Skriv inn et annet org.nr.", icon=":material/info:")
            return
        st.query_params["mot"] = orgnr_b
        try:
            with st.spinner("Henter selskapet du vil sammenligne med …"):
                enhet_b = api.tolk_enhet(hent_enhet(orgnr_b))
                raa_b = hent_regnskap(orgnr_b)
        except api.IngenRegnskap as feil:
            st.warning(str(feil), icon=":material/inbox:")
            return
        except api.BrregFeil as feil:
            st.error(str(feil), icon=":material/search_off:")
            return
        std_b, typer_b, eier_b = standard_regnskap(raa_b)
        if std_b is None:
            st.warning("Fant ikke et gjenkjennelig regnskap for dette selskapet.", icon=":material/inbox:")
            return
        _, typer_a, eier_a = standard_regnskap(raa_a)
        type_a, type_b = sammenligningstyper(valgt_type, typer_a, eier_a, typer_b, std_b, eier_b)
        regnskaper_a = api.velg_regnskap(raa_a, type_a)
        a = next((r for r in regnskaper_a if r["aar"] == valgt_aar), regnskaper_a[0])
        regnskaper_b = api.velg_regnskap(raa_b, type_b)
        b = next((r for r in regnskaper_b if r["aar"] == a["aar"]), regnskaper_b[0])

        navn_a, navn_b = kortnavn(enhet_a.get("navn")), kortnavn(enhet_b.get("navn"))
        typenavn = {"SELSKAP": "selskap", "KONSERN": "konsern"}
        overskrift = ["", f"{navn_a} · {a['aar']} {typenavn.get(type_a, '')}".strip(),
                      f"{navn_b} · {b['aar']} {typenavn.get(type_b, '')}".strip()]
        rader: List[List[str]] = [["Hovedtall"]]
        for navn, felt in [("Driftsinntekter", "sum_driftsinntekter"), ("Driftsresultat", "driftsresultat"),
                           ("Årsresultat", "aarsresultat"), ("Sum eiendeler", "sum_eiendeler"),
                           ("Egenkapital", "egenkapital")]:
            rader.append([navn, fmt.belop(a["tall"].get(felt), a["valuta"]), fmt.belop(b["tall"].get(felt), b["valuta"])])
        nt_a, nt_b = beregn_nokkeltall(a["tall"]), {n.kode: n for n in beregn_nokkeltall(b["tall"])}
        sterke: List[Tuple[int, int]] = []
        gruppe = None
        for x in nt_a:
            y = nt_b[x.kode]
            if x.gruppe != gruppe:
                gruppe = x.gruppe
                rader.append([gruppe])
            celler = []
            for n, r in ((x, a), (y, b)):
                t = fmt.nokkeltall(n.verdi, n.enhet, r["valuta"])
                celler.append("ikke meningsfull" if n.verdi is None and n.merknad and "meningsfull" in n.merknad else t)
            vinner = sterkest(x.kode, x.verdi, y.verdi)
            if vinner is not None:
                sterke.append((len(rader), 1 + vinner))
            rader.append([x.navn] + celler)
        grupperader = [i for i, rad in enumerate(rader) if len(rad) == 1]
        st.html(stil.tabell(overskrift, rader, None, grupperader, sterke))

        merk = ["Grønt = sterkest på nøkkeltallet (lavest for gjeldsgrad). Arbeidskapital har ingen fasit, "
                "fordi den avhenger av hvor stort selskapet er."]
        if b["aar"] != a["aar"]:
            merk.append(f"{navn_b} har ikke regnskap for {a['aar']} i API-et, så {b['aar']} brukes.")
        if type_a == type_b == "KONSERN" and (eier_a or eier_b) and valgt_type != "KONSERN":
            eier = " og ".join(n for n, e in ((navn_a, eier_a), (navn_b, eier_b)) if e)
            merk.append(f"Begge vises som konsern fordi morselskapet i {eier} er et eierselskap. Da er det "
                        "konsernet som viser driften.")
        elif type_a == type_b == "KONSERN" and eier_b and not eier_a:
            merk.append(f"{navn_b} vises som konsern fordi morselskapet er et eierselskap.")
        elif type_b != type_a:
            merk.append(f"{navn_b} vises som {typenavn.get(type_b, type_b.lower())}"
                        + (" fordi morselskapet er et eierselskap." if eier_b else
                           f" fordi det ikke har {typenavn.get(type_a, type_a.lower())}sregnskap."))
        if b["valuta"] != a["valuta"]:
            merk.append(f"Beløpene er i ulike valutaer ({a['valuta']} og {b['valuta']}). Nøkkeltall i prosent "
                        "og ganger kan sammenlignes direkte.")
        if samlet_status(balansekontroll(b["tall"])) == "avvik":
            merk.append(f"Balansen i registerets tall for {navn_b} går ikke opp, så balansebaserte nøkkeltall "
                        "kan være misvisende.")
        st.html("".join(f'<p class="rd-merk">{stil.e(m)}</p>' for m in merk))

        # Graf: prosent-nøkkeltallene side om side.
        koder = [k for k in SAMMENLIGN_PROSENT]
        navn_nt = {n.kode: n.navn for n in nt_a}
        va = {n.kode: n.verdi for n in nt_a}
        vb = {k: n.verdi for k, n in nt_b.items()}
        if any(va.get(k) is not None or vb.get(k) is not None for k in koder):
            fig = go.Figure()
            for i, (navn, verdier) in enumerate(((navn_a, va), (navn_b, vb))):
                y = [None if verdier.get(k) is None else verdier[k] * 100 for k in koder]
                fig.add_bar(name=navn, x=[navn_nt[k] for k in koder], y=y,
                            marker=dict(color=f["serie"][i], line=dict(color=f["flate"], width=2),
                                        cornerradius=5),
                            customdata=[fmt.prosent(verdier.get(k)) for k in koder],
                            hovertemplate=f"<b>{stil.e(navn)}</b><br>%{{x}}: %{{customdata}}<extra></extra>")
            fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
            grafoppsett(fig, f, "%", hoyde=320)
            st.plotly_chart(fig, theme=None, config={"displayModeBar": False})


def vis_ordliste(r: Dict[str, Any]) -> None:
    """Alle forklaringene samlet, for den som vil lese alt på ett sted."""
    with st.expander("Ordliste – hva betyr tallene?", icon=":material/menu_book:"):
        innslag = [forklaringer.hent(k) for k in forklaringer.ORDLISTE_REKKEFOLGE]
        innslag += [(n.navn, [n.forklaring, f"Formel: {n.formel}"]) for n in beregn_nokkeltall(r["tall"])]
        st.html(stil.ordliste(innslag))


def vis_detaljer(enhet: Dict[str, Any], orgnr: str, siste: Dict[str, Any], forrige: Optional[Dict[str, Any]],
                 regnskaper: List[Dict[str, Any]], til_og_med_valgt: List[Dict[str, Any]], valgt: str,
                 aar_liste: List[int], kontroller: list, status: str) -> None:
    st.html(stil.seksjon("Detaljer"))
    vis_ordliste(siste)
    vis_tabell(regnskaper[:3])
    if status not in ("avvik", "mangler"):
        vis_balansedetaljer(siste, kontroller, status)

    st.html(stil.seksjon("Last ned"))
    with st.container(key="kort-last"):
        st.html(stil.tittelrad("Excel med formler", f"Regnskapet for {siste['aar']}"
                               + (f" og {forrige['aar']}" if forrige else "")
                               + " med nøkkeltallene som ekte Excel-formler, så du kan se og endre "
                                 "utregningene selv.", forklar("excel"), luft_under=True))
        st.download_button(
            "Last ned Excel",
            data=lag_excel(enhet, til_og_med_valgt),
            file_name=f"regnskap_{orgnr}_{siste['aar']}_{valgt.lower()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary", icon=":material/download:",
        )
    pdf_aar = hent_pdf_aar(orgnr)
    if pdf_aar:
        st.html('<div class="rd-kort" style="margin-top:14px">'
                + stil.tittelrad("Årsregnskap som PDF", f"Kopi av det innsendte årsregnskapet fra "
                                 f"Brønnøysundregistrene, {pdf_aar[-1]}–{pdf_aar[0]}. Her finner du også årene "
                                 f"før {aar_liste[-1]}.", forklar("pdf"))
                + stil.pdf_lenker([(a, api.pdf_lenke(orgnr, a)) for a in pdf_aar]) + "</div>")


def sett_sok(nokkel: str, verdi: str) -> None:
    st.session_state[nokkel] = verdi


def velg_eksempel(orgnr: str) -> None:
    sett_sok("sok_inn", borsliste.etikett_for_orgnr(orgnr) or orgnr)


# Eget søkefelt (komponenter/sok/index.html): vanlig tekstfelt med forslag fra Oslo Børs-lista.
# Streamlits selectbox søker «fuzzy» (viser treff som ikke inneholder teksten) og lar seg ikke tømme.
_sok_komponent = components.declare_component("sokefelt", path=str(MAPPE / "komponenter" / "sok"))


def sokefelt(nokkel: str, query: str, plassholder: str) -> Optional[str]:
    """Søkefelt med Oslo Børs-selskapene som forslag. Godtar også et hvilket som helst org.nr.

    Valgt tekst ligger i ``st.session_state[nokkel]`` (forslagsknappene kan sette den). Returnerer
    teksten som skal tolkes som org.nr, eller None (og viser da selv en melding hvis det trengs)."""
    if nokkel not in st.session_state:
        q = st.query_params.get(query, "")
        st.session_state[nokkel] = (borsliste.etikett_for_orgnr(q) or q) or None
    # Komponenten husker siste svar (i session_state under sin key); et nytt løpenummer betyr at brukeren
    # har valgt noe nytt. Leses FØR komponenten tegnes, så den får den nye verdien og ikke den gamle.
    svar = st.session_state.get(f"komp-{nokkel}")
    if isinstance(svar, dict) and svar.get("n") != st.session_state.get(f"{nokkel}-n"):
        st.session_state[f"{nokkel}-n"] = svar.get("n")
        st.session_state[nokkel] = (svar.get("tekst") or "").strip() or None
    _sok_komponent(forslag=borsliste.forslag(), verdi=st.session_state.get(nokkel) or "",
                   plassholder=plassholder, farger=stil.TOKENS[modus()], font=stil.FONT,
                   key=f"komp-{nokkel}", default=None)
    tekst = st.session_state.get(nokkel)
    art, verdi = borsliste.tolk(tekst)
    if art == "orgnr":
        return verdi
    if art == "utenlandsk":
        st.info(f"{borsliste.visningsnavn(verdi)} er notert på {verdi['marked']}, men registrert i "
                f"{borsliste.land(verdi)}. Selskapet har derfor ikke årsregnskap i Regnskapsregisteret."
                if verdi["utenlandsk"] else
                f"Fant ikke norsk org.nr for {borsliste.visningsnavn(verdi)}. Søk med org.nr i stedet.",
                icon=":material/public:")
    elif art == "flere":
        st.html('<p class="rd-forslag-tittel">Mente du …</p>')
        with st.container(horizontal=True, gap="small", key=f"flere-{nokkel}"):
            for s in verdi[:12]:
                st.button(borsliste.visningsnavn(s), key=f"eks-{nokkel}-{s['isin']}", on_click=sett_sok,
                          args=(nokkel, borsliste.etikett(s)), help=", ".join(s["tickere"]))
    elif art == "ukjent":
        st.warning(f"Fant ikke «{tekst}» blant selskapene på Oslo Børs. Andre selskaper kan du søke opp "
                   "med org.nr (9 siffer).", icon=":material/search_off:")
    return None


# ---------------------------------------------------------------------------
# Hovedflyt
# ---------------------------------------------------------------------------
def main() -> None:
    m = modus()
    st.html(stil.css(m))
    st.html(stil.topp())

    with st.container(key="sok"):
        tekst = sokefelt("sok_inn", "orgnr", "Søk på selskap på Oslo Børs, ticker eller org.nr")

    if not st.session_state.get("sok_inn"):
        for q in ("orgnr", "mot"):                 # søket er tømt: fjern det fra lenken også
            if q in st.query_params:
                del st.query_params[q]
        st.html('<p class="rd-forslag-tittel">Prøv et kjent selskap</p>')
        with st.container(horizontal=True, gap="small", key="forslag"):
            for navn, nr in EKSEMPLER:
                st.button(navn, key=f"eks-{nr}", on_click=velg_eksempel, args=(nr,), help=f"Org.nr {nr}")
        st.html(stil.bunn())
        return
    if tekst is None:
        if "orgnr" in st.query_params:
            del st.query_params["orgnr"]
        st.html(stil.bunn())
        return

    try:
        orgnr = api.valider_orgnr(tekst)
    except api.UgyldigOrgnr as feil:
        st.error(str(feil), icon=":material/pin:")
        return
    st.query_params["orgnr"] = orgnr

    try:
        with st.spinner("Henter selskapsinfo …"):
            enhet_raa = hent_enhet(orgnr)
            enhet = api.tolk_enhet(enhet_raa)
    except api.BrregFeil as feil:
        st.error(str(feil), icon=":material/search_off:")
        return

    vis_selskapskort(enhet)

    try:
        with st.spinner("Henter årsregnskap …"):
            raa = hent_regnskap(orgnr)
    except api.IngenRegnskap as feil:
        st.warning(str(feil), icon=":material/inbox:")
        # Banker o.l. har ikke tall i API-et, men kan ha årsregnskapet som PDF.
        pdf_aar = hent_pdf_aar(orgnr)
        if pdf_aar:
            st.html('<div class="rd-kort" style="margin-top:14px">'
                    + stil.tittelrad("Årsregnskap som PDF", "Kopi av det innsendte årsregnskapet fra "
                                     "Brønnøysundregistrene.", forklar("pdf"))
                    + stil.pdf_lenker([(a, api.pdf_lenke(orgnr, a)) for a in pdf_aar]) + "</div>")
        st.html(stil.bunn())
        return
    except api.BrregFeil as feil:
        st.error(str(feil), icon=":material/cloud_off:")
        return

    standard, typer, eierselskap = standard_regnskap(raa)
    if standard is None:
        st.warning("Regnskapsregisteret returnerte data, men uten gjenkjennelig regnskapstype.",
                   icon=":material/inbox:")
        return
    valgt = standard
    with st.container(horizontal=True, gap="medium", key="valg", vertical_alignment="center"):
        if len(typer) > 1:
            with st.container(key="typevalg"):
                navn = {"SELSKAP": "Selskap", "KONSERN": "Konsern"}
                # Egen nøkkel per org.nr, så standardvalget gjelder hvert nytt selskap.
                svar = st.segmented_control("Regnskap", typer, default=standard, key=f"regnskapstype-{orgnr}",
                                            format_func=lambda x: navn.get(x, x.title()),
                                            label_visibility="collapsed",
                                            help="Selskap = morselskapet alene. Konsern = hele gruppen.")
                valgt = svar or standard
            st.html(forklar("selskap_konsern", "venstre"))
        regnskaper = api.velg_regnskap(raa, valgt)
        aar_liste = [r["aar"] for r in regnskaper]
        valgt_aar = aar_liste[0]
        if len(aar_liste) > 1:
            with st.container(key="aarvalg"):
                if st.session_state.get("regnskapsaar") not in aar_liste:
                    st.session_state["regnskapsaar"] = aar_liste[0]
                svar_aar = st.segmented_control("Regnskapsår", aar_liste, key="regnskapsaar",
                                                label_visibility="collapsed",
                                                help="Regnskapsregisterets API har tallene for de siste årene. "
                                                     "Eldre år finnes som PDF nederst på siden.")
                valgt_aar = svar_aar or aar_liste[0]
            st.html(forklar("regnskapsaar", "venstre"))

    siste = next(r for r in regnskaper if r["aar"] == valgt_aar)
    forrige = next((r for r in regnskaper if r["aar"] == valgt_aar - 1), None)
    til_og_med_valgt = [r for r in regnskaper if r["aar"] <= valgt_aar]    # nyeste først
    kontroller = balansekontroll(siste["tall"])
    status = samlet_status(kontroller)

    vis_statuslinje(siste, status)
    if eierselskap:
        if valgt == "KONSERN":
            tekst = ("Viser <b>konsern</b> fordi morselskapet i hovedsak er et eierselskap: driften ligger i "
                     "datterselskapene, og morselskapets inntekter er mest finansinntekter (utbytte, "
                     "konsernbidrag og renter). Velg <i>Selskap</i> for å se morselskapet alene.")
        else:
            tekst = ("Morselskapet er i hovedsak et <b>eierselskap</b>: finansinntektene (utbytte, konsernbidrag og "
                     "renter fra datterselskaper) er større enn driftsinntektene. Velg <i>Konsern</i> for å se driften.")
        st.html(f'<p class="rd-merk" style="margin-top:10px;font-size:.8125rem">{tekst}</p>')
    if status == "avvik":
        hoved = next((k for k in kontroller if k.status == "avvik"), None)
        diff = f" (differanse {fmt.belop(abs(hoved.differanse), siste['valuta'])})" if hoved and hoved.differanse else ""
        lenke = f"[innsendte årsregnskapet for {siste['aar']} (PDF)]({api.pdf_lenke(orgnr, siste['aar'])})" \
            if siste["aar"] in hent_pdf_aar(orgnr) else "innsendte årsregnskapet på brreg.no"
        st.warning(
            f"**Balansen i Regnskapsregisterets tall for {siste['aar']} går ikke opp**{diff}. "
            "Det tyder på at noen tall er registrert feil hos Brønnøysundregistrene. Nøkkeltall som bruker "
            f"balansen (rentabilitet, likviditet, soliditet) kan derfor være misvisende. Sammenlign med det {lenke}.",
            icon=":material/error:")
    if status in ("avvik", "mangler"):
        vis_balansedetaljer(siste, kontroller, status)

    eierselskap_alene = eierselskap and valgt == "SELSKAP"
    hendelser = api.tolk_hendelser(enhet_raa, hent_roller(orgnr))
    f = stil.graffarger(m)
    # En delt sammenligningslenke (?mot=…) åpner rett på Sammenlign.
    fane_oversikt, fane_nt, fane_grafer, fane_utv, fane_sml, fane_detaljer = st.tabs(
        ["Oversikt", "Nøkkeltall", "Grafer", "Utvikling", "Sammenlign", "Detaljer"],
        default="Sammenlign" if st.query_params.get("mot") else "Oversikt")

    with fane_oversikt:
        vis_oversikt(siste, forrige, eierselskap_alene, status == "avvik")
        vis_hovedtall(siste, forrige)
        vis_endringer(siste, forrige, hendelser)

    with fane_nt:
        vis_nokkeltall(siste, forrige)

    with fane_grafer:
        st.html(stil.seksjon("Grafer", f"Regnskapsår {siste['aar']}"))
        g1, g2 = st.columns(2, gap="small")
        with g1, st.container(key="kort-balanse"):
            graf_balanse(siste, f)
        with g2, st.container(key="kort-resultat"):
            graf_resultat(siste, f)

    with fane_utv:
        if len(regnskaper) < 2:
            st.html(stil.seksjon("Utvikling"))
            st.info("Regnskapsregisteret har bare ett år for dette selskapet. Eldre år finnes som PDF under "
                    "Detaljer.", icon=":material/info:")
        vis_utvikling(regnskaper, valgt_aar, f)

    with fane_sml:
        vis_sammenligning(enhet, raa, valgt, valgt_aar, f)

    with fane_detaljer:
        vis_detaljer(enhet, orgnr, siste, forrige, regnskaper, til_og_med_valgt, valgt, aar_liste, kontroller,
                     status)

    st.html(stil.bunn())


main()
