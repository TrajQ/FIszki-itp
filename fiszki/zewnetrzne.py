"""Fiszki tworzone z innych modułów (ETAP 68: z cytatu w module przepisy).

Jedyne wejście do fiszek z zewnątrz. Zasada modułu zostaje: fiszka ma
kotwicę w źródle, więc razem z fiszką przychodzi PDF, z którego pochodzi
fragment. PDF kopiujemy do plików fiszek raz — kolejne fiszki z tego
samego pliku (ta sama suma SHA-256) trafiają do już dodanego PDF-a.
"""

import hashlib
import os
import shutil
import uuid
from datetime import datetime

from werkzeug.utils import secure_filename

from . import tematy
from .baza import folder_plikow, get_db

MAKS_DLUGOSC = 2000


class BladFiszki(ValueError):
    """Niepełne albo za długie dane fiszki."""


def _suma(sciezka: str) -> str:
    skrot = hashlib.sha256()
    with open(sciezka, "rb") as plik:
        for blok in iter(lambda: plik.read(1 << 20), b""):
            skrot.update(blok)
    return skrot.hexdigest()


def pdf_dla_pliku(sciezka: str, nazwa: str) -> int:
    """Identyfikator PDF-a w fiszkach dla pliku — istniejący albo nowo dodany."""
    db = get_db()
    suma = _suma(sciezka)
    wiersz = db.execute(
        "SELECT pdf_id FROM pdf_skroty JOIN pdfy ON pdfy.id = pdf_skroty.pdf_id WHERE sha256 = ?", (suma,)
    ).fetchone()
    if wiersz:
        return wiersz["pdf_id"]
    nazwa_na_dysku = f"{uuid.uuid4().hex}_{secure_filename(nazwa) or 'akt.pdf'}"
    shutil.copyfile(sciezka, os.path.join(folder_plikow(), nazwa_na_dysku))
    pdf_id = db.execute(
        "INSERT INTO pdfy (nazwa_oryginalna, nazwa_pliku, data_dodania) VALUES (?, ?, ?)",
        (nazwa, nazwa_na_dysku, datetime.now().isoformat()),
    ).lastrowid
    db.execute("INSERT INTO pdf_skroty (pdf_id, sha256) VALUES (?, ?)", (pdf_id, suma))
    db.commit()
    return pdf_id


def dodaj_fiszke(sciezka_pdf: str, nazwa_pdf: str, strona: int, fragment: str, pytanie: str, odpowiedz: str, lista_tematow) -> dict:
    """Dodaje fiszkę z kotwicą (strona + fragment) w podanym PDF-ie.

    Zwraca {"fiszka_id", "pdf_id"}. BladFiszki przy złych danych.
    """
    pola = {"fragment": fragment, "pytanie": pytanie, "odpowiedź": odpowiedz}
    for nazwa, tekst in pola.items():
        if not str(tekst or "").strip():
            raise BladFiszki(f"Pole „{nazwa}” nie może być puste.")
        if len(tekst) > MAKS_DLUGOSC:
            raise BladFiszki(f"Pole „{nazwa}”: najwyżej {MAKS_DLUGOSC} znaków.")
    if not isinstance(strona, int) or strona < 1:
        raise BladFiszki("Niepoprawny numer strony.")
    try:
        lista_tematow = tematy.normalizuj(lista_tematow)
    except tematy.BladTematow as e:
        raise BladFiszki(str(e)) from None

    pdf_id = pdf_dla_pliku(sciezka_pdf, nazwa_pdf)
    db = get_db()
    fiszka_id = db.execute(
        """INSERT INTO fiszki (pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, data_utworzenia)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (pdf_id, strona, fragment.strip(), pytanie.strip(), odpowiedz.strip(), datetime.now().isoformat()),
    ).lastrowid
    tematy.ustaw(db, fiszka_id, lista_tematow)
    db.commit()
    return {"fiszka_id": fiszka_id, "pdf_id": pdf_id}
