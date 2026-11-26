"""Tester for beregningene. Kjør med:  pytest

Testene bruker både håndlagde tall (der fasiten er enkel å regne for hånd)
og et ekte API-svar for Equinor lagret i tests/data/.
"""
import json
from pathlib import Path

import pytest

import brreg_api as api
import formatering as fmt
from beregninger import (balansekontroll, beregn_nokkeltall, del_, pluss,
                         resultatbro, samlet_status)

DATA = Path(__file__).parent / "data"


def nt(tall, kode):
    return next(n for n in beregn_nokkeltall(tall) if n.kode == kode)


@pytest.fixture
def enkelt():
    """Et lite, tenkt selskap med runde tall."""
    return {
        "sum_driftsinntekter": 1000.0, "sum_driftskostnad": 800.0, "driftsresultat": 200.0,
        "finansinntekter": 50.0, "finanskostnader": 30.0, "netto_finans": 20.0,
        "resultat_for_skatt": 220.0, "skattekostnad": 48.4, "aarsresultat": 171.6,
        "anleggsmidler": 1500.0, "omlopsmidler": 500.0, "sum_eiendeler": 2000.0,
        "egenkapital": 800.0, "langsiktig_gjeld": 950.0, "kortsiktig_gjeld": 250.0,
        "sum_gjeld": 1200.0, "sum_egenkapital_gjeld": 2000.0,
    }


@pytest.fixture
def equinor_raa():
    return json.loads((DATA / "equinor_regnskap.json").read_text())


# ---------------------------------------------------------------------------
# Nøkkeltall med kjente fasitsvar
# ---------------------------------------------------------------------------
class TestNokkeltall:
    def test_driftsmargin(self, enkelt):
        assert nt(enkelt, "driftsmargin").verdi == pytest.approx(0.20)

    def test_resultatmargin(self, enkelt):
        assert nt(enkelt, "resultatmargin").verdi == pytest.approx(0.22)

    def test_totalrentabilitet(self, enkelt):
        # (200 + 50) / 2000
        assert nt(enkelt, "totalrentabilitet").verdi == pytest.approx(0.125)

    def test_egenkapitalrentabilitet(self, enkelt):
        assert nt(enkelt, "egenkapitalrentabilitet").verdi == pytest.approx(171.6 / 800)

    def test_likviditetsgrad1(self, enkelt):
        assert nt(enkelt, "likviditetsgrad1").verdi == pytest.approx(2.0)

    def test_arbeidskapital(self, enkelt):
        assert nt(enkelt, "arbeidskapital").verdi == pytest.approx(250.0)

    def test_egenkapitalandel(self, enkelt):
        assert nt(enkelt, "egenkapitalandel").verdi == pytest.approx(0.40)

    def test_gjeldsgrad(self, enkelt):
        assert nt(enkelt, "gjeldsgrad").verdi == pytest.approx(1.5)

    def test_alle_finnes_med_formel(self, enkelt):
        alle = beregn_nokkeltall(enkelt)
        assert {n.kode for n in alle} == {
            "driftsmargin", "resultatmargin", "totalrentabilitet", "egenkapitalrentabilitet", "skattesats",
            "likviditetsgrad1", "likviditetsgrad2", "arbeidskapital", "egenkapitalandel", "gjeldsgrad",
            "rentedekningsgrad"}
        assert all(n.formel and n.forklaring for n in alle)

    def test_negativ_arbeidskapital(self, enkelt):
        enkelt["kortsiktig_gjeld"] = 700.0
        assert nt(enkelt, "arbeidskapital").verdi == pytest.approx(-200.0)

    def test_negativt_resultat_gir_negativ_margin(self, enkelt):
        enkelt["driftsresultat"] = -100.0
        assert nt(enkelt, "driftsmargin").verdi == pytest.approx(-0.10)


