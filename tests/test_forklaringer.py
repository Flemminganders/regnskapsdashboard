"""Alle forklaringer appen viser, må finnes og være utfylt."""
import re
from pathlib import Path

import forklaringer
import stil

APP = (Path(__file__).parent.parent / "app.py").read_text()


def test_alle_noekler_i_appen_finnes():
    brukt = set(re.findall(r'\bforklar\("([a-z_]+)"', APP))
    # Hovedtall og nøkkeltallgrupper hentes med variabel nøkkel:
    brukt |= {"sum_driftsinntekter", "driftsresultat", "aarsresultat", "sum_eiendeler", "egenkapital",
              "lonnsomhet", "likviditet", "soliditet"}
    mangler = brukt - set(forklaringer.FORKLARINGER)
    assert not mangler, f"Mangler forklaring for: {mangler}"


def test_ordlisten_peker_paa_eksisterende():
    assert set(forklaringer.ORDLISTE_REKKEFOLGE) <= set(forklaringer.FORKLARINGER)


def test_tekstene_er_utfylt_og_korte():
    for nokkel, (tittel, avsnitt) in forklaringer.FORKLARINGER.items():
        assert tittel and avsnitt, nokkel
        assert all(10 < len(a) < 400 for a in avsnitt), nokkel


def test_info_escaper_tekst():
    html = stil.info("<b>x</b>", ["a & b"])
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "a &amp; b" in html
    assert html.startswith('<details class="rd-info')
