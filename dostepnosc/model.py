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


def csv_wynikow(komorki: list[str], kolumny: dict[str, list], ludnosc: list[float] | None) -> str:
    """Plik wyników w formacie, który czyta wyniki.wczytaj_csv."""
    bufor = io.StringIO()
    zapis = csv.writer(bufor)
    nazwy = list(kolumny)
    zapis.writerow(["h3", *nazwy, *(["ludnosc"] if ludnosc is not None else [])])
    for i, komorka in enumerate(komorki):
        wiersz = [komorka]
        for nazwa in nazwy:
            wartosc = kolumny[nazwa][i]
            wiersz.append("" if wartosc is None else f"{wartosc:g}")
        if ludnosc is not None:
            wiersz.append(f"{ludnosc[i]:g}")
        zapis.writerow(wiersz)
    return bufor.getvalue()
