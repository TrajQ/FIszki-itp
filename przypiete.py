"""Przypięte rzeczy na stronie głównej (ETAP 211).

„Wróć do pracy” pokazuje to, czego używało się ostatnio — i znika z
listy, gdy pracuje się nad czymś innym. Przypięte zostają: koncepcja,
nad którą siedzi się cały semestr, akt prawny na egzamin, projekt
terenowy. Lista jest w instance/przypiete.json (trafia do kopii
zapasowej razem z resztą instance/).

Przypinamy adres strony w aplikacji (zaczyna się od „/”) z tytułem i
nazwą modułu — tak jak są w „Wróć do pracy”. Adresy z innych serwerów
odrzucamy.
"""

import json
import os
from datetime import datetime

NAZWA_PLIKU = "przypiete.json"
MAKS_PRZYPIETYCH = 12
MAKS_DLUGOSC_URL = 300
MAKS_DLUGOSC_TYTULU = 120


class BladPrzypiecia(ValueError):
    """Niepoprawna rzecz do przypięcia albo pełna lista."""


def _sciezka(instance_path: str) -> str:
    return os.path.join(instance_path, NAZWA_PLIKU)


def wczytaj(instance_path: str) -> list[dict]:
    """Przypięte w kolejności przypięcia; uszkodzony albo brakujący plik → pusta lista."""
    try:
        with open(_sciezka(instance_path), encoding="utf-8") as plik:
            dane = json.load(plik)
    except (OSError, ValueError):
        return []
    return [p for p in dane if isinstance(p, dict) and isinstance(p.get("url"), str)] if isinstance(dane, list) else []


def _zapisz(instance_path: str, lista: list[dict]) -> None:
    os.makedirs(instance_path, exist_ok=True)
    tymczasowy = _sciezka(instance_path) + ".tmp"
    with open(tymczasowy, "w", encoding="utf-8") as plik:
        json.dump(lista, plik, ensure_ascii=False, indent=1)
    os.replace(tymczasowy, _sciezka(instance_path))  # zapis „w całości albo wcale”


def sprawdz_url(url) -> str:
    url = str(url or "").strip()
    if not url.startswith("/") or url.startswith("//") or "\\" in url or len(url) > MAKS_DLUGOSC_URL or any(z in url for z in "\r\n\t"):
        raise BladPrzypiecia("Przypiąć można tylko stronę tej aplikacji.")
    return url


def przypnij(instance_path: str, dane: dict) -> list[dict]:
    url = sprawdz_url((dane or {}).get("url"))
    tytul = " ".join(str((dane or {}).get("tytul") or "").split())[:MAKS_DLUGOSC_TYTULU]
    if not tytul:
        raise BladPrzypiecia("Brak tytułu.")
    lista = wczytaj(instance_path)
    if any(p["url"] == url for p in lista):
        return lista
    if len(lista) >= MAKS_PRZYPIETYCH:
        raise BladPrzypiecia(f"Najwyżej {MAKS_PRZYPIETYCH} przypiętych — odepnij coś.")
    lista.append({"url": url, "tytul": tytul,
                  "modul": " ".join(str(dane.get("modul") or "").split())[:20],
                  "opis": " ".join(str(dane.get("opis") or "").split())[:120],
                  "data": datetime.now().isoformat(timespec="seconds")})
    _zapisz(instance_path, lista)
    return lista


def odepnij(instance_path: str, url) -> list[dict]:
    lista = [p for p in wczytaj(instance_path) if p["url"] != str(url or "")]
    _zapisz(instance_path, lista)
    return lista
