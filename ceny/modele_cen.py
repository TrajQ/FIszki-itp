"""Modele cen z transakcji RCN: regresja cech i gradient od miejsca (ETAP 246).

Wydzielone z ceny/rcn.py (ETAPy 156 i 241). Liczby liczy kod — opis
wyniku na stronie to tłumaczenie tych liczb, nie wycena.
"""

import math
import statistics
from datetime import date

from .rcn import _kwartyle, odleglosc_m, wspolczynniki_czasu


# ---------- co wpływa na cenę m² — regresja liniowa (ETAP 156) ----------

MIN_TRANSAKCJI_REGRESJI = 30
UCIECIE_PROC = 1  # tyle % najniższych i najwyższych cen m² pomijamy (pomyłki w rejestrze, transakcje nierynkowe)
T_ISTOTNOSCI = 1.96  # |t| ≥ 1,96 ≈ istotne na poziomie 5% (duża próba)

# klucz → (opis efektu, jednostka efektu); kolejność = kolumny modelu
ZMIENNE_REGRESJI = {
    "czas": ("z każdym rokiem", "zł/m² na rok"),
    "pow_10m2": ("każde 10 m² powierzchni więcej", "zł/m²"),
    "kondygnacja": ("każde piętro wyżej", "zł/m²"),
    "pierwotny": ("rynek pierwotny zamiast wtórnego", "zł/m²"),
}


