"""Moduł przepisy: podział aktu na jednostki, wyszukiwarka, API (ETAP 61)."""

import io

import pytest

from app import create_app
from przepisy import routes
from przepisy.baza import podglad, terminy, zapytanie_fts
from przepisy.tekst import BladPdf, podziel, strony_z_pdf

STRONY = [
    "©Kancelaria Sejmu s. 1/2\n2024-01-02\nUSTAWA\nz dnia 27 marca 2003 r.\no planowaniu i zagospodarowaniu przestrzennym\n"
    "Rozdział 1\nPrzepisy ogólne\n"
    "Art. 1. 1. Ustawa określa zasady kształtowania polityki przestrzennej.\n"
    "2. W planowaniu uwzględnia się wymagania ładu przestrzen-\nnego, w tym urbanistyki.\n"
    "Art. 2. Ilekroć w ustawie jest mowa o:\n1) działce budowlanej – należy przez to rozumieć nieruchomość gruntową;\n"
    "2) terenie – zgodnie z art. 15 ust. 2 ustawy.\n1",
    "©Kancelaria Sejmu s. 2/2\nRozdział 2\nPlan miejscowy\n"
    "Art. 15. 1. Wójt sporządza projekt planu miejscowego.\n"
    "2. W planie miejscowym określa się obowiązkowo maksymalną intensywność zabudowy.\n"
    "Art. 15a. Uchwała w sprawie planu ogólnego gminy.\n§ 3. Rozporządzenie wchodzi w życie.",
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    # Zamiast prawdziwego PDF-a — gotowy tekst stron (pypdf testuje osobny test).
    monkeypatch.setattr(routes, "strony_z_pdf", lambda sciezka: STRONY)
    with app.test_client() as c:
        yield c


def wgraj(client, nazwa="ustawa.pdf", tresc=b"%PDF-1.4 atrapa"):
    return client.post("/przepisy/akty", data={"plik": (io.BytesIO(tresc), nazwa)}, content_type="multipart/form-data")


def test_podzial_na_jednostki():
    j = podziel(STRONY)
    assert [x["oznaczenie"] for x in j] == ["Tytuł", "Art. 1", "Art. 2", "Art. 15", "Art. 15a", "§ 3"]
    assert j[0]["tekst"] == "USTAWA z dnia 27 marca 2003 r. o planowaniu i zagospodarowaniu przestrzennym"
    # nagłówek strony, data i numer strony wycięte; przeniesienie wyrazu sklejone; ustęp w nowym wierszu
    assert j[1]["tekst"] == (
        "Art. 1. 1. Ustawa określa zasady kształtowania polityki przestrzennej.\n"
        "2. W planowaniu uwzględnia się wymagania ładu przestrzennego, w tym urbanistyki."
    )
    assert j[1]["naglowek"] == "Rozdział 1 Przepisy ogólne" and j[3]["naglowek"] == "Rozdział 2 Plan miejscowy"
    assert "\n2) terenie – zgodnie z art. 15 ust. 2 ustawy." in j[2]["tekst"]  # odesłanie nie tnie tekstu
    assert (j[2]["strona_od"], j[2]["strona_do"], j[3]["strona_od"]) == (1, 1, 2)
    assert "Kancelaria" not in " ".join(x["tekst"] for x in j)


def test_zapytanie_fts_odmiana_i_fraza():
    assert zapytanie_fts("Działki budowlanej") == '"dzial"* AND "budowlan"*'
    assert zapytanie_fts("plan ust") == '"plan" AND "ust"'
    assert zapytanie_fts('"działka budowlana" gminy') == '"dzialka budowlana" AND "gmin"*'
    assert zapytanie_fts("  !!  ") is None


def test_podglad_z_trafieniami_w_oryginalnym_tekscie():
    tekst = "Wstęp " * 30 + "Łódzka DZIAŁKA budowlana leży w gminie."
    p = podglad(tekst, terminy("lodzka dzialki"))
    assert p.startswith("… ") and "\x02Łódzka\x03 \x02DZIAŁKA\x03 budowlana" in p
    assert podglad("krótki tekst", []) == "krótki tekst"


def test_wgranie_wyszukiwanie_i_usuniecie(client, tmp_path):
    r = wgraj(client)
    assert r.status_code == 302 and "/przepisy/akty/1" in r.headers["Location"]
    html = client.get("/przepisy/akty/1").get_data(as_text=True)
    assert "USTAWA z dnia 27 marca 2003 r." in html and 'id="j2"' in html and "#page=2" in html

    def szukaj(q, **kw):
        return client.get("/przepisy/szukaj", query_string={"q": q, **kw}).get_json()["wyniki"]

    # bez polskich znaków i w innej formie niż w tekście
    wyniki = szukaj("dzialki budowlane")
    assert [w["oznaczenie"] for w in wyniki] == ["Art. 2"]
    assert "\x02" in wyniki[0]["podglad"] and wyniki[0]["nazwa_aktu"].startswith("USTAWA")
    assert [w["oznaczenie"] for w in szukaj("intensywności zabudowy")] == ["Art. 15"]
    assert [w["oznaczenie"] for w in szukaj("art. 15a")] == ["Art. 15a"]
    assert [w["oznaczenie"] for w in szukaj("§3")] == ["§ 3"]
    assert szukaj("intensywność", akt=99) == [] and szukaj("") == []

    assert client.put("/przepisy/akty/1", json={"nazwa": "  Ustawa   o planowaniu "}).get_json()["nazwa"] == "Ustawa o planowaniu"
    assert client.put("/przepisy/akty/1", json={"nazwa": ""}).status_code == 400
    assert "Akty: 1" in client.get("/").get_data(as_text=True)

    assert client.delete("/przepisy/akty/1").get_json() == {"ok": True}
    assert szukaj("intensywność") == [] and client.get("/przepisy/akty/1").status_code == 404
    assert list((tmp_path / "przepisy" / "pliki").iterdir()) == []


def test_zly_plik_i_blad_pdf(client, monkeypatch, tmp_path):
    r = wgraj(client, nazwa="notatki.txt", tresc=b"zwykly tekst")
    assert "blad=" in r.headers["Location"]

    def bez_tekstu(sciezka):
        raise BladPdf("PDF nie ma warstwy tekstowej")

    monkeypatch.setattr(routes, "strony_z_pdf", bez_tekstu)
    r = wgraj(client)
    assert "blad=" in r.headers["Location"] and list((tmp_path / "przepisy" / "pliki").iterdir()) == []


def _minimalny_pdf(linie: list[str]) -> bytes:
    """Jednostronicowy PDF z tekstem (Helvetica, tylko ASCII) — bez zależności."""
    tresc = "BT /F1 11 Tf 14 TL 72 760 Td " + " ".join(f"({t}) Tj T*" for t in linie) + " ET"
    obiekty = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(tresc)} >>\nstream\n{tresc}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    wynik, przesuniecia = b"%PDF-1.4\n", []
    for i, obiekt in enumerate(obiekty, start=1):
        przesuniecia.append(len(wynik))
        wynik += f"{i} 0 obj\n{obiekt}\nendobj\n".encode()
    xref = len(wynik)
    wynik += f"xref\n0 {len(obiekty) + 1}\n0000000000 65535 f \n".encode()
    wynik += "".join(f"{p:010d} 00000 n \n" for p in przesuniecia).encode()
    wynik += f"trailer\n<< /Size {len(obiekty) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return wynik


