"""Tester for søk på navn og ticker blant selskapene på Oslo Børs."""
import borsliste as bl


def test_lista_finnes_og_har_kjente_selskaper():
    alle = {s["orgnr"] for s in bl.selskaper()}
    assert {"923609016", "914778271", "984851006", "964118191"} <= alle   # Equinor, Hydro, DNB, Mowi
    assert len(bl.selskaper()) > 200


def test_org_nr_er_unike_og_gyldige():
    import brreg_api as api
    nr = [s["orgnr"] for s in bl.selskaper() if s["orgnr"]]
    assert len(nr) == len(set(nr))
    assert all(api.valider_orgnr(n) == n for n in nr)


def test_etikett_gir_orgnr():
    e = bl.etikett_for_orgnr("923609016")
    assert e.startswith("Equinor · EQNR")
    assert bl.tolk(e) == ("orgnr", "923609016")


def test_ticker_og_navn():
    assert bl.tolk("eqnr") == ("orgnr", "923609016")
    assert bl.tolk("Norsk Hydro") == ("orgnr", "914778271")
    assert bl.tolk("kongsberg gruppen") == ("orgnr", "943753709")


def test_flere_aksjeklasser_samme_selskap():
    odf = next(s for s in bl.selskaper() if "ODF" in s["tickere"])
    assert "ODFB" in odf["tickere"]
    assert bl.tolk("ODFB") == ("orgnr", odf["orgnr"])


def test_orgnr_sendes_videre_uendret():
    assert bl.tolk("923 609 016") == ("orgnr", "923 609 016")
    assert bl.tolk("123") == ("orgnr", "123")


def test_utenlandsk_flere_og_ukjent():
    art, s = bl.tolk("Frontline")
    assert art == "utenlandsk" and s["utenlandsk"]
    art, treff = bl.tolk("Sparebank")
    assert art == "flere" and len(treff) > 3
    assert bl.tolk("finnes ikke as") == ("ukjent", "finnes ikke as")
    assert bl.tolk("  ") == ("tom", None)


def test_pene_navn():
    assert bl.visningsnavn(next(s for s in bl.selskaper() if s["orgnr"] == "984851006")) == "DNB Bank"
