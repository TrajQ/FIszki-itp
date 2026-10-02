"""Szacunek kosztów koncepcji osiedla (ETAP 155).

Stawki wpisuje użytkownik — Warsztat nie ma stawek domyślnych: ceny budowy
zmieniają się z roku na rok i między regionami, a liczba wpisana w kod
wyglądałaby jak dana. Koszt pozycji = ilość z koncepcji × stawka; ilości
liczy kod z rysunku (bilans, wskaźniki, program), jak wszystko w module.

Pozycje bez wpisanej stawki są pomijane — można liczyć np. tylko budynki.
"""

import math

# klucz → (opis, jednostka stawki, skąd ilość, jednostka ilości)
STAWKI = {
    "budowa_mw": ("budowa zabudowy wielorodzinnej MW", "zł/m² pow. całkowitej", "calkowita_MW", "m²"),
    "budowa_mn": ("budowa zabudowy jednorodzinnej MN", "zł/m² pow. całkowitej", "calkowita_MN", "m²"),
    "budowa_u": ("budowa usług U", "zł/m² pow. całkowitej", "calkowita_U", "m²"),
    "drogi_kd": ("drogi i ciągi pieszo-jezdne KD", "zł/m² terenu", "pole_KD", "m²"),
    "parkingi_ks": ("parkingi naziemne KS", "zł/m² terenu", "pole_KS", "m²"),
    "zielen_zp": ("zieleń urządzona ZP", "zł/m² terenu", "pole_ZP", "m²"),
    "miejsce_podziemne": ("miejsca postojowe, których brakuje na terenach KS (garaż podziemny)", "zł/miejsce", "miejsca_brakuje", "miejsc"),
    "grunt": ("grunt — cały obszar opracowania", "zł/m²", "obszar", "m²"),
}
MAKS_STAWKA = 1_000_000


class BladStawek(ValueError):
    """Niepoprawna stawka kosztów."""


def stawki(ustawienia: dict | None) -> dict[str, float]:
    """Wpisane stawki (tylko te); puste pole = pozycja pominięta."""
    wpisane = (ustawienia or {}).get("koszty") or {}
    if not isinstance(wpisane, dict):
        raise BladStawek("Stawki kosztów muszą być obiektem.")
    wynik = {}
    for klucz, wartosc in wpisane.items():
        if klucz not in STAWKI:
            raise BladStawek(f"Nieznana stawka kosztów „{klucz}”.")
        if wartosc is None or wartosc == "":
            continue
        try:
            liczba = float(wartosc)
        except (TypeError, ValueError):
            liczba = math.nan
        if isinstance(wartosc, bool) or not math.isfinite(liczba) or not 0 <= liczba <= MAKS_STAWKA:
            raise BladStawek(f"Stawka „{STAWKI[klucz][0]}”: podaj liczbę 0–{MAKS_STAWKA:,}.".replace(",", " "))
        wynik[klucz] = liczba
    return wynik


def ilosci(tereny: list[dict], obszar_m2: float | None, program: dict | None) -> dict[str, float]:
    """Ilości, do których stosuje się stawki — z terenów (pole_m2, parametry) i programu."""
    wynik = {"calkowita_MW": 0.0, "calkowita_MN": 0.0, "calkowita_U": 0.0, "pole_KD": 0.0, "pole_KS": 0.0, "pole_ZP": 0.0}
    for t in tereny:
        p = t["parametry"]
        if f"calkowita_{t['funkcja']}" in wynik:
            wynik[f"calkowita_{t['funkcja']}"] += t["pole_m2"] * p["zabudowa_proc"] / 100 * p["kondygnacje"]
        if f"pole_{t['funkcja']}" in wynik:
            wynik[f"pole_{t['funkcja']}"] += t["pole_m2"]
    wynik["miejsca_brakuje"] = float((program or {}).get("miejsca_brakuje") or 0)
    wynik["obszar"] = obszar_m2 or 0.0
    return wynik


def koszty(tereny: list[dict], obszar_m2: float | None, ustawienia: dict | None, program: dict | None) -> dict | None:
    """Pozycje kosztów i suma; None, gdy nie wpisano żadnej stawki."""
    s = stawki(ustawienia)
    if not s:
        return None
    ile = ilosci(tereny, obszar_m2, program)
    pozycje = []
    for klucz, stawka in s.items():
        opis, jednostka, zrodlo, jednostka_ilosci = STAWKI[klucz]
        pozycje.append({"klucz": klucz, "opis": opis, "ilosc": round(ile[zrodlo], 1), "jednostka_ilosci": jednostka_ilosci,
                        "stawka": stawka, "jednostka": jednostka, "koszt": round(ile[zrodlo] * stawka)})
    pozycje.sort(key=lambda p: list(STAWKI).index(p["klucz"]))
    razem = sum(p["koszt"] for p in pozycje)
    mieszkania = (program or {}).get("mieszkania") or 0
    calkowita = ile["calkowita_MW"] + ile["calkowita_MN"] + ile["calkowita_U"]
    return {
        "pozycje": pozycje,
        "razem": razem,
        "na_mieszkanie": round(razem / mieszkania) if mieszkania else None,
        "na_m2_calkowitej": round(razem / calkowita) if calkowita else None,
    }
