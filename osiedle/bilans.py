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

from . import etapy as etp
from .chlonnosc import chlonnosc
from . import koszty as kosz
from . import program as prog
from . import wskazniki as wsk

OBSZAR = "obszar"
# ETAP 173: budynek — obrys z liczbą kondygnacji, rysowany na terenach.
# Nie jest funkcją terenu: nie wchodzi do bilansu terenu (leży na MN/MW/U).
BUDYNEK = "budynek"
DOMYSLNE_KONDYGNACJE_BUDYNKU = 2
# ETAP 239: zielony dach — do terenu biologicznie czynnego wlicza się 50%
# powierzchni stropodachów urządzonych jako stałe trawniki lub kwietniki,
# o powierzchni nie mniejszej niż 10 m² (rozporządzenie o warunkach
# technicznych, § 3 pkt 22). Plan może mieć własną definicję — wtedy ona.
UDZIAL_ZIELONEGO_DACHU_W_PBC = 0.5
MIN_ZIELONY_DACH_M2 = 10.0
KOLOR_BUDYNKU = "#3a3a3c"
# ETAP 175: nieprzekraczalna linia zabudowy — łamana; budynek nie może jej przecinać
LINIA = "linia_zabudowy"
KOLOR_LINII = "#d70015"

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
        if (cecha.get("properties") or {}).get("funkcja") == LINIA:
            if geometria.geom_type != "LineString" or geometria.length == 0:
                raise BladKoncepcji(f"Obiekt {i}: linia zabudowy musi być łamaną.")
            continue  # linie czyta wczytaj_linie
        if geometria.geom_type not in ("Polygon", "MultiPolygon") or geometria.is_empty:
            raise BladKoncepcji(f"Obiekt {i}: dozwolone są tylko wieloboki.")
        if not geometria.is_valid:
            geometria = geometria.buffer(0)  # np. wielobok „ósemka” po przesunięciu wierzchołka
        wlasciwosci = cecha.get("properties") or {}
        funkcja = wlasciwosci.get("funkcja")
        if funkcja == OBSZAR:
            obszar = geometria if obszar is None else obszar.union(geometria)
        elif funkcja == BUDYNEK:
            continue  # budynki czyta wczytaj_budynki
        elif funkcja in FUNKCJE:
            tereny.append({"funkcja": funkcja, "geometria": geometria, "wlasciwosci": wlasciwosci})
        else:
            raise BladKoncepcji(f"Obiekt {i}: nieznana funkcja terenu „{funkcja}”.")
    return obszar, tereny


def wczytaj_budynki(geojson: dict) -> list[dict]:
    """Budynki z rysunku (po wczytaj_tereny, więc kolekcja jest już
    sprawdzona): [{"geometria", "kondygnacje", "wlasciwosci"}]."""
    budynki = []
    for i, cecha in enumerate(geojson.get("features") or [], start=1):
        wlasciwosci = cecha.get("properties") or {}
        if wlasciwosci.get("funkcja") != BUDYNEK:
            continue
        geometria = shape(cecha["geometry"])
        if not geometria.is_valid:
            geometria = geometria.buffer(0)
        kondygnacje = wlasciwosci.get("kondygnacje")
        if kondygnacje is None or kondygnacje == "":
            kondygnacje = DOMYSLNE_KONDYGNACJE_BUDYNKU
        else:
            try:
                kondygnacje = wsk._liczba(kondygnacje, f"Budynek (obiekt {i}), kondygnacje")
            except wsk.BladParametru as e:
                raise BladKoncepcji(str(e)) from None
            if not 1 <= kondygnacje <= wsk.ZAKRESY["kondygnacje"][1]:
                raise BladKoncepcji(f"Budynek (obiekt {i}): kondygnacje muszą być w zakresie 1–{wsk.ZAKRESY['kondygnacje'][1]}.")
        zielony = wlasciwosci.get("zielony_dach_proc")
        if zielony is None or zielony == "":
            zielony = 0.0
        else:
            try:
                zielony = wsk._liczba(zielony, f"Budynek (obiekt {i}), zielony dach")
            except wsk.BladParametru as e:
                raise BladKoncepcji(str(e)) from None
            if not 0 <= zielony <= 100:
                raise BladKoncepcji(f"Budynek (obiekt {i}): zielony dach musi być w zakresie 0–100% dachu.")
        budynki.append({"geometria": geometria, "kondygnacje": kondygnacje, "zielony_dach_proc": zielony, "wlasciwosci": wlasciwosci})
    return budynki


def wczytaj_linie(geojson: dict) -> list:
    """Nieprzekraczalne linie zabudowy (ETAP 175) — łamane w stopniach
    (sprawdzone już w wczytaj_tereny)."""
    return [shape(c["geometry"]) for c in geojson.get("features") or [] if (c.get("properties") or {}).get("funkcja") == LINIA]


