"""Wykres liniowy kilku gmin w czasie do druku (ETAP 171).

SVG rysowany po stronie serwera — tak jak mapy do druku (`mapa_svg.py`):
tylko liczby i kolory z kodu, nazwy gmin są w legendzie strony (HTML,
escapowane przez Jinja), a w SVG — numery linii.
"""

import math

from .statystyki import format_liczby

KOLORY_SERII = ["#0071e3", "#ff9500", "#34c759", "#af52de", "#ff375f"]


def _ladna_os(lo: float, hi: float, podzialek: int = 5) -> tuple[float, float, float]:
    """Granice osi i krok z „okrągłych” liczb (1, 2, 2,5, 5 × 10^n)."""
    if lo == hi:
        lo, hi = lo - (abs(lo) * 0.1 or 1), hi + (abs(hi) * 0.1 or 1)
    surowy = (hi - lo) / podzialek
    potega = 10 ** math.floor(math.log10(surowy))
    krok = next(k * potega for k in (1, 2, 2.5, 5, 10) if k * potega >= surowy)
    return math.floor(lo / krok) * krok, math.ceil(hi / krok) * krok, krok


def wykres_gmin_svg(serie: list[dict], szerokosc: int = 900, wysokosc: int = 340) -> str:
    """serie: [{"szereg": [{"rok", "wartosc"}], "kolor"}] → SVG. Oś lat
    wspólna (suma lat wszystkich serii); brak roku w serii przerywa linię."""
    lata = sorted({p["rok"] for s in serie for p in s["szereg"]})
    wartosci = [p["wartosc"] for s in serie for p in s["szereg"]]
    otwarcie = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" '
                f'height="{wysokosc}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>')
    if len(lata) < 2:
        return otwarcie + f'<text x="{szerokosc / 2}" y="{wysokosc / 2}" text-anchor="middle" fill="#6e6e73">za mało lat z danymi</text></svg>'
    mn, mx = min(wartosci), max(wartosci)
    # oś od zera, gdy dane są dodatnie i blisko zera (względem rozpiętości) — jak w wykresie profilu gminy
    lo, hi, krok = _ladna_os(0.0 if 0 <= mn < mx - mn else mn, mx)
    m = {"l": 76, "p": 36, "g": 14, "d": 30}

    def x(rok):
        return m["l"] + lata.index(rok) * (szerokosc - m["l"] - m["p"]) / (len(lata) - 1)

    def y(v):
        return wysokosc - m["d"] - (v - lo) / ((hi - lo) or 1) * (wysokosc - m["g"] - m["d"])

    czesci = [otwarcie]
    v = lo
    while v <= hi + krok / 2:
        czesci.append(f'<line x1="{m["l"]}" x2="{szerokosc - m["p"]}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#e8e8ed"/>'
                      f'<text x="{m["l"] - 8}" y="{y(v) + 4:.1f}" text-anchor="end" fill="#6e6e73">{format_liczby(round(v, 2))}</text>')
        v += krok
    co_ile = math.ceil(len(lata) / 12)  # najwyżej ~12 podpisów lat; ostatni zawsze
    for i, rok in enumerate(lata):
        if (len(lata) - 1 - i) % co_ile == 0:
            czesci.append(f'<text x="{x(rok):.1f}" y="{wysokosc - 10}" text-anchor="middle" fill="#6e6e73">{rok}</text>')
    for nr, s in enumerate(serie, start=1):
        po_roku = {p["rok"]: p["wartosc"] for p in s["szereg"]}
        odcinek: list[str] = []
        for rok in [*lata, None]:  # None zamyka ostatni odcinek
            if rok in po_roku:
                odcinek.append(f"{x(rok):.1f},{y(po_roku[rok]):.1f}")
                continue
            if len(odcinek) > 1:
                czesci.append(f'<polyline points="{" ".join(odcinek)}" fill="none" stroke="{s["kolor"]}" stroke-width="2.5"/>')
            odcinek = []
        for rok, wartosc in po_roku.items():
            czesci.append(f'<circle cx="{x(rok):.1f}" cy="{y(wartosc):.1f}" r="3" fill="{s["kolor"]}"/>')
        ostatni = max(po_roku)
        czesci.append(f'<text x="{x(ostatni) + 8:.1f}" y="{y(po_roku[ostatni]) + 4:.1f}" font-weight="700" fill="{s["kolor"]}">{nr}</text>')
    czesci.append("</svg>")
    return "".join(czesci)
