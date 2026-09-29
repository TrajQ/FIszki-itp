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

-- ETAP 6: stan powtórek (system Leitnera, zob. fiszki/powtorki.py).
-- Osobna tabela zamiast nowych kolumn w `fiszki`, bo CREATE TABLE IF NOT
-- EXISTS nie dodaje kolumn do istniejącej bazy — tak stare bazy działają
-- bez migracji. Brak wiersza = fiszka nowa (pudełko 1, do powtórki).
CREATE TABLE IF NOT EXISTS powtorki (
    fiszka_id INTEGER PRIMARY KEY REFERENCES fiszki(id) ON DELETE CASCADE,
    pudelko INTEGER NOT NULL,
    nastepna_powtorka TEXT NOT NULL,
    liczba_powtorek INTEGER NOT NULL DEFAULT 0,
    ostatnia_powtorka TEXT
);

-- ETAP 18: dziennik każdej odpowiedzi w powtórce — do statystyk nauki.
-- Bez klucza obcego z kaskadą celowo: usunięcie fiszki nie kasuje
-- historii nauki (liczba powtórek w danym dniu się nie zmienia).
-- ETAP 50: tematy fiszek (wiele na fiszkę). Kaskada: usunięcie fiszki
-- usuwa jej tematy.
CREATE TABLE IF NOT EXISTS tematy_fiszek (
    fiszka_id INTEGER NOT NULL REFERENCES fiszki(id) ON DELETE CASCADE,
    temat TEXT NOT NULL,
    PRIMARY KEY (fiszka_id, temat)
);

-- ETAP 51: terminy egzaminów; zakres: temat albo plik albo (oba NULL) wszystko.
-- Usunięcie PDF-a usuwa egzaminy przypisane do niego.
CREATE TABLE IF NOT EXISTS egzaminy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    data TEXT NOT NULL,
    temat TEXT,
    pdf_id INTEGER REFERENCES pdfy(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dziennik_powtorek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fiszka_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    wynik TEXT NOT NULL
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
