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


# ---------- ETAP 231: notatki w Wordzie ----------

import json  # noqa: E402
import zipfile  # noqa: E402
from xml.dom import minidom  # noqa: E402

from praca import notatki, word  # noqa: E402

ODPOWIEDZ = {
    "tytul": "Planowanie w gminie", "podtytul": "Wykład 3", "streszczenie": "Plan ogólny zastępuje studium od 2026 r.",
    "sekcje": [{"naglowek": "Akty", "bloki": [
        {"typ": "akapit", "tekst": "Plan ogólny jest **aktem prawa miejscowego**."},
        {"typ": "lista", "punkty": ["POG", "MPZP", ""]},
        {"typ": "ramka", "tytul": "", "tekst": "Szkoła do 1500 m."},
        {"typ": "wykres", "tekst": "nieznany typ — pominięty"}]},
        {"naglowek": "Pusta sekcja", "bloki": []}],
    "pojecia": [{"pojecie": "Strefa & <znaczniki>", "definicja": "Obszar \x0b o funkcji dominującej."}, {"pojecie": "bez definicji"}],
    "do_zapamietania": ["Plan miejscowy zgodny z ogólnym."],
}


def test_oczysc_notatki():
    n = notatki.oczysc("```json\n" + json.dumps(ODPOWIEDZ) + "\n```")
    assert [s["naglowek"] for s in n["sekcje"]] == ["Akty"]  # pusta sekcja i nieznany blok odpadają
    bloki = n["sekcje"][0]["bloki"]
    assert [b["typ"] for b in bloki] == ["akapit", "lista", "ramka"] and bloki[1]["punkty"] == ["POG", "MPZP"]
    assert bloki[2]["tytul"] == "Uwaga" and len(n["pojecia"]) == 1
    for zle in ("nie json", "[]", json.dumps({"tytul": "x", "sekcje": []})):
        with pytest.raises(notatki.BladNotatek):
            notatki.oczysc(zle)


def test_liczby_spoza_materialu():
    n = notatki.oczysc(ODPOWIEDZ)
    material = "Od 2026 roku plan ogólny. Szkoła w odległości do 1 500 m."
    assert notatki.liczby_spoza_materialu(n, material) == ["3"]  # „Wykład 3” — nie ma w materiale
    assert notatki.liczby_spoza_materialu(n, material + " Wykład 3") == []


def test_plik_word():
    n = notatki.oczysc(ODPOWIEDZ)
    dane = word.notatki_docx(n, "Źródło: wyklad.pdf")
    z = zipfile.ZipFile(io.BytesIO(dane))
    assert z.namelist()[0] == "[Content_Types].xml"
    for nazwa in z.namelist():
        minidom.parseString(z.read(nazwa))  # każdy XML poprawny (znak sterujący \x0b usunięty)
    dokument = z.read("word/document.xml").decode()
    assert '<w:pStyle w:val="Title"/>' in dokument and '<w:pStyle w:val="Heading1"/>' in dokument
    assert "Strefa &amp; &lt;znaczniki&gt;" in dokument
    assert '<w:rPr><w:b/></w:rPr><w:t xml:space="preserve">aktem prawa miejscowego</w:t>' in dokument  # **…** → pogrubienie
    assert "✓  Plan miejscowy" in dokument and "Źródło: wyklad.pdf" in dokument
    assert "PAGE" in z.read("word/footer1.xml").decode() and "updateFields" not in z.read("word/settings.xml").decode()


def test_trasy_notatek(client, monkeypatch):
    from praca import routes
    wywolania = []
    monkeypatch.setattr(routes, "utworz_notatki", lambda material, pliki, dlugosc="standard": wywolania.append((material, pliki)) or json.dumps(ODPOWIEDZ))
    with open(PDF, "rb") as f:  # PDF z tekstem — idzie jako tekst, liczby sprawdzane
        r = client.post("/praca/notatki/utworz", data={"pliki": [(f, "grafik.pdf")]}, content_type="multipart/form-data")
    w = r.get_json()
    assert r.status_code == 200 and wywolania[-1][1] == [] and "Patryk" in wywolania[-1][0]
    assert "1500" in w["liczby_do_sprawdzenia"] and w["zrodlo"] == "grafik.pdf"
    r = client.post("/praca/notatki/utworz", data={"pliki": [(io.BytesIO(b"\xff\xd8x"), "a.jpg"), (io.BytesIO(b"\xff\xd8y"), "b.PNG")]},
                    content_type="multipart/form-data")
    assert r.get_json()["liczby_do_sprawdzenia"] is None and [t for _, t in wywolania[-1][1]] == ["image/jpeg", "image/png"]
    assert client.post("/praca/notatki/utworz", data={}, content_type="multipart/form-data").status_code == 400
    r = client.post("/praca/notatki/utworz", data={"pliki": [(io.BytesIO(b"x"), "a.docx")]}, content_type="multipart/form-data")
    assert r.status_code == 400
    monkeypatch.setattr(routes, "utworz_notatki", lambda material, pliki, dlugosc="standard": "nie json")
    r = client.post("/praca/notatki/utworz", data={"pliki": [(io.BytesIO(b"\xff\xd8x"), "a.jpg")]}, content_type="multipart/form-data")
    assert r.status_code == 422

    r = client.post("/praca/notatki.docx", json={"notatki": ODPOWIEDZ, "zrodlo": "wyklad.pdf"})
    assert r.status_code == 200 and r.data[:2] == b"PK"
    assert r.headers["Content-Disposition"] == "attachment; filename*=UTF-8''Planowanie_w_gminie.docx"
    assert client.post("/praca/notatki.docx", json={"notatki": {"tytul": "x"}}).status_code == 400


