"""Porównanie dwóch inwentaryzacji (ETAP 157).

Typowo ten sam formularz w dwóch terminach („Utwórz podobny”, ETAP 134).
Dwie części:

1. Zestawienie obok siebie dla pól, które oba projekty mają (ta sama
   nazwa i typ): rozkłady w % i zmiana w punktach procentowych, dla liczb
   średnia i mediana.
2. Te same miejsca: punkt z drugiego projektu łączymy z najbliższym
   punktem pierwszego, jeśli są od siebie najwyżej PROG_M metrów i są dla
   siebie nawzajem najbliższe (bez łączenia jednego punktu z dwoma). Dla
   pól na skali (od najlepszej do najgorszej opcji) liczymy, gdzie jest
   lepiej, gdzie gorzej.
"""

import math

from .raport import zestawienie

PROG_M = 15  # GPS telefonu ma typowo ±5–10 m
R_ZIEMI = 6371008.8


def odleglosc_m(a: dict, b: dict) -> float:
    """Odległość po kuli (haversine) — w terenie wystarcza."""
    f1, f2 = math.radians(a["lat"]), math.radians(b["lat"])
    df, dl = f2 - f1, math.radians(b["lng"] - a["lng"])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * R_ZIEMI * math.asin(math.sqrt(h))


def wspolne_pola(pola_a: list[dict], pola_b: list[dict]) -> list[dict]:
    typy_b = {p["nazwa"]: p for p in pola_b}
    return [p for p in pola_a if p["nazwa"] in typy_b and typy_b[p["nazwa"]]["typ"] == p["typ"]]


def zestawienie_obok(pola: list[dict], punkty_a: list[dict], punkty_b: list[dict]) -> list[dict]:
    """Pozycje zestawienia A i B dla wspólnych pól + zmiany."""
    za, zb = zestawienie(pola, punkty_a), zestawienie(pola, punkty_b)
    wynik = []
    for a, b in zip(za, zb):
        pozycja = {"nazwa": a["nazwa"], "typ": a["typ"], "a": a, "b": b}
        if "rozklad" in a:
            pozycja["wiersze"] = [{"wartosc": ra["wartosc"], "a": ra, "b": rb, "zmiana_pp": rb["procent"] - ra["procent"]}
                                  for ra, rb in zip(a["rozklad"], b["rozklad"])]
        elif "statystyki" in a and "statystyki" in b:
            pozycja["zmiana_sredniej"] = b["statystyki"]["srednia"] - a["statystyki"]["srednia"]
        wynik.append(pozycja)
    return wynik


def pary(punkty_a: list[dict], punkty_b: list[dict], prog_m: float = PROG_M) -> list[tuple[dict, dict, float]]:
    """Wzajemnie najbliższe punkty A i B w promieniu prog_m (z położeniem)."""
    a = [p for p in punkty_a if p.get("lat") is not None]
    b = [p for p in punkty_b if p.get("lat") is not None]
    if not a or not b:
        return []
    najblizszy_a = {id(pb): min(a, key=lambda pa: odleglosc_m(pa, pb)) for pb in b}
    najblizszy_b = {id(pa): min(b, key=lambda pb: odleglosc_m(pa, pb)) for pa in a}
    wynik = []
    for pb in b:
        pa = najblizszy_a[id(pb)]
        d = odleglosc_m(pa, pb)
        if d <= prog_m and najblizszy_b[id(pa)] is pb:
            wynik.append((pa, pb, d))
    return wynik


def zmiany_w_miejscach(pola: list[dict], polaczone: list[tuple[dict, dict, float]]) -> list[dict]:
    """Dla pól na skali: w ilu tych samych miejscach lepiej / gorzej / bez zmian."""
    wynik = []
    for pole in pola:
        if pole["typ"] != "wybor" or not pole.get("skala"):
            continue
        opcje = pole["opcje"]  # od najlepszej do najgorszej
        lepiej, gorzej, bez_zmian = [], [], 0
        for pa, pb, _ in polaczone:
            wa, wb = pa["wartosci"].get(pole["nazwa"]), pb["wartosci"].get(pole["nazwa"])
            if wa not in opcje or wb not in opcje:
                continue
            roznica = opcje.index(wb) - opcje.index(wa)
            if roznica < 0:
                lepiej.append({"a": pa["nr"], "b": pb["nr"], "z": wa, "na": wb})
            elif roznica > 0:
                gorzej.append({"a": pa["nr"], "b": pb["nr"], "z": wa, "na": wb})
            else:
                bez_zmian += 1
        wynik.append({"nazwa": pole["nazwa"], "lepiej": lepiej, "gorzej": gorzej, "bez_zmian": bez_zmian})
    return wynik
