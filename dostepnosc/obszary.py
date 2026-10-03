"""Wyniki dostępności w narysowanych obszarach — dzielnicach, osiedlach (ETAP 163).

Komórka H3 należy do obszaru, gdy jej środek leży w wieloboku. Dla czasu
dojścia: średni czas (ważony liczbą mieszkańców, gdy plik ją ma), mediana
i udział w zasięgu 15 minut; dla innych wskaźników — średnia i mediana.
Obszary nie są zapisywane na serwerze — przysyła je przeglądarka.
"""

import statistics

import h3
import shapely
from shapely.geometry import shape

from .wyniki import PROG_MIASTA_15, BladWynikow, czy_minuty, wartosci_wskaznika

MAKS_OBSZAROW = 8


def _wielobok(geometria):
    try:
        g = shape(geometria)
    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
        raise BladWynikow("Obszar musi być wielobokiem GeoJSON.") from None
    if g.geom_type not in ("Polygon", "MultiPolygon") or g.is_empty:
        raise BladWynikow("Obszar musi być wielobokiem.")
    return g if g.is_valid else g.buffer(0)


def _statystyki(wartosci: list[float], ludnosc: list[float | None], minuty: bool) -> dict:
    wynik = {"komorek": len(wartosci)}
    if not wartosci:
        return wynik
    wynik["mediana"] = statistics.median(wartosci)
    ma_ludnosc = all(l is not None for l in ludnosc) and sum(ludnosc) > 0
    if ma_ludnosc:
        suma = sum(ludnosc)
        wynik["mieszkancy"] = suma
        wynik["srednia"] = sum(w * l for w, l in zip(wartosci, ludnosc)) / suma
    else:
        wynik["srednia"] = statistics.fmean(wartosci)
    if minuty:
        if ma_ludnosc:
            wynik["w_zasiegu_proc"] = 100 * sum(l for w, l in zip(wartosci, ludnosc) if w <= PROG_MIASTA_15) / sum(ludnosc)
        else:
            wynik["w_zasiegu_proc"] = 100 * sum(1 for w in wartosci if w <= PROG_MIASTA_15) / len(wartosci)
    wynik["wazona_ludnoscia"] = ma_ludnosc
    return wynik


def w_obszarach(wyniki: dict, kolumna: str, obszary: list[dict]) -> dict:
    """{"obszary": [{nazwa, …statystyki}], "calosc": {…}, "minuty", "prog"}."""
    if not isinstance(obszary, list) or not 1 <= len(obszary) <= MAKS_OBSZAROW:
        raise BladWynikow(f"Podaj od 1 do {MAKS_OBSZAROW} obszarów.")
    wartosci = wartosci_wskaznika(wyniki, kolumna)
    ludnosc = wyniki.get("ludnosc") or [None] * len(wyniki["komorki"])
    srodki = [h3.cell_to_latlng(k) for k in wyniki["komorki"]]
    lat = [s[0] for s in srodki]
    lng = [s[1] for s in srodki]
    minuty = czy_minuty(kolumna)
    z_wartoscia = [i for i, w in enumerate(wartosci) if w is not None]
    wynik = []
    for o in obszary:
        nazwa = " ".join(str((o or {}).get("nazwa") or "").split())[:60] or "obszar"
        g = _wielobok((o or {}).get("geometria"))
        w_srodku = shapely.contains_xy(g, lng, lat)
        indeksy = [i for i in z_wartoscia if w_srodku[i]]
        wynik.append({"nazwa": nazwa, **_statystyki([wartosci[i] for i in indeksy], [ludnosc[i] for i in indeksy], minuty)})
    calosc = _statystyki([wartosci[i] for i in z_wartoscia], [ludnosc[i] for i in z_wartoscia], minuty)
    return {"obszary": wynik, "calosc": calosc, "minuty": minuty, "prog": PROG_MIASTA_15}


def _zmiana(przed: dict, po: dict) -> dict:
    wynik = {"przed": przed, "po": po}
    for klucz in ("srednia", "mediana", "w_zasiegu_proc"):
        if klucz in przed and klucz in po:
            wynik[f"zmiana_{klucz}"] = po[klucz] - przed[klucz]
    return wynik


def porownanie_w_obszarach(przed: dict, po: dict, kolumna: str, obszary: list[dict]) -> dict:
    """ETAP 184: te same obszary w dwóch scenariuszach (np. przed i po nowej
    szkole) — statystyki obu plików i zmiana (po − przed; ujemna zmiana
    czasu = poprawa, zmiana udziału w zasięgu w punktach procentowych)."""
    a, b = w_obszarach(przed, kolumna, obszary), w_obszarach(po, kolumna, obszary)
    return {"porownanie": True, "minuty": a["minuty"], "prog": a["prog"],
            "obszary": [{"nazwa": x["nazwa"], **_zmiana(x, y)} for x, y in zip(a["obszary"], b["obszary"])],
            "calosc": _zmiana(a["calosc"], b["calosc"])}
