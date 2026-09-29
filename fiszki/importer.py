"""Import fiszek z pliku tekstowego (ETAP 54).

Obsługiwane formaty (rozpoznawane automatycznie):

- eksport Anki „Notes in Plain Text” — linie `#separator:tab`, `#html:true`
  i pola rozdzielone tabulatorem; HTML zamieniamy na zwykły tekst,
- Quizlet — „pojęcie<TAB>definicja” w każdej linii,
- CSV/TSV z nagłówkiem `pytanie`, `odpowiedz` (np. eksport z tej
  aplikacji — wtedy wracają też `strona` i `fragment_tekstu`, czyli
  kotwica w PDF-ie),
- dowolny CSV bez nagłówka: pierwsza kolumna pytanie, druga odpowiedź.

Fiszka bez kotwicy dostaje stronę 0 i pusty fragment — interfejs nie
pokazuje wtedy linku „w źródle”.
"""

import csv
import html
import io
import re

MAKS_FISZEK = 2000
MAKS_ROZMIAR_B = 1_000_000
MAKS_DLUGOSC_POLA = 5000
NAGLOWKI_PYTANIA = {"pytanie", "question", "front", "przod", "przód", "pojecie", "pojęcie", "term"}
NAGLOWKI_ODPOWIEDZI = {"odpowiedz", "odpowiedź", "answer", "back", "tyl", "tył", "definicja", "definition"}


class BladImportu(ValueError):
    """Pliku nie da się zaimportować."""


def _bez_html(tekst: str) -> str:
    """Pole Anki (HTML) → zwykły tekst z nowymi liniami."""
    tekst = re.sub(r"<br\s*/?>|</(div|p|li)>", "\n", tekst, flags=re.IGNORECASE)
    tekst = re.sub(r"<[^>]+>", "", tekst)
    tekst = html.unescape(tekst)
    return "\n".join(linia.strip() for linia in tekst.splitlines()).strip()


def _separator(linie: list[str]) -> str:
    probka = "\n".join(linie[:20])
    if "\t" in probka:
        return "\t"
    return ";" if probka.count(";") > probka.count(",") else ","


def wczytaj(tekst: str) -> tuple[list[dict], list[str]]:
    """Tekst pliku → (fiszki, opisy błędnych wierszy).

    Fiszka: {"pytanie", "odpowiedz", "strona", "fragment_tekstu"}.
    """
    tekst = tekst.lstrip("﻿")
    if not tekst.strip():
        raise BladImportu("Plik jest pusty.")

    linie = tekst.splitlines()
    separator, czy_html = None, False
    # nagłówki Anki: #separator:tab, #html:true, #notetype column:… — pomijamy
    while linie and linie[0].startswith("#"):
        klucz, _, wartosc = linie[0][1:].partition(":")
        if klucz.strip().lower() == "separator":
            separator = {"tab": "\t", "comma": ",", "semicolon": ";", "pipe": "|", "space": " "}.get(wartosc.strip().lower())
        elif klucz.strip().lower() == "html":
            czy_html = wartosc.strip().lower() == "true"
        linie = linie[1:]
    separator = separator or _separator(linie)

    wiersze = list(csv.reader(io.StringIO("\n".join(linie)), delimiter=separator))
    wiersze = [w for w in wiersze if any(pole.strip() for pole in w)]
    if not wiersze:
        raise BladImportu("W pliku nie ma żadnych fiszek.")

    # Nagłówek z nazwami kolumn (np. eksport CSV tej aplikacji)?
    naglowek = [p.strip().lower() for p in wiersze[0]]
    kol_pytanie = next((i for i, n in enumerate(naglowek) if n in NAGLOWKI_PYTANIA), None)
    kol_odpowiedz = next((i for i, n in enumerate(naglowek) if n in NAGLOWKI_ODPOWIEDZI), None)
    if kol_pytanie is not None and kol_odpowiedz is not None:
        kol_strona = naglowek.index("strona") if "strona" in naglowek else None
        kol_fragment = naglowek.index("fragment_tekstu") if "fragment_tekstu" in naglowek else None
        wiersze = wiersze[1:]
        pierwszy_nr = 2
    else:
        kol_pytanie, kol_odpowiedz, kol_strona, kol_fragment = 0, 1, None, None
        pierwszy_nr = 1

    fiszki, bledy = [], []
    for nr, wiersz in enumerate(wiersze, start=pierwszy_nr):
        def pole(i):
            if i is None or i >= len(wiersz):
                return ""
            wartosc = wiersz[i]
            return _bez_html(wartosc) if czy_html else wartosc.strip()

        pytanie, odpowiedz = pole(kol_pytanie), pole(kol_odpowiedz)
        if not pytanie or not odpowiedz:
            bledy.append(f"wiersz {nr}: brak pytania albo odpowiedzi")
            continue
        if len(pytanie) > MAKS_DLUGOSC_POLA or len(odpowiedz) > MAKS_DLUGOSC_POLA:
            bledy.append(f"wiersz {nr}: pole dłuższe niż {MAKS_DLUGOSC_POLA} znaków")
            continue
        strona = 0
        if kol_strona is not None:
            try:
                strona = max(0, int(pole(kol_strona)))
            except ValueError:
                strona = 0
        fragment = pole(kol_fragment) if strona else ""
        if not fragment:
            strona = 0  # kotwica wymaga i strony, i fragmentu
        fiszki.append({"pytanie": pytanie, "odpowiedz": odpowiedz, "strona": strona, "fragment_tekstu": fragment})
        if len(fiszki) > MAKS_FISZEK:
            raise BladImportu(f"Za dużo fiszek w pliku (limit {MAKS_FISZEK}).")
    return fiszki, bledy
