"""Wczytywanie gotowych wyników analizy dostępności na siatce H3.

Moduł nie liczy dostępności sam — czyta wyniki policzone gdzie indziej
(np. w QGIS, Pythonie, r5py) i zapisane jako CSV:

    h3,czas_przystanek_min,czas_szkola_min
    891e24aa52fffff,4.5,11
    ...

- kolumna `h3` — indeks komórki H3 (wymagana),
- pozostałe kolumny liczbowe — wskaźniki; kolumna, której nazwa kończy się
  na `_min` albo zaczyna od `czas`, jest traktowana jako czas dojścia w
  minutach (stałe klasy 5/10/15/20/30 min, udziały „miasta 15-minutowego”),
- separator przecinek albo średnik, przecinek dziesiętny też działa,
- puste pole = brak wartości dla tej komórki.

Wszystkie liczby (statystyki, udziały, powierzchnie) liczy ten moduł,
na podstawie wczytanych wartości.
"""

import csv
import io
import statistics

import h3

KOLUMNA_H3 = "h3"
MAKS_KOMOREK = 100_000
PROGI_MINUT = [5, 10, 15, 20, 30]
LICZBA_KLAS_KWANTYLOWYCH = 5


class BladWynikow(Exception):
    """Plik wyników ma zły format."""


def wczytaj_csv(tekst: str) -> dict:
    """CSV → {"komorki": [h3...], "kolumny": {nazwa: [float|None, ...]}}."""
    tekst = tekst.lstrip("﻿")
    if not tekst.strip():
        raise BladWynikow("Plik jest pusty.")

    pierwsza_linia = tekst.splitlines()[0]
    separator = ";" if pierwsza_linia.count(";") > pierwsza_linia.count(",") else ","
    czytnik = csv.reader(io.StringIO(tekst), delimiter=separator)

    naglowek = [n.strip() for n in next(czytnik)]
    naglowek_male = [n.lower() for n in naglowek]
    if KOLUMNA_H3 not in naglowek_male:
        raise BladWynikow(f"Brak kolumny „{KOLUMNA_H3}” z indeksami komórek H3.")
    indeks_h3 = naglowek_male.index(KOLUMNA_H3)
    nazwy_kolumn = [n for i, n in enumerate(naglowek) if i != indeks_h3 and n]
    powtorzone = sorted({n for n in nazwy_kolumn if nazwy_kolumn.count(n) > 1})
    if powtorzone:
        # Wartości dwóch kolumn o tej samej nazwie trafiałyby do jednej listy
        # i rozjechały się z komórkami — lepiej odrzucić plik.
        raise BladWynikow(f"Powtórzone nazwy kolumn: {', '.join(powtorzone)}.")
    if not nazwy_kolumn:
        raise BladWynikow("Poza kolumną h3 plik nie ma żadnych kolumn z wartościami.")

    komorki = []
    kolumny = {n: [] for n in nazwy_kolumn}
    for nr_wiersza, wiersz in enumerate(czytnik, start=2):
        if not any(pole.strip() for pole in wiersz):
            continue
        komorka = wiersz[indeks_h3].strip().lower() if indeks_h3 < len(wiersz) else ""
        if not h3.is_valid_cell(komorka):
            raise BladWynikow(f"Wiersz {nr_wiersza}: „{komorka}” nie jest poprawnym indeksem H3.")
        komorki.append(komorka)
        if len(komorki) > MAKS_KOMOREK:
            raise BladWynikow(f"Za dużo komórek (limit {MAKS_KOMOREK}).")

        for i, nazwa in enumerate(naglowek):
            if i == indeks_h3 or nazwa not in kolumny:
                continue
            pole = wiersz[i].strip() if i < len(wiersz) else ""
            kolumny[nazwa].append(_liczba(pole, nr_wiersza, nazwa))

    if not komorki:
        raise BladWynikow("Plik nie zawiera żadnych komórek.")

    # Zostawiamy tylko kolumny, które mają przynajmniej jedną wartość.
    kolumny = {n: w for n, w in kolumny.items() if any(v is not None for v in w)}
    if not kolumny:
        raise BladWynikow("Żadna kolumna nie zawiera wartości liczbowych.")

    rozdzielczosci = {h3.get_resolution(k) for k in komorki}
    if len(rozdzielczosci) > 1:
        raise BladWynikow(f"Komórki mają różne rozdzielczości H3: {sorted(rozdzielczosci)}.")

    return {"komorki": komorki, "kolumny": kolumny, "rozdzielczosc": rozdzielczosci.pop()}


def _liczba(pole: str, nr_wiersza: int, kolumna: str) -> float | None:
    if pole == "":
        return None
    try:
        return float(pole.replace(",", "."))
    except ValueError:
        raise BladWynikow(f"Wiersz {nr_wiersza}, kolumna „{kolumna}”: „{pole}” nie jest liczbą.")


def czy_minuty(nazwa_kolumny: str) -> bool:
    nazwa = nazwa_kolumny.lower()
    return nazwa.endswith("_min") or nazwa.startswith("czas")


