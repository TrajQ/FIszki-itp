"""Baza modułu osiedle (surowy sqlite3, jak w pozostałych modułach — D-004).

Koncepcja to nazwa + cały rysunek (GeoJSON) + ustawienia (np. ustalenia
planu). Rysunek trzymamy w jednej kolumnie JSON: zapisujemy go w całości
po każdej zmianie, a bilans liczymy od nowa — przy kilkudziesięciu
wielobokach to ułamek sekundy, a model danych zostaje prosty.
"""

import json
import os
import sqlite3
from datetime import datetime

from flask import current_app, g

SCHEMAT = """
CREATE TABLE IF NOT EXISTS koncepcje (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    geojson TEXT NOT NULL,
    ustawienia TEXT NOT NULL DEFAULT '{}',
    data_utworzenia TEXT NOT NULL,
    data_zmiany TEXT NOT NULL
);
"""

PUSTY_RYSUNEK = {"type": "FeatureCollection", "features": []}


def get_db() -> sqlite3.Connection:
    if "db_osiedle" not in g:
        folder = os.path.join(current_app.instance_path, "osiedle")
        os.makedirs(folder, exist_ok=True)
        g.db_osiedle = sqlite3.connect(os.path.join(folder, "osiedle.db"))
        g.db_osiedle.row_factory = sqlite3.Row
    return g.db_osiedle


def close_db(exception=None):
    db = g.pop("db_osiedle", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    db.commit()


def _na_slownik(wiersz) -> dict:
    wynik = dict(wiersz)
    wynik["geojson"] = json.loads(wynik["geojson"])
    wynik["ustawienia"] = json.loads(wynik["ustawienia"])
    return wynik


def lista() -> list[dict]:
    wiersze = get_db().execute(
        "SELECT id, nazwa, data_utworzenia, data_zmiany FROM koncepcje ORDER BY data_zmiany DESC, id DESC"
    ).fetchall()
    return [dict(w) for w in wiersze]


def pobierz(koncepcja_id: int) -> dict | None:
    wiersz = get_db().execute("SELECT * FROM koncepcje WHERE id = ?", (koncepcja_id,)).fetchone()
    return _na_slownik(wiersz) if wiersz else None


def utworz(nazwa: str) -> int:
    teraz = datetime.now().isoformat(timespec="seconds")
    db = get_db()
    kursor = db.execute(
        "INSERT INTO koncepcje (nazwa, geojson, data_utworzenia, data_zmiany) VALUES (?, ?, ?, ?)",
        (nazwa, json.dumps(PUSTY_RYSUNEK), teraz, teraz),
    )
    db.commit()
    return kursor.lastrowid


def zapisz(koncepcja_id: int, nazwa: str | None = None, geojson: dict | None = None, ustawienia: dict | None = None):
    """Zmienia tylko podane pola."""
    zmiany, parametry = [], []
    if nazwa is not None:
        zmiany.append("nazwa = ?")
        parametry.append(nazwa)
    if geojson is not None:
        zmiany.append("geojson = ?")
        parametry.append(json.dumps(geojson, ensure_ascii=False))
    if ustawienia is not None:
        zmiany.append("ustawienia = ?")
        parametry.append(json.dumps(ustawienia, ensure_ascii=False))
    zmiany.append("data_zmiany = ?")
    parametry.append(datetime.now().isoformat(timespec="seconds"))
    db = get_db()
    db.execute(f"UPDATE koncepcje SET {', '.join(zmiany)} WHERE id = ?", (*parametry, koncepcja_id))
    db.commit()


def usun(koncepcja_id: int):
    db = get_db()
    db.execute("DELETE FROM koncepcje WHERE id = ?", (koncepcja_id,))
    db.commit()
