"""Baza modułu mpzp (surowy sqlite3, jak w pozostałych modułach — D-004).

Tabela `historia`: sprawdzone działki, żeby łatwo do nich wrócić —
tylko ostatnie LIMIT_HISTORII wpisów, bez duplikatów działki.

Tabela `zapisane` (ETAP 44): „Moje działki” — działki zapisane świadomie
(np. do projektu na zajęcia), z notatką, bez limitu i bez wypierania
przez nowe sprawdzenia.
"""

import os
import sqlite3
from datetime import datetime

from flask import current_app, g

LIMIT_HISTORII = 20

SCHEMAT = """
CREATE TABLE IF NOT EXISTS historia (
    dzialka_id TEXT PRIMARY KEY,
    przeznaczenie TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    data_sprawdzenia TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS zapisane (
    dzialka_id TEXT PRIMARY KEY,
    przeznaczenie TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    powierzchnia_m2 REAL,
    notatka TEXT NOT NULL DEFAULT '',
    data_dodania TEXT NOT NULL,
    data_zmiany TEXT NOT NULL
);
"""


def get_db() -> sqlite3.Connection:
    if "db_mpzp" not in g:
        folder = os.path.join(current_app.instance_path, "mpzp")
        os.makedirs(folder, exist_ok=True)
        g.db_mpzp = sqlite3.connect(os.path.join(folder, "mpzp.db"))
        g.db_mpzp.row_factory = sqlite3.Row
    return g.db_mpzp


def close_db(exception=None):
    db = g.pop("db_mpzp", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    db.commit()


def zapisz_w_historii(dzialka_id: str, przeznaczenie: str | None, lat: float, lon: float):
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO historia VALUES (?, ?, ?, ?, ?)",
        (dzialka_id, przeznaczenie, lat, lon, datetime.now().isoformat(timespec="seconds")),
    )
    # Zostawiamy tylko najnowsze wpisy. Kolejność po rowid, nie po dacie:
    # kilka sprawdzeń w tej samej sekundzie ma identyczną datę, a INSERT OR
    # REPLACE nadaje ponownie sprawdzonej działce nowy, największy rowid.
    db.execute(
        """DELETE FROM historia WHERE dzialka_id NOT IN (
               SELECT dzialka_id FROM historia ORDER BY rowid DESC LIMIT ?)""",
        (LIMIT_HISTORII,),
    )
    db.commit()


def historia() -> list[dict]:
    wiersze = get_db().execute(
        "SELECT * FROM historia ORDER BY rowid DESC"
    ).fetchall()
    return [dict(w) for w in wiersze]


# ---------- Moje działki (ETAP 44) ----------


def zapisane() -> list[dict]:
    wiersze = get_db().execute("SELECT * FROM zapisane ORDER BY data_dodania DESC, rowid DESC").fetchall()
    return [dict(w) for w in wiersze]


def zapisana(dzialka_id: str) -> dict | None:
    wiersz = get_db().execute("SELECT * FROM zapisane WHERE dzialka_id = ?", (dzialka_id,)).fetchone()
    return dict(wiersz) if wiersz else None


def zapisz_dzialke(dzialka_id: str, przeznaczenie, lat: float, lon: float, powierzchnia_m2, notatka: str) -> dict:
    """Dodaje działkę albo aktualizuje notatkę i dane (data dodania zostaje)."""
    teraz = datetime.now().isoformat(timespec="seconds")
    db = get_db()
    db.execute(
        """INSERT INTO zapisane (dzialka_id, przeznaczenie, lat, lon, powierzchnia_m2, notatka, data_dodania, data_zmiany)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(dzialka_id) DO UPDATE SET
               przeznaczenie = excluded.przeznaczenie,
               lat = excluded.lat,
               lon = excluded.lon,
               powierzchnia_m2 = excluded.powierzchnia_m2,
               notatka = excluded.notatka,
               data_zmiany = excluded.data_zmiany""",
        (dzialka_id, przeznaczenie, lat, lon, powierzchnia_m2, notatka, teraz, teraz),
    )
    db.commit()
    return zapisana(dzialka_id)


def usun_zapisana(dzialka_id: str) -> bool:
    db = get_db()
    usunieto = db.execute("DELETE FROM zapisane WHERE dzialka_id = ?", (dzialka_id,)).rowcount
    db.commit()
    return usunieto > 0
