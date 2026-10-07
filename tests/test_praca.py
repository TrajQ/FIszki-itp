"""Moduł Praca i notatki: godziny z grafiku (ETAP 230)."""

import io
import os
from decimal import Decimal

import pytest

from app import create_app
from praca import grafik

PDF = os.path.join(os.path.dirname(__file__), "fixtures", "grafik_pazdziernik.pdf")  # tabela jak z Google Docs, wydruk z Chromium

KOMORKAMI = """Pazdziernik 2026
Wt, śr patrzcie czy jest pilates dla ciężarnych o 15:45, czy o 17 pierwsza grupa
poniedziałek wtorek środa czwartek piątek sobota niedziela
12
Tomek
15:30-20:00.
13.
Agata
15:30-20:00
16.
Patryk
15:30-20:00
17.
Patryk
8:30-12:30
27.
patryk
15:30-20:00
"""


def test_przyklad_z_notatki_autora():
    """Wrzesień z notatki autora: 70 h × 31,4 zł = 2198 zł."""
    zmiany = [(4, "15:00-20:00"), (5, "8:00-14:00"), (6, "9:30-12:30"), (11, "15:00-20:00"), (12, "8:00-14:00"), (13, "9:30-12:30"),
              (15, "15:00-20:00"), (17, "16:00-20:00"), (18, "15:00-20:00"), (19, "8:00-14:00"), (20, "9:30-12:30"), (23, "16:00-20:00"),
              (25, "15:00-20:00"), (26, "8:00-15:00"), (27, "9:30-12:30")]
    tekst = "wrzesień 2026\n" + "\n".join(f"{d}.\nPatryk\n{g}" for d, g in zmiany)
    w = grafik.rozliczenie(tekst, "Patryk")
    linie = w["tekst"].splitlines()
    assert linie[0] == "wrzesień 2026" and linie[1] == "4 września 15:00-20:00 5h" and linie[15] == "27 września 9:30-12:30 3h"
    assert linie[-2] == "5+6+3+5+6+3+5+4+5+6+3+4+5+7+3=70"
    assert linie[-1] == "70 h × 31,4 zł = 2 198,00 zł"
    assert (w["godziny"], w["kwota"]) == ("70", "2 198,00")


def test_grafik_komorkami_i_notatka_nad_tabela():
    w = grafik.rozliczenie(KOMORKAMI, "patryk")
    assert (w["miesiac"], w["rok"]) == (10, 2026)
    assert [z["dzien"] for z in w["zmiany"]] == [16, 17, 27]  # „o 17 pierwsza grupa” nad tabelą to nie zmiana
    assert w["godziny"] == "13" and w["kwota"] == "408,20"
    assert w["tekst"].splitlines()[1] == "16 października 15:30-20:00 4,5h"
    assert w["inne_osoby"] == ["Agata", "Tomek"]


def test_grafik_wierszami_tabeli():
    tekst = "Październik 2026\nponiedziałek wtorek środa\n12 13. 14.\nTomek Patryk Agata\n15:30-20:00 8:30-12:30 16:30-20:00\n"
    zmiany = grafik.odczytaj_zmiany(tekst)
    assert [(z.dzien, z.imie, z.minuty) for z in zmiany] == [(12, "Tomek", 270), (13, "Patryk", 240), (14, "Agata", 210)]


def test_pdf_z_tabela():
    from praca.routes import tekst_pdf
    with open(PDF, "rb") as f:
        w = grafik.rozliczenie(tekst_pdf(f.read()), "Patryk")
    assert len(w["zmiany"]) == 13 and w["godziny"] == "51" and w["kwota"] == "1 601,40"


def test_zmiana_przez_polnoc_minuty_i_sasiednie_miesiace():
    tekst = "listopad 2026\n30.\nPatryk\n8:00-12:00\n1.\nPatryk\n22:00-6:15\n2.\nPatryk\n9.00-12.20\n30.\nPatryk\n8:00-9:00\n1.\nPatryk\n8:00-9:00"
    w = grafik.rozliczenie(tekst, "Patryk", Decimal("30"))
    # 30 października na początku i 1 grudnia na końcu — z sąsiednich miesięcy
    assert [z["dzien"] for z in w["zmiany"]] == [1, 2, 30] and w["pominiete_inny_miesiac"] == 2
    assert [z["godziny"] for z in w["zmiany"]] == ["8,25", "3,33", "1"]
    assert w["godziny"] == "12,58" and w["kwota"] == "377,50"  # 755 minut × 30 zł / 60


@pytest.mark.parametrize("tekst, imie, komunikat", [
    ("październik 2026\n1.\nPatryk\n8:00-9:00", "", "Podaj imię"),
    ("1.\nPatryk\n8:00-9:00", "Patryk", "Nie rozpoznano miesiąca"),
    ("październik 2026\nnic tu nie ma", "Patryk", "nie znaleziono zmian"),
    ("październik 2026\n1.\nPatryk\n25:00-26:00", "Patryk", "Niepoprawna godzina"),
])
def test_bledy(tekst, imie, komunikat):
    with pytest.raises(grafik.BladGrafiku, match=komunikat):
        grafik.rozliczenie(tekst, imie)


def test_miesiac_z_formularza_i_osoba_z_dopiskiem():
    w = grafik.rozliczenie("1.\nPatryk (zastępstwo)\n8:00-10:00", "Patryk", miesiac=3, rok=2027)
    assert w["tekst"].splitlines()[:2] == ["marzec 2027", "1 marca 8:00-10:00 2h"] and not w["miesiac_z_tekstu"]


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_trasy(client, monkeypatch):
    assert "Godziny z grafiku" in client.get("/praca/").get_data(as_text=True)
    assert 'href="/praca/"' in client.get("/").get_data(as_text=True)
    with open(PDF, "rb") as f:
        r = client.post("/praca/grafik/odczytaj", data={"plik": (f, "grafik.pdf")}, content_type="multipart/form-data")
    assert r.get_json()["zrodlo"] == "pdf" and "Patryk" in r.get_json()["tekst"]
    w = client.post("/praca/grafik/policz", json={"tekst": KOMORKAMI, "imie": "Patryk", "stawka": "31,4"}).get_json()
    assert w["kwota"] == "408,20"
    assert client.post("/praca/grafik/policz", json={"tekst": KOMORKAMI, "imie": "Patryk", "stawka": "abc"}).status_code == 400
    assert client.post("/praca/grafik/policz", json={"tekst": KOMORKAMI, "imie": ""}).status_code == 400
    # zdjęcie — przepisuje Gemini (tu podstawione)
    from praca import routes
    monkeypatch.setattr(routes, "przepisz_grafik", lambda dane, typ: f"{typ}\n" + KOMORKAMI)
    r = client.post("/praca/grafik/odczytaj", data={"plik": (io.BytesIO(b"\xff\xd8x"), "IMG_1234.HEIC")}, content_type="multipart/form-data")
    assert r.get_json()["zrodlo"] == "gemini" and r.get_json()["tekst"].startswith("image/heic")
    r = client.post("/praca/grafik/odczytaj", data={"plik": (io.BytesIO(b"x"), "grafik.docx")}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_zdjecie_bez_klucza_gemini(client, monkeypatch):
    from dane import gemini
    monkeypatch.setattr(gemini.Config, "GEMINI_API_KEY", "")
    r = client.post("/praca/grafik/odczytaj", data={"plik": (io.BytesIO(b"\xff\xd8x"), "zdjecie.jpg")}, content_type="multipart/form-data")
    assert r.status_code == 502 and "wklej tekst grafiku ręcznie" in r.get_json()["blad"]
