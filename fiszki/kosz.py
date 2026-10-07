"""Kosz fiszek: cofnięcie usunięcia PDF-a albo fiszki (ETAP 212).

Usunięcie nie kasuje od razu: wszystkie wiersze usuwanego PDF-a (albo
fiszki) z tabel, które się do niego odnoszą — fiszki, stan powtórek,
tematy, egzaminy, obrazy, zasłony, wyjaśnienia (historia odpowiedzi zostaje) —
zapisujemy jako JSON w tabeli `kosz`, a pliki (PDF, wycinki rysunków)
przenosimy do instance/fiszki/kosz/. Potem usuwamy jak dotąd, więc reszta
modułu nic o koszu nie wie. Przywrócenie wstawia te same wiersze z tymi
samymi numerami (AUTOINCREMENT nie używa ponownie usuniętych numerów) i
przenosi pliki z powrotem. Po DNI_W_KOSZU dniach wpis i pliki znikają.

Lista tabel jest jawna: nowa tabela z fiszka_id albo pdf_id musi trafić
do TABELE_FISZKI, TABELE_PDF albo TABELE_ZOSTAJA (pilnuje tego test).
"""

import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta

from flask import current_app

DNI_W_KOSZU = 30
# kolejność wstawiania przy przywracaniu: najpierw tabele, do których odwołują się inne
TABELE_PDF = (("pdfy", "id"), ("pdf_skroty", "pdf_id"), ("egzaminy", "pdf_id"), ("fiszki", "pdf_id"))
TABELE_FISZKI = ("powtorki", "tematy_fiszek", "obrazy_fiszek", "zaslony_fiszek", "wyjasnienia_fiszek", "miejsca_fiszek")
# Tabele z fiszka_id, które przy usuwaniu zostają (bez ON DELETE CASCADE): historia
# odpowiedzi (statystyki dni się nie zmieniają) i zastosowane wyniki z telefonu.
TABELE_ZOSTAJA = ("dziennik_powtorek", "powtorki_z_telefonu")


def folder() -> str:
    sciezka = os.path.join(current_app.instance_path, "fiszki", "kosz")
    os.makedirs(sciezka, exist_ok=True)
    return sciezka


def _wiersze(db: sqlite3.Connection, tabela: str, kolumna: str, wartosci: list[int]) -> list[dict]:
    if not wartosci:
        return []
    znaki = ",".join("?" * len(wartosci))
    return [dict(w) for w in db.execute(f"SELECT * FROM {tabela} WHERE {kolumna} IN ({znaki})", wartosci)]


def _zbierz(db: sqlite3.Connection, pdf_id: int | None, fiszki_ids: list[int]) -> dict[str, list[dict]]:
    dane = {}
    if pdf_id is not None:
        for tabela, kolumna in TABELE_PDF:
            dane[tabela] = _wiersze(db, tabela, kolumna, [pdf_id])
    else:
        dane["fiszki"] = _wiersze(db, "fiszki", "id", fiszki_ids)
    for tabela in TABELE_FISZKI:
        dane[tabela] = _wiersze(db, tabela, "fiszka_id", fiszki_ids)
    return dane


def _w_innych_wpisach(db: sqlite3.Connection, nazwa: str, kosz_id: int) -> bool:
    """Czy plik w koszu jest potrzebny innemu wpisowi (ten sam wycinek dwóch fiszek z zasłonami)."""
    return any(nazwa in (n for _, n in json.loads(w[0]))
               for w in db.execute("SELECT pliki_json FROM kosz WHERE id != ?", (kosz_id,)))


def _przenies_pliki(pliki: list[tuple[str, str]], do_kosza: bool, wspolne: set[str] = frozenset()) -> None:
    """pliki: [(folder źródłowy, nazwa)] — do kosza albo z powrotem. Plik
    używany też przez fiszki spoza kosza (wycinek z zasłonami, ETAP 185)
    jest do kosza kopiowany, nie przenoszony; przy przywróceniu kopia z
    kosza znika, gdy oryginał jest na miejscu."""
    for katalog, nazwa in pliki:
        w_folderze, w_koszu = os.path.join(katalog, nazwa), os.path.join(folder(), nazwa)
        if do_kosza:
            if os.path.exists(w_folderze):
                (shutil.copy2 if nazwa in wspolne else shutil.move)(w_folderze, w_koszu)
        elif os.path.exists(w_koszu):
            if os.path.exists(w_folderze):
                if nazwa not in wspolne:
                    os.remove(w_koszu)
            else:
                (shutil.copy2 if nazwa in wspolne else shutil.move)(w_koszu, w_folderze)


