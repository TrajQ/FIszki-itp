"""Zasięg pieszy z wybranego punktu — izochrony szybkiego modelu (ETAP 85).

Klikasz miejsce na mapie („a gdyby tu stała szkoła?”) i widzisz, ilu
mieszkańców siatki dojdzie do niego w 5, 10 i 15 minut. Szybki model
(model.py): czas = odległość w linii prostej × krętość / prędkość, więc
izochrona to okrąg o promieniu  t × prędkość / krętość.  Liczymy komórki,
których ŚRODEK leży w okręgu — tak samo jak czasy w szybkim modelu.

Gdy na mapie jest czas dojścia do usługi, podajemy też, ilu z tych
mieszkańców ma dziś do niej dalej niż próg — tylu nowa placówka w tym
miejscu realnie „przybyłaby”. Obecne czasy mogą pochodzić z analizy
sieciowej, a zasięg z modelu — to przybliżenie do porównania miejsc.
"""

import math

import h3

from .model import KRETOSC_DOMYSLNA, PREDKOSC_DOMYSLNA_KMH, ZAKRES_KRETOSCI, ZAKRES_PREDKOSCI_KMH, BladModelu, _odleglosc_m

PROGI_MIN = (5, 10, 15)


def zasieg_punktu(
    komorki: list[str],
    ludnosc: list[float] | None,
    lat: float,
    lng: float,
    czasy: list[float | None] | None = None,
    predkosc_kmh: float = PREDKOSC_DOMYSLNA_KMH,
    kretosc: float = KRETOSC_DOMYSLNA,
) -> dict:
    if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
        raise BladModelu("Współrzędne punktu poza zakresem.")
    if not ZAKRES_PREDKOSCI_KMH[0] <= predkosc_kmh <= ZAKRES_PREDKOSCI_KMH[1]:
        raise BladModelu(f"Prędkość marszu od {ZAKRES_PREDKOSCI_KMH[0]} do {ZAKRES_PREDKOSCI_KMH[1]} km/h.")
    if not ZAKRES_KRETOSCI[0] <= kretosc <= ZAKRES_KRETOSCI[1]:
        raise BladModelu(f"Krętość od {ZAKRES_KRETOSCI[0]} do {ZAKRES_KRETOSCI[1]}.")

    metry_na_minute = predkosc_kmh * 1000 / 60
    najdalej_m = PROGI_MIN[-1] * metry_na_minute / kretosc
    wagi = ludnosc if ludnosc is not None else [1.0] * len(komorki)
    # minuty dojścia z punktu do środka każdej komórki w zasięgu największego progu
    minuty = {}
    for i, komorka in enumerate(komorki):
        c_lat, c_lng = h3.cell_to_latlng(komorka)
        odleglosc = _odleglosc_m(lat, lng, c_lat, c_lng)
        if odleglosc <= najdalej_m:
            minuty[i] = odleglosc * kretosc / metry_na_minute

    progi = []
    for prog in PROGI_MIN:
        w_zasiegu = [i for i, t in minuty.items() if t <= prog]
        wiersz = {
            "minuty": prog,
            "promien_m": round(prog * metry_na_minute / kretosc),
            "komorki": len(w_zasiegu),
            "ludnosc": round(sum(wagi[i] for i in w_zasiegu), 1),
        }
        if czasy is not None:
            nowi = [i for i in w_zasiegu if czasy[i] is None or czasy[i] > prog]
            wiersz["nowi"] = round(sum(wagi[i] for i in nowi), 1)
        progi.append(wiersz)
    return {
        "lat": lat,
        "lng": lng,
        "predkosc_kmh": predkosc_kmh,
        "kretosc": kretosc,
        "z_ludnoscia": ludnosc is not None,
        "razem": round(sum(wagi), 1),
        "w_siatce": bool(minuty),
        "progi": progi,
    }
