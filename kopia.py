"""Kopia zapasowa danych użytkownika (folder instance/) jako jeden ZIP.

Co trafia do kopii: bazy SQLite wszystkich modułów (fiszki, powtórki,
historia działek, cache atlasu), wgrane PDF-y i pliki wyników
dostępności. Czego nie kopiujemy: granic gmin z PRG (to cache, pobierze
się ponownie) i pliku .env (klucze API zostają na komputerze).

Bazy kopiujemy przez sqlite3 `backup()`, a nie przez zwykłe skopiowanie
pliku — kopia jest spójna nawet wtedy, gdy aplikacja akurat zapisuje.
"""

import glob
import io
import os
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime

# Foldery w instance/, których nie kopiujemy (cache do odtworzenia).
POMIJANE = {os.path.join("atlas", "granice"), "logi"}  # logi: dziennik błędów (ETAP 127), nie dane

INSTRUKCJA = """Kopia zapasowa aplikacji Warsztat — {data}

Zawartość: folder instance/ — bazy wszystkich modułów (fiszki i
powtórki, historia i zapisane działki, cache i zestaw raportu atlasu,
koncepcje osiedli, akty prawne i historia pytań, projekty i punkty
terenowe, wybrany wskaźnik cen), wgrane PDF-y (fiszki, przepisy), zdjęcia z terenu i pliki
wyników dostępności.

Przywracanie:
1. Zamknij aplikację (zamknij okno terminala z serwerem).
2. W katalogu projektu (np. ~/warsztat) zmień nazwę obecnego folderu
   instance/ na instance_stary/ (na wszelki wypadek).
3. Rozpakuj ten ZIP w katalogu projektu — powstanie folder instance/.
4. Uruchom aplikację jak zwykle.
"""


def utworz_kopie(folder_instance: str) -> bytes:
    """ZIP z zawartością instance/ (ścieżki w ZIP zaczynają się od instance/)."""
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w", zipfile.ZIP_DEFLATED) as zip_:
        zip_.writestr("PRZYWRACANIE.txt", INSTRUKCJA.format(data=datetime.now().strftime("%d.%m.%Y %H:%M")))
        for katalog, podkatalogi, pliki in os.walk(folder_instance):
            wzgledny = os.path.relpath(katalog, folder_instance)
            podkatalogi[:] = [
                d for d in podkatalogi if os.path.normpath(os.path.join(wzgledny, d)) not in POMIJANE
            ]
            for nazwa in sorted(pliki):
                sciezka = os.path.join(katalog, nazwa)
                w_zipie = os.path.normpath(os.path.join("instance", wzgledny, nazwa))
                if nazwa.endswith(".db"):
                    zip_.writestr(w_zipie, _spojna_kopia_bazy(sciezka))
                elif not nazwa.endswith((".db-journal", ".db-wal", ".db-shm")):
                    zip_.write(sciezka, w_zipie)
    return bufor.getvalue()


def _spojna_kopia_bazy(sciezka: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        cel_sciezka = os.path.join(tmp, "kopia.db")
        zrodlo = sqlite3.connect(sciezka)
        cel = sqlite3.connect(cel_sciezka)
        try:
            zrodlo.backup(cel)
        finally:
            cel.close()
            zrodlo.close()
        with open(cel_sciezka, "rb") as plik:
            return plik.read()


# ---------- kopia automatyczna przy starcie (ETAP 97) ----------

WZOR_AUTO = "warsztat_auto_*.zip"


def ostatnia_kopia_automatyczna(folder_kopii: str) -> dict | None:
    """{"sciezka", "data"} najnowszej kopii automatycznej albo None."""
    pliki = glob.glob(os.path.join(folder_kopii, WZOR_AUTO))
    if not pliki:
        return None
    najnowszy = max(pliki, key=os.path.getmtime)
    return {"sciezka": najnowszy, "data": datetime.fromtimestamp(os.path.getmtime(najnowszy))}


def kopia_automatyczna(folder_instance: str, folder_kopii: str, co_ile_dni: int = 7, zostaw: int = 5, teraz: float | None = None) -> str | None:
    """Robi kopię, jeśli od ostatniej minęło co_ile_dni (0 = wyłączone).
    Zostawia `zostaw` najnowszych kopii automatycznych, starsze usuwa (kopii
    zrobionych ręcznie z przeglądarki nie rusza). Zwraca ścieżkę nowej kopii
    albo None, gdy nie było potrzeby."""
    teraz = time.time() if teraz is None else teraz
    if co_ile_dni <= 0 or not os.path.isdir(folder_instance) or not os.listdir(folder_instance):
        return None
    ostatnia = ostatnia_kopia_automatyczna(folder_kopii)
    if ostatnia and teraz - os.path.getmtime(ostatnia["sciezka"]) < co_ile_dni * 86400:
        return None
    os.makedirs(folder_kopii, exist_ok=True)
    sciezka = os.path.join(folder_kopii, f"warsztat_auto_{datetime.fromtimestamp(teraz):%Y%m%d_%H%M%S}.zip")
    tymczasowa = sciezka + ".tmp"  # przerwana kopia nie udaje pełnej
    with open(tymczasowa, "wb") as plik:
        plik.write(utworz_kopie(folder_instance))
    os.replace(tymczasowa, sciezka)
    os.utime(sciezka, (teraz, teraz))
    for stara in sorted(glob.glob(os.path.join(folder_kopii, WZOR_AUTO)), key=os.path.getmtime)[:-zostaw]:
        os.remove(stara)
    return sciezka
