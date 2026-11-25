"""Tester for rentedekningsgrad, balansedrivere og sammenligning av to selskaper."""
import io
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

import brreg_api as api
from beregninger import HOYERE_ER_BEDRE, balansedrivere, beregn_nokkeltall, sterkest
from excel_eksport import lag_excel

DATA = Path(__file__).parent / "data"


def nt(t, kode):
    return next(n for n in beregn_nokkeltall(t) if n.kode == kode)


class TestRentedekningsgrad:
    def test_regnes_naar_renter_finnes(self):
        t = {"resultat_for_skatt": 220.0, "annen_rentekostnad": 40.0, "rentekostnad_konsern": 10.0}
        n = nt(t, "rentedekningsgrad")
        assert n.verdi == pytest.approx((220 + 50) / 50)
        assert n.gruppe == "Soliditet" and n.enhet == "ganger" and n.merknad is None

    def test_mangler_uten_renter(self):
        n = nt({"resultat_for_skatt": 220.0}, "rentedekningsgrad")
        assert n.verdi is None and "ikke oppgitt" in n.merknad

    def test_null_renter(self):
        n = nt({"resultat_for_skatt": 220.0, "annen_rentekostnad": 0.0}, "rentedekningsgrad")
        assert n.verdi is None and "ingen rentekostnader" in n.merknad

    def test_under_en_ved_underskudd(self):
        n = nt({"resultat_for_skatt": -80.0, "annen_rentekostnad": 100.0}, "rentedekningsgrad")
        assert n.verdi == pytest.approx(0.2)

    def test_excel_formel(self):
        raa = json.loads((DATA / "equinor_regnskap.json").read_text())
        enhet = api.tolk_enhet(json.loads((DATA / "equinor_enhet.json").read_text()))
        ws = load_workbook(io.BytesIO(lag_excel(enhet, api.velg_regnskap(raa, "KONSERN"))))["Nøkkeltall"]
        formel = next(ws.cell(r, 4).value for r in range(5, ws.max_row + 1)
                      if ws.cell(r, 2).value == "Rentedekningsgrad")
        assert formel.startswith("=IF(AND(OR(ISNUMBER(") and "SUM(" in formel


@pytest.fixture
def balanse():
    for_ = {"sum_eiendeler": 1000.0, "anleggsmidler": 600.0, "omlopsmidler": 400.0,
            "varer": 100.0, "fordringer": 150.0, "bankinnskudd": 150.0,
            "sum_egenkapital_gjeld": 1000.0, "egenkapital": 400.0, "langsiktig_gjeld": 350.0,
            "kortsiktig_gjeld": 250.0}
    na = {"sum_eiendeler": 1200.0, "anleggsmidler": 750.0, "omlopsmidler": 450.0,
          "varer": 90.0, "fordringer": 160.0, "bankinnskudd": 200.0,
          "sum_egenkapital_gjeld": 1200.0, "egenkapital": 420.0, "langsiktig_gjeld": 500.0,
          "kortsiktig_gjeld": 280.0}
    M = 1e6  # i millioner, så restene er større enn avrundingstoleransen
    return {k: v * M for k, v in na.items()}, {k: v * M for k, v in for_.items()}


M = 1e6


class TestBalansedrivere:
    def test_summerer_til_endringen(self, balanse):
        sider = balansedrivere(*balanse)
        for side in sider.values():
            assert sum(d.effekt for d in side.poster) == pytest.approx(side.endring)
            assert side.endring == pytest.approx(200 * M)

    def test_omlop_deles_opp(self, balanse):
        koder = [d.kode for d in balansedrivere(*balanse)["eiendeler"].poster]
        assert koder == ["anlegg", "bank", "varer", "fordringer"]  # størst effekt først (|−10| = |+10|)
        assert "omlop" not in koder

    def test_rest_i_omlop_blir_egen_post(self, balanse):
        na, for_ = balanse
        na["omlopsmidler"] = 480 * M
        na["sum_eiendeler"] = 1230 * M
        side = balansedrivere(na, for_)["eiendeler"]
        andre = next(d for d in side.poster if d.kode == "andre_omlop")
        assert andre.effekt == pytest.approx(30 * M)
        assert sum(d.effekt for d in side.poster) == pytest.approx(230 * M)

    def test_uten_underposter_brukes_omlop(self, balanse):
        na, for_ = balanse
        for t in (na, for_):
            for k in ("varer", "fordringer", "bankinnskudd"):
                t.pop(k)
        koder = {d.kode for d in balansedrivere(na, for_)["eiendeler"].poster}
        assert koder == {"anlegg", "omlop"}

    def test_feil_i_registeret_blir_andre_poster(self, balanse):
        na, for_ = balanse
        na["sum_egenkapital_gjeld"] = 1300 * M  # går ikke opp
        side = balansedrivere(na, for_)["finansiering"]
        assert next(d for d in side.poster if d.kode == "andre").effekt == pytest.approx(100 * M)

    def test_mangler_total_gir_none(self, balanse):
        na, for_ = balanse
        na.pop("sum_eiendeler")
        assert balansedrivere(na, for_)["eiendeler"] is None

    def test_equinor(self):
        raa = json.loads((DATA / "equinor_regnskap.json").read_text())
        r = api.velg_regnskap(raa, "KONSERN")
        sider = balansedrivere(r[0]["tall"], r[1]["tall"])
        for side in sider.values():
            assert side is not None
            assert sum(d.effekt for d in side.poster) == pytest.approx(side.endring)


class TestSterkest:
    def test_retning(self):
        assert sterkest("driftsmargin", 0.2, 0.1) == 0
        assert sterkest("driftsmargin", 0.1, 0.2) == 1
        assert sterkest("gjeldsgrad", 1.0, 2.0) == 0      # lavere gjeldsgrad er sterkest

    def test_ingen_fasit(self):
        assert sterkest("arbeidskapital", 10.0, 5.0) is None
        assert sterkest("driftsmargin", None, 0.1) is None
        assert sterkest("driftsmargin", 0.1, 0.1) is None

    def test_alle_nokkeltall_har_retning(self):
        assert {n.kode for n in beregn_nokkeltall({})} == set(HOYERE_ER_BEDRE)
