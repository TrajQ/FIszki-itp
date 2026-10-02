"""Warstwa integracji z Gemini API.

Zasada: model dostaje wyłącznie zaznaczony fragment tekstu i ma na jego
podstawie zaproponować pytanie/odpowiedź — bez dodawania faktów spoza
fragmentu (ta sama filozofia co zakaz generowania liczb przez LLM: model
tłumaczy i porządkuje to, co dostał, a nie wymyśla).
"""

import json
import re

from config import Config

PROMPT_SYSTEMOWY = (
    "Jesteś asystentem tworzącym fiszki edukacyjne na podstawie fragmentu "
    "tekstu z podręcznika. Na podstawie WYŁĄCZNIE podanego fragmentu ułóż "
    "jedno pytanie i jedną odpowiedź. Nie dodawaj żadnych faktów, liczb ani "
    "informacji, których nie ma w podanym fragmencie. Pytanie i odpowiedź "
    "mają być zwięzłe i po polsku.\n\n"
    "Odpowiedz WYŁĄCZNIE w dokładnie tym formacie, bez dodatkowego tekstu:\n"
    "PYTANIE: <treść pytania>\n"
    "ODPOWIEDZ: <treść odpowiedzi>"
)


class BladGemini(Exception):
    """Błąd komunikacji z Gemini API albo nieparsowalna odpowiedź."""


def _generuj(contents, **konfiguracja):
    """Jedno zapytanie do Gemini; błąd API → BladGemini. Biblioteka
    google-genai ładowana dopiero tu (ETAP 143): jej import to ok. 0,4 s,
    połowa startu aplikacji, a większość uruchomień nie pyta modelu."""
    from google import genai
    from google.genai import errors, types

    try:
        client = genai.Client(api_key=Config.GEMINI_API_KEY)
        return client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(**konfiguracja),
        )
    except errors.APIError as e:
        raise BladGemini(f"Błąd Gemini API: {e.message}") from e


def zaproponuj_fiszke(fragment_tekstu: str) -> dict:
    """Zwraca {"pytanie": str, "odpowiedz": str} na podstawie fragmentu tekstu.

    Podnosi BladGemini przy błędzie sieci/API albo gdy odpowiedzi nie da się
    sparsować — wywołujący (routes.py) zamienia to na czytelny komunikat
    błędu w JSON, bez blokowania ręcznego uzupełnienia formularza.
    """
    if not Config.GEMINI_API_KEY:
        raise BladGemini("Brak GEMINI_API_KEY w konfiguracji (.env).")

    response = _generuj(fragment_tekstu, system_instruction=PROMPT_SYSTEMOWY)

    return _sparsuj_odpowiedz(response.text or "")


def _sparsuj_odpowiedz(tekst: str) -> dict:
    pytanie = None
    odpowiedz = None
    biezacy = None
    bufor = []

    def zapisz():
        nonlocal pytanie, odpowiedz
        if biezacy == "pytanie":
            pytanie = "\n".join(bufor).strip()
        elif biezacy == "odpowiedz":
            odpowiedz = "\n".join(bufor).strip()

    for linia in tekst.splitlines():
        if linia.upper().startswith("PYTANIE:"):
            zapisz()
            biezacy = "pytanie"
            bufor = [linia.split(":", 1)[1].strip()]
        elif linia.upper().startswith("ODPOWIEDZ:"):
            zapisz()
            biezacy = "odpowiedz"
            bufor = [linia.split(":", 1)[1].strip()]
        elif biezacy is not None:
            bufor.append(linia)
    zapisz()

    if not pytanie or not odpowiedz:
        raise BladGemini("Nie udało się sparsować odpowiedzi Gemini.")

    return {"pytanie": pytanie, "odpowiedz": odpowiedz}


# ---------- Fiszki: kilka propozycji z całej strony (ETAP 18) ----------

