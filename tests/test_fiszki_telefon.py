"""Fiszki na telefon (ETAP 74): eksport pliku HTML, import wyników powtórek."""

import io
import json
import re
from datetime import date

import pytest

from app import create_app
from fiszki import powtorki, telefon


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(powtorki, "dzisiaj", lambda: date(2026, 9, 29))
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4 atrapa"), "wyklad.pdf")}, content_type="multipart/form-data")
        for i in range(3):
            c.post("/fiszki/1/fiszki", json={"strona": 1, "fragment_tekstu": f"frag {i}", "pytanie": f"Pytanie {i}?", "odpowiedz": f"Odp {i}",
                                             "tematy": ["planowanie"] if i < 2 else []})
        yield c


def pobierz(client, zapytanie=""):
    r = client.get("/fiszki/telefon.html" + zapytanie)
    html = r.get_data(as_text=True)
    return r, html, (re.search(r'const INSTALACJA = "([^"]+)"', html).group(1) if r.status_code == 200 else None)


def wynik(uid, fiszka_id, ocena, dzien, czas="10:00"):
    return {"uid": uid, "fiszka_id": fiszka_id, "wynik": ocena, "data": dzien, "czas": f"{dzien}T{czas}:00Z"}


def importuj(client, instalacja, *wyniki):
    dane = {"format": "warsztat-powtorki", "wersja": 1, "instalacja": instalacja, "wyniki": list(wyniki)}
    return client.post("/fiszki/telefon/import", data={"plik": (io.BytesIO(json.dumps(dane).encode()), "p.json")}, content_type="multipart/form-data")


def stan(client, fiszka_id):
    from fiszki.baza import get_db

    with client.application.app_context():
        w = get_db().execute("SELECT pudelko, nastepna_powtorka, liczba_powtorek FROM powtorki WHERE fiszka_id = ?", (fiszka_id,)).fetchone()
        return tuple(w) if w else None


def test_eksport_pliku(client):
    r, html, instalacja = pobierz(client)
    assert r.headers["Content-Disposition"] == "attachment; filename=fiszki_na_telefon.html"
    assert "<script src" not in html and "<link" not in html
    assert html.count('"pytanie":') == 3 and '"odstepy_dni": {"1": 1, "2": 2, "3": 4, "4": 8, "5": 16}' in html
    assert pobierz(client)[2] == instalacja  # identyfikator instalacji stały
    assert pobierz(client, "?temat=planowanie")[1].count('"pytanie":') == 2
    assert pobierz(client, "?pdf_id=1")[1].count('"pytanie":') == 3
    assert pobierz(client, "?temat=nieistniejacy")[0].status_code == 404


def test_import_wynikow(client):
    instalacja = pobierz(client)[2]
    r = importuj(client, instalacja,
                 wynik("aaaaaaaa01", 2, "umiem", "2026-09-28", "12:00"),
                 wynik("aaaaaaaa00", 2, "umiem", "2026-09-27"),   # wcześniejszy — stosowany pierwszy
                 wynik("aaaaaaaa02", 3, "nie_umiem", "2026-09-28"),
                 wynik("aaaaaaaa03", 99, "umiem", "2026-09-28"))  # fiszki już nie ma
    assert r.get_json() == {"zastosowane": 3, "powtorzone": 0, "bez_fiszki": 1, "tylko_statystyki": 0}
    # 1 → 2 (27.09, +2 dni), 2 → 3 (28.09, +4 dni)
    assert stan(client, 2) == (3, "2026-10-02", 2)
    assert stan(client, 3) == (1, "2026-09-28", 1)
    # ponownie ten sam plik — nic się nie zmienia
    assert importuj(client, instalacja, wynik("aaaaaaaa01", 2, "umiem", "2026-09-28")).get_json()["powtorzone"] == 1
    assert stan(client, 2) == (3, "2026-10-02", 2)


def test_nowsza_powtorka_na_komputerze_wygrywa(client):
    instalacja = pobierz(client)[2]
    client.post("/fiszki/powtorka/1", json={"wynik": "umiem"})  # na komputerze 29.09
    r = importuj(client, instalacja, wynik("bbbbbbbb00", 1, "nie_umiem", "2026-09-28"))
    assert r.get_json()["tylko_statystyki"] == 1
    assert stan(client, 1) == (2, "2026-10-01", 1)  # stan z komputera zostaje


@pytest.mark.parametrize(
    "zmiana, komunikat",
    [
        ({"instalacja": "inna"}, "innej instalacji"),
        ({"format": "cos"}, "nie jest plik"),
        ({"wyniki": [wynik("cccccccc00", 1, "super", "2026-09-28")]}, "nieznana ocena"),
        ({"wyniki": [wynik("cccccccc00", 1, "umiem", "2026-12-01")]}, "z przyszłości"),
        ({"wyniki": [wynik("x", 1, "umiem", "2026-09-28")]}, "identyfikatora"),
    ],
)
def test_zle_pliki(client, zmiana, komunikat):
    instalacja = pobierz(client)[2]
    dane = {"format": "warsztat-powtorki", "wersja": 1, "instalacja": instalacja, "wyniki": [], **zmiana}
    r = client.post("/fiszki/telefon/import", data={"plik": (io.BytesIO(json.dumps(dane).encode()), "p.json")}, content_type="multipart/form-data")
    assert r.status_code == 400 and komunikat in r.get_json()["blad"]


def test_zasady_z_powtorek():
    z = telefon.zasady()
    assert z["pudelko_max"] == powtorki.PUDELKO_MAX and z["odstep_trudne_dni"] == powtorki.ODSTEP_TRUDNE_DNI
