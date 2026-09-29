"""Bilans terenu koncepcji osiedla (ETAP 57).

Koncepcja to zbiór wieloboków narysowanych na mapie; każdy ma funkcję
(np. MW — zabudowa wielorodzinna, ZP — zieleń). Jeden wielobok może być
obszarem opracowania — granicą, do której odnosimy procenty.

Powierzchnie liczymy z geometrii w stopniach przeliczonych na metry
lokalną skalą (metry na stopień na szerokości środka obszaru, wzory
elipsoidy WGS84). Dla obszaru wielkości osiedla błąd jest poniżej 0,1%.
Świadomie osobna kopia tego przeliczenia niż w mpzp/geometria.py —
moduły są niezależne (CLAUDE.md).
"""

import math

from shapely.affinity import scale
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from . import program as prog
from . import wskazniki as wsk

OBSZAR = "obszar"

# Funkcje terenu: nazwa, kolor na mapie, czy to teren zabudowy
# (powierzchnię zabudowy i kondygnacje liczymy tylko dla tych — wskazniki.py).
# Symbole jak w planach.
FUNKCJE = {
    "MN": {"nazwa": "zabudowa mieszkaniowa jednorodzinna", "kolor": "#ffd60a", "zabudowa": True},
    "MW": {"nazwa": "zabudowa mieszkaniowa wielorodzinna", "kolor": "#ff9f0a", "zabudowa": True},
    "U": {"nazwa": "usługi", "kolor": "#ff375f", "zabudowa": True},
    "ZP": {"nazwa": "zieleń urządzona", "kolor": "#30d158", "zabudowa": False},
    "KD": {"nazwa": "drogi i ciągi pieszo-jezdne", "kolor": "#8e8e93", "zabudowa": False},
    "KS": {"nazwa": "parkingi", "kolor": "#636366", "zabudowa": False},
    "WS": {"nazwa": "wody", "kolor": "#0a84ff", "zabudowa": False},
}

MAKS_TERENOW = 500
MAKS_POLE_M2 = 25_000_000  # 25 km² — więcej to już nie koncepcja osiedla


class BladKoncepcji(ValueError):
    """Niepoprawna geometria albo dane koncepcji."""


def metry_na_stopien(szerokosc: float) -> tuple[float, float]:
    """(metry na 1° długości, metry na 1° szerokości) na danej szerokości."""
    fi = math.radians(szerokosc)
    na_szerokosc = 111132.954 - 559.822 * math.cos(2 * fi) + 1.175 * math.cos(4 * fi)
    na_dlugosc = 111412.84 * math.cos(fi) - 93.5 * math.cos(3 * fi)
    return na_dlugosc, na_szerokosc


def _w_metrach(geometria: BaseGeometry, szerokosc: float) -> BaseGeometry:
    mx, my = metry_na_stopien(szerokosc)
    return scale(geometria, xfact=mx, yfact=my, origin=(0, 0))


def wczytaj_tereny(geojson: dict) -> tuple[BaseGeometry | None, list[dict]]:
    """FeatureCollection → (obszar opracowania albo None, [tereny]).

    Teren: {"funkcja", "geometria" (w stopniach), "wlasciwosci"}. Sprawdza
    typy, funkcje i liczbę obiektów; naprawia drobne błędy geometrii.
    """
    if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
        raise BladKoncepcji("Koncepcja musi być kolekcją obiektów GeoJSON.")
    cechy = geojson.get("features") or []
    if len(cechy) > MAKS_TERENOW:
        raise BladKoncepcji(f"Najwyżej {MAKS_TERENOW} terenów w koncepcji.")
    obszar, tereny = None, []
    for i, cecha in enumerate(cechy, start=1):
        try:
            geometria = shape(cecha["geometry"])
        except Exception:
            raise BladKoncepcji(f"Obiekt {i}: niepoprawna geometria.") from None
        if geometria.geom_type not in ("Polygon", "MultiPolygon") or geometria.is_empty:
            raise BladKoncepcji(f"Obiekt {i}: dozwolone są tylko wieloboki.")
        if not geometria.is_valid:
            geometria = geometria.buffer(0)  # np. wielobok „ósemka” po przesunięciu wierzchołka
        wlasciwosci = cecha.get("properties") or {}
        funkcja = wlasciwosci.get("funkcja")
        if funkcja == OBSZAR:
            obszar = geometria if obszar is None else obszar.union(geometria)
        elif funkcja in FUNKCJE:
            tereny.append({"funkcja": funkcja, "geometria": geometria, "wlasciwosci": wlasciwosci})
        else:
            raise BladKoncepcji(f"Obiekt {i}: nieznana funkcja terenu „{funkcja}”.")
    return obszar, tereny


