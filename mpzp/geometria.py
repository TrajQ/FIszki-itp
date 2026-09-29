"""Geometria działki: powierzchnia w m² i szkic SVG do raportu.

Geometrie z ULDK i WFS są w stopniach (EPSG:4326). Do powierzchni
przeliczamy je na metry lokalną skalą: ile metrów ma stopień długości i
szerokości geograficznej na szerokości środka działki (wzory elipsoidy
WGS84). Dla obiektów wielkości działki błąd jest poniżej 0,1% — bez
dodatkowej biblioteki do odwzorowań (np. pyproj).
"""

import math

from shapely.affinity import scale, translate
from shapely.geometry.base import BaseGeometry


def metry_na_stopien(szerokosc: float) -> tuple[float, float]:
    """(metry na 1° długości, metry na 1° szerokości) na danej szerokości."""
    fi = math.radians(szerokosc)
    na_szerokosc = 111132.954 - 559.822 * math.cos(2 * fi) + 1.175 * math.cos(4 * fi)
    na_dlugosc = 111412.84 * math.cos(fi) - 93.5 * math.cos(3 * fi)
    return na_dlugosc, na_szerokosc


def w_metrach(geometria: BaseGeometry, szerokosc_odniesienia: float) -> BaseGeometry:
    mx, my = metry_na_stopien(szerokosc_odniesienia)
    return scale(geometria, xfact=mx, yfact=my, origin=(0, 0))


def powierzchnia_m2(geometria: BaseGeometry, szerokosc_odniesienia: float | None = None) -> float:
    if geometria.is_empty:
        return 0.0
    if szerokosc_odniesienia is None:
        szerokosc_odniesienia = geometria.centroid.y
    return w_metrach(geometria, szerokosc_odniesienia).area


def szkic_svg(dzialka: BaseGeometry, czesci: list[tuple[BaseGeometry, int]], rozmiar: int = 320) -> dict:
    """Ścieżki SVG działki i jej części w wydzieleniach — do raportu.

    czesci: [(geometria_wydzielenia_przycieta_do_otoczenia, numer_koloru)].
    Zwraca {"viewbox": ..., "dzialka": d, "czesci": [(d, nr)]}; oś Y
    odwrócona (w SVG rośnie w dół), proporcje zachowane w metrach.
    """
    szer = dzialka.centroid.y
    minx, miny, maxx, maxy = w_metrach(dzialka, szer).bounds
    margines = max(maxx - minx, maxy - miny) * 0.25 or 1.0
    minx, miny, maxx, maxy = minx - margines, miny - margines, maxx + margines, maxy + margines
    skala = rozmiar / max(maxx - minx, maxy - miny)

    def do_svg(geom: BaseGeometry) -> str:
        g = w_metrach(geom, szer)
        g = translate(g, -minx, -maxy)
        g = scale(g, xfact=skala, yfact=-skala, origin=(0, 0))
        return _sciezka(g)

    return {
        "viewbox": f"0 0 {(maxx - minx) * skala:.1f} {(maxy - miny) * skala:.1f}",
        "dzialka": do_svg(dzialka),
        "czesci": [(do_svg(g), nr) for g, nr in czesci],
    }


def _sciezka(geom: BaseGeometry) -> str:
    wielokaty = getattr(geom, "geoms", [geom])
    fragmenty = []
    for w in wielokaty:
        if w.geom_type != "Polygon":
            continue
        for pierscien in [w.exterior, *w.interiors]:
            punkty = " L ".join(f"{x:.1f} {y:.1f}" for x, y in pierscien.coords)
            fragmenty.append(f"M {punkty} Z")
    return " ".join(fragmenty)
