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


# ---------- tabela krzyżowa dwóch pytań (ETAP 179) ----------

POLA_KRZYZOWE = ("wybor", "tak_nie")  # jedna odpowiedź na osobę — warunek testu chi-kwadrat


def _opcje(pole: dict) -> list[str]:
    return pole["opcje"] if pole["typ"] == "wybor" else ["tak", "nie"]


def _p_chi2(chi2: float, df: int) -> float:
    """P(X ≥ chi2) dla rozkładu chi-kwadrat: 1 − P(df/2, chi2/2), gdzie P to
    regularyzowana dolna funkcja gamma (szereg dla x < a + 1, inaczej ułamek
    łańcuchowy — Numerical Recipes, rozdz. 6.2)."""
    a, x = df / 2, chi2 / 2
    if x <= 0:
        return 1.0
    if x < a + 1:
        suma = wyraz = 1 / a
        n = a
        for _ in range(500):
            n += 1
            wyraz *= x / n
            suma += wyraz
            if abs(wyraz) < abs(suma) * 1e-15:
                break
        return max(0.0, 1 - suma * math.exp(-x + a * math.log(x) - math.lgamma(a)))
    b, c, d = x + 1 - a, 1e300, 1 / (x + 1 - a)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return min(1.0, math.exp(-x + a * math.log(x) - math.lgamma(a)) * h)


def tabela_krzyzowa(pole_a: dict, pole_b: dict, punkty: list[dict]) -> dict:
    """Liczności odpowiedzi na dwa pytania jednokrotnego wyboru, procenty
    w wierszach, test chi-kwadrat niezależności i V Craméra. Liczymy tylko
    osoby, które odpowiedziały na oba pytania; puste wiersze i kolumny
    pomijamy w teście."""
    wiersze, kolumny = _opcje(pole_a), _opcje(pole_b)
    liczby = [[0] * len(kolumny) for _ in wiersze]
    for p in punkty:
        a, b = p["wartosci"].get(pole_a["nazwa"]), p["wartosci"].get(pole_b["nazwa"])
        if a is None or b is None:
            continue
        a, b = _tekst(a), _tekst(b)
        if a in wiersze and b in kolumny:
            liczby[wiersze.index(a)][kolumny.index(b)] += 1
    w_razem = [sum(w) for w in liczby]
    k_razem = [sum(k) for k in zip(*liczby)]
    n = sum(w_razem)
    wynik = {"wiersze": wiersze, "kolumny": kolumny, "liczby": liczby, "w_razem": w_razem, "k_razem": k_razem, "n": n,
             "procent_w_wierszu": [[100 * x / w_razem[i] if w_razem[i] else None for x in wiersz] for i, wiersz in enumerate(liczby)],
             "chi2": None, "df": None, "p": None, "v_cramera": None, "male_oczekiwane": 0}
    ri = [i for i, s in enumerate(w_razem) if s]
    kj = [j for j, s in enumerate(k_razem) if s]
    if len(ri) < 2 or len(kj) < 2:
        return wynik
    chi2, male = 0.0, 0
    for i in ri:
        for j in kj:
            oczekiwana = w_razem[i] * k_razem[j] / n
            chi2 += (liczby[i][j] - oczekiwana) ** 2 / oczekiwana
            male += oczekiwana < 5
    df = (len(ri) - 1) * (len(kj) - 1)
    wynik.update(chi2=chi2, df=df, p=_p_chi2(chi2, df), v_cramera=math.sqrt(chi2 / (n * (min(len(ri), len(kj)) - 1))),
                 male_oczekiwane=male, komorek=len(ri) * len(kj))
    return wynik


def wykres_krzyzowy_svg(t: dict, kolory: list[str], szerokosc: int = 900) -> str:
    """ETAP 180: skumulowane słupki 100% — rozkład kolumn w każdym wierszu
    tabeli krzyżowej (wiersze bez odpowiedzi pominięte). Numery i liczby z
    kodu; opisy wierszy i kolumn są w HTML obok (tekst użytkownika)."""
    wiersze = [i for i, s in enumerate(t["w_razem"]) if s]
    wys_slupka, odstep, lewy, prawy = 26, 12, 34, 16
    wysokosc = len(wiersze) * (wys_slupka + odstep) + 26
    czesci = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" '
              f'font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>']
    pole = szerokosc - lewy - prawy
    for nr, i in enumerate(wiersze):
        y = nr * (wys_slupka + odstep) + 4
        czesci.append(f'<text x="{lewy - 8}" y="{y + wys_slupka / 2 + 4}" text-anchor="end" fill="#1d1d1f" font-weight="700">{nr + 1}</text>')
        x = lewy
        for j, liczba in enumerate(t["liczby"][i]):
            if not liczba:
                continue
            w = pole * liczba / t["w_razem"][i]
            czesci.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{wys_slupka}" fill="{kolory[j % len(kolory)]}" stroke="#ffffff" stroke-width="1"/>')
            if w >= 34:
                czesci.append(f'<text x="{x + w / 2:.1f}" y="{y + wys_slupka / 2 + 4}" text-anchor="middle" fill="#ffffff" font-weight="600">{round(100 * liczba / t["w_razem"][i])}%</text>')
            x += w
    os_y = len(wiersze) * (wys_slupka + odstep) + 2
    for proc in (0, 25, 50, 75, 100):
        xp = lewy + pole * proc / 100
        czesci.append(f'<line x1="{xp:.1f}" x2="{xp:.1f}" y1="{os_y - 4}" y2="{os_y}" stroke="#86868b"/>'
                      f'<text x="{xp:.1f}" y="{os_y + 14}" text-anchor="middle" fill="#6e6e73">{proc}%</text>')
    czesci.append("</svg>")
    return "".join(czesci)


def kolory_kolumn(pole: dict) -> list[str]:
    """Kolory odpowiedzi w kolumnach: skala zielony→czerwony dla pola-skali, inaczej paleta."""
    opcje = _opcje(pole)
    return [kolor_skali(i, len(opcje)) for i in range(len(opcje))] if pole.get("skala") else PALETA[:len(opcje)]


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
