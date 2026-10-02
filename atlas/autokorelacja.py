"""Autokorelacja przestrzenna: globalne I Morana i lokalne LISA (Anselin).

Pytanie: czy gminy o wysokich wartościach sąsiadują z gminami o wysokich
wartościach (skupiska), czy rozkład w przestrzeni jest losowy?

- Sąsiedztwo typu „queen”: gminy są sąsiadami, gdy ich granice się
  stykają (choćby w punkcie). Granice z PRG upraszczamy dla każdej gminy
  osobno (atlas/granice.py), więc między sąsiadami mogą powstać szczeliny
  rzędu kilkudziesięciu metrów — dlatego sprawdzamy styk z tolerancją.
- Wagi standaryzowane wierszami: każdy sąsiad gminy ma wagę 1/liczba
  sąsiadów, a „opóźnienie przestrzenne” to średnia wartość u sąsiadów.
- Istotność z testu permutacyjnego (losowe przetasowanie wartości), jak w
  GeoDa i PySAL — bez założenia o rozkładzie normalnym. Ziarno losowania
  jest stałe, więc wynik jest powtarzalny.

Gorące punkty Getisa-Orda Gi* (ETAP 152): dla każdej gminy suma wartości
w niej i u sąsiadów porównana z tym, czego należałoby się spodziewać przy
losowym rozkładzie — wynik jako z-score. W odróżnieniu od LISA patrzy na
skupiska wartości (wysokie razem z otoczeniem), nie na podobieństwo do
sąsiadów, więc nie ma kategorii „odstająca”. Wagi binarne z samą gminą
(„gwiazdka”), istotność z rozkładu normalnego, progi 90/95/99% jak
w ArcGIS (Hot Spot Analysis).

Liczby liczy ten moduł; model językowy ich nie dotyka (CLAUDE.md).
"""

import math
import random
import statistics

from shapely.geometry import shape
from shapely.strtree import STRtree

TOLERANCJA_STYKU = 0.001  # stopnie, ok. 70–110 m — większa niż szczeliny po uproszczeniu
LICZBA_PERMUTACJI = 999
ZIARNO = 20260929
POZIOM_ISTOTNOSCI = 0.05

# (z krytyczne, poziom ufności) od najsilniejszego
PROGI_GI = [(2.576, 99), (1.960, 95), (1.645, 90)]
KATEGORIE_GI = {
    "H99": "gorący punkt (99%)", "H95": "gorący punkt (95%)", "H90": "gorący punkt (90%)",
    "ns": "nieistotne statystycznie",
    "C90": "zimny punkt (90%)", "C95": "zimny punkt (95%)", "C99": "zimny punkt (99%)",
}

KATEGORIE = {
    "HH": "wysokie wśród wysokich (gorący punkt)",
    "LL": "niskie wśród niskich (zimny punkt)",
    "HL": "wysoka otoczona niskimi (odstająca)",
    "LH": "niska otoczona wysokimi (odstająca)",
    "ns": "nieistotne statystycznie",
}


def sasiedzi(granice: dict) -> dict[str, set[str]]:
    """{teryt: {teryt sąsiadów}} z kolekcji GeoJSON gmin."""
    terytory = [c["properties"]["teryt"] for c in granice["features"]]
    geometrie = [shape(c["geometry"]).buffer(TOLERANCJA_STYKU / 2) for c in granice["features"]]
    drzewo = STRtree(geometrie)
    wynik = {t: set() for t in terytory}
    for i, geometria in enumerate(geometrie):
        for j in drzewo.query(geometria):
            j = int(j)
            if j != i and geometria.intersects(geometrie[j]):
                wynik[terytory[i]].add(terytory[j])
                wynik[terytory[j]].add(terytory[i])
    return wynik


def _odchylenia(wartosci: dict[str, float]) -> dict[str, float]:
    srednia = statistics.fmean(wartosci.values())
    return {t: v - srednia for t, v in wartosci.items()}


def _moran(z: dict[str, float], sasiedztwo: dict[str, list[str]]) -> float:
    """I Morana dla wag standaryzowanych wierszami (S0 = liczba gmin)."""
    licznik = sum(z[i] * statistics.fmean(z[j] for j in sasiedztwo[i]) for i in sasiedztwo)
    mianownik = sum(v * v for v in z.values())
    return licznik / mianownik


