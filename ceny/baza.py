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

-- ETAP 106: transakcje działek z tego samego pliku RCN
CREATE TABLE IF NOT EXISTS rcn_dzialki (
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
    przeznaczenie TEXT NOT NULL,
    uzytek TEXT NOT NULL,
    nieruchomosc TEXT NOT NULL,
    dzialek INTEGER NOT NULL,
    lat REAL,
    lng REAL
);
CREATE INDEX IF NOT EXISTS rcn_dzialki_plik ON rcn_dzialki (plik_id);

-- ETAP 105: obszary narysowane na mapie transakcji (dzielnice, osiedla) do porównania
CREATE TABLE IF NOT EXISTS rcn_obszary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plik_id INTEGER NOT NULL REFERENCES rcn_pliki(id) ON DELETE CASCADE,
    nazwa TEXT NOT NULL,
    geojson TEXT NOT NULL
);

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


# kolumny dopisane do istniejących baz (jak w module teren)
KOLUMNY_DODANE = {
    "rcn_pliki": {"liczba_dzialek": "INTEGER NOT NULL DEFAULT 0", "odrzucone_dzialki": "TEXT NOT NULL DEFAULT '{}'"},  # ETAP 106
    "rcn_lokale": {"kondygnacja": "INTEGER"},  # ETAP 112: pliki zaimportowane wcześniej mają NULL
}


def init_db():
    db = get_db()
    db.executescript(SCHEMAT)
    for tabela, kolumny in KOLUMNY_DODANE.items():
        istniejace = {w["name"] for w in db.execute(f"PRAGMA table_info({tabela})")}
        for kolumna, definicja in kolumny.items():
            if kolumna not in istniejace:
                db.execute(f"ALTER TABLE {tabela} ADD COLUMN {kolumna} {definicja}")
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

POLA_LOKALU = ("data", "rok", "kwartal", "rynek", "rodzaj", "pow_m2", "cena", "cena_m2", "izby", "kondygnacja", "lat", "lng")
POLA_DZIALKI = ("data", "rok", "kwartal", "rynek", "rodzaj", "pow_m2", "cena", "cena_m2", "przeznaczenie", "uzytek",
                "nieruchomosc", "dzialek", "lat", "lng")


def zapisz_plik_rcn(nazwa: str, lokale: list[dict], odrzucone: dict, dzialki: list[dict] = (), odrzucone_dzialki: dict | None = None,
                    zastap: int | None = None) -> int:
    """Zapisuje transakcje z pliku. ETAP 136: `zastap` = id pliku, którego
    transakcje podmieniamy nowymi — id i narysowane obszary zostają."""
    db = get_db()
    wartosci = (nazwa, datetime.now().isoformat(timespec="seconds"), len(lokale), json.dumps(odrzucone, ensure_ascii=False),
                len(dzialki), json.dumps(odrzucone_dzialki or {}, ensure_ascii=False))
    if zastap is None:
        plik_id = db.execute(
            "INSERT INTO rcn_pliki (nazwa, data_importu, liczba, odrzucone, liczba_dzialek, odrzucone_dzialki) VALUES (?, ?, ?, ?, ?, ?)",
            wartosci,
        ).lastrowid
    else:
        plik_id = zastap
        db.execute(
            "UPDATE rcn_pliki SET nazwa = ?, data_importu = ?, liczba = ?, odrzucone = ?, liczba_dzialek = ?, odrzucone_dzialki = ? WHERE id = ?",
            (*wartosci, plik_id),
        )
        db.execute("DELETE FROM rcn_lokale WHERE plik_id = ?", (plik_id,))
        db.execute("DELETE FROM rcn_dzialki WHERE plik_id = ?", (plik_id,))
    for tabela, pola, wiersze in (("rcn_lokale", POLA_LOKALU, lokale), ("rcn_dzialki", POLA_DZIALKI, dzialki)):
        db.executemany(
            f"INSERT INTO {tabela} (plik_id, {', '.join(pola)}) VALUES (?, {', '.join('?' * len(pola))})",
            [(plik_id, *(w[k] for k in pola)) for w in wiersze],
        )
    db.commit()
    return plik_id


def _plik(w) -> dict:
    return {**dict(w), "odrzucone": json.loads(w["odrzucone"]), "odrzucone_dzialki": json.loads(w["odrzucone_dzialki"])}


def pliki_rcn() -> list[dict]:
    return [_plik(w) for w in get_db().execute("SELECT * FROM rcn_pliki ORDER BY id DESC")]


def plik_rcn(plik_id: int) -> dict | None:
    w = get_db().execute("SELECT * FROM rcn_pliki WHERE id = ?", (plik_id,)).fetchone()
    return _plik(w) if w else None


