"""Przekrój terenu koncepcji z wysokością budynków (ETAP 238).

Linia przekroju A–A' przechodzi przez środek rysunku pod wybranym
kątem (azymut od północy: 0° — przekrój północ–południe, 90° — zachód–
wschód) i może być przesunięta w bok o procent połowy szerokości
rysunku. Na przekroju:

- pas terenu pod linią gruntu w kolorach funkcji (odcinki, w których
  linia przecina tereny),
- budynki jako prostokąty: szerokość = długość przecięcia linii z
  obrysem, wysokość = kondygnacje × WYSOKOSC_KONDYGNACJI_M (jak w
  analizie cienia, osiedle/cien.py),
- granice obszaru opracowania i — gdy plan ustala maks. liczbę
  kondygnacji — linia dopuszczalnej wysokości.

Teren jest płaski: Warsztat nie ma numerycznego modelu terenu, więc
przekrój pokazuje wysokość zabudowy i odstępy między budynkami, nie
rzeźbę terenu. W SVG są tylko liczby i kolory z kodu (D-048).
"""

import math

from shapely.geometry import LineString

from .bilans import FUNKCJE, KOLOR_BUDYNKU, _w_metrach, metry_na_stopien, wczytaj_budynki, wczytaj_tereny
from .cien import WYSOKOSC_KONDYGNACJI_M
from . import wskazniki as wsk


class BladPrzekroju(ValueError):
    """Zły parametr przekroju."""


def _odcinki(geometria, linia: LineString, poczatek) -> list[tuple[float, float]]:
    """Odcinki linii wewnątrz geometrii jako (od, do) w metrach od A."""
    czesc = linia.intersection(geometria)
    if czesc.is_empty:
        return []
    linie = [g for g in getattr(czesc, "geoms", [czesc]) if g.geom_type == "LineString" and g.length > 0.05]
    wynik = []
    for odc in linie:
        a, b = odc.coords[0], odc.coords[-1]
        da = math.dist(a, poczatek)
        db = math.dist(b, poczatek)
        wynik.append((min(da, db), max(da, db)))
    return sorted(wynik)


