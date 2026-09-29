"""Import fiszek z pliku (ETAP 54)."""

import io

import pytest

from app import create_app
from fiszki import importer

ANKI = "#separator:tab\n#html:true\n#tags column:3\nCo to jest <b>MPZP</b>?\tAkt prawa miejscowego.<br>Uchwala go rada gminy.\ttag\nPBC?\tPowierzchnia biologicznie czynna &amp; zieleń\t\n"
QUIZLET = "Studium\tDokument polityki przestrzennej gminy\nWZ\tDecyzja o warunkach zabudowy\n"


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), "a.pdf")}, content_type="multipart/form-data")
        yield c


def importuj(client, tekst, tematy="", nazwa="plik.txt"):
    return client.post(
        "/fiszki/1/import",
        data={"plik": (io.BytesIO(tekst.encode("utf-8")), nazwa), "tematy": tematy},
        content_type="multipart/form-data",
    )


def test_anki_html_na_tekst():
    fiszki, bledy = importer.wczytaj(ANKI)
    assert fiszki[0]["pytanie"] == "Co to jest MPZP?"
    assert fiszki[0]["odpowiedz"] == "Akt prawa miejscowego.\nUchwala go rada gminy."
    assert fiszki[1]["odpowiedz"] == "Powierzchnia biologicznie czynna & zieleń"
    assert all(f["strona"] == 0 and f["fragment_tekstu"] == "" for f in fiszki) and bledy == []


def test_quizlet_i_csv_bez_naglowka():
    assert [f["pytanie"] for f in importer.wczytaj(QUIZLET)[0]] == ["Studium", "WZ"]
    fiszki, bledy = importer.wczytaj("MN;jednorodzinna\nMW;wielorodzinna\ntylko pytanie\n")
    assert [f["odpowiedz"] for f in fiszki] == ["jednorodzinna", "wielorodzinna"]
    assert bledy == ["wiersz 3: brak pytania albo odpowiedzi"]


def test_wlasny_eksport_csv_przywraca_kotwice():
    tekst = "﻿strona,pytanie,odpowiedz,fragment_tekstu,data_utworzenia\n3,P?,O.,cytat ze strony,2026-01-01\n2,Q?,R.,,2026-01-01\n"
    fiszki, _ = importer.wczytaj(tekst)
    assert (fiszki[0]["strona"], fiszki[0]["fragment_tekstu"]) == (3, "cytat ze strony")
    assert fiszki[1]["strona"] == 0  # bez fragmentu nie ma kotwicy


def test_bledy_pliku():
    with pytest.raises(importer.BladImportu):
        importer.wczytaj("   ")
    with pytest.raises(importer.BladImportu):
        importer.wczytaj("\n".join(f"p{i}\to{i}" for i in range(importer.MAKS_FISZEK + 1)))


def test_endpoint_importu_z_tematem_i_duplikatami(client):
    wynik = importuj(client, QUIZLET, tematy="kolokwium 2").get_json()
    assert wynik == {"dodane": 2, "duplikaty": 0, "bledne": [], "liczba_blednych": 0}
    ponownie = importuj(client, QUIZLET).get_json()
    assert ponownie["dodane"] == 0 and ponownie["duplikaty"] == 2

    fiszki = client.get("/fiszki/1/fiszki").get_json()
    assert {f["pytanie"] for f in fiszki} == {"Studium", "WZ"}
    assert all(f["tematy"] == ["kolokwium 2"] and f["strona"] == 0 for f in fiszki)
    # fiszki z importu są w powtórce i w eksporcie Anki bez numeru strony
    assert len(client.get("/fiszki/powtorka/kolejka").get_json()) == 2
    assert ", s. 0" not in client.get("/fiszki/1/eksport.txt").get_data(as_text=True)


def test_endpoint_importu_bledy(client):
    assert client.post("/fiszki/1/import", data={}, content_type="multipart/form-data").status_code == 400
    zly = client.post("/fiszki/1/import", data={"plik": (io.BytesIO("ą".encode("cp1250")), "x.txt")}, content_type="multipart/form-data")
    assert zly.status_code == 400 and "UTF-8" in zly.get_json()["blad"]
    assert importuj(client, "").status_code == 400
    assert client.post("/fiszki/9/import", data={"plik": (io.BytesIO(b"a\tb"), "x.txt")}, content_type="multipart/form-data").status_code == 404
