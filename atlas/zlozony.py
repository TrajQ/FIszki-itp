"""Wskaźnik złożony (syntetyczny) dla gmin województwa (ETAP 84).

Kilka wskaźników GUS o różnych jednostkach sprowadzamy do wspólnej skali
i uśredniamy z wagami — klasyczna metoda analizy regionalnej:

- unitaryzacja zerowana (domyślna): stymulanta (x − min) / (max − min),
  destymulanta (max − x) / (max − min); wynik 0–1, 1 = najlepsza gmina
  w danej składowej,
- standaryzacja: (x − średnia) / odchylenie standardowe (populacyjne —
  gminy województwa to cała populacja); destymulanta ze znakiem minus.

Wskaźnik = średnia ważona składowych. Liczymy tylko dla gmin, które mają
wartości wszystkich składowych — pozostałe wymieniamy jako pominięte.
Składowa stała we wszystkich gminach (max = min) nic nie różnicuje —
zgłaszamy ją jako błąd, zamiast dzielić przez zero.
"""

import statistics

METODY = {"unitaryzacja": "unitaryzacja zerowana (0–1)", "standaryzacja": "standaryzacja (z)"}
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


def wskaznik_zlozony(skladowe: list[dict], metoda: str = "unitaryzacja") -> dict:
    """skladowe: [{"nazwa", "kierunek" (1 stymulanta / -1 destymulanta),
    "waga" (> 0), "gminy": [{"teryt", "nazwa", "wartosc"}]}]."""
    if metoda not in METODY:
        raise BladWskaznika("Metoda: unitaryzacja albo standaryzacja.")
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

    unormowane = [
        _unormuj({t: w[t] for t in wspolne}, s["kierunek"], metoda, s["nazwa"]) for s, w in zip(skladowe, wartosci)
    ]
    suma_wag = sum(s["waga"] for s in skladowe)
    gminy = []
    for t in wspolne:
        wynik = sum(s["waga"] * u[t] for s, u in zip(skladowe, unormowane)) / suma_wag
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