def analiza_kolumny(wyniki: dict, kolumna: str) -> dict:
    """GeoJSON komórek z wartością + klasy + statystyki dla jednej kolumny."""
    if kolumna not in wyniki["kolumny"]:
        raise KeyError(kolumna)

    pary = [
        (k, w) for k, w in zip(wyniki["komorki"], wyniki["kolumny"][kolumna]) if w is not None
    ]
    wartosci = [w for _, w in pary]
    minuty = czy_minuty(kolumna)
    progi = PROGI_MINUT if minuty else _progi_kwantylowe(wartosci)

    cechy = [
        {
            "type": "Feature",
            "properties": {"h3": k, "wartosc": w, "klasa": _klasa(w, progi)},
            "geometry": _geometria_komorki(k),
        }
        for k, w in pary
    ]

    rozdzielczosc = wyniki["rozdzielczosc"]
    pole_komorki_km2 = h3.average_hexagon_area(rozdzielczosc, unit="km^2")
    stat = {
        "liczba_komorek": len(pary),
        "komorki_bez_wartosci": len(wyniki["komorki"]) - len(pary),
        "min": min(wartosci),
        "max": max(wartosci),
        "mediana": statistics.median(wartosci),
        "rozdzielczosc": rozdzielczosc,
        "pole_komorki_km2": pole_komorki_km2,
    }
    if minuty:
        stat["udzialy"] = [
            {
                "prog": prog,
                "procent": 100 * sum(1 for w in wartosci if w <= prog) / len(wartosci),
                "powierzchnia_km2": pole_komorki_km2 * sum(1 for w in wartosci if w <= prog),
            }
            for prog in (5, 10, 15)
        ]

    return {
        "kolumna": kolumna,
        "minuty": minuty,
        "progi": progi,
        "statystyki": stat,
        "geojson": {"type": "FeatureCollection", "features": cechy},
    }


NAZWA_LACZNEGO = "czas_laczny_min"


def kolumny_minut(wyniki: dict) -> list[str]:
    return [k for k in wyniki["kolumny"] if czy_minuty(k)]


def analiza_laczna(wyniki: dict) -> dict:
    """„Miasto 15-minutowe”: czas dojścia do WSZYSTKICH usług naraz.

    Dla każdej komórki bierzemy maksimum z kolumn czasu (dopiero wtedy
    dojdziemy do każdej z usług). Komórka z brakiem w którejkolwiek
    kolumnie nie ma wartości łącznej. Dodatkowo liczymy, która usługa
    najczęściej jest tą najdalszą — „najsłabsze ogniwo”.
    """
    kolumny = kolumny_minut(wyniki)
    if len(kolumny) < 2:
        raise BladWynikow("Wskaźnik łączny wymaga co najmniej dwóch kolumn czasu (*_min).")

    laczne = []
    najdalsze = {k: 0 for k in kolumny}
    for i in range(len(wyniki["komorki"])):
        czasy = [(wyniki["kolumny"][k][i], k) for k in kolumny]
        if any(c is None for c, _ in czasy):
            laczne.append(None)
            continue
        czas, kolumna = max(czasy)
        laczne.append(czas)
        najdalsze[kolumna] += 1

    if all(w is None for w in laczne):
        raise BladWynikow("Żadna komórka nie ma wartości we wszystkich kolumnach czasu.")

    kopia = {**wyniki, "kolumny": {NAZWA_LACZNEGO: laczne}}
    analiza = analiza_kolumny(kopia, NAZWA_LACZNEGO)
    policzone = sum(najdalsze.values())
    analiza["skladowe"] = kolumny
    analiza["najslabsze_ogniwo"] = sorted(
        (
            {"kolumna": k, "komorki": n, "procent": 100 * n / policzone if policzone else 0}
            for k, n in najdalsze.items()
        ),
        key=lambda x: -x["komorki"],
    )
    return analiza


def _progi_kwantylowe(wartosci: list[float]) -> list[float]:
    if len(set(wartosci)) < 2:
        return []
    progi = []
    for prog in statistics.quantiles(wartosci, n=LICZBA_KLAS_KWANTYLOWYCH, method="inclusive"):
        if prog not in progi and min(wartosci) <= prog < max(wartosci):
            progi.append(prog)
    return progi


def _klasa(wartosc: float, progi: list[float]) -> int:
    """Numer klasy 0..len(progi): klasa i obejmuje (progi[i-1], progi[i]]."""
    for i, prog in enumerate(progi):
        if wartosc <= prog:
            return i
    return len(progi)


def _geometria_komorki(komorka: str) -> dict:
    # h3 zwraca (lat, lng); GeoJSON wymaga (lng, lat) i domkniętego pierścienia.
    obwod = [[lng, lat] for lat, lng in h3.cell_to_boundary(komorka)]
    obwod.append(obwod[0])
    return {"type": "Polygon", "coordinates": [obwod]}