def odloz(db: sqlite3.Connection, folder_pdf: str, folder_obrazow: str, pdf_id: int | None = None, fiszka_id: int | None = None) -> int:
    """Zapisuje PDF (z fiszkami) albo jedną fiszkę w koszu i przenosi pliki → id wpisu.
    Samo usunięcie wierszy robi wywołujący (jak przed ETAPem 212)."""
    if pdf_id is not None:
        fiszki_ids = [w[0] for w in db.execute("SELECT id FROM fiszki WHERE pdf_id = ?", (pdf_id,))]
    else:
        fiszki_ids = [fiszka_id]
    dane = _zbierz(db, pdf_id, fiszki_ids)
    pliki = [(folder_obrazow, w["plik"]) for w in dane["obrazy_fiszek"]]
    if pdf_id is not None:
        pdf = dane["pdfy"][0]
        pliki.append((folder_pdf, pdf["nazwa_pliku"]))
        opis = f"{pdf['nazwa_oryginalna']} — fiszek: {len(fiszki_ids)}"
    else:
        f = dane["fiszki"][0]
        nazwa = db.execute("SELECT nazwa_oryginalna FROM pdfy WHERE id = ?", (f["pdf_id"],)).fetchone()
        opis = f"„{f['pytanie'][:80]}” ({nazwa[0] if nazwa else 'plik'})"
    znaki = ",".join("?" * len(fiszki_ids))
    wspolne = {w[0] for w in db.execute(f"SELECT plik FROM obrazy_fiszek WHERE fiszka_id NOT IN ({znaki})", fiszki_ids)} if fiszki_ids else set()
    _przenies_pliki(pliki, do_kosza=True, wspolne=wspolne)
    kosz_id = db.execute(
        "INSERT INTO kosz (rodzaj, opis, dane_json, pliki_json, data) VALUES (?, ?, ?, ?, ?)",
        ("pdf" if pdf_id is not None else "fiszka", opis, json.dumps(dane, ensure_ascii=False),
         json.dumps([[("pdf" if k == folder_pdf else "obraz"), n] for k, n in pliki]), datetime.now().isoformat(timespec="seconds")),
    ).lastrowid
    db.commit()
    return kosz_id


class BladKosza(ValueError):
    """Nie da się przywrócić wpisu."""


def przywroc(db: sqlite3.Connection, kosz_id: int, folder_pdf: str, folder_obrazow: str) -> dict:
    wpis = db.execute("SELECT * FROM kosz WHERE id = ?", (kosz_id,)).fetchone()
    if wpis is None:
        raise BladKosza("Tego wpisu nie ma już w koszu.")
    dane = json.loads(wpis["dane_json"])
    if wpis["rodzaj"] == "fiszka":
        pdf_id = dane["fiszki"][0]["pdf_id"]
        if db.execute("SELECT 1 FROM pdfy WHERE id = ?", (pdf_id,)).fetchone() is None:
            raise BladKosza("Plik PDF tej fiszki jest usunięty — najpierw przywróć plik.")
    kolejnosc = [t for t, _ in TABELE_PDF] + list(TABELE_FISZKI)
    try:
        for tabela in kolejnosc:
            for w in dane.get(tabela, []):
                kolumny = list(w)
                db.execute(f"INSERT INTO {tabela} ({', '.join(kolumny)}) VALUES ({', '.join('?' * len(kolumny))})", [w[k] for k in kolumny])
        db.execute("DELETE FROM kosz WHERE id = ?", (kosz_id,))
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise BladKosza(f"Nie da się przywrócić: {e}.") from None
    pliki = [(folder_pdf if k == "pdf" else folder_obrazow, n) for k, n in json.loads(wpis["pliki_json"])]
    potrzebne = {n for _, n in pliki if _w_innych_wpisach(db, n, kosz_id)}  # wpis już usunięty — liczą się pozostałe
    db.commit()
    _przenies_pliki(pliki, do_kosza=False, wspolne=potrzebne)
    return {"rodzaj": wpis["rodzaj"], "pdf_id": dane["fiszki"][0]["pdf_id"] if dane.get("fiszki") else (dane.get("pdfy") or [{}])[0].get("id")}


def lista(db: sqlite3.Connection) -> list[dict]:
    return [dict(w) for w in db.execute("SELECT id, rodzaj, opis, data FROM kosz ORDER BY id DESC")]


def wyczysc_stare(db: sqlite3.Connection, teraz: datetime | None = None) -> int:
    """Wpisy starsze niż DNI_W_KOSZU dni — razem z plikami."""
    granica = ((teraz or datetime.now()) - timedelta(days=DNI_W_KOSZU)).isoformat(timespec="seconds")
    stare = db.execute("SELECT id, pliki_json FROM kosz WHERE data < ?", (granica,)).fetchall()
    for w in stare:
        for _, nazwa in json.loads(w["pliki_json"]):
            sciezka = os.path.join(folder(), nazwa)
            if os.path.exists(sciezka) and not _w_innych_wpisach(db, nazwa, w["id"]):
                os.remove(sciezka)
        db.execute("DELETE FROM kosz WHERE id = ?", (w["id"],))
    db.commit()
    return len(stare)
