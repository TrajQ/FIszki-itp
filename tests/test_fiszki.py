import io
import json

import pytest

from app import create_app
import fiszki.routes as fiszki_routes
from dane.gemini import BladGemini

PDF_MINIMALNY = b"%PDF-1.4\n%testowy plik, wystarczy naglowek\n"


@pytest.fixture
def app(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


def wgraj_pdf(client, nazwa="test.pdf", tresc=PDF_MINIMALNY):
    dane = {"plik": (io.BytesIO(tresc), nazwa)}
    return client.post("/fiszki/upload", data=dane, content_type="multipart/form-data")


def test_upload_poprawnego_pdf(client):
    odpowiedz = wgraj_pdf(client)
    assert odpowiedz.status_code == 302
    assert "/fiszki/1/" in odpowiedz.headers["Location"]


def test_upload_odrzuca_nie_pdf(client):
    dane = {"plik": (io.BytesIO(b"to nie jest pdf"), "notatka.txt")}
    odpowiedz = client.post("/fiszki/upload", data=dane, content_type="multipart/form-data")
    assert odpowiedz.status_code == 400


def test_upload_odrzuca_falszywe_rozszerzenie(client):
    dane = {"plik": (io.BytesIO(b"to nie jest pdf w srodku"), "udawany.pdf")}
    odpowiedz = client.post("/fiszki/upload", data=dane, content_type="multipart/form-data")
    assert odpowiedz.status_code == 400


def test_szkic_zwraca_propozycje_z_zamockowanego_gemini(client, monkeypatch):
    wgraj_pdf(client)
    monkeypatch.setattr(
        fiszki_routes,
        "zaproponuj_fiszke",
        lambda fragment: {"pytanie": "Pytanie testowe?", "odpowiedz": "Odpowiedź testowa."},
    )

    odpowiedz = client.post(
        "/fiszki/1/szkic",
        data=json.dumps({"fragment": "jakiś fragment tekstu", "strona": 1}),
        content_type="application/json",
    )
    assert odpowiedz.status_code == 200
    assert odpowiedz.get_json() == {"pytanie": "Pytanie testowe?", "odpowiedz": "Odpowiedź testowa."}


def test_szkic_przy_bledzie_gemini_zwraca_czytelny_blad(client, monkeypatch):
    wgraj_pdf(client)

    def zepsuty_gemini(fragment):
        raise BladGemini("symulowany błąd API")

    monkeypatch.setattr(fiszki_routes, "zaproponuj_fiszke", zepsuty_gemini)

    odpowiedz = client.post(
        "/fiszki/1/szkic",
        data=json.dumps({"fragment": "jakiś fragment tekstu", "strona": 1}),
        content_type="application/json",
    )
    assert odpowiedz.status_code == 502
    assert "blad" in odpowiedz.get_json()


def test_zapis_i_usuwanie_fiszki(client):
    wgraj_pdf(client)

    odpowiedz = client.post(
        "/fiszki/1/fiszki",
        data=json.dumps(
            {
                "strona": 3,
                "fragment_tekstu": "zaznaczony fragment",
                "pytanie": "Co to jest X?",
                "odpowiedz": "X to Y.",
            }
        ),
        content_type="application/json",
    )
    assert odpowiedz.status_code == 201
    fiszka_id = odpowiedz.get_json()["id"]

    lista = client.get("/fiszki/1/fiszki").get_json()
    assert len(lista) == 1
    assert lista[0]["pytanie"] == "Co to jest X?"

    usuniecie = client.delete(f"/fiszki/1/fiszki/{fiszka_id}")
    assert usuniecie.status_code == 204

    lista_po = client.get("/fiszki/1/fiszki").get_json()
    assert lista_po == []
