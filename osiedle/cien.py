"""Odległości od granicy obszaru i możliwy cień terenów zabudowy (ETAP 94).

Koncepcja składa się z terenów o funkcjach, a nie z budynków — nie wiemy,
gdzie na terenie MW stanie blok. Dlatego liczymy NAJGORSZY PRZYPADEK:
budynki mogą stać przy samej krawędzi terenu.

1. Odległość terenu zabudowy (MN, MW, U) od granicy obszaru opracowania
   (np. granicy działek z ULDK). 0 m znaczy, że budynki trzeba będzie
   odsunąć od granicy — minimalne odległości budynku od granicy działki
   podaje § 12 rozporządzenia w sprawie warunków technicznych.
2. Strefa możliwego cienia: wysokość = kondygnacje × WYSOKOSC_KONDYGNACJI_M,
   położenie słońca ze wzorów astronomicznych dla szerokości koncepcji i
   wybranego dnia, co godzinę od 9 do 15 (czas słoneczny, tzn. 12:00 =
   słońce najwyżej). Cień terenu w danej godzinie to teren „przesunięty”
   o długość cienia w stronę przeciwną do słońca; strefa to suma tych
   śladów poza samym terenem. Pokazujemy, jaka część terenów MN, MW i ZP
   leży w tej strefie — to miejsca, gdzie przy wysokiej zabudowie przy
   krawędzi trzeba sprawdzić nasłonecznienie (§ 60 tego rozporządzenia)
   i przesłanianie (§ 13) na projekcie budynków.

To przybliżenie do porównania wariantów, nie analiza nasłonecznienia.

ETAP 195: gdy koncepcja ma narysowane budynki (ETAP 173), cień liczymy od
budynków (obrys i ich kondygnacje) zamiast od całych terenów zabudowy —
to już nie najgorszy przypadek, tylko konkretny rysunek. Cień na samych
budynkach nie wlicza się do strefy.
"""

import math

from shapely.affinity import scale, translate
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union

from .bilans import _w_metrach, metry_na_stopien, wczytaj_budynki, wczytaj_tereny
from . import wskazniki as wsk

WYSOKOSC_KONDYGNACJI_M = 3.0
GODZINY = range(9, 16)  # czas słoneczny
# Deklinacja słońca w wybranych dniach (równonoc, przesilenia).
DNI = {
    "rownonoc": ("21 marca / 23 września (równonoc)", 0.0),
    "lato": ("21 czerwca (przesilenie letnie)", 23.44),
    "zima": ("21 grudnia (przesilenie zimowe)", -23.44),
}
FUNKCJE_CHRONIONE = ("MN", "MW", "ZP")  # mieszkania i zieleń — tu cień ma znaczenie


class BladCienia(ValueError):
    """Zły parametr analizy cienia."""


def polozenie_slonca(szerokosc: float, deklinacja: float, godzina: float) -> tuple[float, float]:
    """(wysokość nad horyzontem, azymut od północy zgodnie z ruchem wskazówek) w stopniach."""
    fi, d = math.radians(szerokosc), math.radians(deklinacja)
    h = math.radians(15 * (godzina - 12))  # kąt godzinny
    sin_a = math.sin(fi) * math.sin(d) + math.cos(fi) * math.cos(d) * math.cos(h)
    wysokosc = math.asin(max(-1.0, min(1.0, sin_a)))
    azymut = math.atan2(math.sin(h), math.cos(h) * math.sin(fi) - math.tan(d) * math.cos(fi)) + math.pi
    return math.degrees(wysokosc), math.degrees(azymut) % 360


def _slad(geometria, dx: float, dy: float):
    """Obszar, który zakrywa figura przesuwana o wektor (dx, dy) — suma
    czworoboków z każdej krawędzi i obu położeń figury (suma Minkowskiego
    z odcinkiem)."""
    czesci = [geometria, translate(geometria, dx, dy)]
    wielokaty = getattr(geometria, "geoms", [geometria])
    for w in wielokaty:
        for pierscien in [w.exterior, *w.interiors]:
            punkty = list(pierscien.coords)
            for (x1, y1), (x2, y2) in zip(punkty, punkty[1:]):
                czworobok = Polygon([(x1, y1), (x2, y2), (x2 + dx, y2 + dy), (x1 + dx, y1 + dy)])
                if czworobok.area > 0:
                    czesci.append(czworobok)
    return unary_union(czesci)


