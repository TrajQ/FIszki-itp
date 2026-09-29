"""Baza modułu przepisy (surowy sqlite3, jak w pozostałych modułach — D-004).

Akt prawny = wgrany PDF. Jego tekst dzielimy na jednostki (artykuły,
paragrafy — przepisy/tekst.py) i wkładamy do indeksu pełnotekstowego
SQLite FTS5. Indeks ignoruje polskie znaki, więc „dzialka” znajdzie
„działka”. Uwaga: tokenizer FTS5 (remove_diacritics) zdejmuje ogonki i
kreski, ale „ł” to dla Unicode osobna litera, nie „l” ze znakiem — dlatego
do indeksu i do zapytań wkładamy tekst po `sprowadz()`, a podgląd z
podświetleniem liczymy w Pythonie na oryginalnym tekście.
"""

import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime

from flask import current_app, g

SCHEMAT = """
CREATE TABLE IF NOT EXISTS akty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    nazwa_pliku TEXT NOT NULL,
    liczba_stron INTEGER NOT NULL,
    data_dodania TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jednostki (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    akt_id INTEGER NOT NULL REFERENCES akty(id) ON DELETE CASCADE,
    kolejnosc INTEGER NOT NULL,
    oznaczenie TEXT NOT NULL,
    naglowek TEXT,
    strona_od INTEGER NOT NULL,
    strona_do INTEGER NOT NULL,
    tekst TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jednostki_akt ON jednostki(akt_id, kolejnosc);

-- Indeks pełnotekstowy: rowid = jednostki.id, tekst po sprowadz()
-- (bez polskich znaków), więc nie nadaje się do wyświetlania.
CREATE VIRTUAL TABLE IF NOT EXISTS jednostki_fts USING fts5(
    tekst, tokenize='unicode61 remove_diacritics 2'
);

-- ETAP 62: zadane pytania z odpowiedzią (JSON: odpowiedź, cytaty z
-- oznaczeniem jednostki i stroną — kopia, żeby historia przetrwała zmiany).
CREATE TABLE IF NOT EXISTS pytania (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pytanie TEXT NOT NULL,
    akt_id INTEGER,
    wynik TEXT NOT NULL,
    data TEXT NOT NULL
);
"""

MAKS_WYNIKOW = 30
DLUGOSC_PODGLADU = 260
# Znaczniki trafień w podglądzie — znaki sterujące, których nie ma w tekście
# aktu; przeglądarka zamienia je na <mark> bez innerHTML.
ZNACZNIK_OD, ZNACZNIK_DO = "\x02", "\x03"


def _sprowadz_znak(znak: str) -> str:
    if znak in "łŁ":
        return "l"
    return unicodedata.normalize("NFD", znak)[0].lower()


def sprowadz(tekst: str) -> str:
    """Małe litery bez polskich znaków; długość tekstu bez zmian (znak za
    znak), więc pozycje trafień pasują do tekstu oryginalnego."""
    return "".join(_sprowadz_znak(z) for z in tekst)


def folder() -> str:
    sciezka = os.path.join(current_app.instance_path, "przepisy")
    os.makedirs(sciezka, exist_ok=True)
    return sciezka


def folder_plikow() -> str:
    sciezka = os.path.join(folder(), "pliki")
    os.makedirs(sciezka, exist_ok=True)
    return sciezka


def get_db() -> sqlite3.Connection:
    if "db_przepisy" not in g:
        g.db_przepisy = sqlite3.connect(os.path.join(folder(), "przepisy.db"))
        g.db_przepisy.row_factory = sqlite3.Row
        g.db_przepisy.execute("PRAGMA foreign_keys = ON")
    return g.db_przepisy


