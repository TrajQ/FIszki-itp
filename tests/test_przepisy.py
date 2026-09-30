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


# ---------- ETAP 77: porównanie wersji aktu ----------

from przepisy.porownanie import porownaj, roznice_slow  # noqa: E402


def test_roznice_slow_i_porownanie():
    assert roznice_slow("Wójt sporządza projekt planu.", "Wójt  sporządza\nprojekt planu ogólnego.") == [
        {"typ": "=", "tekst": "Wójt sporządza projekt"}, {"typ": "-", "tekst": "planu."}, {"typ": "+", "tekst": "planu ogólnego."}]

    def j(o, t):
        return {"oznaczenie": o, "tekst": t, "id": hash(o) % 1000}

    stare = [j("Tytuł", "USTAWA"), j("Art. 1", "Art. 1. Bez zmian."), j("Art. 2", "Art. 2. Stary."), j("Art. 3", "Art. 3. Uchylony później."), j("Art. 4", "Art. 4. Ten sam.")]
    nowe = [j("Tytuł", "USTAWA"), j("Art. 1", "Art. 1.  Bez\nzmian."), j("Art. 2", "Art. 2. Nowy."), j("Art. 4", "Art. 4. Ten sam."), j("Art. 4a", "Art. 4a. Dodany.")]
    w = porownaj(stare, nowe)
    assert [(p["oznaczenie"], p["status"]) for p in w["jednostki"]] == [
        ("Art. 1", "bez zmian"), ("Art. 2", "zmieniona"), ("Art. 3", "usunięta"), ("Art. 4", "bez zmian"), ("Art. 4a", "dodana")]
    assert w["liczby"] == {"zmieniona": 1, "dodana": 1, "usunięta": 1, "bez zmian": 2}


def test_strona_porownania(client):
    wgraj(client)
    wgraj(client)  # druga wersja — atrapa z tym samym tekstem
    html = client.get("/przepisy/porownanie?stary=1&nowy=2").get_data(as_text=True)
    assert "zmienione: 0" in html and "Brak różnic" in html
    assert "Art. 15a" in client.get("/przepisy/porownanie?stary=1&nowy=2&wszystkie=1").get_data(as_text=True)
    assert client.get("/przepisy/porownanie?stary=1&nowy=9").status_code == 404


# ---------- ETAP 82: fiszki z artykułu ----------

from przepisy.pytania import sprawdz_propozycje_fiszek  # noqa: E402


def test_sprawdz_propozycje_fiszek():
    j = {"oznaczenie": "Art. 15", "tekst": "Art. 15. 2. W planie miejscowym określa się obowiązkowo maksymalną intensywność zabudowy w terminie 30 dni."}
    dobre, odrzucone = sprawdz_propozycje_fiszek([
        {"pytanie": "Co określa plan?", "odpowiedz": "Intensywność (art. 15 ust. 2).", "fragment": "określa się  obowiązkowo maksymalną intensywność"},
        {"pytanie": "W jakim terminie?", "odpowiedz": "30 dni.", "fragment": "w terminie 30 dni"},
        {"pytanie": "Ile pięter?", "odpowiedz": "Najwyżej 5.", "fragment": "maksymalną intensywność zabudowy"},  # liczba spoza tekstu
        {"pytanie": "?", "odpowiedz": "x", "fragment": "tego zdania nie ma w przepisie"},
    ], j)
    assert [d["odpowiedz"] for d in dobre] == ["Intensywność (art. 15 ust. 2).", "30 dni."] and odrzucone == 2
    assert dobre[0]["fragment"] == "określa się obowiązkowo maksymalną intensywność"


