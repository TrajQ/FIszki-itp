"""Raport gminy: jeden wskaźnik na tle województwa i w czasie (ETAP 63).

Dla każdego wskaźnika z zestawu raportu liczymy:
- ostatni rok z danymi dla gminy i wartość,
- zmianę w ostatnich LAT_WSTECZ latach (albo od najstarszego roku, jeśli
  szereg jest krótszy),
- miejsce gminy w województwie w tym samym roku (1 = najwyższa wartość),
  liczbę gmin z danymi i medianę województwa.

Prognoza (ETAP 92) to ekstrapolacja trendu liniowego z ostatnich lat
(metoda najmniejszych kwadratów) — „co będzie, jeśli dotychczasowa zmiana
się utrzyma”, a nie prognoza demograficzna GUS (ta uwzględnia urodzenia,
zgony i migracje według wieku). Pokazujemy ją z R² — przy słabym
dopasowaniu trend jest niestabilny i ekstrapolacja mało znaczy.

Wszystkie liczby liczy kod z danych BDL; model językowy dostaje je jako
fakty i tylko opisuje (sprawdzanie liczb — dane/gemini.py).
"""

import statistics

from .statystyki import format_liczby

LAT_WSTECZ = 10
LAT_PROGNOZY = 5
MIN_PUNKTOW_TRENDU = 5
R2_STABILNY = 0.7


def prognoza_trendu(szereg: list[dict], lat_naprzod: int = LAT_PROGNOZY) -> dict | None:
    """Trend liniowy z ostatnich LAT_WSTECZ lat szeregu i wartość za lat_naprzod lat."""
    if not szereg:
        return None
    od_roku = szereg[-1]["rok"] - LAT_WSTECZ
    punkty = [p for p in szereg if p["rok"] >= od_roku]
    if len(punkty) < MIN_PUNKTOW_TRENDU:
        return None
    lata = [p["rok"] for p in punkty]
    wartosci = [p["wartosc"] for p in punkty]
    sr_r, sr_w = statistics.fmean(lata), statistics.fmean(wartosci)
    sxx = sum((r - sr_r) ** 2 for r in lata)
    nachylenie = sum((r - sr_r) * (w - sr_w) for r, w in zip(lata, wartosci)) / sxx
    wyraz = sr_w - nachylenie * sr_r
    ss_tot = sum((w - sr_w) ** 2 for w in wartosci)
    ss_res = sum((w - (wyraz + nachylenie * r)) ** 2 for r, w in zip(lata, wartosci))
    r2 = 1.0 if ss_tot == 0 else 1 - ss_res / ss_tot
    rok = szereg[-1]["rok"] + lat_naprzod
    return {
        "od": lata[0],
        "do": lata[-1],
        "rok": rok,
        "wartosc": wyraz + nachylenie * rok,
        "zmiana_roczna": nachylenie,
        "r2": r2,
        "stabilny": r2 >= R2_STABILNY,
    }


def podsumuj(szereg: list[dict], gminy_w_roku: list[dict], gmina_bdl_id: str) -> dict | None:
    """szereg: [{"rok", "wartosc"}] gminy rosnąco; gminy_w_roku: wartości
    wszystkich gmin województwa w ostatnim roku szeregu. None = brak danych."""
    if not szereg:
        return None
    ostatni = szereg[-1]
    od_roku = ostatni["rok"] - LAT_WSTECZ
    bazowy = next((p for p in szereg if p["rok"] >= od_roku), szereg[0])
    zmiana = None
    if bazowy["rok"] < ostatni["rok"]:
        roznica = ostatni["wartosc"] - bazowy["wartosc"]
        zmiana = {
            "od": bazowy["rok"],
            "wartosc_od": bazowy["wartosc"],
            "zmiana": roznica,
            "zmiana_proc": None if bazowy["wartosc"] == 0 else roznica / abs(bazowy["wartosc"]) * 100,
        }

    wartosci = [g["wartosc"] for g in gminy_w_roku]
    pozycja = None
    if any(g["bdl_id"] == gmina_bdl_id for g in gminy_w_roku):
        # miejsce = 1 + liczba gmin z wyższą wartością (remisy dzielą miejsce)
        pozycja = 1 + sum(1 for w in wartosci if w > ostatni["wartosc"])
    return {
        "rok": ostatni["rok"],
        "wartosc": ostatni["wartosc"],
        "zmiana": zmiana,
        "pozycja": pozycja,
        "liczba_gmin": len(wartosci),
        "mediana_wojewodztwa": statistics.median(wartosci) if wartosci else None,
        "szereg": szereg,
        "prognoza": prognoza_trendu(szereg),
    }


def _procent(x: float) -> str:
    return format_liczby(x) + "%"


def fakty_raportu(nazwa_gminy: str, wojewodztwo: str, pozycje: list[dict]) -> list[str]:
    """Zdania-fakty do opisu przez Gemini. pozycje: [{"nazwa", "jednostka", "podsumowanie"}]."""
    fakty = [f"Gmina: {nazwa_gminy}, województwo {wojewodztwo}."]
    for p in pozycje:
        s = p["podsumowanie"]
        if s is None:
            continue
        jednostka = f" {p['jednostka']}" if p["jednostka"] else ""
        zdanie = f"{p['nazwa']}: {format_liczby(s['wartosc'])}{jednostka} w {s['rok']} r."
        if s["zmiana"] is not None:
            zdanie += f" W {s['zmiana']['od']} r. było {format_liczby(s['zmiana']['wartosc_od'])}{jednostka}"
            if s["zmiana"]["zmiana_proc"] is not None:
                zdanie += f", zmiana o {_procent(s['zmiana']['zmiana_proc'])}"
            zdanie += "."
        if s["pozycja"] is not None:
            zdanie += (
                f" Miejsce {s['pozycja']} na {s['liczba_gmin']} gmin województwa"
                f" (mediana województwa: {format_liczby(s['mediana_wojewodztwa'])}{jednostka})."
            )
        fakty.append(zdanie)
    return fakty
