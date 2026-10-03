"""Terminy egzaminów i postęp przygotowania (ETAP 51).

Egzamin ma nazwę, datę i zakres: temat, jeden plik PDF albo wszystkie
fiszki. Postęp liczymy z pudełek Leitnera:

- „utrwalona” fiszka = w pudełku 3 lub wyższym, czyli co najmniej dwa
  razy z rzędu oceniona „umiem” od ostatniego „nie umiem”,
- plan = ile nieutrwalonych fiszek dziennie trzeba przerobić, żeby każdą
  zobaczyć przed egzaminem (proste dzielenie — podpowiedź, nie wyrocznia).

Prognoza (ETAP 224): ile fiszek będzie utrwalonych w dniu egzaminu, jeśli
codziennie przerabiasz wszystko, co wypada do powtórki. Liczona dzień po
dniu z harmonogramu Leitnera (powtorki.py) i z Twoich odpowiedzi z
dziennika — udziały „umiem”, „trudne” i „nie umiem” z ostatnich dni.

Liczby liczy ten moduł z bazy — nic nie przychodzi od modelu językowego.
"""

import math
import sqlite3
from collections import Counter
from datetime import date, timedelta

from .powtorki import ODSTEP_TRUDNE_DNI, ODSTEPY_DNI, PUDELKO_MAX

PUDELKO_UTRWALONE = 3
MAKS_DLUGOSC_NAZWY = 80


class BladEgzaminu(ValueError):
    """Niepoprawne dane egzaminu."""


def dodaj(db: sqlite3.Connection, nazwa: str, data: str, temat: str | None, pdf_id: int | None, dzis: date) -> int:
    nazwa = " ".join((nazwa or "").split())
    if not nazwa:
        raise BladEgzaminu("Podaj nazwę egzaminu, np. „Kolokwium z planowania”.")
    if len(nazwa) > MAKS_DLUGOSC_NAZWY:
        raise BladEgzaminu(f"Nazwa może mieć najwyżej {MAKS_DLUGOSC_NAZWY} znaków.")
    try:
        termin = date.fromisoformat(data or "")
    except ValueError:
        raise BladEgzaminu("Podaj datę egzaminu.") from None
    if termin < dzis:
        raise BladEgzaminu("Data egzaminu już minęła.")
    if temat and pdf_id is not None:
        raise BladEgzaminu("Zakres to temat albo plik, nie oba naraz.")
    kursor = db.execute(
        "INSERT INTO egzaminy (nazwa, data, temat, pdf_id) VALUES (?, ?, ?, ?)",
        (nazwa, termin.isoformat(), temat or None, pdf_id),
    )
    db.commit()
    return kursor.lastrowid


def usun(db: sqlite3.Connection, egzamin_id: int) -> None:
    db.execute("DELETE FROM egzaminy WHERE id = ?", (egzamin_id,))
    db.commit()


def _pudelka_w_zakresie(db: sqlite3.Connection, temat: str | None, pdf_id: int | None) -> list[int]:
    warunki, parametry = [], {}
    if temat:
        warunki.append("fiszki.id IN (SELECT fiszka_id FROM tematy_fiszek WHERE temat = :temat)")
        parametry["temat"] = temat
    if pdf_id is not None:
        warunki.append("fiszki.pdf_id = :pdf_id")
        parametry["pdf_id"] = pdf_id
    gdzie = (" WHERE " + " AND ".join(warunki)) if warunki else ""
    return [
        w[0]
        for w in db.execute(
            "SELECT COALESCE(powtorki.pudelko, 1) FROM fiszki LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id" + gdzie,
            parametry,
        )
    ]


# ---------- prognoza gotowości (ETAP 224) ----------

DNI_DZIENNIKA = 60  # z ilu ostatnich dni bierzemy udziały odpowiedzi
MIN_ODPOWIEDZI = 30  # mniej — prognoza „przy Twojej skuteczności” byłaby losowa
# po „nie umiem” fiszka wraca tego samego dnia, aż padnie „umiem” → pudełko 2
PUDELKO_PO_POWROCIE = 2


