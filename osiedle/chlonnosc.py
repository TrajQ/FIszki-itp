"""Chłonność terenu według wpisanych ustaleń planu (ETAP 197).

Ile powierzchni całkowitej (i ile mieszkań) plan pozwala zmieścić na
obszarze — wobec tego, co narysowano w koncepcji. Liczy się z tych samych
ustaleń, które sprawdza zgodność (wskazniki.py), i od tej samej podstawy
(obszar opracowania, a bez niego suma terenów):

- z intensywności: podstawa × max intensywność,
- z wysokości: podstawa × max wskaźnik zabudowy × max kondygnacje
  (gdy wpisano oba),
- chłonność = mniejsza z dostępnych wartości (ona ogranicza),
- minimum = podstawa × min intensywność (gdy wpisano).

Mieszkania przelicza się jak w programie (program.py): powierzchnia
całkowita × udział mieszkań / średnie mieszkanie MW — to szacunek górny
dla zabudowy wielorodzinnej, nie liczba z planu.
"""

from .program import _w_dol


def chlonnosc(wskazniki: dict | None, wskazniki_budynkow: dict | None, plan: dict, podstawa_m2: float | None, program: dict | None) -> dict | None:
    """Chłonność i wykorzystanie; None, gdy plan nie ogranicza powierzchni całkowitej."""
    if not wskazniki or not podstawa_m2:
        return None
    ograniczenia = []
    if "max_intensywnosc" in plan:
        ograniczenia.append({"z": "intensywność zabudowy", "calkowita_m2": podstawa_m2 * plan["max_intensywnosc"]})
    if "max_zabudowa_proc" in plan and "max_kondygnacje" in plan:
        ograniczenia.append({"z": "wskaźnik zabudowy × kondygnacje",
                             "calkowita_m2": podstawa_m2 * plan["max_zabudowa_proc"] / 100 * plan["max_kondygnacje"]})
    if not ograniczenia:
        return None
    for o in ograniczenia:
        o["calkowita_m2"] = round(o["calkowita_m2"], 1)
    decyduje = min(ograniczenia, key=lambda o: o["calkowita_m2"])
    maks = decyduje["calkowita_m2"]
    obecna = wskazniki["powierzchnia_calkowita_m2"]
    z = (program or {}).get("zalozenia")
    na_mieszkanie = z["metraz_mw_m2"] / (z["udzial_mieszkan_proc"] / 100) if z else None  # m² pow. całkowitej na mieszkanie MW

    def mieszkania(m2):
        return _w_dol(m2 / na_mieszkanie) if na_mieszkanie and m2 > 0 else 0

    wynik = {
        "ograniczenia": ograniczenia,
        "decyduje": decyduje["z"],
        "maks_calkowita_m2": maks,
        "min_calkowita_m2": round(podstawa_m2 * plan["min_intensywnosc"], 1) if "min_intensywnosc" in plan else None,
        "calkowita_m2": obecna,
        "wykorzystanie_proc": round(100 * obecna / maks, 1) if maks else None,
        "zapas_m2": round(maks - obecna, 1),
        "maks_mieszkan": mieszkania(maks),
        "zapas_mieszkan": mieszkania(maks - obecna),
    }
    if wskazniki_budynkow:
        wynik["calkowita_budynkow_m2"] = wskazniki_budynkow["powierzchnia_calkowita_m2"]
        wynik["wykorzystanie_budynkow_proc"] = round(100 * wynik["calkowita_budynkow_m2"] / maks, 1) if maks else None
    return wynik

