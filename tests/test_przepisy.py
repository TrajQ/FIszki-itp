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
