"""Norsk tallformatering. ``None`` blir alltid «mangler» – aldri 0."""
from __future__ import annotations

from typing import Optional

MANGLER = "mangler"
_NBSP = " "


def _norsk(tall: float, desimaler: int) -> str:
    tekst = f"{tall:,.{desimaler}f}"          # 1,234,567.89
    return tekst.replace(",", _NBSP).replace(".", ",").replace("-", "−")


def belop(verdi: Optional[float], valuta: str = "NOK", kort: bool = True) -> str:
    """106 462 000 000 -> «106,5 mrd. NOK» (kort) eller «106 462 000 000 NOK»."""
    if verdi is None:
        return MANGLER
    if not kort:
        return f"{_norsk(verdi, 0)} {valuta}"
    a = abs(verdi)
    if a >= 1e9:
        return f"{_norsk(verdi / 1e9, 1)} mrd. {valuta}"
    if a >= 1e6:
        return f"{_norsk(verdi / 1e6, 1)} mill. {valuta}"
    return f"{_norsk(verdi, 0)} {valuta}"


def prosent(verdi: Optional[float], desimaler: int = 1) -> str:
    """0.2381 -> «23,8 %»."""
    if verdi is None:
        return MANGLER
    return f"{_norsk(verdi * 100, desimaler)}{_NBSP}%"


def ganger(verdi: Optional[float], desimaler: int = 2) -> str:
    """1.2649 -> «1,26»."""
    if verdi is None:
        return MANGLER
    return _norsk(verdi, desimaler)


def nokkeltall(verdi: Optional[float], enhet: str, valuta: str = "NOK") -> str:
    if enhet == "prosent":
        return prosent(verdi)
    if enhet == "ganger":
        return ganger(verdi)
    return belop(verdi, valuta)


def heltall(verdi: Optional[float]) -> str:
    return MANGLER if verdi is None else _norsk(verdi, 0)


_MND = ["jan.", "feb.", "mars", "apr.", "mai", "juni", "juli", "aug.", "sep.", "okt.", "nov.", "des."]


def dato_kort(d) -> str:
    """date(2026, 9, 4) -> «4. sep. 2026». None -> «mangler»."""
    if d is None:
        return MANGLER
    return f"{d.day}. {_MND[d.month - 1]} {d.year}"


def fortegn_belop(verdi: Optional[float], valuta: str = "NOK") -> str:
    """Beløp med eksplisitt fortegn: «+2,7 mrd. USD» / «−4,6 mrd. USD»."""
    if verdi is None:
        return MANGLER
    tekst = belop(abs(verdi), valuta)
    return ("+" if verdi > 0 else "−" if verdi < 0 else "") + tekst


def fortegn_prosent(verdi: Optional[float], desimaler: int = 1) -> str:
    """0.063 -> «+6,3 %», -0.296 -> «−29,6 %»."""
    if verdi is None:
        return MANGLER
    tekst = prosent(abs(verdi), desimaler)
    return ("+" if verdi > 0 else "−" if verdi < 0 else "") + tekst
