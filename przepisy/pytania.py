"""Pytanie do przepisów → odpowiedź modelu sprawdzona w źródle (ETAP 62).

1. Kod wybiera kandydatów: jednostki (artykuły, paragrafy) najlepiej
   pasujące do słów pytania (FTS5, baza.py).
2. Model (dane/gemini.py) dostaje TYLKO te jednostki i ma odpowiedzieć z
   dosłownymi cytatami.
3. Kod sprawdza odpowiedź:
   - cytat musi naprawdę być w tekście wskazanej jednostki (bez względu
     na białe znaki, cudzysłowy i rodzaj myślnika) — cytaty wymyślone
     odrzucamy,
   - odpowiedź bez ani jednego prawdziwego cytatu nie jest pokazywana,
   - każda liczba z odpowiedzi musi występować w podanych jednostkach
     albo w pytaniu (model nie generuje liczb — CLAUDE.md).
"""

import re

from dane.gemini import liczby_w_tekscie

from . import baza

MAKS_JEDNOSTEK = 8
MAKS_ZNAKOW_JEDNOSTKI = 4000  # długie artykuły (np. definicje) przycinamy
MAKS_DLUGOSC_PYTANIA = 500

# Słowa pytania, które nic nie mówią o treści przepisów.
SLOWA_POMIJANE = {
    "czy", "jak", "jaka", "jaki", "jakie", "jakich", "jest", "sa", "kto", "co", "czego", "gdzie", "kiedy",
    "moze", "mozna", "trzeba", "nalezy", "ktory", "ktora", "ktore", "jesli", "oraz", "albo", "lub", "dla",
    "przez", "sie", "tego", "tym", "ten", "ta", "to", "od", "do", "na", "po", "za", "ze", "przy", "nie",
    "mi", "mnie", "prosze", "wyjasnij", "powiedz", "ustawa", "ustawy", "przepis", "przepisy", "przepisach",
}

_ROWNOWAZNE = str.maketrans({"„": '"', "”": '"', "“": '"', "«": '"', "»": '"', "–": "-", "—": "-", "’": "'"})


class BladOdpowiedzi(ValueError):
    """Odpowiedź modelu nie przeszła sprawdzenia w źródle."""


def do_porownania(tekst: str) -> str:
    """Tekst bez białych znaków, z ujednoliconymi cudzysłowami i myślnikami."""
    return re.sub(r"\s+", "", tekst.translate(_ROWNOWAZNE)).lower()


def kandydaci(pytanie: str, akt_id: int | None) -> list[dict]:
    """Jednostki do pokazania modelowi. Słowa pomijane usuwamy przed
    zamianą na terminy (terminy mają już obcięte końcówki)."""
    slowa = [s for s in re.findall(r"\w+", baza.sprowadz(pytanie)) if s not in SLOWA_POMIJANE]
    return baza.jednostki_do_pytania(baza.terminy(" ".join(slowa)), akt_id, MAKS_JEDNOSTEK)


def fragment_dla_modelu(j: dict) -> str:
    tekst = j["tekst"]
    if len(tekst) > MAKS_ZNAKOW_JEDNOSTKI:
        tekst = tekst[:MAKS_ZNAKOW_JEDNOSTKI] + " […]"
    return f"{j['oznaczenie']} — {j['nazwa_aktu']}\n{tekst}"


def sprawdz(surowa: dict, jednostki: list[dict], pytanie: str) -> dict:
    """Surowa odpowiedź modelu → wynik do pokazania albo BladOdpowiedzi."""
    odpowiedz = str(surowa.get("odpowiedz") or "").strip()
    if not odpowiedz:
        raise BladOdpowiedzi("Model nie podał odpowiedzi. Spróbuj ponownie.")
    brak = bool(surowa.get("brak_odpowiedzi"))

    cytaty, odrzucone = [], 0
    for c in surowa.get("cytaty") or []:
        try:
            nr = int(c.get("fragment"))
            cytat = " ".join(str(c.get("cytat") or "").split()).strip(' "„”')
        except (AttributeError, TypeError, ValueError):
            odrzucone += 1
            continue
        if not (1 <= nr <= len(jednostki)) or len(cytat) < 10:
            odrzucone += 1
            continue
        j = jednostki[nr - 1]
        if do_porownania(cytat) not in do_porownania(j["tekst"]):
            odrzucone += 1
            continue
        cytaty.append({
            "cytat": cytat,
            "jednostka_id": j["id"],
            "akt_id": j["akt_id"],
            "oznaczenie": j["oznaczenie"],
            "nazwa_aktu": j["nazwa_aktu"],
            "strona": j["strona_od"],
        })

    if not brak and not cytaty:
        raise BladOdpowiedzi(
            "Odpowiedź odrzucona: model nie podał żadnego cytatu, który da się znaleźć w tekście przepisów. "
            "Spróbuj ponownie albo zadaj pytanie inaczej."
        )

    zrodla = [pytanie] + [f"{j['oznaczenie']} {j['tekst']}" for j in jednostki]
    obce = liczby_w_tekscie(odpowiedz) - liczby_w_tekscie("\n".join(zrodla))
    if obce:
        raise BladOdpowiedzi(
            "Odpowiedź odrzucona: model podał liczby, których nie ma w przepisach ("
            + ", ".join(sorted(obce))
            + "). Spróbuj ponownie."
        )
    return {"odpowiedz": odpowiedz, "brak_odpowiedzi": brak, "cytaty": cytaty, "odrzucone_cytaty": odrzucone}