def udzialy_odpowiedzi(db: sqlite3.Connection, dzis: date) -> dict | None:
    """Udziały odpowiedzi z ostatnich DNI_DZIENNIKA dni albo None, gdy
    odpowiedzi jest mniej niż MIN_ODPOWIEDZI."""
    od = (dzis - timedelta(days=DNI_DZIENNIKA)).isoformat()
    liczby = dict(db.execute("SELECT wynik, COUNT(*) FROM dziennik_powtorek WHERE data >= ? GROUP BY wynik", (od,)).fetchall())
    razem = sum(liczby.values())
    if razem < MIN_ODPOWIEDZI:
        return None
    return {"umiem": liczby.get("umiem", 0) / razem, "trudne": liczby.get("trudne", 0) / razem,
            "nie_umiem": liczby.get("nie_umiem", 0) / razem, "odpowiedzi": razem}


def _prawdopodobienstwo_utrwalenia(pudelko: int, za_dni: int, ostatni_dzien: int, u: dict) -> tuple[float, list[float]]:
    """Jedna fiszka (pudełko, powtórka za `za_dni` dni; zaległa = 0) →
    (szansa, że w dniu egzaminu jest w pudełku ≥ 3, oczekiwane powtórki
    w kolejnych dniach). Dni nauki: 0 … ostatni_dzien."""
    stany = {(pudelko, max(za_dni, 0)): 1.0}
    powtorki = [0.0] * (ostatni_dzien + 1)
    for t in range(ostatni_dzien + 1):
        nowe: dict = {}
        for (b, termin), p in stany.items():
            if termin > t:
                nowe[(b, termin)] = nowe.get((b, termin), 0.0) + p
                continue
            powtorki[t] += p * (1 + u["nie_umiem"])  # po „nie umiem” — jeszcze raz tego dnia
            wyjscia = [((min(b + 1, PUDELKO_MAX), t + ODSTEPY_DNI[min(b + 1, PUDELKO_MAX)]), u["umiem"]),
                       ((b, t + ODSTEP_TRUDNE_DNI), u["trudne"]),
                       ((PUDELKO_PO_POWROCIE, t + ODSTEPY_DNI[PUDELKO_PO_POWROCIE]), u["nie_umiem"])]
            for stan, q in wyjscia:
                if q:
                    nowe[stan] = nowe.get(stan, 0.0) + p * q
        stany = nowe
    return sum(p for (b, _), p in stany.items() if b >= PUDELKO_UTRWALONE), powtorki


def prognoza(stany: list[tuple[int, int]], dni_do_egzaminu: int, udzialy: dict | None) -> dict:
    """stany: [(pudełko, za ile dni powtórka)] fiszek z zakresu egzaminu.

    Dni nauki: od dziś do dnia przed egzaminem (egzamin dziś — tylko dziś).
    `maksimum` — same „umiem”: więcej się nie da (odstępy Leitnera);
    `oczekiwane` — przy udziałach odpowiedzi z dziennika (None, gdy za mało
    odpowiedzi). Zakłada codzienne przerabianie wszystkiego, co wypada."""
    ostatni_dzien = max(dni_do_egzaminu - 1, 0)
    grupy = Counter(stany)
    wynik = {"dni_nauki": ostatni_dzien + 1, "fiszki": len(stany)}
    zestawy = {"maksimum": {"umiem": 1.0, "trudne": 0.0, "nie_umiem": 0.0}}
    if udzialy:
        zestawy["oczekiwane"] = udzialy
    for nazwa, u in zestawy.items():
        suma, dzienne = 0.0, [0.0] * (ostatni_dzien + 1)
        for (b, za_dni), ile in grupy.items():
            p, powtorki = _prawdopodobienstwo_utrwalenia(b, za_dni, ostatni_dzien, u)
            suma += p * ile
            dzienne = [a + ile * x for a, x in zip(dzienne, powtorki)]
        wynik[nazwa] = round(suma)
        wynik[nazwa + "_proc"] = round(100 * suma / len(stany)) if stany else None
        wynik[nazwa + "_powtorek_dziennie"] = round(max(dzienne)) if dzienne else 0
    wynik["udzialy"] = udzialy
    return wynik


