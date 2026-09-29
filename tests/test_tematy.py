"""Tematy fiszek (ETAP 50)."""

import io
import json

import pytest

from app import create_app
from fiszki import tematy


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), "a.pdf")}, content_type="multipart/form-data")
        yield c


def dodaj(client, pytanie="P?", odpowiedz="O.", **dodatki):
    odpowiedz = client.post(
        "/fiszki/1/fiszki",
        data=json.dumps({"strona": 1, "fragment_tekstu": "f", "pytanie": pytanie, "odpowiedz": odpowiedz, **dodatki}),
        content_type="application/json",
    )
    return odpowiedz


def test_normalizuj():
    assert tematy.normalizuj(" kolokwium  1, Prawo ,prawo,, ") == ["kolokwium 1", "Prawo"]
    assert tematy.normalizuj(None) == [] and tematy.normalizuj(["a", "A"]) == ["a"]
    with pytest.raises(tematy.BladTematow):
        tematy.normalizuj("x" * 31)
    with pytest.raises(tematy.BladTematow):
        tematy.normalizuj([str(i) for i in range(11)])
    with pytest.raises(tematy.BladTematow):
        tematy.normalizuj({"a": 1})


def test_tematy_przy_zapisie_edycji_i_liscie(client):
    nowa = dodaj(client, tematy="kolokwium 1, planowanie").get_json()
    assert nowa["tematy"] == ["kolokwium 1", "planowanie"]
    # ta sama nazwa inną wielkością liter trafia do istniejącego tematu
    druga = dodaj(client, pytanie="Q?", tematy="Kolokwium 1").get_json()
    assert druga["tematy"] == ["kolokwium 1"]

    # edycja bez pola „tematy” ich nie rusza, z polem — zastępuje
    bez = client.put(f"/fiszki/1/fiszki/{nowa['id']}", json={"pytanie": "P2?", "odpowiedz": "O."}).get_json()
    assert bez["tematy"] == ["kolokwium 1", "planowanie"]
    z = client.put(f"/fiszki/1/fiszki/{nowa['id']}", json={"pytanie": "P2?", "odpowiedz": "O.", "tematy": "prawo"}).get_json()
    assert z["tematy"] == ["prawo"]
    assert client.put(f"/fiszki/1/fiszki/{nowa['id']}", json={"pytanie": "P?", "odpowiedz": "O.", "tematy": "x" * 40}).status_code == 400

    lista = {f["id"]: f["tematy"] for f in client.get("/fiszki/1/fiszki").get_json()}
    assert lista == {nowa["id"]: ["prawo"], druga["id"]: ["kolokwium 1"]}
    assert dodaj(client, tematy="y" * 40).status_code == 400


def test_filtr_tematu_w_powtorce_quizie_druku_i_lista_na_stronie(client):
    for i in range(4):
        dodaj(client, pytanie=f"K{i}?", odpowiedz=f"Odp {i}.", tematy="kolokwium 1")
    dodaj(client, pytanie="Inne?", odpowiedz="Inna.")

    kolejka = client.get("/fiszki/powtorka/kolejka?temat=kolokwium 1").get_json()
    assert sorted(f["pytanie"] for f in kolejka) == ["K0?", "K1?", "K2?", "K3?"]
    assert len(client.get("/fiszki/powtorka/kolejka?temat=kolokwium 1&wszystkie=1").get_json()) == 4

    pytania = client.get("/fiszki/quiz/pytania?temat=kolokwium 1&ziarno=1").get_json()
    assert pytania and all(p["pytanie"].startswith("K") for p in pytania)
    assert "Inne?" not in client.get("/fiszki/druk?temat=kolokwium 1").get_data(as_text=True)

    strona = client.get("/fiszki/").get_data(as_text=True)
    assert "kolokwium 1" in strona and "4 fiszki" in strona and "temat=kolokwium" in strona


def test_usuniecie_fiszki_i_pdf_usuwa_tematy(client):
    nowa = dodaj(client, tematy="a").get_json()
    client.delete(f"/fiszki/1/fiszki/{nowa['id']}")
    dodaj(client, tematy="b")
    client.post("/fiszki/1/usun")
    with client.application.app_context():
        from fiszki.baza import get_db

        assert get_db().execute("SELECT COUNT(*) FROM tematy_fiszek").fetchone()[0] == 0
