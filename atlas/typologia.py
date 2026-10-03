"""Typologia gmin metodą k-średnich (ETAP 124).

Gminy województwa dzielimy na k typów o podobnym profilu kilku
wskaźników GUS — klasyczna metoda delimitacji w analizie regionalnej:

1. standaryzacja każdego wskaźnika (z = (x − średnia) / odchylenie
   populacyjne), żeby wskaźniki o różnych jednostkach ważyły tyle samo;
2. k-średnich (algorytm Lloyda): każda gmina trafia do najbliższego
   środka (odległość euklidesowa w przestrzeni z), środki przeliczamy jako
   średnie, do ustabilizowania się podziału;
3. start deterministyczny (bez losowania): pierwszy środek — gmina
   najbliższa średniej województwa, kolejne — gmina najdalsza od już
   wybranych (maximin). Ten sam zestaw danych daje zawsze ten sam podział.

Typy numerujemy od najliczniejszego. Opis typu powstaje z profilu: średnie
z ≥ 0,5 to „wysoki …”, ≤ −0,5 to „niski …” — słowa z liczb, bez modelu
językowego. Jakość podziału: średni wskaźnik sylwetki (−1…1; powyżej
ok. 0,5 typy wyraźnie oddzielone, poniżej 0,25 podział słaby).
"""

import math
import statistics

MIN_K, MAKS_K = 2, 8
PROG_OPISU = 0.5
MAKS_ITERACJI = 200


class BladTypologii(ValueError):
    """Złe składowe albo dane, z których nie da się zbudować typologii."""


def _odleglosc(a: list[float], b: list[float]) -> float:
    return math.dist(a, b)


def _start(punkty: list[list[float]], k: int) -> list[list[float]]:
    """Środki startowe: najbliższy średniej, potem kolejno najdalszy od wybranych."""
    srednia = [statistics.fmean(kol) for kol in zip(*punkty)]
    wybrane = [min(range(len(punkty)), key=lambda i: (_odleglosc(punkty[i], srednia), i))]
    while len(wybrane) < k:
        wybrane.append(max(range(len(punkty)), key=lambda i: (min(_odleglosc(punkty[i], punkty[j]) for j in wybrane), -i)))
    return [list(punkty[i]) for i in wybrane]


def k_srednich(punkty: list[list[float]], k: int) -> list[int]:
    """Przypisanie punktów do k skupień (numery 0…k−1)."""
    srodki = _start(punkty, k)
    przypisanie = None
    for _ in range(MAKS_ITERACJI):
        nowe = [min(range(k), key=lambda c: (_odleglosc(p, srodki[c]), c)) for p in punkty]
        if nowe == przypisanie:
            break
        przypisanie = nowe
        for c in range(k):
            czlonkowie = [p for p, n in zip(punkty, przypisanie) if n == c]
            if not czlonkowie:  # puste skupienie: przejmuje punkt najdalszy od swojego środka
                najdalszy = max(range(len(punkty)), key=lambda i: _odleglosc(punkty[i], srodki[przypisanie[i]]))
                przypisanie[najdalszy] = c
                czlonkowie = [punkty[najdalszy]]
            srodki[c] = [statistics.fmean(kol) for kol in zip(*czlonkowie)]
    return przypisanie


def sylwetka(punkty: list[list[float]], przypisanie: list[int]) -> float | None:
    """Średni wskaźnik sylwetki; None, gdy jest jedno skupienie."""
    if len(set(przypisanie)) < 2:
        return None
    wartosci = []
    for i, p in enumerate(punkty):
        odleglosci: dict[int, list[float]] = {}
        for j, q in enumerate(punkty):
            if i != j:
                odleglosci.setdefault(przypisanie[j], []).append(_odleglosc(p, q))
        wlasne = odleglosci.get(przypisanie[i])
        if not wlasne:
            wartosci.append(0.0)  # jedyny członek skupienia — sylwetka 0 (konwencja)
            continue
        a = statistics.fmean(wlasne)
        b = min(statistics.fmean(v) for c, v in odleglosci.items() if c != przypisanie[i])
        wartosci.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return statistics.fmean(wartosci)


def _dane(skladowe: list[dict]) -> tuple[dict, list[dict], list[str], list[list[float]]]:
    """→ (nazwy gmin, wartości surowe, gminy z kompletem danych, punkty z)."""
    if not 2 <= len(skladowe) <= 12:
        raise BladTypologii("Wybierz od 2 do 12 wskaźników.")
    nazwy_gmin = {g["teryt"]: g["nazwa"] for s in skladowe for g in s["gminy"]}
    wartosci = [{g["teryt"]: g["wartosc"] for g in s["gminy"]} for s in skladowe]
    wspolne = sorted(set.intersection(*(set(w) for w in wartosci)))
    z = []
    for s, w in zip(skladowe, wartosci):
        liczby = [w[t] for t in wspolne]
        if len(liczby) < 2:
            break  # komunikat o liczbie gmin niżej
        srednia, odchylenie = statistics.fmean(liczby), statistics.pstdev(liczby)
        if odchylenie == 0:
            raise BladTypologii(f"Wskaźnik „{s['nazwa']}” ma tę samą wartość we wszystkich gminach — nic nie różnicuje.")
        z.append([(x - srednia) / odchylenie for x in liczby])
    return nazwy_gmin, wartosci, wspolne, [list(p) for p in zip(*z)]


