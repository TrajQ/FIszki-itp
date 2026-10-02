"""Kontrast kolorów tekstu w obu motywach — WCAG AA, 4,5:1 (ETAP 131).

Kolory czytamy z tokenów w static/style.css, więc zmiana koloru, która
obniży kontrast poniżej progu, zatrzyma testy.
"""

import os
import re

import pytest

STYL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "style.css")
AA = 4.5
PARY = [  # (kolor tekstu, tło) — rzeczywiste połączenia w aplikacji
    ("tekst", "tlo"), ("tekst", "tlo-karty"), ("tekst", "tlo-pola"),
    ("tekst-drugi", "tlo"), ("tekst-drugi", "tlo-karty"), ("tekst-drugi", "tlo-wyciszone"), ("tekst-drugi", "tlo-pola"),
    ("akcent", "tlo"), ("akcent", "tlo-karty"), ("#ffffff", "akcent-wypelnienie"), ("#ffffff", "akcent-wypelnienie-hover"),
    ("blad", "tlo-karty"), ("ostrzezenie", "tlo-karty"), ("sukces", "tlo-karty"),
]


def _tokeny():
    with open(STYL, encoding="utf-8") as plik:
        css = plik.read()
    poczatek_ciemnego = css.index("@media (prefers-color-scheme: dark)")

    def odczytaj(blok):
        return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", blok))

    jasny = odczytaj(css[css.index(":root {"):poczatek_ciemnego])
    ciemny = {**jasny, **odczytaj(css[poczatek_ciemnego:css.index("/* ---------- Podstawy")])}
    return {"jasny": jasny, "ciemny": ciemny}


def _luminancja(kolor):
    def kanal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(kolor[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)


def kontrast(a, b):
    jasniejszy, ciemniejszy = sorted((_luminancja(a), _luminancja(b)), reverse=True)
    return (jasniejszy + 0.05) / (ciemniejszy + 0.05)


def test_wzor_kontrastu():
    assert kontrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert kontrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


@pytest.mark.parametrize("motyw", ["jasny", "ciemny"])
def test_kontrast_tekstu(motyw):
    t = _tokeny()[motyw]
    za_malo = [(a, b, round(kontrast(t.get(a, a), t.get(b, b)), 2)) for a, b in PARY if kontrast(t.get(a, a), t.get(b, b)) < AA]
    assert za_malo == []
