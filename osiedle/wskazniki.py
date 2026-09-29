"""Wskaźniki zabudowy koncepcji i zgodność z ustaleniami planu (ETAP 58).

Każdy teren ma parametry (zapisane we właściwościach obiektu GeoJSON):

- zabudowa_proc — jaka część terenu jest pod budynkami [%] (tylko MN, MW, U),
- kondygnacje — liczba kondygnacji nadziemnych budynków (tylko MN, MW, U),
- pbc_proc — jaka część terenu jest biologicznie czynna [%].

Brak parametru = wartość domyślna z tabeli DOMYSLNE — pokazywana w
panelu, żeby było widać, z czego liczymy. Definicje wskaźników jak w
module mpzp (mpzp/zabudowa.py), ale odniesione do całego obszaru
opracowania, a bez niego — do sumy terenów:

- wskaźnik zabudowy [%] = Σ(pole terenu × zabudowa_proc) / podstawa,
- intensywność [–] = Σ(pole × zabudowa_proc × kondygnacje) / podstawa,
- PBC [%] = Σ(pole × pbc_proc) / podstawa.

Część obszaru bez przypisanej funkcji nie jest ani zabudową, ani PBC.
"""

import math

# Domyślne parametry terenów — typowe wartości do szybkiego szkicu.
# Woda powierzchniowa liczy się do terenu biologicznie czynnego
# (definicja w rozporządzeniu o warunkach technicznych, § 3 pkt 22).
DOMYSLNE = {
    "MN": {"zabudowa_proc": 30, "kondygnacje": 2, "pbc_proc": 50},
    "MW": {"zabudowa_proc": 30, "kondygnacje": 5, "pbc_proc": 30},
    "U": {"zabudowa_proc": 40, "kondygnacje": 2, "pbc_proc": 20},
    "ZP": {"pbc_proc": 90},
    "KD": {"pbc_proc": 0},
    "KS": {"pbc_proc": 0},
    "WS": {"pbc_proc": 100},
}

ZAKRESY = {"zabudowa_proc": (0, 100), "kondygnacje": (0, 50), "pbc_proc": (0, 100)}

# Ustalenia planu, które można wpisać: klucz → (nazwa, rodzaj granicy, jednostka).
USTALENIA = {
    "max_zabudowa_proc": ("wskaźnik zabudowy", "max", "%"),
    "min_intensywnosc": ("intensywność zabudowy", "min", ""),
    "max_intensywnosc": ("intensywność zabudowy", "max", ""),
    "min_pbc_proc": ("powierzchnia biologicznie czynna", "min", "%"),
    "max_kondygnacje": ("liczba kondygnacji", "max", ""),
}

# który wskaźnik porównujemy z którym ustaleniem
_WSKAZNIK_USTALENIA = {
    "max_zabudowa_proc": "zabudowa_proc",
    "min_intensywnosc": "intensywnosc",
    "max_intensywnosc": "intensywnosc",
    "min_pbc_proc": "pbc_proc",
    "max_kondygnacje": "max_kondygnacje",
}


class BladParametru(ValueError):
    """Niepoprawny parametr terenu albo ustalenie planu."""


def _liczba(wartosc, opis: str) -> float:
    if isinstance(wartosc, bool):
        raise BladParametru(f"{opis}: to nie jest liczba.")
    try:
        liczba = float(wartosc)
    except (TypeError, ValueError):
        raise BladParametru(f"{opis}: to nie jest liczba.") from None
    if not math.isfinite(liczba):
        raise BladParametru(f"{opis}: to nie jest liczba.")
    return liczba


def parametry_terenu(funkcja: str, wlasciwosci: dict) -> dict:
    """Parametry terenu: domyślne nadpisane tym, co wpisał użytkownik."""
    wynik = dict(DOMYSLNE[funkcja])
    for klucz in wynik:
        wartosc = wlasciwosci.get(klucz)
        if wartosc is None or wartosc == "":
            continue
        liczba = _liczba(wartosc, f"Teren {funkcja}, {klucz}")
        od, do = ZAKRESY[klucz]
        if not od <= liczba <= do:
            raise BladParametru(f"Teren {funkcja}: {klucz} musi być w zakresie {od}–{do}.")
        wynik[klucz] = liczba
    return wynik


def ustalenia_planu(ustawienia: dict | None) -> dict:
    """Ustalenia planu z ustawień koncepcji (tylko wpisane, sprawdzone)."""
    plan = (ustawienia or {}).get("plan") or {}
    if not isinstance(plan, dict):
        raise BladParametru("Ustalenia planu muszą być obiektem.")
    wynik = {}
    for klucz, wartosc in plan.items():
        if klucz not in USTALENIA:
            raise BladParametru(f"Nieznane ustalenie planu „{klucz}”.")
        if wartosc is None or wartosc == "":
            continue
        liczba = _liczba(wartosc, USTALENIA[klucz][0].capitalize())
        if liczba < 0:
            raise BladParametru(f"{USTALENIA[klucz][0].capitalize()}: wartość nie może być ujemna.")
        wynik[klucz] = liczba
    if wynik.get("min_intensywnosc", 0) > wynik.get("max_intensywnosc", math.inf):
        raise BladParametru("Minimalna intensywność jest większa od maksymalnej.")
    return wynik


def wskazniki(tereny: list[dict], podstawa_m2: float) -> dict:
    """Wskaźniki dla koncepcji.

    tereny: [{"funkcja", "pole_m2", "parametry", "zabudowa" (bool)}].
    """
    zabudowa_m2 = calkowita_m2 = pbc_m2 = 0.0
    kondygnacje = []
    for t in tereny:
        p = t["parametry"]
        pbc_m2 += t["pole_m2"] * p["pbc_proc"] / 100
        if t["zabudowa"]:
            rzut = t["pole_m2"] * p["zabudowa_proc"] / 100
            zabudowa_m2 += rzut
            calkowita_m2 += rzut * p["kondygnacje"]
            if rzut > 0:
                kondygnacje.append(p["kondygnacje"])

    def udzial(m2):
        return m2 / podstawa_m2 if podstawa_m2 else None

    return {
        "powierzchnia_zabudowy_m2": round(zabudowa_m2, 1),
        "powierzchnia_calkowita_m2": round(calkowita_m2, 1),
        "pbc_m2": round(pbc_m2, 1),
        "zabudowa_proc": _zaokraglij(udzial(zabudowa_m2), 100, 1),
        "intensywnosc": _zaokraglij(udzial(calkowita_m2), 1, 2),
        "pbc_proc": _zaokraglij(udzial(pbc_m2), 100, 1),
        "max_kondygnacje": max(kondygnacje, default=None),
    }


def _zaokraglij(wartosc, mnoznik, miejsca):
    return None if wartosc is None else round(wartosc * mnoznik, miejsca)


def zgodnosc(wsk: dict, plan: dict) -> list[dict]:
    """Każde wpisane ustalenie planu z wynikiem: spełnione czy nie."""
    wynik = []
    for klucz, granica in plan.items():
        nazwa, rodzaj, jednostka = USTALENIA[klucz]
        wartosc = wsk[_WSKAZNIK_USTALENIA[klucz]]
        if wartosc is None:
            continue
        ok = wartosc <= granica + 1e-9 if rodzaj == "max" else wartosc >= granica - 1e-9
        wynik.append({"ustalenie": klucz, "nazwa": nazwa, "rodzaj": rodzaj, "jednostka": jednostka, "wartosc": wartosc, "granica": granica, "spelnione": ok})
    return wynik
