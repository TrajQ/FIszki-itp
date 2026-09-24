"""Surowy sqlite3 — bez ORM (decyzja D-004, moduł ma tylko dwie tabele)."""

import os
import sqlite3

from flask import current_app, g

SCHEMAT = """
CREATE TABLE IF NOT EXISTS pdfy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa_oryginalna TEXT NOT NULL,
    nazwa_pliku TEXT NOT NULL,
    data_dodania TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fiszki (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_id INTEGER NOT NULL REFERENCES pdfy(id),
    strona INTEGER NOT NULL,
    fragment_tekstu TEXT NOT NULL,
    pytanie TEXT NOT NULL,
    odpowiedz TEXT NOT NULL,
    data_utworzenia TEXT NOT NULL
);
"""


def _sciezka_bazy() -> str:
    folder = os.path.join(current_app.instance_path, "fiszki")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "fiszki.db")


def folder_plikow() -> str:
    folder = os.path.join(current_app.instance_path, "fiszki", "pliki")
    os.makedirs(folder, exist_ok=True)
    return folder


def get_db() -> sqlite3.Connection:
    if "db_fiszki" not in g:
        g.db_fiszki = sqlite3.connect(_sciezka_bazy())
        g.db_fiszki.row_factory = sqlite3.Row
        g.db_fiszki.execute("PRAGMA foreign_keys = ON")
    return g.db_fiszki


def close_db(exception=None):
    db = g.pop("db_fiszki", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    db.commit()
