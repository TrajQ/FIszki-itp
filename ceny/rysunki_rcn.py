"""Rysunki SVG z transakcji RCN: mapy schematyczne i wykresy w latach (ETAP 246).

Wydzielone z ceny/rcn.py (ETAPy 105, 110, 113, 165, 221): rcn.py czyta
pliki i liczy statystyki, tu są tylko rysunki. W SVG są wyłącznie liczby
i kolory z kodu (D-048) — bez tekstu z pliku RCN.
"""

import math
import statistics

import shapely
from shapely.geometry import shape

from . import rcn
from .rcn import KOLORY_OBSZAROW, MIN_W_ROKU


def wykres_plikow_svg(zestawienie: dict) -> str:
    """Wykres median w latach — linia na plik (bez linii „cały plik”)."""
    return wykres_lat_svg({"obszary": zestawienie["pliki"], "calosc": {}, "lata": zestawienie["lata"]})


def mapa_svg(lokale: list[dict], obszary: list[dict], progi: list[float], kolory: list[str],
             szerokosc: int = 1000, wysokosc: int = 620) -> str:
    """Schematyczna mapa do raportu: punkty transakcji w klasach ceny i
    obrysy obszarów z numerami, podziałka i strzałka północy. Tylko liczby i
    kolory z kodu (nazwy obszarów są w legendzie raportu, nie w SVG)."""
    # te same punkty co na mapie strony: najwyżej MAKS_PUNKTOW_MAPY najnowszych (ETAP 117 —
    # wcześniej rysowało wszystkie, przy 100 tys. transakcji raport miał 9 MB)
    najnowsze = sorted((l for l in lokale if l["lat"] is not None), key=lambda l: l["data"], reverse=True)[:rcn.MAKS_PUNKTOW_MAPY]
    punkty = [(l["lng"], l["lat"], l["cena_m2"]) for l in najnowsze]
    ksztalty = [shape(o["geometria"]) for o in obszary]
    xs = [p[0] for p in punkty] + [b for k in ksztalty for b in (k.bounds[0], k.bounds[2])]
    ys = [p[1] for p in punkty] + [b for k in ksztalty for b in (k.bounds[1], k.bounds[3])]
    otwarcie = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>'
    if not xs:
        return otwarcie + f'<text x="{szerokosc / 2}" y="{wysokosc / 2}" text-anchor="middle" fill="#6e6e73">brak transakcji z położeniem</text></svg>'
    kx = math.cos(math.radians((min(ys) + max(ys)) / 2))  # metry na stopień długości / szerokości
    margines = 30
    skala = min((szerokosc - 2 * margines) / (((max(xs) - min(xs)) * kx) or 1e-9), (wysokosc - 2 * margines - 20) / ((max(ys) - min(ys)) or 1e-9))

    def px(lng, lat):
        return margines + (lng - min(xs)) * kx * skala, margines + (max(ys) - lat) * skala

    czesci = [otwarcie]
    for lng, lat, cena in sorted(punkty, key=lambda p: p[2]):
        i = 0
        while i < len(progi) and cena > progi[i]:
            i += 1
        x, y = px(lng, lat)
        czesci.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{kolory[i]}" stroke="#3a2a1a" stroke-width="0.3"/>')
    for nr, (k, o) in enumerate(zip(ksztalty, obszary), start=1):
        kolor = KOLORY_OBSZAROW[(nr - 1) % len(KOLORY_OBSZAROW)]
        for w in getattr(k, "geoms", [k]):
            d = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in (px(*p) for p in w.exterior.coords)) + " Z"
            czesci.append(f'<path d="{d}" fill="{kolor}" fill-opacity="0.06" stroke="{kolor}" stroke-width="2.5"/>')
        x, y = px(*k.representative_point().coords[0])
        czesci.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="#ffffff" stroke="{kolor}" stroke-width="2"/><text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" font-weight="700" fill="{kolor}">{nr}</text>')
    czesci += _podzialka_i_polnoc(skala, szerokosc, wysokosc, margines)
    czesci.append("</svg>")
    return "".join(czesci)