def close_db(exception=None):
    db = g.pop("db_przepisy", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    db.commit()


def dodaj_akt(nazwa: str, nazwa_pliku: str, liczba_stron: int, jednostki: list[dict]) -> int:
    db = get_db()
    akt_id = db.execute(
        "INSERT INTO akty (nazwa, nazwa_pliku, liczba_stron, data_dodania) VALUES (?, ?, ?, ?)",
        (nazwa, nazwa_pliku, liczba_stron, datetime.now().isoformat(timespec="seconds")),
    ).lastrowid
    for kolejnosc, j in enumerate(jednostki):
        jednostka_id = db.execute(
            """INSERT INTO jednostki (akt_id, kolejnosc, oznaczenie, naglowek, strona_od, strona_do, tekst)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (akt_id, kolejnosc, j["oznaczenie"], j["naglowek"], j["strona_od"], j["strona_do"], j["tekst"]),
        ).lastrowid
        db.execute("INSERT INTO jednostki_fts (rowid, tekst) VALUES (?, ?)", (jednostka_id, sprowadz(j["tekst"])))
    db.commit()
    return akt_id


def lista_aktow() -> list[dict]:
    wiersze = get_db().execute(
        """SELECT akty.*, COUNT(jednostki.id) AS liczba_jednostek
           FROM akty LEFT JOIN jednostki ON jednostki.akt_id = akty.id
           GROUP BY akty.id ORDER BY akty.nazwa COLLATE NOCASE"""
    ).fetchall()
    return [dict(w) for w in wiersze]


def akt(akt_id: int) -> dict | None:
    wiersz = get_db().execute("SELECT * FROM akty WHERE id = ?", (akt_id,)).fetchone()
    return dict(wiersz) if wiersz else None


def jednostki_aktu(akt_id: int) -> list[dict]:
    wiersze = get_db().execute(
        "SELECT * FROM jednostki WHERE akt_id = ? ORDER BY kolejnosc", (akt_id,)
    ).fetchall()
    return [dict(w) for w in wiersze]


def zmien_nazwe(akt_id: int, nazwa: str):
    db = get_db()
    db.execute("UPDATE akty SET nazwa = ? WHERE id = ?", (nazwa, akt_id))
    db.commit()


def usun_akt(akt_id: int) -> str | None:
    """Usuwa akt z jednostkami i indeksem; zwraca nazwę pliku do skasowania."""
    db = get_db()
    wiersz = db.execute("SELECT nazwa_pliku FROM akty WHERE id = ?", (akt_id,)).fetchone()
    if wiersz is None:
        return None
    db.execute("DELETE FROM jednostki_fts WHERE rowid IN (SELECT id FROM jednostki WHERE akt_id = ?)", (akt_id,))
    db.execute("DELETE FROM jednostki WHERE akt_id = ?", (akt_id,))
    db.execute("DELETE FROM akty WHERE id = ?", (akt_id,))
    db.commit()
    return wiersz["nazwa_pliku"]


# ---------- wyszukiwanie ----------

_SLOWO = re.compile(r"\w+", re.UNICODE)
_ODWOLANIE = re.compile(r"^\s*(art\.?|§)\s*(\d+[a-z]*)\s*$", re.IGNORECASE)


def terminy(tekst: str) -> list[tuple[str, bool]]:
    """Słowa użytkownika → [(termin bez polskich znaków, czy szukać po początku)].

    Polski odmienia wyrazy, a FTS5 nie ma polskiego stemmera. Prosty
    zamiennik: dłuższe słowa szukamy po początku — od 7 liter bez 2
    ostatnich („działki” → „dział…”: działka, działce, działkami), od 5
    liter bez ostatniej („planu” → „plan…”). Tekst w cudzysłowie to fraza
    szukana dokładnie.
    """
    wynik = []
    for fraza, zwykle in re.findall(r'"([^"]+)"|([^"]+)', sprowadz(tekst)):
        if fraza:
            slowa = _SLOWO.findall(fraza)
            if slowa:
                wynik.append((" ".join(slowa), False))
            continue
        for slowo in _SLOWO.findall(zwykle):
            if len(slowo) >= 7:
                wynik.append((slowo[:-2], True))
            elif len(slowo) >= 5:
                wynik.append((slowo[:-1], True))
            elif len(slowo) >= 2 or slowo.isdigit():
                wynik.append((slowo, False))
    return wynik


def zapytanie_fts(tekst: str) -> str | None:
    """Zapytanie FTS5: wszystkie terminy naraz (AND)."""
    czesci = [f'"{t}"' + ("*" if prefiks else "") for t, prefiks in terminy(tekst)]
    return " AND ".join(czesci) if czesci else None


def podglad(tekst: str, szukane: list[tuple[str, bool]]) -> str:
    """Fragment jednostki wokół pierwszego trafienia, trafienia w znacznikach.

    Szukamy w tekście sprowadzonym (bez polskich znaków) — ma tę samą
    długość, więc pozycje pasują do oryginału.
    """
    sprowadzony = sprowadz(tekst)
    trafienia = []
    for termin, prefiks in szukane:
        wzor = r"\b" + r"\W+".join(map(re.escape, termin.split())) + (r"\w*" if prefiks else r"\b")
        trafienia += [m.span() for m in re.finditer(wzor, sprowadzony)]
    trafienia.sort()
    poczatek = 0
    if trafienia and trafienia[0][0] > 80:
        poczatek = tekst.rfind(" ", 0, trafienia[0][0] - 80) + 1
    koniec = min(len(tekst), poczatek + DLUGOSC_PODGLADU)
    spacja = tekst.rfind(" ", poczatek, koniec)
    if koniec < len(tekst) and spacja > poczatek:
        koniec = spacja  # nie tniemy wyrazu
    czesci, pozycja = [], poczatek
    for od, do in trafienia:
        if od < pozycja or do > koniec:
            continue  # nakładające się albo poza fragmentem
        czesci += [tekst[pozycja:od], ZNACZNIK_OD, tekst[od:do], ZNACZNIK_DO]
        pozycja = do
    czesci.append(tekst[pozycja:koniec])
    return ("… " if poczatek else "") + "".join(czesci).replace("\n", " ") + (" …" if koniec < len(tekst) else "")


def szukaj(tekst: str, akt_id: int | None = None) -> list[dict]:
    """Jednostki pasujące do zapytania, najlepsze pierwsze.

    „art. 15” albo „§ 4” szuka jednostki o tym oznaczeniu, a nie słów.
    """
    db = get_db()
    warunek_aktu = " AND jednostki.akt_id = :akt" if akt_id else ""
    odwolanie = _ODWOLANIE.match(tekst)
    if odwolanie:
        rodzaj = "Art." if odwolanie.group(1).lower().startswith("art") else "§"
        wiersze = db.execute(
            f"""SELECT jednostki.*, akty.nazwa AS nazwa_aktu
                FROM jednostki JOIN akty ON akty.id = jednostki.akt_id
                WHERE jednostki.oznaczenie = :oznaczenie{warunek_aktu}
                ORDER BY akty.nazwa LIMIT :limit""",
            {"oznaczenie": f"{rodzaj} {odwolanie.group(2)}", "akt": akt_id, "limit": MAKS_WYNIKOW},
        ).fetchall()
        return [{**dict(w), "podglad": podglad(w["tekst"], [])} for w in wiersze]

    fts = zapytanie_fts(tekst)
    if fts is None:
        return []
    wiersze = db.execute(
        f"""SELECT jednostki.*, akty.nazwa AS nazwa_aktu
            FROM jednostki_fts
            JOIN jednostki ON jednostki.id = jednostki_fts.rowid
            JOIN akty ON akty.id = jednostki.akt_id
            WHERE jednostki_fts MATCH :fts{warunek_aktu}
            ORDER BY bm25(jednostki_fts) LIMIT :limit""",
        {"fts": fts, "akt": akt_id, "limit": MAKS_WYNIKOW},
    ).fetchall()
    szukane = terminy(tekst)
    return [{**dict(w), "podglad": podglad(w["tekst"], szukane)} for w in wiersze]


def jednostki_do_pytania(szukane: list[tuple[str, bool]], akt_id: int | None, limit: int) -> list[dict]:
    """Jednostki z którymkolwiek terminem (OR), najtrafniejsze pierwsze —
    kandydaci do odpowiedzi na pytanie zadane zwykłym zdaniem."""
    if not szukane:
        return []
    fts = " OR ".join(f'"{t}"' + ("*" if prefiks else "") for t, prefiks in szukane)
    warunek_aktu = " AND jednostki.akt_id = :akt" if akt_id else ""
    wiersze = get_db().execute(
        f"""SELECT jednostki.*, akty.nazwa AS nazwa_aktu
            FROM jednostki_fts
            JOIN jednostki ON jednostki.id = jednostki_fts.rowid
            JOIN akty ON akty.id = jednostki.akt_id
            WHERE jednostki_fts MATCH :fts AND jednostki.oznaczenie != 'Tytuł'{warunek_aktu}
            ORDER BY bm25(jednostki_fts) LIMIT :limit""",
        {"fts": fts, "akt": akt_id, "limit": limit},
    ).fetchall()
    return [dict(w) for w in wiersze]


# ---------- historia pytań ----------

MAKS_HISTORII = 30


def zapisz_pytanie(pytanie: str, akt_id: int | None, wynik: dict) -> int:
    db = get_db()
    pytanie_id = db.execute(
        "INSERT INTO pytania (pytanie, akt_id, wynik, data) VALUES (?, ?, ?, ?)",
        (pytanie, akt_id, json.dumps(wynik, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
    ).lastrowid
    db.commit()
    return pytanie_id


def historia_pytan() -> list[dict]:
    wiersze = get_db().execute("SELECT * FROM pytania ORDER BY id DESC LIMIT ?", (MAKS_HISTORII,)).fetchall()
    return [{**dict(w), "wynik": json.loads(w["wynik"])} for w in wiersze]


def usun_pytanie(pytanie_id: int) -> bool:
    db = get_db()
    usuniete = db.execute("DELETE FROM pytania WHERE id = ?", (pytanie_id,)).rowcount
    db.commit()
    return bool(usuniete)
