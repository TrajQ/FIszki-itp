"""Projekt terenowy jako GeoPackage dla QGIS (ETAP 214).

Warstwa „punkty” w PL-1992 (EPSG:2180): położenie, czas, dokładność GPS
i wartości pól formularza jako kolumny (liczby jako liczby, wielokrotny
wybór jako tekst „a; b”). Styl: kolor wg pierwszego pola wyboru albo
tak/nie — te same kolory co mapa projektu i raport (teren/raport.py).
"""

from shapely.geometry import Point

from dane.geopaczka import geopackage, styl_kategorie, styl_pojedynczy, symbol_punktu
from mpzp.uklady import pl1992

from .raport import KOLOR_BRAK, KOLOR_JEDNOLITY, kolory_pola

EPSG = 2180
STALE_KOLUMNY = ("id", "czas", "dokladnosc_m", "polozenie_reczne", "uwagi", "zdjecie", "zdjecie_opis", "zdjecie_kierunek")


def _kolumny_pol(pola: list[dict]) -> dict[str, str]:
    """Nazwa pola → nazwa kolumny, różna od stałych kolumn i od siebie (bez rozróżniania wielkości liter, jak SQLite)."""
    zajete = {k.lower() for k in STALE_KOLUMNY + ("fid", "geom")}
    wynik = {}
    for p in pola:
        kolumna, n = p["nazwa"], 1
        while kolumna.lower() in zajete:
            n += 1
            kolumna = f"{p['nazwa']}_{n}"
        zajete.add(kolumna.lower())
        wynik[p["nazwa"]] = kolumna
    return wynik


def _wartosc(w, typ: str):
    if isinstance(w, list):
        return "; ".join(map(str, w))
    if isinstance(w, bool):
        return "tak" if w else "nie"
    if typ == "liczba" and isinstance(w, (int, float)):
        return float(w)
    return None if w in (None, "") else str(w)


def projekt_gpkg(projekt: dict, punkty: list[dict]) -> bytes:
    pola = projekt["pola"]
    kolumna = _kolumny_pol(pola)
    kolumny = [("id", "INTEGER"), ("czas", "TEXT"), ("dokladnosc_m", "REAL"), ("polozenie_reczne", "INTEGER"),
               *[(kolumna[p["nazwa"]], "REAL" if p["typ"] == "liczba" else "TEXT") for p in pola], ("uwagi", "TEXT"), ("zdjecie", "TEXT"),
               ("zdjecie_opis", "TEXT"), ("zdjecie_kierunek", "INTEGER")]  # ETAP 219: kierunek w stopniach od północy
    obiekty = []
    for pt in punkty:
        if pt["lat"] is None:
            continue
        xy = pl1992(pt["lat"], pt["lng"])
        atrybuty = {"id": pt["id"], "czas": pt["czas"], "dokladnosc_m": pt["dokladnosc_m"], "polozenie_reczne": int(bool(pt["polozenie_reczne"])),
                    "uwagi": pt["uwagi"], "zdjecie": pt["zdjecie"],
                    "zdjecie_opis": pt.get("zdjecie_opis"), "zdjecie_kierunek": pt.get("zdjecie_kierunek")}
        for p in pola:
            atrybuty[kolumna[p["nazwa"]]] = _wartosc(pt["wartosci"].get(p["nazwa"]), p["typ"])
        obiekty.append((Point(xy["y"], xy["x"]), atrybuty))  # PL-1992: x = północ, y = wschód; w GIS: X = wschód
    pole_koloru = next((p for p in pola if p["typ"] in ("wybor", "tak_nie")), None)
    if pole_koloru:
        styl = styl_kategorie(kolumna[pole_koloru["nazwa"]],
                              [(w, w, symbol_punktu(k)) for w, k in kolory_pola(pole_koloru).items()] + [("", "(brak wartości)", symbol_punktu(KOLOR_BRAK))])
    else:
        styl = styl_pojedynczy(symbol_punktu(KOLOR_JEDNOLITY))
    return geopackage([{"nazwa": "punkty", "typ": "POINT", "kolumny": kolumny, "obiekty": obiekty, "styl_qml": styl,
                        "opis": f"Projekt terenowy „{projekt['nazwa']}” (Warsztat)"}], EPSG)