def _transakcje(tabela: str, plik_id: int, rowne: dict, od_roku: int | None, do_roku: int | None) -> tuple[list[str], list]:
    """Warunki WHERE wspólne dla lokali i działek: plik, lata, pola równe wartości."""
    warunki, parametry = ["plik_id = ?"], [plik_id]
    for pole, wartosc in rowne.items():
        if wartosc:
            warunki.append(f"{pole} = ?")
            parametry.append(wartosc)
    if od_roku:
        warunki.append("rok >= ?")
        parametry.append(od_roku)
    if do_roku:
        warunki.append("rok <= ?")
        parametry.append(do_roku)
    return warunki, parametry


def lokale_rcn(plik_id: int, rynek: str | None = None, od_roku: int | None = None, do_roku: int | None = None,
               izby: str | None = None, rodzaj: str | None = None, pietro: tuple[int, int] | None = None) -> list[dict]:
    warunki, parametry = _transakcje("rcn_lokale", plik_id, {"rynek": rynek, "rodzaj": rodzaj}, od_roku, do_roku)
    if pietro:
        warunki.append("kondygnacja BETWEEN ? AND ?")
        parametry.extend(pietro)
    if izby == "4+":
        warunki.append("izby >= 4")
    elif izby:
        warunki.append("izby = ?")
        parametry.append(int(izby))
    return [dict(w) for w in get_db().execute(f"SELECT * FROM rcn_lokale WHERE {' AND '.join(warunki)}", parametry)]


def dzialki_rcn(plik_id: int, rynek: str | None = None, od_roku: int | None = None, do_roku: int | None = None,
                rodzaj: str | None = None, przeznaczenie: str | None = None, nieruchomosc: str | None = None) -> list[dict]:
    warunki, parametry = _transakcje(
        "rcn_dzialki", plik_id, {"rynek": rynek, "rodzaj": rodzaj, "przeznaczenie": przeznaczenie, "nieruchomosc": nieruchomosc},
        od_roku, do_roku)
    return [dict(w) for w in get_db().execute(f"SELECT * FROM rcn_dzialki WHERE {' AND '.join(warunki)}", parametry)]


def w_prostokacie(tabela: str, lat_min: float, lat_max: float, lng_min: float, lng_max: float) -> dict[int, list[dict]]:
    """Transakcje wszystkich plików w prostokącie współrzędnych, pogrupowane
    po pliku (ETAP 109: ceny w okolicy działki i obszaru osiedla)."""
    assert tabela in ("rcn_lokale", "rcn_dzialki")
    po_pliku: dict[int, list[dict]] = {}
    for w in get_db().execute(
        f"SELECT * FROM {tabela} WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?", (lat_min, lat_max, lng_min, lng_max)
    ):
        po_pliku.setdefault(w["plik_id"], []).append(dict(w))
    return po_pliku


def wartosci_pola(plik_id: int, pole: str, tabela: str = "rcn_lokale") -> list[dict]:
    """Wartości pola z liczbą transakcji (do list w filtrach), od najczęstszej."""
    assert (tabela, pole) in {("rcn_lokale", "rodzaj"), ("rcn_dzialki", "rodzaj"), ("rcn_dzialki", "przeznaczenie"),
                              ("rcn_dzialki", "nieruchomosc"), ("rcn_lokale", "rok"), ("rcn_dzialki", "rok")}
    kolejnosc = f"{pole}" if pole == "rok" else "liczba DESC"  # lata rosnąco, reszta od najczęstszej
    return [{"wartosc": w[0], "liczba": w[1]} for w in get_db().execute(
        f"SELECT {pole}, COUNT(*) AS liczba FROM {tabela} WHERE plik_id = ? GROUP BY {pole} ORDER BY {kolejnosc}", (plik_id,))]


def usun_plik_rcn(plik_id: int) -> bool:
    db = get_db()
    usuniete = db.execute("DELETE FROM rcn_pliki WHERE id = ?", (plik_id,)).rowcount
    db.commit()
    return bool(usuniete)


# ---------- obszary do porównania (ETAP 105) ----------


def obszary_rcn(plik_id: int) -> list[dict]:
    return [
        {"id": w["id"], "nazwa": w["nazwa"], "geometria": json.loads(w["geojson"])}
        for w in get_db().execute("SELECT * FROM rcn_obszary WHERE plik_id = ? ORDER BY id", (plik_id,))
    ]


def dodaj_obszar_rcn(plik_id: int, nazwa: str, geometria: dict) -> int:
    db = get_db()
    obszar_id = db.execute(
        "INSERT INTO rcn_obszary (plik_id, nazwa, geojson) VALUES (?, ?, ?)", (plik_id, nazwa, json.dumps(geometria))
    ).lastrowid
    db.commit()
    return obszar_id


def zmien_nazwe_obszaru(obszar_id: int, nazwa: str) -> bool:
    db = get_db()
    zmienione = db.execute("UPDATE rcn_obszary SET nazwa = ? WHERE id = ?", (nazwa, obszar_id)).rowcount
    db.commit()
    return bool(zmienione)


def usun_obszar_rcn(obszar_id: int) -> bool:
    db = get_db()
    usuniete = db.execute("DELETE FROM rcn_obszary WHERE id = ?", (obszar_id,)).rowcount
    db.commit()
    return bool(usuniete)
