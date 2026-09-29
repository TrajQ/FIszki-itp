"""Program osiedla: mieszkania, mieszkańcy, parkingi, miejsca w przedszkolu
i szkole (ETAP 59).

Wszystko wynika z powierzchni całkowitej terenów zabudowy (wskazniki.py)
i z założeń, które użytkownik widzi i może zmienić w panelu. Założenia
domyślne to typowe wartości do szkicu koncepcji, nie normy — każdą
trzeba sprawdzić z planem miejscowym i danymi gminy:

- mieszkania = powierzchnia całkowita × udział powierzchni mieszkań
  / średnia powierzchnia mieszkania (osobno MN i MW),
- mieszkańcy = mieszkania × osoby na mieszkanie,
- miejsca postojowe = mieszkania × wskaźnik + powierzchnia całkowita U
  / 1000 × wskaźnik; miejsca na terenach KS = pole KS / m² na miejsce,
- dzieci = mieszkańcy × udział dzieci w wieku przedszkolnym / szkolnym,
  oddziały = dzieci / liczebność oddziału (w górę).
"""

import math

# klucz → (opis, wartość domyślna, jednostka, najmniejsza, największa)
ZALOZENIA = {
    "udzial_mieszkan_proc": ("powierzchnia mieszkań w powierzchni całkowitej", 70, "%", 1, 100),
    "metraz_mw_m2": ("średnie mieszkanie MW", 55, "m²", 10, 500),
    "metraz_mn_m2": ("średni dom MN", 120, "m²", 10, 1000),
    "osoby_na_mieszkanie": ("osoby na mieszkanie", 2.4, "os.", 0.5, 10),
    "miejsca_na_mieszkanie_mw": ("miejsca postojowe na mieszkanie MW", 1.2, "", 0, 5),
    "miejsca_na_mieszkanie_mn": ("miejsca postojowe na dom MN", 2, "", 0, 5),
    "miejsca_na_1000m2_u": ("miejsca postojowe na 1000 m² usług", 25, "", 0, 200),
    "m2_na_miejsce_ks": ("m² terenu KS na miejsce (z dojazdem)", 25, "m²", 10, 100),
    "dzieci_przedszkole_proc": ("dzieci w wieku przedszkolnym (3–6 lat)", 4, "% mieszk.", 0, 30),
    "dzieci_szkola_proc": ("dzieci w wieku szkolnym (7–14 lat)", 9, "% mieszk.", 0, 30),
    "dzieci_w_oddziale": ("dzieci w oddziale / klasie", 25, "", 5, 40),
}


def _w_dol(x: float) -> int:
    """Część całkowita z tolerancją 0,01 na błąd przeliczenia powierzchni
    (np. 6,9999 mieszkania z pola 1999,98 m² to 7, nie 6)."""
    return math.floor(x + 0.01)


class BladZalozen(ValueError):
    """Niepoprawne założenie programu."""


def zalozenia(ustawienia: dict | None) -> dict:
    """Założenia domyślne nadpisane wpisanymi w ustawieniach koncepcji."""
    wpisane = (ustawienia or {}).get("program") or {}
    if not isinstance(wpisane, dict):
        raise BladZalozen("Założenia programu muszą być obiektem.")
    wynik = {klucz: z[1] for klucz, z in ZALOZENIA.items()}
    for klucz, wartosc in wpisane.items():
        if klucz not in ZALOZENIA:
            raise BladZalozen(f"Nieznane założenie programu „{klucz}”.")
        if wartosc is None or wartosc == "":
            continue
        opis, _, _, od, do = ZALOZENIA[klucz]
        try:
            liczba = float(wartosc)
        except (TypeError, ValueError):
            liczba = math.nan
        if isinstance(wartosc, bool) or not math.isfinite(liczba) or not od <= liczba <= do:
            raise BladZalozen(f"Założenie „{opis}”: podaj liczbę {od}–{do}.")
        wynik[klucz] = liczba
    return wynik


def program(tereny: list[dict], obszar_m2: float | None, ustawienia: dict | None) -> dict:
    """Program osiedla z terenów (z polami pole_m2 i parametry) i założeń."""
    z = zalozenia(ustawienia)
    calkowita = {"MN": 0.0, "MW": 0.0, "U": 0.0}
    pole = {"KS": 0.0, "ZP": 0.0}
    for t in tereny:
        p = t["parametry"]
        if t["funkcja"] in calkowita:
            calkowita[t["funkcja"]] += t["pole_m2"] * p["zabudowa_proc"] / 100 * p["kondygnacje"]
        if t["funkcja"] in pole:
            pole[t["funkcja"]] += t["pole_m2"]

    udzial = z["udzial_mieszkan_proc"] / 100
    mieszkania_mw = _w_dol(calkowita["MW"] * udzial / z["metraz_mw_m2"])
    mieszkania_mn = _w_dol(calkowita["MN"] * udzial / z["metraz_mn_m2"])
    mieszkania = mieszkania_mw + mieszkania_mn
    mieszkancy = round(mieszkania * z["osoby_na_mieszkanie"])

    miejsca_potrzebne = math.ceil(
        mieszkania_mw * z["miejsca_na_mieszkanie_mw"]
        + mieszkania_mn * z["miejsca_na_mieszkanie_mn"]
        + calkowita["U"] / 1000 * z["miejsca_na_1000m2_u"]
    )
    miejsca_ks = _w_dol(pole["KS"] / z["m2_na_miejsce_ks"])

    dzieci_przedszkole = round(mieszkancy * z["dzieci_przedszkole_proc"] / 100)
    dzieci_szkola = round(mieszkancy * z["dzieci_szkola_proc"] / 100)

    return {
        "mieszkania_mw": mieszkania_mw,
        "mieszkania_mn": mieszkania_mn,
        "mieszkania": mieszkania,
        "mieszkancy": mieszkancy,
        "gestosc_os_na_ha": round(mieszkancy / (obszar_m2 / 10_000), 1) if obszar_m2 else None,
        "powierzchnia_uslug_m2": round(calkowita["U"], 1),
        "miejsca_potrzebne": miejsca_potrzebne,
        "miejsca_na_terenach_ks": miejsca_ks,
        # dodatnie = brakuje miejsc (trzeba parkingu podziemnego albo więcej KS)
        "miejsca_brakuje": max(0, miejsca_potrzebne - miejsca_ks),
        "dzieci_przedszkole": dzieci_przedszkole,
        "oddzialy_przedszkolne": math.ceil(dzieci_przedszkole / z["dzieci_w_oddziale"]),
        "dzieci_szkola": dzieci_szkola,
        "oddzialy_szkolne": math.ceil(dzieci_szkola / z["dzieci_w_oddziale"]),
        "zielen_na_mieszkanca_m2": round(pole["ZP"] / mieszkancy, 1) if mieszkancy else None,
        "zalozenia": z,
    }
