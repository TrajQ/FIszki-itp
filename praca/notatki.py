"""Notatki do nauki z PDF-u albo zdjęć (ETAP 231).

Treść układa Gemini (dane/gemini.py, `utworz_notatki`) jako JSON:
tytuł, streszczenie, sekcje z akapitami, listami i ramkami, pojęcia,
„do zapamiętania”. Tu sprawdzamy i porządkujemy ten JSON (limity, puste
pola, nieznane typy bloków) i — gdy materiał był tekstem — szukamy liczb,
których w materiale nie ma: model miał je tylko przepisywać.
Plik Word buduje praca/word.py.
"""

import csv
import io
import json

from dane.gemini import liczby_w_tekscie

MAKS_SEKCJI = 40
MAKS_BLOKOW = 40
MAKS_PUNKTOW = 40
MAKS_POJEC = 60
MAKS_DLUGOSC = 4000
MAKS_ZNAKOW_MATERIALU = 120_000  # ok. 50 stron tekstu — więcej i tak nie zmieści się w jednej notatce


class BladNotatek(ValueError):
    """Odpowiedzi modelu albo danych notatki nie da się użyć."""


def _tekst(x, maks: int = MAKS_DLUGOSC) -> str:
    return " ".join(str(x or "").split())[:maks]


def _lista(x, maks: int) -> list[str]:
    return [t for t in (_tekst(p) for p in (x if isinstance(x, list) else [])[:maks]) if t]


def _blok(b) -> dict | None:
    if not isinstance(b, dict):
        return None
    typ = b.get("typ")
    if typ == "akapit" and _tekst(b.get("tekst")):
        return {"typ": "akapit", "tekst": _tekst(b.get("tekst"))}
    if typ == "lista" and _lista(b.get("punkty"), MAKS_PUNKTOW):
        return {"typ": "lista", "punkty": _lista(b.get("punkty"), MAKS_PUNKTOW)}
    if typ == "ramka" and _tekst(b.get("tekst")):
        return {"typ": "ramka", "tytul": _tekst(b.get("tytul"), 80) or "Uwaga", "tekst": _tekst(b.get("tekst"))}
    return None


MAKS_PYTAN = 15


def _pytania(x) -> list[dict]:
    wynik = []
    for p in (x if isinstance(x, list) else [])[:MAKS_PYTAN]:
        if isinstance(p, dict) and _tekst(p.get("pytanie")) and _tekst(p.get("odpowiedz")):
            wynik.append({"pytanie": _tekst(p.get("pytanie"), 500), "odpowiedz": _tekst(p.get("odpowiedz"), 1500)})
    return wynik


def fiszki_csv(n: dict) -> str:
    """ETAP 233: pytania kontrolne i pojęcia jako CSV z nagłówkiem
    `pytanie;odpowiedz` — format, który przyjmuje import Fiszek (fiszki/importer.py)."""
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";")
    zapis.writerow(["pytanie", "odpowiedz"])
    for p in n["pytania"]:
        zapis.writerow([p["pytanie"], p["odpowiedz"]])
    for p in n["pojecia"]:
        zapis.writerow([f"Co to jest: {p['pojecie']}?", p["definicja"]])
    return bufor.getvalue()


def oczysc(dane) -> dict:
    """JSON od modelu albo notatka odesłana ze strony → notatka w stałym kształcie."""
    if isinstance(dane, str):
        tekst = dane.strip()
        if tekst.startswith("```"):  # model czasem owija JSON w blok ```json
            tekst = tekst.strip("`").removeprefix("json").strip()
        try:
            dane = json.loads(tekst)
        except json.JSONDecodeError as e:
            raise BladNotatek("Gemini zwrócił notatki w formacie, którego nie da się odczytać — spróbuj ponownie.") from e
    if not isinstance(dane, dict):
        raise BladNotatek("Nieoczekiwany format notatek.")
    sekcje = []
    for s in (dane.get("sekcje") if isinstance(dane.get("sekcje"), list) else [])[:MAKS_SEKCJI]:
        if not isinstance(s, dict):
            continue
        bloki = [b for b in (_blok(x) for x in (s.get("bloki") if isinstance(s.get("bloki"), list) else [])[:MAKS_BLOKOW]) if b]
        if bloki:
            sekcje.append({"naglowek": _tekst(s.get("naglowek"), 200) or "Notatki", "bloki": bloki})
    pojecia = []
    for p in (dane.get("pojecia") if isinstance(dane.get("pojecia"), list) else [])[:MAKS_POJEC]:
        if isinstance(p, dict) and _tekst(p.get("pojecie")) and _tekst(p.get("definicja")):
            pojecia.append({"pojecie": _tekst(p.get("pojecie"), 200), "definicja": _tekst(p.get("definicja"))})
    wynik = {
        "tytul": _tekst(dane.get("tytul"), 200) or "Notatki",
        "podtytul": _tekst(dane.get("podtytul"), 200),
        "streszczenie": _tekst(dane.get("streszczenie")),
        "sekcje": sekcje,
        "pojecia": pojecia,
        "do_zapamietania": _lista(dane.get("do_zapamietania"), 15),
        "pytania": _pytania(dane.get("pytania")),  # ETAP 233
        "nieczytelne": _lista(dane.get("nieczytelne"), 20),
    }
    if not sekcje and not pojecia and not wynik["do_zapamietania"]:
        raise BladNotatek("Notatki są puste — materiał był nieczytelny albo za krótki.")
    return wynik


def caly_tekst(n: dict) -> str:
    """Wszystkie teksty notatki w jednym ciągu (do sprawdzenia liczb)."""
    czesci = [n["tytul"], n["podtytul"], n["streszczenie"], *n["do_zapamietania"]]
    for s in n["sekcje"]:
        czesci.append(s["naglowek"])
        for b in s["bloki"]:
            czesci += b.get("punkty", []) + [b.get("tytul", ""), b.get("tekst", "")]
    for p in n["pojecia"]:
        czesci += [p["pojecie"], p["definicja"]]
    for p in n.get("pytania", []):
        czesci += [p["pytanie"], p["odpowiedz"]]
    return "\n".join(c for c in czesci if c)


def liczby_spoza_materialu(n: dict, material: str) -> list[str]:
    """Liczby w notatce, których nie ma w materiale (do sprawdzenia przez autora)."""
    return sorted(liczby_w_tekscie(caly_tekst(n)) - liczby_w_tekscie(material), key=lambda x: (len(x), x))
