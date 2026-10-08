"""Diagnoza polskich znaków w PDF-ie (ETAP 253).

    .venv/bin/python narzedzia/sprawdz_pdf.py ~/Pobrane/ustawa.pdf

Pokazuje, jakie nietypowe znaki wyciąga z PDF-a pypdf (przed i po
czyszczeniu w przepisy/tekst.py) i przykłady z kontekstem — wynik
można wkleić autorowi Warsztatu albo asystentowi, żeby poprawić
czyszczenie dla konkretnego pliku. Niczego nie zapisuje.
"""

import collections
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pypdf import PdfReader  # noqa: E402

from przepisy.tekst import oczysc_tekst  # noqa: E402

POLSKIE = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
ZWYKLE = set("–—„”“’‘«»§·…•°×±²³©®€ ")
MAKS_STRON = 30


def dziwne(tekst: str) -> collections.Counter:
    return collections.Counter(z for z in tekst if ord(z) > 127 and z not in POLSKIE and z not in ZWYKLE)


def opis(z: str) -> str:
    return f"U+{ord(z):04X} {unicodedata.name(z, '(bez nazwy)')} „{z}”"


def main(sciezka: str):
    czytnik = PdfReader(sciezka)
    surowy = "\n".join(s.extract_text() or "" for s in czytnik.pages[:MAKS_STRON])
    czysty = oczysc_tekst(surowy)
    print(f"Plik: {sciezka} | stron: {len(czytnik.pages)} (sprawdzam {min(MAKS_STRON, len(czytnik.pages))})")
    print(f"Polskie litery po czyszczeniu: {sum(1 for z in czysty if z in POLSKIE)}")
    for etykieta, tekst in (("PRZED czyszczeniem", surowy), ("PO czyszczeniu", czysty)):
        licznik = dziwne(tekst)
        print(f"\n{etykieta}: nietypowych znaków {sum(licznik.values())}")
        for z, ile in licznik.most_common(15):
            i = tekst.find(z)
            kontekst = tekst[max(0, i - 25):i + 25].replace("\n", " ")
            print(f"  {ile:5} × {opis(z)}   …{kontekst}…")
    fonty = set()
    for strona in czytnik.pages[:MAKS_STRON]:
        for font in ((strona.get("/Resources") or {}).get("/Font") or {}).values():
            font = font.get_object()
            fonty.add((str(font.get("/BaseFont")), str(font.get("/Subtype")), "/ToUnicode" in font))
    print("\nFonty (nazwa, typ, ma mapę znaków /ToUnicode):")
    for f in sorted(fonty):
        print("  ", f)
    print("\nPierwsze 400 znaków po czyszczeniu:\n" + czysty[:400])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
