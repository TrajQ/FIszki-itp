"""Quiz ABCD z własnych fiszek i lista najtrudniejszych fiszek.

Błędne odpowiedzi (dystraktory) to odpowiedzi z INNYCH fiszek — najpierw
z tego samego PDF-a (podobny temat, trudniej zgadnąć), potem z reszty.
Nic nie jest generowane przez model: quiz składa się wyłącznie z treści,
którą student sam zatwierdził.
"""

import random
import sqlite3

LICZBA_ODPOWIEDZI = 4
MIN_FISZEK = LICZBA_ODPOWIEDZI  # żeby były 3 różne błędne odpowiedzi


class ZaMaloFiszek(ValueError):
    pass


def _klucz(tekst: str) -> str:
    return " ".join(tekst.casefold().split())


def uloz_quiz(
    zakres: list[dict], pula: list[dict], liczba_pytan: int, losowanie: random.Random
) -> list[dict]:
    """Pytania quizu.

    zakres — fiszki, z których losujemy pytania (np. jeden PDF),
    pula — wszystkie fiszki, z których bierzemy błędne odpowiedzi.
    Fiszka = {id, pdf_id, pytanie, odpowiedz, strona, ...}.
    """
    unikalne_odpowiedzi = {_klucz(f["odpowiedz"]) for f in pula}
    if len(pula) < MIN_FISZEK or len(unikalne_odpowiedzi) < LICZBA_ODPOWIEDZI:
        raise ZaMaloFiszek(
            f"Do quizu potrzeba co najmniej {MIN_FISZEK} fiszek z różnymi odpowiedziami."
        )

    fiszki = pula
    wybrane = losowanie.sample(zakres, min(liczba_pytan, len(zakres)))
    pytania = []
    for f in wybrane:
        poprawna = _klucz(f["odpowiedz"])
        z_tego_pdf = [x for x in fiszki if x["pdf_id"] == f["pdf_id"]]
        z_innych = [x for x in fiszki if x["pdf_id"] != f["pdf_id"]]
        losowanie.shuffle(z_tego_pdf)
        losowanie.shuffle(z_innych)

        bledne, uzyte = [], {poprawna}
        for kandydat in z_tego_pdf + z_innych:
            k = _klucz(kandydat["odpowiedz"])
            if k not in uzyte:
                bledne.append(kandydat["odpowiedz"])
                uzyte.add(k)
            if len(bledne) == LICZBA_ODPOWIEDZI - 1:
                break

        odpowiedzi = bledne + [f["odpowiedz"]]
        losowanie.shuffle(odpowiedzi)
        pytania.append(
            {
                "fiszka_id": f["id"],
                "pdf_id": f["pdf_id"],
                "strona": f["strona"],
                "pytanie": f["pytanie"],
                "odpowiedzi": odpowiedzi,
                "poprawna": odpowiedzi.index(f["odpowiedz"]),
            }
        )
    return pytania


def najtrudniejsze(db: sqlite3.Connection, limit: int = 5) -> list[dict]:
    """Fiszki z największą liczbą odpowiedzi „nie umiem” w dzienniku powtórek."""
    # ETAP 226: najpierw zliczenie w dzienniku (indeks po fiszce), potem złączenie
    wiersze = db.execute(
        """SELECT fiszki.id, fiszki.pdf_id, fiszki.pytanie, fiszki.strona,
                  pdfy.nazwa_oryginalna, d.bledy, d.proby
           FROM (SELECT fiszka_id, SUM(wynik = 'nie_umiem') AS bledy, COUNT(*) AS proby
                 FROM dziennik_powtorek GROUP BY fiszka_id HAVING bledy > 0) d
           JOIN fiszki ON fiszki.id = d.fiszka_id
           JOIN pdfy ON pdfy.id = fiszki.pdf_id
           ORDER BY d.bledy DESC, 1.0 * d.bledy / d.proby DESC, fiszki.id
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(w) for w in wiersze]
