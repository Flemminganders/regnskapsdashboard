"""Tester for klartekst og vurdering av nøkkeltall, navnesøket og valutaomregningen."""
import pytest

import borsliste
import brreg_api as api
import stil
import tolkning
import valuta


# --- Vurdering og klartekst -------------------------------------------------------
@pytest.mark.parametrize("kode, verdi, niva", [
    ("driftsmargin", 0.15, "sterk"), ("driftsmargin", 0.05, "middels"), ("driftsmargin", -0.02, "svak"),
    ("likviditetsgrad1", 0.88, "svak"), ("likviditetsgrad1", 2.0, "sterk"),
    ("egenkapitalandel", 0.379, "sterk"), ("egenkapitalandel", 0.20, "middels"),
    ("gjeldsgrad", 1.5, "sterk"), ("gjeldsgrad", 3.0, "middels"), ("gjeldsgrad", 6.0, "svak"),
    ("altman_z", 1.93, "middels"), ("altman_z", 3.0, "sterk"), ("altman_z", 0.5, "svak"),
])
def test_vurdering(kode, verdi, niva):
    assert tolkning.vurder(kode, verdi).niva == niva


def test_ingen_vurdering_uten_fasit():
    assert tolkning.vurder("arbeidskapital", 1e6) is None
    assert tolkning.vurder("skattesats", 0.22) is None
    assert tolkning.vurder("driftsmargin", None) is None


def test_regel_er_lesbar():
    assert tolkning.vurder("driftsmargin", 0.05).regel == \
        "Tommelfingerregel: 10\xa0% eller mer er sterkt, under 3\xa0% er svakt."


def test_klartekst_i_kroner():
    assert tolkning.klartekst("driftsmargin", 0.082) == \
        "Av hver 100 kr i inntekter satt selskapet igjen med 8,2 kr etter å ha betalt for driften."
    assert "tapte selskapet 5,0 kr" in tolkning.klartekst("driftsmargin", -0.05)
    assert "er 38 kr betalt av eierne" in tolkning.klartekst("egenkapitalandel", 0.379)
    assert "0,88 kr" in tolkning.klartekst("likviditetsgrad1", 0.88)
    assert "skylder 4,4 mrd. USD mer" in tolkning.klartekst("arbeidskapital", -4.4e9, "USD")
    assert tolkning.klartekst("driftsmargin", None) is None


def test_alle_nokkeltall_har_klartekst():
    from beregninger import beregn_nokkeltall
    t = {"sum_driftsinntekter": 1.0, "driftsresultat": 0.1}
    for n in beregn_nokkeltall(t):
        assert tolkning.klartekst(n.kode, 0.5) is not None, n.kode


# --- Navnesøk ----------------------------------------------------------------------
def svar(*enheter):
    return {"_embedded": {"enheter": [
        {"organisasjonsnummer": nr, "navn": navn, "organisasjonsform": {"kode": form},
         "forretningsadresse": {"kommune": "OSLO"}, "antallAnsatte": ans} for nr, navn, form, ans in enheter]}}


def test_navnesok_sorterer_og_filtrerer():
    treff = api.tolk_sokeresultat(svar(("1", "REMA 1000 AS", "AS", None), ("2", "1000 BALLONGER DA", "DA", None),
                                       ("3", "REMA 1000 NORGE AS", "AS", 554), ("4", "OLA REMA 1000", "ENK", 1)))
    assert [x["orgnr"] for x in treff][:2] == ["3", "1"]          # flest ansatte først blant AS
    filtrert = api.filtrer_treff(treff, "rema 1000")
    assert [x["orgnr"] for x in filtrert] == ["3", "1"]           # ikke Ballonger (mangler «rema»), ikke ENK
    assert treff[0]["kommune"] == "Oslo"


def test_valgt_navnesokstreff_tolkes_som_orgnr():
    assert borsliste.tolk("Rema 1000 Norge AS · 982254604") == ("orgnr", "982254604")


# --- Valuta ------------------------------------------------------------------------
def sdmx(obs, mult="0"):
    return {"data": {
        "dataSets": [{"series": {"0:0:0:0": {"attributes": [0, 0, 0], "observations": obs}}}],
        "structure": {"dimensions": {"observation": [{"values": [{"id": "2024"}, {"id": "2025"}]}]},
                      "attributes": {"series": [{"id": "DECIMALS", "values": [{"id": "2"}]},
                                                {"id": "CALCULATED", "values": [{"id": "false"}]},
                                                {"id": "UNIT_MULT", "values": [{"id": mult}]}]}}}}


def test_tolk_kurser():
    assert valuta.tolk_kurser(sdmx({"0": ["10.7433"], "1": ["10.3912"]})) == {2024: 10.7433, 2025: 10.3912}


def test_tolk_kurser_per_hundre():
    assert valuta.tolk_kurser(sdmx({"0": ["101.74"]}, "2"))[2024] == pytest.approx(1.0174)


def test_til_nok():
    assert valuta.til_nok(2e9, 2025, {2025: 10.0}) == 2e10
    assert valuta.til_nok(2e9, 2023, {2025: 10.0}) is None
    assert valuta.hent_kurser("NOK") == {}


# --- Visning -------------------------------------------------------------------------
def test_minisoyler():
    html = stil.minisoyler([("2023", 10.0, False), ("2024", -5.0, False), ("2025", 20.0, True)])
    assert html.count("<span") == 3 and 'class="valgt"' in html and 'class="neg"' in html
    assert stil.minisoyler([("2025", 1.0, True)]) == ""


def test_nokkeltall_rad_med_vurdering():
    html = stil.nokkeltall_rad("Driftsmargin", "8,2 %", None, "f", "x", [], None, "",
                               "Av hver 100 kr …", ("middels", "Middels", "Regel"))
    assert 'rd-vurd middels' in html and "rd-klartekst" in html and "Regel" in html
