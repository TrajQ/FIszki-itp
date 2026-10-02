"""Zestawienie „Moich działek” do druku (ETAP 162).

Wszystko z danych zapisanych w Warsztacie (bez zapytań do ULDK i planów):
tabela, suma powierzchni według przeznaczenia i schemat położenia działek
(punkty z numerami, bez podkładu). Powierzchnia jest ta zapisana razem
z działką — z geometrii ULDK w chwili zapisu.
"""

import math
import statistics
from html import escape

from .symbole import opisz_symbol
from .uklady import pl2000

KROKI_PODZIALKI_M = [50, 100, 200, 250, 500, 1000, 2000, 5000, 10_000, 20_000, 50_000]


def wiersze(dzialki: list[dict]) -> list[dict]:
    """Działki z numerem, opisem przeznaczenia i współrzędnymi PL-2000."""
    wynik = []
    for nr, d in enumerate(dzialki, start=1):
        p = pl2000(d["lat"], d["lon"])
        opisy = [f"{s['symbol']} — {s['opis']}" if s["opis"] else s["symbol"] for s in opisz_symbol(d["przeznaczenie"])]
        wynik.append({**d, "nr": nr, "opis_przeznaczenia": "; ".join(opisy), "x2000": p["x"], "y2000": p["y"], "uklad": p["uklad"]})
    return wynik


def wedlug_przeznaczenia(dzialki: list[dict]) -> list[dict]:
    """[{przeznaczenie, liczba, pow_m2}] od największej powierzchni; bez planu na końcu."""
    grupy: dict = {}
    for d in dzialki:
        g = grupy.setdefault(d["przeznaczenie"] or "", {"przeznaczenie": d["przeznaczenie"], "liczba": 0, "pow_m2": None})
        g["liczba"] += 1
        if d["powierzchnia_m2"] is not None:  # nieznana powierzchnia to nie 0 m²
            g["pow_m2"] = (g["pow_m2"] or 0.0) + d["powierzchnia_m2"]
    return sorted(grupy.values(), key=lambda g: (g["przeznaczenie"] is None, -(g["pow_m2"] or 0)))


def schemat_svg(dzialki: list[dict], szerokosc: int = 900, wysokosc: int = 420) -> str:
    """Punkty działek z numerami na tle prostokąta; podziałka w metrach."""
    margines = 40
    if not dzialki:
        return ""
    lat0 = statistics.fmean(d["lat"] for d in dzialki)
    mx, my = 111_320 * math.cos(math.radians(lat0)), 110_574  # metry na stopień
    xs, ys = [d["lon"] * mx for d in dzialki], [d["lat"] * my for d in dzialki]
    rozpietosc = max(max(xs) - min(xs), max(ys) - min(ys), 100.0)
    skala = min((szerokosc - 2 * margines) / max(max(xs) - min(xs), rozpietosc * 0.2), (wysokosc - 2 * margines - 30) / max(max(ys) - min(ys), rozpietosc * 0.2))
    srodek_x, srodek_y = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    czesci = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" font-family="sans-serif">',
              '<rect width="100%" height="100%" fill="#ffffff" stroke="#d2d2d7"/>']
    for d, x, y in zip(dzialki, xs, ys):
        px = szerokosc / 2 + (x - srodek_x) * skala
        py = (wysokosc - 30) / 2 - (y - srodek_y) * skala
        czesci.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="#0071e3" stroke="#ffffff" stroke-width="1.5"><title>{escape(d["dzialka_id"])}</title></circle>')
        czesci.append(f'<text x="{px:.1f}" y="{py + 4:.1f}" font-size="10" font-weight="700" fill="#ffffff" text-anchor="middle">{d["nr"]}</text>')
    metry = max((m for m in KROKI_PODZIALKI_M if m * skala <= szerokosc / 4), default=KROKI_PODZIALKI_M[0])
    dlugosc = metry * skala
    czesci.append(f'<rect x="{margines}" y="{wysokosc - 24}" width="{dlugosc:.1f}" height="5" fill="#1d1d1f"/>')
    etykieta = f"{metry // 1000} km" if metry >= 1000 else f"{metry} m"
    czesci.append(f'<text x="{margines + dlugosc + 6:.1f}" y="{wysokosc - 18}" font-size="11" fill="#1d1d1f">{etykieta}</text>')
    czesci.append("</svg>")
    return "".join(czesci)