def test_prawdziwy_pdf_przez_pypdf(tmp_path):
    sciezka = tmp_path / "akt.pdf"
    sciezka.write_bytes(_minimalny_pdf(["ROZPORZADZENIE MINISTRA", "Par. wstep", "Art. 1. Przepis pierwszy.", "Art. 2. Przepis drugi."]))
    j = podziel(strony_z_pdf(str(sciezka)))
    assert [x["oznaczenie"] for x in j] == ["Tytuł", "Art. 1", "Art. 2"]

    zepsuty = tmp_path / "zly.pdf"
    zepsuty.write_bytes(b"%PDF-1.4\nto nie jest PDF")
    with pytest.raises(BladPdf):
        strony_z_pdf(str(zepsuty))
    pusty = tmp_path / "pusty.pdf"
    pusty.write_bytes(_minimalny_pdf([]))
    with pytest.raises(BladPdf, match="warstwy tekstowej"):
        strony_z_pdf(str(pusty))


# ---------- ETAP 62: pytania z cytatami ----------

from dane import gemini  # noqa: E402
from przepisy.pytania import BladOdpowiedzi, do_porownania, sprawdz  # noqa: E402

JEDNOSTKI = [
    {"id": 7, "akt_id": 1, "oznaczenie": "Art. 15", "nazwa_aktu": "Ustawa", "strona_od": 2,
     "tekst": "Art. 15. 2. W planie miejscowym określa się obowiązkowo maksymalną intensywność zabudowy – jako wskaźnik."},
    {"id": 9, "akt_id": 1, "oznaczenie": "§ 12", "nazwa_aktu": "Rozporządzenie", "strona_od": 5,
     "tekst": "§ 12. Odległość budynku od granicy działki wynosi 4 m."},
]


