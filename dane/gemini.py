"""Warstwa integracji z Gemini API.

Zasada: model dostaje wyłącznie zaznaczony fragment tekstu i ma na jego
podstawie zaproponować pytanie/odpowiedź — bez dodawania faktów spoza
fragmentu (ta sama filozofia co zakaz generowania liczb przez LLM: model
tłumaczy i porządkuje to, co dostał, a nie wymyśla).
"""

from google import genai
from google.genai import errors, types

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


def zaproponuj_fiszke(fragment_tekstu: str) -> dict:
    """Zwraca {"pytanie": str, "odpowiedz": str} na podstawie fragmentu tekstu.

    Podnosi BladGemini przy błędzie sieci/API albo gdy odpowiedzi nie da się
    sparsować — wywołujący (routes.py) zamienia to na czytelny komunikat
    błędu w JSON, bez blokowania ręcznego uzupełnienia formularza.
    """
    if not Config.GEMINI_API_KEY:
        raise BladGemini("Brak GEMINI_API_KEY w konfiguracji (.env).")

    try:
        client = genai.Client(api_key=Config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=fragment_tekstu,
            config=types.GenerateContentConfig(
                system_instruction=PROMPT_SYSTEMOWY,
            ),
        )
    except errors.APIError as e:
        raise BladGemini(f"Błąd Gemini API: {e.message}") from e

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
