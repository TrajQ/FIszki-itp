"""Statystyki nauki liczone z dziennika powtórek (tabela dziennik_powtorek).

Wszystkie liczby pochodzą z bazy — to podsumowanie tego, co student
faktycznie powtórzył, a nie ocena modelu.
"""

import sqlite3
from datetime import date, timedelta

DNI_AKTYWNOSCI = 30


def policz(db: sqlite3.Connection, dzis: date) -> dict:
    start = dzis - timedelta(days=DNI_AKTYWNOSCI - 1)
    wiersze = db.execute(
        """SELECT data,
                  COUNT(*) AS wszystkie,
                  SUM(wynik IN ('umiem', 'trudne')) AS umiem
           FROM dziennik_powtorek WHERE data >= ? GROUP BY data""",
        (start.isoformat(),),
    ).fetchall()
    po_dniu = {w["data"]: (w["wszystkie"], w["umiem"]) for w in wiersze}

    aktywnosc = []
    for i in range(DNI_AKTYWNOSCI):
        dzien = (start + timedelta(days=i)).isoformat()
        aktywnosc.append({"data": dzien, "powtorki": po_dniu.get(dzien, (0, 0))[0]})

    wszystkie = sum(w for w, _ in po_dniu.values())
    umiem = sum(u for _, u in po_dniu.values())
    opanowane = db.execute("SELECT COUNT(*) FROM powtorki WHERE pudelko = 5").fetchone()[0]

    return {
        "prognoza": prognoza(db, dzis),
        "seria_dni": _seria(db, dzis),
        "aktywnosc": aktywnosc,
        "powtorki_30_dni": wszystkie,
        "skutecznosc_proc": 100 * umiem / wszystkie if wszystkie else None,
        "opanowane": opanowane,
        "dzis": po_dniu.get(dzis.isoformat(), (0, 0))[0],
        "krzywa": krzywa_zapominania(db),
    }


# ---------- krzywa zapominania (ETAP 186) ----------
# Dla każdej powtórki: ile dni minęło od poprzedniej powtórki tej samej
# fiszki i czy fiszka była zapamiętana („umiem” albo „trudne”). Udział
# zapamiętanych w przedziałach odstępu to własna krzywa zapominania
# (Ebbinghaus) — z prawdziwych odpowiedzi, nie z modelu.

PRZEDZIALY_DNI = [(1, 1), (2, 3), (4, 7), (8, 14), (15, 30), (31, None)]
MIN_POWTOREK_PRZEDZIALU = 5


# ETAP 226: dziennik tylko przybywa (nic go nie zmienia ani nie usuwa), więc
# krzywa zależy od pliku bazy, ostatniego id i liczby wpisów — liczymy ją
# ponownie dopiero po nowych odpowiedziach.
_pamiec_krzywej: dict = {}


def krzywa_zapominania(db: sqlite3.Connection) -> list[dict]:
    plik = db.execute("PRAGMA database_list").fetchone()[2]
    stan = tuple(db.execute("SELECT MAX(id), COUNT(*) FROM dziennik_powtorek").fetchone())
    klucz = (plik, stan) if plik else None  # baza w pamięci (testy) — bez zapamiętywania
    if klucz and klucz in _pamiec_krzywej:
        return _pamiec_krzywej[klucz]
    wynik = _licz_krzywa(db)
    if klucz:
        _pamiec_krzywej.clear()  # jedna baza fiszek — trzymamy tylko ostatni wynik
        _pamiec_krzywej[klucz] = wynik
    return wynik


def _licz_krzywa(db: sqlite3.Connection) -> list[dict]:
    # ETAP 226: odstęp od poprzedniej powtórki tej samej fiszki liczy SQLite
    # (funkcja okna LAG) — wcześniej pętla w Pythonie po całym dzienniku
    # (przy 300 tys. odpowiedzi ok. 1,4 s przy każdym wejściu na stronę Fiszek).
    wiersze = db.execute(
        """WITH odstepy AS (
               SELECT CAST(ROUND(julianday(data) - julianday(LAG(data) OVER (PARTITION BY fiszka_id ORDER BY data, id))) AS INTEGER) AS dni,
                      wynik IN ('umiem', 'trudne') AS zapamietana
               FROM dziennik_powtorek)
           SELECT dni, COUNT(*), SUM(zapamietana) FROM odstepy WHERE dni >= 1 GROUP BY dni"""
    ).fetchall()  # 0 dni (powtórka w tej samej sesji) i pierwsza powtórka fiszki (NULL) pomijamy
    licznik = [[0, 0] for _ in PRZEDZIALY_DNI]  # [powtórki, zapamiętane]
    for dni, n, z in wiersze:
        for i, (od, do) in enumerate(PRZEDZIALY_DNI):
            if dni >= od and (do is None or dni <= do):
                licznik[i][0] += n
                licznik[i][1] += z
                break
    return [{"od": od, "do": do, "powtorki": n, "zapamietane": z,
             "procent": 100 * z / n if n >= MIN_POWTOREK_PRZEDZIALU else None}
            for (od, do), (n, z) in zip(PRZEDZIALY_DNI, licznik)]


DNI_PROGNOZY = 7


def prognoza(db: sqlite3.Connection, dzis: date) -> list[dict]:
    """Ile fiszek przypada do powtórki w każdym z najbliższych 7 dni.

    Zaległe i nowe (bez stanu) liczymy na dziś — tyle czeka od razu.
    """
    koniec = dzis + timedelta(days=DNI_PROGNOZY - 1)
    wiersze = db.execute(
        """SELECT MAX(COALESCE(powtorki.nastepna_powtorka, :dzis), :dzis) AS dzien, COUNT(*) AS ile
           FROM fiszki LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id
           WHERE COALESCE(powtorki.nastepna_powtorka, :dzis) <= :koniec
           GROUP BY 1""",
        {"dzis": dzis.isoformat(), "koniec": koniec.isoformat()},
    ).fetchall()
    po_dniu = {w["dzien"]: w["ile"] for w in wiersze}
    return [
        {"data": (d := dzis + timedelta(days=i)).isoformat(), "dzien_tygodnia": d.weekday(), "fiszki": po_dniu.get(d.isoformat(), 0)}
        for i in range(DNI_PROGNOZY)
    ]


def _seria(db: sqlite3.Connection, dzis: date) -> int:
    """Ile kolejnych dni z co najmniej jedną powtórką, licząc wstecz od dziś.

    Jeśli dziś jeszcze nic nie było, seria z wczoraj się nie przerywa —
    dzień się jeszcze nie skończył.
    """
    dni = {w[0] for w in db.execute("SELECT DISTINCT data FROM dziennik_powtorek")}
    dzien = dzis if dzis.isoformat() in dni else dzis - timedelta(days=1)
    seria = 0
    while dzien.isoformat() in dni:
        seria += 1
        dzien -= timedelta(days=1)
    return seria
