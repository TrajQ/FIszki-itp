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
    assert linie[:3] == ["#separator:tab", "#html:true", "#tags column:4"]
    assert linie[3].split("\t") == [
        "Co znaczy &lt;MN&gt;?",
        "Zabudowa mieszkaniowa<br>jednorodzinna",
        "wyklad.pdf, s. 2",
        "",
    ]


def test_eksport_nieistniejacego_pdf_to_404(client):
    assert client.get("/fiszki/7/eksport.csv").status_code == 404
    assert client.get("/fiszki/7/eksport.txt").status_code == 404



def test_widok_pdf_uzywa_wektorowanego_workera_i_ma_miejsce_na_blad(client):
    wgraj_pdf(client)
    strona = client.get("/fiszki/1/").get_data(as_text=True)
    assert "pdfjs/pdf.worker.min.mjs" in strona
    assert 'id="blad-pdf"' in strona
    assert client.get("/fiszki/static/pdfjs/pdf.worker.min.mjs").status_code == 200


def test_lista_plikow_pokazuje_liczbe_fiszek(client):
    wgraj_pdf(client, nazwa="skrypt.pdf")
    dodaj_fiszke(client)
    dodaj_fiszke(client)

    strona = client.get("/fiszki/").get_data(as_text=True)
    assert "skrypt.pdf" in strona
    assert "2 fiszki" in strona


# ---------- ETAP 11: wyszukiwarka, eksport wszystkiego, usuwanie PDF-a ----------


def test_szukaj_bez_rozrozniania_wielkosci_liter_z_polskimi_znakami(client):
    wgraj_pdf(client, nazwa="a.pdf")
    wgraj_pdf(client, nazwa="b.pdf")
    dodaj_fiszke(client, pytanie="Czym jest ŁAD przestrzenny?", odpowiedz="Harmonią całości.")
    dodaj_fiszke(client, pdf_id=2, pytanie="Co to MPZP?", odpowiedz="Akt prawa miejscowego, ład w gminie.")
    dodaj_fiszke(client, pdf_id=2, pytanie="Inne?", odpowiedz="Nic.")

    wyniki = client.get("/fiszki/szukaj?q=ład").get_json()
    assert sorted(w["pytanie"] for w in wyniki) == ["Co to MPZP?", "Czym jest ŁAD przestrzenny?"]
    assert {w["nazwa_oryginalna"] for w in wyniki} == {"a.pdf", "b.pdf"}

    # fragment też jest przeszukiwany
    assert len(client.get("/fiszki/szukaj?q=ZAZNACZONY").get_json()) == 3
    assert client.get("/fiszki/szukaj?q=x").status_code == 400


def test_eksport_wszystkich_ma_kolumne_plik(client):
    wgraj_pdf(client, nazwa="a.pdf")
    wgraj_pdf(client, nazwa="b.pdf")
    dodaj_fiszke(client, pytanie="P1")
    dodaj_fiszke(client, pdf_id=2, pytanie="P2")

    wiersze = list(csv.reader(io.StringIO(client.get("/fiszki/eksport.csv").data.decode("utf-8-sig"))))
    assert wiersze[0][0] == "plik"
    assert [(w[0], w[2]) for w in wiersze[1:]] == [("a.pdf", "P1"), ("b.pdf", "P2")]

    anki = client.get("/fiszki/eksport.txt")
    assert "fiszki_wszystkie.txt" in anki.headers["Content-Disposition"]
    assert "b.pdf, s. 2" in anki.data.decode("utf-8")


def test_usuniecie_pdf_usuwa_plik_fiszki_i_powtorki(client, app):
    import os

    from fiszki.baza import folder_plikow, get_db

    wgraj_pdf(client)
    wgraj_pdf(client, nazwa="zostaje.pdf")
    fiszka_id = dodaj_fiszke(client)
    dodaj_fiszke(client, pdf_id=2)
    client.post(f"/fiszki/powtorka/{fiszka_id}", data=json.dumps({"wynik": "umiem"}), content_type="application/json")
    with app.app_context():
        plik = get_db().execute("SELECT nazwa_pliku FROM pdfy WHERE id = 1").fetchone()[0]
        sciezka = os.path.join(folder_plikow(), plik)
    assert os.path.exists(sciezka)

    odpowiedz = client.post("/fiszki/1/usun")

    assert odpowiedz.status_code == 302
    assert not os.path.exists(sciezka)
    assert client.get("/fiszki/1/").status_code == 404
    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM fiszki").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM powtorki").fetchone()[0] == 0
    assert client.post("/fiszki/1/usun").status_code == 404


# ---------- ETAP 95: tematy jako tagi Anki i eksport jednego tematu ----------


def test_eksport_anki_z_tagami_i_jednego_tematu(client):
    wgraj_pdf(client, nazwa="wyklad.pdf")
    dodaj_fiszke(client, pytanie="P1?", tematy=["kolokwium 1", "prawo"])
    dodaj_fiszke(client, pytanie="P2?", tematy=["prawo"])
    dodaj_fiszke(client, pytanie="P3?")
    wszystkie = client.get("/fiszki/eksport.txt").data.decode("utf-8").splitlines()[3:]
    assert [w.split("\t")[3] for w in wszystkie] == ["kolokwium_1 prawo", "prawo", ""]
    odp = client.get("/fiszki/eksport.txt?temat=kolokwium 1")
    assert "fiszki_kolokwium_1.txt" in odp.headers["Content-Disposition"]
    assert [w.split("\t")[0] for w in odp.data.decode("utf-8").splitlines()[3:]] == ["P1?"]
    assert "eksport.txt?temat=prawo" in client.get("/fiszki/").get_data(as_text=True)


def test_eksport_anki_wraca_importem(client):
    wgraj_pdf(client, nazwa="wyklad.pdf")
    dodaj_fiszke(client, pytanie="P1?", odpowiedz="O1", tematy=["prawo"])
    plik = client.get("/fiszki/eksport.txt").data
    wgraj_pdf(client, nazwa="drugi.pdf")
    odp = client.post("/fiszki/2/import", data={"plik": (io.BytesIO(plik), "fiszki.txt")}, content_type="multipart/form-data")
    assert odp.status_code in (200, 302)
    assert client.get("/fiszki/2/fiszki").get_json()[0]["pytanie"] == "P1?"