def test_fiszki_z_artykulu(client, monkeypatch):
    wgraj(client)
    jednostka = next(j for j in client.application.test_client().get("/przepisy/szukaj?q=art. 15").get_json()["wyniki"])
    monkeypatch.setattr(gemini, "zaproponuj_fiszki_z_przepisu", lambda tekst, oznaczenie, liczba=4: [
        {"pytanie": "Kto sporządza projekt planu?", "odpowiedz": "Wójt (art. 15 ust. 1).", "fragment": "Wójt sporządza projekt planu miejscowego"},
        {"pytanie": "Zmyślone", "odpowiedz": "x", "fragment": "zdanie spoza przepisu"}])
    url = f"/przepisy/jednostki/{jednostka['id']}"
    dane = client.post(url + "/szkice-fiszek").get_json()
    assert len(dane["propozycje"]) == 1 and dane["odrzucone"] == 1

    r = client.post(url + "/fiszki", json={"fiszki": dane["propozycje"], "tematy": ["planowanie"]})
    assert r.status_code == 201 and r.get_json()["dodane"] == 1
    fiszki = client.get(r.get_json()["url"] + "fiszki").get_json()
    assert fiszki[0]["fragment_tekstu"] == "Wójt sporządza projekt planu miejscowego" and fiszki[0]["strona"] == 2

    # podrobiony cytat i pusta odpowiedź — nic nie zapisujemy (także pierwszej, poprawnej)
    zle = [dane["propozycje"][0], {"pytanie": "a", "odpowiedz": "b", "fragment": "nie ma tego w artykule"}]
    assert client.post(url + "/fiszki", json={"fiszki": zle}).status_code == 400
    assert client.post(url + "/fiszki", json={"fiszki": [{**dane["propozycje"][0], "odpowiedz": " "}]}).status_code == 400
    assert len(client.get(r.get_json()["url"] + "fiszki").get_json()) == 1
    assert client.post("/przepisy/jednostki/999/szkice-fiszek").status_code == 404


# ---------- ETAP 88: akty z API Sejmu ----------

from dane import sejm  # noqa: E402


class _Odp:
    def __init__(self, json_=None, tresc=b"", status=200):
        self._json, self.tresc, self.status_code = json_, tresc, status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(response=self)

    def json(self):
        return self._json

    def iter_content(self, rozmiar):
        yield self.tresc


def test_sejm_szukaj_i_pobierz(client, monkeypatch):
    zapytania = []
    wyniki = {"count": 3, "items": [
        {"publisher": "DU", "year": 2003, "pos": 717, "title": "Ustawa z dnia 27 marca 2003 r. o planowaniu i zagospodarowaniu przestrzennym",
         "type": "Ustawa", "status": "obowiązujący", "textPDF": True},
        {"publisher": "DU", "year": 2024, "pos": 1130, "title": "Obwieszczenie Marszałka Sejmu RP w sprawie ogłoszenia jednolitego tekstu ustawy o planowaniu i zagospodarowaniu przestrzennym",
         "type": "Obwieszczenie", "status": "obowiązujący", "textPDF": "/eli/acts/DU/2024/1130/text.pdf"},
        {"publisher": "DU", "year": "x", "pos": 1, "title": "zepsuty wpis"},
    ]}

    def get(url, params=None, **k):
        zapytania.append((url, params))
        if url.endswith("/search"):
            return _Odp(wyniki)
        return _Odp(tresc=b"%PDF-1.4 ustawa")

    monkeypatch.setattr(sejm.requests, "get", get)
    akty = client.get("/przepisy/sejm/szukaj?q=planowaniu").get_json()
    assert [a["adres"] for a in akty] == ["Dz.U. 2024 poz. 1130", "Dz.U. 2003 poz. 717"]  # najnowsze najpierw
    assert akty[0]["tekst_jednolity"] and akty[0]["ma_pdf"] and not akty[1]["tekst_jednolity"]
    assert zapytania[0][1] == {"title": "planowaniu", "publisher": "DU", "limit": sejm.MAKS_WYNIKOW}
    assert client.get("/przepisy/sejm/szukaj?q=ab").status_code == 502  # za krótkie

    odp = client.post("/przepisy/sejm/pobierz", json={"rok": 2024, "pozycja": 1130, "tytul": "Obwieszczenie … jednolitego tekstu"})
    assert odp.status_code == 201
    assert zapytania[-1][0] == "https://api.sejm.gov.pl/eli/acts/DU/2024/1130/text.pdf"
    html = client.get(odp.get_json()["url"]).get_data(as_text=True)
    assert "(Dz.U. 2024 poz. 1130)" in html and "Art. 1" in html
    assert client.post("/przepisy/sejm/pobierz", json={"rok": "x"}).status_code == 400

    monkeypatch.setattr(sejm.requests, "get", lambda url, **k: _Odp(tresc=b"<html>nie PDF"))
    assert "nie zwróciło pliku PDF" in client.post("/przepisy/sejm/pobierz", json={"rok": 2024, "pozycja": 1}).get_json()["blad"]

    def brak_sieci(*a, **k):
        raise sejm.requests.ConnectionError("x")

    monkeypatch.setattr(sejm.requests, "get", brak_sieci)
    assert "brak połączenia" in client.get("/przepisy/sejm/szukaj?q=planowaniu").get_json()["blad"]


