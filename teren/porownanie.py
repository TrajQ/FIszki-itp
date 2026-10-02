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
import statistics

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


def _siatka(punkty: list[dict], bok_m: float) -> tuple[dict, callable]:
    """Punkty w komórkach ok. bok_m × bok_m (indeks do szukania sąsiadów)."""
    stopien_szer = bok_m / 111_320
    stopien_dl = bok_m / (111_320 * max(0.1, math.cos(math.radians(statistics.fmean(p["lat"] for p in punkty)))))
    def komorka(p):
        return int(p["lat"] // stopien_szer), int(p["lng"] // stopien_dl)
    komorki: dict = {}
    for p in punkty:
        komorki.setdefault(komorka(p), []).append(p)
    return komorki, komorka


def _najblizszy(p: dict, komorki: dict, komorka, prog_m: float):
    """Najbliższy punkt z siatki w promieniu prog_m (albo None) — sąsiednie komórki wystarczą."""
    w, k = komorka(p)
    kandydaci = [q for dw in (-1, 0, 1) for dk in (-1, 0, 1) for q in komorki.get((w + dw, k + dk), ())]
    najlepszy = min(kandydaci, key=lambda q: odleglosc_m(p, q), default=None)
    return najlepszy if najlepszy is not None and odleglosc_m(p, najlepszy) <= prog_m else None


def pary(punkty_a: list[dict], punkty_b: list[dict], prog_m: float = PROG_M) -> list[tuple[dict, dict, float]]:
    """Wzajemnie najbliższe punkty A i B w promieniu prog_m (z położeniem).
    Para musi leżeć w promieniu prog_m, więc najbliższego szukamy tylko w
    sąsiednich komórkach siatki o boku prog_m (ETAP 160) — ten sam wynik co
    porównanie każdego z każdym, ale w czasie liniowym."""
    a = [p for p in punkty_a if p.get("lat") is not None]
    b = [p for p in punkty_b if p.get("lat") is not None]
    if not a or not b:
        return []
    siatka_a, komorka_a = _siatka(a, prog_m)
    siatka_b, komorka_b = _siatka(b, prog_m)
    wynik = []
    for pb in b:
        pa = _najblizszy(pb, siatka_a, komorka_a, prog_m)
        if pa is not None and _najblizszy(pa, siatka_b, komorka_b, prog_m) is pb:
            wynik.append((pa, pb, odleglosc_m(pa, pb)))
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
