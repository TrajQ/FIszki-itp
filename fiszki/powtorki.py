"""System powtórek Leitnera — 5 pudełek, stałe odstępy.

Każda fiszka jest w jednym z pudełek 1–5. Odpowiedź „umiem” przesuwa ją
do następnego pudełka i odsuwa kolejną powtórkę o coraz dłuższy odstęp.
Odpowiedź „nie umiem” cofa ją do pudełka 1 z powtórką jeszcze dziś —
wraca, dopóki nie zostanie opanowana.

Fiszka bez wpisu w tabeli `powtorki` (np. utworzona przed ETAPem 6) jest
traktowana jak nowa: pudełko 1, do powtórki od razu.
"""

from datetime import date, timedelta

PUDELKO_MIN = 1
PUDELKO_MAX = 5

# Po awansie do pudełka N następna powtórka za ODSTEPY_DNI[N] dni.
ODSTEPY_DNI = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}

WYNIKI = ("umiem", "nie_umiem")


def dzisiaj() -> date:
    """Osobna funkcja, żeby testy mogły podmienić „dzisiaj”."""
    return date.today()


def nastepny_stan(pudelko: int, wynik: str, dzien: date) -> tuple[int, date]:
    """Zwraca (nowe_pudelko, data_nastepnej_powtorki) po odpowiedzi."""
    if wynik not in WYNIKI:
        raise ValueError(f"Nieznany wynik powtórki: {wynik}")

    if wynik == "nie_umiem":
        return PUDELKO_MIN, dzien

    nowe = min(pudelko + 1, PUDELKO_MAX)
    return nowe, dzien + timedelta(days=ODSTEPY_DNI[nowe])
