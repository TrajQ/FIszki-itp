"""Geometria działki: powierzchnia w m² i szkic SVG do raportu.

Geometrie z ULDK i WFS są w stopniach (EPSG:4326). Do powierzchni
przeliczamy je na metry lokalną skalą: ile metrów ma stopień długości i
szerokości geograficznej na szerokości środka działki (wzory elipsoidy
WGS84). Dla obiektów wielkości działki błąd jest poniżej 0,1% — bez
dodatkowej biblioteki do odwzorowań (np. pyproj).
"""

import math

from shapely.affinity import scale, translate
from shapely.geometry import LineString, mapping
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


# Boki krótsze niż to (po uproszczeniu) to zwykle szum w granicach
# ewidencyjnych — nie podpisujemy ich osobno.
UPROSZCZENIE_M = 0.2


def _z_metrow(x: float, y: float, szerokosc_odniesienia: float) -> list[float]:
    """Punkt w metrach (z w_metrach) → [lat, lon]."""
    mx, my = metry_na_stopien(szerokosc_odniesienia)
    return [y / my, x / mx]


def _najwiekszy_wielokat(geometria: BaseGeometry) -> BaseGeometry:
    czesci = [g for g in getattr(geometria, "geoms", [geometria]) if g.geom_type == "Polygon"]
    return max(czesci, key=lambda g: g.area)


def wymiary(geometria: BaseGeometry) -> dict:
    """Wymiary działki w metrach: boki, obwód, prostokąt opisany, zwartość.

    - boki — z największego wielokąta działki, po uproszczeniu o 20 cm
      (granice ewidencyjne mają dużo prawie współliniowych punktów),
    - szerokość i głębokość — krótszy i dłuższy bok najmniejszego
      prostokąta opisanego (obróconego) na działce,
    - zwartość (wskaźnik Polsby-Popper) = 4πP / L²: 1 dla koła, ok. 0,785
      dla kwadratu, mało dla działek wąskich i długich albo postrzępionych.
    """
    szer = geometria.centroid.y
    wielokat = w_metrach(_najwiekszy_wielokat(geometria), szer)
    uproszczony = wielokat.simplify(UPROSZCZENIE_M, preserve_topology=True)
    punkty = list(uproszczony.exterior.coords)
    boki = []
    for (x1, y1), (x2, y2) in zip(punkty, punkty[1:]):
        dlugosc = math.hypot(x2 - x1, y2 - y1)
        if dlugosc <= 0:
            continue
        boki.append(
            {
                "nr": len(boki) + 1,
                "dlugosc_m": round(dlugosc, 2),
                "od": _z_metrow(x1, y1, szer),
                "do": _z_metrow(x2, y2, szer),
                "srodek": _z_metrow((x1 + x2) / 2, (y1 + y2) / 2, szer),
            }
        )

    metryczna = w_metrach(geometria, szer)
    obwod = sum(g.exterior.length for g in getattr(metryczna, "geoms", [metryczna]) if g.geom_type == "Polygon")
    prostokat = wielokat.minimum_rotated_rectangle
    naroza = list(prostokat.exterior.coords)
    boki_prostokata = sorted(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(naroza[:2], naroza[1:3]))
    return {
        "boki": boki,
        "obwod_m": round(obwod, 2),
        "szerokosc_m": round(boki_prostokata[0], 2),
        "glebokosc_m": round(boki_prostokata[-1], 2),
        "zwartosc": round(4 * math.pi * metryczna.area / obwod**2, 3) if obwod else None,
    }


# Obszar analizowany do decyzji o warunkach zabudowy (§ 3 ust. 2
# rozporządzenia MI z 26.08.2003, Dz.U. nr 164 poz. 1588): wokół działki,
# w odległości co najmniej trzykrotnej szerokości frontu, nie mniej niż 50 m.
KROTNOSC_FRONTU = 3
MIN_ODLEGLOSC_ANALIZY_M = 50.0


def obszar_analizowany(geometria: BaseGeometry, szerokosc_frontu_m: float) -> dict:
    """Bufor wokół działki: max(3 × front, 50 m). GeoJSON w stopniach."""
    if not 0 < szerokosc_frontu_m <= 1000:
        raise ValueError("Szerokość frontu musi być z przedziału 0–1000 m.")
    szer = geometria.centroid.y
    mx, my = metry_na_stopien(szer)
    odleglosc = max(KROTNOSC_FRONTU * szerokosc_frontu_m, MIN_ODLEGLOSC_ANALIZY_M)
    bufor = w_metrach(geometria, szer).buffer(odleglosc, quad_segs=16)
    w_stopniach = scale(bufor, xfact=1 / mx, yfact=1 / my, origin=(0, 0))
    return {
        "odleglosc_m": odleglosc,
        "z_minimum": odleglosc == MIN_ODLEGLOSC_ANALIZY_M,
        "powierzchnia_m2": round(bufor.area, 1),
        "geometria": mapping(w_stopniach),
    }


def szkice_w_jednej_skali(geometrie: list[BaseGeometry], rozmiar: int = 200) -> tuple[list[dict], float]:
    """Szkice kilku działek w TEJ SAMEJ skali — do porównania kształtu i
    wielkości. Skala z największej działki; każda wyśrodkowana w swoim polu.
    Zwraca ([{"viewbox", "sciezka"}], skala w px na metr)."""
    metryczne = [w_metrach(g, g.centroid.y) for g in geometrie]
    rozpietosc = max(max(g.bounds[2] - g.bounds[0], g.bounds[3] - g.bounds[1]) for g in metryczne) or 1.0
    skala = rozmiar * 0.85 / rozpietosc
    wynik = []
    for g in metryczne:
        minx, miny, maxx, maxy = g.bounds
        srodek_x, srodek_y = (minx + maxx) / 2, (miny + maxy) / 2
        przesuniety = translate(g, -srodek_x, -srodek_y)
        w_pikselach = scale(przesuniety, xfact=skala, yfact=-skala, origin=(0, 0))
        w_pikselach = translate(w_pikselach, rozmiar / 2, rozmiar / 2)
        wynik.append({"viewbox": f"0 0 {rozmiar} {rozmiar}", "sciezka": _sciezka(w_pikselach)})
    return wynik, skala


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