def test_sprawdz_cytaty_i_liczby():
    wynik = sprawdz(
        {
            "odpowiedz": "Plan musi określać maksymalną intensywność, a budynek stoi 4 m od granicy (§ 12).",
            "cytaty": [
                {"fragment": 1, "cytat": "określa się obowiązkowo  maksymalną intensywność zabudowy - jako"},  # inne spacje i myślnik
                {"fragment": 2, "cytat": "„Odległość budynku od granicy działki wynosi 4 m.”"},
                {"fragment": 2, "cytat": "Odległość budynku wynosi 3 m od granicy."},  # wymyślony
                {"fragment": 5, "cytat": "nie ma takiego fragmentu w ogóle"},
                "zły format",
            ],
        },
        JEDNOSTKI,
        "Jaka odległość od granicy?",
    )
    assert [c["oznaczenie"] for c in wynik["cytaty"]] == ["Art. 15", "§ 12"]
    assert wynik["cytaty"][1] == {"cytat": "Odległość budynku od granicy działki wynosi 4 m.", "jednostka_id": 9, "akt_id": 1,
                                  "oznaczenie": "§ 12", "nazwa_aktu": "Rozporządzenie", "strona": 5}
    assert wynik["odrzucone_cytaty"] == 3 and wynik["brak_odpowiedzi"] is False
    assert do_porownania("A „b” – c") == do_porownania('a "b" - c')


@pytest.mark.parametrize(
    "surowa, komunikat",
    [
        ({"odpowiedz": "Tak.", "cytaty": [{"fragment": 1, "cytat": "tego nie ma w przepisie wcale"}]}, "cytatu"),
        ({"odpowiedz": "Odległość to 5 m.", "cytaty": [{"fragment": 2, "cytat": "Odległość budynku od granicy działki"}]}, "5"),
        ({"odpowiedz": "", "cytaty": []}, "nie podał odpowiedzi"),
    ],
)
def test_sprawdz_odrzuca(surowa, komunikat):
    with pytest.raises(BladOdpowiedzi, match=komunikat):
        sprawdz(surowa, JEDNOSTKI, "pytanie")


def test_brak_odpowiedzi_bez_cytatow_jest_dozwolony():
    wynik = sprawdz({"odpowiedz": "Fragmenty nie mówią o linii zabudowy.", "brak_odpowiedzi": True}, JEDNOSTKI, "linia zabudowy?")
    assert wynik["brak_odpowiedzi"] is True and wynik["cytaty"] == []


