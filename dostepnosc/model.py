"""Szybki model dostępności liczony w aplikacji (ETAP 47).

Reszta modułu czyta wyniki policzone gdzie indziej (np. QGIS, r5py).
Ten model daje wynik od razu, z punktów usług wstawionych na mapie:

    czas [min] = odległość w linii prostej × krętość / prędkość marszu

- krętość (domyślnie 1,3) — o ile droga po ulicach jest dłuższa niż
  w linii prostej; typowe wartości dla miast to 1,2–1,4,
- prędkość (domyślnie 4,8 km/h = 80 m/min) — spokojny marsz dorosłego.

To PRZYBLIŻENIE: nie zna barier (rzeki, tory, ogrodzenia), przejść ani
rzeczywistej sieci ulic. Tych samych założeń używają pliki przykładowe
(dostepnosc/przyklad/generuj_przyklad.py). Do pracy, w której liczy się
dokładność, lepsza jest analiza sieciowa — ten model służy do szybkiego
porównania wariantów („co jeśli postawimy tu szkołę?”).

Czas liczymy dla środka każdej komórki H3 do najbliższego punktu.
Przy okazji każda komórka trafia do obszaru obsługi najbliższej placówki
— stąd liczba mieszkańców przypadająca na placówkę.
"""

import csv
import io
import math
import re
import statistics

import h3

PREDKOSC_DOMYSLNA_KMH = 4.8
KRETOSC_DOMYSLNA = 1.3
ZAKRES_PREDKOSCI_KMH = (2.0, 7.0)
ZAKRES_KRETOSCI = (1.0, 2.0)
MAKS_PUNKTOW = 100
MAKS_KOMOREK_NOWEJ_SIATKI = 20_000
ROZDZIELCZOSC_NOWEJ_SIATKI = 9  # ok. 10,5 ha na komórkę — skala kwartału

_R_ZIEMI_M = 6_371_008.8


class BladModelu(ValueError):
    """Złe dane wejściowe szybkiego modelu."""


def nazwa_kolumny(usluga: str) -> str:
    """„Szkoła podstawowa” → „czas_szkola_podstawowa_min” (moduł rozpozna minuty)."""
    tekst = usluga.strip().lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))
    tekst = re.sub(r"[^a-z0-9]+", "_", tekst).strip("_")[:40]
    if not tekst:
        raise BladModelu("Podaj nazwę usługi, np. „szkoła” albo „przystanek”.")
    return f"czas_{tekst}_min"


def siatka_obszaru(poludnie: float, zachod: float, polnoc: float, wschod: float) -> list[str]:
    """Komórki H3 (rozdzielczość 9) pokrywające prostokąt widocznej mapy."""
    if not (-90 <= poludnie < polnoc <= 90 and -180 <= zachod < wschod <= 180):
        raise BladModelu("Niepoprawny obszar mapy.")
    # Najpierw szacunek z pola prostokąta — h3shape_to_cells dla ogromnego
    # obszaru liczyłby się długo tylko po to, żeby przekroczyć limit.
    km_na_stopien = 111.32
    pole_km2 = (polnoc - poludnie) * km_na_stopien * (wschod - zachod) * km_na_stopien * math.cos(
        math.radians((poludnie + polnoc) / 2)
    )
    szacunek = pole_km2 / h3.average_hexagon_area(ROZDZIELCZOSC_NOWEJ_SIATKI, unit="km^2")
    if szacunek > 1.2 * MAKS_KOMOREK_NOWEJ_SIATKI:
        raise BladModelu(
            f"Obszar ma ok. {round(szacunek, -3):.0f} komórek (limit {MAKS_KOMOREK_NOWEJ_SIATKI}) — przybliż mapę do dzielnicy albo miasta."
        )
    wielokat = h3.LatLngPoly([(poludnie, zachod), (poludnie, wschod), (polnoc, wschod), (polnoc, zachod)])
    komorki = sorted(h3.h3shape_to_cells(wielokat, ROZDZIELCZOSC_NOWEJ_SIATKI))
    if not komorki:
        raise BladModelu("Obszar jest za mały — przybliż mniej.")
    if len(komorki) > MAKS_KOMOREK_NOWEJ_SIATKI:
        raise BladModelu(
            f"Obszar ma {len(komorki)} komórek (limit {MAKS_KOMOREK_NOWEJ_SIATKI}) — przybliż mapę do dzielnicy albo miasta."
        )
    return komorki


