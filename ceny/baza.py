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

-- ETAP 104: transakcje lokali z Rejestru Cen Nieruchomości (plik GeoPackage powiatu)
CREATE TABLE IF NOT EXISTS rcn_pliki (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    data_importu TEXT NOT NULL,
    liczba INTEGER NOT NULL,
    odrzucone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rcn_lokale (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plik_id INTEGER NOT NULL REFERENCES rcn_pliki(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    rok INTEGER NOT NULL,
    kwartal INTEGER NOT NULL,
    rynek TEXT NOT NULL,
    rodzaj TEXT NOT NULL,
    pow_m2 REAL NOT NULL,
    cena REAL NOT NULL,
    cena_m2 REAL NOT NULL,
    izby INTEGER,
    lat REAL,
    lng REAL
);
CREATE INDEX IF NOT EXISTS rcn_lokale_plik ON rcn_lokale (plik_id);

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
        g.db_ceny.execute("PRAGMA foreign_keys = ON")
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


# ---------- pliki RCN (ETAP 104) ----------

POLA_LOKALU = ("data", "rok", "kwartal", "rynek", "rodzaj", "pow_m2", "cena", "cena_m2", "izby", "lat", "lng")


def zapisz_plik_rcn(nazwa: str, lokale: list[dict], odrzucone: dict) -> int:
    db = get_db()
    plik_id = db.execute(
        "INSERT INTO rcn_pliki (nazwa, data_importu, liczba, odrzucone) VALUES (?, ?, ?, ?)",
        (nazwa, datetime.now().isoformat(timespec="seconds"), len(lokale), json.dumps(odrzucone, ensure_ascii=False)),
    ).lastrowid
    db.executemany(
        f"INSERT INTO rcn_lokale (plik_id, {', '.join(POLA_LOKALU)}) VALUES (?, {', '.join('?' * len(POLA_LOKALU))})",
        [(plik_id, *(l[k] for k in POLA_LOKALU)) for l in lokale],
    )
    db.commit()
    return plik_id


def pliki_rcn() -> list[dict]:
    wynik = []
    for w in get_db().execute("SELECT * FROM rcn_pliki ORDER BY id DESC"):
        wynik.append({**dict(w), "odrzucone": json.loads(w["odrzucone"])})
    return wynik


def plik_rcn(plik_id: int) -> dict | None:
    w = get_db().execute("SELECT * FROM rcn_pliki WHERE id = ?", (plik_id,)).fetchone()
    return {**dict(w), "odrzucone": json.loads(w["odrzucone"])} if w else None


def lokale_rcn(plik_id: int, rynek: str | None = None, od_roku: int | None = None, do_roku: int | None = None,
               izby: str | None = None, rodzaj: str | None = None) -> list[dict]:
    warunki, parametry = ["plik_id = ?"], [plik_id]
    if rynek:
        warunki.append("rynek = ?")
        parametry.append(rynek)
    if od_roku:
        warunki.append("rok >= ?")
        parametry.append(od_roku)
    if do_roku:
        warunki.append("rok <= ?")
        parametry.append(do_roku)
    if izby == "4+":
        warunki.append("izby >= 4")
    elif izby:
        warunki.append("izby = ?")
        parametry.append(int(izby))
    if rodzaj:
        warunki.append("rodzaj = ?")
        parametry.append(rodzaj)
    return [dict(w) for w in get_db().execute(f"SELECT * FROM rcn_lokale WHERE {' AND '.join(warunki)}", parametry)]


def rodzaje_transakcji(plik_id: int) -> list[dict]:
    return [dict(w) for w in get_db().execute(
        "SELECT rodzaj, COUNT(*) AS liczba FROM rcn_lokale WHERE plik_id = ? GROUP BY rodzaj ORDER BY liczba DESC", (plik_id,))]


def usun_plik_rcn(plik_id: int) -> bool:
    db = get_db()
    usuniete = db.execute("DELETE FROM rcn_pliki WHERE id = ?", (plik_id,)).rowcount
    db.commit()
    return bool(usuniete)