MAKS_PODOBNYCH = 10


def podobne(skladowe: list[dict], teryt: str, ile: int = MAKS_PODOBNYCH) -> dict:
    """ETAP 177: gminy najbardziej podobne do wybranej — najmniejsza
    odległość euklidesowa w przestrzeni z (te same standaryzowane wskaźniki
    co typologia). Przy każdej: wskaźnik, którym różni się najbardziej."""
    nazwy_gmin, wartosci, wspolne, punkty = _dane(skladowe)
    if teryt not in wspolne:
        raise BladTypologii("Wybrana gmina nie ma danych wszystkich wskaźników w tym roku.")
    i0 = wspolne.index(teryt)
    wynik = []
    for i, t in enumerate(wspolne):
        if i == i0:
            continue
        roznice = [b - a for a, b in zip(punkty[i0], punkty[i])]
        j = max(range(len(roznice)), key=lambda n: abs(roznice[n]))
        wynik.append({"teryt": t, "nazwa": nazwy_gmin[t], "odleglosc": round(_odleglosc(punkty[i0], punkty[i]), 3),
                      "surowe": [w[t] for w in wartosci],
                      "najwieksza_roznica": {"wskaznik": skladowe[j]["nazwa"], "z": round(roznice[j], 2)}})
    wynik.sort(key=lambda g: (g["odleglosc"], g["nazwa"]))
    return {"gmina": {"teryt": teryt, "nazwa": nazwy_gmin[teryt], "surowe": [w[teryt] for w in wartosci]},
            "podobne": wynik[:ile], "liczba_gmin": len(wspolne)}


def sylwetki(skladowe: list[dict]) -> list[dict]:
    """ETAP 125: średnia sylwetka dla k = 2…8 (o ile gmin wystarcza) — pomoc w wyborze liczby typów."""
    _, _, wspolne, punkty = _dane(skladowe)
    wynik = []
    for k in range(MIN_K, min(MAKS_K, len(wspolne) // 2) + 1):
        wynik.append({"k": k, "sylwetka": sylwetka(punkty, k_srednich(punkty, k))})
    if not wynik:
        raise BladTypologii(f"Za mało gmin z danymi wszystkich wskaźników ({len(wspolne)}).")
    najlepsza = max(wynik, key=lambda w: (w["sylwetka"] or -2, -w["k"]))
    for w in wynik:
        w["najlepsza"] = w is najlepsza
    return wynik


def typologia(skladowe: list[dict], k: int) -> dict:
    """skladowe: [{"nazwa", "gminy": [{"teryt", "nazwa", "wartosc"}]}] → typy i gminy."""
    if not MIN_K <= k <= MAKS_K:
        raise BladTypologii(f"Liczba typów od {MIN_K} do {MAKS_K}.")
    nazwy_gmin, wartosci, wspolne, punkty = _dane(skladowe)
    if len(wspolne) < 2 * k:
        raise BladTypologii(f"Za mało gmin z danymi wszystkich wskaźników ({len(wspolne)}) na {k} typy — potrzeba co najmniej {2 * k}.")
    przypisanie = k_srednich(punkty, k)
    # typy od najliczniejszego (przy remisie — kolejność skupień)
    licznosc = {c: przypisanie.count(c) for c in set(przypisanie)}
    kolejnosc = sorted(licznosc, key=lambda c: (-licznosc[c], c))
    numer = {c: i + 1 for i, c in enumerate(kolejnosc)}
    typy = []
    for c in kolejnosc:
        indeksy = [i for i, n in enumerate(przypisanie) if n == c]
        profil = [statistics.fmean(punkty[i][j] for i in indeksy) for j in range(len(skladowe))]
        srednie = [statistics.fmean(wartosci[j][wspolne[i]] for i in indeksy) for j in range(len(skladowe))]
        cechy = [("wysoki" if p >= PROG_OPISU else "niski") + f": {s['nazwa']}" for p, s in zip(profil, skladowe) if abs(p) >= PROG_OPISU]
        typy.append({"nr": numer[c], "liczba": len(indeksy), "profil_z": [round(p, 3) for p in profil],
                     "srednie": srednie, "opis": "; ".join(cechy) if cechy else "profil bliski średniej województwa"})
    gminy = sorted(
        ({"teryt": t, "nazwa": nazwy_gmin[t], "typ": numer[przypisanie[i]], "z": [round(v, 3) for v in punkty[i]],
          "surowe": [w[t] for w in wartosci]} for i, t in enumerate(wspolne)),
        key=lambda g: (g["typ"], g["nazwa"]),
    )
    return {"k": k, "typy": typy, "gminy": gminy, "sylwetka": sylwetka(punkty, przypisanie),
            "pominiete": sorted(nazwy_gmin[t] for t in set(nazwy_gmin) - set(wspolne))}
