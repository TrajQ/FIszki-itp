import csv
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


def dodaj_fiszke(client, pdf_id=1, **pola):
    fiszka = {
        "strona": 2,
        "fragment_tekstu": "zaznaczony fragment",
        "pytanie": "Co to jest X?",
        "odpowiedz": "X to Y.",
    }
    fiszka.update(pola)
    odpowiedz = client.post(
        f"/fiszki/{pdf_id}/fiszki", data=json.dumps(fiszka), content_type="application/json"
    )
    return odpowiedz.get_json()["id"]


def test_edycja_fiszki_zmienia_tylko_pytanie_i_odpowiedz(client):
    wgraj_pdf(client)
    fiszka_id = dodaj_fiszke(client)

    odpowiedz = client.put(
        f"/fiszki/1/fiszki/{fiszka_id}",
        data=json.dumps({"pytanie": "Nowe pytanie?", "odpowiedz": "Nowa odpowiedź.", "strona": 99}),
        content_type="application/json",
    )
    assert odpowiedz.status_code == 200
    zmieniona = odpowiedz.get_json()
    assert zmieniona["pytanie"] == "Nowe pytanie?"
    assert zmieniona["odpowiedz"] == "Nowa odpowiedź."
    # kotwica w źródle nietknięta
    assert zmieniona["strona"] == 2
    assert zmieniona["fragment_tekstu"] == "zaznaczony fragment"


def test_edycja_odrzuca_puste_pola(client):
    wgraj_pdf(client)
    fiszka_id = dodaj_fiszke(client)

    odpowiedz = client.put(
        f"/fiszki/1/fiszki/{fiszka_id}",
        data=json.dumps({"pytanie": "  ", "odpowiedz": "coś"}),
        content_type="application/json",
    )
    assert odpowiedz.status_code == 400
    assert client.get("/fiszki/1/fiszki").get_json()[0]["pytanie"] == "Co to jest X?"


def test_edycja_nieistniejacej_albo_cudzej_fiszki_to_404(client):
    wgraj_pdf(client)
    wgraj_pdf(client, nazwa="drugi.pdf")
    fiszka_z_pdf_2 = dodaj_fiszke(client, pdf_id=2)
    zmiana = json.dumps({"pytanie": "P?", "odpowiedz": "O."})

    assert client.put("/fiszki/1/fiszki/999", data=zmiana, content_type="application/json").status_code == 404
    assert (
        client.put(f"/fiszki/1/fiszki/{fiszka_z_pdf_2}", data=zmiana, content_type="application/json").status_code
        == 404
    )


def test_eksport_csv(client):
    wgraj_pdf(client, nazwa="wykład 1.pdf")
    dodaj_fiszke(client, pytanie="Czym jest MPZP?", odpowiedz="Aktem prawa\nmiejscowego, gmina.")

    odpowiedz = client.get("/fiszki/1/eksport.csv")
    assert odpowiedz.status_code == 200
    assert odpowiedz.mimetype == "text/csv"
    assert "attachment" in odpowiedz.headers["Content-Disposition"]
    assert odpowiedz.data.startswith(b"\xef\xbb\xbf")

    wiersze = list(csv.reader(io.StringIO(odpowiedz.data.decode("utf-8-sig"))))
    assert wiersze[0] == ["strona", "pytanie", "odpowiedz", "fragment_tekstu", "data_utworzenia"]
    assert wiersze[1][:4] == ["2", "Czym jest MPZP?", "Aktem prawa\nmiejscowego, gmina.", "zaznaczony fragment"]


def test_eksport_anki_escapuje_html_tabulatory_i_nowe_linie(client):
    wgraj_pdf(client, nazwa="wyklad.pdf")
    dodaj_fiszke(client, pytanie="Co znaczy <MN>?", odpowiedz="Zabudowa\tmieszkaniowa\njednorodzinna")

    odpowiedz = client.get("/fiszki/1/eksport.txt")
    assert odpowiedz.status_code == 200
    linie = odpowiedz.data.decode("utf-8").splitlines()
    assert linie[:2] == ["#separator:tab", "#html:true"]
    assert linie[2].split("\t") == [
        "Co znaczy &lt;MN&gt;?",
        "Zabudowa mieszkaniowa<br>jednorodzinna",
        "wyklad.pdf, s. 2",
    ]


def test_eksport_nieistniejacego_pdf_to_404(client):
    assert client.get("/fiszki/7/eksport.csv").status_code == 404
    assert client.get("/fiszki/7/eksport.txt").status_code == 404


def test_widok_pdf_laduje_worker_z_polyfillem(client):
    # pdf.js 6.x wymaga Map.getOrInsertComputed — worker musi startować przez
    # pdf_worker.mjs, który najpierw ładuje polyfill (D-008).
    wgraj_pdf(client)
    strona = client.get("/fiszki/1/").get_data(as_text=True)
    assert "pdf_worker.mjs" in strona
    assert "pdf.worker.min.mjs" not in strona

    worker = client.get("/fiszki/static/pdf_worker.mjs").get_data(as_text=True)
    assert worker.index("polyfill_map.mjs") < worker.index("pdf.worker.min.mjs")
    assert client.get("/fiszki/static/polyfill_map.mjs").status_code == 200
