"""Aktualizacja Warsztatu z ZIP-a jednym poleceniem (ETAP 71).

Uruchamiane przez ./aktualizuj.sh (tylko biblioteka standardowa Pythona —
działa nawet wtedy, gdy .venv jest uszkodzone). Kolejność:

1. znajdź ZIP (podany albo najnowszy warsztat_etap*.zip w Pobranych),
2. sprawdź, że to ZIP Warsztatu (katalog warsztat/, app.py w środku,
   żadnych ścieżek wychodzących poza katalog),
3. sprawdź, że aplikacja nie działa (inaczej podmiana plików w trakcie),
4. kopia zapasowa: kod + instance/ + .env → ~/warsztat_kopie/…zip,
5. podmień pliki programu; NIGDY nie ruszaj instance/, .env, .venv/,
6. usuń pliki, które były w poprzedniej wersji, a w nowej ich nie ma
   (lista plików wersji w .pliki_wersji — przy pierwszej aktualizacji
   nic nie usuwamy),
7. doinstaluj zależności (.venv/bin/pip), zapisz sumę requirements.txt
   tak jak uruchom.sh, żeby nie instalował drugi raz.
"""

import glob
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime

PREFIKS = "warsztat/"
CHRONIONE = {"instance", ".env", ".venv"}  # pierwszy człon ścieżki
POMIJANE_W_KOPII = {".venv", "__pycache__", "releases", ".pytest_cache", ".git"}
LISTA_WERSJI = ".pliki_wersji"


class BladAktualizacji(Exception):
    """Czytelny komunikat dla użytkownika — skrypt kończy się bez zmian."""


def znajdz_zip(argument: str | None, katalogi: list[str]) -> str:
    """ZIP podany w argumencie albo najnowszy warsztat_etap*.zip w katalogach."""
    if argument:
        if not os.path.isfile(argument):
            raise BladAktualizacji(f"Nie ma pliku {argument}.")
        return argument
    kandydaci = [p for k in katalogi for p in glob.glob(os.path.join(k, "warsztat_etap*.zip"))]
    if not kandydaci:
        raise BladAktualizacji("Nie znalazłem warsztat_etap*.zip w " + ", ".join(katalogi) + ". Podaj ścieżkę: ./aktualizuj.sh ~/Pobrane/plik.zip")
    return max(kandydaci, key=os.path.getmtime)


def pliki_w_zipie(sciezka_zip: str) -> list[str]:
    """Ścieżki plików (względem katalogu projektu) — po sprawdzeniu ZIP-a."""
    try:
        with zipfile.ZipFile(sciezka_zip) as z:
            nazwy = z.namelist()
    except zipfile.BadZipFile:
        raise BladAktualizacji(f"{sciezka_zip} nie jest poprawnym plikiem ZIP (niepełne pobieranie?).") from None
    pliki = []
    for nazwa in nazwy:
        if not nazwa.startswith(PREFIKS):
            raise BladAktualizacji("To nie jest ZIP Warsztatu (brak katalogu warsztat/).")
        wzgledna = nazwa[len(PREFIKS):]
        if not wzgledna or wzgledna.endswith("/"):
            continue
        czesci = wzgledna.split("/")
        if wzgledna.startswith("/") or ".." in czesci:
            raise BladAktualizacji(f"Podejrzana ścieżka w ZIP-ie: {nazwa}")
        if czesci[0] in CHRONIONE:
            continue  # ZIP z git archive ich nie ma; gdyby były — nie nadpisujemy danych
        pliki.append(wzgledna)
    if "app.py" not in pliki:
        raise BladAktualizacji("To nie jest ZIP Warsztatu (brak app.py).")
    return pliki


