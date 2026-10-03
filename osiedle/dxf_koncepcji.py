"""Koncepcja osiedla jako DXF do programu CAD (ETAP 122).

Każda funkcja terenu (MN, MW, U, ZP, KD, KS, WS) to osobna warstwa
OSIEDLE_<symbol> w kolorze zbliżonym do aplikacji, obszar opracowania —
warstwa OSIEDLE_OBSZAR, opisy (symbol i numer terenu jak w raporcie) —
OSIEDLE_OPISY. Współrzędne w metrach w układzie PL-2000 (strefa wg
środka koncepcji, jedna dla całego rysunku — jak na mapie zasadniczej)
albo PL-1992; w konwencji CAD: X = wschód, Y = północ.
"""

from shapely.geometry import shape
from shapely.ops import unary_union

from dane.dxf import KOLORY_ACI, dxf
from mpzp.uklady import gauss_kruger, strefa_pl2000

from .bilans import FUNKCJE, LINIA, OBSZAR

KOLORY_FUNKCJI = {"MN": "zolty", "MW": "pomaranczowy", "U": "czerwony", "ZP": "zielony", "KD": "szary",
                  "KS": "jasnoszary", "WS": "niebieski", OBSZAR: "bialy", LINIA: "czerwony"}
UKLADY = ("pl2000", "pl1992")
WYSOKOSC_OPISU_M = 4.0


def _przelicznik(uklad: str, srodek_lon: float):
    """(lon, lat) → (X wschód, Y północ) w metrach wybranego układu."""
    if uklad == "pl1992":
        def na_metry(lon, lat):
            polnoc, wschod = gauss_kruger(lat, lon, 19.0, 0.9993)
            return wschod + 500_000, polnoc - 5_300_000
        return na_metry, "PL-1992 (EPSG:2180)"
    strefa = strefa_pl2000(srodek_lon)

    def na_metry(lon, lat):
        polnoc, wschod = gauss_kruger(lat, lon, 3.0 * strefa, 0.999923)
        return strefa * 1_000_000 + 500_000 + wschod, polnoc
    return na_metry, f"PL-2000 strefa {strefa} (EPSG:{2171 + strefa})"


def koncepcja_dxf(geojson: dict, uklad: str = "pl2000") -> tuple[str, str]:
    """→ (tekst DXF, opis układu). Pusta koncepcja → DXF bez obiektów."""
    cechy = [c for c in geojson.get("features", []) if c.get("geometry")]
    srodek_lon = unary_union([shape(c["geometry"]) for c in cechy]).centroid.x if cechy else 19.0
    na_metry, opis_ukladu = _przelicznik(uklad, srodek_lon)
    warstwy, obiekty, nr = {"OSIEDLE_OPISY": KOLORY_ACI["bialy"]}, [], 0
    for c in cechy:
        funkcja = c["properties"].get("funkcja") or "INNE"
        warstwa = f"OSIEDLE_{funkcja.upper()}"
        warstwy.setdefault(warstwa, KOLORY_ACI[KOLORY_FUNKCJI.get(funkcja, "bialy")])
        geometria = shape(c["geometry"])
        if geometria.geom_type == "LineString":  # linia zabudowy (ETAP 175)
            obiekty.append({"warstwa": warstwa, "linia": [na_metry(lon, lat) for lon, lat in geometria.coords]})
            continue
        for wielobok in getattr(geometria, "geoms", [geometria]):
            for pierscien in [wielobok.exterior, *wielobok.interiors]:
                obiekty.append({"warstwa": warstwa, "wielobok": [na_metry(lon, lat) for lon, lat in pierscien.coords]})
        if funkcja in FUNKCJE:  # bez obszaru i budynków (ETAP 173)
            nr += 1  # numeracja terenów jak w raporcie (kolejność rysunku, bez obszaru)
            punkt = geometria.representative_point()
            obiekty.append({"warstwa": "OSIEDLE_OPISY", "tekst": f"{funkcja} {nr}", "punkt": na_metry(punkt.x, punkt.y),
                            "wysokosc": WYSOKOSC_OPISU_M})
    return dxf(warstwy, obiekty), opis_ukladu