def przekroj(geojson: dict, kat: float = 90, przesuniecie_proc: float = 0, ustawienia: dict | None = None) -> dict:
    """Przecięcia linii A–A' z terenami, budynkami i obszarem; odległości w metrach od A."""
    if not (isinstance(kat, (int, float)) and math.isfinite(kat)):
        raise BladPrzekroju("Kąt przekroju musi być liczbą.")
    if not (isinstance(przesuniecie_proc, (int, float)) and -100 <= przesuniecie_proc <= 100):
        raise BladPrzekroju("Przesunięcie przekroju: od −100 do 100%.")
    obszar, tereny = wczytaj_tereny(geojson)
    budynki = wczytaj_budynki(geojson)
    wszystkie = [t["geometria"] for t in tereny] + [b["geometria"] for b in budynki] + ([obszar] if obszar is not None else [])
    if not wszystkie:
        raise BladPrzekroju("Narysuj tereny albo budynki — nie ma czego przeciąć.")

    szerokosc = sum(g.centroid.y for g in wszystkie) / len(wszystkie)
    metry = [_w_metrach(g, szerokosc) for g in wszystkie]
    minx = min(g.bounds[0] for g in metry)
    miny = min(g.bounds[1] for g in metry)
    maxx = max(g.bounds[2] for g in metry)
    maxy = max(g.bounds[3] for g in metry)
    srodek = ((minx + maxx) / 2, (miny + maxy) / 2)

    kat = kat % 180
    kierunek = (math.sin(math.radians(kat)), math.cos(math.radians(kat)))  # azymut od północy
    prostopadly = (kierunek[1], -kierunek[0])
    # połowa rozpiętości rysunku w kierunku prostopadłym — skala przesunięcia
    narozniki = [(minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]
    polowa = max(abs((x - srodek[0]) * prostopadly[0] + (y - srodek[1]) * prostopadly[1]) for x, y in narozniki)
    przesuniecie = przesuniecie_proc / 100 * polowa
    s = (srodek[0] + prostopadly[0] * przesuniecie, srodek[1] + prostopadly[1] * przesuniecie)
    # linia przez cały prostokąt rysunku: rzut narożników na kierunek
    rzuty = [(x - s[0]) * kierunek[0] + (y - s[1]) * kierunek[1] for x, y in narozniki]
    zapas = 5.0
    a = (s[0] + kierunek[0] * (min(rzuty) - zapas), s[1] + kierunek[1] * (min(rzuty) - zapas))
    b = (s[0] + kierunek[0] * (max(rzuty) + zapas), s[1] + kierunek[1] * (max(rzuty) + zapas))
    # A zawsze z lewej (zachód) albo — przy przekroju N–S — od północy
    if a[0] > b[0] + 1e-6 or (abs(a[0] - b[0]) <= 1e-6 and a[1] < b[1]):
        a, b = b, a
    linia = LineString([a, b])

    wynik_tereny = []
    for nr, t in enumerate(tereny, start=1):
        for od, do in _odcinki(_w_metrach(t["geometria"], szerokosc), linia, a):
            wynik_tereny.append({"nr": nr, "funkcja": t["funkcja"], "od_m": round(od, 1), "do_m": round(do, 1)})
    wynik_budynki = []
    for nr, bud in enumerate(budynki, start=1):
        wysokosc = bud["kondygnacje"] * WYSOKOSC_KONDYGNACJI_M
        for od, do in _odcinki(_w_metrach(bud["geometria"], szerokosc), linia, a):
            wynik_budynki.append({"nr": nr, "kondygnacje": bud["kondygnacje"], "wysokosc_m": wysokosc, "od_m": round(od, 1), "do_m": round(do, 1)})
    granice_obszaru = []
    if obszar is not None:
        granice_obszaru = [{"od_m": round(od, 1), "do_m": round(do, 1)} for od, do in _odcinki(_w_metrach(obszar, szerokosc), linia, a)]

    # odstępy między kolejnymi budynkami na linii — do porównania z wysokością
    odstepy = []
    po_kolei = sorted(wynik_budynki, key=lambda x: x["od_m"])
    for lewy, prawy in zip(po_kolei, po_kolei[1:]):
        if prawy["od_m"] > lewy["do_m"]:
            odstepy.append({"miedzy": [lewy["nr"], prawy["nr"]], "od_m": lewy["do_m"], "do_m": prawy["od_m"], "odstep_m": round(prawy["od_m"] - lewy["do_m"], 1)})

    plan = wsk.ustalenia_planu(ustawienia) if ustawienia else {}
    max_kondygnacje = plan.get("max_kondygnacje")
    mx, my = metry_na_stopien(szerokosc)
    return {
        "kat": round(kat, 1),
        "przesuniecie_proc": przesuniecie_proc,
        "dlugosc_m": round(linia.length, 1),
        "linia": [[a[0] / mx, a[1] / my], [b[0] / mx, b[1] / my]],  # [lon, lat] — do mapy
        "tereny": wynik_tereny,
        "budynki": wynik_budynki,
        "odstepy": odstepy,
        "obszar": granice_obszaru,
        "max_wysokosc_planu_m": max_kondygnacje * WYSOKOSC_KONDYGNACJI_M if max_kondygnacje else None,
        "wysokosc_kondygnacji_m": WYSOKOSC_KONDYGNACJI_M,
    }


KROKI_M = [5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000]


def przekroj_svg(p: dict, szerokosc_px: int = 1000, wysokosc_px: int = 340) -> str:
    """Rysunek przekroju: poziomo i pionowo ta sama skala, chyba że budynki
    byłyby za niskie, by je zobaczyć — wtedy przewyższenie (podpisane)."""
    margines, dol = 40, 70  # dół: pas terenu, oś odległości i podpisy
    pole_szer = szerokosc_px - 2 * margines
    skala_x = pole_szer / max(p["dlugosc_m"], 1)
    najwyzszy = max([b["wysokosc_m"] for b in p["budynki"]] + [p["max_wysokosc_planu_m"] or 0, WYSOKOSC_KONDYGNACJI_M])
    pole_wys = wysokosc_px - dol - 30
    skala_y = skala_x
    if najwyzszy * skala_x > pole_wys or najwyzszy * skala_x < 0.35 * pole_wys:
        # za wysokie — zmniejszamy; za niskie (długi przekrój) — przewyższamy, najwyżej ×10
        skala_y = min(skala_x * 10, pole_wys / (najwyzszy * 1.15))
    przewyzszenie = skala_y / skala_x
    grunt = wysokosc_px - dol

    def x(m):
        return margines + m * skala_x

    czesci = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc_px} {wysokosc_px}" width="{szerokosc_px}" height="{wysokosc_px}" '
        f'font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>'
    ]
    # pas terenu pod gruntem
    czesci.append(f'<rect x="{margines}" y="{grunt}" width="{pole_szer}" height="10" fill="#e5e5ea"/>')
    for t in p["tereny"]:
        kolor = FUNKCJE.get(t["funkcja"], {}).get("kolor", "#8e8e93")
        czesci.append(f'<rect x="{x(t["od_m"]):.1f}" y="{grunt}" width="{max(0.5, (t["do_m"] - t["od_m"]) * skala_x):.1f}" height="10" fill="{kolor}"/>')
    # dopuszczalna wysokość z planu
    if p["max_wysokosc_planu_m"]:
        y = grunt - p["max_wysokosc_planu_m"] * skala_y
        czesci.append(
            f'<line x1="{margines}" y1="{y:.1f}" x2="{margines + pole_szer}" y2="{y:.1f}" stroke="#d70015" stroke-width="1.5" stroke-dasharray="8 4"/>'
            f'<text x="{margines + pole_szer}" y="{y - 4:.1f}" text-anchor="end" fill="#d70015">plan: maks. {_liczba(p["max_wysokosc_planu_m"])} m</text>'
        )
    # budynki
    for b in p["budynki"]:
        x0, x1 = x(b["od_m"]), x(b["do_m"])
        h = b["wysokosc_m"] * skala_y
        czesci.append(f'<rect x="{x0:.1f}" y="{grunt - h:.1f}" width="{max(1.0, x1 - x0):.1f}" height="{h:.1f}" fill="{KOLOR_BUDYNKU}" fill-opacity="0.85" stroke="#1d1d1f" stroke-width="1"/>')
        # kreski kondygnacji
        for k in range(1, int(b["kondygnacje"])):
            yk = grunt - k * WYSOKOSC_KONDYGNACJI_M * skala_y
            czesci.append(f'<line x1="{x0:.1f}" y1="{yk:.1f}" x2="{x1:.1f}" y2="{yk:.1f}" stroke="#ffffff" stroke-opacity="0.35" stroke-width="1"/>')
        srodek = (x0 + x1) / 2
        czesci.append(f'<text x="{srodek:.1f}" y="{grunt - h - 18:.1f}" text-anchor="middle" fill="#1d1d1f" font-weight="700">{b["nr"]}</text>'
                      f'<text x="{srodek:.1f}" y="{grunt - h - 5:.1f}" text-anchor="middle" fill="#3a3a3c" font-size="11">{_liczba(b["wysokosc_m"])} m</text>')
    # odstępy między budynkami (wymiar nad gruntem)
    for o in p["odstepy"]:
        x0, x1 = x(o["od_m"]), x(o["do_m"])
        if x1 - x0 < 34:
            continue
        y = grunt - 8
        czesci.append(
            f'<g stroke="#0071e3" stroke-width="1"><line x1="{x0:.1f}" y1="{y}" x2="{x1:.1f}" y2="{y}"/>'
            f'<line x1="{x0:.1f}" y1="{y - 4}" x2="{x0:.1f}" y2="{y + 4}"/><line x1="{x1:.1f}" y1="{y - 4}" x2="{x1:.1f}" y2="{y + 4}"/></g>'
            f'<text x="{(x0 + x1) / 2:.1f}" y="{y - 4}" text-anchor="middle" fill="#0071e3" font-size="11">{_liczba(o["odstep_m"])} m</text>'
        )
    # linia gruntu i granice obszaru
    czesci.append(f'<line x1="{margines}" y1="{grunt}" x2="{margines + pole_szer}" y2="{grunt}" stroke="#1d1d1f" stroke-width="2"/>')
    for g in p["obszar"]:
        for m in (g["od_m"], g["do_m"]):
            czesci.append(f'<line x1="{x(m):.1f}" y1="{grunt - 30}" x2="{x(m):.1f}" y2="{grunt + 16}" stroke="#1d1d1f" stroke-width="1.5" stroke-dasharray="6 4"/>')
    # oś odległości
    krok = next((k for k in KROKI_M if k * skala_x >= 60), KROKI_M[-1])
    yo = grunt + 28
    czesci.append(f'<line x1="{margines}" y1="{yo}" x2="{margines + pole_szer}" y2="{yo}" stroke="#8e8e93" stroke-width="1"/>')
    m = 0
    while m <= p["dlugosc_m"] + 1e-6:
        czesci.append(f'<line x1="{x(m):.1f}" y1="{yo - 3}" x2="{x(m):.1f}" y2="{yo + 3}" stroke="#8e8e93"/>'
                      f'<text x="{x(m):.1f}" y="{yo + 16}" text-anchor="middle" fill="#6e6e73" font-size="11">{m}</text>')
        m += krok
    czesci.append(f'<text x="{margines + pole_szer}" y="{yo + 32}" text-anchor="end" fill="#6e6e73" font-size="11">odległość od A [m]</text>')
    # A i A'
    czesci.append(f'<text x="{margines - 8}" y="{grunt + 5}" text-anchor="end" font-weight="700" fill="#1d1d1f">A</text>'
                  f'<text x="{margines + pole_szer + 8}" y="{grunt + 5}" font-weight="700" fill="#1d1d1f">A′</text>')
    opis = f"przekrój A–A′, azymut {_liczba(p['kat'])}°, teren płaski, kondygnacja = {_liczba(WYSOKOSC_KONDYGNACJI_M)} m"
    if abs(przewyzszenie - 1) > 0.05:
        opis += f", skala pionowa ×{_liczba(round(przewyzszenie, 1))} poziomej"
    czesci.append(f'<text x="{margines}" y="18" fill="#6e6e73" font-size="11">{opis}</text>')
    czesci.append("</svg>")
    return "".join(czesci)


def _liczba(w: float) -> str:
    """12.0 → „12”, 7.5 → „7,5” (polski przecinek)."""
    return (f"{w:.1f}".rstrip("0").rstrip(".")).replace(".", ",")