def _odwroc(m: list[list[float]]) -> list[list[float]]:
    """Odwrotność małej macierzy (Gauss-Jordan z wyborem elementu głównego)."""
    n = len(m)
    a = [wiersz[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, wiersz in enumerate(m)]
    for kol in range(n):
        glowny = max(range(kol, n), key=lambda w: abs(a[w][kol]))
        if abs(a[glowny][kol]) < 1e-12:
            raise ValueError("Zmienne są współliniowe — nie da się rozdzielić ich wpływu.")
        a[kol], a[glowny] = a[glowny], a[kol]
        dzielnik = a[kol][kol]
        a[kol] = [x / dzielnik for x in a[kol]]
        for w in range(n):
            if w != kol and a[w][kol]:
                mnoznik = a[w][kol]
                a[w] = [x - mnoznik * y for x, y in zip(a[w], a[kol])]
    return [wiersz[n:] for wiersz in a]


def najmniejsze_kwadraty(x: list[list[float]], y: list[float]) -> dict:
    """OLS: współczynniki, błędy standardowe, R². x — wiersze bez wyrazu wolnego."""
    wiersze = [[1.0, *w] for w in x]
    k, n = len(wiersze[0]), len(wiersze)
    xtx = [[sum(w[i] * w[j] for w in wiersze) for j in range(k)] for i in range(k)]
    xty = [sum(w[i] * yi for w, yi in zip(wiersze, y)) for i in range(k)]
    odwrotna = _odwroc(xtx)
    b = [sum(odwrotna[i][j] * xty[j] for j in range(k)) for i in range(k)]
    reszty = [yi - sum(bi * wi for bi, wi in zip(b, w)) for w, yi in zip(wiersze, y)]
    rss = sum(r * r for r in reszty)
    srednia = statistics.fmean(y)
    tss = sum((yi - srednia) ** 2 for yi in y)
    sigma2 = rss / (n - k)
    bledy = [math.sqrt(sigma2 * odwrotna[i][i]) for i in range(k)]
    return {"b": b, "se": bledy, "r2": 1 - rss / tss if tss else None, "rmse": math.sqrt(rss / n), "n": n}


def regresja_cen(lokale: list[dict]) -> dict:
    """Jak cechy transakcji wiążą się z ceną m² „przy pozostałych równych”:
    czas, powierzchnia, piętro, rynek pierwotny. Zmienne bez zróżnicowania
    w danych (np. sam rynek wtórny) są pomijane. Piętro — tylko gdy znane
    w co najmniej 80% transakcji (pozostałe wtedy pomijamy). Wynik to
    związek w danych, nie wycena i nie przyczyna."""
    rekordy = [l for l in lokale if l.get("cena_m2") and l.get("pow_m2")]
    if len(rekordy) < MIN_TRANSAKCJI_REGRESJI:
        raise ValueError(f"Za mało transakcji (potrzeba co najmniej {MIN_TRANSAKCJI_REGRESJI}).")
    ceny = sorted(l["cena_m2"] for l in rekordy)
    ile = len(ceny) * UCIECIE_PROC // 100
    dolna, gorna = ceny[ile], ceny[-ile - 1]
    pominiete_skrajne = sum(1 for l in rekordy if not dolna <= l["cena_m2"] <= gorna)
    rekordy = [l for l in rekordy if dolna <= l["cena_m2"] <= gorna]

    zmienne = ["czas", "pow_10m2"]
    ze_pietrem = [l for l in rekordy if l.get("kondygnacja") is not None]
    if len(ze_pietrem) >= 0.8 * len(rekordy) and len({l["kondygnacja"] for l in ze_pietrem}) > 1:
        zmienne.append("kondygnacja")
        rekordy = ze_pietrem
    rynki = {l["rynek"] for l in rekordy}
    if {"pierwotny", "wtórny"} <= rynki:
        zmienne.append("pierwotny")
        rekordy = [l for l in rekordy if l["rynek"] in ("pierwotny", "wtórny")]
    if len(rekordy) < MIN_TRANSAKCJI_REGRESJI:
        raise ValueError(f"Za mało transakcji z kompletem cech (potrzeba co najmniej {MIN_TRANSAKCJI_REGRESJI}).")

    poczatek = min(date.fromisoformat(l["data"]) for l in rekordy)
    def wartosc(l, z):
        if z == "czas":
            return (date.fromisoformat(l["data"]) - poczatek).days / 365.25
        if z == "pow_10m2":
            return l["pow_m2"] / 10
        if z == "kondygnacja":
            return float(l["kondygnacja"])
        return 1.0 if l["rynek"] == "pierwotny" else 0.0
    zmienne = [z for z in zmienne if len({wartosc(l, z) for l in rekordy}) > 1]
    try:
        model = najmniejsze_kwadraty([[wartosc(l, z) for z in zmienne] for l in rekordy], [l["cena_m2"] for l in rekordy])
    except ValueError as e:
        raise ValueError(str(e)) from None
    efekty = []
    for i, z in enumerate(zmienne, start=1):
        b, se = model["b"][i], model["se"][i]
        t = b / se if se else None
        efekty.append({"zmienna": z, "opis": ZMIENNE_REGRESJI[z][0], "jednostka": ZMIENNE_REGRESJI[z][1],
                       "efekt": b, "blad": se, "t": t, "istotny": t is not None and abs(t) >= T_ISTOTNOSCI})
    return {"efekty": efekty, "r2": model["r2"], "rmse": model["rmse"], "n": model["n"],
            "pominiete_skrajne": pominiete_skrajne, "od": poczatek.isoformat(), "wyraz_wolny": model["b"][0]}


# ---------- cena a odległość od miejsca (ETAP 241) ----------

SZEROKOSCI_PIERSCIENI_M = (250, 500, 1000)
ZASIEGI_GRADIENTU_M = (2000, 5000, 10000)
MIN_W_PIERSCIENIU = 5  # mniej transakcji — mediana pierścienia niepewna (pusty słupek)
MIN_DO_TRENDU = 30


def gradient(rekordy: list[dict], lat: float, lng: float, szerokosc_m: int, zasieg_m: int) -> dict:
    """Mediana ceny za m² w pierścieniach co szerokosc_m od punktu (do zasieg_m)
    i średnia zmiana ceny na każdy kilometr (regresja liniowa).

    Gdy plik ma dość lat, ceny są najpierw sprowadzone do roku bazowego
    (wspolczynniki_czasu, ETAP 201) — inaczej pierścień z samymi starszymi
    transakcjami wyglądałby na tańszy tylko przez datę. To opis danych, nie
    model wartości lokalizacji: odległość od jednego punktu to nie
    jedyna cecha miejsca."""
    if szerokosc_m not in SZEROKOSCI_PIERSCIENI_M or zasieg_m not in ZASIEGI_GRADIENTU_M:
        raise ValueError("Niepoprawna szerokość pierścieni albo zasięg.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("Niepoprawne miejsce.")
    czas = wspolczynniki_czasu(rekordy)
    w_zasiegu = []
    for r in rekordy:
        if r["lat"] is None:
            continue
        odl = odleglosc_m(lat, lng, r["lat"], r["lng"])
        if odl > zasieg_m:
            continue
        cena = r["cena_m2"]
        if czas:
            wsp = czas["wspolczynniki"].get(r["rok"])
            if wsp is None:
                continue  # rok z za małą liczbą transakcji — bez korekty nie porównujemy
            cena *= wsp
        w_zasiegu.append((odl, cena))
    pierscienie = []
    for i in range(zasieg_m // szerokosc_m):
        od, do = i * szerokosc_m, (i + 1) * szerokosc_m
        ceny = sorted(c for d, c in w_zasiegu if od <= d < do or (do == zasieg_m and d == zasieg_m))
        p = {"od_m": od, "do_m": do, "liczba": len(ceny), "mediana_m2": None, "q1_m2": None, "q3_m2": None}
        if len(ceny) >= MIN_W_PIERSCIENIU:
            p["q1_m2"], p["mediana_m2"], p["q3_m2"] = _kwartyle(ceny)
        pierscienie.append(p)
    trend = None
    if len(w_zasiegu) >= MIN_DO_TRENDU and len({round(d) for d, _ in w_zasiegu}) > 2:
        ols = najmniejsze_kwadraty([[d / 1000] for d, _ in w_zasiegu], [c for _, c in w_zasiegu])
        trend = {"zmiana_na_km": ols["b"][1], "blad": ols["se"][1], "istotny": abs(ols["b"][1]) >= T_ISTOTNOSCI * ols["se"][1],
                 "r2": ols["r2"], "n": ols["n"]}
    return {
        "liczba": len(w_zasiegu),
        "pierscienie": pierscienie,
        "trend": trend,
        "rok_bazowy": czas["rok_bazowy"] if czas else None,
        "min_w_pierscieniu": MIN_W_PIERSCIENIU,
        "min_do_trendu": MIN_DO_TRENDU,
    }
