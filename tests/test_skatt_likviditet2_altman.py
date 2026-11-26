"""Tester for effektiv skattesats, likviditetsgrad 2 og Altman Z''-scoren."""
import io
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

import brreg_api as api
from beregninger import altman_z, beregn_nokkeltall, opptjent_egenkapital, varelager
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


# --- Altman Z'' ---------------------------------------------------------------
def test_altman_z_fasit(t):
    # X1 = 250/2000, X2 = 500/2000, X3 = 200/2000, X4 = 800/1200
    fasit = 6.56 * 0.125 + 3.26 * 0.25 + 6.72 * 0.1 + 1.05 * (800 / 1200)
    a = altman_z(t)
    assert a.score == pytest.approx(fasit)
    assert sum(b for *_, b in a.ledd) == pytest.approx(fasit)
    assert a.sone == "trygg"                            # 3,01 > 2,6
    assert nt(t, "altman_z").verdi == pytest.approx(fasit)


def test_altman_soner(t):
    a = altman_z(t)
    for score, sone in ((3.0, "trygg"), (2.6, "grå"), (1.1, "grå"), (1.09, "fare"), (-2.0, "fare")):
        a.score = score
        assert a.sone == sone


def test_altman_utleder_opptjent_egenkapital(t):
    t["opptjent_egenkapital"] = None
    assert opptjent_egenkapital(t) == (500.0, True)
    a = altman_z(t)
    assert a.score is not None and "innskutt" in a.merknad


def test_altman_mangler_naar_tall_mangler(t):
    t["sum_gjeld"] = None
    assert altman_z(t).score is None and altman_z(t).sone is None


def test_altman_varsler_naar_nesten_alt_er_innskutt(t):
    t["innskutt_egenkapital"], t["opptjent_egenkapital"] = 790.0, 10.0
    assert "IFRS" in altman_z(t).merknad


# --- Excel-formlene ------------------------------------------------------------
def test_nye_formler_i_excel():
    raa = json.loads((DATA / "equinor_regnskap.json").read_text())
    enhet = api.tolk_enhet(json.loads((DATA / "equinor_enhet.json").read_text()))
    ws = load_workbook(io.BytesIO(lag_excel(enhet, api.velg_regnskap(raa, "SELSKAP"))))["Nøkkeltall"]
    rader = {ws.cell(r, 2).value: r for r in range(5, ws.max_row + 1)}
    for navn in ("Effektiv skattesats", "Likviditetsgrad 2", "Konkursrisiko (Altman Z'')"):
        formel = ws.cell(rader[navn], 4).value
        assert formel.startswith("=IF(") and "Regnskap!" in formel
        assert formel.count("(") == formel.count(")")