def bilans(geojson: dict, ustawienia: dict | None = None) -> dict:
    """Bilans terenu: m² i % dla każdej funkcji, kontrole rysunku,
    wskaźniki zabudowy, zgodność z ustaleniami planu i program osiedla
    (ustalenia i założenia programu — z ustawień koncepcji)."""
    obszar, tereny = wczytaj_tereny(geojson)
    try:
        plan = wsk.ustalenia_planu(ustawienia)
        prog.zalozenia(ustawienia)  # sprawdzenie także przy pustym rysunku
        for t in tereny:
            t["parametry"] = wsk.parametry_terenu(t["funkcja"], t["wlasciwosci"])
    except (wsk.BladParametru, prog.BladZalozen) as e:
        raise BladKoncepcji(str(e)) from None
    wszystko = [t["geometria"] for t in tereny] + ([obszar] if obszar is not None else [])
    if not wszystko:
        return {"obszar_m2": None, "funkcje": [], "razem_m2": 0.0, "kontrole": {}, "wskazniki": None, "zgodnosc": [], "program": None}
    szerokosc = unary_union(wszystko).centroid.y

    def pole(geometria):
        return _w_metrach(geometria, szerokosc).area

    obszar_m2 = pole(obszar) if obszar is not None else None
    if obszar_m2 is not None and obszar_m2 > MAKS_POLE_M2:
        raise BladKoncepcji("Obszar opracowania jest za duży (limit 25 km²).")

    po_funkcji: dict[str, float] = {}
    for t in tereny:
        t["pole_m2"] = pole(t["geometria"])
        t["zabudowa"] = FUNKCJE[t["funkcja"]]["zabudowa"]
        po_funkcji[t["funkcja"]] = po_funkcji.get(t["funkcja"], 0.0) + t["pole_m2"]
    razem = sum(po_funkcji.values())
    podstawa = obszar_m2 or razem  # procenty od obszaru, a bez niego — od sumy terenów

    funkcje = [
        {
            "funkcja": kod,
            "nazwa": FUNKCJE[kod]["nazwa"],
            "kolor": FUNKCJE[kod]["kolor"],
            "powierzchnia_m2": round(m2, 1),
            "procent": round(100 * m2 / podstawa, 1) if podstawa else None,
        }
        for kod, m2 in sorted(po_funkcji.items(), key=lambda p: -p[1])
    ]

    # Kontrole rysunku: nakładanie się terenów, tereny poza obszarem i
    # część obszaru, której nie przypisano żadnej funkcji.
    zajete = unary_union([t["geometria"] for t in tereny]) if tereny else None
    nakladanie = max(0.0, razem - pole(zajete)) if zajete is not None else 0.0
    kontrole = {"nakladanie_m2": round(nakladanie, 1)}
    if obszar is not None:
        poza = pole(zajete.difference(obszar)) if zajete is not None else 0.0
        wolne = pole(obszar.difference(zajete)) if zajete is not None else obszar_m2
        kontrole.update(
            poza_obszarem_m2=round(poza, 1),
            niezagospodarowane_m2=round(wolne, 1),
            niezagospodarowane_proc=round(100 * wolne / obszar_m2, 1) if obszar_m2 else None,
        )
    # Teren, na którym budynki i zieleń razem zajmują ponad 100% — do poprawy.
    kontrole["parametry_ponad_100"] = sum(
        1 for t in tereny if t["parametry"].get("zabudowa_proc", 0) + t["parametry"]["pbc_proc"] > 100 + 1e-9
    )
    wskazniki = wsk.wskazniki(tereny, podstawa)
    return {
        "obszar_m2": round(obszar_m2, 1) if obszar_m2 is not None else None,
        "funkcje": funkcje,
        "razem_m2": round(razem, 1),
        "kontrole": kontrole,
        "wskazniki": wskazniki,
        "zgodnosc": wsk.zgodnosc(wskazniki, plan),
        "program": prog.program(tereny, obszar_m2, ustawienia),
    }