def _podzialka_i_polnoc(skala: float, szerokosc: int, wysokosc: int, margines: int) -> list[str]:
    """Podziałka (okrągła długość do ok. 1/4 szerokości) i strzałka północy;
    skala w pikselach na stopień szerokości."""
    czesci = []
    m_na_px = 111_320 / skala
    dlugosc_m = max((k for k in (100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 50000) if k / m_na_px <= szerokosc / 4), default=100)
    dl = dlugosc_m / m_na_px
    y0 = wysokosc - 14
    czesci.append(
        f'<g stroke="#1d1d1f" stroke-width="2"><line x1="{margines}" y1="{y0}" x2="{margines + dl:.1f}" y2="{y0}"/>'
        f'<line x1="{margines}" y1="{y0 - 5}" x2="{margines}" y2="{y0 + 1}"/><line x1="{margines + dl:.1f}" y1="{y0 - 5}" x2="{margines + dl:.1f}" y2="{y0 + 1}"/></g>'
        f'<text x="{margines + dl + 6:.1f}" y="{y0 + 4}" fill="#1d1d1f">{dlugosc_m if dlugosc_m < 1000 else dlugosc_m // 1000} {"m" if dlugosc_m < 1000 else "km"}</text>'
    )
    x = szerokosc - margines
    czesci.append(f'<path d="M{x},{margines - 12} L{x + 6},{margines + 4} L{x},{margines} L{x - 6},{margines + 4} Z" fill="#1d1d1f"/><text x="{x}" y="{margines + 18}" text-anchor="middle" fill="#1d1d1f">N</text>')
    return czesci


# ---------- mapa schematyczna zestawienia plików (ETAP 221) ----------

RDZEN_PLIKU = 0.95  # udział transakcji najbliższych środka pliku, z których rysujemy zasięg
MAKS_PUNKTOW_PLIKU_NA_MAPIE = 1500


def _rdzen(punkty: list[tuple[float, float]]) -> tuple[tuple[float, float], list[tuple[float, float]]]:
    """Środek pliku (mediana długości i szerokości — odporna na pojedyncze
    błędne położenia) i RDZEN_PLIKU punktów najbliższych temu środkowi."""
    srodek = (statistics.median(p[0] for p in punkty), statistics.median(p[1] for p in punkty))
    kx = math.cos(math.radians(srodek[1]))
    po_odleglosci = sorted(punkty, key=lambda p: math.hypot((p[0] - srodek[0]) * kx, p[1] - srodek[1]))
    return srodek, po_odleglosci[:max(1, math.ceil(len(punkty) * RDZEN_PLIKU))]


def mapa_plikow_svg(pliki: list[dict], szerokosc: int = 1000, wysokosc: int = 560) -> str:
    """Schematyczna mapa zestawienia: dla każdego pliku [{"kolor", "lokale"}]
    zasięg transakcji (otoczka wypukła rdzenia — bez 5% najdalszych od środka,
    zwykle błędnie położonych), punkty (najwyżej MAKS_PUNKTOW_PLIKU_NA_MAPIE
    najnowszych z rdzenia) i numer pliku w środku. Tylko liczby i kolory —
    nazwy plików są w tabeli raportu (D-048)."""
    otwarcie = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>'
    warstwy = []
    for nr, p in enumerate(pliki, start=1):
        z_polozeniem = sorted((l for l in p["lokale"] if l["lat"] is not None), key=lambda l: l["data"], reverse=True)
        if not z_polozeniem:
            continue
        srodek, rdzen = _rdzen([(l["lng"], l["lat"]) for l in z_polozeniem])
        w_rdzeniu = set(rdzen)
        punkty = [(l["lng"], l["lat"]) for l in z_polozeniem if (l["lng"], l["lat"]) in w_rdzeniu][:MAKS_PUNKTOW_PLIKU_NA_MAPIE]
        warstwy.append((nr, p["kolor"], srodek, rdzen, punkty))
    if not warstwy:
        return otwarcie + f'<text x="{szerokosc / 2}" y="{wysokosc / 2}" text-anchor="middle" fill="#6e6e73">brak transakcji z położeniem</text></svg>'
    xs = [x for w in warstwy for x, _ in w[3]]
    ys = [y for w in warstwy for _, y in w[3]]
    kx = math.cos(math.radians((min(ys) + max(ys)) / 2))
    margines = 30
    skala = min((szerokosc - 2 * margines) / (((max(xs) - min(xs)) * kx) or 1e-9), (wysokosc - 2 * margines - 20) / ((max(ys) - min(ys)) or 1e-9))
    skala = min(skala, 111_320 / 5)  # jeden punkt w pliku — nie powiększaj ponad 5 m na piksel
    # schemat na środku rysunku (wolne miejsce po równo z obu stron)
    dx = (szerokosc - 2 * margines - (max(xs) - min(xs)) * kx * skala) / 2
    dy = (wysokosc - 2 * margines - 20 - (max(ys) - min(ys)) * skala) / 2

    def px(lng, lat):
        return margines + dx + (lng - min(xs)) * kx * skala, margines + dy + (max(ys) - lat) * skala

    czesci = [otwarcie]
    for nr, kolor, srodek, rdzen, punkty in warstwy:
        otoczka = shapely.MultiPoint(rdzen).convex_hull
        if otoczka.geom_type == "Polygon":
            d = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in (px(*q) for q in otoczka.exterior.coords)) + " Z"
            czesci.append(f'<path d="{d}" fill="{kolor}" fill-opacity="0.08" stroke="{kolor}" stroke-width="2" stroke-dasharray="6 4"/>')
    for nr, kolor, srodek, rdzen, punkty in warstwy:
        for lng, lat in punkty:
            x, y = px(lng, lat)
            czesci.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{kolor}" fill-opacity="0.55"/>')
    for nr, kolor, srodek, rdzen, punkty in warstwy:
        x, y = px(*srodek)
        czesci.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="#ffffff" stroke="{kolor}" stroke-width="2.5"/><text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" font-weight="700" font-size="14" fill="{kolor}">{nr}</text>')
    czesci += _podzialka_i_polnoc(skala, szerokosc, wysokosc, margines)
    czesci.append("</svg>")
    return "".join(czesci)