# ---------- ETAP 232: wyłączanie zmian i historia miesięcy ----------


def test_pominiete_zmiany():
    w = grafik.rozliczenie(KOMORKAMI, "Patryk", pominiete={"17|8:30|12:30"})
    assert [(z["dzien"], z["wliczona"]) for z in w["zmiany"]] == [(16, True), (17, False), (27, True)]
    assert (w["wliczonych"], w["godziny"], w["minuty"], w["kwota_dokladna"]) == (2, "9", 540, "282.60")
    assert "17 października" not in w["tekst"] and w["tekst"].splitlines()[-2] == "4,5+4,5=9"


def test_historia_rozliczen(client):
    cialo = {"tekst": KOMORKAMI, "imie": "Patryk", "stawka": "31,4"}
    h = client.post("/praca/rozliczenia", json=cialo).get_json()
    assert [(m["nazwa"], m["godziny"], m["kwota_tekst"], m["zmian"]) for m in h["miesiace"]] == [("październik 2026", "13", "408,20", 3)]
    # ponowny zapis tego samego miesiąca zastępuje (np. po odznaczeniu zmiany); liczby zawsze z serwera
    h = client.post("/praca/rozliczenia", json={**cialo, "pominiete": ["17|8:30|12:30"], "kwota": "999999"}).get_json()
    assert len(h["miesiace"]) == 1 and h["miesiace"][0]["kwota_tekst"] == "282,60"
    wrzesien = "wrzesień 2026\n4.\nPatryk\n15:00-20:00\n5.\nPatryk\n8:00-14:00"
    h = client.post("/praca/rozliczenia", json={**cialo, "tekst": wrzesien}).get_json()
    assert [m["nazwa"] for m in h["miesiace"]] == ["październik 2026", "wrzesień 2026"]
    assert h["lata"] == [{"rok": 2026, "minuty": 1200, "kwota": "628,00", "miesiecy": 2, "godziny": "20"}]  # 282,60 + 11 h × 31,4 = 345,40
    assert "październik 2026: 9 h, 282,60 zł" in client.get("/").get_data(as_text=True)
    assert client.post("/praca/rozliczenia", json={**cialo, "imie": ""}).status_code == 400
    pierwszy = h["miesiace"][0]["id"]
    assert len(client.delete(f"/praca/rozliczenia/{pierwszy}").get_json()["miesiace"]) == 1
    assert client.delete(f"/praca/rozliczenia/{pierwszy}").status_code == 404
    assert len(client.get("/praca/rozliczenia").get_json()["miesiace"]) == 1



# ---------- ETAP 233: pytania kontrolne, długość, wklejony tekst, fiszki ----------

Z_PYTANIAMI = {**ODPOWIEDZ, "pytania": [{"pytanie": "Co zastąpił plan ogólny?", "odpowiedz": "Studium uwarunkowań."},
                                        {"pytanie": "Bez odpowiedzi?", "odpowiedz": ""}]}


def test_pytania_w_notatce_i_w_wordzie():
    n = notatki.oczysc(Z_PYTANIAMI)
    assert n["pytania"] == [{"pytanie": "Co zastąpił plan ogólny?", "odpowiedz": "Studium uwarunkowań."}]
    z = zipfile.ZipFile(io.BytesIO(word.notatki_docx(n, "Źródło: x")))
    dokument = z.read("word/document.xml").decode()
    assert "Sprawdź się" in dokument and '<w:numId w:val="2"/>' in dokument
    assert dokument.index("Co zastąpił") < dokument.index("<w:pageBreakBefore/>") < dokument.index("Studium uwarunkowań.") < dokument.index("Źródło: x")
    minidom.parseString(z.read("word/numbering.xml"))
    assert notatki.oczysc(ODPOWIEDZ)["pytania"] == []  # odpowiedź bez pytań (starsza) — bez sekcji
    assert "Sprawdź się" not in zipfile.ZipFile(io.BytesIO(word.notatki_docx(notatki.oczysc(ODPOWIEDZ), "x"))).read("word/document.xml").decode()


