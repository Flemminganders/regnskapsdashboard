"""Tester for sammendraget i klartekst."""
import json
from pathlib import Path

import brreg_api as api
from sammendrag import lag_sammendrag

DATA = Path(__file__).parent / "data"


def regnskap(aar, **tall):
    grunn = {
        "sum_driftsinntekter": 1_000e6, "sum_driftskostnad": 800e6, "driftsresultat": 200e6,
        "finansinntekter": 50e6, "finanskostnader": 30e6, "netto_finans": 20e6,
        "resultat_for_skatt": 220e6, "skattekostnad": 48.4e6, "aarsresultat": 171.6e6,
        "anleggsmidler": 1_500e6, "omlopsmidler": 500e6, "sum_eiendeler": 2_000e6,
        "egenkapital": 800e6, "innskutt_egenkapital": 300e6, "opptjent_egenkapital": 500e6,
        "langsiktig_gjeld": 950e6, "kortsiktig_gjeld": 250e6, "sum_gjeld": 1_200e6, "sum_egenkapital_gjeld": 2_000e6,
    }
    grunn.update(tall)
    return {"aar": aar, "valuta": "NOK", "tall": grunn}


def tekst(s):
    return " ".join(p.tekst for p in s.punkter).replace("\xa0", " ")


def test_vekst_og_overskrift():
    s = lag_sammendrag(regnskap(2025, sum_driftsinntekter=1_100e6), regnskap(2024))
    assert s.overskrift == "Lønnsomt og solid i 2025"
    assert "Driftsinntektene økte 10,0 % til 1,1 mrd. NOK." in tekst(s)
    assert s.punkter[0].tone == "ok"


def test_fra_overskudd_til_underskudd():
    s = lag_sammendrag(regnskap(2025, aarsresultat=-50e6), regnskap(2024))
    assert "fra overskudd på 171,6 mill. NOK til underskudd på 50,0 mill. NOK" in tekst(s)
    assert s.overskrift == "Underskudd i 2025, men solid egenkapital"
    assert any(p.tone == "feil" for p in s.punkter)


def test_storste_driver_nevnes():
    na = regnskap(2025, sum_driftskostnad=900e6, driftsresultat=100e6, resultat_for_skatt=120e6,
                  skattekostnad=26.4e6, aarsresultat=93.6e6)
    s = lag_sammendrag(na, regnskap(2024))
    assert "Størst utslag ga høyere driftskostnader" in tekst(s)


def test_uten_forrige_aar():
    s = lag_sammendrag(regnskap(2025), None)
    assert "Driftsinntektene var 1,0 mrd. NOK." in tekst(s)
    assert "overskudd på 171,6 mill. NOK" in tekst(s)


def test_negativ_egenkapital_og_svak_likviditet():
    na = regnskap(2025, egenkapital=-100e6, kortsiktig_gjeld=600e6, sum_gjeld=2_100e6)
    s = lag_sammendrag(na, None)
    assert "Egenkapitalen er negativ" in tekst(s)
    assert "likviditetsgrad 1: 0,83" in tekst(s)
    assert s.overskrift == "Overskudd i 2025, men negativ egenkapital"


def test_eierselskap_og_balanseavvik():
    s = lag_sammendrag(regnskap(2025), regnskap(2024), eierselskap_alene=True, balanse_avvik=True)
    assert s.punkter[0].tone == "feil" and "går ikke opp" in s.punkter[0].tekst
    assert "eierselskap" in tekst(s) and "Altman" not in tekst(s)


def test_ulik_valuta_sammenlignes_ikke():
    forrige = regnskap(2024)
    forrige["valuta"] = "USD"
    s = lag_sammendrag(regnskap(2025), forrige)
    assert "økte" not in tekst(s) and "falt" not in tekst(s)


def test_equinor_konsern():
    raa = json.loads((DATA / "equinor_regnskap.json").read_text())
    rs = api.velg_regnskap(raa, "KONSERN")
    s = lag_sammendrag(rs[0], rs[1])
    assert s.overskrift and len(s.punkter) >= 5
    assert "skattesats" in tekst(s) and "trolig for lav" in tekst(s)
