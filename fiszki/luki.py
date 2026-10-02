"""Fiszki z luką — cloze (ETAP 139).

Użytkownik bierze zaznaczony fragment PDF-a i otacza słowa do zapamiętania
podwójnymi nawiasami: „Plan miejscowy jest [[aktem prawa miejscowego]].”
Każda luka daje osobną fiszkę: pytanie = tekst z tą luką zastąpioną „[…]”
(pozostałe luki odsłonięte), odpowiedź = ukryte słowa.

To zwykłe fiszki (pytanie + odpowiedź) — powtórki, telefon, quiz, druk
i eksport działają bez zmian. Bez modelu językowego: luki wybiera człowiek.
"""

import re

LUKA = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)
ZNAK_LUKI = "[…]"
MAKS_LUK = 10
MAKS_DLUGOSC = 2000


class BladLuk(ValueError):
    pass


def fiszki_z_luk(tekst: str) -> list[dict]:
    """Tekst z [[lukami]] → [{"pytanie", "odpowiedz"}], po jednej na lukę."""
    tekst = " ".join((tekst or "").split())
    if len(tekst) > MAKS_DLUGOSC:
        raise BladLuk(f"Tekst z lukami może mieć najwyżej {MAKS_DLUGOSC} znaków.")
    luki = list(LUKA.finditer(tekst))
    if not luki:
        raise BladLuk("Otocz słowa do zapamiętania podwójnymi nawiasami, np. [[akt prawa miejscowego]].")
    if len(luki) > MAKS_LUK:
        raise BladLuk(f"Najwyżej {MAKS_LUK} luk w jednym tekście.")
    reszta = LUKA.sub("", tekst)
    if "[[" in reszta or "]]" in reszta:
        raise BladLuk("Niedomknięty nawias [[ albo ]] — każda luka to [[słowa]].")
    if not reszta.strip(" .,;:—–-"):
        raise BladLuk("Poza lukami nie ma tekstu — pytanie byłoby puste.")
    wynik = []
    for i, luka in enumerate(luki):
        odpowiedz = luka.group(1).strip()
        if not odpowiedz:
            raise BladLuk("Pusta luka [[ ]] — wpisz w nią słowa do ukrycia.")
        if "[[" in odpowiedz:
            raise BladLuk("Luki nie mogą być zagnieżdżone.")
        pytanie = LUKA.sub(lambda m, i=i: ZNAK_LUKI if m.start() == luka.start() else m.group(1).strip(), tekst)
        wynik.append({"pytanie": pytanie, "odpowiedz": odpowiedz})
    return wynik
