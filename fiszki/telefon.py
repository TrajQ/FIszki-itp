"""Powtórki na telefonie bez internetu (ETAP 74).

Eksport: samodzielny plik HTML z fiszkami i ich stanem (pudełko, data
następnej powtórki) oraz zasadami Leitnera z powtorki.py — telefon
planuje powtórki tak samo jak Warsztat, także przez kilka dni bez sieci.

Import: plik JSON z wynikami z telefonu. Wyniki stosujemy w kolejności
czasu, z datą z telefonu (statystyki pokazują właściwe dni). Zasady:
- wynik o znanym uid pomijamy (ponowny import tego samego pliku),
- fiszka usunięta w międzyczasie — wynik pomijamy,
- fiszka powtarzana w Warsztacie później niż na telefonie — nowszy stan
  zostaje, wynik z telefonu trafia tylko do dziennika (statystyk).
"""

import re
import secrets
from datetime import date, timedelta

from . import obrazy, powtorki

FORMAT = "warsztat-powtorki"
MAKS_WYNIKOW = 20000


class BladPliku(ValueError):
    """Plik wyników nie pochodzi z tej instalacji albo jest niepoprawny."""


def identyfikator_instalacji(db) -> str:
    wiersz = db.execute("SELECT wartosc FROM ustawienia WHERE klucz = 'instalacja'").fetchone()
    if wiersz:
        return wiersz["wartosc"]
    nowy = secrets.token_urlsafe(12)
    db.execute("INSERT INTO ustawienia (klucz, wartosc) VALUES ('instalacja', ?)", (nowy,))
    db.commit()
    return nowy


def zasady() -> dict:
    """Zasady Leitnera dla telefonu — jedno źródło prawdy: powtorki.py."""
    return {
        "pudelko_min": powtorki.PUDELKO_MIN,
        "pudelko_max": powtorki.PUDELKO_MAX,
        "odstepy_dni": {str(k): v for k, v in powtorki.ODSTEPY_DNI.items()},
        "odstep_trudne_dni": powtorki.ODSTEP_TRUDNE_DNI,
    }


def fiszki_do_eksportu(db, dzis: date, temat: str | None, pdf_id: int | None) -> list[dict]:
    warunki, parametry = ["1 = 1"], {"dzis": dzis.isoformat()}
    if temat:
        warunki.append("fiszki.id IN (SELECT fiszka_id FROM tematy_fiszek WHERE temat = :temat)")
        parametry["temat"] = temat
    if pdf_id is not None:
        warunki.append("fiszki.pdf_id = :pdf_id")
        parametry["pdf_id"] = pdf_id
    wiersze = db.execute(
        f"""SELECT fiszki.id, fiszki.pytanie, fiszki.odpowiedz, fiszki.strona, pdfy.nazwa_oryginalna AS zrodlo,
                   COALESCE(powtorki.pudelko, 1) AS pudelko,
                   COALESCE(powtorki.nastepna_powtorka, :dzis) AS nastepna
            FROM fiszki JOIN pdfy ON pdfy.id = fiszki.pdf_id
            LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id
            WHERE {" AND ".join(warunki)} ORDER BY fiszki.id""",
        parametry,
    ).fetchall()
    # ETAP 154: wycinek rysunku osadzony w pliku (telefon działa bez połączenia z Warsztatem)
    obrazki = obrazy.obrazy_fiszek(db)
    return [{**dict(w), "obraz": obrazy.jako_data_url(obrazki[w["id"]]) if w["id"] in obrazki else None} for w in wiersze]


