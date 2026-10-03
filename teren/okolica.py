"""Punkty z inwentaryzacji w okolicy działki albo obszaru (ETAP 176).

Moduł MPZP (karta działki) pyta o nie przez trasę POST /teren/okolica —
tak jak o ceny w okolicy (D-117): moduły nie czytają nawzajem swoich baz.
Odległość liczymy w lokalnym układzie metrycznym (przybliżenie
równoodległościowe wokół środka kształtu) — przy setkach metrów błąd
jest pomijalny wobec dokładności GPS telefonu.
"""

import math

from shapely.affinity import scale
from shapely.geometry import Point, shape

PROMIENIE_M = (50, 100, 250)
MAKS_PUNKTOW = 50
R_ZIEMI = 6371008.8


class BladOkolicy(ValueError):
    pass


def ksztalt(geometria) -> object:
    """GeoJSON punktu albo wieloboku w WGS84 → kształt shapely; BladOkolicy, gdy zły."""
    try:
        k = shape(geometria)
    except Exception:
        raise BladOkolicy("Niepoprawna geometria.") from None
    if k.geom_type not in ("Point", "Polygon", "MultiPolygon") or k.is_empty:
        raise BladOkolicy("Geometria musi być punktem albo wielobokiem.")
    minx, miny, maxx, maxy = k.bounds
    if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
        raise BladOkolicy("Współrzędne muszą być w stopniach (WGS84).")
    return k


def punkty_w_okolicy(k, promien_m: float, projekty: list[tuple[dict, list[dict]]]) -> list[dict]:
    """[(projekt, punkty)] → punkty z położeniem najwyżej promien_m od kształtu
    (także w środku), od najbliższego, najwyżej MAKS_PUNKTOW."""
    lat0 = math.radians(k.centroid.y)
    mx, my = R_ZIEMI * math.pi / 180 * math.cos(lat0), R_ZIEMI * math.pi / 180

    def w_metrach(g):
        return scale(g, xfact=mx, yfact=my, origin=(0, 0))

    k_m = w_metrach(k)
    wynik = []
    for projekt, punkty in projekty:
        for p in punkty:
            if p["lat"] is None:
                continue
            odleglosc = k_m.distance(Point(p["lng"] * mx, p["lat"] * my))
            if odleglosc <= promien_m:
                wynik.append({"projekt": projekt, "punkt": p, "odleglosc_m": round(odleglosc, 1)})
    wynik.sort(key=lambda w: w["odleglosc_m"])
    return wynik[:MAKS_PUNKTOW]
