"""Kopia zapasowa danych użytkownika (folder instance/) jako jeden ZIP.

Co trafia do kopii: bazy SQLite wszystkich modułów (fiszki, powtórki,
historia działek, cache atlasu), wgrane PDF-y i pliki wyników
dostępności. Czego nie kopiujemy: granic gmin z PRG (to cache, pobierze
się ponownie) i pliku .env (klucze API zostają na komputerze).

Bazy kopiujemy przez sqlite3 `backup()`, a nie przez zwykłe skopiowanie
pliku — kopia jest spójna nawet wtedy, gdy aplikacja akurat zapisuje.
"""

import io
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime

# Foldery w instance/, których nie kopiujemy (cache do odtworzenia).
POMIJANE = {os.path.join("atlas", "granice")}

INSTRUKCJA = """Kopia zapasowa aplikacji Warsztat — {data}

Zawartość: folder instance/ — bazy wszystkich modułów (fiszki i
powtórki, historia i zapisane działki, cache i zestaw raportu atlasu,
koncepcje osiedli, akty prawne i historia pytań, projekty i punkty
terenowe), wgrane PDF-y (fiszki, przepisy), zdjęcia z terenu i pliki
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
