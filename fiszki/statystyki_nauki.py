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
                  SUM(wynik = 'umiem') AS umiem
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
        "seria_dni": _seria(db, dzis),
        "aktywnosc": aktywnosc,
        "powtorki_30_dni": wszystkie,
        "skutecznosc_proc": 100 * umiem / wszystkie if wszystkie else None,
        "opanowane": opanowane,
        "dzis": po_dniu.get(dzis.isoformat(), (0, 0))[0],
    }


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
