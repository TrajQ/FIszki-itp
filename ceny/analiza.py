"""Ceny mieszkań w miastach — obliczenia na danych GUS (ETAP 103).

Wszystkie liczby liczy kod z szeregów BDL (bez modelu językowego):
- zmiana rok do roku, w 5 lat i od najstarszego roku (w % i w zł),
- średnie roczne tempo zmian (CAGR) od najstarszego roku,
- miejsce powiatu w województwie i mediana województwa w danym roku.

Miasto na prawach powiatu rozpoznajemy po kodzie TERYT powiatu: w
każdym województwie powiaty grodzkie mają numery od 61 w górę.
"""

import statistics

LAT_WSTECZ = 5


def miasto_na_prawach_powiatu(teryt_powiatu: str) -> bool:
    """TERYT 4-znakowy (woj + powiat); powiaty grodzkie mają numer ≥ 61."""
    return len(teryt_powiatu) == 4 and teryt_powiatu[2:].isdigit() and int(teryt_powiatu[2:]) >= 61


def _zmiana(od: dict | None, do: dict) -> dict | None:
    if od is None or od["rok"] >= do["rok"]:
        return None
    roznica = do["wartosc"] - od["wartosc"]
    return {
        "od": od["rok"],
        "wartosc_od": od["wartosc"],
        "zmiana": roznica,
        "zmiana_proc": None if od["wartosc"] == 0 else 100 * roznica / abs(od["wartosc"]),
    }


def podsumuj(szereg: list[dict]) -> dict | None:
    """szereg: [{"rok", "wartosc"}] rosnąco. None = brak danych."""
    if not szereg:
        return None
    ostatni = szereg[-1]
    po_roku = {p["rok"]: p for p in szereg}
    pierwszy = szereg[0]
    cagr = None
    lata = ostatni["rok"] - pierwszy["rok"]
    if lata > 0 and pierwszy["wartosc"] > 0 and ostatni["wartosc"] > 0:
        cagr = 100 * ((ostatni["wartosc"] / pierwszy["wartosc"]) ** (1 / lata) - 1)
    return {
        "rok": ostatni["rok"],
        "wartosc": ostatni["wartosc"],
        "rok_do_roku": _zmiana(po_roku.get(ostatni["rok"] - 1), ostatni),
        "w_5_lat": _zmiana(po_roku.get(ostatni["rok"] - LAT_WSTECZ), ostatni),
        "od_poczatku": _zmiana(pierwszy, ostatni),
        "srednio_rocznie_proc": cagr,
    }


def ranking(wartosci: list[dict]) -> dict:
    """wartosci: [{"bdl_id", "teryt", "nazwa", "wartosc"}] powiatów województwa
    → pozycje od najdroższego, z miejscem (remisy dzielą miejsce) i medianą."""
    liczby = [w["wartosc"] for w in wartosci]
    pozycje = [
        {**w, "miejsce": 1 + sum(1 for x in liczby if x > w["wartosc"]), "miasto": miasto_na_prawach_powiatu(w["teryt"])}
        for w in sorted(wartosci, key=lambda w: (-w["wartosc"], w["nazwa"]))
    ]
    return {"pozycje": pozycje, "mediana": statistics.median(liczby) if liczby else None, "liczba": len(liczby)}
