"""System powtórek Leitnera — 5 pudełek, stałe odstępy.

Każda fiszka jest w jednym z pudełek 1–5. Odpowiedź „umiem” przesuwa ją
do następnego pudełka i odsuwa kolejną powtórkę o coraz dłuższy odstęp.
Odpowiedź „nie umiem” cofa ją do pudełka 1 z powtórką jeszcze dziś —
wraca, dopóki nie zostanie opanowana.

Odpowiedź „trudne” (ETAP 39) to „pamiętam, ale z wysiłkiem”: fiszka
zostaje w swoim pudełku i wraca jutro — nie awansuje, ale też nie spada
na początek.

Fiszka bez wpisu w tabeli `powtorki` (np. utworzona przed ETAPem 6) jest
traktowana jak nowa: pudełko 1, do powtórki od razu.
"""

from datetime import date, timedelta

PUDELKO_MIN = 1
PUDELKO_MAX = 5

# Po awansie do pudełka N następna powtórka za ODSTEPY_DNI[N] dni.
ODSTEPY_DNI = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}

WYNIKI = ("umiem", "trudne", "nie_umiem")
# Odpowiedzi, przy których student pamiętał (do skuteczności w statystykach).
WYNIKI_ZAPAMIETANE = ("umiem", "trudne")
ODSTEP_TRUDNE_DNI = 1


def dzisiaj() -> date:
    """Osobna funkcja, żeby testy mogły podmienić „dzisiaj”."""
    return date.today()


def nastepny_stan(pudelko: int, wynik: str, dzien: date) -> tuple[int, date]:
    """Zwraca (nowe_pudelko, data_nastepnej_powtorki) po odpowiedzi."""
    if wynik not in WYNIKI:
        raise ValueError(f"Nieznany wynik powtórki: {wynik}")

    if wynik == "nie_umiem":
        return PUDELKO_MIN, dzien
    if wynik == "trudne":
        return pudelko, dzien + timedelta(days=ODSTEP_TRUDNE_DNI)

    nowe = min(pudelko + 1, PUDELKO_MAX)
    return nowe, dzien + timedelta(days=ODSTEPY_DNI[nowe])


def przeplec(fiszki: list[dict], grupa) -> list[dict]:
    """ETAP 206: przeplatanie tematów — kolejność, w której sąsiednie fiszki
    są (gdy się da) z różnych grup. W każdej grupie zostaje kolejność
    wejściowa (np. najpierw niższe pudełka). Krok: z grup innych niż
    poprzednia bierzemy tę, w której zostało najwięcej fiszek (remis — ta,
    której następna fiszka była wcześniej na liście); dzięki temu duża grupa
    nie zostaje sama na końcu."""
    kolejki: dict = {}
    for i, f in enumerate(fiszki):
        kolejki.setdefault(grupa(f), []).append((i, f))
    wynik, poprzednia = [], object()
    while kolejki:
        kandydaci = [g for g in kolejki if g != poprzednia] or list(kolejki)
        g = min(kandydaci, key=lambda k: (-len(kolejki[k]), kolejki[k][0][0]))
        wynik.append(kolejki[g].pop(0)[1])
        if not kolejki[g]:
            del kolejki[g]
        poprzednia = g
    return wynik
