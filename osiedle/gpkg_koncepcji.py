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

from xml.sax.saxutils import quoteattr

from shapely.geometry import MultiPolygon, shape
from shapely.ops import transform

from dane.geopaczka import geopackage
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


def _rgb(kolor: str, alfa: int = 255) -> str:
    kolor = kolor.lstrip("#")
    return f"{int(kolor[0:2], 16)},{int(kolor[2:4], 16)},{int(kolor[4:6], 16)},{alfa}"


def _symbol(nazwa: str, typ: str, warstwa: str) -> str:
    return f'<symbol type="{typ}" name="{nazwa}" alpha="1" clip_to_extent="1" force_rhr="0">{warstwa}</symbol>'


def _wypelnienie(kolor: str, alfa: int, obrys: str = "35,35,35,255", styl: str = "solid", szerokosc: float = 0.26) -> str:
    return ('<layer class="SimpleFill" enabled="1" locked="0" pass="0"><Option type="Map">'
            f'<Option type="QString" name="color" value="{_rgb(kolor, alfa) if kolor else "0,0,0,0"}"/>'
            f'<Option type="QString" name="style" value="{styl}"/>'
            f'<Option type="QString" name="outline_color" value="{obrys}"/>'
            f'<Option type="QString" name="outline_width" value="{szerokosc}"/>'
            '<Option type="QString" name="outline_width_unit" value="MM"/>'
            '</Option></layer>')


def _qml(renderer: str) -> str:
    return f'<!DOCTYPE qgis PUBLIC \'http://mrcc.com/qgis.dtd\' \'SYSTEM\'><qgis version="3.28.0" styleCategories="Symbology">{renderer}</qgis>'


def styl_terenow() -> str:
    """Styl kategoryzowany po kolumnie „funkcja” — kolory jak na mapie w aplikacji."""
    kategorie = "".join(f'<category render="true" symbol="{i}" value={quoteattr(kod)} label={quoteattr(kod + " — " + f["nazwa"])}/>'
                        for i, (kod, f) in enumerate(FUNKCJE.items()))
    symbole = "".join(_symbol(str(i), "fill", _wypelnienie(f["kolor"], 170)) for i, f in enumerate(FUNKCJE.values()))
    return _qml(f'<renderer-v2 type="categorizedSymbol" attr="funkcja" symbollevels="0" enableorderby="0" forceraster="0">'
                f'<categories>{kategorie}</categories><symbols>{symbole}</symbols></renderer-v2>')


def _pojedynczy(symbol: str) -> str:
    return _qml(f'<renderer-v2 type="singleSymbol" symbollevels="0" enableorderby="0" forceraster="0"><symbols>{symbol}</symbols></renderer-v2>')


def styl_budynkow() -> str:
    return _pojedynczy(_symbol("0", "fill", _wypelnienie(KOLOR_BUDYNKU, 230, obrys="255,255,255,255", szerokosc=0.2)))


def styl_obszaru() -> str:
    return _pojedynczy(_symbol("0", "fill", _wypelnienie("", 0, obrys="29,29,31,255", szerokosc=0.6)))


def styl_linii() -> str:
    linia = ('<layer class="SimpleLine" enabled="1" locked="0" pass="0"><Option type="Map">'
             f'<Option type="QString" name="line_color" value="{_rgb(KOLOR_LINII)}"/>'
             '<Option type="QString" name="line_width" value="0.6"/><Option type="QString" name="line_width_unit" value="MM"/>'
             '<Option type="QString" name="line_style" value="dash"/></Option></layer>')
    return _pojedynczy(_symbol("0", "line", linia))


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
