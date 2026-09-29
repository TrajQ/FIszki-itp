"""Baza modułu atlas (surowy sqlite3, jak w fiszkach — D-004).

Jedyna tabela to cache odpowiedzi API BDL. Dane GUS za dany rok się nie
zmieniają, a API ma limity zapytań (zwłaszcza bez klucza), więc raz
pobrane wyniki trzymamy lokalnie przez WAZNOSC_DNI.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta

from flask import current_app, g

WAZNOSC_DNI = 30

SCHEMAT = """
CREATE TABLE IF NOT EXISTS cache_bdl (
    klucz TEXT PRIMARY KEY,
    dane_json TEXT NOT NULL,
    data_pobrania TEXT NOT NULL
);
"""


def folder_modulu() -> str:
    folder = os.path.join(current_app.instance_path, "atlas")
    os.makedirs(folder, exist_ok=True)
    return folder


def get_db() -> sqlite3.Connection:
    if "db_atlas" not in g:
        g.db_atlas = sqlite3.connect(os.path.join(folder_modulu(), "atlas.db"))
        g.db_atlas.row_factory = sqlite3.Row
    return g.db_atlas


def close_db(exception=None):
    db = g.pop("db_atlas", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    db.commit()


def z_cache(klucz: str, pobierz):
    """Zwraca dane z cache albo wywołuje pobierz(), zapisuje i zwraca wynik.

    Wynik pobierz() musi dać się zapisać jako JSON.
    """
    db = get_db()
    wiersz = db.execute(
        "SELECT dane_json, data_pobrania FROM cache_bdl WHERE klucz = ?", (klucz,)
    ).fetchone()
    if wiersz is not None:
        pobrano = datetime.fromisoformat(wiersz["data_pobrania"])
        if datetime.now() - pobrano < timedelta(days=WAZNOSC_DNI):
            return json.loads(wiersz["dane_json"])

    dane = pobierz()
    if not dane:
        # Pustego wyniku nie zapamiętujemy: GUS mógł jeszcze nie opublikować
        # danych za ten rok — po publikacji mają się pojawić od razu.
        return dane
    db.execute(
        "INSERT OR REPLACE INTO cache_bdl (klucz, dane_json, data_pobrania) VALUES (?, ?, ?)",
        (klucz, json.dumps(dane, ensure_ascii=False), datetime.now().isoformat()),
    )
    db.commit()
    return dane


def liczba_zapisanych_zestawow() -> int:
    """Ile zestawów danych (wskaźnik × rok × województwo) jest w cache."""
    return get_db().execute(
        "SELECT COUNT(*) FROM cache_bdl WHERE klucz LIKE 'dane:%'"
    ).fetchone()[0]
