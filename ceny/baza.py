"""Baza modułu ceny (surowy sqlite3, jak w pozostałych modułach — D-004).

- ustawienia: wybrany wskaźnik ceny z BDL (numer zmiennej, nazwa, jednostka),
- cache: odpowiedzi API BDL — dane GUS za miniony rok się nie zmieniają,
  a API ma limity zapytań.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta

from flask import current_app, g

WAZNOSC_DNI = 30

SCHEMAT = """
CREATE TABLE IF NOT EXISTS ustawienia (
    klucz TEXT PRIMARY KEY,
    wartosc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cache_bdl (
    klucz TEXT PRIMARY KEY,
    dane_json TEXT NOT NULL,
    data_pobrania TEXT NOT NULL
);
"""


def get_db() -> sqlite3.Connection:
    if "db_ceny" not in g:
        folder = os.path.join(current_app.instance_path, "ceny")
        os.makedirs(folder, exist_ok=True)
        g.db_ceny = sqlite3.connect(os.path.join(folder, "ceny.db"))
        g.db_ceny.row_factory = sqlite3.Row
    return g.db_ceny


def close_db(exception=None):
    db = g.pop("db_ceny", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    db.commit()


def ustawienie(klucz: str):
    wiersz = get_db().execute("SELECT wartosc FROM ustawienia WHERE klucz = ?", (klucz,)).fetchone()
    return json.loads(wiersz["wartosc"]) if wiersz else None


def zapisz_ustawienie(klucz: str, wartosc) -> None:
    db = get_db()
    db.execute("INSERT OR REPLACE INTO ustawienia (klucz, wartosc) VALUES (?, ?)", (klucz, json.dumps(wartosc, ensure_ascii=False)))
    db.commit()


def z_cache(klucz: str, pobierz):
    """Dane z cache (WAZNOSC_DNI) albo pobierz() i zapisz. Pustych wyników nie
    zapamiętujemy — GUS mógł jeszcze nie opublikować danych za ostatni rok."""
    db = get_db()
    wiersz = db.execute("SELECT dane_json, data_pobrania FROM cache_bdl WHERE klucz = ?", (klucz,)).fetchone()
    if wiersz is not None and datetime.now() - datetime.fromisoformat(wiersz["data_pobrania"]) < timedelta(days=WAZNOSC_DNI):
        return json.loads(wiersz["dane_json"])
    dane = pobierz()
    if dane:
        db.execute(
            "INSERT OR REPLACE INTO cache_bdl (klucz, dane_json, data_pobrania) VALUES (?, ?, ?)",
            (klucz, json.dumps(dane, ensure_ascii=False), datetime.now().isoformat()),
        )
        db.commit()
    return dane
