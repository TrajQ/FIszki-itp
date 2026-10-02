"""Raport z inwentaryzacji terenowej (ETAP 69): zestawienie i mapa SVG.

Punkty numerujemy w kolejności pomiaru (1, 2, 3…) — ten sam numer jest
na mapie, w tabeli i przy zdjęciu. Mapa jest schematyczna (bez podkładu,
żeby dała się wydrukować bez internetu): współrzędne przeliczone na metry
lokalną skalą, północ u góry, podziałka.
"""

import math
import statistics
from collections import Counter

import h3

PALETA = ["#0a84ff", "#ff9f0a", "#30d158", "#ff375f", "#bf5af2", "#64d2ff", "#ffd60a", "#ac8e68", "#5e5ce6", "#ff6961"]
KOLOR_BRAK = "#8e8e93"
KOLOR_JEDNOLITY = "#0a84ff"
KROKI_PODZIALKI_M = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000]


def ponumeruj(punkty: list[dict]) -> list[dict]:
    """Punkty w kolejności pomiaru z numerem „nr”."""
    return [{**p, "nr": i} for i, p in enumerate(sorted(punkty, key=lambda p: (p["czas"], p["id"])), start=1)]


def _tekst(w) -> str:
    if isinstance(w, list):
        return "; ".join(w)
    return "tak" if w is True else "nie" if w is False else str(w)


KOLOR_PASKA = "#0071e3"


def zestawienie(pola: list[dict], punkty: list[dict]) -> list[dict]:
    """Dla każdego pola: rozkład wartości (wybór, tak/nie), statystyki
    (liczba) albo liczba wypełnionych (tekst)."""
    wynik = []
    for pole in pola:
        wartosci = [p["wartosci"][pole["nazwa"]] for p in punkty if pole["nazwa"] in p["wartosci"]]
        pozycja = {"nazwa": pole["nazwa"], "typ": pole["typ"], "wypelnione": len(wartosci), "wszystkie": len(punkty)}
        if pole["typ"] in ("wybor", "tak_nie"):
            opcje = pole["opcje"] if pole["typ"] == "wybor" else ["tak", "nie"]
            teksty = [_tekst(w) for w in wartosci]
            pozycja["rozklad"] = [
                {"wartosc": o, "liczba": teksty.count(o), "procent": 100 * teksty.count(o) / len(punkty) if punkty else 0}
                for o in opcje
            ]
        elif pole["typ"] == "wiele":
            # procent wszystkich punktów (odpowiedzi); suma może przekroczyć 100%
            pozycja["rozklad"] = [
                {"wartosc": o, "liczba": sum(1 for w in wartosci if o in w), "procent": 100 * sum(1 for w in wartosci if o in w) / len(punkty) if punkty else 0}
                for o in pole["opcje"]
            ]
            pozycja["wiele"] = True
        elif pole["typ"] == "liczba" and wartosci:
            pozycja["statystyki"] = {
                "min": min(wartosci),
                "max": max(wartosci),
                "srednia": statistics.fmean(wartosci),
                "mediana": statistics.median(wartosci),
                "suma": math.fsum(wartosci),
            }
        if "rozklad" in pozycja:
            # ETAP 99: kolor paska wykresu — skala od zielonego do czerwonego, inaczej jeden kolor
            n = len(pozycja["rozklad"])
            for i, r in enumerate(pozycja["rozklad"]):
                r["kolor"] = kolor_skali(i, n) if pole.get("skala") else KOLOR_PASKA
        wynik.append(pozycja)
    return wynik


def kolor_skali(i: int, liczba: int) -> str:
    """Kolor i-tej opcji skali od najlepszej (zielony) do najgorszej
    (czerwony) — odcień HSL od 130° do 0°. Ten sam wzór jest w teren.js."""
    odcien = 130 if liczba < 2 else round(130 - 130 * i / (liczba - 1))
    return f"hsl({odcien}, 70%, 42%)"


def kolory_pola(pole: dict | None) -> dict[str, str]:
    if pole is None:
        return {}
    opcje = pole["opcje"] if pole["typ"] == "wybor" else ["tak", "nie"]
    if pole.get("skala"):
        return {o: kolor_skali(i, len(opcje)) for i, o in enumerate(opcje)}
    return {o: PALETA[i % len(PALETA)] for i, o in enumerate(opcje)}


def kolor_punktu(p: dict, pole: dict | None, kolory: dict[str, str]) -> str:
    if pole is None:
        return KOLOR_JEDNOLITY
    if pole["nazwa"] not in p["wartosci"]:
        return KOLOR_BRAK
    return kolory.get(_tekst(p["wartosci"][pole["nazwa"]]), KOLOR_BRAK)


