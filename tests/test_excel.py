"""Tester at Excel-fila har ekte formler og viser «mangler» riktig."""
import io
import json
from pathlib import Path

from openpyxl import load_workbook

import brreg_api as api
from excel_eksport import lag_excel

DATA = Path(__file__).parent / "data"


def lag_bok(regnskapstype="KONSERN"):
    raa = json.loads((DATA / "equinor_regnskap.json").read_text())
    enhet = api.tolk_enhet(json.loads((DATA / "equinor_enhet.json").read_text()))
    return load_workbook(io.BytesIO(lag_excel(enhet, api.velg_regnskap(raa, regnskapstype))))


def test_ark_finnes():
    assert lag_bok().sheetnames == ["Regnskap", "Nøkkeltall", "Balansekontroll", "Om"]


def test_nokkeltall_er_formler():
    ws = lag_bok()["Nøkkeltall"]
    rader = {ws.cell(r, 2).value: r for r in range(5, ws.max_row + 1)}
    assert len(rader) == 9
    driftsmargin = ws.cell(rader["Driftsmargin"], 4).value
    assert driftsmargin.startswith("=IF(")
    assert "Regnskap!" in driftsmargin and "/" in driftsmargin
    # Kolonnen ved siden av viser formelteksten
    assert ws.cell(rader["Driftsmargin"], 6).value.startswith("=FORMULATEXT(")


def test_formel_peker_paa_riktige_celler():
    wb = lag_bok()
    reg, ws = wb["Regnskap"], wb["Nøkkeltall"]
    rad_for = {reg.cell(r, 1).value: r for r in range(1, reg.max_row + 1)}
    formel = next(ws.cell(r, 4).value for r in range(5, ws.max_row + 1)
                  if ws.cell(r, 2).value == "Likviditetsgrad 1")
    assert f"Regnskap!$B${rad_for['Omløpsmidler']}" in formel
    assert f"Regnskap!$B${rad_for['Kortsiktig gjeld']}" in formel


def test_manglende_tall_skrives_som_mangler():
    reg = lag_bok("SELSKAP")["Regnskap"]
    rad = next(r for r in range(1, reg.max_row + 1)
               if (reg.cell(r, 1).value or "").strip() == "herav investeringer")
    assert reg.cell(rad, 2).value == "mangler"


def test_balansekontroll_formler():
    ws = lag_bok()["Balansekontroll"]
    assert ws.cell(5, 4).value.startswith("=IF(")
    assert "AVVIK" in ws.cell(5, 5).value