# ---------------------------------------------------------------------------
# Manglende tall skal gi None («mangler»), aldri 0
# ---------------------------------------------------------------------------
class TestManglendeTall:
    @pytest.mark.parametrize("felt, kode", [
        ("driftsresultat", "driftsmargin"),
        ("sum_driftsinntekter", "driftsmargin"),
        ("resultat_for_skatt", "resultatmargin"),
        ("finansinntekter", "totalrentabilitet"),
        ("sum_eiendeler", "totalrentabilitet"),
        ("aarsresultat", "egenkapitalrentabilitet"),
        ("omlopsmidler", "likviditetsgrad1"),
        ("kortsiktig_gjeld", "arbeidskapital"),
        ("egenkapital", "egenkapitalandel"),
        ("sum_gjeld", "gjeldsgrad"),
    ])
    def test_manglende_inndata_gir_none(self, enkelt, felt, kode):
        enkelt[felt] = None
        assert nt(enkelt, kode).verdi is None

    def test_felt_som_ikke_finnes_gir_none(self):
        assert all(n.verdi is None for n in beregn_nokkeltall({}))

    def test_null_i_nevner_gir_none(self, enkelt):
        enkelt["sum_driftsinntekter"] = 0.0
        assert nt(enkelt, "driftsmargin").verdi is None
        assert nt(enkelt, "resultatmargin").verdi is None

    def test_null_i_teller_er_et_ekte_tall(self, enkelt):
        enkelt["driftsresultat"] = 0.0
        assert nt(enkelt, "driftsmargin").verdi == 0.0

    def test_negativ_egenkapital(self, enkelt):
        enkelt["egenkapital"] = -100.0
        for kode in ("egenkapitalrentabilitet", "gjeldsgrad"):
            n = nt(enkelt, kode)
            assert n.verdi is None
            assert "negativ" in n.merknad
        # Egenkapitalandel er fortsatt meningsfull (negativ).
        assert nt(enkelt, "egenkapitalandel").verdi == pytest.approx(-0.05)

    def test_hjelpefunksjoner(self):
        assert del_(1, None) is None
        assert del_(None, 1) is None
        assert del_(1, 0) is None
        assert del_(1, 4) == 0.25
        assert pluss(1, None) is None
        assert pluss(1, 2, 3) == 6


# ---------------------------------------------------------------------------
# Balansekontroll
# ---------------------------------------------------------------------------
class TestBalansekontroll:
    def test_balanse_som_gaar_opp(self, enkelt):
        k = balansekontroll(enkelt)
        assert all(x.status == "ok" for x in k)
        assert samlet_status(k) == "ok"

    def test_stort_avvik(self, enkelt):
        enkelt["sum_eiendeler"] = 5000.0
        k = balansekontroll(enkelt)
        assert k[0].status == "avvik"
        assert k[0].differanse == pytest.approx(3000.0)
        assert samlet_status(k) == "avvik"

    def test_avrunding_godtas(self):
        # Ekte tilfelle: Equinor SELSKAP 2025 har 1 mill i differanse på 103 mrd.
        t = {"sum_eiendeler": 103_432e6, "sum_egenkapital_gjeld": 103_431e6}
        k = balansekontroll(t)[0]
        assert k.status == "avrunding"
        assert k.differanse == pytest.approx(1e6)

    def test_lite_selskap_smaa_avvik(self):
        t = {"sum_eiendeler": 100_500.0, "sum_egenkapital_gjeld": 100_000.0}
        assert balansekontroll(t)[0].status == "avrunding"    # 500 kr <= 1 000 kr
        t["sum_eiendeler"] = 105_000.0
        assert balansekontroll(t)[0].status == "avvik"

    def test_manglende_tall(self, enkelt):
        enkelt["sum_egenkapital_gjeld"] = None
        k = balansekontroll(enkelt)
        assert k[0].status == "mangler"
        assert samlet_status(k) == "mangler"


# ---------------------------------------------------------------------------
# Veien fra inntekter til årsresultat
# ---------------------------------------------------------------------------
class TestResultatbro:
    def test_fortegn_og_rekkefolge(self, enkelt):
        steg = resultatbro(enkelt)
        assert [s.navn for s in steg] == [
            "Driftsinntekter", "Driftskostnader", "Driftsresultat", "Netto finans",
            "Resultat før skatt", "Skattekostnad", "Årsresultat"]
        verdier = {s.navn: s.verdi for s in steg}
        assert verdier["Driftskostnader"] == -800.0
        assert verdier["Skattekostnad"] == pytest.approx(-48.4)

    def test_stegene_summerer_til_aarsresultat(self, enkelt):
        endringer = [s.verdi for s in resultatbro(enkelt) if s.type != "sum"]
        assert sum(endringer) == pytest.approx(enkelt["aarsresultat"])

    def test_manglende_kostnad_blir_none(self, enkelt):
        enkelt["sum_driftskostnad"] = None
        assert resultatbro(enkelt)[1].verdi is None


