"""Baza modułu praca (ETAP 232): zapisane rozliczenia miesięcy.

Jeden wiersz na miesiąc i osobę — ponowne zapisanie tego samego miesiąca
zastępuje poprzednie (np. po poprawce grafiku). Godziny trzymamy w
minutach, a kwotę jako tekst z dokładnej wartości Decimal — bez błędów
zaokrągleń liczb zmiennoprzecinkowych przy sumowaniu roku.
"""

import os
import sqlite3
from datetime import datetime
from decimal import Decimal

from flask import current_app, g

SCHEMAT = """
CREATE TABLE IF NOT EXISTS rozliczenia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rok INTEGER NOT NULL,
    miesiac INTEGER NOT NULL,
    imie TEXT NOT NULL,
    minuty INTEGER NOT NULL,
    stawka TEXT NOT NULL,
    kwota TEXT NOT NULL,
    zmian INTEGER NOT NULL,
    tekst TEXT NOT NULL,
    data_zapisu TEXT NOT NULL,
    UNIQUE (rok, miesiac, imie)
);
"""


def get_db() -> sqlite3.Connection:
    if "db_praca" not in g:
        folder = os.path.join(current_app.instance_path, "praca")
        os.makedirs(folder, exist_ok=True)
        g.db_praca = sqlite3.connect(os.path.join(folder, "praca.db"))
        g.db_praca.row_factory = sqlite3.Row
    return g.db_praca


def close_db(exception=None):
    db = g.pop("db_praca", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    db.commit()


def zapisz(rok: int, miesiac: int, imie: str, minuty: int, stawka: Decimal, kwota: Decimal, zmian: int, tekst: str) -> int:
    db = get_db()
    db.execute(
        """INSERT INTO rozliczenia (rok, miesiac, imie, minuty, stawka, kwota, zmian, tekst, data_zapisu)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (rok, miesiac, imie) DO UPDATE SET minuty = excluded.minuty, stawka = excluded.stawka,
               kwota = excluded.kwota, zmian = excluded.zmian, tekst = excluded.tekst, data_zapisu = excluded.data_zapisu""",
        (rok, miesiac, imie, minuty, str(stawka), str(kwota), zmian, tekst, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    return db.execute("SELECT id FROM rozliczenia WHERE rok = ? AND miesiac = ? AND imie = ?", (rok, miesiac, imie)).fetchone()[0]


def rozliczenia() -> list[dict]:
    """Od najnowszego miesiąca."""
    return [dict(w) for w in get_db().execute("SELECT * FROM rozliczenia ORDER BY rok DESC, miesiac DESC, imie")]


def usun(rozliczenie_id: int) -> bool:
    db = get_db()
    usuniete = db.execute("DELETE FROM rozliczenia WHERE id = ?", (rozliczenie_id,)).rowcount
    db.commit()
    return bool(usuniete)
