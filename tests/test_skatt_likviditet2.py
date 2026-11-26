"""Tester for effektiv skattesats og likviditetsgrad 2."""
import io
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

import brreg_api as api
from beregninger import beregn_nokkeltall, varelager
from excel_eksport import lag_excel

DATA = Path(__file__).parent / "data"


def nt(tall, kode):
    return next(n for n in beregn_nokkeltall(tall) if n.kode == kode)


@pytest.fixture
def t():
    return {
        "sum_driftsinntekter": 1000.0, "sum_driftskostnad": 800.0, "driftsresultat": 200.0,
        "finansinntekter": 50.0, "finanskostnader": 30.0, "netto_finans": 20.0,
        "resultat_for_skatt": 220.0, "skattekostnad": 48.4, "aarsresultat": 171.6,
        "anleggsmidler": 1500.0, "omlopsmidler": 500.0, "varer": 100.0, "fordringer": 250.0,
        "bankinnskudd": 150.0, "sum_eiendeler": 2000.0,
        "egenkapital": 800.0, "innskutt_egenkapital": 300.0, "opptjent_egenkapital": 500.0,
        "langsiktig_gjeld": 950.0, "kortsiktig_gjeld": 250.0,
        "sum_gjeld": 1200.0, "sum_egenkapital_gjeld": 2000.0,
    }


# --- Effektiv skattesats ------------------------------------------------------
def test_skattesats(t):
    assert nt(t, "skattesats").verdi == pytest.approx(0.22)


def test_skattesats_ikke_meningsfull_ved_underskudd(t):
    t["resultat_for_skatt"], t["skattekostnad"] = -100.0, -22.0
    n = nt(t, "skattesats")
    assert n.verdi is None and "meningsfull" in n.merknad


def test_skattesats_mangler(t):
    t["skattekostnad"] = None
    assert nt(t, "skattesats").verdi is None


# --- Likviditetsgrad 2 --------------------------------------------------------
def test_likviditetsgrad2(t):
    assert nt(t, "likviditetsgrad2").verdi == pytest.approx((500 - 100) / 250)


def test_likviditetsgrad2_uten_varelager_naar_resten_gaar_opp(t):
    t["varer"], t["fordringer"] = None, 350.0          # 350 + 150 = 500 = omløpsmidler
    assert varelager(t) == (0.0, True)
    n = nt(t, "likviditetsgrad2")
    assert n.verdi == pytest.approx(2.0) and "ikke varelager" in n.merknad


def test_likviditetsgrad2_mangler_naar_varer_ikke_kan_utledes(t):
    t["varer"], t["omlopsmidler"] = None, 5000.0         # 250 + 150 = 400, langt fra 5 000
    assert varelager(t) == (None, False)
    n = nt(t, "likviditetsgrad2")
    assert n.verdi is None and "ikke oppgitt" in n.merknad


# --- Excel-formlene ------------------------------------------------------------
def test_nye_formler_i_excel():
    raa = json.loads((DATA / "equinor_regnskap.json").read_text())
    enhet = api.tolk_enhet(json.loads((DATA / "equinor_enhet.json").read_text()))
    ws = load_workbook(io.BytesIO(lag_excel(enhet, api.velg_regnskap(raa, "SELSKAP"))))["Nøkkeltall"]
    rader = {ws.cell(r, 2).value: r for r in range(5, ws.max_row + 1)}
    for navn in ("Effektiv skattesats", "Likviditetsgrad 2"):
        formel = ws.cell(rader[navn], 4).value
        assert formel.startswith("=IF(") and "Regnskap!" in formel
        assert formel.count("(") == formel.count(")")
