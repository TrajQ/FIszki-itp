"""Baza modułu teren (surowy sqlite3, jak w pozostałych modułach — D-004).

Projekt = nazwa + pola formularza + losowy klucz, po którym import
rozpoznaje, że plik z telefonu należy do tego projektu. Punkt ma uid
nadany na telefonie — ponowny import tego samego pliku nie dubluje
punktów. Zdjęcia leżą jako pliki JPEG w instance/teren/zdjecia/.
"""

import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import current_app, g

SCHEMAT = """
CREATE TABLE IF NOT EXISTS projekty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    klucz TEXT NOT NULL UNIQUE,
    pola TEXT NOT NULL,
    data_utworzenia TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS punkty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projekt_id INTEGER NOT NULL REFERENCES projekty(id) ON DELETE CASCADE,
    uid TEXT NOT NULL,
    lat REAL,
    lng REAL,
    dokladnosc_m REAL,
    czas TEXT NOT NULL,
    wartosci TEXT NOT NULL,
    uwagi TEXT NOT NULL DEFAULT '',
    zdjecie TEXT,
    data_importu TEXT NOT NULL,
    UNIQUE (projekt_id, uid)
);
"""

# Kolumny dodane później: CREATE TABLE IF NOT EXISTS nie dodaje ich do
# istniejącej bazy, więc dopisujemy je przy starcie (bez utraty danych).
KOLUMNY_DODANE = {
    "punkty": {
        # ETAP 72: 1 = położenie poprawione ręcznie w Warsztacie (dokładność GPS nie obowiązuje)
        "polozenie_reczne": "INTEGER NOT NULL DEFAULT 0",
        # ETAP 72: czas ostatniej poprawki w Warsztacie
        "data_poprawki": "TEXT",
        # ETAP 219: podpis zdjęcia i kierunek patrzenia aparatu (stopnie: 0, 45, … 315)
        "zdjecie_opis": "TEXT",
        "zdjecie_kierunek": "INTEGER",
    },
    "projekty": {
        # ETAP 83: obszar prac [południe, zachód, północ, wschód] — podkład mapy w formularzu
        "obszar": "TEXT",
        # ETAP 86: planowany termin wyjścia w teren (RRRR-MM-DD) — w kalendarzu na stronie głównej
        "termin": "TEXT",
        # ETAP 93: inwentaryzacja albo ankieta
        "rodzaj": "TEXT NOT NULL DEFAULT 'inwentaryzacja'",
        # ETAP 212: kosz — data usunięcia; projekt z punktami i zdjęciami zostaje DNI_W_KOSZU dni
        "usunieto": "TEXT",
    },
}
DNI_W_KOSZU = 30


def folder() -> str:
    sciezka = os.path.join(current_app.instance_path, "teren")
    os.makedirs(sciezka, exist_ok=True)
    return sciezka


def folder_zdjec() -> str:
    sciezka = os.path.join(folder(), "zdjecia")
    os.makedirs(sciezka, exist_ok=True)
    return sciezka


def get_db() -> sqlite3.Connection:
    if "db_teren" not in g:
        g.db_teren = sqlite3.connect(os.path.join(folder(), "teren.db"))
        g.db_teren.row_factory = sqlite3.Row
        g.db_teren.execute("PRAGMA foreign_keys = ON")
    return g.db_teren


