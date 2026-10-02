"""Fiszka z wycinkiem rysunku z PDF (ETAP 154)."""

import base64
import io
import os
import re
import struct
import zlib

import pytest

from app import create_app


def png(szer=4, wys=3) -> bytes:
    """Najmniejszy poprawny PNG (szary)."""
    def blok(typ, dane):
        return struct.pack(">I", len(dane)) + typ + dane + struct.pack(">I", zlib.crc32(typ + dane))
    surowe = b"".join(b"\x00" + b"\x80" * szer for _ in range(wys))
    return b"\x89PNG\r\n\x1a\n" + blok(b"IHDR", struct.pack(">IIBBBBB", szer, wys, 8, 0, 0, 0, 0)) + blok(b"IDAT", zlib.compress(surowe)) + blok(b"IEND", b"")


def data_url(dane: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(dane).decode()


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4 atrapa"), "wyklad.pdf")}, content_type="multipart/form-data")
        c.tmp = tmp_path
        yield c


def fiszka(client, **zmiany):
    dane = {"strona": 2, "fragment_tekstu": "[wycinek rysunku, s. 2]", "pytanie": "Co oznacza symbol MN?", "odpowiedz": "Zabudowa jednorodzinna"}
    return client.post("/fiszki/1/fiszki", json={**dane, **zmiany})


def test_fiszka_z_wycinkiem_wszedzie(client):
    odp = fiszka(client, obraz=data_url(png()))
    assert odp.status_code == 201
    url = odp.get_json()["obraz"]
    assert re.fullmatch(r"/fiszki/obrazy/[0-9a-f]{32}\.png", url)
    obraz = client.get(url)
    assert obraz.status_code == 200 and obraz.mimetype == "image/png" and obraz.data == png()
    obraz.close()  # plik wysyłany strumieniem — odpowiedź trzeba zamknąć
    fiszka(client)  # zwykła fiszka — bez obrazu
    lista = client.get("/fiszki/1/fiszki").get_json()
    assert [f["obraz"] for f in lista] == [url, None]
    assert client.get("/fiszki/powtorka/kolejka").get_json()[0]["obraz"] == url
    assert url in client.get("/fiszki/druk").get_data(as_text=True)
    telefon = client.get("/fiszki/telefon.html").get_data(as_text=True)
    assert data_url(png()) in telefon  # osadzony — telefon działa bez Warsztatu
    for i in range(3):  # quiz potrzebuje kilku różnych odpowiedzi
        fiszka(client, odpowiedz=f"inna {i}")
    pytania = client.get("/fiszki/quiz/pytania?ziarno=1&liczba=50").get_json()
    assert {p["obraz"] for p in pytania if p["fiszka_id"] == 1} == {url}


def test_zly_obraz_i_sprzatanie(client):
    for zly in ["data:image/jpeg;base64,AAAA", data_url(b"nie png"), "data:image/png;base64,!!!", 5]:
        odp = fiszka(client, obraz=zly)
        assert odp.status_code == 400, zly
    assert client.get("/fiszki/1/fiszki").get_json() == []  # nic nie zapisane
    duzy = data_url(png() + b"\x00" * 2_100_000)
    assert "za duży" in fiszka(client, obraz=duzy).get_json()["blad"]
    assert client.get("/fiszki/obrazy/..%2Fapp.py").status_code == 404
    assert client.get("/fiszki/obrazy/nie-ma.png").status_code == 404

    folder = client.tmp / "fiszki" / "obrazy"
    pierwsza = fiszka(client, obraz=data_url(png())).get_json()
    druga = fiszka(client, obraz=data_url(png(8, 8))).get_json()
    assert len(os.listdir(folder)) == 2
    client.delete(f"/fiszki/1/fiszki/{pierwsza['id']}")
    assert len(os.listdir(folder)) == 1 and client.get(pierwsza["obraz"]).status_code == 404
    client.post("/fiszki/1/usun")  # usunięcie PDF-a usuwa fiszki i ich wycinki
    assert os.listdir(folder) == [] and client.get(druga["obraz"]).status_code == 404