def _ladna_os(lo: float, hi: float, podzialek: int = 5) -> tuple[float, float, float]:
    """Zakres osi zaokrąglony do „ładnego” kroku 1/2/2,5/5 × 10^n."""
    rozpietosc = (hi - lo) or abs(hi) or 1
    potega = 10 ** math.floor(math.log10(rozpietosc / podzialek))
    krok = next(k * potega for k in (1, 2, 2.5, 5, 10) if rozpietosc / (k * potega) <= podzialek)
    return math.floor(lo / krok) * krok, math.ceil(hi / krok) * krok, krok


def wykres_lat_svg(por: dict, szerokosc: int = 900, wysokosc: int = 300) -> str:
    """Wykres liniowy median ceny za m² w latach: obszary w ich kolorach,
    cały plik linią przerywaną. Rok z mniej niż MIN_W_ROKU transakcjami —
    pusty punkt. Tylko liczby i kolory z kodu (nazwy są w legendzie raportu)."""
    lata = por["lata"]
    serie = [(o["kolor"], o.get("lata", {}), o.get("lata_liczba", {}), str(nr), False) for nr, o in enumerate(por["obszary"], start=1)]
    serie.append(("#6e6e73", por["calosc"].get("lata", {}), por["calosc"].get("lata_liczba", {}), "", True))
    wartosci = [v for _, med, _, _, _ in serie for v in med.values()]
    otwarcie = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>'
    if len(lata) < 2 or not wartosci:
        return otwarcie + f'<text x="{szerokosc / 2}" y="{wysokosc / 2}" text-anchor="middle" fill="#6e6e73">za mało lat do wykresu</text></svg>'
    lo, hi, krok = _ladna_os(min(wartosci), max(wartosci))
    m = {"l": 70, "p": 40, "g": 14, "d": 30}

    def x(rok):
        return m["l"] + (lata.index(rok)) * (szerokosc - m["l"] - m["p"]) / (len(lata) - 1)

    def y(v):
        return wysokosc - m["d"] - (v - lo) / ((hi - lo) or 1) * (wysokosc - m["g"] - m["d"])

    czesci = [otwarcie]
    v = lo
    while v <= hi + krok / 2:
        etykieta = f"{v:,.0f}".replace(",", " ")
        czesci.append(f'<line x1="{m["l"]}" x2="{szerokosc - m["p"]}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#e8e8ed"/>'
                      f'<text x="{m["l"] - 8}" y="{y(v) + 4:.1f}" text-anchor="end" fill="#6e6e73">{etykieta}</text>')
        v += krok
    co_ile = math.ceil(len(lata) / 12)  # najwyżej ~12 podpisów lat; ostatni rok zawsze podpisany
    for i, rok in enumerate(lata):
        if (len(lata) - 1 - i) % co_ile == 0:
            czesci.append(f'<text x="{x(rok):.1f}" y="{wysokosc - 10}" text-anchor="middle" fill="#6e6e73">{rok}</text>')
    for kolor, mediany, liczby, numer, przerywana in serie:
        punkty = [(x(r), y(mediany[r]), liczby.get(r, 0)) for r in lata if r in mediany]
        if not punkty:
            continue
        kreska = ' stroke-dasharray="6 4"' if przerywana else ""
        czesci.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b, _ in punkty)}" fill="none" stroke="{kolor}" stroke-width="2.5"{kreska}/>')
        for a, b, n in punkty:
            wypelnienie = kolor if n >= MIN_W_ROKU else "#ffffff"
            czesci.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="4" fill="{wypelnienie}" stroke="{kolor}" stroke-width="2"/>')
        if numer:
            a, b, _ = punkty[-1]
            czesci.append(f'<text x="{a + 8:.1f}" y="{b + 4:.1f}" font-weight="700" fill="{kolor}">{numer}</text>')
    czesci.append("</svg>")
    return "".join(czesci)