def mapa_svg(punkty: list[dict], pole: dict | None, szerokosc: int = 1000, wysokosc: int = 640) -> str:
    """Schematyczna mapa ponumerowanych punktów. W SVG trafiają tylko
    liczby i kolory z kodu (numery punktów, podziałka)."""
    z_polozeniem = [p for p in punkty if p["lat"] is not None]
    naglowek = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" '
        f'font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>'
    )
    if not z_polozeniem:
        return naglowek + f'<text x="{szerokosc / 2}" y="{wysokosc / 2}" text-anchor="middle" fill="#6e6e73">brak punktów z położeniem</text></svg>'

    szer_geo = sum(p["lat"] for p in z_polozeniem) / len(z_polozeniem)
    fi = math.radians(szer_geo)
    m_lat = 111132.954 - 559.822 * math.cos(2 * fi) + 1.175 * math.cos(4 * fi)
    m_lng = 111412.84 * math.cos(fi) - 93.5 * math.cos(3 * fi)
    xy = [((p["lng"]) * m_lng, (p["lat"]) * m_lat) for p in z_polozeniem]
    minx, maxx = min(x for x, _ in xy), max(x for x, _ in xy)
    miny, maxy = min(y for _, y in xy), max(y for _, y in xy)
    margines, pole_dol = 50, 40
    zasieg = max(maxx - minx, maxy - miny, 20.0)  # co najmniej 20 m, żeby jeden punkt nie wypełnił mapy
    skala = zasieg / min(szerokosc - 2 * margines, wysokosc - 2 * margines - pole_dol)  # m na piksel
    sx, sy = (minx + maxx) / 2, (miny + maxy) / 2

    def piksel(x, y):
        return szerokosc / 2 + (x - sx) / skala, (wysokosc - pole_dol) / 2 - (y - sy) / skala

    kolory = kolory_pola(pole)
    czesci = [naglowek]
    for p, (x, y) in zip(z_polozeniem, xy):
        px, py = piksel(x, y)
        czesci.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="11" fill="{kolor_punktu(p, pole, kolory)}" stroke="#ffffff" stroke-width="2"/>'
            f'<text x="{px:.1f}" y="{py + 4:.1f}" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">{int(p["nr"])}</text>'
        )
    dlugosc_m = max((k for k in KROKI_PODZIALKI_M if k / skala <= szerokosc / 4), default=KROKI_PODZIALKI_M[0])
    dl = dlugosc_m / skala
    y0 = wysokosc - 18
    czesci.append(
        f'<g stroke="#1d1d1f" stroke-width="2"><line x1="{margines}" y1="{y0}" x2="{margines + dl:.1f}" y2="{y0}"/>'
        f'<line x1="{margines}" y1="{y0 - 5}" x2="{margines}" y2="{y0 + 1}"/><line x1="{margines + dl:.1f}" y1="{y0 - 5}" x2="{margines + dl:.1f}" y2="{y0 + 1}"/></g>'
        f'<text x="{margines + dl + 6:.1f}" y="{y0 + 4}" fill="#1d1d1f">{dlugosc_m} m</text>'
    )
    xn = szerokosc - margines
    czesci.append(
        f'<path d="M{xn},{margines - 30} L{xn + 7},{margines - 12} L{xn},{margines - 16} L{xn - 7},{margines - 12} Z" fill="#1d1d1f"/>'
        f'<text x="{xn}" y="{margines + 2}" text-anchor="middle" fill="#1d1d1f">N</text>'
    )
    czesci.append("</svg>")
    return "".join(czesci)


# ---------- rozmieszczenie punktów w heksagonach H3 (ETAP 132) ----------

ROZDZIELCZOSCI = (11, 10, 9)  # krawędź ok. 30 / 75 / 200 m — teren to zwykle setki metrów
MIN_PUNKTOW_HEKSAGONOW = 10
SREDNIO_W_KOMORCE = 2  # wybieramy najdrobniejszą siatkę z co najmniej tyloma punktami na komórkę
KOLORY_GESTOSCI = ["#dbeafe", "#93c5fd", "#60a5fa", "#2563eb", "#1e3a8a"]


