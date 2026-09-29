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

# Symbol w planie to zwykle numer porządkowy + litery, np. „1MN”, „12KDL”,
# czasem numer na końcu („MN1”) albo przeznaczenie mieszane („MN/U”,
# „MW,U”). Wyciągamy grupy wielkich liter.
_WZOR_LITER = re.compile(r"[A-ZĄĆĘŁŃÓŚŹŻ]+")


def opisz_symbol(symbol: str | None) -> list[dict]:
    """„3MN/U” → [{"symbol": "MN", "opis": ...}, {"symbol": "U", "opis": ...}].

    Symbol spoza słownika ma opis None — frontend pokaże „brak w słowniku”.
    """
    if not symbol:
        return []
    wynik = []
    for litery in _WZOR_LITER.findall(symbol.upper()):
        if litery not in {c["symbol"] for c in wynik}:
            wynik.append({"symbol": litery, "opis": SLOWNIK.get(litery)})
    return wynik
