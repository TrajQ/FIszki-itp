"""Słowniczek definicji ustawowych z tekstu aktu (ETAP 120).

Rozpoznajemy dwa typowe sposoby definiowania pojęć w polskich ustawach:

1. Artykuł z definicjami: „Ilekroć w ustawie jest mowa o: 1) ładzie
   przestrzennym – należy przez to rozumieć …” albo „Użyte w ustawie
   określenia oznaczają: 1) teren – …”. Każdy punkt „N)” z myślnikiem to
   jedna definicja.
2. Skróty w treści: „… planu ogólnego gminy, zwanego dalej „planem
   ogólnym” …” — pojęcie i miejsce, w którym je wprowadzono.

Pojęcie zostawiamy w formie z tekstu („ładzie przestrzennym” — po „mowa
o”), bez odmieniania: odmiana wymagałaby słownika, a zgadywanie formy
podstawowej mogłoby zmienić sens. Treść definicji to dokładny tekst
ustawy (przycięty do podglądu), z odnośnikiem do artykułu.
"""

import re

MAKS_DEFINICJI = 400
DLUGOSC_PODGLADU = 500
MAKS_DLUGOSC_POJECIA = 90

_WSTEP_DEFINICJI = re.compile(
    r"Ilekroć\s+w\s+(?:ustawie|rozporządzeniu|uchwale|niniejszej\s+ustawie)[^:]{0,80}mowa\s+o\s*:"
    r"|Użyte\s+w\s+(?:ustawie|rozporządzeniu|uchwale)\s+określenia\s+oznaczają\s*:"
    r"|Ilekroć\s+w\s+(?:ustawie|rozporządzeniu)[^:]{0,60}używa\s+się\s+określenia[^:]{0,40}:",
    re.IGNORECASE,
)
_PUNKT = re.compile(r"(?:^|\n)\s*(\d+[a-z]*)\)\s*(.+?)(?=\n\s*\d+[a-z]*\)\s|\Z)", re.DOTALL)
_MYSLNIK = re.compile(r"\s[–—-]\s")
_NALEZY_ROZUMIEC = re.compile(r"^(?:należy\s+przez\s+to\s+rozumieć|rozumie\s+się\s+przez\s+to|oznacza(?:ją)?)\s*", re.IGNORECASE)
_ZWANY_DALEJ = re.compile(r"zwan\w{0,3}\s+dalej\s+[„\"]([^”\"]{2,80})[”\"]", re.IGNORECASE)

# kolejność liter polskiego alfabetu do sortowania (bez zależności od locale systemu)
_ALFABET = "aąbcćdeęfghijklłmnńoóprsśtuvwxyzźż"
_KLUCZ = {litera: f"{i:02d}" for i, litera in enumerate(_ALFABET)}


def klucz_sortowania(tekst: str) -> str:
    return "".join(_KLUCZ.get(z, "99" + z) for z in tekst.casefold())


def _skroc(tekst: str) -> str:
    tekst = " ".join(tekst.split())
    return tekst if len(tekst) <= DLUGOSC_PODGLADU else tekst[:DLUGOSC_PODGLADU].rsplit(" ", 1)[0] + " …"


def definicje_w_jednostce(tekst: str) -> list[dict]:
    """Definicje z artykułu z wyliczeniem „Ilekroć w ustawie jest mowa o: 1) … – …”."""
    wstep = _WSTEP_DEFINICJI.search(tekst)
    if not wstep:
        return []
    wynik = []
    for numer, tresc in _PUNKT.findall(tekst[wstep.end():]):
        podzial = _MYSLNIK.search(tresc)
        if not podzial:
            continue  # punkt bez myślnika — to nie definicja (np. wyliczenie w środku definicji)
        pojecie = " ".join(tresc[:podzial.start()].split()).rstrip(",;")
        if not pojecie or len(pojecie) > MAKS_DLUGOSC_POJECIA:
            continue
        definicja = _NALEZY_ROZUMIEC.sub("", tresc[podzial.end():].strip())
        wynik.append({"pojecie": pojecie, "punkt": numer, "definicja": _skroc(definicja).rstrip(";"), "rodzaj": "definicja"})
    return wynik


def skroty_w_jednostce(tekst: str) -> list[dict]:
    """„… zwanego dalej „planem ogólnym” …” — skrót z fragmentem zdania przed nim."""
    wynik = []
    for m in _ZWANY_DALEJ.finditer(tekst):
        poczatek = max(0, m.start() - 160)
        kontekst = tekst[poczatek:m.end()]
        kontekst = ("… " if poczatek else "") + " ".join(kontekst.split())
        wynik.append({"pojecie": m.group(1).strip(), "punkt": None, "definicja": kontekst, "rodzaj": "skrót"})
    return wynik


def slowniczek(jednostki: list[dict]) -> list[dict]:
    """Definicje i skróty całego aktu, alfabetycznie, z odnośnikiem do jednostki."""
    pozycje = []
    for j in jednostki:
        for p in definicje_w_jednostce(j["tekst"]) + skroty_w_jednostce(j["tekst"]):
            miejsce = j["oznaczenie"] + (f" pkt {p['punkt']}" if p["punkt"] else "")
            pozycje.append({**p, "jednostka_id": j.get("id"), "oznaczenie": j["oznaczenie"], "miejsce": miejsce})
    pozycje.sort(key=lambda p: (klucz_sortowania(p["pojecie"]), p["rodzaj"] != "definicja"))
    return pozycje[:MAKS_DEFINICJI]