def heksagony(punkty: list[dict], pole: dict | None) -> dict | None:
    """Punkty z położeniem w komórkach H3: liczba punktów, ich numery i (dla
    wybranego pola) wartość najczęstsza z udziałem. Rozdzielczość dobierana
    tak, żeby komórka miała średnio co najmniej 2 punkty."""
    z_polozeniem = [p for p in punkty if p["lat"] is not None]
    if len(z_polozeniem) < MIN_PUNKTOW_HEKSAGONOW:
        return None
    for r in ROZDZIELCZOSCI:
        po_komorce: dict = {}
        for p in z_polozeniem:
            po_komorce.setdefault(h3.latlng_to_cell(p["lat"], p["lng"], r), []).append(p)
        if len(z_polozeniem) / len(po_komorce) >= SREDNIO_W_KOMORCE:
            break
    komorki = []
    for komorka, czlonkowie in sorted(po_komorce.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        dominujaca = udzial = None
        if pole is not None:
            wartosci = [_tekst(p["wartosci"][pole["nazwa"]]) for p in czlonkowie if pole["nazwa"] in p["wartosci"]]
            if wartosci:
                dominujaca, ile = max(Counter(wartosci).items(), key=lambda kv: (kv[1], kv[0]))
                udzial = 100 * ile / len(czlonkowie)
        komorki.append({"nr": len(komorki) + 1, "h3": komorka, "granica": h3.cell_to_boundary(komorka), "liczba": len(czlonkowie),
                        "numery": sorted(p["nr"] for p in czlonkowie), "dominujaca": dominujaca, "udzial": udzial})
    liczby = sorted({k["liczba"] for k in komorki})
    return {"rozdzielczosc": r, "krawedz_m": round(h3.average_hexagon_edge_length(r, unit="m")), "komorki": komorki,
            "maks": liczby[-1], "punktow": len(z_polozeniem)}


def kolor_gestosci(liczba: int, maks: int) -> str:
    """Pięć odcieni niebieskiego od 1 do maks punktów w komórce."""
    return KOLORY_GESTOSCI[min(len(KOLORY_GESTOSCI) - 1, int((liczba - 1) * len(KOLORY_GESTOSCI) / max(1, maks)))]


def heksagony_svg(wynik: dict, szerokosc: int = 1000, wysokosc: int = 560) -> str:
    """Mapa komórek: liczba punktów (duża) i numer komórki jak w tabeli raportu (mały)."""
    wierzcholki = [w for k in wynik["komorki"] for w in k["granica"]]
    szer_geo = sum(w[0] for w in wierzcholki) / len(wierzcholki)
    fi = math.radians(szer_geo)
    m_lat = 111132.954 - 559.822 * math.cos(2 * fi) + 1.175 * math.cos(4 * fi)
    m_lng = 111412.84 * math.cos(fi) - 93.5 * math.cos(3 * fi)
    xy = [(lng * m_lng, lat * m_lat) for lat, lng in wierzcholki]
    minx, maxx = min(x for x, _ in xy), max(x for x, _ in xy)
    miny, maxy = min(y for _, y in xy), max(y for _, y in xy)
    margines, pole_dol = 40, 40
    skala = max(maxx - minx, maxy - miny) / min(szerokosc - 2 * margines, wysokosc - 2 * margines - pole_dol)
    sx, sy = (minx + maxx) / 2, (miny + maxy) / 2

    def piksel(lat, lng):
        return szerokosc / 2 + (lng * m_lng - sx) / skala, (wysokosc - pole_dol) / 2 - (lat * m_lat - sy) / skala

    czesci = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" '
              f'font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>']
    for k in wynik["komorki"]:
        punkty = " ".join(f"{a:.1f},{b:.1f}" for a, b in (piksel(lat, lng) for lat, lng in k["granica"]))
        cx, cy = piksel(*h3.cell_to_latlng(k["h3"]))
        jasne_tlo = KOLORY_GESTOSCI.index(kolor_gestosci(k["liczba"], wynik["maks"])) < 3
        czesci.append(f'<polygon points="{punkty}" fill="{kolor_gestosci(k["liczba"], wynik["maks"])}" stroke="#ffffff" stroke-width="2"/>'
                      f'<text x="{cx:.1f}" y="{cy + 3:.1f}" text-anchor="middle" font-size="15" font-weight="700" fill="{"#1d1d1f" if jasne_tlo else "#ffffff"}">{k["liczba"]}</text>'
                      f'<text x="{cx:.1f}" y="{cy + 17:.1f}" text-anchor="middle" font-size="10" fill="{"#1d1d1f" if jasne_tlo else "#ffffff"}">nr {k["nr"]}</text>')
    dlugosc_m = max((d for d in KROKI_PODZIALKI_M if d / skala <= szerokosc / 4), default=KROKI_PODZIALKI_M[0])
    dl = dlugosc_m / skala
    y0 = wysokosc - 18
    czesci.append(f'<g stroke="#1d1d1f" stroke-width="2"><line x1="{margines}" y1="{y0}" x2="{margines + dl:.1f}" y2="{y0}"/></g>'
                  f'<text x="{margines + dl + 6:.1f}" y="{y0 + 4}" fill="#1d1d1f">{dlugosc_m} m</text>')
    czesci.append("</svg>")
    return "".join(czesci)
