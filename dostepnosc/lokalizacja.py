"""Gdzie postawić nową placówkę? (ETAP 78)

Problem maksymalnego pokrycia (maximal covering location problem) w
wersji zachłannej:

1. komórki „poza zasięgiem” — czas dojścia do obecnych usług większy niż
   próg (albo brak danych); waga = liczba mieszkańców (bez ludności w
   pliku: każda komórka waży 1),
2. kandydaci — środki komórek siatki z pliku (placówka stoi w obszarze
   opracowania),
3. dla każdego kandydata: suma wag komórek poza zasięgiem, do których z
   niego dojdzie się w progu (szybki model: odległość w linii prostej ×
   krętość / prędkość — model.py),
4. wybieramy najlepszego, jego komórki uznajemy za obsłużone i szukamy
   następnego (do 5 placówek).

Zachłanny wybór nie gwarantuje optimum dla kilku placówek naraz, ale
pierwsza propozycja jest najlepsza z możliwych, a kolejne — dobre i
zrozumiałe krok po kroku. Obecne czasy mogą pochodzić z analizy sieciowej,
a zasięg nowej placówki — z szybkiego modelu; to przybliżenie do
porównania miejsc, nie projekt.
"""

import math

import h3

from .model import KRETOSC_DOMYSLNA, PREDKOSC_DOMYSLNA_KMH, _odleglosc_m

MAKS_PLACOWEK = 5
ZAKRES_PROGU_MIN = (1, 120)


class BladLokalizacji(ValueError):
    """Złe parametry wyszukiwania lokalizacji."""


def najlepsze_lokalizacje(
    komorki: list[str],
    czasy: list[float | None],
    ludnosc: list[float] | None,
    prog_min: float,
    ile: int = 1,
    predkosc_kmh: float = PREDKOSC_DOMYSLNA_KMH,
    kretosc: float = KRETOSC_DOMYSLNA,
) -> dict:
    if not ZAKRES_PROGU_MIN[0] <= prog_min <= ZAKRES_PROGU_MIN[1]:
        raise BladLokalizacji(f"Próg od {ZAKRES_PROGU_MIN[0]} do {ZAKRES_PROGU_MIN[1]} minut.")
    if not 1 <= ile <= MAKS_PLACOWEK:
        raise BladLokalizacji(f"Od 1 do {MAKS_PLACOWEK} placówek.")

    wagi = ludnosc if ludnosc is not None else [1.0] * len(komorki)
    razem = sum(wagi)
    srodki = {k: h3.cell_to_latlng(k) for k in komorki}
    poza = {k: w for k, c, w in zip(komorki, czasy, wagi) if (c is None or c > prog_min) and w > 0}
    przed = razem - sum(poza.values())

    # Kto (który kandydat) obsłuży daną komórkę poza zasięgiem: komórki w
    # promieniu progu, szukane w sąsiedztwie H3, potem sprawdzane odległością.
    promien_m = prog_min * (predkosc_kmh * 1000 / 60) / kretosc
    krawedz_m = h3.average_hexagon_edge_length(h3.get_resolution(komorki[0]), unit="m") if komorki else 1
    k = math.ceil(promien_m / (krawedz_m * 1.5)) + 1  # odstęp środków sąsiadów ≈ 1,73 krawędzi
    w_siatce = set(komorki)
    zasieg = {}  # komórka poza zasięgiem → kandydaci, którzy do niej dojdą
    for komorka in poza:
        lat, lng = srodki[komorka]
        zasieg[komorka] = [
            kandydat for kandydat in h3.grid_disk(komorka, k)
            if kandydat in w_siatce and _odleglosc_m(lat, lng, *srodki[kandydat]) <= promien_m
        ]

    propozycje = []
    obsluzone: set[str] = set()
    for nr in range(1, ile + 1):
        punkty: dict[str, float] = {}
        for komorka, kandydaci in zasieg.items():
            if komorka in obsluzone:
                continue
            for kandydat in kandydaci:
                punkty[kandydat] = punkty.get(kandydat, 0.0) + poza[komorka]
        if not punkty:
            break
        # remis: kandydat o niższym indeksie H3 (powtarzalny wynik)
        najlepszy = max(sorted(punkty), key=punkty.get)
        nowe = [c for c, kandydaci in zasieg.items() if c not in obsluzone and najlepszy in kandydaci]
        obsluzone.update(nowe)
        lat, lng = srodki[najlepszy]
        propozycje.append({
            "nr": nr,
            "komorka": najlepszy,
            "lat": lat,
            "lng": lng,
            "obejmie": round(punkty[najlepszy], 1),
            "obejmie_proc": round(100 * punkty[najlepszy] / razem, 1) if razem else None,
            "komorki": len(nowe),
        })

    po = przed + sum(p["obejmie"] for p in propozycje)
    return {
        "prog_min": prog_min,
        "z_ludnoscia": ludnosc is not None,
        "w_zasiegu_przed_proc": round(100 * przed / razem, 1) if razem else None,
        "w_zasiegu_po_proc": round(100 * po / razem, 1) if razem else None,
        "poza_zasiegiem": round(sum(poza.values()), 1),
        "propozycje": propozycje,
    }