def _budynki(budynki: list[dict], tereny: list[dict], obszar, pole, linie: list | None = None, w_metrach=None) -> dict | None:
    """Zestawienie budynków (ETAP 173): powierzchnia zabudowy (rzut) i
    całkowita (rzut × kondygnacje), teren, na którym leży większość
    budynku, i kontrole: budynek nie na terenie zabudowy, poza obszarem.
    ETAP 175: przecięcie nieprzekraczalnej linii zabudowy i odległość od niej."""
    if not budynki:
        return None
    linie_m = [w_metrach(linia) for linia in (linie or [])]
    lista, poza_zabudowa, poza_obszarem, przecina = [], 0, 0, 0
    for nr, b in enumerate(budynki, start=1):
        rzut = pole(b["geometria"])
        nakladanie = [(pole(b["geometria"].intersection(t["geometria"])), t["funkcja"]) for t in tereny if b["geometria"].intersects(t["geometria"])]
        teren = max(nakladanie, default=(0.0, None))
        funkcja = teren[1] if teren[0] > rzut / 2 else None
        if funkcja is None or not FUNKCJE[funkcja]["zabudowa"]:
            poza_zabudowa += 1
        if obszar is not None and pole(b["geometria"].difference(obszar)) > max(1.0, rzut * 0.01):
            poza_obszarem += 1
        wpis = {"nr": nr, "pole_m2": round(rzut, 1), "kondygnacje": b["kondygnacje"],
                "calkowita_m2": round(rzut * b["kondygnacje"], 1), "teren": funkcja}
        # ETAP 239: zielony dach (część rzutu) i jego udział w PBC
        zielony_m2 = rzut * b.get("zielony_dach_proc", 0) / 100
        wpis["zielony_dach_m2"] = round(zielony_m2, 1)
        wpis["pbc_z_dachu_m2"] = round(UDZIAL_ZIELONEGO_DACHU_W_PBC * zielony_m2, 1) if zielony_m2 >= MIN_ZIELONY_DACH_M2 else 0.0
        if linie_m:
            obrys = w_metrach(b["geometria"])
            wpis["przecina_linie"] = any(obrys.intersects(linia) for linia in linie_m)
            wpis["od_linii_m"] = 0.0 if wpis["przecina_linie"] else round(min(obrys.distance(linia) for linia in linie_m), 1)
            przecina += wpis["przecina_linie"]
        lista.append(wpis)
    return {
        "liczba": len(lista),
        "zabudowa_m2": round(sum(b["pole_m2"] for b in lista), 1),
        "calkowita_m2": round(sum(b["calkowita_m2"] for b in lista), 1),
        "zielone_dachy_m2": round(sum(b["zielony_dach_m2"] for b in lista), 1),
        "pbc_z_dachow_m2": round(sum(b["pbc_z_dachu_m2"] for b in lista), 1),
        "lista": lista,
        "poza_terenem_zabudowy": poza_zabudowa,
        "poza_obszarem": poza_obszarem,
        "linii_zabudowy": len(linie_m),
        "przecina_linie": przecina,
    }


def bilans(geojson: dict, ustawienia: dict | None = None) -> dict:
    """Bilans terenu: m² i % dla każdej funkcji, kontrole rysunku,
    wskaźniki zabudowy, zgodność z ustaleniami planu i program osiedla
    (ustalenia i założenia programu — z ustawień koncepcji)."""
    obszar, tereny = wczytaj_tereny(geojson)
    budynki = wczytaj_budynki(geojson)
    linie = wczytaj_linie(geojson)
    try:
        plan = wsk.ustalenia_planu(ustawienia)
        prog.zalozenia(ustawienia)  # sprawdzenie także przy pustym rysunku
        kosz.stawki(ustawienia)  # ETAP 155
        for t in tereny:
            t["parametry"] = wsk.parametry_terenu(t["funkcja"], t["wlasciwosci"])
            t["etap"] = etp.etap_terenu(t["funkcja"], t["wlasciwosci"])  # ETAP 196
    except (wsk.BladParametru, prog.BladZalozen, kosz.BladStawek, etp.BladEtapu) as e:
        raise BladKoncepcji(str(e)) from None
    wszystko = [t["geometria"] for t in tereny] + [b["geometria"] for b in budynki] + ([obszar] if obszar is not None else [])
    if not wszystko:
        return {"obszar_m2": None, "funkcje": [], "razem_m2": 0.0, "kontrole": {}, "wskazniki": None, "zgodnosc": [], "program": None, "koszty": None,
                "budynki": None, "wskazniki_budynkow": None, "zgodnosc_budynkow": [], "etapy": None,
                "chlonnosc": None}
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
    program = prog.program(tereny, obszar_m2, ustawienia)
    zestawienie_budynkow = _budynki(budynki, tereny, obszar, pole, linie, lambda g: _w_metrach(g, szerokosc))
    if zestawienie_budynkow and zestawienie_budynkow["pbc_z_dachow_m2"] > 0:
        wsk.dolicz_zielone_dachy(wskazniki, zestawienie_budynkow["pbc_z_dachow_m2"], podstawa)  # ETAP 239
    wskazniki_budynkow = wsk.wskazniki_budynkow(zestawienie_budynkow, podstawa)  # ETAP 174
    return {
        "obszar_m2": round(obszar_m2, 1) if obszar_m2 is not None else None,
        "funkcje": funkcje,
        "razem_m2": round(razem, 1),
        "kontrole": kontrole,
        "wskazniki": wskazniki,
        "zgodnosc": wsk.zgodnosc(wskazniki, plan),
        "program": program,
        "koszty": kosz.koszty(tereny, obszar_m2, ustawienia, program),
        "budynki": zestawienie_budynkow,
        "wskazniki_budynkow": wskazniki_budynkow,
        "zgodnosc_budynkow": wsk.zgodnosc(wskazniki_budynkow, plan) if wskazniki_budynkow else [],
        "etapy": etp.etapy(tereny, ustawienia),
        "chlonnosc": chlonnosc(wskazniki, wskazniki_budynkow, plan, podstawa, program),  # ETAP 197
    }
