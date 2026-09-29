"""Kalkulator wskaźników zabudowy działki — zgodność z ustaleniami planu.

Definicje jak w ustawie o planowaniu i zagospodarowaniu przestrzennym
(art. 15 ust. 2 pkt 6) i w typowych ustaleniach planów:

- wskaźnik powierzchni zabudowy [%] = powierzchnia zabudowy (suma rzutów
  budynków) / powierzchnia działki × 100,
- intensywność zabudowy [–] = powierzchnia całkowita (suma powierzchni
  wszystkich kondygnacji nadziemnych) / powierzchnia działki,
- udział powierzchni biologicznie czynnej [%] = PBC / powierzchnia
  działki × 100.

Uproszczenie: powierzchnia kondygnacji = rzut budynku (bez uwzględniania
cofnięć i nadwieszeń) — to kalkulator do szybkiej oceny wariantów, nie
projekt budowlany.
"""

from dataclasses import dataclass


@dataclass
class Budynek:
    rzut_m2: float
    kondygnacje: int
    wysokosc_m: float | None = None


@dataclass
class Ustalenia:
    """Parametry z planu; None = plan tego nie ustala."""

    max_zabudowa_proc: float | None = None
    min_intensywnosc: float | None = None
    max_intensywnosc: float | None = None
    min_pbc_proc: float | None = None
    max_wysokosc_m: float | None = None
    max_kondygnacje: int | None = None


class BladDanych(ValueError):
    """Niepoprawne dane wejściowe kalkulatora."""


def policz(powierzchnia_dzialki: float, budynki: list[Budynek], pbc_m2: float, ustalenia: Ustalenia) -> dict:
    if powierzchnia_dzialki <= 0:
        raise BladDanych("Powierzchnia działki musi być większa od zera.")
    if pbc_m2 < 0 or any(b.rzut_m2 < 0 or b.kondygnacje < 0 for b in budynki):
        raise BladDanych("Powierzchnie i liczby kondygnacji nie mogą być ujemne.")

    zabudowa_m2 = sum(b.rzut_m2 for b in budynki)
    calkowita_m2 = sum(b.rzut_m2 * b.kondygnacje for b in budynki)
    if zabudowa_m2 + pbc_m2 > powierzchnia_dzialki + 1e-9:
        raise BladDanych(
            "Zabudowa i powierzchnia biologicznie czynna razem przekraczają powierzchnię działki."
        )

    wskazniki = {
        "powierzchnia_zabudowy_m2": zabudowa_m2,
        "powierzchnia_calkowita_m2": calkowita_m2,
        "zabudowa_proc": 100 * zabudowa_m2 / powierzchnia_dzialki,
        "intensywnosc": calkowita_m2 / powierzchnia_dzialki,
        "pbc_proc": 100 * pbc_m2 / powierzchnia_dzialki,
        "max_kondygnacje": max((b.kondygnacje for b in budynki), default=0),
        "max_wysokosc_m": max((b.wysokosc_m for b in budynki if b.wysokosc_m is not None), default=None),
    }
    return {
        "wskazniki": wskazniki,
        "zgodnosc": _zgodnosc(wskazniki, ustalenia),
        "zapas": _zapas(powierzchnia_dzialki, wskazniki, ustalenia),
    }


def _zgodnosc(w: dict, u: Ustalenia) -> list[dict]:
    """Każde ustalenie planu z wynikiem: spełnione / niespełnione."""
    sprawdzenia = []

    def dodaj(nazwa, wartosc, granica, rodzaj, jednostka):
        if granica is None or wartosc is None:
            return
        ok = wartosc <= granica + 1e-9 if rodzaj == "max" else wartosc >= granica - 1e-9
        sprawdzenia.append(
            {"parametr": nazwa, "wartosc": wartosc, "granica": granica, "rodzaj": rodzaj, "jednostka": jednostka, "spelnione": ok}
        )

    dodaj("Powierzchnia zabudowy", w["zabudowa_proc"], u.max_zabudowa_proc, "max", "%")
    dodaj("Intensywność zabudowy", w["intensywnosc"], u.min_intensywnosc, "min", "")
    dodaj("Intensywność zabudowy", w["intensywnosc"], u.max_intensywnosc, "max", "")
    dodaj("Powierzchnia biologicznie czynna", w["pbc_proc"], u.min_pbc_proc, "min", "%")
    dodaj("Wysokość zabudowy", w["max_wysokosc_m"], u.max_wysokosc_m, "max", "m")
    dodaj("Liczba kondygnacji", w["max_kondygnacje"], u.max_kondygnacje, "max", "")
    return sprawdzenia


def _zapas(dzialka: float, w: dict, u: Ustalenia) -> dict:
    """Ile jeszcze można dobudować, nie łamiąc planu (None = bez limitu)."""
    zapas = {"rzut_m2": None, "powierzchnia_calkowita_m2": None}
    ograniczenia_rzutu = []
    if u.max_zabudowa_proc is not None:
        ograniczenia_rzutu.append(u.max_zabudowa_proc / 100 * dzialka - w["powierzchnia_zabudowy_m2"])
    if u.min_pbc_proc is not None:
        # nowy rzut zajmie teren, który dziś może być biologicznie czynny
        pbc_m2 = w["pbc_proc"] / 100 * dzialka
        wolne = dzialka - w["powierzchnia_zabudowy_m2"] - pbc_m2
        ograniczenia_rzutu.append(wolne + (pbc_m2 - u.min_pbc_proc / 100 * dzialka))
    if ograniczenia_rzutu:
        zapas["rzut_m2"] = max(0.0, min(ograniczenia_rzutu))
    if u.max_intensywnosc is not None:
        zapas["powierzchnia_calkowita_m2"] = max(0.0, u.max_intensywnosc * dzialka - w["powierzchnia_calkowita_m2"])
    return zapas
