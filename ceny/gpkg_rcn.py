"""Transakcje RCN jako GeoPackage dla QGIS (ETAP 214).

Dwie warstwy w PL-1992 (EPSG:2180), z filtrami strony:
- transakcje — punkty z datą, rynkiem, powierzchnią, ceną i ceną za m²;
  styl: pięć klas ceny za m² (kwintyle) w kolorach mapy transakcji,
- obszary — narysowane obszary z liczbą transakcji i medianą; kontury w
  kolorach obszarów ze strony.
"""

import statistics

from shapely.geometry import MultiPolygon, Point, shape
from shapely.ops import transform

from dane.geopaczka import geopackage, styl_kategorie, styl_przedzialy, symbol_punktu, symbol_wypelnienia
from mpzp.uklady import pl1992

from .rcn import KOLORY_KLAS, KOLORY_OBSZAROW

EPSG = 2180


def _xy(lat: float, lng: float) -> tuple[float, float]:
    p = pl1992(lat, lng)
    return p["y"], p["x"]  # X = wschód, Y = północ


def _klasy(ceny: list[float]) -> list[tuple[float, float, str, tuple[str, str]]]:
    if len(ceny) < 5:
        return [(min(ceny), max(ceny), "wszystkie", symbol_punktu(KOLORY_KLAS[2]))] if ceny else []
    progi = statistics.quantiles(ceny, n=5, method="inclusive")
    granice = [min(ceny), *progi, max(ceny)]
    return [(granice[i], granice[i + 1], f"{round(granice[i]):,} – {round(granice[i + 1]):,} zł/m²".replace(",", " "), symbol_punktu(KOLORY_KLAS[i]))
            for i in range(5)]


def rcn_gpkg(rekordy: list[dict], obszary: list[dict], porownanie: dict, co: str) -> bytes:
    pola = [("data", "TEXT"), ("rynek", "TEXT"), ("rodzaj", "TEXT"), ("pow_m2", "REAL"), ("cena", "REAL"), ("cena_m2", "REAL")]
    pola += [("przeznaczenie", "TEXT"), ("uzytek", "TEXT"), ("nieruchomosc", "TEXT"), ("dzialek", "INTEGER")] if co == "dzialki" \
        else [("izby", "INTEGER"), ("kondygnacja", "INTEGER")]
    punkty = [(Point(*_xy(r["lat"], r["lng"])), {k: r.get(k) for k, _ in pola})
              for r in sorted(rekordy, key=lambda r: r["data"]) if r["lat"] is not None]
    warstwy = [{"nazwa": "transakcje", "typ": "POINT", "kolumny": pola, "obiekty": punkty,
                "styl_qml": styl_przedzialy("cena_m2", _klasy([a["cena_m2"] for _, a in punkty])),
                "opis": "Transakcje z Rejestru Cen Nieruchomości (GUGiK)"}]
    if obszary:
        def przelicz(lon, lat, z=None):
            xy = [_xy(b, a) for a, b in zip(lon, lat)]
            return [x for x, _ in xy], [y for _, y in xy]
        wieloboki = []
        for nr, (o, w) in enumerate(zip(obszary, porownanie["obszary"]), start=1):
            g = transform(przelicz, shape(o["geometria"]))
            wieloboki.append((g if g.geom_type == "MultiPolygon" else MultiPolygon([g]),
                              {"nr": nr, "nazwa": o["nazwa"], "liczba": w["liczba"], "mediana_m2": w.get("mediana_m2")}))
        warstwy.append({"nazwa": "obszary", "typ": "MULTIPOLYGON", "obiekty": wieloboki, "opis": "Obszary narysowane na mapie transakcji",
                        "kolumny": [("nr", "INTEGER"), ("nazwa", "TEXT"), ("liczba", "INTEGER"), ("mediana_m2", "REAL")],
                        "styl_qml": styl_kategorie("nr", [(nr, f"{nr}. {o['nazwa']}", symbol_wypelnienia("", obrys=KOLORY_OBSZAROW[(nr - 1) % len(KOLORY_OBSZAROW)], szerokosc_obrysu=0.8))
                                                          for nr, o in enumerate(obszary, start=1)])})
    return geopackage(warstwy, EPSG)