def analiza(wartosci: dict[str, float], sasiedzi_gmin: dict[str, set[str]]) -> dict:
    """Globalne I Morana i LISA dla gmin z wartością.

    Gminy bez sąsiadów z danymi („wyspy”) pomijamy — nie ma dla nich
    średniej u sąsiadów. Zwraca też liczbę pominiętych.
    """
    # Stała kolejność gmin: te same dane dają te same permutacje, a więc
    # ten sam wynik — niezależnie od kolejności, w jakiej przyszły z BDL.
    wartosci = dict(sorted(wartosci.items()))
    sasiedztwo = {
        t: sorted(s for s in sasiedzi_gmin.get(t, ()) if s in wartosci)
        for t in wartosci
    }
    sasiedztwo = {t: s for t, s in sasiedztwo.items() if s}
    # po usunięciu wysp ktoś mógł stracić wszystkich sąsiadów — powtarzamy
    while True:
        oczyszczone = {t: [s for s in lista if s in sasiedztwo] for t, lista in sasiedztwo.items()}
        oczyszczone = {t: lista for t, lista in oczyszczone.items() if lista}
        if oczyszczone == sasiedztwo:
            break
        sasiedztwo = oczyszczone

    n = len(sasiedztwo)
    if n < 5:
        raise ValueError("Za mało gmin z sąsiadami i danymi, żeby liczyć autokorelację (potrzeba co najmniej 5).")
    uzyte = {t: wartosci[t] for t in sasiedztwo}
    if len(set(uzyte.values())) < 2:
        raise ValueError("Wszystkie gminy mają tę samą wartość — autokorelacja nie ma sensu.")

    z = _odchylenia(uzyte)
    i_obs = _moran(z, sasiedztwo)
    oczekiwane = -1 / (n - 1)

    losowanie = random.Random(ZIARNO)
    terytory = list(z)
    wartosci_z = list(z.values())
    permutacje = []
    for _ in range(LICZBA_PERMUTACJI):
        losowanie.shuffle(wartosci_z)
        permutacje.append(_moran(dict(zip(terytory, wartosci_z)), sasiedztwo))
    if i_obs >= oczekiwane:
        ekstremalne = sum(1 for p in permutacje if p >= i_obs)
    else:
        ekstremalne = sum(1 for p in permutacje if p <= i_obs)
    p_globalne = (ekstremalne + 1) / (LICZBA_PERMUTACJI + 1)
    sd_perm = statistics.pstdev(permutacje)
    z_globalne = (i_obs - statistics.fmean(permutacje)) / sd_perm if sd_perm else None

    return {
        "moran_i": i_obs,
        "oczekiwane_i": oczekiwane,
        "p": p_globalne,
        "z": z_globalne,
        "permutacje": LICZBA_PERMUTACJI,
        "liczba_gmin": n,
        "pominiete": len(wartosci) - n,
        "interpretacja": _interpretacja(i_obs, oczekiwane, p_globalne),
        "lisa": _lisa(z, sasiedztwo, losowanie),
        "kategorie": KATEGORIE,
        "gi": gi_star(uzyte, sasiedztwo),
        "kategorie_gi": KATEGORIE_GI,
    }


def gi_star(wartosci: dict[str, float], sasiedztwo: dict[str, list[str]]) -> list[dict]:
    """Gi* (Ord i Getis 1995) z wagami binarnymi, gmina liczona jako swój sąsiad:

    Gi* = (Σ w_ij x_j − x̄ Σ w_ij) / (S √((n Σ w_ij² − (Σ w_ij)²) / (n − 1))),
    S = √(Σ x_j² / n − x̄²). Wynik jest z-score; p dwustronne z rozkładu normalnego.
    """
    n = len(wartosci)
    srednia = statistics.fmean(wartosci.values())
    s = math.sqrt(sum(v * v for v in wartosci.values()) / n - srednia * srednia)
    wynik = []
    for t, sasiedzi in sasiedztwo.items():
        okno = [t, *sasiedzi]
        w = len(okno)  # Σ w_ij = Σ w_ij² przy wagach 0/1
        mianownik = s * math.sqrt((n * w - w * w) / (n - 1))
        z = (sum(wartosci[j] for j in okno) - srednia * w) / mianownik if mianownik else 0.0
        p = math.erfc(abs(z) / math.sqrt(2))  # 2 × (1 − Φ(|z|))
        kategoria = next((("H" if z > 0 else "C") + str(poziom) for prog, poziom in PROGI_GI if abs(z) >= prog), "ns")
        wynik.append({"teryt": t, "z": z, "p": p, "kategoria": kategoria})
    return wynik


def _lisa(z: dict[str, float], sasiedztwo: dict[str, list[str]], losowanie: random.Random) -> list[dict]:
    """Lokalne I Morana z warunkowym testem permutacyjnym.

    Dla gminy i losujemy k_i wartości spośród pozostałych gmin (tyle, ilu
    ma sąsiadów) i sprawdzamy, jak często wychodzi równie skrajne Ii.
    """
    n = len(z)
    # Jak w PySAL (esda.Moran_Local): wariancja z dzielnikiem n − 1.
    m2 = sum(v * v for v in z.values()) / (n - 1)
    terytory = list(z)
    wynik = []
    for t in terytory:
        k = len(sasiedztwo[t])
        opoznienie = statistics.fmean(z[s] for s in sasiedztwo[t])
        i_lok = z[t] / m2 * opoznienie
        pozostale = [z[u] for u in terytory if u != t]
        ekstremalne = 0
        for _ in range(LICZBA_PERMUTACJI):
            i_perm = z[t] / m2 * statistics.fmean(losowanie.sample(pozostale, k))
            if (i_lok >= 0 and i_perm >= i_lok) or (i_lok < 0 and i_perm <= i_lok):
                ekstremalne += 1
        p = (ekstremalne + 1) / (LICZBA_PERMUTACJI + 1)
        if p >= POZIOM_ISTOTNOSCI:
            kategoria = "ns"
        else:
            kategoria = ("H" if z[t] > 0 else "L") + ("H" if opoznienie > 0 else "L")
        wynik.append({"teryt": t, "i": i_lok, "p": p, "kategoria": kategoria, "sasiedzi": k})
    return wynik


def _interpretacja(i_obs: float, oczekiwane: float, p: float) -> str:
    if p >= POZIOM_ISTOTNOSCI:
        return "Brak istotnej autokorelacji — rozkład wartości w przestrzeni nie różni się od losowego."
    if i_obs > oczekiwane:
        return "Dodatnia autokorelacja: podobne wartości skupiają się w sąsiednich gminach."
    return "Ujemna autokorelacja: sąsiednie gminy częściej się różnią, niż są podobne (układ „szachownicy”)."
