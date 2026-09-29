"""Generuje SYNTETYCZNE pliki przykładowe dla modułu dostępność.

To nie są prawdziwe wyniki — punkty docelowe są zmyślone, a czas dojścia
to odległość w linii prostej × 1,3 (współczynnik krętości sieci) przez
prędkość marszu 80 m/min. Ludność komórek też jest zmyślona (maleje od
środka). Powstają dwa pliki: stan obecny i scenariusz z jedną nową
szkołą — do pokazania porównania scenariuszy. Uruchomienie (z katalogu
projektu):

    .venv/bin/python dostepnosc/przyklad/generuj_przyklad.py
"""

import csv
import math
import os

import h3

SRODEK = (52.4064, 16.9252)  # okolice Starego Rynku w Poznaniu
ROZDZIELCZOSC = 9
PROMIEN_PIERSCIENI = 14
KRETOSC = 1.3
PREDKOSC_M_NA_MIN = 80

# Zmyślone punkty docelowe (lat, lon) — tylko do przykładu.
PUNKTY = {
    "czas_przystanek_min": [
        (52.4064, 16.9252), (52.4100, 16.9350), (52.4010, 16.9120), (52.3990, 16.9400),
        (52.4150, 16.9150), (52.3930, 16.9250), (52.4200, 16.9450), (52.4030, 16.8990),
    ],
    "czas_szkola_min": [(52.4120, 16.9300), (52.3960, 16.9180), (52.4230, 16.9020)],
    "czas_przychodnia_min": [(52.4040, 16.9330), (52.3880, 16.9050)],
}


def odleglosc_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    d = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(d))


# Scenariusz: jedna nowa szkoła w obszarze, gdzie dziś daleko do szkół.
NOWA_SZKOLA = (52.3960, 16.9420)


def ludnosc(srodek) -> int:
    # Zmyślony rozkład: gęsto w centrum, rzadziej na obrzeżach.
    return round(900 * math.exp(-odleglosc_m(srodek, SRODEK) / 1800))


def zapisz(nazwa_pliku, punkty_wg_kolumny, komorki):
    sciezka = os.path.join(os.path.dirname(__file__), nazwa_pliku)
    with open(sciezka, "w", newline="", encoding="utf-8") as plik:
        zapis = csv.writer(plik)
        zapis.writerow(["h3", *punkty_wg_kolumny, "ludnosc"])
        for komorka in komorki:
            srodek = h3.cell_to_latlng(komorka)
            czasy = [
                round(min(odleglosc_m(srodek, p) for p in punkty) * KRETOSC / PREDKOSC_M_NA_MIN, 1)
                for punkty in punkty_wg_kolumny.values()
            ]
            zapis.writerow([komorka, *czasy, ludnosc(srodek)])
    print(f"Zapisano {len(komorki)} komórek do {sciezka}")


def main():
    komorki = sorted(h3.grid_disk(h3.latlng_to_cell(*SRODEK, ROZDZIELCZOSC), PROMIEN_PIERSCIENI))
    zapisz("przyklad_poznan_syntetyczny.csv", PUNKTY, komorki)
    ze_szkola = {**PUNKTY, "czas_szkola_min": PUNKTY["czas_szkola_min"] + [NOWA_SZKOLA]}
    zapisz("przyklad_poznan_nowa_szkola_syntetyczny.csv", ze_szkola, komorki)


if __name__ == "__main__":
    main()
