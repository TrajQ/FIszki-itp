"""„Co nowego” po aktualizacji (ETAP 159).

Źródłem jest docs/CHANGELOG.md — każdy ETAP ma tam nagłówek
„## ETAP N — data” i punkty. Numer ostatnio obejrzanego ETAPu zapisujemy
w instance/widziana_wersja.txt: gdy po aktualizacji (aktualizuj.sh)
w CHANGELOG-u jest nowszy ETAP, strona główna pokazuje pasek „Co nowego”.
Przy pierwszym uruchomieniu zapisujemy bieżący ETAP bez paska — nowa
instalacja nie ma „nowości”.
"""

import os
import re

PLIK_CHANGELOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "CHANGELOG.md")
NAGLOWEK = re.compile(r"^## ETAP (\d+) — (\d{4}-\d{2}-\d{2})\s*$")
NAZWA_PLIKU = "widziana_wersja.txt"


def wpisy(sciezka: str = PLIK_CHANGELOG) -> list[dict]:
    """[{etap, data, punkty}] od najnowszego; punkt wieloliniowy sklejony w jeden."""
    wynik = []
    try:
        with open(sciezka, encoding="utf-8") as plik:
            linie = plik.read().splitlines()
    except OSError:
        return []
    for linia in linie:
        m = NAGLOWEK.match(linia)
        if m:
            wynik.append({"etap": int(m.group(1)), "data": m.group(2), "punkty": []})
        elif wynik and linia.startswith("- "):
            wynik[-1]["punkty"].append(linia[2:].strip())
        elif wynik and wynik[-1]["punkty"] and linia.startswith("  ") and linia.strip():
            wynik[-1]["punkty"][-1] += " " + linia.strip()
    return sorted(wynik, key=lambda w: w["etap"], reverse=True)


def widziany(instance_path: str) -> int | None:
    try:
        with open(os.path.join(instance_path, NAZWA_PLIKU), encoding="utf-8") as plik:
            return int(plik.read().strip())
    except (OSError, ValueError):
        return None


def zapisz_widziany(instance_path: str, etap: int) -> None:
    os.makedirs(instance_path, exist_ok=True)
    with open(os.path.join(instance_path, NAZWA_PLIKU), "w", encoding="utf-8") as plik:
        plik.write(f"{etap}\n")


def nowe(instance_path: str, sciezka: str = PLIK_CHANGELOG) -> list[dict]:
    """Wpisy nowsze niż ostatnio obejrzany ETAP; pierwsze uruchomienie — []."""
    lista = wpisy(sciezka)
    if not lista:
        return []
    ostatni = widziany(instance_path)
    if ostatni is None:
        zapisz_widziany(instance_path, lista[0]["etap"])
        return []
    return [w for w in lista if w["etap"] > ostatni]
