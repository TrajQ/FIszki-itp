"""Przeniesienie notatek i „Moich przepisów” na nowszy tekst aktu (ETAP 208).

Po pobraniu nowszego tekstu jednolitego (ETAP 101) notatki i zbiór
„Moje przepisy” zostają przy starym akcie — są przypięte do jego
jednostek. Tu przenosimy je na jednostki nowego aktu o tym samym
oznaczeniu („art. 15”, „§ 4”, „art. 10a”):

- notatka trafia do jednostki o tym samym oznaczeniu; gdy tam już jest
  notatka, stara jest dopisywana pod nią (nic nie ginie),
- jednostka z „Moich przepisów” jest dodawana do zbioru w nowym akcie,
- oznaczenia, których w nowym tekście nie ma (np. uchylone artykuły)
  albo które są w nim kilka razy, są wypisane w raporcie — bez zgadywania,
- jednostki, których tekst się zmienił, są wypisane, żeby notatkę
  przeczytać jeszcze raz.

Stary akt zostaje bez zmian (można go usunąć ręcznie).
"""

import sqlite3
from datetime import datetime

from .baza import MAKS_MOICH, MAKS_NOTATKI


def _klucz(oznaczenie: str) -> str:
    return " ".join(oznaczenie.lower().split())


def _jednostki(db: sqlite3.Connection, akt_id: int) -> list[sqlite3.Row]:
    return db.execute("SELECT id, oznaczenie, tekst FROM jednostki WHERE akt_id = ? ORDER BY kolejnosc", (akt_id,)).fetchall()


def przenies(db: sqlite3.Connection, z_aktu: int, do_aktu: int, nazwa_starego: str) -> dict:
    """Przenosi notatki i „Moje przepisy” z aktu z_aktu na do_aktu → raport."""
    if z_aktu == do_aktu:
        raise ValueError("Wybierz inny akt niż bieżący.")
    nowe: dict[str, list] = {}
    for j in _jednostki(db, do_aktu):
        nowe.setdefault(_klucz(j["oznaczenie"]), []).append(j)
    stare = {j["id"]: j for j in _jednostki(db, z_aktu)}
    notatki = db.execute("SELECT jednostka_id, tekst FROM notatki WHERE akt_id = ?", (z_aktu,)).fetchall()
    moje = [w[0] for w in db.execute("SELECT jednostka_id FROM moje_przepisy WHERE akt_id = ?", (z_aktu,))]
    teraz = datetime.now().isoformat(timespec="seconds")
    raport = {"notatki": 0, "moje": 0, "bez_odpowiednika": [], "niejednoznaczne": [], "zmieniony_tekst": [], "pelny_zbior": False}

    def odpowiednik(jednostka_id: int):
        j = stare[jednostka_id]
        kandydaci = nowe.get(_klucz(j["oznaczenie"]), [])
        if len(kandydaci) != 1:
            lista = raport["bez_odpowiednika"] if not kandydaci else raport["niejednoznaczne"]
            if j["oznaczenie"] not in lista:
                lista.append(j["oznaczenie"])
            return None
        cel = kandydaci[0]
        if " ".join(j["tekst"].split()) != " ".join(cel["tekst"].split()) and j["oznaczenie"] not in raport["zmieniony_tekst"]:
            raport["zmieniony_tekst"].append(j["oznaczenie"])
        return cel

    for n in notatki:
        cel = odpowiednik(n["jednostka_id"])
        if cel is None:
            continue
        istniejaca = db.execute("SELECT tekst FROM notatki WHERE jednostka_id = ?", (cel["id"],)).fetchone()
        tekst = n["tekst"] if istniejaca is None else f"{istniejaca[0]}\n\n[z: {nazwa_starego}]\n{n['tekst']}"
        if istniejaca is not None and n["tekst"] in istniejaca[0]:
            continue  # już przeniesiona wcześniej
        db.execute(
            """INSERT INTO notatki (jednostka_id, akt_id, tekst, data_zmiany) VALUES (?, ?, ?, ?)
               ON CONFLICT(jednostka_id) DO UPDATE SET tekst = excluded.tekst, data_zmiany = excluded.data_zmiany""",
            (cel["id"], do_aktu, tekst[:MAKS_NOTATKI], teraz),
        )
        raport["notatki"] += 1
    for jednostka_id in moje:
        cel = odpowiednik(jednostka_id)
        if cel is None or db.execute("SELECT 1 FROM moje_przepisy WHERE jednostka_id = ?", (cel["id"],)).fetchone():
            continue
        if db.execute("SELECT COUNT(*) FROM moje_przepisy").fetchone()[0] >= MAKS_MOICH:
            raport["pelny_zbior"] = True
            break
        db.execute("INSERT INTO moje_przepisy (jednostka_id, akt_id, data_dodania) VALUES (?, ?, ?)", (cel["id"], do_aktu, teraz))
        raport["moje"] += 1
    db.commit()
    return raport