def close_db(exception=None):
    db = g.pop("db_teren", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    for tabela, kolumny in KOLUMNY_DODANE.items():
        istniejace = {w["name"] for w in db.execute(f"PRAGMA table_info({tabela})")}
        for kolumna, definicja in kolumny.items():
            if kolumna not in istniejace:
                db.execute(f"ALTER TABLE {tabela} ADD COLUMN {kolumna} {definicja}")
    db.commit()


def _projekt(wiersz) -> dict:
    wynik = {**dict(wiersz), "pola": json.loads(wiersz["pola"])}
    wynik["obszar"] = json.loads(wynik["obszar"]) if wynik.get("obszar") else None
    return wynik


def ustaw_obszar(projekt_id: int, obszar: list[float] | None):
    db = get_db()
    db.execute("UPDATE projekty SET obszar = ? WHERE id = ?", (json.dumps(obszar) if obszar else None, projekt_id))
    db.commit()


def ustaw_rodzaj(projekt_id: int, rodzaj: str):
    db = get_db()
    db.execute("UPDATE projekty SET rodzaj = ? WHERE id = ?", (rodzaj, projekt_id))
    db.commit()


def ustaw_termin(projekt_id: int, termin: str | None):
    db = get_db()
    db.execute("UPDATE projekty SET termin = ? WHERE id = ?", (termin, projekt_id))
    db.commit()


def projekty() -> list[dict]:
    wiersze = get_db().execute(
        """SELECT projekty.*, COUNT(punkty.id) AS liczba_punktow, MAX(punkty.czas) AS ostatni_pomiar
           FROM projekty LEFT JOIN punkty ON punkty.projekt_id = projekty.id
           WHERE projekty.usunieto IS NULL
           GROUP BY projekty.id ORDER BY projekty.id DESC"""
    ).fetchall()
    return [_projekt(w) for w in wiersze]


def projekt(projekt_id: int) -> dict | None:
    wiersz = get_db().execute("SELECT * FROM projekty WHERE id = ? AND usunieto IS NULL", (projekt_id,)).fetchone()
    return _projekt(wiersz) if wiersz else None


def utworz_projekt(nazwa: str, pola: list[dict], rodzaj: str = "inwentaryzacja") -> int:
    db = get_db()
    projekt_id = db.execute(
        "INSERT INTO projekty (nazwa, klucz, pola, data_utworzenia, rodzaj) VALUES (?, ?, ?, ?, ?)",
        (nazwa, secrets.token_urlsafe(12), json.dumps(pola, ensure_ascii=False), datetime.now().isoformat(timespec="seconds"), rodzaj),
    ).lastrowid
    db.commit()
    return projekt_id


def zmien_projekt(projekt_id: int, nazwa: str, pola: list[dict]):
    db = get_db()
    db.execute("UPDATE projekty SET nazwa = ?, pola = ? WHERE id = ?", (nazwa, json.dumps(pola, ensure_ascii=False), projekt_id))
    db.commit()


def _usun_pliki(nazwy):
    for nazwa in nazwy:
        if nazwa:
            try:
                os.remove(os.path.join(folder_zdjec(), nazwa))
            except OSError:
                pass  # plik mógł zniknąć ręcznie


def usun_projekt(projekt_id: int):
    """Do kosza (ETAP 212): projekt znika z list, punkty i zdjęcia zostają."""
    db = get_db()
    db.execute("UPDATE projekty SET usunieto = ? WHERE id = ?", (datetime.now().isoformat(timespec="seconds"), projekt_id))
    db.commit()


def w_koszu() -> list[dict]:
    """Usunięte projekty (najnowsze najpierw); starsze niż DNI_W_KOSZU dni — usuwa na dobre ze zdjęciami."""
    db = get_db()
    granica = (datetime.now() - timedelta(days=DNI_W_KOSZU)).isoformat(timespec="seconds")
    for (projekt_id,) in db.execute("SELECT id FROM projekty WHERE usunieto IS NOT NULL AND usunieto < ?", (granica,)).fetchall():
        _usun_na_dobre(projekt_id)
    return [dict(w) for w in db.execute(
        """SELECT projekty.id, projekty.nazwa, projekty.usunieto, COUNT(punkty.id) AS liczba_punktow
           FROM projekty LEFT JOIN punkty ON punkty.projekt_id = projekty.id
           WHERE projekty.usunieto IS NOT NULL GROUP BY projekty.id ORDER BY projekty.usunieto DESC""")]


def przywroc_projekt(projekt_id: int) -> bool:
    db = get_db()
    zmienione = db.execute("UPDATE projekty SET usunieto = NULL WHERE id = ? AND usunieto IS NOT NULL", (projekt_id,)).rowcount
    db.commit()
    return bool(zmienione)


def _usun_na_dobre(projekt_id: int):
    db = get_db()
    zdjecia = [w["zdjecie"] for w in db.execute("SELECT zdjecie FROM punkty WHERE projekt_id = ?", (projekt_id,))]
    db.execute("DELETE FROM punkty WHERE projekt_id = ?", (projekt_id,))
    db.execute("DELETE FROM projekty WHERE id = ?", (projekt_id,))
    db.commit()
    _usun_pliki(zdjecia)


def punkty(projekt_id: int) -> list[dict]:
    wiersze = get_db().execute("SELECT * FROM punkty WHERE projekt_id = ? ORDER BY czas, id", (projekt_id,)).fetchall()
    return [{**dict(w), "wartosci": json.loads(w["wartosci"])} for w in wiersze]


def zapisz_punkty(projekt_id: int, nowe: list[dict]) -> tuple[int, int]:
    """Zapisuje punkty z pliku; (dodane, pominięte — już były)."""
    db = get_db()
    dodane = pominiete = 0
    zapisane_zdjecia = []
    try:
        for p in nowe:
            if db.execute("SELECT 1 FROM punkty WHERE projekt_id = ? AND uid = ?", (projekt_id, p["uid"])).fetchone():
                pominiete += 1
                continue
            nazwa_zdjecia = None
            if p["zdjecie"]:
                nazwa_zdjecia = f"{projekt_id}_{p['uid']}.jpg"
                with open(os.path.join(folder_zdjec(), nazwa_zdjecia), "wb") as plik:
                    plik.write(p["zdjecie"])
                zapisane_zdjecia.append(nazwa_zdjecia)
            db.execute(
                """INSERT INTO punkty (projekt_id, uid, lat, lng, dokladnosc_m, czas, wartosci, uwagi, zdjecie, data_importu,
                                     zdjecie_opis, zdjecie_kierunek)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (projekt_id, p["uid"], p["lat"], p["lng"], p["dokladnosc_m"], p["czas"],
                 json.dumps(p["wartosci"], ensure_ascii=False), p["uwagi"], nazwa_zdjecia,
                 datetime.now().isoformat(timespec="seconds"),
                 (p.get("zdjecie_opis") or None) if nazwa_zdjecia else None,
                 p.get("zdjecie_kierunek") if nazwa_zdjecia else None),
            )
            dodane += 1
        db.commit()
    except Exception:
        db.rollback()
        _usun_pliki(zapisane_zdjecia)
        raise
    return dodane, pominiete


def usun_punkt(projekt_id: int, punkt_id: int) -> bool:
    db = get_db()
    wiersz = db.execute("SELECT zdjecie FROM punkty WHERE id = ? AND projekt_id = ?", (punkt_id, projekt_id)).fetchone()
    if wiersz is None:
        return False
    db.execute("DELETE FROM punkty WHERE id = ?", (punkt_id,))
    db.commit()
    _usun_pliki([wiersz["zdjecie"]])
    return True


def popraw_punkt(projekt_id: int, punkt_id: int, poprawka: dict) -> bool:
    """Zapisuje poprawkę (ETAP 72). Nowe położenie = położenie ręczne,
    dokładność GPS przestaje obowiązywać."""
    db = get_db()
    if db.execute("SELECT 1 FROM punkty WHERE id = ? AND projekt_id = ?", (punkt_id, projekt_id)).fetchone() is None:
        return False
    teraz = datetime.now().isoformat(timespec="seconds")
    db.execute(
        "UPDATE punkty SET wartosci = ?, uwagi = ?, data_poprawki = ? WHERE id = ?",
        (json.dumps(poprawka["wartosci"], ensure_ascii=False), poprawka["uwagi"], teraz, punkt_id),
    )
    if "lat" in poprawka:
        db.execute(
            "UPDATE punkty SET lat = ?, lng = ?, dokladnosc_m = NULL, polozenie_reczne = 1 WHERE id = ?",
            (poprawka["lat"], poprawka["lng"], punkt_id),
        )
    for kolumna in ("zdjecie_opis", "zdjecie_kierunek"):  # ETAP 219; nazwy kolumn ze stałej listy
        if kolumna in poprawka:
            db.execute(f"UPDATE punkty SET {kolumna} = ? WHERE id = ?", (poprawka[kolumna] if poprawka[kolumna] != "" else None, punkt_id))
    db.commit()
    return True


def ostatnio_zmienione(limit: int) -> list[dict]:
    """ETAP 141: projekty od ostatniej zmiany (utworzenie, import punktów)."""
    wiersze = get_db().execute(
        """SELECT projekty.id, projekty.nazwa, COUNT(punkty.id) AS liczba_punktow,
                  MAX(projekty.data_utworzenia, COALESCE(MAX(punkty.data_importu), '')) AS kiedy
           FROM projekty LEFT JOIN punkty ON punkty.projekt_id = projekty.id
           WHERE projekty.usunieto IS NULL
           GROUP BY projekty.id ORDER BY kiedy DESC LIMIT ?""", (limit,)
    ).fetchall()
    return [dict(w) for w in wiersze]
