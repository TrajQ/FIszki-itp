"""Akty prawne z API Sejmu (ELI) — oficjalne teksty z Dziennika Ustaw (ETAP 88).

Kancelaria Sejmu udostępnia bez klucza API z metadanymi aktów i ich
tekstami w PDF (https://api.sejm.gov.pl/ — ta sama baza co ISAP):

- wyszukiwanie: /eli/acts/search?title=…&publisher=DU&limit=…
  → {"count", "items": [{"publisher", "year", "pos", "title", "type",
  "status", "textPDF", …}]}
- tekst: /eli/acts/{publisher}/{year}/{pos}/text.pdf

Tekst jednolity ustawy to w Dzienniku Ustaw osobna pozycja —
„Obwieszczenie Marszałka Sejmu … w sprawie ogłoszenia jednolitego
tekstu ustawy …” — i to ją warto pobrać do modułu przepisy.

Z odpowiedzi bierzemy tylko potrzebne pola i nie zakładamy, że wszystkie
są zawsze obecne (np. textPDF bywa wartością logiczną albo adresem).
"""

import re

import requests

from .siec import opis_bledu_sieci

URL_API = "https://api.sejm.gov.pl/eli"
MAKS_WYNIKOW = 30
MAKS_ROZMIAR_PDF = 60 * 1024 * 1024  # ustawy z załącznikami bywają duże
MAKS_DLUGOSC_ZAPYTANIA = 200


class BladSejmu(Exception):
    """Błąd API Sejmu albo odpowiedź, której nie da się użyć."""


def _pozycja(item: dict) -> dict | None:
    try:
        rok, poz = int(item["year"]), int(item["pos"])
    except (KeyError, TypeError, ValueError):
        return None
    wydawca = str(item.get("publisher") or "DU")
    return {
        "wydawca": wydawca,
        "rok": rok,
        "pozycja": poz,
        "adres": f"{'Dz.U.' if wydawca == 'DU' else 'M.P.'} {rok} poz. {poz}",
        "tytul": " ".join(str(item.get("title") or "").split()),
        "rodzaj": str(item.get("type") or ""),
        "status": str(item.get("status") or ""),
        "ma_pdf": bool(item.get("textPDF")),
        "tekst_jednolity": "jednolitego tekstu" in str(item.get("title") or "").lower(),
    }


def szukaj_aktow(tytul: str) -> list[dict]:
    """Akty z Dziennika Ustaw, których tytuł zawiera podane słowa. Najnowsze najpierw."""
    tytul = " ".join((tytul or "").split())[:MAKS_DLUGOSC_ZAPYTANIA]
    if len(tytul) < 3:
        raise BladSejmu("Wpisz co najmniej 3 znaki tytułu, np. „planowaniu i zagospodarowaniu”.")
    try:
        odpowiedz = requests.get(
            f"{URL_API}/acts/search",
            params={"title": tytul, "publisher": "DU", "limit": MAKS_WYNIKOW},
            timeout=30,
        )
        odpowiedz.raise_for_status()
        dane = odpowiedz.json()
    except requests.RequestException as e:
        raise BladSejmu(f"Błąd połączenia z API Sejmu: {opis_bledu_sieci(e)}.") from e
    except ValueError as e:
        raise BladSejmu("API Sejmu zwróciło odpowiedź, której nie da się odczytać.") from e
    items = dane.get("items") if isinstance(dane, dict) else dane
    wynik = [p for p in (_pozycja(i) for i in items or [] if isinstance(i, dict)) if p]
    return sorted(wynik, key=lambda p: (p["rok"], p["pozycja"]), reverse=True)


def pobierz_pdf(rok: int, pozycja: int, wydawca: str = "DU") -> bytes:
    """Urzędowy tekst aktu w PDF."""
    if wydawca not in ("DU", "MP") or not (1918 <= rok <= 2100) or not (0 < pozycja < 100_000):
        raise BladSejmu("Niepoprawny adres aktu.")
    try:
        odpowiedz = requests.get(f"{URL_API}/acts/{wydawca}/{rok}/{pozycja}/text.pdf", timeout=120, stream=True)
        odpowiedz.raise_for_status()
        dane = bytearray()
        for kawalek in odpowiedz.iter_content(1 << 16):
            dane += kawalek
            if len(dane) > MAKS_ROZMIAR_PDF:
                raise BladSejmu("PDF aktu jest za duży (ponad 60 MB).")
    except requests.RequestException as e:
        raise BladSejmu(f"Nie udało się pobrać tekstu aktu z API Sejmu: {opis_bledu_sieci(e)}.") from e
    if not dane.startswith(b"%PDF-"):
        raise BladSejmu("API Sejmu nie zwróciło pliku PDF dla tego aktu (może nie mieć tekstu w PDF).")
    return bytes(dane)


# ---------- czy jest nowszy tekst jednolity (ETAP 101) ----------

_ADRES = re.compile(r"\(Dz\.U\. (\d{4}) poz\. (\d+)\)\s*$")
# przedmiot ustawy: „o planowaniu …” albo „Prawo budowlane” — najpierw po „tekstu
# ustawy” (obwieszczenie), dopiero potem po dacie (sama ustawa)
_PRZEDMIOT = [
    re.compile(r"tekstu ustawy\s*[–-]?\s*([^()]+?)\s*(?:\(Dz\.U\.|$)"),
    re.compile(r"\d{4} r\.\s*[–-]?\s*([^()]+?)\s*(?:\(Dz\.U\.|$)"),
]


def adres_i_przedmiot(nazwa: str) -> tuple[int, int, str] | None:
    """Z nazwy aktu pobranego z Dziennika Ustaw: (rok, pozycja, przedmiot) albo None."""
    adres = _ADRES.search(nazwa or "")
    przedmiot = next((m for wzor in _PRZEDMIOT if (m := wzor.search(nazwa or ""))), None)
    if not adres or not przedmiot or len(przedmiot.group(1)) < 5:
        return None
    return int(adres.group(1)), int(adres.group(2)), " ".join(przedmiot.group(1).split())


def nowsze_teksty_jednolite(nazwa: str) -> dict:
    """Obwieszczenia z tekstem jednolitym tej samej ustawy, nowsze niż akt w bibliotece."""
    dane = adres_i_przedmiot(nazwa)
    if dane is None:
        raise BladSejmu("To działa dla aktów pobranych z Dziennika Ustaw — w nazwie musi zostać tytuł i „(Dz.U. rok poz. …)”.")
    rok, pozycja, przedmiot = dane
    wszystkie = szukaj_aktow(przedmiot)
    nowsze = [
        a for a in wszystkie
        if a["tekst_jednolity"] and przedmiot.lower() in a["tytul"].lower() and (a["rok"], a["pozycja"]) > (rok, pozycja)
    ]
    return {"przedmiot": przedmiot, "adres": f"Dz.U. {rok} poz. {pozycja}", "nowsze": nowsze}
