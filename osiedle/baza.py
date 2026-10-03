"""Baza modułu osiedle (surowy sqlite3, jak w pozostałych modułach — D-004).

Koncepcja to nazwa + cały rysunek (GeoJSON) + ustawienia (np. ustalenia
planu). Rysunek trzymamy w jednej kolumnie JSON: zapisujemy go w całości
po każdej zmianie, a bilans liczymy od nowa — przy kilkudziesięciu
wielobokach to ułamek sekundy, a model danych zostaje prosty.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta

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

-- ETAP 218: własne zestawy założeń programu (np. „normatywy gminy X”) do użycia w wielu koncepcjach
CREATE TABLE IF NOT EXISTS zestawy_zalozen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL UNIQUE,
    zalozenia TEXT NOT NULL,
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


# ETAP 212: kosz — usunięta koncepcja ma datę usunięcia i znika z list; po DNI_W_KOSZU dniach — na dobre
DNI_W_KOSZU = 30


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    if "usunieto" not in {w[1] for w in db.execute("PRAGMA table_info(koncepcje)")}:
        db.execute("ALTER TABLE koncepcje ADD COLUMN usunieto TEXT")
    db.commit()


def _na_slownik(wiersz) -> dict:
    wynik = dict(wiersz)
    wynik["geojson"] = json.loads(wynik["geojson"])
    wynik["ustawienia"] = json.loads(wynik["ustawienia"])
    return wynik


def lista() -> list[dict]:
    wiersze = get_db().execute(
        "SELECT id, nazwa, data_utworzenia, data_zmiany FROM koncepcje WHERE usunieto IS NULL ORDER BY data_zmiany DESC, id DESC"
    ).fetchall()
    return [dict(w) for w in wiersze]


def pobierz(koncepcja_id: int) -> dict | None:
    wiersz = get_db().execute("SELECT * FROM koncepcje WHERE id = ? AND usunieto IS NULL", (koncepcja_id,)).fetchone()
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
    """Do kosza (ETAP 212) — rysunek zostaje, koncepcja znika z list."""
    db = get_db()
    db.execute("UPDATE koncepcje SET usunieto = ? WHERE id = ?", (datetime.now().isoformat(timespec="seconds"), koncepcja_id))
    db.commit()


MAKS_ZESTAWOW = 30


def zestawy() -> list[dict]:
    return [{**dict(w), "zalozenia": json.loads(w["zalozenia"])}
            for w in get_db().execute("SELECT * FROM zestawy_zalozen ORDER BY nazwa COLLATE NOCASE")]


def zapisz_zestaw(nazwa: str, zalozenia: dict) -> int:
    """Nowy zestaw albo zastąpienie zestawu o tej samej nazwie → id."""
    db = get_db()
    teraz = datetime.now().isoformat(timespec="seconds")
    db.execute("""INSERT INTO zestawy_zalozen (nazwa, zalozenia, data_zmiany) VALUES (?, ?, ?)
                  ON CONFLICT(nazwa) DO UPDATE SET zalozenia = excluded.zalozenia, data_zmiany = excluded.data_zmiany""",
               (nazwa, json.dumps(zalozenia, ensure_ascii=False), teraz))
    db.commit()
    return db.execute("SELECT id FROM zestawy_zalozen WHERE nazwa = ?", (nazwa,)).fetchone()[0]


def usun_zestaw(zestaw_id: int) -> bool:
    db = get_db()
    usuniete = db.execute("DELETE FROM zestawy_zalozen WHERE id = ?", (zestaw_id,)).rowcount
    db.commit()
    return bool(usuniete)


def w_koszu() -> list[dict]:
    """Usunięte koncepcje (najpierw najnowsze); starsze niż DNI_W_KOSZU dni usuwa na dobre."""
    db = get_db()
    granica = (datetime.now() - timedelta(days=DNI_W_KOSZU)).isoformat(timespec="seconds")
    db.execute("DELETE FROM koncepcje WHERE usunieto IS NOT NULL AND usunieto < ?", (granica,))
    db.commit()
    return [dict(w) for w in db.execute("SELECT id, nazwa, usunieto FROM koncepcje WHERE usunieto IS NOT NULL ORDER BY usunieto DESC")]


def przywroc(koncepcja_id: int) -> bool:
    db = get_db()
    zmienione = db.execute("UPDATE koncepcje SET usunieto = NULL WHERE id = ? AND usunieto IS NOT NULL", (koncepcja_id,)).rowcount
    db.commit()
    return bool(zmienione)
