"""Egzaminy i postęp przygotowania (ETAP 51)."""

import io
import json
from datetime import date

import pytest

from app import create_app
from fiszki import egzaminy, powtorki


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(powtorki, "dzisiaj", lambda: date(2026, 10, 1))
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), "a.pdf")}, content_type="multipart/form-data")
        yield c


def dodaj_fiszke(client, tematy=""):
    return client.post(
        "/fiszki/1/fiszki",
        data=json.dumps({"strona": 1, "fragment_tekstu": "f", "pytanie": "P?", "odpowiedz": "O.", "tematy": tematy}),
        content_type="application/json",
    ).get_json()["id"]


def test_postep_i_plan_dzienny():
    # 10 fiszek, 4 utrwalone (pudełko ≥ 3), egzamin za 3 dni → 6 do nauki, 2 dziennie
    assert egzaminy.postep([1, 1, 2, 2, 1, 2, 3, 4, 5, 3], 3) == {
        "fiszki": 10, "utrwalone": 4, "procent": 40, "do_nauki": 6, "dziennie": 2
    }
    assert egzaminy.postep([1, 1, 1], 0)["dziennie"] == 3  # egzamin dziś: wszystko dziś
    assert egzaminy.postep([], 5)["procent"] is None


def test_dodanie_egzaminu_z_tematem_i_postep(client):
    ids = [dodaj_fiszke(client, "kolokwium") for _ in range(4)]
    dodaj_fiszke(client)
    for _ in range(2):  # jedna fiszka dwa razy „umiem” → pudełko 3
        client.post(f"/fiszki/powtorka/{ids[0]}", json={"wynik": "umiem"})

    odpowiedz = client.post("/fiszki/egzaminy", data={"nazwa": "Kolokwium 1", "data": "2026-10-05", "zakres": "temat:kolokwium"})
    assert odpowiedz.status_code == 302
    with client.application.app_context():
        from fiszki.baza import get_db

        lista = egzaminy.lista(get_db(), date(2026, 10, 1))
    assert lista[0]["dni"] == 4 and lista[0]["fiszki"] == 4 and lista[0]["utrwalone"] == 1 and lista[0]["dziennie"] == 1

    strona = client.get("/fiszki/").get_data(as_text=True)
    assert "Kolokwium 1" in strona and "za 4 dni" in strona and "utrwalone 1 z 4 (25%)" in strona


@pytest.mark.parametrize(
    "formularz,komunikat",
    [
        ({"nazwa": "", "data": "2026-10-05"}, "Podaj nazwę"),
        ({"nazwa": "X", "data": ""}, "Podaj datę"),
        ({"nazwa": "X", "data": "2026-09-01"}, "już minęła"),
        ({"nazwa": "X", "data": "2026-10-05", "zakres": "pdf:abc"}, "Nieznany zakres"),
    ],
)
def test_bledne_dane_egzaminu(client, formularz, komunikat):
    odpowiedz = client.post("/fiszki/egzaminy", data=formularz)
    assert odpowiedz.status_code == 302
    strona = client.get(odpowiedz.headers["Location"]).get_data(as_text=True)
    assert komunikat in strona


def test_egzamin_pliku_znika_z_plikiem_i_usuwanie(client):
    dodaj_fiszke(client)
    client.post("/fiszki/egzaminy", data={"nazwa": "Egzamin z pliku", "data": "2026-10-10", "zakres": "pdf:1"})
    client.post("/fiszki/egzaminy", data={"nazwa": "Ogólny", "data": "2026-10-20"})
    assert "Egzamin z pliku" in client.get("/fiszki/").get_data(as_text=True)
    client.post("/fiszki/1/usun")
    strona = client.get("/fiszki/").get_data(as_text=True)
    assert "Egzamin z pliku" not in strona and "Ogólny" in strona

    with client.application.app_context():
        from fiszki.baza import get_db

        egzamin_id = get_db().execute("SELECT id FROM egzaminy").fetchone()[0]
    client.post(f"/fiszki/egzaminy/{egzamin_id}/usun")
    assert "Ogólny" not in client.get("/fiszki/").get_data(as_text=True)
    assert client.post("/fiszki/egzaminy", data={"nazwa": "X", "data": "2026-10-05", "zakres": "pdf:99"}).status_code == 404
