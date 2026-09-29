"""Kotwica w źródle: dopasowanie fragmentu do tekstu strony PDF-a.

Tekst z pdf.js i tekst zaznaczony myszką różnią się białymi znakami
(nowe linie, podwójne spacje, dzielenie na elementy). Dlatego fragment
porównujemy z tekstem strony z pominięciem wszystkich białych znaków —
tak samo robi podświetlanie w przeglądarce (fiszki.js: podswietlFragment).
"""

import re

_BIALE = re.compile(r"\s+")


def bez_bialych_znakow(tekst: str) -> str:
    return _BIALE.sub("", tekst)


def fragment_na_stronie(fragment: str, tekst_strony: str) -> bool:
    szukany = bez_bialych_znakow(fragment)
    return bool(szukany) and szukany in bez_bialych_znakow(tekst_strony)


def zakotwiczone(propozycje: list[dict], tekst_strony: str) -> tuple[list[dict], int]:
    """Zostawia propozycje, których fragment naprawdę jest na stronie.

    Zwraca (dobre, liczba_odrzuconych). Fiszka bez kotwicy w źródle łamie
    główną zasadę modułu, więc nie pokazujemy jej wcale.
    """
    dobre = [p for p in propozycje if fragment_na_stronie(p["fragment"], tekst_strony)]
    return dobre, len(propozycje) - len(dobre)
