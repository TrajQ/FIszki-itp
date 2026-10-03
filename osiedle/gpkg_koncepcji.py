"""Koncepcja osiedla jako GeoPackage dla QGIS (ETAP 213).

Cztery warstwy w układzie PL-1992 (EPSG:2180), każda ze stylem QML
zapisanym w pliku (tabela layer_styles — QGIS wczytuje go jako domyślny):

- tereny — wieloboki z funkcją (kolory jak w aplikacji), numerem jak w
  raporcie, parametrami (zabudowa, kondygnacje, PBC), etapem i polem m²,
- budynki — obrysy z kondygnacjami i rzutem,
- obszar — granica opracowania (sam kontur),
- linia_zabudowy — nieprzekraczalna linia (czerwona przerywana).

Liczby (pola) liczy kod z geometrii w metrach układu, jak reszta modułu.
Warstwy bez obiektów pomijamy.
"""

from shapely.geometry import MultiPolygon, shape
from shapely.ops import transform

from dane.geopaczka import geopackage, styl_kategorie, styl_pojedynczy, symbol_linii, symbol_wypelnienia
from mpzp.uklady import gauss_kruger

from . import wskazniki as wsk
from .bilans import BUDYNEK, DOMYSLNE_KONDYGNACJE_BUDYNKU, FUNKCJE, KOLOR_BUDYNKU, KOLOR_LINII, LINIA, OBSZAR
from .etapy import etap_terenu

EPSG = 2180


def _na_pl1992(geometria):
    def przelicz(lon, lat, z=None):
        wynik = [gauss_kruger(b, a, 19.0, 0.9993) for a, b in zip(lon, lat)]
        return [w + 500_000 for _, w in wynik], [p - 5_300_000 for p, _ in wynik]
    return transform(przelicz, geometria)


def styl_terenow() -> str:
    """Styl kategoryzowany po kolumnie „funkcja” — kolory jak na mapie w aplikacji."""
    return styl_kategorie("funkcja", [(kod, f"{kod} — {f['nazwa']}", symbol_wypelnienia(f["kolor"])) for kod, f in FUNKCJE.items()])


def styl_budynkow() -> str:
    return styl_pojedynczy(symbol_wypelnienia(KOLOR_BUDYNKU, 230, obrys="#ffffff", szerokosc_obrysu=0.2))


def styl_obszaru() -> str:
    return styl_pojedynczy(symbol_wypelnienia("", obrys="#1d1d1f", szerokosc_obrysu=0.6))


def styl_linii() -> str:
    return styl_pojedynczy(symbol_linii(KOLOR_LINII, 0.6, "dash"))


def koncepcja_gpkg(geojson: dict, nazwa: str) -> bytes:
    """GeoJSON koncepcji (WGS84) → plik GeoPackage w PL-1992."""
    tereny, budynki, obszary, linie = [], [], [], []
    nr_terenu = nr_budynku = 0
    for cecha in geojson.get("features", []):
        if not cecha.get("geometry"):
            continue
        wlasciwosci = cecha.get("properties") or {}
        funkcja = wlasciwosci.get("funkcja")
        g = _na_pl1992(shape(cecha["geometry"]))
        if not g.is_valid:
            g = g.buffer(0)
        if g.geom_type == "Polygon":
            g = MultiPolygon([g])  # jeden typ geometrii w warstwie — QGIS nie pyta o typ przy otwieraniu
        if funkcja in FUNKCJE:
            nr_terenu += 1
            p = wsk.parametry_terenu(funkcja, wlasciwosci)
            tereny.append((g, {"nr": nr_terenu, "funkcja": funkcja, "nazwa": FUNKCJE[funkcja]["nazwa"], "etykieta": f"{funkcja} {nr_terenu}",
                               "zabudowa_proc": p.get("zabudowa_proc"), "kondygnacje": p.get("kondygnacje"), "pbc_proc": p["pbc_proc"],
                               "etap": etap_terenu(funkcja, wlasciwosci), "pole_m2": round(g.area, 1), "koncepcja": nazwa}))
        elif funkcja == BUDYNEK:
            nr_budynku += 1
            kondygnacje = wlasciwosci.get("kondygnacje") or DOMYSLNE_KONDYGNACJE_BUDYNKU
            budynki.append((g, {"nr": nr_budynku, "kondygnacje": kondygnacje, "rzut_m2": round(g.area, 1),
                                "calkowita_m2": round(g.area * float(kondygnacje), 1)}))
        elif funkcja == OBSZAR:
            obszary.append((g, {"pole_m2": round(g.area, 1), "koncepcja": nazwa}))
        elif funkcja == LINIA:
            linie.append((g, {"dlugosc_m": round(g.length, 1)}))
    warstwy = [
        {"nazwa": "tereny", "typ": "MULTIPOLYGON", "obiekty": tereny, "styl_qml": styl_terenow(), "opis": "Tereny koncepcji z funkcją",
         "kolumny": [("nr", "INTEGER"), ("funkcja", "TEXT"), ("nazwa", "TEXT"), ("etykieta", "TEXT"), ("zabudowa_proc", "REAL"),
                     ("kondygnacje", "REAL"), ("pbc_proc", "REAL"), ("etap", "INTEGER"), ("pole_m2", "REAL"), ("koncepcja", "TEXT")]},
        {"nazwa": "budynki", "typ": "MULTIPOLYGON", "obiekty": budynki, "styl_qml": styl_budynkow(), "opis": "Obrysy budynków",
         "kolumny": [("nr", "INTEGER"), ("kondygnacje", "REAL"), ("rzut_m2", "REAL"), ("calkowita_m2", "REAL")]},
        {"nazwa": "obszar", "typ": "MULTIPOLYGON", "obiekty": obszary, "styl_qml": styl_obszaru(), "opis": "Obszar opracowania",
         "kolumny": [("pole_m2", "REAL"), ("koncepcja", "TEXT")]},
        {"nazwa": "linia_zabudowy", "typ": "LINESTRING", "obiekty": linie, "styl_qml": styl_linii(), "opis": "Nieprzekraczalna linia zabudowy",
         "kolumny": [("dlugosc_m", "REAL")]},
    ]
    return geopackage([w for w in warstwy if w["obiekty"]], EPSG)