PROMPT_STRONY = (
    "Jesteś asystentem tworzącym fiszki edukacyjne. Dostajesz tekst jednej "
    "strony podręcznika. Ułóż od 1 do {liczba} fiszek sprawdzających "
    "najważniejsze pojęcia i zależności z tej strony — WYŁĄCZNIE na podstawie "
    "podanego tekstu, bez dodawania faktów, liczb ani informacji spoza niego. "
    "Pytania i odpowiedzi mają być zwięzłe i po polsku.\n"
    "Każda fiszka musi mieć pole \"fragment\": DOSŁOWNY cytat (1–2 zdania, "
    "skopiowany znak w znak z tekstu strony), na którym opiera się odpowiedź.\n"
    "Odpowiedz WYŁĄCZNIE listą JSON w formacie: "
    '[{{"pytanie": "...", "odpowiedz": "...", "fragment": "..."}}]'
)


def zaproponuj_fiszki_ze_strony(tekst_strony: str, liczba: int = 5) -> list[dict]:
    """Zwraca listę {"pytanie", "odpowiedz", "fragment"} z tekstu strony.

    Czy „fragment” naprawdę występuje na stronie, sprawdza wywołujący
    (fiszki/strona.py) — model bywa nieprecyzyjny przy cytowaniu.
    """
    if not Config.GEMINI_API_KEY:
        raise BladGemini("Brak GEMINI_API_KEY w konfiguracji (.env).")

    response = _generuj(tekst_strony, system_instruction=PROMPT_STRONY.format(liczba=liczba),
                        response_mime_type="application/json")

    return sparsuj_liste_fiszek(response.text or "")


def sparsuj_liste_fiszek(tekst: str) -> list[dict]:
    """JSON od modelu → lista poprawnych propozycji (niepełne pomijamy)."""
    tekst = tekst.strip()
    # Model czasem owija JSON w blok ```json ... ```
    if tekst.startswith("```"):
        tekst = tekst.strip("`").removeprefix("json").strip()
    try:
        dane = json.loads(tekst)
    except json.JSONDecodeError as e:
        raise BladGemini("Gemini zwrócił odpowiedź, której nie da się odczytać jako JSON.") from e
    if isinstance(dane, dict):
        dane = dane.get("fiszki", [])
    if not isinstance(dane, list):
        raise BladGemini("Gemini zwrócił nieoczekiwany format odpowiedzi.")

    wynik = []
    for pozycja in dane:
        if not isinstance(pozycja, dict):
            continue
        pola = {k: str(pozycja.get(k) or "").strip() for k in ("pytanie", "odpowiedz", "fragment")}
        if all(pola.values()):
            wynik.append(pola)
    return wynik


# ---------- Atlas: opis wskaźnika (ETAP 7) ----------

PROMPT_OPISU = (
    "Jesteś analitykiem gospodarki przestrzennej. Dostajesz listę faktów o "
    "jednym wskaźniku GUS dla gmin jednego województwa. Napisz po polsku "
    "zwięzły opis (3–5 zdań) dla studenta: co pokazuje wskaźnik, gdzie jest "
    "najwyżej, gdzie najniżej, jak duże jest zróżnicowanie.\n"
    "ZASADY BEZWZGLĘDNE:\n"
    "- Używaj WYŁĄCZNIE liczb podanych w faktach, przepisanych dokładnie tak, "
    "jak są zapisane. Nie licz niczego sam: żadnych różnic, ilorazów, "
    "procentów, zaokrągleń ani nowych liczb.\n"
    "- Nie dodawaj faktów spoza listy, nie zgaduj przyczyn jako pewników.\n"
    "- Zwykły tekst, bez nagłówków i list."
)

