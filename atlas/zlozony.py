"""Wskaźnik złożony (syntetyczny) dla gmin województwa (ETAP 84).

Kilka wskaźników GUS o różnych jednostkach sprowadzamy do wspólnej skali
i uśredniamy z wagami — klasyczna metoda analizy regionalnej:

- unitaryzacja zerowana (domyślna): stymulanta (x − min) / (max − min),
  destymulanta (max − x) / (max − min); wynik 0–1, 1 = najlepsza gmina
  w danej składowej,
- standaryzacja: (x − średnia) / odchylenie standardowe (populacyjne —
  gminy województwa to cała populacja); destymulanta ze znakiem minus.

Wskaźnik = średnia ważona składowych.

Metoda Hellwiga (ETAP 91) — miara rozwoju względem wzorca:
1. standaryzacja jak wyżej (destymulanty ze znakiem minus, więc dla
   każdej składowej więcej = lepiej),
2. wzorzec rozwoju z_0j = najlepsza wartość składowej wśród gmin,
3. odległość gminy od wzorca d_i0 = √(Σ w_j (z_ij − z_0j)²), wagi
   przeskalowane tak, by ich suma była liczbą składowych (równe wagi =
   wersja klasyczna),
4. d_0 = średnia(d_i0) + 2·odchylenie(d_i0), miara m_i = 1 − d_i0 / d_0.
   Zwykle 0–1; im bliżej 1, tym bliżej wzorca.

Liczymy tylko dla gmin, które mają
wartości wszystkich składowych — pozostałe wymieniamy jako pominięte.
Składowa stała we wszystkich gminach (max = min) nic nie różnicuje —
zgłaszamy ją jako błąd, zamiast dzielić przez zero.
"""

import statistics

METODY = {
    "unitaryzacja": "unitaryzacja zerowana (0–1)",
    "standaryzacja": "standaryzacja (z)",
    "hellwig": "metoda Hellwiga (odległość od wzorca)",
}
MAKS_SKLADOWYCH = 12


class BladWskaznika(ValueError):
    """Złe składowe albo dane, z których nie da się policzyć wskaźnika."""


def _unormuj(wartosci: dict[str, float], kierunek: int, metoda: str, nazwa: str) -> dict[str, float]:
    liczby = list(wartosci.values())
    if metoda == "unitaryzacja":
        najmniej, najwiecej = min(liczby), max(liczby)
        if najwiecej == najmniej:
            raise BladWskaznika(f"Składowa „{nazwa}” ma tę samą wartość we wszystkich gminach — nic nie różnicuje.")
        rozstep = najwiecej - najmniej
        if kierunek > 0:
            return {t: (x - najmniej) / rozstep for t, x in wartosci.items()}
        return {t: (najwiecej - x) / rozstep for t, x in wartosci.items()}
    srednia, odchylenie = statistics.fmean(liczby), statistics.pstdev(liczby)
    if odchylenie == 0:
        raise BladWskaznika(f"Składowa „{nazwa}” ma tę samą wartość we wszystkich gminach — nic nie różnicuje.")
    return {t: kierunek * (x - srednia) / odchylenie for t, x in wartosci.items()}


def _hellwig(unormowane: list[dict], wagi: list[float], gminy: set[str]) -> dict[str, float]:
    wzorzec = [max(u.values()) for u in unormowane]
    odleglosci = {
        t: sum(w * (u[t] - z0) ** 2 for u, w, z0 in zip(unormowane, wagi, wzorzec)) ** 0.5 for t in gminy
    }
    d0 = statistics.fmean(odleglosci.values()) + 2 * statistics.pstdev(odleglosci.values())
    if d0 == 0:
        raise BladWskaznika("Wszystkie gminy są w tym samym miejscu względem wzorca — nic nie różnicuje.")
    return {t: 1 - d / d0 for t, d in odleglosci.items()}


def wskaznik_zlozony(skladowe: list[dict], metoda: str = "unitaryzacja") -> dict:
    """skladowe: [{"nazwa", "kierunek" (1 stymulanta / -1 destymulanta),
    "waga" (> 0), "gminy": [{"teryt", "nazwa", "wartosc"}]}]."""
    if metoda not in METODY:
        raise BladWskaznika("Metoda: unitaryzacja, standaryzacja albo metoda Hellwiga.")
    if not 2 <= len(skladowe) <= MAKS_SKLADOWYCH:
        raise BladWskaznika(f"Wybierz od 2 do {MAKS_SKLADOWYCH} składowych.")
    for s in skladowe:
        if s["kierunek"] not in (1, -1) or not s["waga"] > 0:
            raise BladWskaznika(f"Składowa „{s['nazwa']}”: kierunek ±1 i waga większa od zera.")

    nazwy_gmin = {g["teryt"]: g["nazwa"] for s in skladowe for g in s["gminy"]}
    wartosci = [{g["teryt"]: g["wartosc"] for g in s["gminy"]} for s in skladowe]
    wspolne = set.intersection(*(set(w) for w in wartosci))
    if len(wspolne) < 3:
        raise BladWskaznika("Za mało gmin z danymi wszystkich składowych (potrzeba co najmniej 3). Sprawdź rok.")

    normalizacja = "standaryzacja" if metoda == "hellwig" else metoda
    unormowane = [
        _unormuj({t: w[t] for t in wspolne}, s["kierunek"], normalizacja, s["nazwa"]) for s, w in zip(skladowe, wartosci)
    ]
    suma_wag = sum(s["waga"] for s in skladowe)
    wyniki = (
        _hellwig(unormowane, [s["waga"] * len(skladowe) / suma_wag for s in skladowe], wspolne)
        if metoda == "hellwig"
        else {t: sum(s["waga"] * u[t] for s, u in zip(skladowe, unormowane)) / suma_wag for t in wspolne}
    )
    gminy = []
    for t in wspolne:
        wynik = wyniki[t]
        gminy.append({
            "teryt": t,
            "nazwa": nazwy_gmin[t],
            "wartosc": round(wynik, 4),
            "skladowe": [round(u[t], 4) for u in unormowane],
            "surowe": [w[t] for w in wartosci],
        })
    gminy.sort(key=lambda g: (-g["wartosc"], g["nazwa"]))
    for miejsce, g in enumerate(gminy, start=1):
        g["miejsce"] = miejsce
    pominiete = sorted(nazwy_gmin[t] for t in set(nazwy_gmin) - wspolne)
    return {"metoda": metoda, "gminy": gminy, "pominiete": pominiete}
