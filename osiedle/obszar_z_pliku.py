"""Obszar opracowania z pliku GeoJSON (ETAP 138).

Granica opracowania często już jest — narysowana w QGIS albo wyeksportowana
z modułu MPZP. Plik może być w WGS84 (EPSG:4326, domyślny w GeoJSON) albo
w polskich układach płaskich: PL-1992 (EPSG:2180) i PL-2000 (EPSG:2176–2179).
Układ bierzemy z pola „crs” (QGIS je zapisuje), a gdy go nie ma — z zakresu
liczb: stopnie, PL-2000 (wschód zaczyna się od numeru strefy 5–8) i PL-1992
mają rozłączne zakresy, więc pomyłka nie jest możliwa.
"""

import re

from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import transform, unary_union
from shapely.validation import make_valid

from mpzp.uklady import w_polsce, wgs84_z_pl1992, wgs84_z_pl2000

from .bilans import BladKoncepcji

MAKS_OBIEKTOW = 500
WIELOBOKI = ("Polygon", "MultiPolygon")


def _geometrie(dane) -> list[dict]:
    """FeatureCollection, pojedynczy Feature albo sama geometria → lista geometrii."""
    if not isinstance(dane, dict):
        raise BladKoncepcji("To nie jest plik GeoJSON.")
    if dane.get("type") == "FeatureCollection":
        cechy = dane.get("features")
        if not isinstance(cechy, list):
            raise BladKoncepcji("To nie jest plik GeoJSON.")
        if len(cechy) > MAKS_OBIEKTOW:
            raise BladKoncepcji(f"Najwyżej {MAKS_OBIEKTOW} obiektów w pliku — zostaw w QGIS tylko granicę opracowania.")
        return [(c or {}).get("geometry") or {} for c in cechy if isinstance(c, dict)]
    if dane.get("type") == "Feature":
        return [dane.get("geometry") or {}]
    return [dane]


def _uklad_z_crs(dane: dict) -> str | None:
    """„crs” w stylu GeoJSON 2008 (QGIS): urn:ogc:def:crs:EPSG::2180 itp."""
    nazwa = str(((dane.get("crs") or {}).get("properties") or {}).get("name") or "")
    m = re.search(r"EPSG:+(\d+)", nazwa)
    if m is None:
        return "wgs84" if "CRS84" in nazwa else None
    kod = int(m.group(1))
    if kod == 4326:
        return "wgs84"
    if kod == 2180:
        return "pl1992"
    if 2176 <= kod <= 2179:
        return "pl2000"
    raise BladKoncepcji(f"Nieobsługiwany układ EPSG:{kod} — w QGIS zapisz plik w EPSG:4326, 2180 albo 2176–2179.")


def _uklad_z_liczb(x: float, y: float) -> str:
    """x, y jak w GeoJSON: pierwsza współrzędna — wschód / długość."""
    if abs(x) <= 180 and abs(y) <= 90:
        return "wgs84"
    if 5_000_000 <= x < 9_000_000 and 5_400_000 <= y <= 6_200_000:
        return "pl2000"
    if 100_000 <= x <= 900_000 and 100_000 <= y <= 800_000:
        return "pl1992"
    raise BladKoncepcji("Nie rozpoznaję układu współrzędnych — w QGIS zapisz plik w EPSG:4326 (WGS84) albo 2180 (PL-1992).")


PRZELICZENIA = {
    "wgs84": None,
    # GeoJSON: (wschód, północ); funkcje z uklady.py: (północ, wschód) → (szer., dł.)
    "pl1992": lambda e, n, z=None: tuple(reversed(wgs84_z_pl1992(n, e))),
    "pl2000": lambda e, n, z=None: tuple(reversed(wgs84_z_pl2000(n, e))),
}
OPISY_UKLADOW = {"wgs84": "WGS84", "pl1992": "PL-1992", "pl2000": "PL-2000"}


def _tylko_wieloboki(g):
    if isinstance(g, (Polygon, MultiPolygon)):
        return g
    czesci = [c for c in getattr(g, "geoms", []) if isinstance(c, (Polygon, MultiPolygon))]
    return unary_union(czesci) if czesci else None


def obszar_z_geojson(dane) -> tuple[Polygon | MultiPolygon, str]:
    """→ (granica w WGS84, nazwa układu pliku). Wieloboki z pliku są sumowane;
    punkty i linie pomijane."""
    geometrie = [g for g in _geometrie(dane) if isinstance(g, dict) and g.get("type") in WIELOBOKI]
    if not geometrie:
        raise BladKoncepcji("W pliku nie ma wieloboków (Polygon / MultiPolygon) — granica opracowania musi być powierzchnią.")
    try:
        ksztalty = [shape(g) for g in geometrie]
    except (ValueError, TypeError, AttributeError, IndexError):
        raise BladKoncepcji("Uszkodzona geometria w pliku GeoJSON.") from None
    ksztalty = [k for k in ksztalty if not k.is_empty]
    if not ksztalty:
        raise BladKoncepcji("Wieloboki w pliku są puste.")
    suma = unary_union([make_valid(k) for k in ksztalty])
    uklad = _uklad_z_crs(dane) or _uklad_z_liczb(*suma.representative_point().coords[0])
    if PRZELICZENIA[uklad] is not None:
        try:
            suma = transform(PRZELICZENIA[uklad], suma)
        except ValueError as e:
            raise BladKoncepcji(str(e)) from None
    obszar = _tylko_wieloboki(make_valid(suma))
    if obszar is None or obszar.is_empty:
        raise BladKoncepcji("Wieloboki w pliku są puste.")
    punkt = obszar.representative_point()
    if not w_polsce(punkt.y, punkt.x):
        raise BladKoncepcji("Obszar z pliku leży poza Polską — sprawdź układ współrzędnych (w QGIS: EPSG:4326 albo 2180).")
    return obszar, OPISY_UKLADOW[uklad]
