"""Tester for driver-analysen (hva forklarer endringen i årsresultatet),
hendelser fra registrene og PDF-lenker."""
import json
from datetime import date
from pathlib import Path

import pytest

import brreg_api as api
import formatering as fmt
from beregninger import resultatdrivere

DATA = Path(__file__).parent / "data"


def tall(inntekter, kostnader, finans, skatt):
    driftsres = inntekter - kostnader
    for_skatt = driftsres + finans
    return {"sum_driftsinntekter": inntekter, "sum_driftskostnad": kostnader, "driftsresultat": driftsres,
            "netto_finans": finans, "resultat_for_skatt": for_skatt, "skattekostnad": skatt,
            "aarsresultat": for_skatt - skatt}


class TestDrivere:
    def test_bidragene_summerer_til_endringen(self):
        a = resultatdrivere(tall(1200, 900, 10, 70), tall(1000, 800, -20, 40))
        assert a.endring == pytest.approx(240 - 140)
        assert sum(d.effekt for d in a.drivere) == pytest.approx(a.endring)

    def test_fortegn_og_rangering(self):
        a = resultatdrivere(tall(1200, 900, 10, 70), tall(1000, 800, -20, 40))
        effekt = {d.kode: d.effekt for d in a.drivere}
        assert effekt == {"inntekter": 200, "kostnader": -100, "finans": 30, "skatt": -30}
        assert [d.kode for d in a.topp(3)][:2] == ["inntekter", "kostnader"]
        assert len(a.topp(3)) == 3

    def test_okt_kostnad_trekker_ned(self):
        a = resultatdrivere(tall(1000, 900, 0, 0), tall(1000, 800, 0, 0))
        d = a.topp(1)[0]
        assert d.kode == "kostnader" and d.effekt == -100 and d.endring == 100

    def test_uforklart_rest_blir_andre_poster(self):
        na = tall(1000, 800, 0, 0)
        na["aarsresultat"] += 50_000          # en post API-et ikke viser
        a = resultatdrivere(na, tall(1000, 800, 0, 0))
        assert a.drivere[0].kode == "andre" and a.drivere[0].effekt == pytest.approx(50_000)

    def test_avrunding_gir_ikke_andre_poster(self):
        na = tall(1_000_000, 800_000, 0, 0)
        na["aarsresultat"] += 400            # under toleransen
        a = resultatdrivere(na, tall(900_000, 800_000, 0, 0))
        assert all(d.kode != "andre" for d in a.drivere)

    def test_manglende_post_hoppes_over(self):
        na, for_ = tall(1200, 900, 10, 70), tall(1000, 800, -20, 40)
        na["skattekostnad"] = None
        a = resultatdrivere(na, for_)
        assert "skatt" not in {d.kode for d in a.drivere}
        assert sum(d.effekt for d in a.drivere) == pytest.approx(a.endring)   # resten havner i «andre»

    def test_netto_finans_fra_inntekter_og_kostnader(self):
        na, for_ = tall(1000, 800, 0, 0), tall(1000, 800, 0, 0)
        na.update(netto_finans=None, finansinntekter=50.0, finanskostnader=20.0)
        na["aarsresultat"] += 30
        for_.update(netto_finans=None, finansinntekter=0.0, finanskostnader=0.0)
        a = resultatdrivere(na, for_)
        assert {d.kode: d.effekt for d in a.drivere}["finans"] == pytest.approx(30)

    def test_mangler_aarsresultat_gir_none(self):
        na = tall(1000, 800, 0, 0)
        na["aarsresultat"] = None
        assert resultatdrivere(na, tall(1000, 800, 0, 0)) is None

    def test_equinor_konsern_2025(self):
        raa = json.loads((DATA / "equinor_regnskap.json").read_text())
        r = api.velg_regnskap(raa, "KONSERN")
        a = resultatdrivere(r[0]["tall"], r[1]["tall"])
        assert a.endring == pytest.approx(5_058e6 - 8_829e6)
        assert sum(d.effekt for d in a.drivere) == pytest.approx(a.endring)
        topp = a.topp(3)
        assert topp[0].kode == "kostnader" and topp[0].effekt == pytest.approx(-(81_109e6 - 72_846e6))
        assert [d.kode for d in topp] == ["kostnader", "inntekter", "skatt"]


class TestHendelser:
    @pytest.fixture
    def enhet(self):
        return json.loads((DATA / "equinor_enhet.json").read_text())

    @pytest.fixture
    def roller(self):
        return json.loads((DATA / "equinor_roller.json").read_text())

    def test_nyeste_forst_og_innenfor_24_mnd(self, enhet, roller):
        h = api.tolk_hendelser(enhet, roller, i_dag=date(2026, 11, 25))
        datoer = [x["dato"] for x in h]
        assert datoer == sorted(datoer, reverse=True)
        assert all(date(2024, 11, 1) <= d <= date(2026, 11, 25) for d in datoer)
        titler = [x["tittel"] for x in h]
        assert titler[0] == "Styret endret"                       # 2026-09-04
        assert "Kapitalendring registrert" in titler            # 2026-07-02
        assert "Nye vedtekter" in titler                        # 2026-05-12
        assert "Daglig leder endret" not in titler              # 2020 – for gammelt

    def test_styredetalj_uten_fodselsdato(self, enhet, roller):
        h = api.tolk_hendelser(enhet, roller, i_dag=date(2026, 11, 25))
        styret = next(x for x in h if x["tittel"] == "Styret endret")
        assert "styreleder" in styret["detalj"] and "medlemmer" in styret["detalj"]
        assert "19" not in styret["detalj"]                       # ingen fødselsår/-datoer

    def test_lengre_vindu_tar_med_eldre(self, enhet, roller):
        h = api.tolk_hendelser(enhet, roller, i_dag=date(2026, 11, 25), maaneder=120)
        dl = next(x for x in h if x["tittel"] == "Daglig leder endret")
        assert dl["detalj"] == "Daglig leder: Anders Opedal"

    def test_tomme_data(self):
        assert api.tolk_hendelser({}, {}, i_dag=date(2026, 1, 1)) == []

    def test_grense_ved_aarsskifte(self):
        enhet = {"vedtektsdato": "2024-01-01"}
        assert api.tolk_hendelser(enhet, {}, i_dag=date(2026, 1, 15))   # grense 2024-01-01
        assert not api.tolk_hendelser(enhet, {}, i_dag=date(2026, 2, 15))


class FalskSvar:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


def test_pdf_aar_sorteres_nyeste_forst(monkeypatch):
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: FalskSvar(200, ["2011", "2025", "2024"]))
    assert api.hent_pdf_aar("923609016") == [2025, 2024, 2011]


def test_pdf_aar_feil_gir_tom_liste(monkeypatch):
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: FalskSvar(500))
    assert api.hent_pdf_aar("923609016") == []


def test_pdf_lenke():
    assert api.pdf_lenke("923609016", 2022).endswith("/aarsregnskap/kopi/923609016/2022")


def test_formatering_med_fortegn():
    assert fmt.fortegn_belop(-4_587e6, "USD") == "−4,6 mrd. USD"
    assert fmt.fortegn_belop(2_740e6, "USD") == "+2,7 mrd. USD"
    assert fmt.fortegn_prosent(-0.296) == "−29,6 %"
    assert fmt.dato_kort(date(2026, 9, 4)) == "4. sep. 2026"
    assert fmt.fortegn_belop(None) == "mangler"
