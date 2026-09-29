"""Tematy fiszek (ETAP 50) — np. „kolokwium 1”, „planowanie”, „prawo”.

Fiszka może mieć kilka tematów; temat to krótki tekst wpisany przez
studenta. Po temacie filtrujemy powtórkę, quiz i karty do druku — żeby
przed kolokwium powtarzać tylko to, co na nim będzie.

Porównanie tematów bez rozróżniania wielkości liter („Prawo” = „prawo”),
zapisujemy pierwszą użytą pisownię.
"""

import sqlite3

MAKS_DLUGOSC = 30
MAKS_NA_FISZKE = 10


class BladTematow(ValueError):
    """Niepoprawna lista tematów."""


def normalizuj(tematy) -> list[str]:
    """Lista albo tekst „a, b” → unikalne, przycięte tematy."""
    if tematy is None:
        return []
    if isinstance(tematy, str):
        tematy = tematy.split(",")
    if not isinstance(tematy, list):
        raise BladTematow("Tematy to lista albo tekst rozdzielony przecinkami.")
    wynik: list[str] = []
    for temat in tematy:
        temat = " ".join(str(temat).split())
        if not temat:
            continue
        if len(temat) > MAKS_DLUGOSC:
            raise BladTematow(f"Temat może mieć najwyżej {MAKS_DLUGOSC} znaków.")
        if temat.casefold() not in {t.casefold() for t in wynik}:
            wynik.append(temat)
    if len(wynik) > MAKS_NA_FISZKE:
        raise BladTematow(f"Najwyżej {MAKS_NA_FISZKE} tematów na fiszkę.")
    return wynik


def _istniejaca_pisownia(db: sqlite3.Connection, temat: str) -> str:
    for (zapisany,) in db.execute("SELECT DISTINCT temat FROM tematy_fiszek"):
        if zapisany.casefold() == temat.casefold():
            return zapisany
    return temat


def ustaw(db: sqlite3.Connection, fiszka_id: int, tematy: list[str]) -> None:
    """Zastępuje tematy fiszki podaną listą (bez commit)."""
    db.execute("DELETE FROM tematy_fiszek WHERE fiszka_id = ?", (fiszka_id,))
    for temat in tematy:
        db.execute(
            "INSERT OR IGNORE INTO tematy_fiszek (fiszka_id, temat) VALUES (?, ?)",
            (fiszka_id, _istniejaca_pisownia(db, temat)),
        )


def tematy_fiszek(db: sqlite3.Connection) -> dict[int, list[str]]:
    """{fiszka_id: [tematy]} dla wszystkich fiszek z tematami."""
    wynik: dict[int, list[str]] = {}
    for fiszka_id, temat in db.execute("SELECT fiszka_id, temat FROM tematy_fiszek ORDER BY temat"):
        wynik.setdefault(fiszka_id, []).append(temat)
    return wynik


def wszystkie(db: sqlite3.Connection, warunek_do_powtorki: str, dzis: str) -> list[dict]:
    """Tematy z liczbą fiszek i liczbą fiszek do powtórki dziś."""
    wiersze = db.execute(
        f"""SELECT t.temat, COUNT(*) AS fiszki, COALESCE(SUM({warunek_do_powtorki}), 0) AS do_powtorki
            FROM tematy_fiszek t
            JOIN fiszki ON fiszki.id = t.fiszka_id
            LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id
            GROUP BY t.temat ORDER BY t.temat COLLATE NOCASE""",
        {"dzis": dzis},
    ).fetchall()
    return [dict(w) for w in wiersze]