# ---------------------------------------------------------------------------
# Ekte data: Equinor
# ---------------------------------------------------------------------------
class TestEquinor:
    def test_typer_og_sortering(self, equinor_raa):
        assert api.tilgjengelige_typer(equinor_raa) == ["SELSKAP", "KONSERN"]
        aar = [r["aar"] for r in api.velg_regnskap(equinor_raa, "KONSERN")]
        assert aar == [2025, 2024, 2023]

    def test_tolking(self, equinor_raa):
        siste = api.velg_regnskap(equinor_raa, "KONSERN")[0]
        t = siste["tall"]
        assert siste["valuta"] == "USD"
        assert t["sum_driftsinntekter"] == 106_462e6
        assert t["aarsresultat"] == 5_058e6
        assert t["innskutt_egenkapital"] == 40_424e6   # feilstavet felt i API-et

    def test_manglende_felt_blir_none(self, equinor_raa):
        selskap = api.velg_regnskap(equinor_raa, "SELSKAP")
        assert selskap[0]["tall"]["investeringer"] is None          # finnes ikke i svaret
        konsern_2023 = api.velg_regnskap(equinor_raa, "KONSERN")[2]
        assert konsern_2023["tall"]["opptjent_egenkapital"] is None  # tom {} i svaret

    def test_nokkeltall_konsern_2025(self, equinor_raa):
        t = api.velg_regnskap(equinor_raa, "KONSERN")[0]["tall"]
        assert nt(t, "driftsmargin").verdi == pytest.approx(25_353 / 106_462)
        assert nt(t, "likviditetsgrad1").verdi == pytest.approx(38_940 / 30_780)
        assert nt(t, "egenkapitalandel").verdi == pytest.approx(40_497 / 131_727)
        assert samlet_status(balansekontroll(t)) == "ok"

    def test_selskap_2025_har_avrundingsavvik(self, equinor_raa):
        t = api.velg_regnskap(equinor_raa, "SELSKAP")[0]["tall"]
        assert balansekontroll(t)[0].status == "avrunding"


# ---------------------------------------------------------------------------
# Org.nr-validering
# ---------------------------------------------------------------------------
class TestOrgnr:
    @pytest.mark.parametrize("tekst", ["923609016", "923 609 016", " 923.609.016 ", "984851006"])
    def test_gyldige(self, tekst):
        assert len(api.valider_orgnr(tekst)) == 9

    @pytest.mark.parametrize("tekst, del_av_melding", [
        ("", "Skriv inn"),
        ("12345", "9 siffer"),
        ("1234567890", "9 siffer"),
        ("92360901A", "ikke er siffer"),
        ("923609017", "kontrollsifferet"),
        ("123456789", "kontrollsifferet"),
    ])
    def test_ugyldige(self, tekst, del_av_melding):
        with pytest.raises(api.UgyldigOrgnr, match=del_av_melding):
            api.valider_orgnr(tekst)


# ---------------------------------------------------------------------------
# Feilhåndtering mot API-et (uten nettverk – svarene er simulert)
# ---------------------------------------------------------------------------
class FalskSvar:
    def __init__(self, status, data=None):
        self.status_code = status
        self._data = data

    def json(self):
        return self._data


@pytest.mark.parametrize("status, feiltype", [
    (404, api.IngenRegnskap), (500, api.TjenesteFeil)])
def test_regnskap_feilkoder(monkeypatch, status, feiltype):
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: FalskSvar(status))
    with pytest.raises(feiltype):
        api.hent_regnskap("923609016")


def test_tom_regnskapsliste(monkeypatch):
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: FalskSvar(200, []))
    with pytest.raises(api.IngenRegnskap):
        api.hent_regnskap("923609016")


@pytest.mark.parametrize("status, feiltype", [
    (404, api.FantIkkeSelskap), (410, api.FantIkkeSelskap), (400, api.UgyldigOrgnr)])
def test_enhet_feilkoder(monkeypatch, status, feiltype):
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: FalskSvar(status))
    with pytest.raises(feiltype):
        api.hent_enhet("923609016")


# ---------------------------------------------------------------------------
# Formatering
# ---------------------------------------------------------------------------
class TestFormatering:
    def test_mangler(self):
        assert fmt.belop(None) == "mangler"
        assert fmt.prosent(None) == "mangler"
        assert fmt.ganger(None) == "mangler"

    def test_null_er_ikke_mangler(self):
        assert fmt.prosent(0.0) != "mangler"
        assert fmt.belop(0.0) != "mangler"

    def test_norsk_format(self):
        assert fmt.prosent(0.2381) == "23,8 %"
        assert fmt.belop(106_462e6, "USD") == "106,5 mrd. USD"
        assert fmt.belop(1_234_567, kort=False) == "1 234 567 NOK"
        assert fmt.ganger(-1.5) == "−1,50"


def test_bankregnskap_gir_tydelig_melding(monkeypatch):
    svar = FalskSvar(500, {"status": "500", "message":
                           "Regnskapet inneholder en oppstillingsplan som ikke er stottet (BANK)"})
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: svar)
    with pytest.raises(api.IngenRegnskap, match="BANK"):
        api.hent_regnskap("984851006")
