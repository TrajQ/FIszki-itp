"""Działka i jej części w przeznaczeniach planu jako DXF (ETAP 123).

Te same obiekty co eksport GeoJSON: obrys działki (warstwa DZIALKA) i —
gdzie gmina ma WFS — części działki w przeznaczeniach (warstwa
PRZEZN_<symbol>), z opisami: numer działki z powierzchnią i symbol
przeznaczenia. Współrzędne w PL-2000 (strefa wg położenia działki) albo
PL-1992, X = wschód, Y = północ (dane/dxf.py).
"""

from shapely.geometry import shape

from dane.dxf import KOLORY_ACI, dxf, nazwa_ascii

from .uklady import gauss_kruger, strefa_pl2000

UKLADY = ("pl2000", "pl1992")
KOLORY_CZESCI = ["zielony", "pomaranczowy", "niebieski", "magenta", "czerwony", "cyjan"]  # jak KOLORY_RAPORTU
WYSOKOSC_OPISU_M = 1.5


def _przelicznik(uklad: str, lon_srodka: float):
    if uklad == "pl1992":
        def na_metry(lon, lat):
            polnoc, wschod = gauss_kruger(lat, lon, 19.0, 0.9993)
            return wschod + 500_000, polnoc - 5_300_000
        return na_metry, "PL-1992 (EPSG:2180)"
    strefa = strefa_pl2000(lon_srodka)

    def na_metry(lon, lat):
        polnoc, wschod = gauss_kruger(lat, lon, 3.0 * strefa, 0.999923)
        return strefa * 1_000_000 + 500_000 + wschod, polnoc
    return na_metry, f"PL-2000 strefa {strefa} (EPSG:{2171 + strefa})"


def _pierscienie(geometria):
    for wielobok in getattr(geometria, "geoms", [geometria]):
        if wielobok.geom_type == "Polygon":
            yield from [wielobok.exterior, *wielobok.interiors]


def dzialka_dxf(cechy: list[dict], uklad: str = "pl2000") -> tuple[str, str]:
    """cechy jak w eksporcie GeoJSON MPZP (pierwsza — działka) → (DXF, opis układu)."""
    dzialka = shape(cechy[0]["geometry"])
    na_metry, opis = _przelicznik(uklad, dzialka.centroid.x)
    warstwy = {"DZIALKA": KOLORY_ACI["czerwony"], "OPISY": KOLORY_ACI["bialy"]}
    obiekty = []
    kolory: dict[str, str] = {}
    for c in cechy[1:]:  # części działki w przeznaczeniach (tylko gminy z WFS)
        symbol = str(c["properties"].get("przeznaczenie") or "BRAK")
        warstwa = f"PRZEZN_{nazwa_ascii(symbol)}"
        kolory.setdefault(symbol, KOLORY_CZESCI[len(kolory) % len(KOLORY_CZESCI)])
        warstwy.setdefault(warstwa, KOLORY_ACI[kolory[symbol]])
        czesc = shape(c["geometry"])
        for pierscien in _pierscienie(czesc):
            obiekty.append({"warstwa": warstwa, "wielobok": [na_metry(x, y) for x, y in pierscien.coords]})
        if not czesc.is_empty:
            p = czesc.representative_point()
            obiekty.append({"warstwa": "OPISY", "tekst": symbol, "punkt": na_metry(p.x, p.y), "wysokosc": WYSOKOSC_OPISU_M})
    for pierscien in _pierscienie(dzialka):  # obrys działki na wierzchu
        obiekty.append({"warstwa": "DZIALKA", "wielobok": [na_metry(x, y) for x, y in pierscien.coords]})
    wlasciwosci = cechy[0]["properties"]
    p = dzialka.representative_point()
    numer = ".".join(wlasciwosci["id_dzialki"].split(".")[2:]) or wlasciwosci["id_dzialki"]  # jak w raporcie: po jednostce i obrębie
    opis_dzialki = f"{numer} ({wlasciwosci['powierzchnia_m2']:.0f} m2)"
    if wlasciwosci.get("przeznaczenie_kimpzp"):
        opis_dzialki += f" {wlasciwosci['przeznaczenie_kimpzp']}"
    x, y = na_metry(p.x, p.y)
    obiekty.append({"warstwa": "OPISY", "tekst": opis_dzialki, "punkt": (x, y - 2 * WYSOKOSC_OPISU_M), "wysokosc": WYSOKOSC_OPISU_M})
    return dxf(warstwy, obiekty), opis
