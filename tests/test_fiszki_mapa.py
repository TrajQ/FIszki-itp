"""Fiszki „gdzie to jest” i quiz z mapą (ETAP 248)."""

import io

import pytest

from app import create_app
from fiszki import miejsca


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4 atrapa"), "geografia.pdf")}, content_type="multipart/form-data")
        yield c


def test_ocena_odleglosci():
    m = {"lat": 52.4, "lng": 16.9, "promien_m": 300}
    assert miejsca.odleglosc_m(52.4, 16.9, 52.401, 16.9) == pytest.approx(111.2, abs=0.2)
    assert miejsca.ocen(m, 52.401, 16.9)["ocena"] == "trafione"
    assert miejsca.ocen(m, 52.405, 16.9)["ocena"] == "blisko"  # ok. 556 m — do trzech promieni
    assert miejsca.ocen(m, 52.42, 16.9)["ocena"] == "pudło"
    for zle in ((None, 16.9, 300), (95, 16.9, 300), (52.4, 16.9, 123)):
        with pytest.raises(miejsca.BladMiejsca):
            miejsca.sprawdz(*zle)


def test_fiszka_z_miejscem_i_quiz(client):
    nowa = client.post("/fiszki/mapa/fiszki", json={"pdf_id": 1, "pytanie": "Gdzie jest Stary Rynek?", "odpowiedz": "Stary Rynek, Poznań",
                                                   "lat": 52.4084, "lng": 16.9341, "promien_m": 300})
    assert nowa.status_code == 201
    fiszka_id = nowa.get_json()["id"]
    strona = client.get("/fiszki/mapa").get_data(as_text=True)
    assert "Gdzie jest Stary Rynek?" in strona and 'id="formularz-miejsca"' in strona
    # pytania quizu nie zdradzają miejsca
    pytania = client.get("/fiszki/mapa/quiz/pytania").get_json()
    assert pytania == [{"id": fiszka_id, "pytanie": "Gdzie jest Stary Rynek?"}]
    w = client.post(f"/fiszki/mapa/quiz/{fiszka_id}", json={"lat": 52.4090, "lng": 16.9341}).get_json()
    assert w["ocena"] == "trafione" and w["odleglosc_m"] == pytest.approx(67, abs=2) and w["odpowiedz"] == "Stary Rynek, Poznań"
    assert client.post(f"/fiszki/mapa/quiz/{fiszka_id}", json={"lat": "x"}).status_code == 400
    assert client.post("/fiszki/mapa/quiz/999", json={"lat": 52.4, "lng": 16.9}).status_code == 404
    # zwykła fiszka: jest w powtórce jak każda inna
    assert any(f["id"] == fiszka_id for f in client.get("/fiszki/powtorka/kolejka").get_json())
    # błędy zapisu
    assert client.post("/fiszki/mapa/fiszki", json={"pdf_id": 1, "pytanie": "A", "odpowiedz": "B"}).status_code == 400
    assert client.post("/fiszki/mapa/fiszki", json={"pytanie": "A", "odpowiedz": "B", "lat": 52, "lng": 16, "promien_m": 300}).status_code == 400
    assert client.post("/fiszki/mapa/fiszki", json={"pdf_id": 9, "pytanie": "A", "odpowiedz": "B", "lat": 52, "lng": 16, "promien_m": 300}).status_code == 404
    assert 'href="/fiszki/mapa"' in client.get("/fiszki/").get_data(as_text=True)


def test_quiz_mapy_strona_i_pusto(client):
    assert client.get("/fiszki/mapa/quiz/pytania").get_json() == []
    assert "Quiz z mapą" in client.get("/fiszki/mapa/quiz").get_data(as_text=True)


def test_kosz_przywraca_miejsce(client):
    f = client.post("/fiszki/mapa/fiszki", json={"pdf_id": 1, "pytanie": "Gdzie?", "odpowiedz": "Tu", "lat": 52.4, "lng": 16.9, "promien_m": 100}).get_json()
    kosz_id = client.delete(f"/fiszki/1/fiszki/{f['id']}").get_json()["kosz_id"]
    assert client.get("/fiszki/mapa/quiz/pytania").get_json() == []
    client.post(f"/fiszki/kosz/{kosz_id}/przywroc", headers={"Accept": "application/json"})
    assert client.get("/fiszki/mapa/quiz/pytania").get_json()[0]["id"] == f["id"]