def analiza(geojson: dict, dzien: str = "rownonoc") -> dict:
    if dzien not in DNI:
        raise BladCienia("Dzień: rownonoc, lato albo zima.")
    obszar, tereny = wczytaj_tereny(geojson)
    budynki = wczytaj_budynki(geojson)
    for t in tereny:
        t["parametry"] = wsk.parametry_terenu(t["funkcja"], t["wlasciwosci"])
    wszystko = [t["geometria"] for t in tereny] + [b["geometria"] for b in budynki] + ([obszar] if obszar is not None else [])
    if not wszystko:
        return {"dzien": DNI[dzien][0], "tereny": [], "zacienione": [], "strefa": None, "slonce": []}
    szerokosc = unary_union(wszystko).centroid.y
    mx, my = metry_na_stopien(szerokosc)
    opis_dnia, deklinacja = DNI[dzien]
    slonce = []
    for g in GODZINY:
        wys, az = polozenie_slonca(szerokosc, deklinacja, g)
        slonce.append({"godzina": g, "wysokosc": round(wys, 1), "azymut": round(az, 1)})

    granica = _w_metrach(obszar, szerokosc).boundary if obszar is not None else None
    # źródła cienia: budynki, gdy są narysowane, inaczej tereny zabudowy (najgorszy przypadek)
    if budynki:
        zrodla = [("budynek", nr, b["geometria"], b["kondygnacje"]) for nr, b in enumerate(budynki, start=1)]
    else:
        zrodla = [(t["funkcja"], nr, t["geometria"], t["parametry"]["kondygnacje"]) for nr, t in enumerate(tereny, start=1) if t["funkcja"] in ("MN", "MW", "U")]
    wyniki, strefy = [], []
    for funkcja, nr, geometria, kondygnacje in zrodla:
        teren_m = _w_metrach(geometria, szerokosc)
        wysokosc = kondygnacje * WYSOKOSC_KONDYGNACJI_M
        slady = []
        for s in slonce:
            if s["wysokosc"] <= 0 or wysokosc <= 0:
                continue
            dlugosc = wysokosc / math.tan(math.radians(s["wysokosc"]))
            kierunek = math.radians(s["azymut"] + 180)  # cień pada od słońca
            slady.append(_slad(teren_m, dlugosc * math.sin(kierunek), dlugosc * math.cos(kierunek)))
        strefa = unary_union(slady).difference(teren_m) if slady else None
        if strefa is not None and not strefa.is_empty:
            strefy.append(strefa)
        poludnie = next(s for s in slonce if s["godzina"] == 12)
        wyniki.append({
            "nr": nr,
            "funkcja": funkcja,
            "wysokosc_m": round(wysokosc, 1),
            "cien_w_poludnie_m": round(wysokosc / math.tan(math.radians(poludnie["wysokosc"])), 1) if poludnie["wysokosc"] > 0 and wysokosc > 0 else None,
            # 0 m = teren sięga granicy obszaru (albo ją przecina)
            "od_granicy_m": round(granica.distance(teren_m), 1) if granica is not None else None,
        })

    strefa = unary_union(strefy) if strefy else None
    if strefa is not None and budynki:
        strefa = strefa.difference(unary_union([_w_metrach(b["geometria"], szerokosc) for b in budynki]))
    zacienione = []
    if strefa is not None:
        for nr, t in enumerate(tereny, start=1):
            if t["funkcja"] not in FUNKCJE_CHRONIONE:
                continue
            teren_m = _w_metrach(t["geometria"], szerokosc)
            w_cieniu = teren_m.intersection(strefa).area
            if w_cieniu >= 1:
                zacienione.append({
                    "nr": nr,
                    "funkcja": t["funkcja"],
                    "pole_m2": round(teren_m.area, 1),
                    "w_cieniu_m2": round(w_cieniu, 1),
                    "procent": round(100 * w_cieniu / teren_m.area, 1),
                })
    return {
        "dzien": opis_dnia,
        "szerokosc": round(szerokosc, 4),
        "slonce": slonce,
        "tereny": wyniki,
        "zacienione": zacienione,
        # strefa z powrotem w stopniach — do narysowania na mapie
        "strefa": mapping(scale(strefa, xfact=1 / mx, yfact=1 / my, origin=(0, 0))) if strefa is not None and not strefa.is_empty else None,
        "wysokosc_kondygnacji_m": WYSOKOSC_KONDYGNACJI_M,
        "zrodlo": "budynki" if budynki else "tereny",  # ETAP 195
    }

