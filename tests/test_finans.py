"""Tester for banker og forsikringsselskaper (tall fra ESEF-årsrapporten)."""
import json
from pathlib import Path

import pytest

import finans
import tolkning

DATA = Path(__file__).parent / "data"


@pytest.fixture
def dnb():
    return finans.tolk_esef(json.loads((DATA / "dnb_esef_utdrag.json").read_text()))


def test_tolk_esef_aar_og_valuta(dnb):
    tall, valuta = dnb
    assert valuta == "NOK"                                 # ikke «NOK/xbrli:shares» fra tall per aksje
    assert {2024, 2025} <= set(tall)
    t = tall[2025]
    assert t["aarsresultat"] == 43_586e6
    assert t["utlan"] == 2_403_340e6 and t["innskudd"] == 1_521_872e6
    assert t["sum_inntekter"] == 90_649e6 and t["tap_utlan"] == 2_803e6


def test_fakta_med_dimensjoner_tas_ikke_med(dnb):
    # Utdraget har noen fakta med ekstra dimensjoner (f.eks. morselskapet alene); de skal ikke overstyre konsernet.
    tall, _ = dnb
    assert tall[2025]["egenkapital"] == 295_855e6


def test_periode_til_aar():
    assert finans._aar_for_periode("2025-01-01T00:00:00/2026-01-01T00:00:00") == (2025, True)
    assert finans._aar_for_periode("2026-01-01T00:00:00") == (2025, False)
    assert finans._aar_for_periode("2025-07-01T00:00:00/2025-10-01T00:00:00") is None   # kvartal


def test_bank_nokkeltall(dnb):
    t = dnb[0][2025]
    assert finans.selskapstype(t) == "bank"
    nt = {n.kode: n.verdi for n in finans.nokkeltall(t)}
    assert nt["kostnadsgrad"] == pytest.approx(34_476 / 90_649)
    assert nt["tap_utlan"] == pytest.approx(2_803 / 2_403_340)
    assert nt["innskuddsdekning"] == pytest.approx(1_521_872 / 2_403_340)
    assert nt["egenkapitalrentabilitet"] == pytest.approx(43_586 / 295_855)
    assert tolkning.vurder("kostnadsgrad", nt["kostnadsgrad"]).niva == "sterk"
    assert all(tolkning.klartekst(k, v) for k, v in nt.items())


def test_forsikring():
    t = {"forsikringsinntekter": 100.0, "forsikringsresultat": 14.0, "aarsresultat": 10.0, "egenkapital": 50.0,
         "sum_eiendeler": 300.0}
    assert finans.selskapstype(t) == "forsikring"
    nt = {n.kode: n.verdi for n in finans.nokkeltall(t)}
    assert nt["combined_ratio"] == pytest.approx(0.86)
    assert "kostnadsgrad" not in nt
    overskrift, punkter = finans.sammendrag(t, None, 2024, "NOK")
    assert overskrift == "Forsikringsselskapet tjente godt i 2024"
    assert any("combined ratio" in p for p, _ in punkter)


def test_sammendrag_bank(dnb):
    tall, _ = dnb
    overskrift, punkter = finans.sammendrag(tall[2025], tall[2024], 2025, "NOK")
    tekst = " ".join(p for p, _ in punkter).replace("\xa0", " ")
    assert overskrift == "Banken tjente godt i 2025"
    assert "kostnadsgrad 38,0 %" in tekst and "Kundenes innskudd dekker 63 %" in tekst


def test_slaa_sammen_nyeste_vinner():
    ny = ({2025: {"aarsresultat": 2.0}, 2024: {"aarsresultat": 1.5, "egenkapital": None}}, "NOK")
    gammel = ({2024: {"aarsresultat": 1.0, "egenkapital": 9.0}, 2023: {"aarsresultat": 0.5}}, "NOK")
    ut = finans.slaa_sammen([ny, gammel])
    assert ut[2024] == {"aarsresultat": 1.5, "egenkapital": 9.0} and ut[2023]["aarsresultat"] == 0.5
