"""Liczby z formularzy i zapytań modułu mpzp."""

import math


def liczba_skonczona(tekst) -> float:
    """float z pola formularza, ale tylko skończony: „nan”, „inf”, „1e400”
    też są dla Pythona liczbami, a zepsułyby odpowiedź JSON."""
    wartosc = float(str(tekst).strip().replace(",", ".").replace(" ", ""))
    if not math.isfinite(wartosc):
        raise ValueError("liczba nieskończona")
    return wartosc
