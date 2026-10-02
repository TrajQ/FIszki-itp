"""Fiszki z luką — cloze (ETAP 139)."""

import io

import pytest

from app import create_app
from fiszki.luki import BladLuk, fiszki_z_luk


def test_fiszki_z_luk():
    f = fiszki_z_luk("Plan  miejscowy jest [[aktem prawa miejscowego]],\n uchwala go [[ rada gminy ]].")
    assert f == [
        {"pytanie": "Plan miejscowy jest […], uchwala go rada gminy.", "odpowiedz": "aktem prawa miejscowego"},
        {"pytanie": "Plan miejscowy jest aktem prawa miejscowego, uchwala go […].", "odpowiedz": "rada gminy"},
    ]
    # ta sama odpowiedź w dwóch lukach — dwie fiszki, każda ukrywa swoje miejsce
    f = fiszki_z_luk("[[MPZP]] to plan; studium nie jest [[MPZP]].")
    assert [x["pytanie"] for x in f] == ["[…] to plan; studium nie jest MPZP.", "MPZP to plan; studium nie jest […]."]
    for zly, komunikat in [("bez luk", "podwójnymi nawiasami"), ("tekst [[ ]] dalej", "Pusta luka"), ("[[cały tekst]]", "Poza lukami"),
                           ("tekst [[luka]] i [[niedomknięta", "Niedomknięty"), ("x " + "[[a]] " * 11, "Najwyżej 10"),
                           ("[[a]] " + "b" * 2000, "najwyżej 2000")]:
        with pytest.raises(BladLuk, match=komunikat):
            fiszki_z_luk(zly)


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4 atrapa"), "wyklad.pdf")}, content_type="multipart/form-data")
        yield c


def test_trasa_luk(client):
    fragment = "Plan miejscowy jest aktem prawa miejscowego, uchwala go rada gminy."
    odp = client.post("/fiszki/1/luki", json={"strona": 3, "fragment_tekstu": fragment, "tematy": "planowanie",
                                             "tekst": "Plan miejscowy jest [[aktem prawa miejscowego]], uchwala go [[rada gminy]]."})
    assert odp.status_code == 201 and odp.get_json()["liczba"] == 2
    fiszki = client.get("/fiszki/1/fiszki").get_json()
    assert [(f["pytanie"].count("[…]"), f["strona"], f["fragment_tekstu"], f["tematy"]) for f in fiszki] == [(1, 3, fragment, ["planowanie"])] * 2
    assert {f["odpowiedz"] for f in fiszki} == {"aktem prawa miejscowego", "rada gminy"}
    assert client.post("/fiszki/1/luki", json={"strona": 3, "fragment_tekstu": fragment, "tekst": "bez luk"}).get_json()["blad"].startswith("Otocz")
    assert client.post("/fiszki/1/luki", json={"strona": "3", "fragment_tekstu": fragment, "tekst": "[[a]] b"}).status_code == 400
    assert client.post("/fiszki/1/luki", json={"strona": 3, "fragment_tekstu": fragment, "tekst": "[[a]] b", "tematy": ["x" * 40]}).status_code == 400
    assert client.post("/fiszki/9/luki", json={"strona": 3, "fragment_tekstu": fragment, "tekst": "[[a]] b"}).status_code == 404
    assert len(client.get("/fiszki/1/fiszki").get_json()) == 2  # odrzucone nic nie zapisały


def test_druk_odmienia_liczbe_kart(client):
    """ETAP 148: „1 karta”, „2 karty”, „5 kart” w nagłówku wydruku."""
    def naglowek():
        return client.get("/fiszki/druk").get_data(as_text=True)
    zapis = {"strona": 1, "fragment_tekstu": "f", "tematy": ""}
    client.post("/fiszki/1/luki", json={**zapis, "tekst": "[[a]] b"})
    assert "1 karta." in naglowek()
    client.post("/fiszki/1/luki", json={**zapis, "tekst": "[[c]] d"})
    assert "2 karty." in naglowek()
    client.post("/fiszki/1/luki", json={**zapis, "tekst": "[[e]] [[f]] [[g]] h"})
    assert "5 kart." in naglowek()