def odczytaj_wyniki(dane, instalacja: str, dzis: date) -> list[dict]:
    """Plik z telefonu → posortowane wyniki {uid, fiszka_id, wynik, data}."""
    if not isinstance(dane, dict) or dane.get("format") != FORMAT:
        raise BladPliku("To nie jest plik z powtórek fiszek na telefonie.")
    if dane.get("wersja") != 1:
        raise BladPliku("Nieobsługiwana wersja pliku — pobierz fiszki na telefon jeszcze raz.")
    if dane.get("instalacja") != instalacja:
        raise BladPliku("Plik pochodzi z innej instalacji Warsztatu (inne numery fiszek).")
    surowe = dane.get("wyniki")
    if not isinstance(surowe, list):
        raise BladPliku("Plik nie zawiera listy wyników.")
    if len(surowe) > MAKS_WYNIKOW:
        raise BladPliku(f"Najwyżej {MAKS_WYNIKOW} wyników w jednym pliku.")
    wynik = []
    for i, w in enumerate(surowe, start=1):
        if not isinstance(w, dict):
            raise BladPliku(f"Wynik {i}: zły format.")
        uid, fiszka_id, ocena, dzien = w.get("uid"), w.get("fiszka_id"), w.get("wynik"), w.get("data")
        if not isinstance(uid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", uid):
            raise BladPliku(f"Wynik {i}: brak identyfikatora.")
        if not isinstance(fiszka_id, int) or isinstance(fiszka_id, bool):
            raise BladPliku(f"Wynik {i}: zły numer fiszki.")
        if ocena not in powtorki.WYNIKI:
            raise BladPliku(f"Wynik {i}: nieznana ocena.")
        try:
            data = date.fromisoformat(str(dzien))
        except ValueError:
            raise BladPliku(f"Wynik {i}: zła data.") from None
        if data > dzis + timedelta(days=1):  # zapas na strefę czasu telefonu
            raise BladPliku(f"Wynik {i}: data z przyszłości ({data}) — sprawdź zegar telefonu.")
        wynik.append({"uid": uid, "fiszka_id": fiszka_id, "wynik": ocena, "data": data, "czas": str(w.get("czas") or "")})
    return sorted(wynik, key=lambda w: (w["data"], w["czas"]))


def zastosuj(db, wyniki: list[dict]) -> dict:
    """Wyniki → pudełka i dziennik. Zwraca liczby: zastosowane, powtórzone
    (już były), bez_fiszki, tylko_statystyki (Warsztat miał nowszą powtórkę)."""
    liczby = {"zastosowane": 0, "powtorzone": 0, "bez_fiszki": 0, "tylko_statystyki": 0}
    for w in wyniki:
        if db.execute("SELECT 1 FROM powtorki_z_telefonu WHERE uid = ?", (w["uid"],)).fetchone():
            liczby["powtorzone"] += 1
            continue
        if db.execute("SELECT 1 FROM fiszki WHERE id = ?", (w["fiszka_id"],)).fetchone() is None:
            liczby["bez_fiszki"] += 1
            continue
        dzien = w["data"].isoformat()
        stan = db.execute("SELECT pudelko, ostatnia_powtorka FROM powtorki WHERE fiszka_id = ?", (w["fiszka_id"],)).fetchone()
        if stan and stan["ostatnia_powtorka"] and stan["ostatnia_powtorka"] > dzien:
            liczby["tylko_statystyki"] += 1
        else:
            pudelko = stan["pudelko"] if stan else powtorki.PUDELKO_MIN
            nowe, nastepna = powtorki.nastepny_stan(pudelko, w["wynik"], w["data"])
            db.execute(
                """INSERT INTO powtorki (fiszka_id, pudelko, nastepna_powtorka, liczba_powtorek, ostatnia_powtorka)
                   VALUES (?, ?, ?, 1, ?)
                   ON CONFLICT(fiszka_id) DO UPDATE SET
                       pudelko = excluded.pudelko,
                       nastepna_powtorka = excluded.nastepna_powtorka,
                       liczba_powtorek = powtorki.liczba_powtorek + 1,
                       ostatnia_powtorka = excluded.ostatnia_powtorka""",
                (w["fiszka_id"], nowe, nastepna.isoformat(), dzien),
            )
            liczby["zastosowane"] += 1
        db.execute("INSERT INTO dziennik_powtorek (fiszka_id, data, wynik) VALUES (?, ?, ?)", (w["fiszka_id"], dzien, w["wynik"]))
        db.execute("INSERT INTO powtorki_z_telefonu (uid, fiszka_id, data) VALUES (?, ?, ?)", (w["uid"], w["fiszka_id"], dzien))
    db.commit()
    return liczby