def test_fiszki_csv_do_importu():
    from fiszki import importer
    n = notatki.oczysc(Z_PYTANIAMI)
    nowe, bledne = importer.wczytaj(notatki.fiszki_csv(n))
    assert [(f["pytanie"], f["odpowiedz"]) for f in nowe] == [
        ("Co zastąpił plan ogólny?", "Studium uwarunkowań."), ("Co to jest: Strefa & <znaczniki>?", "Obszar o funkcji dominującej.")]


def test_wklejony_tekst_dlugosc_i_trasa_fiszek(client, monkeypatch):
    from praca import routes
    wywolania = []
    monkeypatch.setattr(routes, "utworz_notatki", lambda material, pliki, dlugosc: wywolania.append((material, pliki, dlugosc)) or json.dumps(Z_PYTANIAMI))
    tekst = "Plan ogólny gminy zastępuje studium od 2026 r. Szkoła do 1500 m. " * 2
    r = client.post("/praca/notatki/utworz", data={"tekst": tekst, "dlugosc": "zwiezle"}, content_type="multipart/form-data")
    w = r.get_json()
    assert r.status_code == 200 and wywolania[-1] == (tekst.strip(), [], "zwiezle")
    assert w["zrodlo"] == "wklejony tekst" and w["liczby_do_sprawdzenia"] == ["3"] and len(w["notatki"]["pytania"]) == 1
    assert client.post("/praca/notatki/utworz", data={"tekst": "za krótko"}, content_type="multipart/form-data").status_code == 400
    assert client.post("/praca/notatki/utworz", data={"tekst": tekst, "dlugosc": "epopeja"}, content_type="multipart/form-data").status_code == 400
    r = client.post("/praca/notatki/fiszki.csv", json={"notatki": Z_PYTANIAMI})
    assert r.status_code == 200 and r.get_data(as_text=True).startswith("\ufeffpytanie;odpowiedz")
    assert r.headers["Content-Disposition"].endswith("Planowanie_w_gminie_fiszki.csv")
    bez = {**ODPOWIEDZ, "pojecia": [], "pytania": []}
    assert client.post("/praca/notatki/fiszki.csv", json={"notatki": bez}).status_code == 400


# ---------- ETAP 234: warstwa Gemini modułu Praca (bez sieci) ----------


class _OdpGemini:
    def __init__(self, text):
        self.text = text


def test_gemini_grafik_i_notatki_bez_sieci(monkeypatch):
    from dane import gemini
    wywolania = []
    monkeypatch.setattr(gemini.Config, "GEMINI_API_KEY", "test")
    monkeypatch.setattr(gemini, "_generuj", lambda contents, **k: wywolania.append((contents, k)) or _OdpGemini(" 16.\nPatryk\n15:30-20:00 "))
    assert gemini.przepisz_grafik(b"\xff\xd8x", "image/jpeg") == "16.\nPatryk\n15:30-20:00"
    czesci, ustawienia = wywolania[-1]
    assert czesci[0].inline_data.mime_type == "image/jpeg" and ustawienia["temperature"] == 0
    with pytest.raises(gemini.BladGemini, match="Obsługiwane"):
        gemini.przepisz_grafik(b"x", "text/plain")
    monkeypatch.setattr(gemini, "_generuj", lambda contents, **k: _OdpGemini(""))
    with pytest.raises(gemini.BladGemini, match="nie odczytał"):
        gemini.przepisz_grafik(b"x", "image/png")

    monkeypatch.setattr(gemini, "_generuj", lambda contents, **k: wywolania.append((contents, k)) or _OdpGemini('{"tytul": "x"}'))
    assert gemini.utworz_notatki("Tekst wykładu", dlugosc="zwiezle") == '{"tytul": "x"}'
    czesci, ustawienia = wywolania[-1]
    assert czesci == ["Materiał:\nTekst wykładu"] and "ZWIĘZŁE" in ustawienia["system_instruction"]
    assert ustawienia["response_mime_type"] == "application/json"
    gemini.utworz_notatki(pliki=[(b"\x89PNG", "image/png")], dlugosc="nieznana")
    czesci, ustawienia = wywolania[-1]
    assert czesci[0].inline_data.mime_type == "image/png" and "umiarkowanej" in ustawienia["system_instruction"]
    with pytest.raises(gemini.BladGemini):
        gemini.utworz_notatki(pliki=[(b"x", "application/zip")])
    monkeypatch.setattr(gemini, "_generuj", lambda contents, **k: _OdpGemini("  "))
    with pytest.raises(gemini.BladGemini, match="nie zwrócił"):
        gemini.utworz_notatki("x")
    monkeypatch.setattr(gemini.Config, "GEMINI_API_KEY", "")
    with pytest.raises(gemini.BladGemini, match="GEMINI_API_KEY"):
        gemini.utworz_notatki("x")
