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


def krzywa_zapominania(db: sqlite3.Connection) -> list[dict]:
    wiersze = db.execute("SELECT fiszka_id, data, wynik FROM dziennik_powtorek ORDER BY fiszka_id, data, id").fetchall()
    licznik = [[0, 0] for _ in PRZEDZIALY_DNI]  # [powtórki, zapamiętane]
    poprzednia = (None, None)
    for w in wiersze:
        if poprzednia[0] == w["fiszka_id"]:
            dni = (date.fromisoformat(w["data"]) - date.fromisoformat(poprzednia[1])).days
            for i, (od, do) in enumerate(PRZEDZIALY_DNI):
                if dni >= od and (do is None or dni <= do):  # 0 dni (powtórka w tej samej sesji) pomijamy
                    licznik[i][0] += 1
                    licznik[i][1] += w["wynik"] in ("umiem", "trudne")
                    break
        poprzednia = (w["fiszka_id"], w["data"])
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
