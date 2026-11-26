"""Lager en Excel-fil der nøkkeltallene er ekte, synlige Excel-formler.

Arkene:
- «Regnskap»      – tallene fra Regnskapsregisteret (inndata)
- «Nøkkeltall»    – formler som peker på «Regnskap», og formelteksten ved siden av
- «Balansekontroll» – formler som sjekker at balansen går opp
- «Om»            – selskapsinfo og kilde
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from beregninger import ABSOLUTT_TOLERANSE, RELATIV_TOLERANSE, beregn_nokkeltall

MANGLER = "mangler"

# Rekkefølge og etiketter for inndata-arket.
POSTER = [
    ("Resultatregnskap", None),
    ("Salgsinntekter", "salgsinntekter"),
    ("Sum driftsinntekter", "sum_driftsinntekter"),
    ("Sum driftskostnader", "sum_driftskostnad"),
    ("Driftsresultat", "driftsresultat"),
    ("Finansinntekter", "finansinntekter"),
    ("Finanskostnader", "finanskostnader"),
    ("  herav annen rentekostnad", "annen_rentekostnad"),
    ("  herav rentekostnad til konsernselskap", "rentekostnad_konsern"),
    ("Netto finans", "netto_finans"),
    ("Ordinært resultat før skatt", "resultat_for_skatt"),
    ("Skattekostnad", "skattekostnad"),
    ("Årsresultat", "aarsresultat"),
    ("Eiendeler", None),
    ("Anleggsmidler", "anleggsmidler"),
    ("Omløpsmidler", "omlopsmidler"),
    ("  herav varer", "varer"),
    ("  herav fordringer", "fordringer"),
    ("  herav investeringer", "investeringer"),
    ("  herav bankinnskudd og kontanter", "bankinnskudd"),
    ("Sum eiendeler", "sum_eiendeler"),
    ("Egenkapital og gjeld", None),
    ("Innskutt egenkapital", "innskutt_egenkapital"),
    ("Opptjent egenkapital", "opptjent_egenkapital"),
    ("Sum egenkapital", "egenkapital"),
    ("Langsiktig gjeld", "langsiktig_gjeld"),
    ("Kortsiktig gjeld", "kortsiktig_gjeld"),
    ("Sum gjeld", "sum_gjeld"),
    ("Sum egenkapital og gjeld", "sum_egenkapital_gjeld"),
]

FET = Font(bold=True)
OVERSKRIFT = Font(bold=True, size=14)
GRUPPE_FYLL = PatternFill("solid", fgColor="EEF3FA")
FORMEL_FONT = Font(name="Consolas", color="52514E")
BELOP_FORMAT = "#,##0;-#,##0"
FORMATER = {"prosent": "0.0%", "ganger": "0.00", "belop": BELOP_FORMAT}


def _er_tall(*refs: str) -> str:
    return "AND(" + ",".join(f"ISNUMBER({r})" for r in refs) + ")"


def _formel(kode: str, ref: Dict[str, str]) -> str:
    """Excel-formelen for et nøkkeltall. ``ref`` gir celleadresse per felt."""
    r = ref
    if kode == "driftsmargin":
        a, b = r["driftsresultat"], r["sum_driftsinntekter"]
        return f'=IF({_er_tall(a, b)},IF({b}=0,"{MANGLER}",{a}/{b}),"{MANGLER}")'
    if kode == "resultatmargin":
        a, b = r["resultat_for_skatt"], r["sum_driftsinntekter"]
        return f'=IF({_er_tall(a, b)},IF({b}=0,"{MANGLER}",{a}/{b}),"{MANGLER}")'
    if kode == "totalrentabilitet":
        # Lærebokformel når rentekostnader er oppgitt, ellers tilnærmingen (som i beregninger.py).
        a, f, b = r["driftsresultat"], r["finansinntekter"], r["sum_eiendeler"]
        rfs, r1, r2 = r["resultat_for_skatt"], r["annen_rentekostnad"], r["rentekostnad_konsern"]
        laerebok = f'IF({_er_tall(rfs, b)},IF({b}=0,"{MANGLER}",({rfs}+SUM({r1},{r2}))/{b}),"{MANGLER}")'
        tilnaerming = f'IF({_er_tall(a, f, b)},IF({b}=0,"{MANGLER}",({a}+{f})/{b}),"{MANGLER}")'
        return f"=IF(OR(ISNUMBER({r1}),ISNUMBER({r2})),{laerebok},{tilnaerming})"
    if kode == "egenkapitalrentabilitet":
        a, ek = r["aarsresultat"], r["egenkapital"]
        return (f'=IF({_er_tall(a, ek)},IF({ek}<0,"ikke meningsfull",'
                f'IF({ek}=0,"{MANGLER}",{a}/{ek})),"{MANGLER}")')
    if kode == "likviditetsgrad1":
        a, b = r["omlopsmidler"], r["kortsiktig_gjeld"]
        return f'=IF({_er_tall(a, b)},IF({b}=0,"{MANGLER}",{a}/{b}),"{MANGLER}")'
    if kode == "arbeidskapital":
        a, b = r["omlopsmidler"], r["kortsiktig_gjeld"]
        return f'=IF({_er_tall(a, b)},{a}-{b},"{MANGLER}")'
    if kode == "egenkapitalandel":
        ek, b = r["egenkapital"], r["sum_egenkapital_gjeld"]
        return f'=IF({_er_tall(ek, b)},IF({b}=0,"{MANGLER}",{ek}/{b}),"{MANGLER}")'
    if kode == "gjeldsgrad":
        g, ek = r["sum_gjeld"], r["egenkapital"]
        return (f'=IF({_er_tall(g, ek)},IF({ek}<0,"ikke meningsfull",'
                f'IF({ek}=0,"{MANGLER}",{g}/{ek})),"{MANGLER}")')
    if kode == "rentedekningsgrad":
        rfs, r1, r2 = r["resultat_for_skatt"], r["annen_rentekostnad"], r["rentekostnad_konsern"]
        renter = f"SUM({r1},{r2})"
        return (f'=IF(AND(OR(ISNUMBER({r1}),ISNUMBER({r2})),ISNUMBER({rfs})),'
                f'IF({renter}=0,"ingen renter",({rfs}+{renter})/{renter}),"{MANGLER}")')
    if kode == "skattesats":
        s, rfs = r["skattekostnad"], r["resultat_for_skatt"]
        return f'=IF({_er_tall(s, rfs)},IF({rfs}<=0,"ikke meningsfull",{s}/{rfs}),"{MANGLER}")'
    if kode == "likviditetsgrad2":
        # Mangler varelageret, men resten av omløpspostene utgjør hele omløpsmidlene, er varelageret 0.
        o, v, k = r["omlopsmidler"], r["varer"], r["kortsiktig_gjeld"]
        f, i, b = r["fordringer"], r["investeringer"], r["bankinnskudd"]
        uten_varer = (f'IF(AND(COUNT({f},{i},{b})>0,ABS({o}-SUM({f},{i},{b}))<=MAX({ABSOLUTT_TOLERANSE:.0f},'
                      f'{RELATIV_TOLERANSE}*ABS({o}))),{o}/{k},"{MANGLER}")')
        return (f'=IF({_er_tall(o, k)},IF({k}=0,"{MANGLER}",IF(ISNUMBER({v}),({o}-{v})/{k},{uten_varer})),'
                f'"{MANGLER}")')
    if kode == "altman_z":
        o, k, d, ek = r["omlopsmidler"], r["kortsiktig_gjeld"], r["driftsresultat"], r["egenkapital"]
        g, ta, op, inn = r["sum_gjeld"], r["sum_eiendeler"], r["opptjent_egenkapital"], r["innskutt_egenkapital"]
        opptjent = f"IF(ISNUMBER({op}),{op},{ek}-{inn})"
        return (f'=IF(AND({_er_tall(o, k, d, ek, g, ta)[4:-1]},OR(ISNUMBER({op}),ISNUMBER({inn}))),'
                f'IF(OR({ta}=0,{g}=0),"{MANGLER}",6.56*({o}-{k})/{ta}+3.26*{opptjent}/{ta}'
                f'+6.72*{d}/{ta}+1.05*{ek}/{g}),"{MANGLER}")')
    raise ValueError(f"Ukjent nøkkeltall: {kode}")


def _bredder(ws, bredder: List[int]) -> None:
    for i, b in enumerate(bredder, start=1):
        ws.column_dimensions[get_column_letter(i)].width = b


def lag_excel(enhet: Dict[str, Any], regnskaper: List[Dict[str, Any]]) -> bytes:
    """Bygger arbeidsboka. ``regnskaper`` er tolkede regnskap, nyeste først.

    Det nyeste året og (hvis det finnes) året før tas med som kolonner.
    """
    aar_liste = regnskaper[:2]
    if not aar_liste:
        raise ValueError("Ingen regnskap å eksportere.")
    valuta = aar_liste[0]["valuta"]
    wb = Workbook()

    # ---------------- Regnskap (inndata) ---------------------------------
    ws = wb.active
    ws.title = "Regnskap"
    ws["A1"] = f"{enhet.get('navn') or ''} – årsregnskap ({aar_liste[0]['regnskapstype'].lower()})"
    ws["A1"].font = OVERSKRIFT
    ws["A2"] = f"Beløp i {valuta}. Kilde: Regnskapsregisteret (data.brreg.no). «{MANGLER}» = ikke oppgitt."
    ws.append([])
    ws.append(["Post"] + [str(r["aar"]) for r in aar_liste])
    for c in ws[4]:
        c.font = FET

    # adresse[felt][kolonneindeks] -> "Regnskap!$B$7"
    adresse: Dict[str, List[str]] = {}
    for etikett, felt in POSTER:
        rad = ws.max_row + 1
        ws.cell(rad, 1, etikett)
        if felt is None:
            ws.cell(rad, 1).font = FET
            for kol in range(1, 2 + len(aar_liste)):
                ws.cell(rad, kol).fill = GRUPPE_FYLL
            continue
        if felt.startswith("sum") or felt in ("driftsresultat", "aarsresultat", "egenkapital"):
            ws.cell(rad, 1).font = FET
        adresse[felt] = []
        for i, r in enumerate(aar_liste):
            kol = 2 + i
            verdi: Optional[float] = r["tall"].get(felt)
            celle = ws.cell(rad, kol, MANGLER if verdi is None else verdi)
            celle.number_format = BELOP_FORMAT
            celle.alignment = Alignment(horizontal="right")
            adresse[felt].append(f"Regnskap!${get_column_letter(kol)}${rad}")
    _bredder(ws, [38] + [20] * len(aar_liste))
    ws.freeze_panes = "B5"

    # ---------------- Nøkkeltall (formler) -------------------------------
    wn = wb.create_sheet("Nøkkeltall")
    wn["A1"] = "Nøkkeltall – regnes ut av Excel fra arket «Regnskap»"
    wn["A1"].font = OVERSKRIFT
    wn["A2"] = "Kolonnen «Excel-formel» viser nøyaktig hvilken formel som står i cellen til venstre."
    wn.append([])
    overskrift = ["Gruppe", "Nøkkeltall", "Formel"] + [str(r["aar"]) for r in aar_liste] + \
                 ["Excel-formel (" + str(aar_liste[0]["aar"]) + ")", "Forklaring"]
    wn.append(overskrift)
    for c in wn[4]:
        c.font = FET

    nokkeltall = beregn_nokkeltall(aar_liste[0]["tall"])  # brukes for tekster og enhet
    for nt in nokkeltall:
        rad = wn.max_row + 1
        wn.cell(rad, 1, nt.gruppe)
        wn.cell(rad, 2, nt.navn).font = FET
        wn.cell(rad, 3, nt.formel)
        for i in range(len(aar_liste)):
            ref = {felt: adr[i] for felt, adr in adresse.items()}
            celle = wn.cell(rad, 4 + i, _formel(nt.kode, ref))
            celle.number_format = FORMATER[nt.enhet]
            celle.alignment = Alignment(horizontal="right")
        siste_kol = 4 + len(aar_liste)
        forste_verdi = f"{get_column_letter(4)}{rad}"
        wn.cell(rad, siste_kol, f"=FORMULATEXT({forste_verdi})").font = FORMEL_FONT
        tekst = nt.forklaring + (f" {nt.merknad}" if nt.merknad else "")
        wn.cell(rad, siste_kol + 1, tekst).alignment = Alignment(wrap_text=True, vertical="top")
    _bredder(wn, [12, 24, 46] + [14] * len(aar_liste) + [70, 70])
    wn.freeze_panes = "C5"

    # ---------------- Balansekontroll -----------------------------------
    wk = wb.create_sheet("Balansekontroll")
    wk["A1"] = f"Kontroll av balansen ({aar_liste[0]['aar']})"
    wk["A1"].font = OVERSKRIFT
    wk["A2"] = (f"Avvik på inntil {RELATIV_TOLERANSE:.2%} av totalen eller "
                f"{ABSOLUTT_TOLERANSE:,.0f} regnes som avrunding.").replace(",", " ")
    wk.append([])
    wk.append(["Kontroll", "Venstre side", "Høyre side", "Differanse", "Status"])
    for c in wk[4]:
        c.font = FET
    a = {felt: adr[0] for felt, adr in adresse.items()}
    kontroller = [
        ("Sum eiendeler = Sum egenkapital og gjeld",
         a["sum_eiendeler"], a["sum_egenkapital_gjeld"]),
        ("Anleggsmidler + omløpsmidler = Sum eiendeler",
         f"{a['anleggsmidler']}+{a['omlopsmidler']}", a["sum_eiendeler"]),
        ("Egenkapital + gjeld = Sum egenkapital og gjeld",
         f"{a['egenkapital']}+{a['sum_gjeld']}", a["sum_egenkapital_gjeld"]),
        ("Langsiktig + kortsiktig gjeld = Sum gjeld",
         f"{a['langsiktig_gjeld']}+{a['kortsiktig_gjeld']}", a["sum_gjeld"]),
    ]
    for navn, venstre, hoyre in kontroller:
        rad = wk.max_row + 1
        refs = [x for x in venstre.split("+")] + [hoyre]
        wk.cell(rad, 1, navn)
        wk.cell(rad, 2, f'=IF({_er_tall(*refs)},{venstre},"{MANGLER}")').number_format = BELOP_FORMAT
        wk.cell(rad, 3, f'=IF({_er_tall(hoyre)},{hoyre},"{MANGLER}")').number_format = BELOP_FORMAT
        wk.cell(rad, 4, f'=IF(AND(ISNUMBER(B{rad}),ISNUMBER(C{rad})),B{rad}-C{rad},"{MANGLER}")'
                ).number_format = BELOP_FORMAT
        wk.cell(rad, 5, f'=IF(ISNUMBER(D{rad}),IF(D{rad}=0,"OK",IF(ABS(D{rad})<=MAX({ABSOLUTT_TOLERANSE:.0f},'
                        f'{RELATIV_TOLERANSE}*ABS(B{rad})),"OK (avrunding)","AVVIK")),"{MANGLER}")')
    _bredder(wk, [48, 20, 20, 16, 18])

    # ---------------- Om ------------------------------------------------
    wo = wb.create_sheet("Om")
    wo["A1"] = "Om selskapet og dataene"
    wo["A1"].font = OVERSKRIFT
    rader = [
        ("Navn", enhet.get("navn")),
        ("Org.nr", enhet.get("orgnr")),
        ("Organisasjonsform", enhet.get("organisasjonsform")),
        ("Næring", " ".join(x for x in (enhet.get("naering_kode"), enhet.get("naering")) if x) or None),
        ("Adresse", enhet.get("adresse")),
        ("Regnskapstype", aar_liste[0]["regnskapstype"]),
        ("Regnskapsregler", aar_liste[0].get("regnskapsregler")),
        ("Valuta", valuta),
        ("Kilde", "Enhetsregisteret og Regnskapsregisteret, data.brreg.no"),
        ("Laget", date.today().isoformat()),
    ]
    for i, (k, v) in enumerate(rader, start=3):
        wo.cell(i, 1, k).font = FET
        wo.cell(i, 2, v if v not in (None, "") else MANGLER)
    _bredder(wo, [20, 60])

    # Be Excel regne ut alle formler når fila åpnes.
    wb.calculation.fullCalcOnLoad = True

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