def _stany_w_zakresie(db: sqlite3.Connection, temat: str | None, pdf_id: int | None, dzis: date) -> list[tuple[int, int]]:
    """(pudełko, za ile dni powtórka) fiszek zakresu; fiszka bez wpisu — nowa, do powtórki dziś."""
    warunki, parametry = [], {}
    if temat:
        warunki.append("fiszki.id IN (SELECT fiszka_id FROM tematy_fiszek WHERE temat = :temat)")
        parametry["temat"] = temat
    if pdf_id is not None:
        warunki.append("fiszki.pdf_id = :pdf_id")
        parametry["pdf_id"] = pdf_id
    gdzie = (" WHERE " + " AND ".join(warunki)) if warunki else ""
    wynik = []
    for pudelko, termin in db.execute(
        "SELECT COALESCE(powtorki.pudelko, 1), powtorki.nastepna_powtorka FROM fiszki LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id" + gdzie,
        parametry,
    ):
        za_dni = (date.fromisoformat(termin[:10]) - dzis).days if termin else 0
        wynik.append((pudelko, za_dni))
    return wynik


def postep(pudelka: list[int], dni_do_egzaminu: int) -> dict:
    wszystkie = len(pudelka)
    utrwalone = sum(1 for p in pudelka if p >= PUDELKO_UTRWALONE)
    do_nauki = wszystkie - utrwalone
    # Dziś też jest dniem nauki, więc egzamin jutro = 1 dzień, dziś = 1 dzień.
    dni_nauki = max(dni_do_egzaminu, 1)
    return {
        "fiszki": wszystkie,
        "utrwalone": utrwalone,
        "procent": round(100 * utrwalone / wszystkie) if wszystkie else None,
        "do_nauki": do_nauki,
        "dziennie": math.ceil(do_nauki / dni_nauki) if do_nauki else 0,
    }


def lista(db: sqlite3.Connection, dzis: date, z_prognoza: bool = True) -> list[dict]:
    """Egzaminy od najbliższego, z postępem. Minione — na końcu.
    z_prognoza=False — bez prognozy (kalendarz na stronie głównej jej nie
    pokazuje, a przy dużej bazie to większość czasu, ETAP 226)."""
    wynik = []
    udzialy = udzialy_odpowiedzi(db, dzis) if z_prognoza else None
    for w in db.execute(
        """SELECT egzaminy.*, pdfy.nazwa_oryginalna FROM egzaminy
           LEFT JOIN pdfy ON pdfy.id = egzaminy.pdf_id ORDER BY data, id"""
    ):
        egzamin = dict(w)
        dni = (date.fromisoformat(egzamin["data"]) - dzis).days
        egzamin["dni"] = dni
        egzamin["minal"] = dni < 0
        egzamin.update(postep(_pudelka_w_zakresie(db, egzamin["temat"], egzamin["pdf_id"]), dni))
        if z_prognoza and not egzamin["minal"] and egzamin["fiszki"]:
            egzamin["prognoza"] = prognoza(_stany_w_zakresie(db, egzamin["temat"], egzamin["pdf_id"], dzis), dni, udzialy)
        wynik.append(egzamin)
    return sorted(wynik, key=lambda e: (e["minal"], e["data"]))


def utrwalone_w_plikach(db: sqlite3.Connection) -> dict[int, int]:
    """{pdf_id: liczba utrwalonych fiszek} — do paska postępu przy pliku."""
    return {
        pdf_id: ile
        for pdf_id, ile in db.execute(
            """SELECT fiszki.pdf_id, COUNT(*) FROM fiszki
               JOIN powtorki ON powtorki.fiszka_id = fiszki.id
               WHERE powtorki.pudelko >= ? GROUP BY fiszki.pdf_id""",
            (PUDELKO_UTRWALONE,),
        )
    }
