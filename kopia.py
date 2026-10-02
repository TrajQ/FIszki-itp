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
import shutil
import sqlite3
import tempfile
import time
import zipfile
from contextlib import closing
from datetime import datetime

# Foldery w instance/, których nie kopiujemy (cache do odtworzenia).
POMIJANE = {os.path.join("atlas", "granice"), "logi"}  # logi: dziennik błędów (ETAP 127), nie dane

INSTRUKCJA = """Kopia zapasowa aplikacji Warsztat — {data}

Zawartość: folder instance/ — bazy wszystkich modułów (fiszki i
powtórki, historia i zapisane działki, cache i zestaw raportu atlasu,
koncepcje osiedli, akty prawne i historia pytań, projekty i punkty
terenowe, wybrany wskaźnik cen), wgrane PDF-y (fiszki, przepisy), zdjęcia z terenu i pliki
wyników dostępności.

Przywracanie: w aplikacji — strona główna → „Przywróć z kopii”
(ETAP 129). Ręcznie:
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
    try:
        sprawdz_kopie(tymczasowa)  # ETAP 168: w folderze zostają tylko kopie, które dają się przywrócić
    except BladKopii:
        os.remove(tymczasowa)
        raise
    os.replace(tymczasowa, sciezka)
    os.utime(sciezka, (teraz, teraz))
    for stara in sorted(glob.glob(os.path.join(folder_kopii, WZOR_AUTO)), key=os.path.getmtime)[:-zostaw]:
        os.remove(stara)
    return sciezka


# ---------- przywracanie kopii w aplikacji (ETAP 129) ----------

MAKS_ROZPAKOWANE_B = 4_000_000_000  # zabezpieczenie przed „bombą zip”
MAKS_PLIKOW = 100_000
WZOR_PRZED = "warsztat_przed_przywroceniem_{:%Y%m%d_%H%M%S}.zip"


class BladKopii(ValueError):
    """Plik nie jest poprawną kopią Warsztatu albo jest uszkodzony."""


def _sprawdz_i_rozpakuj(zip_: zipfile.ZipFile, cel: str) -> int:
    """Rozpakowuje tylko instance/… do `cel`; BladKopii przy obcym albo
    niebezpiecznym pliku. Zwraca liczbę plików."""
    nazwy = zip_.namelist()
    if "PRZYWRACANIE.txt" not in nazwy:
        raise BladKopii("To nie jest kopia Warsztatu (brak pliku PRZYWRACANIE.txt).")
    pliki = [i for i in zip_.infolist() if not i.is_dir() and i.filename != "PRZYWRACANIE.txt"]
    if not pliki or len(pliki) > MAKS_PLIKOW or sum(i.file_size for i in pliki) > MAKS_ROZPAKOWANE_B:
        raise BladKopii("Kopia jest pusta albo podejrzanie duża.")
    for i in pliki:
        czesci = i.filename.replace("\\", "/").split("/")
        if czesci[0] != "instance" or len(czesci) < 2 or any(c in ("", ".", "..") for c in czesci[1:]) or i.filename.startswith("/"):
            raise BladKopii(f"Niedozwolona ścieżka w kopii: {i.filename[:80]}")
        if czesci[1] == "logi":
            continue  # dziennik błędów zostaje bieżący
        sciezka = os.path.join(cel, *czesci[1:])
        os.makedirs(os.path.dirname(sciezka), exist_ok=True)
        with zip_.open(i) as zrodlo, open(sciezka, "wb") as plik:
            shutil.copyfileobj(zrodlo, plik)
    for katalog, _, nazwy_plikow in os.walk(cel):
        for nazwa in nazwy_plikow:
            if nazwa.endswith(".db"):
                try:
                    # closing(): „with sqlite3.connect()” tylko zatwierdza transakcję, połączenia nie zamyka
                    with closing(sqlite3.connect(f"file:{os.path.join(katalog, nazwa)}?mode=ro", uri=True)) as db:
                        wynik = db.execute("PRAGMA integrity_check").fetchone()[0]
                except sqlite3.DatabaseError as e:
                    raise BladKopii(f"Baza {nazwa} w kopii jest uszkodzona ({e}).") from e
                if wynik != "ok":
                    raise BladKopii(f"Baza {nazwa} w kopii jest uszkodzona ({wynik}).")
    return len(pliki)


def sprawdz_kopie(zrodlo) -> int:
    """Sprawdzenie kopii bez przywracania (ETAP 168): sumy kontrolne plików
    w ZIP, ścieżki i `PRAGMA integrity_check` każdej bazy — to samo, co przed
    przywróceniem, w folderze tymczasowym. Zwraca liczbę plików; BladKopii,
    gdy kopia nie nadaje się do przywrócenia."""
    with tempfile.TemporaryDirectory(prefix=".sprawdzanie_") as tymczasowy:
        try:
            with zipfile.ZipFile(zrodlo) as zip_:
                zly = zip_.testzip()
                if zly is not None:
                    raise BladKopii(f"Plik {zly[:80]} w kopii jest uszkodzony (zła suma kontrolna).")
                return _sprawdz_i_rozpakuj(zip_, tymczasowy)
        except zipfile.BadZipFile as e:
            raise BladKopii("To nie jest plik ZIP albo jest uszkodzony.") from e


# ---------- kopia poza tym komputerem (ETAP 168) ----------
# Warsztat nie widzi pendrive'a ani chmury — data to deklaracja użytkownika
# („skopiowałem kopię”), a przypomnienie wraca po PRZYPOMNIENIE_DNI.

PLIK_POZA_DYSKIEM = "kopia_poza_dyskiem.txt"
PRZYPOMNIENIE_DNI = 30


def kopia_poza_dyskiem(folder_instance: str) -> datetime | None:
    try:
        with open(os.path.join(folder_instance, PLIK_POZA_DYSKIEM), encoding="utf-8") as plik:
            return datetime.fromisoformat(plik.read().strip())
    except (OSError, ValueError):
        return None


def zapisz_kopie_poza_dyskiem(folder_instance: str, teraz: datetime | None = None) -> None:
    os.makedirs(folder_instance, exist_ok=True)
    with open(os.path.join(folder_instance, PLIK_POZA_DYSKIEM), "w", encoding="utf-8") as plik:
        plik.write((teraz or datetime.now()).isoformat(timespec="seconds"))


def ten_sam_dysk(folder_instance: str, folder_kopii: str) -> bool:
    """Czy folder kopii leży na tym samym systemie plików co dane (awaria
    dysku zabiera wtedy jedno i drugie). Folderu kopii może jeszcze nie być —
    sprawdzamy najbliższy istniejący folder nad nim."""
    sciezka = os.path.abspath(folder_kopii)
    while not os.path.exists(sciezka) and os.path.dirname(sciezka) != sciezka:
        sciezka = os.path.dirname(sciezka)
    try:
        return os.stat(sciezka).st_dev == os.stat(folder_instance).st_dev
    except OSError:
        return False


def _wolna_nazwa(sciezka: str) -> str:
    """Ścieżka, która jeszcze nie istnieje (…_2, …_3 przy dwóch przywróceniach w tej samej sekundzie)."""
    rdzen, rozszerzenie = os.path.splitext(sciezka)
    nr = 1
    while os.path.exists(sciezka):
        nr += 1
        sciezka = f"{rdzen}_{nr}{rozszerzenie}"
    return sciezka


def przywroc_kopie(folder_instance: str, zrodlo, folder_kopii: str, teraz: datetime | None = None) -> dict:
    """Przywraca dane z kopii (ścieżka albo plik-obiekt ZIP).

    Kolejność chroni obecne dane: najpierw rozpakowanie i sprawdzenie kopii
    w folderze tymczasowym, potem kopia bezpieczeństwa obecnych danych,
    potem obecne pliki przenoszone (nie usuwane) do instance_stary_<data>/,
    a na ich miejsce pliki z kopii. Folder logi/ zostaje bez zmian."""
    teraz = teraz or datetime.now()
    rodzic = os.path.dirname(os.path.abspath(folder_instance))
    tymczasowy = tempfile.mkdtemp(prefix=".przywracanie_", dir=rodzic)
    try:
        try:
            with zipfile.ZipFile(zrodlo) as zip_:
                plikow = _sprawdz_i_rozpakuj(zip_, tymczasowy)
        except zipfile.BadZipFile as e:
            raise BladKopii("To nie jest plik ZIP albo jest uszkodzony.") from e
        os.makedirs(folder_kopii, exist_ok=True)
        przed = _wolna_nazwa(os.path.join(folder_kopii, WZOR_PRZED.format(teraz)))
        os.makedirs(folder_instance, exist_ok=True)
        if any(n != "logi" for n in os.listdir(folder_instance)):
            with open(przed, "wb") as plik:
                plik.write(utworz_kopie(folder_instance))
        else:
            przed = None
        stary = _wolna_nazwa(os.path.join(rodzic, f"instance_stary_{teraz:%Y%m%d_%H%M%S}"))
        os.makedirs(stary)
        for nazwa in os.listdir(folder_instance):
            if nazwa != "logi":
                shutil.move(os.path.join(folder_instance, nazwa), os.path.join(stary, nazwa))
        for nazwa in os.listdir(tymczasowy):
            shutil.move(os.path.join(tymczasowy, nazwa), os.path.join(folder_instance, nazwa))
        return {"plikow": plikow, "kopia_bezpieczenstwa": przed, "stary_folder": stary}
    finally:
        shutil.rmtree(tymczasowy, ignore_errors=True)


def kopie_do_przywrocenia(folder_kopii: str) -> list[dict]:
    """Kopie automatyczne i sprzed przywrócenia z folderu kopii, od najnowszej."""
    pliki = glob.glob(os.path.join(folder_kopii, "warsztat_*.zip"))
    return [{"nazwa": os.path.basename(p), "data": datetime.fromtimestamp(os.path.getmtime(p)), "mb": round(os.path.getsize(p) / 1e6, 1)}
            for p in sorted(pliki, key=os.path.getmtime, reverse=True)]
