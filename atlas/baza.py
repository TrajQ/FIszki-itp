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

-- ETAP 63: zestaw wskaźników „Raportu gminy” — układa go użytkownik z
-- wyszukiwarki BDL (bez identyfikatorów zmiennych wpisanych w kod).
-- mianownik: opcjonalnie inna zmienna BDL (np. ludność) → wskaźnik względny.
CREATE TABLE IF NOT EXISTS raport_wskazniki (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zmienna_id INTEGER NOT NULL,
    nazwa TEXT NOT NULL,
    jednostka TEXT NOT NULL DEFAULT '',
    mianownik_id INTEGER,
    mianownik_nazwa TEXT,
    mnoznik INTEGER NOT NULL DEFAULT 1,
    kolejnosc INTEGER NOT NULL
);
"""

MAKS_WSKAZNIKOW_RAPORTU = 20


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


# ---------- zestaw wskaźników raportu gminy (ETAP 63) ----------


def wskazniki_raportu() -> list[dict]:
    wiersze = get_db().execute("SELECT * FROM raport_wskazniki ORDER BY kolejnosc, id").fetchall()
    return [dict(w) for w in wiersze]


def dodaj_wskaznik_raportu(zmienna: dict, mianownik: dict | None, mnoznik: int) -> int:
    db = get_db()
    kolejnosc = db.execute("SELECT COALESCE(MAX(kolejnosc), -1) + 1 FROM raport_wskazniki").fetchone()[0]
    wskaznik_id = db.execute(
        """INSERT INTO raport_wskazniki (zmienna_id, nazwa, jednostka, mianownik_id, mianownik_nazwa, mnoznik, kolejnosc)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            zmienna["id"], zmienna["nazwa"], zmienna["jednostka"] or "",
            mianownik["id"] if mianownik else None, mianownik["nazwa"] if mianownik else None,
            mnoznik if mianownik else 1, kolejnosc,
        ),
    ).lastrowid
    db.commit()
    return wskaznik_id


def usun_wskaznik_raportu(wskaznik_id: int) -> bool:
    db = get_db()
    usuniete = db.execute("DELETE FROM raport_wskazniki WHERE id = ?", (wskaznik_id,)).rowcount
    db.commit()
    return bool(usuniete)


def przesun_wskaznik_raportu(wskaznik_id: int, o: int) -> bool:
    """Zamienia miejscami z sąsiadem wyżej (o = -1) albo niżej (o = 1)."""
    lista = wskazniki_raportu()
    indeksy = [i for i, w in enumerate(lista) if w["id"] == wskaznik_id]
    if not indeksy:
        return False
    i, j = indeksy[0], indeksy[0] + o
    if 0 <= j < len(lista):
        lista[i], lista[j] = lista[j], lista[i]
        db = get_db()
        for k, w in enumerate(lista):
            db.execute("UPDATE raport_wskazniki SET kolejnosc = ? WHERE id = ?", (k, w["id"]))
        db.commit()
    return True