def aplikacja_dziala(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        return True
    except OSError:
        return False


def port_z_env(katalog: str) -> int:
    try:
        with open(os.path.join(katalog, ".env"), encoding="utf-8") as f:
            for wiersz in f:
                if wiersz.startswith("PORT="):
                    return int(wiersz.split("=", 1)[1].strip())
    except (OSError, ValueError):
        pass
    return 5000


def kopia_zapasowa(katalog: str, folder_kopii: str) -> str:
    """ZIP z kodem, instance/ i .env (bez .venv i plików tymczasowych)."""
    os.makedirs(folder_kopii, exist_ok=True)
    sciezka = os.path.join(folder_kopii, f"przed_aktualizacja_{datetime.now():%Y%m%d_%H%M%S}.zip")
    with zipfile.ZipFile(sciezka, "w", zipfile.ZIP_DEFLATED) as z:
        for korzen, podkatalogi, pliki in os.walk(katalog):
            podkatalogi[:] = [d for d in podkatalogi if d not in POMIJANE_W_KOPII]
            for plik in pliki:
                pelna = os.path.join(korzen, plik)
                z.write(pelna, os.path.join("warsztat", os.path.relpath(pelna, katalog)))
    return sciezka


def podmien_pliki(sciezka_zip: str, katalog: str, pliki: list[str]) -> list[str]:
    """Kopiuje nowe pliki, usuwa te z poprzedniej wersji, których już nie ma.
    Zwraca listę usuniętych plików."""
    with tempfile.TemporaryDirectory() as tymczasowy:
        with zipfile.ZipFile(sciezka_zip) as z:
            for wzgledna in pliki:
                z.extract(PREFIKS + wzgledna, tymczasowy)
        for wzgledna in pliki:
            cel = os.path.join(katalog, wzgledna)
            os.makedirs(os.path.dirname(cel) or katalog, exist_ok=True)
            shutil.copy2(os.path.join(tymczasowy, PREFIKS + wzgledna), cel)

    usuniete = []
    lista = os.path.join(katalog, LISTA_WERSJI)
    if os.path.isfile(lista):
        with open(lista, encoding="utf-8") as f:
            stare = {w.strip() for w in f if w.strip()}
        for wzgledna in sorted(stare - set(pliki)):
            czesci = wzgledna.split("/")
            if czesci[0] in CHRONIONE or ".." in czesci:
                continue
            cel = os.path.join(katalog, wzgledna)
            if os.path.isfile(cel):
                os.remove(cel)
                usuniete.append(wzgledna)
    with open(lista, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(pliki)) + "\n")
    return usuniete


def etap(katalog: str) -> str:
    try:
        with open(os.path.join(katalog, "CLAUDE.md"), encoding="utf-8") as f:
            for wiersz in f:
                if wiersz.startswith("ETAP:"):
                    return wiersz[5:].strip()
    except OSError:
        pass
    return "?"


def zaleznosci(katalog: str):
    pip = os.path.join(katalog, ".venv", "bin", "pip")
    if not os.path.exists(pip):
        print("Brak .venv — utwórz je raz: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")
        return
    wymagania = os.path.join(katalog, "requirements.txt")
    print("Instaluję zależności…")
    subprocess.run([pip, "install", "-q", "--disable-pip-version-check", "-r", wymagania], check=True)
    with open(wymagania, "rb") as f:
        suma = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(katalog, ".venv", ".requirements.sha256"), "w") as f:
        f.write(suma + "\n")  # ta sama suma, której szuka uruchom.sh


def main(argumenty: list[str], katalog: str | None = None, dom: str | None = None) -> int:
    katalog = katalog or os.path.dirname(os.path.abspath(__file__))
    dom = dom or os.path.expanduser("~")
    try:
        sciezka_zip = znajdz_zip(argumenty[0] if argumenty else None, [os.path.join(dom, "Pobrane"), os.path.join(dom, "Downloads")])
        print(f"ZIP: {sciezka_zip}")
        pliki = pliki_w_zipie(sciezka_zip)
        if aplikacja_dziala(port_z_env(katalog)):
            raise BladAktualizacji("Warsztat jest uruchomiony — zamknij jego okno terminala i uruchom aktualizację jeszcze raz.")
        print(f"Obecna wersja: {etap(katalog)}")
        kopia = kopia_zapasowa(katalog, os.path.join(dom, "warsztat_kopie"))
        print(f"Kopia zapasowa: {kopia}")
        usuniete = podmien_pliki(sciezka_zip, katalog, pliki)
        for sciezka in ("uruchom.sh", "zainstaluj_ikone.sh", "aktualizuj.sh"):
            if os.path.exists(os.path.join(katalog, sciezka)):
                os.chmod(os.path.join(katalog, sciezka), 0o755)
        print(f"Podmienione pliki: {len(pliki)}" + (f", usunięte stare: {len(usuniete)}" if usuniete else ""))
        zaleznosci(katalog)
    except BladAktualizacji as e:
        print(f"Nie zaktualizowano: {e}")
        return 1
    except subprocess.CalledProcessError:
        print("Pliki podmienione, ale instalacja zależności się nie udała — sprawdź internet i uruchom ./aktualizuj.sh jeszcze raz.")
        return 1
    print(f"Gotowe. Nowa wersja: {etap(katalog)}. Dane (instance/) i klucze (.env) bez zmian.")
    print("Uruchom Warsztat ikoną; w przeglądarce odśwież stronę przez Ctrl+Shift+R.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