def _odleglosc_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Odległość po kuli (haversine) — w skali miasta błąd rzędu 0,3%."""
    fi1, fi2 = math.radians(lat1), math.radians(lat2)
    dfi = fi2 - fi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dfi / 2) ** 2 + math.cos(fi1) * math.cos(fi2) * math.sin(dlambda / 2) ** 2
    return 2 * _R_ZIEMI_M * math.asin(math.sqrt(a))


def sprawdz_parametry(punkty, predkosc_kmh: float, kretosc: float) -> list[tuple[float, float]]:
    if not punkty:
        raise BladModelu("Wstaw na mapie co najmniej jeden punkt usługi.")
    if len(punkty) > MAKS_PUNKTOW:
        raise BladModelu(f"Najwyżej {MAKS_PUNKTOW} punktów.")
    wynik = []
    for punkt in punkty:
        try:
            lat, lon = float(punkt[0]), float(punkt[1])
        except (TypeError, ValueError, IndexError):
            raise BladModelu("Punkty to pary [szerokość, długość].") from None
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise BladModelu("Współrzędne punktu poza zakresem.")
        wynik.append((lat, lon))
    if not ZAKRES_PREDKOSCI_KMH[0] <= predkosc_kmh <= ZAKRES_PREDKOSCI_KMH[1]:
        raise BladModelu(f"Prędkość marszu od {ZAKRES_PREDKOSCI_KMH[0]} do {ZAKRES_PREDKOSCI_KMH[1]} km/h.")
    if not ZAKRES_KRETOSCI[0] <= kretosc <= ZAKRES_KRETOSCI[1]:
        raise BladModelu(f"Krętość od {ZAKRES_KRETOSCI[0]} do {ZAKRES_KRETOSCI[1]}.")
    return wynik


def czasy_dojscia(
    komorki: list[str], punkty: list[tuple[float, float]], predkosc_kmh: float, kretosc: float
) -> tuple[list[float], list[int]]:
    """(czas w minutach, numer najbliższego punktu) dla środka każdej komórki."""
    metry_na_minute = predkosc_kmh * 1000 / 60
    czasy, najblizsze = [], []
    for komorka in komorki:
        lat, lon = h3.cell_to_latlng(komorka)
        odleglosci = [_odleglosc_m(lat, lon, p_lat, p_lon) for p_lat, p_lon in punkty]
        nr = min(range(len(punkty)), key=odleglosci.__getitem__)
        czasy.append(round(odleglosci[nr] * kretosc / metry_na_minute, 1))
        najblizsze.append(nr)
    return czasy, najblizsze


def polacz_z_istniejacymi(stare: list, nowe: list[float]) -> tuple[list[float], list[bool]]:
    """Nowe punkty dołożone do istniejących usług: w każdej komórce czas do
    najbliższej z nich (starej albo nowej). Zwraca też, gdzie nowy punkt
    skrócił czas — tylko te komórki należą do obszarów obsługi nowych punktów."""
    polaczone, lepiej = [], []
    for stary, nowy in zip(stare, nowe):
        if stary is None or nowy < stary:
            polaczone.append(nowy)
            lepiej.append(True)
        else:
            polaczone.append(stary)
            lepiej.append(False)
    return polaczone, lepiej


def obszary_obslugi(
    punkty: list[tuple[float, float]],
    czasy: list[float],
    najblizsze: list[int],
    ludnosc: list[float] | None,
    maska: list[bool] | None = None,
) -> list[dict]:
    """Dla każdego punktu: ile komórek (i mieszkańców) ma go najbliżej.

    `maska` — tylko te komórki (np. te, którym nowy punkt skrócił dojście)."""
    wynik = []
    for nr, (lat, lon) in enumerate(punkty):
        indeksy = [i for i, n in enumerate(najblizsze) if n == nr and (maska is None or maska[i])]
        obszar = {
            "nr": nr + 1,
            "lat": lat,
            "lon": lon,
            "komorki": len(indeksy),
            "sredni_czas_min": round(statistics.fmean(czasy[i] for i in indeksy), 1) if indeksy else None,
            "maks_czas_min": max((czasy[i] for i in indeksy), default=None),
        }
        if ludnosc is not None:
            obszar["ludnosc"] = round(sum(ludnosc[i] for i in indeksy))
        wynik.append(obszar)
    return wynik


def csv_wynikow(komorki: list[str], kolumny: dict[str, list], ludnosc: list[float] | None, grupy: dict[str, list] | None = None) -> str:
    """Plik wyników w formacie, który czyta wyniki.wczytaj_csv (grupy
    mieszkańców z ETAPu 204 przepisywane bez zmian)."""
    bufor = io.StringIO()
    zapis = csv.writer(bufor)
    grupy = grupy or {}
    nazwy = list(kolumny)
    zapis.writerow(["h3", *nazwy, *(["ludnosc"] if ludnosc is not None else []), *grupy])
    for i, komorka in enumerate(komorki):
        wiersz = [komorka]
        for nazwa in nazwy:
            wartosc = kolumny[nazwa][i]
            wiersz.append("" if wartosc is None else f"{wartosc:g}")
        if ludnosc is not None:
            wiersz.append(f"{ludnosc[i]:g}")
        wiersz += [f"{osoby[i]:g}" for osoby in grupy.values()]
        zapis.writerow(wiersz)
    return bufor.getvalue()


# ---------- Punkty usług z pliku CSV (ETAP 55) ----------

NAGLOWKI_SZEROKOSCI = {"lat", "latitude", "szerokosc", "szerokość", "y", "szer"}
NAGLOWKI_DLUGOSCI = {"lon", "lng", "long", "longitude", "dlugosc", "długość", "x", "dl"}
NAGLOWKI_NAZWY = {"nazwa", "name", "opis", "placowka", "placówka"}
MAKS_DLUGOSC_NAZWY = 60


def _liczba_wsp(tekst: str) -> float:
    liczba = float(tekst.strip().replace(" ", "").replace(",", "."))
    if not math.isfinite(liczba):
        raise ValueError("liczba nieskończona")
    return liczba


def punkty_z_csv(tekst: str) -> tuple[list[dict], list[str]]:
    """CSV z punktami w WGS84 → ([{"lat", "lon", "nazwa"}], błędy wierszy).

    Kolumny rozpoznajemy po nagłówku (lat/lon, szerokosc/dlugosc, y/x,
    nazwa). Bez nagłówka: dwie pierwsze kolumny to współrzędne, a która
    jest szerokością, poznajemy po zakresie (Polska: szerokość 49–55°,
    długość 14–24,2° — zakresy się nie nakładają).
    """
    tekst = tekst.lstrip("﻿")
    if not tekst.strip():
        raise BladModelu("Plik jest pusty.")
    pierwsza = tekst.splitlines()[0]
    # średnik, gdy jest (wtedy przecinek bywa dziesiętny: „52,40;16,92”)
    separator = "\t" if "\t" in pierwsza else ";" if ";" in pierwsza else ","
    wiersze = [w for w in csv.reader(io.StringIO(tekst), delimiter=separator) if any(p.strip() for p in w)]

    naglowek = [p.strip().lower() for p in wiersze[0]]
    kol_lat = next((i for i, n in enumerate(naglowek) if n in NAGLOWKI_SZEROKOSCI), None)
    kol_lon = next((i for i, n in enumerate(naglowek) if n in NAGLOWKI_DLUGOSCI), None)
    kol_nazwa = next((i for i, n in enumerate(naglowek) if n in NAGLOWKI_NAZWY), None)
    if kol_lat is not None and kol_lon is not None:
        dane, pierwszy_nr = wiersze[1:], 2
    else:
        dane, pierwszy_nr, kol_lat, kol_lon = wiersze, 1, 0, 1
        kol_nazwa = 2  # opcjonalna trzecia kolumna

    punkty, bledy = [], []
    for nr, wiersz in enumerate(dane, start=pierwszy_nr):
        try:
            a, b = _liczba_wsp(wiersz[kol_lat]), _liczba_wsp(wiersz[kol_lon])
        except (IndexError, ValueError):
            bledy.append(f"wiersz {nr}: brak liczbowych współrzędnych")
            continue
        # bez nagłówka kolejność bywa odwrotna (x, y) — rozpoznajemy po zakresie
        if not (48 <= a <= 56) and 48 <= b <= 56:
            a, b = b, a
        if not (-90 <= a <= 90 and -180 <= b <= 180):
            bledy.append(f"wiersz {nr}: współrzędne poza zakresem — potrzebne stopnie WGS84 (EPSG:4326)")
            continue
        nazwa = wiersz[kol_nazwa].strip()[:MAKS_DLUGOSC_NAZWY] if kol_nazwa is not None and kol_nazwa < len(wiersz) else ""
        punkty.append({"lat": a, "lon": b, "nazwa": nazwa})
        if len(punkty) > MAKS_PUNKTOW:
            raise BladModelu(f"Za dużo punktów w pliku (limit {MAKS_PUNKTOW}).")
    if not punkty:
        raise BladModelu("W pliku nie znaleziono punktów. Potrzebne kolumny lat i lon w stopniach (EPSG:4326).")
    return punkty, bledy
