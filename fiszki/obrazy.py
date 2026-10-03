"""Wycinki rysunków z PDF przy pytaniach fiszek (ETAP 154).

Mapy, schematy i przekroje z wykładów nie dają się zapisać tekstem. Wycinek
robi przeglądarka (prostokąt zaznaczony na wyrenderowanej stronie PDF) i
przysyła go jako PNG w data URL; serwer sprawdza, że to naprawdę PNG
rozsądnej wielkości, zapisuje plik pod losową nazwą i wiąże go z fiszką.
Pliki leżą w instance/fiszki/obrazy/, więc trafiają do kopii zapasowej.
"""

import base64
import binascii
import os
import re
import uuid

from flask import current_app

PREFIKS = "data:image/png;base64,"
SYGNATURA_PNG = b"\x89PNG\r\n\x1a\n"
MAKS_BAJTOW = 2_000_000
WZOR_NAZWY = re.compile(r"^[0-9a-f]{32}\.png$")


class BladObrazu(ValueError):
    pass


def folder() -> str:
    sciezka = os.path.join(current_app.instance_path, "fiszki", "obrazy")
    os.makedirs(sciezka, exist_ok=True)
    return sciezka


def odczytaj(data_url) -> bytes:
    """data URL z przeglądarki → bajty PNG albo BladObrazu."""
    if not isinstance(data_url, str) or not data_url.startswith(PREFIKS):
        raise BladObrazu("Wycinek musi być obrazem PNG.")
    if len(data_url) > MAKS_BAJTOW * 4 // 3 + len(PREFIKS) + 4:
        raise BladObrazu("Wycinek jest za duży (najwyżej 2 MB) — zaznacz mniejszy fragment.")
    try:
        dane = base64.b64decode(data_url[len(PREFIKS):], validate=True)
    except (binascii.Error, ValueError):
        raise BladObrazu("Uszkodzony obraz.") from None
    if not dane.startswith(SYGNATURA_PNG):
        raise BladObrazu("Wycinek musi być obrazem PNG.")
    return dane


def zapisz(db, fiszka_id: int, dane: bytes) -> str:
    nazwa = f"{uuid.uuid4().hex}.png"
    with open(os.path.join(folder(), nazwa), "wb") as plik:
        plik.write(dane)
    db.execute("INSERT INTO obrazy_fiszek (fiszka_id, plik) VALUES (?, ?)", (fiszka_id, nazwa))
    return nazwa


# ---------- zasłonięte fragmenty obrazu (ETAP 185) ----------
# Mapa albo schemat z zasłoniętym jednym miejscem: „co tu jest?”. Jak luki
# (D-147) — każdy prostokąt to osobna, zwykła fiszka z tym samym plikiem
# obrazu i własną zasłoną.

MAKS_ZASLON = 12
MIN_ROZMIAR = 0.01  # 1% boku obrazu


def sprawdz_zaslony(prostokaty) -> list[tuple[float, float, float, float]]:
    """[[x, y, w, h], …] we współrzędnych względnych → lista krotek albo BladObrazu."""
    if not isinstance(prostokaty, list) or not 1 <= len(prostokaty) <= MAKS_ZASLON:
        raise BladObrazu(f"Zaznacz od 1 do {MAKS_ZASLON} fragmentów do zasłonięcia.")
    wynik = []
    for p in prostokaty:
        if not isinstance(p, list) or len(p) != 4 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p):
            raise BladObrazu("Zły format zaznaczenia.")
        x, y, w, h = (float(v) for v in p)
        if w < MIN_ROZMIAR or h < MIN_ROZMIAR or x < 0 or y < 0 or x + w > 1.0001 or y + h > 1.0001:
            raise BladObrazu("Zaznaczenie wychodzi poza obraz albo jest za małe.")
        wynik.append((x, y, w, h))
    return wynik


def zaslony_fiszek(db) -> dict[int, list[float]]:
    """{fiszka_id: [x, y, w, h]}"""
    return {w[0]: [w[1], w[2], w[3], w[4]] for w in db.execute("SELECT fiszka_id, x, y, w, h FROM zaslony_fiszek")}


def obrazy_fiszek(db) -> dict[int, str]:
    """{fiszka_id: nazwa pliku}"""
    return {w[0]: w[1] for w in db.execute("SELECT fiszka_id, plik FROM obrazy_fiszek")}


def usun_osierocone(db) -> int:
    """Usuwa pliki, do których nie odwołuje się już żadna fiszka (po usunięciu
    fiszki albo całego PDF-a — wiersze znikają kaskadowo)."""
    w_bazie = {w[0] for w in db.execute("SELECT plik FROM obrazy_fiszek")}
    usuniete = 0
    for nazwa in os.listdir(folder()):
        if WZOR_NAZWY.match(nazwa) and nazwa not in w_bazie:
            os.remove(os.path.join(folder(), nazwa))
            usuniete += 1
    return usuniete


def jako_data_url(nazwa: str) -> str | None:
    """Plik → data URL (do samodzielnego pliku na telefon); None, gdy pliku brak."""
    sciezka = os.path.join(folder(), nazwa)
    if not WZOR_NAZWY.match(nazwa) or not os.path.exists(sciezka):
        return None
    with open(sciezka, "rb") as plik:
        return PREFIKS + base64.b64encode(plik.read()).decode("ascii")
