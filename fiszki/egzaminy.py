"""Terminy egzaminów i postęp przygotowania (ETAP 51).

Egzamin ma nazwę, datę i zakres: temat, jeden plik PDF albo wszystkie
fiszki. Postęp liczymy z pudełek Leitnera:

- „utrwalona” fiszka = w pudełku 3 lub wyższym, czyli co najmniej dwa
  razy z rzędu oceniona „umiem” od ostatniego „nie umiem”,
- plan = ile nieutrwalonych fiszek dziennie trzeba przerobić, żeby każdą
  zobaczyć przed egzaminem (proste dzielenie — podpowiedź, nie wyrocznia).

Liczby liczy ten moduł z bazy — nic nie przychodzi od modelu językowego.
"""

import math
import sqlite3
from datetime import date

PUDELKO_UTRWALONE = 3
MAKS_DLUGOSC_NAZWY = 80


class BladEgzaminu(ValueError):
    """Niepoprawne dane egzaminu."""


def dodaj(db: sqlite3.Connection, nazwa: str, data: str, temat: str | None, pdf_id: int | None, dzis: date) -> int:
    nazwa = " ".join((nazwa or "").split())
    if not nazwa:
        raise BladEgzaminu("Podaj nazwę egzaminu, np. „Kolokwium z planowania”.")
    if len(nazwa) > MAKS_DLUGOSC_NAZWY:
        raise BladEgzaminu(f"Nazwa może mieć najwyżej {MAKS_DLUGOSC_NAZWY} znaków.")
    try:
        termin = date.fromisoformat(data or "")
    except ValueError:
        raise BladEgzaminu("Podaj datę egzaminu.") from None
    if termin < dzis:
        raise BladEgzaminu("Data egzaminu już minęła.")
    if temat and pdf_id is not None:
        raise BladEgzaminu("Zakres to temat albo plik, nie oba naraz.")
    kursor = db.execute(
        "INSERT INTO egzaminy (nazwa, data, temat, pdf_id) VALUES (?, ?, ?, ?)",
        (nazwa, termin.isoformat(), temat or None, pdf_id),
    )
    db.commit()
    return kursor.lastrowid


def usun(db: sqlite3.Connection, egzamin_id: int) -> None:
    db.execute("DELETE FROM egzaminy WHERE id = ?", (egzamin_id,))
    db.commit()


def _pudelka_w_zakresie(db: sqlite3.Connection, temat: str | None, pdf_id: int | None) -> list[int]:
    warunki, parametry = [], {}
    if temat:
        warunki.append("fiszki.id IN (SELECT fiszka_id FROM tematy_fiszek WHERE temat = :temat)")
        parametry["temat"] = temat
    if pdf_id is not None:
        warunki.append("fiszki.pdf_id = :pdf_id")
        parametry["pdf_id"] = pdf_id
    gdzie = (" WHERE " + " AND ".join(warunki)) if warunki else ""
    return [
        w[0]
        for w in db.execute(
            "SELECT COALESCE(powtorki.pudelko, 1) FROM fiszki LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id" + gdzie,
            parametry,
        )
    ]


def postep(pudelka: list[int], dni_do_egzaminu: int) -> dict:
    wszystkie = len(pudelka)
    utrwalone = sum(1 for p in pudelka if p >= PUDELKO_UTRWALONE)
    do_nauki = wszystkie - utrwalone
    # Dziś też jest dniem nauki, więc egzamin jutro = 1 dzień, dziś = 1 dzień.
    dni_nauki = max(dni_do_egzaminu, 1)
    return {
        "fiszki": wszystkie,
        "utrwalone": utrwalone,
        "procent": round(100 * utrwalone / wszystkie) if wszystkie else None,
        "do_nauki": do_nauki,
        "dziennie": math.ceil(do_nauki / dni_nauki) if do_nauki else 0,
    }


def lista(db: sqlite3.Connection, dzis: date) -> list[dict]:
    """Egzaminy od najbliższego, z postępem. Minione — na końcu."""
    wynik = []
    for w in db.execute(
        """SELECT egzaminy.*, pdfy.nazwa_oryginalna FROM egzaminy
           LEFT JOIN pdfy ON pdfy.id = egzaminy.pdf_id ORDER BY data, id"""
    ):
        egzamin = dict(w)
        dni = (date.fromisoformat(egzamin["data"]) - dzis).days
        egzamin["dni"] = dni
        egzamin["minal"] = dni < 0
        egzamin.update(postep(_pudelka_w_zakresie(db, egzamin["temat"], egzamin["pdf_id"]), dni))
        wynik.append(egzamin)
    return sorted(wynik, key=lambda e: (e["minal"], e["data"]))


def utrwalone_w_plikach(db: sqlite3.Connection) -> dict[int, int]:
    """{pdf_id: liczba utrwalonych fiszek} — do paska postępu przy pliku."""
    return {
        pdf_id: ile
        for pdf_id, ile in db.execute(
            """SELECT fiszki.pdf_id, COUNT(*) FROM fiszki
               JOIN powtorki ON powtorki.fiszka_id = fiszki.id
               WHERE powtorki.pudelko >= ? GROUP BY fiszki.pdf_id""",
            (PUDELKO_UTRWALONE,),
        )
    }
