import io

import pytest

from app import create_app

PDF = b"%PDF-1.4\n%test\n"


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(PDF), "a.pdf")}, content_type="multipart/form-data")
        yield c


def test_obcy_origin_nie_usunie_pliku(client):
    odpowiedz = client.post("/fiszki/1/usun", headers={"Origin": "https://zla-strona.example"})
    assert odpowiedz.status_code == 403
    assert client.get("/fiszki/1/").status_code == 200


def test_obcy_referer_bez_origin_tez_blokowany(client):
    assert client.post("/fiszki/1/usun", headers={"Referer": "https://zla-strona.example/x"}).status_code == 403


def test_origin_null_blokowany(client):
    assert client.post("/fiszki/1/usun", headers={"Origin": "null"}).status_code == 403


def test_inny_port_na_localhost_to_obca_strona(client):
    # Inna lokalna aplikacja (np. na porcie 8000) to inne źródło.
    assert client.post("/fiszki/1/usun", headers={"Origin": "http://localhost:8000"}).status_code == 403


def test_wlasny_origin_przechodzi(client):
    # Klient testowy Flaska przedstawia się jako Host: localhost
    odpowiedz = client.post("/fiszki/1/usun", headers={"Origin": "http://localhost"})
    assert odpowiedz.status_code == 302


def test_bez_origin_i_referer_przechodzi(client):
    assert client.post("/fiszki/1/usun").status_code == 302


def test_dns_rebinding_obcy_host_blokowany_nawet_dla_get(client):
    assert client.get("/fiszki/", headers={"Host": "zla-strona.example:5000"}).status_code == 403
    assert client.get("/fiszki/", headers={"Host": "127.0.0.1:5000"}).status_code == 200


def test_get_z_obcym_referer_dziala(client):
    # Zwykłe wejście z linku na innej stronie nie zmienia stanu — przepuszczamy.
    assert client.get("/fiszki/", headers={"Referer": "https://google.com/"}).status_code == 200


def test_naglowki_bezpieczenstwa(client):
    odpowiedz = client.get("/")
    assert odpowiedz.headers["X-Frame-Options"] == "DENY"
    assert odpowiedz.headers["X-Content-Type-Options"] == "nosniff"
    assert odpowiedz.headers["Referrer-Policy"] == "same-origin"
