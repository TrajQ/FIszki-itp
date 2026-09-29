"""Słownik symboli przeznaczenia terenu w planach miejscowych.

Podstawa: oznaczenia literowe z rozporządzenia Ministra Infrastruktury
z 26 sierpnia 2003 r. w sprawie wymaganego zakresu projektu miejscowego
planu zagospodarowania przestrzennego (Dz.U. 2003 nr 164 poz. 1587),
uzupełnione o kilka oznaczeń powszechnie stosowanych w planach.

Opis jest ORIENTACYJNY: gmina może w swojej uchwale stosować własne
oznaczenia albo doprecyzowywać przeznaczenie. Rozstrzyga tekst uchwały
planu — dlatego panel zawsze pokazuje też surowe atrybuty z WFS.
"""

import re

SLOWNIK = {
    "MN": "tereny zabudowy mieszkaniowej jednorodzinnej",
    "MW": "tereny zabudowy mieszkaniowej wielorodzinnej",
    "M": "tereny zabudowy mieszkaniowej",
    "U": "tereny zabudowy usługowej",
    "US": "tereny sportu i rekreacji",
    "P": "tereny obiektów produkcyjnych, składów i magazynów",
    "R": "tereny rolnicze",
    "RM": "tereny zabudowy zagrodowej w gospodarstwach rolnych, hodowlanych i ogrodniczych",
    "RU": "tereny obsługi produkcji w gospodarstwach rolnych, hodowlanych i ogrodniczych",
    "ZL": "tereny lasów",
    "ZP": "tereny zieleni urządzonej",
    "ZC": "tereny cmentarzy",
    "ZD": "tereny ogrodów działkowych",
    "WS": "tereny wód powierzchniowych śródlądowych",
    "KD": "tereny dróg publicznych",
    "KDA": "tereny dróg publicznych — autostrada",
    "KDS": "tereny dróg publicznych — droga ekspresowa",
    "KDGP": "tereny dróg publicznych — droga główna ruchu przyspieszonego",
    "KDG": "tereny dróg publicznych — droga główna",
    "KDZ": "tereny dróg publicznych — droga zbiorcza",
    "KDL": "tereny dróg publicznych — droga lokalna",
    "KDD": "tereny dróg publicznych — droga dojazdowa",
    "KDW": "tereny dróg wewnętrznych",
    "KK": "tereny komunikacji kolejowej",
    "E": "tereny infrastruktury technicznej — elektroenergetyka",
    "G": "tereny infrastruktury technicznej — gazownictwo",
    "C": "tereny infrastruktury technicznej — ciepłownictwo",
    "W": "tereny infrastruktury technicznej — wodociągi",
    "K": "tereny infrastruktury technicznej — kanalizacja",
}

# Oznaczenia spoza listy rozporządzenia, ale często spotykane w planach
# (ETAP 45). Znaczenie bywa różne w różnych gminach — dlatego osobny
# słownik, a panel mówi wprost, że to oznaczenie zwyczajowe.
SLOWNIK_ZWYCZAJOWY = {
    "MU": "tereny zabudowy mieszkaniowo-usługowej",
    "ML": "tereny zabudowy rekreacji indywidualnej (letniskowej)",
    "UC": "tereny obiektów handlowych o powierzchni sprzedaży powyżej 2000 m²",
    "UO": "tereny usług oświaty",
    "UZ": "tereny usług zdrowia",
    "UK": "tereny usług kultu religijnego",
    "UT": "tereny usług turystyki",
    "UP": "tereny usług publicznych",
    "ZN": "tereny zieleni naturalnej",
    "ZI": "tereny zieleni izolacyjnej",
    "KS": "tereny obsługi komunikacji samochodowej (np. parkingi)",
    "IT": "tereny infrastruktury technicznej",
    "O": "tereny gospodarki odpadami",
    "PG": "tereny powierzchniowej eksploatacji kopalin",
}

# Grupy do tabeli w słowniku — po pierwszej literze symbolu.
GRUPY = {
    "M": "Zabudowa mieszkaniowa",
    "U": "Usługi, sport i rekreacja",
    "P": "Produkcja, składy, eksploatacja",
    "R": "Rolnictwo",
    "Z": "Zieleń i lasy",
    "W": "Wody i wodociągi",
    "K": "Komunikacja i kanalizacja",
    "E": "Infrastruktura techniczna",
    "G": "Infrastruktura techniczna",
    "C": "Infrastruktura techniczna",
    "I": "Infrastruktura techniczna",
    "O": "Infrastruktura techniczna",
}

# Symbol w planie to zwykle numer porządkowy + litery, np. „1MN”, „12KDL”,
# czasem numer na końcu („MN1”) albo przeznaczenie mieszane („MN/U”,
# „MW,U”). Wyciągamy grupy wielkich liter.
_WZOR_LITER = re.compile(r"[A-ZĄĆĘŁŃÓŚŹŻ]+")


def opisz_symbol(symbol: str | None) -> list[dict]:
    """„3MN/U” → [{"symbol": "MN", "opis": ...}, {"symbol": "U", "opis": ...}].

    Symbol spoza słowników ma opis None — frontend pokaże „brak w słowniku”.
    `zwyczajowe` = True, gdy opis pochodzi ze słownika zwyczajowego.
    """
    if not symbol:
        return []
    wynik = []
    for litery in _WZOR_LITER.findall(symbol.upper()):
        if litery in {c["symbol"] for c in wynik}:
            continue
        opis = SLOWNIK.get(litery)
        zwyczajowe = opis is None and litery in SLOWNIK_ZWYCZAJOWY
        wynik.append({"symbol": litery, "opis": opis or SLOWNIK_ZWYCZAJOWY.get(litery), "zwyczajowe": zwyczajowe})
    return wynik


def wszystkie_symbole() -> list[dict]:
    """Cały słownik do tabeli: grupa, symbol, opis, źródło — posortowany."""
    wiersze = [
        {"symbol": s, "opis": o, "zwyczajowe": False} for s, o in SLOWNIK.items()
    ] + [{"symbol": s, "opis": o, "zwyczajowe": True} for s, o in SLOWNIK_ZWYCZAJOWY.items()]
    for w in wiersze:
        w["grupa"] = GRUPY.get(w["symbol"][0], "Inne")
    kolejnosc = list(dict.fromkeys(GRUPY.values()))
    return sorted(wiersze, key=lambda w: (kolejnosc.index(w["grupa"]) if w["grupa"] in kolejnosc else 99, w["symbol"]))