def test_api_pytania_i_historia(client, monkeypatch):
    wgraj(client)
    widziane = {}

    def udawany_model(pytanie, fragmenty):
        widziane["fragmenty"] = fragmenty
        return {"odpowiedz": "Obowiązkowo określa się maksymalną intensywność zabudowy.",
                "cytaty": [{"fragment": 1, "cytat": "określa się obowiązkowo maksymalną intensywność zabudowy"}]}

    monkeypatch.setattr(gemini, "odpowiedz_z_przepisow", udawany_model)
    r = client.post("/przepisy/pytanie", json={"pytanie": "Co trzeba określić w planie miejscowym o intensywności?"})
    dane = r.get_json()
    assert r.status_code == 200 and dane["cytaty"][0]["oznaczenie"] == "Art. 15" and dane["cytaty"][0]["strona"] == 2
    assert widziane["fragmenty"][0].startswith("Art. 15 — USTAWA")  # najtrafniejsza jednostka pierwsza
    assert not any(f.startswith("Tytuł") for f in widziane["fragmenty"])
    html = client.get("/przepisy/").get_data(as_text=True)
    assert "Co trzeba okre" in html  # historia w stronie (JSON dla skryptu)

    assert client.post("/przepisy/pytanie", json={"pytanie": "  "}).status_code == 400
    assert client.post("/przepisy/pytanie", json={"pytanie": "x", "akt": 99}).status_code == 400
    assert client.post("/przepisy/pytanie", json={"pytanie": "kosmiczne rakiety"}).status_code == 404

    def zmyslajacy(pytanie, fragmenty):
        return {"odpowiedz": "Intensywność wynosi 2,5.", "cytaty": [{"fragment": 1, "cytat": "maksymalną intensywność zabudowy"}]}

    monkeypatch.setattr(gemini, "odpowiedz_z_przepisow", zmyslajacy)
    r = client.post("/przepisy/pytanie", json={"pytanie": "Jaka intensywność zabudowy?"})
    assert r.status_code == 502 and "2.5" in r.get_json()["blad"]

    assert client.delete(f"/przepisy/pytania/{dane['id']}").get_json() == {"ok": True}
    assert client.delete(f"/przepisy/pytania/{dane['id']}").status_code == 404

    # usunięcie aktu usuwa pytania z cytatami z niego (ETAP 66)
    monkeypatch.setattr(gemini, "odpowiedz_z_przepisow", udawany_model)
    client.post("/przepisy/pytanie", json={"pytanie": "Kontrolne pytanie o intensywność zabudowy"})
    assert "Kontrolne pytanie" in client.get("/przepisy/").get_data(as_text=True)
    client.delete("/przepisy/akty/1")
    assert "Kontrolne pytanie" not in client.get("/przepisy/").get_data(as_text=True)


# ---------- ETAP 68: fiszka z cytatu ----------

from przepisy.pytania import strona_cytatu  # noqa: E402


def test_strona_cytatu():
    teksty = {2: "Art. 15. 1. Wójt sporządza\nprojekt planu.", 3: "2. W planie miejscowym określa się obowiązkowo\nintensywność."}
    assert strona_cytatu(teksty, "określa się  obowiązkowo intensywność", 2) == 3
    assert strona_cytatu(teksty, "tego nie ma", 2) == 2
    assert strona_cytatu({}, "cokolwiek", 7) == 7


def test_fiszka_z_cytatu(client, monkeypatch):
    wgraj(client)
    monkeypatch.setattr(gemini, "odpowiedz_z_przepisow", lambda pytanie, fragmenty: {
        "odpowiedz": "Obowiązkowo określa się maksymalną intensywność zabudowy.",
        "cytaty": [{"fragment": 1, "cytat": "określa się obowiązkowo maksymalną intensywność zabudowy"}]})
    pytanie_id = client.post("/przepisy/pytanie", json={"pytanie": "Co z intensywnością zabudowy?"}).get_json()["id"]
    url = f"/przepisy/pytania/{pytanie_id}/fiszka"

    r = client.post(url, json={"cytat": 0, "pytanie": "Co plan określa obowiązkowo?", "odpowiedz": "maks. intensywność (art. 15)", "tematy": ["przepisy"]})
    assert r.status_code == 201
    wynik = r.get_json()
    assert wynik["strona"] == 2 and wynik["url"] == f"/fiszki/{wynik['pdf_id']}/"  # atrapa PDF-a: strona początku artykułu
    fiszki = client.get(f"/fiszki/{wynik['pdf_id']}/fiszki").get_json()
    assert fiszki[0]["fragment_tekstu"] == "określa się obowiązkowo maksymalną intensywność zabudowy"
    assert fiszki[0]["strona"] == 2 and fiszki[0]["tematy"] == ["przepisy"]

    # druga fiszka z tego samego aktu — ten sam PDF w fiszkach, bez kopii
    assert client.post(url, json={"cytat": 0, "pytanie": "Inne pytanie", "odpowiedz": "x"}).get_json()["pdf_id"] == wynik["pdf_id"]
    assert client.post(url, json={"cytat": 5, "pytanie": "a", "odpowiedz": "b"}).status_code == 400
    assert client.post(url, json={"cytat": 0, "pytanie": " ", "odpowiedz": "b"}).status_code == 400
    assert client.post("/przepisy/pytania/999/fiszka", json={"cytat": 0}).status_code == 404
