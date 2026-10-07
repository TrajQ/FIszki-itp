"""Rodzaj i data aktu z jego tytułu — do filtrów wyszukiwarki (ETAP 243).

Tytuł aktu z ISAP zaczyna się nagłówkiem wielkimi literami: „USTAWA z
dnia 27 marca 2003 r.”, „ROZPORZĄDZENIE MINISTRA INFRASTRUKTURY z dnia
12 kwietnia 2002 r.”. W tekście jednolitym przed ustawą stoi
obwieszczenie Marszałka Sejmu („…jednolitego tekstu ustawy…” — małymi
literami), więc szukamy pierwszego nagłówka wielkimi literami z datą:
data to dzień wydania aktu, nie obwieszczenia. Bez takiego nagłówka —
rodzaj z nazwy (bez daty) albo „inny”.
"""

import re
from datetime import date

RODZAJE = ("ustawa", "rozporządzenie", "uchwała", "zarządzenie", "inny")
MIESIACE = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7,
            "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12}
_NAGLOWEK = re.compile(
    r"\b(USTAWA|ROZPORZĄDZENIE|UCHWAŁA|ZARZĄDZENIE)\b[^\n]{0,200}?\s*(?:\n[^\n]{0,200}?)??\s*z\s+dnia\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s*r",
)
_RODZAJ_W_NAZWIE = re.compile(r"\b(ustawa|rozporządzenie|uchwała|zarządzenie)\b", re.IGNORECASE)


def metryka(nazwa: str, tytul: str = "") -> dict:
    """{"rodzaj", "data" (RRRR-MM-DD albo None)} z tytułu, a bez niego z nazwy."""
    for tekst in (tytul, nazwa):
        m = _NAGLOWEK.search(tekst or "")
        if m:
            miesiac = MIESIACE.get(m.group(3).lower())
            try:
                data = date(int(m.group(4)), miesiac, int(m.group(2))).isoformat() if miesiac else None
            except ValueError:
                data = None
            return {"rodzaj": m.group(1).lower(), "data": data}
    m = _RODZAJ_W_NAZWIE.search(nazwa or "")
    return {"rodzaj": m.group(1).lower() if m else "inny", "data": None}
