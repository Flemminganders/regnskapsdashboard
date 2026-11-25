"""Tester for totalrentabilitet med rentekostnader, nettoførte finansposter og eierselskap."""
import io

import pytest
from openpyxl import load_workbook

import brreg_api as api
from beregninger import beregn_nokkeltall, er_eierselskap, finans_er_netto, rentekostnader
from excel_eksport import lag_excel


def nt(t, kode):
    return next(n for n in beregn_nokkeltall(t) if n.kode == kode)


@pytest.fixture
def t():
    return {"sum_driftsinntekter": 1000.0, "driftsresultat": 200.0, "finansinntekter": 50.0,
            "finanskostnader": 30.0, "netto_finans": 20.0, "resultat_for_skatt": 220.0,
            "sum_eiendeler": 2000.0}


class TestTotalrentabilitet:
    def test_laerebok_naar_renter_finnes(self, t):
        t.update(annen_rentekostnad=24.0, rentekostnad_konsern=6.0)
        n = nt(t, "totalrentabilitet")
        assert n.verdi == pytest.approx((220 + 30) / 2000)
        assert n.formel.startswith("(Resultat før skatt + Rentekostnader)")
        assert "annen_rentekostnad" in n.inndata

    def test_bare_en_rentepost(self, t):
        t["annen_rentekostnad"] = 24.0
        assert nt(t, "totalrentabilitet").verdi == pytest.approx((220 + 24) / 2000)

    def test_tilnaerming_uten_renter(self, t):
        n = nt(t, "totalrentabilitet")
        assert n.verdi == pytest.approx((200 + 50) / 2000)
        assert "ikke oppgitt rentekostnader" in n.merknad

    def test_rente_null_er_et_ekte_tall(self, t):
        t["annen_rentekostnad"] = 0.0
        assert nt(t, "totalrentabilitet").verdi == pytest.approx(220 / 2000)

    def test_mangler_resultat_for_skatt(self, t):
        t.update(annen_rentekostnad=24.0, resultat_for_skatt=None)
        assert nt(t, "totalrentabilitet").verdi is None

    def test_rentekostnader(self):
        assert rentekostnader({}) is None
        assert rentekostnader({"annen_rentekostnad": 5.0}) == 5.0
        assert rentekostnader({"annen_rentekostnad": 5.0, "rentekostnad_konsern": 2.0}) == 7.0


class TestNettoFinans:
    def test_netto_naar_kostnad_mangler_og_lik_netto(self):
        t = {"finansinntekter": 6_978e6, "netto_finans": 6_978e6, "finanskostnader": None}
        assert finans_er_netto(t)
        n = nt({**t, "driftsresultat": 1.0, "sum_eiendeler": 10.0}, "totalrentabilitet")
        assert "nettotall" in n.merknad

    def test_ikke_netto_naar_kostnad_finnes(self):
        assert not finans_er_netto({"finansinntekter": 50.0, "netto_finans": 20.0, "finanskostnader": 30.0})

    def test_ikke_netto_naar_tallene_er_ulike(self):
        assert not finans_er_netto({"finansinntekter": 5e9, "netto_finans": 4e9, "finanskostnader": None})


class TestEierselskap:
    def test_holding(self):
        assert er_eierselskap({"sum_driftsinntekter": 0.4e9, "finansinntekter": 17.2e9})

    def test_driftsselskap(self):
        assert not er_eierselskap({"sum_driftsinntekter": 68e9, "finansinntekter": 2.8e9})

    def test_uten_driftsinntekter(self):
        assert er_eierselskap({"sum_driftsinntekter": None, "finansinntekter": 1.0})
        assert not er_eierselskap({"sum_driftsinntekter": None, "finansinntekter": None})


def test_api_tolker_rentefelt():
    raa = {"regnskapsperiode": {"tilDato": "2025-12-31"}, "resultatregnskapResultat": {"finansresultat": {
        "finanskostnad": {"rentekostnadSammeKonsern": 2876e6, "annenRentekostnad": 174e6, "sumFinanskostnad": 3041e6}}}}
    tall = api.tolk_regnskap(raa)["tall"]
    assert tall["annen_rentekostnad"] == 174e6 and tall["rentekostnad_konsern"] == 2876e6


def test_excel_har_begge_grener():
    regnskap = {"aar": 2025, "regnskapstype": "SELSKAP", "valuta": "NOK", "regnskapsregler": None,
                "tall": {"annen_rentekostnad": 24.0, "resultat_for_skatt": 220.0, "sum_eiendeler": 2000.0}}
    wb = load_workbook(io.BytesIO(lag_excel({"navn": "Test"}, [regnskap])))
    ws = wb["Nøkkeltall"]
    formel = next(ws.cell(r, 4).value for r in range(5, ws.max_row + 1) if ws.cell(r, 2).value == "Totalrentabilitet")
    assert formel.startswith("=IF(OR(ISNUMBER(") and "SUM(" in formel
