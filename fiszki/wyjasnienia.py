"""Wyjaśnienia odpowiedzi fiszek (ETAP 207).

Po odsłonięciu odpowiedzi w powtórce można zobaczyć wyjaśnienie: własne
(wpisane przez użytkownika) albo z Gemini — tylko z fragmentu źródła
fiszki, z liczbami sprawdzonymi w źródle (dane/gemini.wyjasnij_fiszke).
Jedno wyjaśnienie na fiszkę; zapis zastępuje poprzednie.
"""

import sqlite3
from datetime import datetime

MAKS_DLUGOSC = 1500
ZRODLA = ("wlasne", "gemini")


class BladWyjasnienia(ValueError):
    """Niepoprawne wyjaśnienie."""


def wszystkie(db: sqlite3.Connection) -> dict[int, dict]:
    """{fiszka_id: {"tekst", "zrodlo"}} — do kolejki powtórki."""
    return {w["fiszka_id"]: {"tekst": w["tekst"], "zrodlo": w["zrodlo"]}
            for w in db.execute("SELECT fiszka_id, tekst, zrodlo FROM wyjasnienia_fiszek")}


def zapisz(db: sqlite3.Connection, fiszka_id: int, tekst, zrodlo: str) -> dict:
    tekst = " ".join(str(tekst or "").split())
    if not tekst:
        raise BladWyjasnienia("Wpisz treść wyjaśnienia.")
    if len(tekst) > MAKS_DLUGOSC:
        raise BladWyjasnienia(f"Wyjaśnienie może mieć najwyżej {MAKS_DLUGOSC} znaków.")
    if zrodlo not in ZRODLA:
        raise BladWyjasnienia("Nieznane źródło wyjaśnienia.")
    db.execute(
        "INSERT INTO wyjasnienia_fiszek (fiszka_id, tekst, zrodlo, data) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(fiszka_id) DO UPDATE SET tekst = excluded.tekst, zrodlo = excluded.zrodlo, data = excluded.data",
        (fiszka_id, tekst, zrodlo, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    return {"tekst": tekst, "zrodlo": zrodlo}


def usun(db: sqlite3.Connection, fiszka_id: int) -> None:
    db.execute("DELETE FROM wyjasnienia_fiszek WHERE fiszka_id = ?", (fiszka_id,))
    db.commit()