# Liczba w tekście: cyfry z opcjonalnymi grupami tysięcy (spacja zwykła,
# niełamliwa lub wąska) i częścią dziesiętną po przecinku lub kropce.
_WZOR_LICZBY = re.compile(r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")


def _znormalizuj_liczbe(tekst: str) -> str:
    return re.sub(r"[ \u00a0\u202f]", "", tekst).replace(",", ".")


def liczby_w_tekscie(tekst: str) -> set[str]:
    return {_znormalizuj_liczbe(m) for m in _WZOR_LICZBY.findall(tekst)}


def opisz_wskaznik(fakty: list[str]) -> str:
    """Opis wskaźnika na podstawie faktów policzonych w atlas/statystyki.py.

    Po odpowiedzi modelu sprawdzamy, czy każda liczba z opisu występuje w
    faktach. Jeśli model „wymyślił” liczbę — odrzucamy opis (BladGemini),
    zgodnie z zasadą: model opisuje, liczby przychodzą z danych.
    """
    if not Config.GEMINI_API_KEY:
        raise BladGemini("Brak GEMINI_API_KEY w konfiguracji (.env).")

    response = _generuj("Fakty:\n" + "\n".join(f"- {f}" for f in fakty), system_instruction=PROMPT_OPISU)

    opis = (response.text or "").strip()
    if not opis:
        raise BladGemini("Gemini zwrócił pusty opis.")
    sprawdz_liczby(opis, fakty)
    return opis


def sprawdz_liczby(opis: str, fakty: list[str]) -> None:
    obce = liczby_w_tekscie(opis) - liczby_w_tekscie("\n".join(fakty))
    if obce:
        raise BladGemini(
            "Opis odrzucony: model podał liczby, których nie ma w danych ("
            + ", ".join(sorted(obce))
            + "). Spróbuj ponownie."
        )


# ---------- Przepisy: odpowiedź na pytanie z cytatami (ETAP 62) ----------

PROMPT_PRZEPISOW = (
    "Jesteś asystentem pomagającym studentowi gospodarki przestrzennej czytać "
    "przepisy. Dostajesz pytanie i ponumerowane fragmenty aktów prawnych "
    "([1], [2], …). Odpowiedz po polsku, zwięźle (2–6 zdań), WYŁĄCZNIE na "
    "podstawie tych fragmentów.\n"
    "ZASADY BEZWZGLĘDNE:\n"
    "- Każde stwierdzenie oprzyj na cytacie. Cytat to DOSŁOWNY fragment "
    "(kilka–kilkadziesiąt słów) skopiowany znak w znak z jednego fragmentu.\n"
    "- Nie dodawaj wiedzy spoza fragmentów, liczb ani terminów, których w nich nie ma.\n"
    "- Jeśli fragmenty nie odpowiadają na pytanie, ustaw \"brak_odpowiedzi\": true "
    "i w polu \"odpowiedz\" napisz krótko, czego brakuje.\n"
    "Odpowiedz WYŁĄCZNIE obiektem JSON: "
    '{"odpowiedz": "...", "brak_odpowiedzi": false, '
    '"cytaty": [{"fragment": 1, "cytat": "..."}]}'
)


def odpowiedz_z_przepisow(pytanie: str, fragmenty: list[str]) -> dict:
    """Surowa odpowiedź modelu: {"odpowiedz", "brak_odpowiedzi", "cytaty"}.

    Czy cytaty naprawdę są w tekście i czy liczby pochodzą ze źródeł,
    sprawdza wywołujący (przepisy/pytania.py).
    """
    if not Config.GEMINI_API_KEY:
        raise BladGemini("Brak GEMINI_API_KEY w konfiguracji (.env).")
    tresc = "PYTANIE: " + pytanie + "\n\nFRAGMENTY:\n\n" + "\n\n".join(
        f"[{i}] {f}" for i, f in enumerate(fragmenty, start=1)
    )
    response = _generuj(tresc, system_instruction=PROMPT_PRZEPISOW, response_mime_type="application/json")

    tekst = (response.text or "").strip()
    if tekst.startswith("```"):
        tekst = tekst.strip("`").removeprefix("json").strip()
    try:
        dane = json.loads(tekst)
    except json.JSONDecodeError as e:
        raise BladGemini("Gemini zwrócił odpowiedź, której nie da się odczytać jako JSON.") from e
    if not isinstance(dane, dict):
        raise BladGemini("Gemini zwrócił nieoczekiwany format odpowiedzi.")
    return dane


# ---------- Atlas: opis raportu gminy (ETAP 63) ----------

PROMPT_RAPORTU_GMINY = (
    "Jesteś analitykiem gospodarki przestrzennej. Dostajesz fakty o jednej "
    "gminie: wartości wskaźników GUS, ich zmianę w czasie i miejsce gminy w "
    "województwie. Napisz po polsku zwięzłą charakterystykę gminy (4–7 zdań) "
    "dla studenta przygotowującego diagnozę uwarunkowań: co wyróżnia gminę na "
    "tle województwa, co się zmienia w czasie.\n"
    "ZASADY BEZWZGLĘDNE:\n"
    "- Używaj WYŁĄCZNIE liczb podanych w faktach, przepisanych dokładnie tak, "
    "jak są zapisane. Nie licz niczego sam: żadnych różnic, ilorazów, "
    "procentów, zaokrągleń ani nowych liczb.\n"
    "- Nie dodawaj faktów spoza listy, nie zgaduj przyczyn jako pewników.\n"
    "- Zwykły tekst, bez nagłówków i list."
)


def opisz_gmine(fakty: list[str]) -> str:
    """Charakterystyka gminy z faktów policzonych w atlas/raport.py.

    Tak jak w opisz_wskaznik: liczba spoza faktów odrzuca opis.
    """
    if not Config.GEMINI_API_KEY:
        raise BladGemini("Brak GEMINI_API_KEY w konfiguracji (.env).")
    response = _generuj("Fakty:\n" + "\n".join(f"- {f}" for f in fakty), system_instruction=PROMPT_RAPORTU_GMINY)
    opis = (response.text or "").strip()
    if not opis:
        raise BladGemini("Gemini zwrócił pusty opis.")
    sprawdz_liczby(opis, fakty)
    return opis


# ---------- Przepisy: fiszki z artykułu (ETAP 82) ----------

PROMPT_FISZEK_Z_PRZEPISU = (
    "Jesteś asystentem studenta gospodarki przestrzennej uczącego się przepisów. "
    "Dostajesz tekst jednej jednostki aktu prawnego ({oznaczenie}). Ułóż od 1 do "
    "{liczba} fiszek sprawdzających, co ten przepis stanowi (obowiązki, warunki, "
    "terminy, definicje) — WYŁĄCZNIE na podstawie podanego tekstu. W odpowiedzi "
    "wskaż jednostkę redakcyjną (np. „art. 15 ust. 2 pkt 6”), jeśli wynika z tekstu. "
    "Nie dodawaj faktów ani liczb spoza tekstu. Pytania i odpowiedzi zwięzłe, po polsku.\n"
    "Każda fiszka musi mieć pole \"fragment\": DOSŁOWNY cytat (fragment zdania, "
    "skopiowany znak w znak z tekstu), na którym opiera się odpowiedź.\n"
    "Odpowiedz WYŁĄCZNIE listą JSON w formacie: "
    '[{{"pytanie": "...", "odpowiedz": "...", "fragment": "..."}}]'
)


def zaproponuj_fiszki_z_przepisu(tekst: str, oznaczenie: str, liczba: int = 4) -> list[dict]:
    """Propozycje {"pytanie", "odpowiedz", "fragment"} z jednej jednostki aktu.

    Cytaty i liczby sprawdza wywołujący (przepisy/pytania.py)."""
    if not Config.GEMINI_API_KEY:
        raise BladGemini("Brak GEMINI_API_KEY w konfiguracji (.env).")
    response = _generuj(tekst, system_instruction=PROMPT_FISZEK_Z_PRZEPISU.format(oznaczenie=oznaczenie, liczba=liczba),
                        response_mime_type="application/json")
    return sparsuj_liste_fiszek(response.text or "")
