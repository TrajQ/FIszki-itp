"""Karta działki (ETAP 80): dodatki do raportu działki.

- położenie: środek działki (punkt wewnątrz) w WGS84, PL-1992, PL-2000,
- ortofotomapa: adresy obrazów WMS dla prostokąta wokół działki —
  obecnej i najstarszej dostępnej archiwalnej — oraz obrys działki w tym
  samym prostokącie (SVG nakładany na obraz).

Obrazy pobiera przeglądarka, tak jak kafelki ortofotomapy na mapach
Leaflet w innych modułach: WMS 1.3.0, CRS=EPSG:3857 (Web Mercator),
BBOX w metrach w kolejności x,y — ten sam układ, którego używa Leaflet.
"""

import math
from urllib.parse import urlencode

from shapely.geometry.base import BaseGeometry

from . import uklady

URL_ORTO = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution"
_R = 6378137.0  # promień sfery Web Mercator
SZEROKOSC_PX, WYSOKOSC_PX = 640, 480
MARGINES = 0.35  # zapas wokół działki (część rozmiaru), żeby było widać sąsiedztwo


def web_mercator(lon: float, lat: float) -> tuple[float, float]:
    return _R * math.radians(lon), _R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def polozenie(geometria: BaseGeometry) -> dict:
    punkt = geometria.representative_point()
    lat, lon = punkt.y, punkt.x
    return {"lat": lat, "lon": lon, "uklady": [uklady.pl1992(lat, lon), uklady.pl2000(lat, lon)] if uklady.w_polsce(lat, lon) else []}


def prostokat(geometria: BaseGeometry) -> tuple[float, float, float, float]:
    """Prostokąt w EPSG:3857 wokół działki o proporcjach obrazu."""
    xs, ys = zip(*(web_mercator(x, y) for x, y in geometria.envelope.exterior.coords))
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    szer, wys = (maxx - minx) * (1 + 2 * MARGINES), (maxy - miny) * (1 + 2 * MARGINES)
    szer, wys = max(szer, 60.0), max(wys, 60.0)  # nawet mała działka — co najmniej 60 m widoku
    proporcja = SZEROKOSC_PX / WYSOKOSC_PX
    if szer / wys < proporcja:
        szer = wys * proporcja
    else:
        wys = szer / proporcja
    sx, sy = (minx + maxx) / 2, (miny + maxy) / 2
    return sx - szer / 2, sy - wys / 2, sx + szer / 2, sy + wys / 2


def adres_obrazu(url: str, warstwa: str, bbox: tuple, czas: str | None = None) -> str:
    parametry = {
        "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": warstwa, "STYLES": "",
        "CRS": "EPSG:3857", "BBOX": ",".join(f"{v:.2f}" for v in bbox),
        "WIDTH": SZEROKOSC_PX, "HEIGHT": WYSOKOSC_PX, "FORMAT": "image/jpeg",
    }
    if czas:
        parametry["TIME"] = czas
    return f"{url}?{urlencode(parametry)}"


def obrys_svg(geometria: BaseGeometry, bbox: tuple) -> str:
    """Ścieżka SVG obrysu działki w pikselach obrazu (viewBox 0 0 640 480)."""
    minx, miny, maxx, maxy = bbox

    def piksel(lon, lat):
        x, y = web_mercator(lon, lat)
        return (x - minx) / (maxx - minx) * SZEROKOSC_PX, (maxy - y) / (maxy - miny) * WYSOKOSC_PX

    wieloboki = geometria.geoms if geometria.geom_type == "MultiPolygon" else [geometria]
    czesci = []
    for w in wieloboki:
        for pierscien in [w.exterior, *w.interiors]:
            czesci.append("M" + " L".join("%.1f,%.1f" % piksel(x, y) for x, y in pierscien.coords) + " Z")
    return " ".join(czesci)
