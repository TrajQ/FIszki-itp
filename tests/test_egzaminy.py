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


# ---------- ETAP 224: prognoza gotowości na dzień egzaminu ----------


def test_prognoza_przy_samych_umiem_wynika_z_odstepow():
    # nowa fiszka (pudełko 1, dziś): dziś → pudełko 2 (powtórka za 2 dni) → pudełko 3
    assert egzaminy.prognoza([(1, 0)], 3, None)["maksimum"] == 1  # nauka w dniach 0, 1, 2
    assert egzaminy.prognoza([(1, 0)], 2, None)["maksimum"] == 0  # dzień 2 to już egzamin
    assert egzaminy.prognoza([(2, 5)], 30, None)["maksimum"] == 1  # zaplanowana na za 5 dni
    assert egzaminy.prognoza([(2, 5)], 5, None)["maksimum"] == 0  # powtórka wypada w dniu egzaminu
    assert egzaminy.prognoza([(4, 40)], 3, None)["maksimum"] == 1  # utrwalona, powtórka po egzaminie
    g = egzaminy.prognoza([(1, -3)] * 4, 0, None)  # zaległe, egzamin dziś
    assert (g["dni_nauki"], g["maksimum"], g["maksimum_powtorek_dziennie"]) == (1, 0, 4)
    assert "oczekiwane" not in g and g["udzialy"] is None


def test_prognoza_przy_udzialach_odpowiedzi():
    u = {"umiem": 0.5, "trudne": 0.0, "nie_umiem": 0.5, "odpowiedzi": 100}
    # pudełko 2 na jutro, egzamin za 3 dni (nauka 0–2): jedna szansa (dzień 1) → 50%;
    # po „nie umiem” wraca do pudełka 2 na dzień 3 — już po nauce
    g = egzaminy.prognoza([(2, 1)] * 10, 3, u)
    assert (g["oczekiwane"], g["oczekiwane_proc"], g["maksimum"]) == (5, 50, 10)
    assert g["oczekiwane_powtorek_dziennie"] == 15  # 10 powtórek + połowa jeszcze raz tego dnia
    # utrwalona może wypaść: pudełko 3 z powtórką jutro, egzamin za 2 dni
    assert egzaminy.prognoza([(3, 1)], 2, u)["oczekiwane_proc"] == 50


def test_udzialy_z_dziennika_i_prognoza_na_stronie(client):
    ids = [dodaj_fiszke(client, "kolokwium") for _ in range(3)]
    client.post("/fiszki/egzaminy", data={"nazwa": "Kolokwium 1", "data": "2026-10-05", "zakres": "temat:kolokwium"})
    strona = client.get("/fiszki/").get_data(as_text=True)
    assert "Prognoza na dzień egzaminu: najwyżej <strong>3</strong> z 3" in strona and "mniej niż 30 odpowiedzi" in strona
    with client.application.app_context():
        from fiszki.baza import get_db
        db = get_db()
        db.executemany("INSERT INTO dziennik_powtorek (fiszka_id, data, wynik) VALUES (?, ?, ?)",
                       [(ids[0], "2026-09-20", "umiem")] * 24 + [(ids[0], "2026-09-20", "nie_umiem")] * 6
                       + [(ids[0], "2026-06-01", "nie_umiem")] * 50)  # stare — poza 60 dniami
        db.commit()
        u = egzaminy.udzialy_odpowiedzi(db, date(2026, 10, 1))
    assert (u["odpowiedzi"], u["umiem"], u["nie_umiem"]) == (30, 0.8, 0.2)
    strona = client.get("/fiszki/").get_data(as_text=True)
    assert "Prognoza na dzień egzaminu: ok. <strong>" in strona and "„umiem” 80%" in strona