# ---------- ETAP 101: czy jest nowszy tekst jednolity ----------


def test_adres_i_przedmiot():
    assert sejm.adres_i_przedmiot("Obwieszczenie Marszałka Sejmu RP z dnia 5 lipca 2024 r. w sprawie ogłoszenia jednolitego tekstu ustawy o planowaniu i zagospodarowaniu przestrzennym (Dz.U. 2024 poz. 1130)") == (2024, 1130, "o planowaniu i zagospodarowaniu przestrzennym")
    assert sejm.adres_i_przedmiot("Ustawa z dnia 7 lipca 1994 r. - Prawo budowlane (Dz.U. 1994 poz. 414)") == (1994, 414, "Prawo budowlane")
    assert sejm.adres_i_przedmiot("USTAWA z dnia 7 lipca 1994 r. Prawo budowlane") is None  # wgrany PDF bez adresu


def test_nowszy_tekst_jednolity(client, monkeypatch):
    def tj(rok, poz, tytul="Obwieszczenie … w sprawie ogłoszenia jednolitego tekstu ustawy o planowaniu i zagospodarowaniu przestrzennym"):
        return {"publisher": "DU", "year": rok, "pos": poz, "title": tytul, "textPDF": True, "status": "obowiązujący"}

    wyniki = {"items": [tj(2023, 977), tj(2024, 1130), tj(2025, 50), tj(2025, 60, "Ustawa o zmianie ustawy o planowaniu i zagospodarowaniu przestrzennym"),
                        tj(2026, 5, "Obwieszczenie … jednolitego tekstu ustawy o planowaniu przestrzennym w innym akcie")]}
    zapytania = []

    def get(url, params=None, **k):
        zapytania.append(params)
        return _Odp(wyniki) if url.endswith("/search") else _Odp(tresc=b"%PDF-1.4 x")

    monkeypatch.setattr(sejm.requests, "get", get)
    odp = client.post("/przepisy/sejm/pobierz", json={"rok": 2024, "pozycja": 1130, "tytul": tj(2024, 1130)["title"]})
    akt_url = odp.get_json()["url"]
    akt_id = int(akt_url.rstrip("/").split("/")[-1])
    assert "Czy jest nowszy tekst?" in client.get(akt_url).get_data(as_text=True)
    w = client.get(f"/przepisy/akty/{akt_id}/aktualnosc").get_json()
    assert w["przedmiot"] == "o planowaniu i zagospodarowaniu przestrzennym" and w["adres"] == "Dz.U. 2024 poz. 1130"
    assert [a["adres"] for a in w["nowsze"]] == ["Dz.U. 2025 poz. 50"]  # starsze, nowelizacje i inne ustawy odpadają
    assert zapytania[-1]["title"] == "o planowaniu i zagospodarowaniu przestrzennym"
    wgraj(client)  # akt wgrany z dysku — bez adresu Dz.U.
    assert client.get("/przepisy/akty/2/aktualnosc").status_code == 422