# ---------- karta wyceny porównawczej do druku (ETAP 113) ----------


def mapa_wyceny_svg(wynik: dict, lat: float, lng: float, szerokosc: int = 640, wysokosc: int = 640) -> str:
    """Schemat: okrąg promienia, wskazane miejsce i podobne transakcje z
    numerami jak w tabeli karty (od najbliższej), podziałka, strzałka północy."""
    promien = wynik["promien_m"]
    margines = 36
    skala = (min(szerokosc, wysokosc) / 2 - margines) / promien  # piksele na metr
    kx = math.cos(math.radians(lat)) * 111_195

    def px(la, ln):
        return szerokosc / 2 + (ln - lng) * kx * skala, wysokosc / 2 - (la - lat) * 111_195 * skala

    czesci = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" font-family="sans-serif" font-size="11"><rect width="100%" height="100%" fill="#ffffff"/>',
              f'<circle cx="{szerokosc / 2}" cy="{wysokosc / 2}" r="{promien * skala:.1f}" fill="#0071e3" fill-opacity="0.04" stroke="#0071e3" stroke-width="1.5" stroke-dasharray="6 5"/>']
    for nr, t in reversed(list(enumerate(wynik["transakcje"], start=1))):  # najbliższe rysowane na wierzchu
        x, y = px(t["lat"], t["lng"])
        czesci.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#ff9f0a" stroke="#a33a00" stroke-width="1"/>'
                      f'<text x="{x:.1f}" y="{y + 3.5:.1f}" text-anchor="middle" font-weight="700" fill="#1d1d1f">{nr}</text>')
    srodek_x, srodek_y = szerokosc / 2, wysokosc / 2
    czesci.append(f'<path d="M{srodek_x},{srodek_y} l-7,-18 a7,7 0 1,1 14,0 z" fill="#0071e3" stroke="#ffffff" stroke-width="1.5"/>')
    _, _, krok = _ladna_os(0, promien / 2, 1)
    dlugosc = krok * skala
    opis = f"{krok / 1000:g} km".replace(".", ",") if krok >= 1000 else f"{krok:g} m"
    czesci.append(f'<path d="M{margines},{wysokosc - 18} v6 h{dlugosc:.1f} v-6" fill="none" stroke="#1d1d1f" stroke-width="1.5"/>'
                  f'<text x="{margines + dlugosc + 6:.1f}" y="{wysokosc - 12}" fill="#1d1d1f">{opis}</text>')
    x = szerokosc - margines + 10
    czesci.append(f'<path d="M{x},{margines - 22} L{x + 6},{margines - 6} L{x},{margines - 10} L{x - 6},{margines - 6} Z" fill="#1d1d1f"/><text x="{x}" y="{margines + 6}" text-anchor="middle" fill="#1d1d1f">N</text>')
    czesci.append("</svg>")
    return "".join(czesci)

