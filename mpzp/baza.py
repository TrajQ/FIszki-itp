"""Baza modułu mpzp (surowy sqlite3, jak w pozostałych modułach — D-004).

Jedna tabela: historia sprawdzonych działek, żeby łatwo do nich wrócić.
Trzymamy tylko ostatnie LIMIT_HISTORII wpisów, bez duplikatów działki.
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
