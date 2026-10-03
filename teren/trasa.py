"""Trasa obchodu punktów w terenie (ETAP 198).

Kolejność odwiedzania punktów tak, żeby droga była krótka: najpierw
„najbliższy nieodwiedzony” (od punktu startowego), potem poprawki 2-opt —
odwracanie fragmentów trasy, dopóki skraca to drogę. To heurystyka, nie
optimum (problem komiwojażera), ale dla kilkudziesięciu punktów daje
trasę zwykle o kilka–kilkanaście procent krótszą od samego „najbliższego”.

Odległości w linii prostej (wzór haversine) — ulice i przeszkody nie są
znane, więc długość jest dolnym oszacowaniem drogi pieszej. Trasa jest
otwarta: kończy się na ostatnim punkcie, bez powrotu na start.
"""

import math
from xml.sax.saxutils import escape

PROMIEN_ZIEMI_M = 6_371_008.8
MAKS_PUNKTOW_TRASY = 200
PREDKOSC_KMH = 4.5  # spacer z zatrzymaniami przy punktach liczony osobno
MAKS_PRZEJSC_2OPT = 50


class BladTrasy(ValueError):
    """Za mało albo za dużo punktów do trasy."""


def odleglosc_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Odległość po kuli między (lat, lng) w metrach."""
    fi1, fi2 = math.radians(a[0]), math.radians(b[0])
    dfi, dla = fi2 - fi1, math.radians(b[1] - a[1])
    h = math.sin(dfi / 2) ** 2 + math.cos(fi1) * math.cos(fi2) * math.sin(dla / 2) ** 2
    return 2 * PROMIEN_ZIEMI_M * math.asin(min(1.0, math.sqrt(h)))


def _dlugosc(kolejnosc: list[int], d: list[list[float]]) -> float:
    return sum(d[a][b] for a, b in zip(kolejnosc, kolejnosc[1:]))


def _najblizszy(start: int, d: list[list[float]]) -> list[int]:
    n = len(d)
    kolejnosc, wolne = [start], set(range(n)) - {start}
    while wolne:
        ostatni = kolejnosc[-1]
        nastepny = min(wolne, key=lambda j: (d[ostatni][j], j))
        kolejnosc.append(nastepny)
        wolne.remove(nastepny)
    return kolejnosc


def _dwa_opt(kolejnosc: list[int], d: list[list[float]], staly_start: bool) -> list[int]:
    """Poprawki 2-opt dla trasy otwartej (koniec wolny; start stały albo wolny)."""
    t = list(kolejnosc)
    n = len(t)
    for _ in range(MAKS_PRZEJSC_2OPT):
        poprawa = False
        for i in range(1 if staly_start else 0, n - 1):
            for j in range(i + 1, n):
                przed = (d[t[i - 1]][t[i]] if i > 0 else 0) + (d[t[j]][t[j + 1]] if j + 1 < n else 0)
                po = (d[t[i - 1]][t[j]] if i > 0 else 0) + (d[t[i]][t[j + 1]] if j + 1 < n else 0)
                if po < przed - 1e-6:
                    t[i:j + 1] = reversed(t[i:j + 1])
                    poprawa = True
        if not poprawa:
            break
    return t


def trasa(punkty: list[dict], start_id: int | None = None) -> dict:
    """punkty: [{"id", "lat", "lng"}] → kolejność, odcinki i długość.

    Bez punktu startowego trasa zaczyna się od punktu najdalszego od
    środka grupy (naturalny koniec), a 2-opt może zmienić oba końce."""
    if len(punkty) < 2:
        raise BladTrasy("Do trasy potrzeba co najmniej dwóch punktów z położeniem.")
    if len(punkty) > MAKS_PUNKTOW_TRASY:
        raise BladTrasy(f"Najwyżej {MAKS_PUNKTOW_TRASY} punktów w jednej trasie — zawęź filtr w legendzie.")
    wsp = [(p["lat"], p["lng"]) for p in punkty]
    d = [[odleglosc_m(a, b) for b in wsp] for a in wsp]
    ids = [p["id"] for p in punkty]
    if start_id is not None:
        if start_id not in ids:
            raise BladTrasy("Punktu startowego nie ma wśród punktów trasy.")
        start = ids.index(start_id)
    else:
        srodek = (sum(a for a, _ in wsp) / len(wsp), sum(b for _, b in wsp) / len(wsp))
        start = max(range(len(wsp)), key=lambda i: (odleglosc_m(srodek, wsp[i]), -i))
    poczatkowa = _najblizszy(start, d)
    kolejnosc = _dwa_opt(poczatkowa, d, staly_start=start_id is not None)
    odcinki = [round(d[a][b], 1) for a, b in zip(kolejnosc, kolejnosc[1:])]
    dlugosc = _dlugosc(kolejnosc, d)
    return {
        "kolejnosc": [ids[i] for i in kolejnosc],
        "odcinki_m": odcinki,
        "dlugosc_m": round(dlugosc, 1),
        "dlugosc_najblizszy_m": round(_dlugosc(poczatkowa, d), 1),
        "czas_min": round(dlugosc / 1000 / PREDKOSC_KMH * 60),
    }


def gpx(punkty: list[dict], kolejnosc: list[int], nazwa: str) -> str:
    """Trasa jako GPX 1.1: punkty (wpt) z numerem kolejności i trasa (rte)
    — do aplikacji nawigacyjnej na telefonie (np. OsmAnd, Locus)."""
    po_id = {p["id"]: p for p in punkty}
    wiersze = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<gpx version="1.1" creator="Warsztat" xmlns="http://www.topografix.com/GPX/1/1">',
               f"  <metadata><name>{escape(nazwa)}</name></metadata>"]
    for nr, pid in enumerate(kolejnosc, start=1):
        p = po_id[pid]
        wiersze.append(f'  <wpt lat="{p["lat"]:.7f}" lon="{p["lng"]:.7f}"><name>{nr}</name><desc>punkt {pid}</desc></wpt>')
    wiersze.append(f"  <rte><name>{escape(nazwa)}</name>")
    for nr, pid in enumerate(kolejnosc, start=1):
        p = po_id[pid]
        wiersze.append(f'    <rtept lat="{p["lat"]:.7f}" lon="{p["lng"]:.7f}"><name>{nr}</name></rtept>')
    wiersze += ["  </rte>", "</gpx>", ""]
    return "\n".join(wiersze)
