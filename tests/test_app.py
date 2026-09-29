import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


def test_strona_glowna(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.parametrize("sciezka", ["/atlas/", "/mpzp/", "/fiszki/", "/dostepnosc/"])
def test_placeholdery_modulow(client, sciezka):
    response = client.get(sciezka)
    assert response.status_code == 200


# ---------- ETAP 14: pulpit na stronie głównej ----------

import io
import json


@pytest.fixture
def czysty_client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_pulpit_pokazuje_podsumowania_modulow(czysty_client):
    c = czysty_client
    c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), "a.pdf")}, content_type="multipart/form-data")
    for _ in range(3):
        c.post(
            "/fiszki/1/fiszki",
            data=json.dumps({"strona": 1, "fragment_tekstu": "f", "pytanie": "P?", "odpowiedz": "O."}),
            content_type="application/json",
        )
    with c.application.app_context():
        from mpzp.baza import zapisz_w_historii

        zapisz_w_historii("306401_1.0051.AR_18.14", "1MN", 52.4, 16.9)

    strona = c.get("/").get_data(as_text=True)
    assert "3 do powtórki dziś" in strona
    assert "306401_1.0051.AR_18.14" in strona
    assert "1MN" in strona


def test_pulpit_dziala_mimo_bledu_modulu(czysty_client, monkeypatch):
    import fiszki.routes

    def zepsute():
        raise RuntimeError("symulowany błąd")

    monkeypatch.setattr(fiszki.routes, "podsumowanie", zepsute)
    assert czysty_client.get("/").status_code == 200


def test_favicon(czysty_client):
    odpowiedz = czysty_client.get("/favicon.ico")
    assert odpowiedz.status_code == 302
    assert odpowiedz.headers["Location"].endswith("/static/favicon.svg")


# ---------- ETAP 32: kopia zapasowa ----------


def test_kopia_zapasowa_zawiera_dane_i_pomija_cache(czysty_client, tmp_path):
    import os
    import sqlite3
    import zipfile

    c = czysty_client
    c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), "wyklad.pdf")}, content_type="multipart/form-data")
    c.post(
        "/fiszki/1/fiszki",
        data=json.dumps({"strona": 1, "fragment_tekstu": "f", "pytanie": "Kopia?", "odpowiedz": "Tak."}),
        content_type="application/json",
    )
    granice = os.path.join(c.application.instance_path, "atlas", "granice")
    os.makedirs(granice, exist_ok=True)
    open(os.path.join(granice, "gminy_12.geojson"), "w").write("{}")

    odp = c.get("/kopia-zapasowa")
    assert odp.mimetype == "application/zip"
    assert "warsztat_kopia_" in odp.headers["Content-Disposition"]

    with zipfile.ZipFile(io.BytesIO(odp.data)) as z:
        nazwy = z.namelist()
        assert "PRZYWRACANIE.txt" in nazwy
        assert "instance/fiszki/fiszki.db" in nazwy
        assert any(n.startswith("instance/fiszki/pliki/") and n.endswith("wyklad.pdf") for n in nazwy)
        assert not any("granice" in n for n in nazwy)
        # baza w kopii jest poprawna i zawiera fiszkę
        z.extract("instance/fiszki/fiszki.db", tmp_path)
    db = sqlite3.connect(tmp_path / "instance" / "fiszki" / "fiszki.db")
    assert db.execute("SELECT pytanie FROM fiszki").fetchall() == [("Kopia?",)]
    db.close()

    assert "Pobierz kopię zapasową" in c.get("/").get_data(as_text=True)
