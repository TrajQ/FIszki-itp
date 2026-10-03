"""Moduł teren: pola projektu, plik z telefonu, import i eksport (ETAP 65)."""

import base64
import io
import json
import os
import re

import pytest

from app import create_app
from teren.projekt import WZORY, BladDanych, odczytaj_plik, sprawdz_pola

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60 + b"\xff\xd9"  # wystarczy nagłówek JPEG
ZDJECIE = "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()
POLA = sprawdz_pola(WZORY["zielen"]["pola"])


def punkt(uid="a1b2c3d4e5f6", **zmiany):
    p = {"uid": uid, "lat": 52.4, "lng": 16.9, "dokladnosc_m": 6.2, "czas": "2026-09-29T10:15:00.000Z",
         "wartosci": {"obiekt": "drzewo", "obwód pnia [cm]": 120, "stan": "dobry", "nieznane": 1}, "uwagi": " Lipa  przy ławce ", "zdjecie": ZDJECIE}
    return {**p, **zmiany}


def plik(klucz, *punkty):
    return {"format": "warsztat-teren", "wersja": 1, "projekt_klucz": klucz, "projekt_nazwa": "Zieleń", "punkty": list(punkty)}


def test_sprawdz_pola():
    assert sprawdz_pola([{"nazwa": "  stan ", "typ": "wybor", "opcje": ["a", " b ", ""]}]) == [{"nazwa": "stan", "typ": "wybor", "opcje": ["a", "b"], "skala": False}]
    for zle in ([], [{"nazwa": "", "typ": "tekst"}], [{"nazwa": "x", "typ": "data"}], [{"nazwa": "x", "typ": "wybor", "opcje": ["a"]}],
                [{"nazwa": "x", "typ": "tekst"}, {"nazwa": "X", "typ": "liczba"}]):
        with pytest.raises(BladDanych):
            sprawdz_pola(zle)


def test_odczytaj_plik():
    wynik = odczytaj_plik(plik("K", punkt(), punkt("bezgps00001", lat=None, lng=None, zdjecie=None, wartosci={}, uwagi="")), "K", POLA)
    p = wynik[0]
    assert p["wartosci"] == {"obiekt": "drzewo", "obwód pnia [cm]": 120.0, "stan": "dobry"}  # nieznane pole pominięte
    assert p["uwagi"] == "Lipa przy ławce" and p["zdjecie"] == JPEG and p["czas"] == "2026-09-29T10:15:00+00:00"
    assert wynik[1]["lat"] is None and wynik[1]["zdjecie"] is None


@pytest.mark.parametrize(
    "zmiana, komunikat",
    [
        ({"wartosci": {"stan": "świetny"}}, "nie ma na liście"),
        ({"wartosci": {"obwód pnia [cm]": "gruby"}}, "nie jest liczba"),
        ({"lat": 95}, "poza zakresem"),
        ({"uid": "x"}, "identyfikatora"),
        ({"czas": "wczoraj"}, "czas"),
        ({"zdjecie": "data:image/png;base64,AAAA"}, "JPEG"),
        ({"zdjecie": "data:image/jpeg;base64," + base64.b64encode(b"GIF89a").decode()}, "nie jest plik JPEG"),
    ],
)
def test_odczytaj_plik_odrzuca(zmiana, komunikat):
    with pytest.raises(BladDanych, match=komunikat):
        odczytaj_plik(plik("K", punkt(**zmiana)), "K", POLA)


def test_plik_innego_projektu_i_zly_format():
    with pytest.raises(BladDanych, match="innego projektu"):
        odczytaj_plik(plik("INNY", punkt()), "K", POLA)
    with pytest.raises(BladDanych, match="formularza terenowego"):
        odczytaj_plik({"type": "FeatureCollection"}, "K", POLA)


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_pelny_obieg(client, tmp_path):
    r = client.post("/teren/projekty", data={"nazwa": "Zieleń — Park Wilsona", "wzor": "zielen"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/teren/projekty/1")
    assert "Park Wilsona" in client.get("/teren/projekty/1").get_data(as_text=True)

    r = client.get("/teren/projekty/1/formularz.html")
    assert "attachment; filename=teren_zielen_park_wilsona.html" == r.headers["Content-Disposition"]
    html = r.get_data(as_text=True)
    klucz = re.search(r'"klucz": "([^"]+)"', html).group(1)
    assert "<script src" not in html and "<link" not in html  # samodzielny plik, bez zasobów z sieci

    def importuj(dane):
        return client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(json.dumps(dane).encode()), "teren.json")},
                           content_type="multipart/form-data")

    assert importuj(plik(klucz, punkt(), punkt("drugi000000", lat=None, lng=None))).get_json() == {"dodane": 2, "pominiete": 0}
    assert importuj(plik(klucz, punkt(), punkt("trzeci00000"))).get_json() == {"dodane": 1, "pominiete": 1}
    r = importuj(plik(klucz, punkt("czwarty0000", wartosci={"stan": "zły stan"})))
    assert r.status_code == 400 and "Punkt 1" in r.get_json()["blad"]

    punkty = client.get("/teren/projekty/1/punkty").get_json()
    assert len(punkty) == 3 and punkty[0]["zdjecie"].endswith(f"/zdjecia/{punkty[0]['id']}.jpg")
    with client.get(punkty[0]["zdjecie"]) as odp:  # plik ze zdjęciem — zamknąć odpowiedź
        assert odp.data == JPEG

    geo = json.loads(client.get("/teren/projekty/1.geojson").data)
    assert len(geo["features"]) == 2 and geo["features"][0]["properties"]["obiekt"] == "drzewo"
    csv = client.get("/teren/projekty/1.csv").get_data(as_text=True)
    assert csv.startswith("﻿id;czas;szerokosc;dlugosc;dokladnosc_m;polozenie_reczne;obiekt;gatunek;obwód pnia [cm];stan;uwagi;zdjecie")

    assert client.delete(f"/teren/projekty/1/punkty/{punkty[0]['id']}").get_json() == {"ok": True}
    assert len(list((tmp_path / "teren" / "zdjecia").iterdir())) == 2  # zdjęcie usuniętego punktu skasowane
    assert client.put("/teren/projekty/1", json={"nazwa": "Zieleń", "pola": []}).status_code == 400
    assert client.put("/teren/projekty/1", json={"nazwa": "Zieleń", "pola": [{"nazwa": "stan", "typ": "tak_nie"}]}).get_json()["pola"][0]["typ"] == "tak_nie"
    assert "Projekty: 1, punkty: 2" in client.get("/").get_data(as_text=True)

    assert client.delete("/teren/projekty/1").get_json() == {"ok": True}
    assert client.get("/teren/projekty/1").status_code == 404
    assert len(list((tmp_path / "teren" / "zdjecia").iterdir())) == 2  # ETAP 212: zdjęcia czekają w koszu 30 dni


def test_zly_import_i_nazwa(client):
    assert "blad=" in client.post("/teren/projekty", data={"nazwa": " ", "wzor": "zielen"}).headers["Location"]
    client.post("/teren/projekty", data={"nazwa": "Własny", "wzor": ""})
    r = client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(b"\x00nie json"), "x.json")}, content_type="multipart/form-data")
    assert r.status_code == 400


# ---------- ETAP 69: raport z terenu ----------

from teren import raport as raport_terenu  # noqa: E402


def test_zestawienie_i_numeracja():
    pola = sprawdz_pola([
        {"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "zły"]},
        {"nazwa": "obwód", "typ": "liczba"},
        {"nazwa": "chroniony", "typ": "tak_nie"},
        {"nazwa": "gatunek", "typ": "tekst"},
    ])
    punkty = raport_terenu.ponumeruj([
        {"id": 2, "czas": "2026-09-29T10:05:00", "wartosci": {"stan": "zły", "obwód": 80.0, "chroniony": True}},
        {"id": 1, "czas": "2026-09-29T10:00:00", "wartosci": {"stan": "dobry", "obwód": 120.0, "gatunek": "lipa"}},
        {"id": 3, "czas": "2026-09-29T10:09:00", "wartosci": {"stan": "dobry"}},
    ])
    assert [(p["id"], p["nr"]) for p in punkty] == [(1, 1), (2, 2), (3, 3)]  # kolejność pomiaru
    z = {x["nazwa"]: x for x in raport_terenu.zestawienie(pola, punkty)}
    assert [(r["wartosc"], r["liczba"]) for r in z["stan"]["rozklad"]] == [("dobry", 2), ("zły", 1)]
    assert z["stan"]["rozklad"][0]["procent"] == pytest.approx(66.667, abs=0.01)
    assert z["obwód"]["statystyki"] == {"min": 80.0, "max": 120.0, "srednia": 100.0, "mediana": 100.0, "suma": 200.0}
    assert [(r["wartosc"], r["liczba"]) for r in z["chroniony"]["rozklad"]] == [("tak", 1), ("nie", 0)]
    assert z["gatunek"]["wypelnione"] == 1 and "rozklad" not in z["gatunek"]


def test_mapa_svg_raportu():
    pole = {"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "zły"]}
    punkty = [
        {"nr": 1, "lat": 52.4, "lng": 16.9, "wartosci": {"stan": "dobry"}},
        {"nr": 2, "lat": 52.4009, "lng": 16.9, "wartosci": {}},  # ok. 100 m na północ, bez wartości
        {"nr": 3, "lat": None, "lng": None, "wartosci": {"stan": "zły"}},
    ]
    svg = raport_terenu.mapa_svg(punkty, pole)
    assert svg.count("<circle") == 2 and ">1</text>" in svg and ">2</text>" in svg and ">3</text>" not in svg
    assert raport_terenu.PALETA[0] in svg and raport_terenu.KOLOR_BRAK in svg and " m</text>" in svg
    assert "brak punktów z położeniem" in raport_terenu.mapa_svg([punkty[2]], None)


def test_strona_raportu(client):
    client.post("/teren/projekty", data={"nazwa": "Zieleń <test>", "wzor": "zielen"})
    klucz = re.search(r'"klucz": "([^"]+)"', client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)).group(1)
    client.post("/teren/projekty/1/import", content_type="multipart/form-data",
                data={"plik": (io.BytesIO(json.dumps(plik(klucz, punkt(), punkt("drugi000000", zdjecie=None, wartosci={"stan": "zły"}))).encode()), "t.json")})
    html = client.get("/teren/projekty/1/raport").get_data(as_text=True)
    assert "Zieleń &lt;test&gt;" in html and "<svg" in html and "Dokumentacja fotograficzna" in html
    assert "wg: obiekt" in html and 'value="obiekt" selected' in html  # domyślny kolor wg pierwszego pola wyboru
    assert html.count('alt="Zdjęcie punktu') == 1
    html = client.get("/teren/projekty/1/raport?pole=").get_data(as_text=True)
    assert '<option value="" selected>jednolity' in html
    assert client.get("/teren/projekty/9/raport").status_code == 404



# ---------- ETAP 70: kolory skali dobry–zły ----------


def test_kolory_skali():
    pole = sprawdz_pola([{"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "średni", "zły", "do usunięcia"], "skala": True}])[0]
    assert pole["skala"] is True
    assert raport_terenu.kolory_pola(pole) == {
        "dobry": "hsl(130, 70%, 42%)", "średni": "hsl(87, 70%, 42%)", "zły": "hsl(43, 70%, 42%)", "do usunięcia": "hsl(0, 70%, 42%)"}
    # skala tylko dla listy wyboru; bez skali — zwykła paleta
    assert sprawdz_pola([{"nazwa": "x", "typ": "tekst", "skala": True}])[0]["skala"] is False
    assert raport_terenu.kolory_pola({**pole, "skala": False})["dobry"] == raport_terenu.PALETA[0]
    assert WZORY["zielen"]["pola"][3]["skala"] is True and WZORY["budynki"]["pola"][2]["skala"] is True
    svg = raport_terenu.mapa_svg([{"nr": 1, "lat": 52.4, "lng": 16.9, "wartosci": {"stan": "zły"}}], pole)
    assert 'fill="hsl(43, 70%, 42%)"' in svg


# ---------- ETAP 72: poprawianie punktów ----------


def test_poprawka_punktu(client):
    client.post("/teren/projekty", data={"nazwa": "Zieleń", "wzor": "zielen"})
    klucz = re.search(r'"klucz": "([^"]+)"', client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)).group(1)
    tresc = json.dumps(plik(klucz, punkt())).encode()
    client.post("/teren/projekty/1/import", content_type="multipart/form-data", data={"plik": (io.BytesIO(tresc), "t.json")})
    pid = client.get("/teren/projekty/1/punkty").get_json()[0]["id"]
    url = f"/teren/projekty/1/punkty/{pid}"

    # same wartości — położenie i dokładność GPS bez zmian
    p = client.put(url, json={"wartosci": {"obiekt": "krzew", "stan": "zły"}, "uwagi": " poprawione "}).get_json()
    assert p["wartosci"] == {"obiekt": "krzew", "stan": "zły"} and p["uwagi"] == "poprawione"
    assert p["dokladnosc_m"] == 6.2 and p["polozenie_reczne"] is False and p["data_poprawki"]

    p = client.put(url, json={"wartosci": {}, "uwagi": "", "lat": 52.401, "lng": 16.902}).get_json()
    assert (p["lat"], p["lng"], p["dokladnosc_m"], p["polozenie_reczne"]) == (52.401, 16.902, None, True)
    assert "poprawione ręcznie" in client.get("/teren/projekty/1/raport").get_data(as_text=True)
    assert json.loads(client.get("/teren/projekty/1.geojson").data)["features"][0]["properties"]["polozenie_reczne"] is True

    for zle in ({"wartosci": {"stan": "fatalny"}}, {"lat": 95, "lng": 16}, {"lat": "x", "lng": 1}, "tekst"):
        assert client.put(url, json=zle).status_code == 400
    assert client.put("/teren/projekty/1/punkty/999", json={"wartosci": {}}).status_code == 404

    # ponowny import pliku z telefonu nie nadpisuje poprawek
    client.post("/teren/projekty/1/import", content_type="multipart/form-data", data={"plik": (io.BytesIO(tresc), "t.json")})
    assert client.get("/teren/projekty/1/punkty").get_json()[0]["lat"] == 52.401


def test_stara_baza_dostaje_nowe_kolumny(tmp_path):
    import sqlite3

    (tmp_path / "teren").mkdir()
    db = sqlite3.connect(tmp_path / "teren" / "teren.db")
    db.executescript("""
        CREATE TABLE projekty (id INTEGER PRIMARY KEY AUTOINCREMENT, nazwa TEXT NOT NULL, klucz TEXT NOT NULL UNIQUE, pola TEXT NOT NULL, data_utworzenia TEXT NOT NULL);
        CREATE TABLE punkty (id INTEGER PRIMARY KEY AUTOINCREMENT, projekt_id INTEGER NOT NULL, uid TEXT NOT NULL, lat REAL, lng REAL,
            dokladnosc_m REAL, czas TEXT NOT NULL, wartosci TEXT NOT NULL, uwagi TEXT NOT NULL DEFAULT '', zdjecie TEXT, data_importu TEXT NOT NULL);
        INSERT INTO projekty VALUES (1, 'Stary', 'k', '[]', '2026-09-01');
        INSERT INTO punkty (projekt_id, uid, lat, lng, czas, wartosci, data_importu) VALUES (1, 'abcdefgh', 52, 17, '2026-09-01', '{}', '2026-09-01');
    """)
    db.commit()
    db.close()
    app = create_app(instance_path=str(tmp_path))
    with app.test_client() as c:
        punkty = c.get("/teren/projekty/1/punkty").get_json()
    assert punkty[0]["polozenie_reczne"] is False and punkty[0]["data_poprawki"] is None


# ---------- ETAP 83: obszar prac i mapa offline w formularzu ----------


def test_obszar_prac_i_podklad(client, monkeypatch):
    from dane import ortofoto
    from teren import podklad

    client.post("/teren/projekty", data={"nazwa": "Park", "wzor": "zielen"})
    url = "/teren/projekty/1/obszar"
    assert client.put(url, json={"obszar": [52.40, 16.90, 52.41, 16.92]}).get_json()["obszar"] == [52.4, 16.9, 52.41, 16.92]
    for zle in ([52.41, 16.90, 52.40, 16.92], [52.0, 16.0, 52.2, 16.3], [52.4, 16.9, 52.4001, 16.9001], "x", [1, 2, 3]):
        assert client.put(url, json={"obszar": zle}).status_code == 400

    zapytania = []
    monkeypatch.setattr(ortofoto, "obraz_ortofotomapy", lambda bbox, s, w: zapytania.append((bbox, s, w)) or JPEG)
    html = client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)
    assert "data:image/jpeg;base64," in html and '"bbox_3857"' in html
    (x1, y1, x2, y2), szer, wys = zapytania[0]
    assert max(szer, wys) == podklad.MAKS_PX and szer / wys == pytest.approx((x2 - x1) / (y2 - y1), rel=0.01)

    def awaria(bbox, s, w):
        raise ortofoto.BladOrtofoto("brak połączenia")

    monkeypatch.setattr(ortofoto, "obraz_ortofotomapy", awaria)
    html = client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)
    assert "brak po" in html and "data:image/jpeg" not in html  # formularz działa bez podkładu (komunikat w JSON)

    assert client.put(url, json={"obszar": None}).get_json() == {"obszar": None}
    assert "const MAPA = null" in client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)


def test_obraz_ortofotomapy_odrzuca_nie_jpeg(monkeypatch):
    from dane import ortofoto

    class Odp:
        content = b"<ServiceException>zly</ServiceException>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(ortofoto.requests, "get", lambda *a, **k: Odp())
    with pytest.raises(ortofoto.BladOrtofoto, match="JPEG"):
        ortofoto.obraz_ortofotomapy((0, 0, 1, 1), 10, 10)


# ---------- ETAP 86: kalendarz na stronie głównej ----------


def test_kalendarz_egzaminy_i_teren(client):
    from datetime import date, timedelta

    dzien = lambda n: (date.today() + timedelta(days=n)).isoformat()  # noqa: E731
    assert "Najbliższe terminy" not in client.get("/").get_data(as_text=True)

    client.post("/teren/projekty", data={"nazwa": "Zieleń — Park Wilsona", "wzor": "zielen"})
    client.post("/teren/projekty", data={"nazwa": "Stary termin", "wzor": "zielen"})
    assert client.post("/teren/projekty/1/termin", data={"termin": dzien(1)}).status_code == 302
    client.post("/teren/projekty/2/termin", data={"termin": dzien(-3)})  # minął — nie w kalendarzu
    assert client.post("/teren/projekty/1/termin", data={"termin": "jutro"}).status_code == 400
    assert client.post("/teren/projekty/99/termin", data={"termin": dzien(1)}).status_code == 404
    assert f'value="{dzien(1)}"' in client.get("/teren/projekty/1").get_data(as_text=True)
    client.post("/fiszki/egzaminy", data={"nazwa": "Kolokwium z planowania", "data": dzien(10)})

    html = client.get("/").get_data(as_text=True)
    kalendarz = html[html.index("Najbliższe terminy"):html.index('class="siatka-kart"')]
    assert "jutro" in kalendarz and "za 10 dni" in kalendarz and "Stary termin" not in kalendarz
    assert kalendarz.index("Park Wilsona") < kalendarz.index("Kolokwium z planowania")  # od najbliższego
    assert "wszystkie fiszki: brak fiszek w zakresie" in kalendarz and "bez obszaru prac" in kalendarz

    client.post("/teren/projekty/1/termin", data={"termin": dzien(1), "usun": "1"})
    html = client.get("/").get_data(as_text=True)
    assert "Park Wilsona" not in html[html.index("Najbliższe terminy"):html.index('class="siatka-kart"')]  # „Wróć do pracy” go pokazuje — to nie termin


# ---------- ETAP 93: tryb ankiety i wielokrotny wybór ----------


def test_wielokrotny_wybor_w_polach_i_pliku():
    pola = sprawdz_pola(WZORY["ankieta"]["pola"])
    assert pola[1]["typ"] == "wiele" and "odpoczynek" in pola[1]["opcje"] and not pola[1]["skala"]
    with pytest.raises(BladDanych, match="powtarzają"):
        sprawdz_pola([{"nazwa": "x", "typ": "wiele", "opcje": ["a", "A"]}])
    p = punkt(wartosci={"po co tu przychodzisz": ["sport", "odpoczynek", "sport"], "czego tu brakuje": []})
    wynik = odczytaj_plik(plik("k", p), "k", pola)[0]["wartosci"]
    assert wynik == {"po co tu przychodzisz": ["odpoczynek", "sport"]}  # kolejność opcji, bez powtórzeń, pusta lista pominięta
    for zle in ({"po co tu przychodzisz": "sport"}, {"po co tu przychodzisz": ["latanie"]}):
        with pytest.raises(BladDanych):
            odczytaj_plik(plik("k", punkt(wartosci=zle)), "k", pola)


def test_zestawienie_wielokrotnego_wyboru():
    from teren.raport import zestawienie

    pola = sprawdz_pola([{"nazwa": "brakuje", "typ": "wiele", "opcje": ["ławek", "zieleni", "cienia"]}])
    punkty = [{"wartosci": {"brakuje": ["ławek", "zieleni"]}}, {"wartosci": {"brakuje": ["zieleni"]}}, {"wartosci": {}}, {"wartosci": {}}]
    z = zestawienie(pola, punkty)[0]
    assert z["wiele"] and z["wypelnione"] == 2
    assert [(r["wartosc"], r["liczba"], r["procent"]) for r in z["rozklad"]] == [("ławek", 1, 25), ("zieleni", 2, 50), ("cienia", 0, 0)]


def test_ankieta_obieg(client):
    client.post("/teren/projekty", data={"nazwa": "Ankieta — Rynek Jeżycki", "wzor": "ankieta"})
    html = client.get("/teren/projekty/1").get_data(as_text=True)
    assert 'value="ankieta" selected' in html
    telefon = client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)
    assert "Nowa odpowiedź" in telefon and "Miejsce ankiety i zdjęcie (opcjonalnie)" in telefon and '"ankieta": true' in telefon
    klucz = re.search(r'"klucz": "([^"]+)"', telefon).group(1)
    odpowiedzi = [
        punkt("odp1000000a", lat=None, lng=None, zdjecie=None, wartosci={"po co tu przychodzisz": ["zakupy", "spotkania"], "wiek": "19–35"}),
        punkt("odp2000000a", lat=None, lng=None, zdjecie=None, wartosci={"po co tu przychodzisz": ["zakupy"]}),
    ]
    r = client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(json.dumps(plik(klucz, *odpowiedzi)).encode()), "a.json")},
                    content_type="multipart/form-data")
    assert r.get_json() == {"dodane": 2, "pominiete": 0}
    raport = client.get("/teren/projekty/1/raport").get_data(as_text=True)
    assert "Ankieta · odpowiedzi: 2" in raport and "Wyniki ankiety" in raport and "nie sumują się do 100" in raport
    assert "zakupy; spotkania" in raport and 'class="raport-terenu__mapa"' not in raport  # bez położeń — bez mapy
    assert "zakupy; spotkania" in client.get("/teren/projekty/1.csv").get_data(as_text=True)
    assert client.post("/teren/projekty/1/rodzaj", data={"rodzaj": "inwentaryzacja"}).status_code == 302
    assert "Nowy punkt" in client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)
    assert client.post("/teren/projekty/1/rodzaj", data={"rodzaj": "x"}).status_code == 400


# ---------- ETAP 99: paski wykresu w zestawieniu ----------


def test_zestawienie_ma_kolory_paskow():
    from teren.raport import KOLOR_PASKA, kolor_skali, zestawienie

    pola = sprawdz_pola([{"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "średni", "zły"], "skala": True},
                         {"nazwa": "obiekt", "typ": "wybor", "opcje": ["drzewo", "krzew"]}])
    z = zestawienie(pola, [{"wartosci": {"stan": "zły", "obiekt": "drzewo"}}])
    assert [r["kolor"] for r in z[0]["rozklad"]] == [kolor_skali(i, 3) for i in range(3)]
    assert {r["kolor"] for r in z[1]["rozklad"]} == {KOLOR_PASKA}


# ---------- ETAP 132: rozmieszczenie w heksagonach ----------


def test_heksagony_terenu():
    from teren import raport

    pole = {"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "zły"]}
    # 12 punktów w dwóch skupiskach ok. 400 m od siebie; w pierwszym przeważa „dobry”
    punkty = [{"nr": i + 1, "lat": 52.4 + (0 if i < 8 else 0.004) + i * 1e-6, "lng": 16.9, "wartosci": {"stan": "dobry" if i < 6 else "zły"}}
              for i in range(12)] + [{"nr": 13, "lat": None, "lng": None, "wartosci": {}}]
    w = raport.heksagony(punkty, pole)
    assert w["punktow"] == 12 and len(w["komorki"]) == 2 and w["rozdzielczosc"] == 11  # najdrobniejsza siatka, średnio ≥ 2 w komórce
    k1, k2 = w["komorki"]
    assert (k1["nr"], k1["liczba"], k1["numery"], k1["dominujaca"], k1["udzial"]) == (1, 8, list(range(1, 9)), "dobry", 75)
    assert (k2["liczba"], k2["dominujaca"], k2["udzial"]) == (4, "zły", 100)
    assert raport.heksagony(punkty[:9], pole) is None  # za mało punktów z położeniem
    rozproszone = [{"nr": i, "lat": 52.4 + i * 0.003, "lng": 16.9, "wartosci": {}} for i in range(12)]
    assert raport.heksagony(rozproszone, None)["rozdzielczosc"] == 9  # punkty daleko od siebie → większe heksagony
    svg = raport.heksagony_svg(w)
    assert svg.count("<polygon") == 2 and ">8<" in svg and ">nr 2<" in svg
    assert raport.kolor_gestosci(8, 8) == raport.KOLORY_GESTOSCI[-1] and raport.kolor_gestosci(1, 8) == raport.KOLORY_GESTOSCI[0]


# ---------- ETAP 133: import z GeoJSON ----------


def _geojson(*cechy):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": wsp}, "properties": atr} for wsp, atr in cechy]}


def test_odczytaj_geojson():
    from teren.projekt import BladDanych, odczytaj_geojson

    pola = [{"nazwa": "Stan", "typ": "wybor", "opcje": ["dobry", "zły"]}, {"nazwa": "liczba miejsc", "typ": "liczba", "opcje": []},
            {"nazwa": "oświetlenie", "typ": "tak_nie", "opcje": []}, {"nazwa": "wyposażenie", "typ": "wiele", "opcje": ["kosz", "stojak"]}]
    dane = _geojson(([16.93, 52.40], {"stan": "dobry", "Liczba miejsc": "4,5", "OŚWIETLENIE": "tak", "wyposażenie": "kosz; stojak",
                                      "opis": "przy fontannie", "id_qgis": 17, "czas": "2026-09-30T10:00:00"}),
                    ([16.94, 52.41], {"Stan": "zły", "oświetlenie": 0}))
    punkty, niedopasowane = odczytaj_geojson(dane, pola)
    p1, p2 = punkty
    assert (p1["lat"], p1["lng"]) == (52.40, 16.93) and p1["czas"] == "2026-09-30T10:00:00"
    assert p1["wartosci"] == {"Stan": "dobry", "liczba miejsc": 4.5, "oświetlenie": True, "wyposażenie": ["kosz", "stojak"]}
    assert p1["uwagi"] == "przy fontannie; id_qgis: 17" and niedopasowane == ["id_qgis"]
    assert p2["wartosci"] == {"Stan": "zły", "oświetlenie": False}
    assert odczytaj_geojson(dane, pola)[0][0]["uid"] == p1["uid"] and p1["uid"] != p2["uid"]  # stały identyfikator
    with pytest.raises(BladDanych, match="EPSG:4326"):
        odczytaj_geojson(_geojson(([357000.0, 506000.0], {})), pola)  # metry PL-1992
    with pytest.raises(BladDanych, match="nie ma na liście opcji"):
        odczytaj_geojson(_geojson(([16.9, 52.4], {"stan": "średni"})), pola)
    with pytest.raises(BladDanych, match="tylko punkty"):
        odczytaj_geojson({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": []}, "properties": {}}]}, pola)


def test_import_geojson_przez_trase(client):
    import io
    import json

    client.post("/teren/projekty", data={"nazwa": "Ławki", "wzor": "lawki"})
    dane = json.dumps(_geojson(([16.93, 52.40], {"nazwa_z_qgis": "A"}), ([16.94, 52.41], {}))).encode()
    wynik = client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(dane), "punkty.geojson")}, content_type="multipart/form-data").get_json()
    assert (wynik["dodane"], wynik["pominiete"], wynik["niedopasowane"]) == (2, 0, ["nazwa_z_qgis"])
    ponownie = client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(dane), "punkty.geojson")}, content_type="multipart/form-data").get_json()
    assert (ponownie["dodane"], ponownie["pominiete"]) == (0, 2)


# ---------- ETAP 134: projekt jako wzór ----------


def test_podobny_projekt(client):
    client.post("/teren/projekty", data={"nazwa": "Ławki — Rynek", "wzor": "lawki"})
    client.post("/teren/projekty/1/rodzaj", data={"rodzaj": "ankieta"})
    with client.application.app_context():
        from teren import baza
        baza.ustaw_obszar(1, [52.40, 16.92, 52.41, 16.94])
        baza.zapisz_punkty(1, [{"uid": "abcdefgh1", "lat": 52.405, "lng": 16.93, "dokladnosc_m": 3, "czas": "2026-09-30T10:00:00",
                                "wartosci": {}, "uwagi": "", "zdjecie": None}])
    odp = client.post("/teren/projekty/1/podobny")
    assert odp.status_code == 302 and odp.headers["Location"].endswith("/teren/projekty/2")
    with client.application.app_context():
        from teren import baza
        stary, nowy = baza.projekt(1), baza.projekt(2)
        assert nowy["nazwa"] == "Ławki — Rynek (kopia)" and nowy["pola"] == stary["pola"] and nowy["rodzaj"] == "ankieta"
        assert nowy["obszar"] == stary["obszar"] and nowy["klucz"] != stary["klucz"]  # osobny klucz pliku z telefonu
        assert baza.punkty(2) == [] and len(baza.punkty(1)) == 1
    assert client.post("/teren/projekty/99/podobny").status_code == 404
    assert "Utwórz podobny" in client.get("/teren/projekty/1").get_data(as_text=True)


# ---------- ETAP 157: porównanie dwóch inwentaryzacji ----------


def test_porownanie_inwentaryzacji(client):
    client.post("/teren/projekty", data={"nazwa": "Zieleń 2025", "wzor": "zielen"})
    client.post("/teren/projekty/1/podobny")  # „Zieleń 2025 (kopia)” — te same pola
    client.post("/teren/projekty", data={"nazwa": "Inny formularz", "wzor": "budynki"})

    def pkt(uid, lat, lng, stan, obwod, czas):
        return {"uid": uid, "lat": lat, "lng": lng, "dokladnosc_m": 4, "czas": czas, "wartosci": {"obiekt": "drzewo", "stan": stan, "obwód pnia [cm]": obwod},
                "uwagi": "", "zdjecie": None}
    with client.application.app_context():
        from teren import baza
        baza.zapisz_punkty(1, [pkt("a000001", 52.40000, 16.90000, "dobry", 100, "2025-05-01T10:00"),
                               pkt("a000002", 52.40100, 16.90000, "średni", 80, "2025-05-01T10:05"),
                               pkt("a000003", 52.40200, 16.90000, "dobry", 60, "2025-05-01T10:10")])
        # rok później: drzewo 1 lepiej… nie, gorzej (dobry → zły), 2 bez zmian, 3 przesunięte o ~40 m (nie para), nowe 4
        baza.zapisz_punkty(2, [pkt("b000001", 52.40005, 16.90003, "zły", 104, "2026-05-01T10:00"),
                               pkt("b000002", 52.40102, 16.89998, "średni", 82, "2026-05-01T10:05"),
                               pkt("b000003", 52.40236, 16.90000, "dobry", 61, "2026-05-01T10:10"),
                               pkt("b000004", 52.40500, 16.90000, "dobry", 20, "2026-05-01T10:15")])
    html = client.get("/teren/porownanie?a=1&b=2").get_data(as_text=True)
    assert "Porównanie inwentaryzacji" in html and "(3 punktów)" in html and "(4 punktów)" in html
    assert "<strong>2</strong> par" in html  # punkt 3 przesunięty o ~40 m — nie para
    assert "lepiej: <strong>0</strong> · gorzej: <strong>1</strong> · bez zmian: 1" in html
    assert "dobry</td><td>zły" in html and "-8,3 p.p." in html  # stan „średni”: 1/3 → 1/4
    assert "stopka-wydruku" in html
    inny = client.get("/teren/porownanie?a=1&b=3").get_data(as_text=True)
    assert "nie mają wspólnych pól" in inny
    assert client.get("/teren/porownanie?a=1&b=1").status_code == 400
    assert client.get("/teren/porownanie?a=1&b=99").status_code == 404
    assert "Porównaj" in client.get("/teren/projekty/1").get_data(as_text=True)


def test_pary_punktow():
    from teren import porownanie
    a = [{"lat": 52.0, "lng": 17.0, "nr": 1}, {"lat": 52.0001, "lng": 17.0, "nr": 2}]
    b = [{"lat": 52.00002, "lng": 17.0, "nr": 1}]  # bliżej punktu 1 niż 2 — jedna para, punkt 2 bez pary
    assert [(x["nr"], y["nr"]) for x, y, _ in porownanie.pary(a, b)] == [(1, 1)]
    assert porownanie.odleglosc_m({"lat": 52.0, "lng": 17.0}, {"lat": 52.001, "lng": 17.0}) == pytest.approx(111.2, abs=0.2)
    assert porownanie.pary(a, [{"lat": None, "lng": None, "nr": 1}]) == []


def test_pary_z_siatki_jak_kazdy_z_kazdym():
    """ETAP 160: indeks w siatce daje te same pary co porównanie wszystkich punktów."""
    import random
    from teren import porownanie
    los = random.Random(5)
    a = [{"lat": 52.4 + los.uniform(0, 0.002), "lng": 16.9 + los.uniform(0, 0.003), "nr": i} for i in range(150)]
    b = [{"lat": p["lat"] + los.gauss(0, 0.00008), "lng": p["lng"] + los.gauss(0, 0.0001), "nr": i} for i, p in enumerate(a)]

    def kazdy_z_kazdym():
        wynik = set()
        for pb in b:
            pa = min(a, key=lambda q: porownanie.odleglosc_m(q, pb))
            if porownanie.odleglosc_m(pa, pb) <= porownanie.PROG_M and min(b, key=lambda q: porownanie.odleglosc_m(pa, q)) is pb:
                wynik.add((pa["nr"], pb["nr"]))
        return wynik
    z_siatki = {(x["nr"], y["nr"]) for x, y, _ in porownanie.pary(a, b)}
    assert z_siatki == kazdy_z_kazdym() and len(z_siatki) > 50


# ---------- ETAP 166: pola wymagane i zakresy liczb ----------


def test_reguly_pol():
    from teren.projekt import braki

    pola = sprawdz_pola([{"nazwa": "obwód", "typ": "liczba", "min": "10", "max": 900, "wymagane": True},
                         {"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "zły"], "wymagane": True, "min": 5},
                         {"nazwa": "uwaga", "typ": "tekst", "wymagane": "tak"}])
    assert pola[0] == {"nazwa": "obwód", "typ": "liczba", "opcje": [], "skala": False, "wymagane": True, "min": 10.0, "max": 900.0}
    assert "min" not in pola[1] and pola[1]["wymagane"] is True  # zakres tylko dla liczby
    assert "wymagane" not in pola[2]  # tylko wartość true
    for zle in ({"min": 5, "max": 1}, {"min": "dużo"}, {"max": float("inf")}):
        with pytest.raises(BladDanych):
            sprawdz_pola([{"nazwa": "x", "typ": "liczba", **zle}])
    assert braki({"obwód": 120, "stan": "dobry"}, pola) == []
    assert braki({"obwód": 5}, pola) == ["obwód poza zakresem 10–900", "brak: stan"]
    bez_minimum = {k: v for k, v in pola[0].items() if k != "min"}
    assert braki({"stan": "zły", "obwód": 1000}, [bez_minimum, pola[1]]) == ["obwód poza zakresem …–900"]


def test_braki_w_liscie_punktow(client):
    client.post("/teren/projekty", data={"nazwa": "Drzewa"})
    pola = [{"nazwa": "obwód", "typ": "liczba", "opcje": [], "min": 10, "max": 900}, {"nazwa": "gatunek", "typ": "tekst", "opcje": [], "wymagane": True}]
    assert client.put("/teren/projekty/1", json={"nazwa": "Drzewa", "pola": pola}).status_code == 200
    dane = json.dumps(_geojson(([16.93, 52.40], {"obwód": 1200, "gatunek": "lipa"}), ([16.94, 52.41], {"obwód": 80}))).encode()
    wynik = client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(dane), "punkty.geojson")}, content_type="multipart/form-data").get_json()
    assert wynik["dodane"] == 2  # import nie odrzuca punktów z brakami
    punkty = sorted(client.get("/teren/projekty/1/punkty").get_json(), key=lambda p: p["lng"])
    assert [p["braki"] for p in punkty] == [["obwód poza zakresem 10–900"], ["brak: gatunek"]]
    formularz = client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)
    assert '"wymagane": true' in formularz and '"max": 900.0' in formularz and "problemPol" in formularz


# ---------- ETAP 176: punkty w okolicy (dla karty działki MPZP) ----------


def test_punkty_w_okolicy(client):
    client.post("/teren/projekty", data={"nazwa": "Zieleń", "wzor": "zielen"})
    client.post("/teren/projekty", data={"nazwa": "Ławki"})
    with client.application.app_context():
        from teren import baza
        baza.zapisz_punkty(1, [
            {"uid": "a0000001", "lat": 52.40000, "lng": 16.90000, "dokladnosc_m": 4, "czas": "2025-05-01T10:00", "wartosci": {"obiekt": "drzewo"}, "uwagi": "dąb", "zdjecie": None},
            {"uid": "a0000002", "lat": 52.40050, "lng": 16.90000, "dokladnosc_m": 4, "czas": "2025-05-01T10:01", "wartosci": {}, "uwagi": "", "zdjecie": None},   # ok. 56 m na północ
            {"uid": "a0000003", "lat": 52.41000, "lng": 16.90000, "dokladnosc_m": 4, "czas": "2025-05-01T10:02", "wartosci": {}, "uwagi": "", "zdjecie": None},   # ponad 1 km
            {"uid": "a0000004", "lat": None, "lng": None, "dokladnosc_m": None, "czas": "2025-05-01T10:03", "wartosci": {}, "uwagi": "", "zdjecie": None}])
        baza.zapisz_punkty(2, [{"uid": "b0000001", "lat": 52.40020, "lng": 16.90010, "dokladnosc_m": 4, "czas": "2025-06-01T10:00", "wartosci": {"uwaga": "ławka"}, "uwagi": "", "zdjecie": None}])
    dzialka = {"type": "Polygon", "coordinates": [[[16.8999, 52.3999], [16.9001, 52.3999], [16.9001, 52.4001], [16.8999, 52.4001], [16.8999, 52.3999]]]}
    w = client.post("/teren/okolica", json={"geometria": dzialka, "promien": 100}).get_json()
    assert [p["projekt"] for p in w["punkty"]] == ["Zieleń", "Ławki", "Zieleń"] and w["projektow"] == 2
    assert w["punkty"][0]["odleglosc_m"] == 0 and w["punkty"][0]["uwagi"] == "dąb"  # w granicach działki
    assert 40 < w["punkty"][2]["odleglosc_m"] < 50  # 56 m od środka, ok. 45 m od krawędzi
    assert len(client.post("/teren/okolica", json={"geometria": {"type": "Point", "coordinates": [16.9, 52.4]}, "promien": 50}).get_json()["punkty"]) == 2  # 56 m — za daleko od punktu
    assert client.post("/teren/okolica", json={"geometria": dzialka, "promien": 1000}).status_code == 400
    assert client.post("/teren/okolica", json={"geometria": {"type": "Point", "coordinates": [500000, 5800000]}}).status_code == 400
    assert client.post("/teren/okolica", json={"geometria": {"type": "LineString", "coordinates": [[16, 52], [17, 52]]}}).status_code == 400


# ---------- ETAP 179: tabela krzyżowa ----------


def test_tabela_krzyzowa():
    from teren import raport as r

    a = {"nazwa": "wiek", "typ": "wybor", "opcje": ["młodzi", "starsi", "dzieci"]}
    b = {"nazwa": "bezpiecznie", "typ": "tak_nie", "opcje": []}
    odpowiedzi = [("młodzi", True)] * 30 + [("młodzi", False)] * 10 + [("starsi", True)] * 10 + [("starsi", False)] * 30 + [("starsi", None)] * 3
    punkty = [{"wartosci": {"wiek": w, **({} if t is None else {"bezpiecznie": t})}} for w, t in odpowiedzi]
    t = r.tabela_krzyzowa(a, b, punkty)
    assert t["n"] == 80 and t["liczby"] == [[30, 10], [10, 30], [0, 0]] and t["w_razem"] == [40, 40, 0]
    assert t["procent_w_wierszu"][0] == [75.0, 25.0] and t["procent_w_wierszu"][2] == [None, None]
    assert t["chi2"] == pytest.approx(20.0) and t["df"] == 1  # pusty wiersz „dzieci” pominięty w teście
    assert t["p"] == pytest.approx(7.744e-06, rel=1e-3) and t["v_cramera"] == pytest.approx(0.5) and t["male_oczekiwane"] == 0
    assert r.tabela_krzyzowa(a, b, punkty[:30])["chi2"] is None  # jedna kolumna
    assert r._p_chi2(3.841, 1) == pytest.approx(0.05, abs=1e-4) and r._p_chi2(9.488, 4) == pytest.approx(0.05, abs=1e-4)
    assert r._p_chi2(30, 4) == pytest.approx(4.8944e-06, rel=1e-3) and r._p_chi2(0.5, 3) == pytest.approx(0.91889, abs=1e-4)


def test_tabela_krzyzowa_w_raporcie(client):
    client.post("/teren/projekty", data={"nazwa": "Ankieta", "wzor": "ankieta"})
    with client.application.app_context():
        from teren import baza
        baza.zapisz_punkty(1, [{"uid": f"a{i:07d}", "lat": None, "lng": None, "dokladnosc_m": None, "czas": "2025-05-01T10:00",
                                "wartosci": {"wiek": ["19–35", "61 i więcej"][i % 2], "czy czujesz się tu bezpiecznie": ["tak", "nie"][i % 2 if i < 10 else 0]},
                                "uwagi": "", "zdjecie": None} for i in range(16)])
    strona = client.get("/teren/projekty/1/raport").get_data(as_text=True)
    assert 'id="tabela-krzyzowa"' in strona and "Test chi-kwadrat" not in strona  # bez wyboru — tylko formularz
    wynik = client.get("/teren/projekty/1/raport?krzyz_a=wiek&krzyz_b=czy+czujesz+się+tu+bezpiecznie").get_data(as_text=True)
    assert "Test chi-kwadrat" in wynik and "V Craméra" in wynik and "liczność oczekiwana" in wynik
    assert "Test chi-kwadrat" not in client.get("/teren/projekty/1/raport?krzyz_a=wiek&krzyz_b=wiek").get_data(as_text=True)


def test_wykres_tabeli_krzyzowej():
    from teren import raport as r

    a = {"nazwa": "wiek", "typ": "wybor", "opcje": ["młodzi", "starsi", "dzieci"]}
    b = {"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "zły"], "skala": True}
    punkty = [{"wartosci": {"wiek": w, "stan": s}} for w, s in [("młodzi", "dobry")] * 3 + [("młodzi", "zły")] + [("starsi", "zły")] * 2]
    t = r.tabela_krzyzowa(a, b, punkty)
    kolory = r.kolory_kolumn(b)
    assert kolory == [r.kolor_skali(0, 2), r.kolor_skali(1, 2)]
    svg = r.wykres_krzyzowy_svg(t, kolory)
    assert svg.count("<rect") == 1 + 3  # tło + młodzi (2 części) + starsi (1); „dzieci” bez odpowiedzi pominięte
    assert ">75%<" in svg and ">100%<" in svg and ">2</text>" in svg
    assert r.kolory_kolumn({"nazwa": "x", "typ": "tak_nie", "opcje": []}) == r.PALETA[:2]


# ---------- ETAP 198: trasa obchodu ----------

from teren import trasa as trasa_terenu  # noqa: E402


def test_trasa_najblizszy_i_dwa_opt():
    # punkty na prostej co ok. 111 m (0,001° szerokości), podane w pomieszanej kolejności
    punkty = [{"id": i, "lat": 52.0 + 0.001 * k, "lng": 16.9} for i, k in [(1, 3), (2, 0), (3, 4), (4, 1), (5, 2)]]
    t = trasa_terenu.trasa(punkty)
    assert t["kolejnosc"] in ([2, 4, 5, 1, 3], [3, 1, 5, 4, 2])  # od końca do końca
    assert t["dlugosc_m"] == pytest.approx(4 * 111.2, rel=0.01) and len(t["odcinki_m"]) == 4
    assert t["czas_min"] == round(t["dlugosc_m"] / 1000 / 4.5 * 60)
    # stały start w środku: musi zacząć od niego
    t = trasa_terenu.trasa(punkty, start_id=5)
    assert t["kolejnosc"][0] == 5 and sorted(t["kolejnosc"]) == [1, 2, 3, 4, 5]
    # 2-opt nie wydłuża trasy z „najbliższego sąsiada”
    import random
    los = random.Random(7)
    chmura = [{"id": i, "lat": 52 + los.random() * 0.01, "lng": 16.9 + los.random() * 0.015} for i in range(40)]
    t = trasa_terenu.trasa(chmura)
    assert t["dlugosc_m"] <= t["dlugosc_najblizszy_m"] and len(set(t["kolejnosc"])) == 40
    for zle, start in (([punkty[0]], None), (punkty, 99), ([{"id": i, "lat": 52, "lng": 16} for i in range(201)], None)):
        with pytest.raises(trasa_terenu.BladTrasy):
            trasa_terenu.trasa(zle, start)


def test_trasa_przez_trase_i_gpx(client):
    client.post("/teren/projekty", data={"nazwa": "Obchód <Jeżyce>", "wzor": "zielen"})
    klucz = re.search(r'"klucz": "([^"]+)"', client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)).group(1)
    pkt = [punkt(f"p{i:010d}", lat=52.4 + 0.001 * i, lng=16.9) for i in range(4)] + [punkt("bezgps0000", lat=None, lng=None)]
    client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(json.dumps(plik(klucz, *pkt)).encode()), "t.json")},
                content_type="multipart/form-data")
    ids = [p["id"] for p in client.get("/teren/projekty/1/punkty").get_json() if p["lat"] is not None]
    t = client.get("/teren/projekty/1/trasa").get_json()
    assert sorted(t["kolejnosc"]) == sorted(ids)  # punkt bez położenia pominięty
    t = client.get(f"/teren/projekty/1/trasa?punkty={ids[1]},{ids[3]},{ids[2]}&start={ids[3]}").get_json()
    assert t["kolejnosc"] == [ids[3], ids[2], ids[1]]
    assert client.get("/teren/projekty/1/trasa?punkty=x").status_code == 400
    assert client.get(f"/teren/projekty/1/trasa?punkty={ids[0]}").status_code == 400
    r = client.get(f"/teren/projekty/1/trasa.gpx?start={ids[0]}")
    tekst = r.get_data(as_text=True)
    assert r.mimetype == "application/gpx+xml" and "trasa_obchod_jezyce.gpx" in r.headers["Content-Disposition"]
    assert tekst.count("<wpt ") == 4 and tekst.count("<rtept ") == 4 and "&lt;Jeżyce&gt;" in tekst
    import xml.etree.ElementTree as ET
    ET.fromstring(tekst.encode())
    assert client.get("/teren/projekty/99/trasa").status_code == 404


# ---------- ETAP 199: punkty do sprawdzenia w formularzu ----------


def test_formularz_z_punktami_do_sprawdzenia(client):
    client.post("/teren/projekty", data={"nazwa": "Kontrola", "wzor": "zielen"})
    klucz = re.search(r'"klucz": "([^"]+)"', client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)).group(1)
    pkt = [punkt("p1000000000", lat=52.40, uwagi="Lipa <b>stara</b> " + "x" * 80), punkt("p2000000000", lat=52.41, wartosci={"obiekt": "krzew"}, uwagi=""),
           punkt("p3000000000", lat=None, lng=None)]
    client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(json.dumps(plik(klucz, *pkt)).encode()), "t.json")},
                content_type="multipart/form-data")
    ids = [p["id"] for p in client.get("/teren/projekty/1/punkty").get_json()]
    zwykly = client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)
    assert "const DO_SPRAWDZENIA = [];" in zwykly and "karta-do-sprawdzenia" not in zwykly
    html = client.get(f"/teren/projekty/1/formularz.html?do_sprawdzenia={ids[1]},{ids[0]},{ids[2]},{ids[1]},999").get_data(as_text=True)
    cele = json.loads(re.search(r"const DO_SPRAWDZENIA = (\[.*?\]);", html).group(1))
    assert [c["id"] for c in cele] == [ids[1], ids[0]] and [c["nr"] for c in cele] == [1, 2]  # kolejność trasy, bez duplikatów i punktów bez GPS
    assert cele[0]["opis"] == "krzew" and cele[1]["opis"].startswith("drzewo · 120 · dobry · Lipa <b>stara</b>") and cele[1]["opis"].endswith("…")
    assert "<b>stara" not in html  # tekst użytkownika w JSON jest zabezpieczony (<)
    assert 'id="karta-do-sprawdzenia"' in html
    assert client.get("/teren/projekty/1/formularz.html?do_sprawdzenia=a,b").status_code == 400


# ---------- ETAP 212: kosz projektów ----------


def test_kosz_projektow(client, tmp_path):
    from datetime import datetime, timedelta

    client.post("/teren/projekty", data={"nazwa": "Zieleń <Wilda>", "wzor": "zielen"})
    klucz = re.search(r'"klucz": "([^"]+)"', client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)).group(1)
    client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(json.dumps(plik(klucz, punkt())).encode()), "t.json")},
                content_type="multipart/form-data")
    folder = tmp_path / "teren" / "zdjecia"
    assert len(os.listdir(folder)) == 1
    client.delete("/teren/projekty/1")
    strona = client.get("/teren/").get_data(as_text=True)
    assert "Kosz (1)" in strona and "Zieleń &lt;Wilda&gt;" in strona and client.get("/teren/projekty/1").status_code == 404
    assert client.get("/teren/projekty.json").get_json() == [] and len(os.listdir(folder)) == 1  # zdjęcie czeka w koszu
    r = client.post("/teren/projekty/1/przywroc")
    assert r.status_code == 302 and r.headers["Location"].endswith("/teren/projekty/1")
    assert len(client.get("/teren/projekty/1/punkty").get_json()) == 1
    assert client.post("/teren/projekty/1/przywroc").status_code == 404
    client.delete("/teren/projekty/1")
    with client.application.app_context():
        from teren import baza
        baza.get_db().execute("UPDATE projekty SET usunieto = ?", ((datetime.now() - timedelta(days=31)).isoformat(),))
        baza.get_db().commit()
    assert "Kosz (" not in client.get("/teren/").get_data(as_text=True)
    assert os.listdir(folder) == []  # na dobre — ze zdjęciem


# ---------- ETAP 214: GeoPackage projektu ----------


def test_gpkg_projektu(client, tmp_path):
    import sqlite3
    import xml.etree.ElementTree as ET

    client.post("/teren/projekty", data={"nazwa": "Zieleń", "wzor": "zielen"})
    # pola o nazwach jak stałe kolumny i z cudzysłowem — w pliku mają się zmieścić
    client.put("/teren/projekty/1", json={"nazwa": "Zieleń", "pola": [
        {"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "zły"]}, {"nazwa": "obwód", "typ": "liczba"},
        {"nazwa": "ID", "typ": "tekst"}, {"nazwa": 'nazwa "lokalna"', "typ": "tekst"}]})
    klucz = re.search(r'"klucz": "([^"]+)"', client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)).group(1)
    pkt = [punkt("a0000000001", wartosci={"stan": "dobry", "obwód": 120, "ID": "x", 'nazwa "lokalna"': "Lipa"}),
           punkt("a0000000002", lat=None, lng=None, wartosci={"stan": "zły"})]
    client.post("/teren/projekty/1/import", data={"plik": (io.BytesIO(json.dumps(plik(klucz, *pkt)).encode()), "t.json")},
                content_type="multipart/form-data")
    r = client.get("/teren/projekty/1.gpkg")
    assert r.mimetype == "application/geopackage+sqlite3" and "teren_zielen.gpkg" in r.headers["Content-Disposition"]
    sciezka = tmp_path / "p.gpkg"
    sciezka.write_bytes(r.data)
    db = sqlite3.connect(sciezka)
    try:
        kolumny = [w[1] for w in db.execute("PRAGMA table_info(punkty)")]
        assert kolumny[:6] == ["fid", "geom", "id", "czas", "dokladnosc_m", "polozenie_reczne"]
        assert "ID_2" in kolumny and 'nazwa "lokalna"' in kolumny
        wiersze = db.execute('SELECT stan, "obwód", "nazwa ""lokalna""" FROM punkty').fetchall()
        assert wiersze == [("dobry", 120.0, "Lipa")]  # punkt bez położenia pominięty
        qml = db.execute("SELECT styleQML FROM layer_styles WHERE f_table_name = 'punkty'").fetchone()[0]
        ET.fromstring(qml.split(">", 1)[1])
        assert 'attr="stan"' in qml and 'value="dobry"' in qml
    finally:
        db.close()


# ---------- ETAP 219: opis i kierunek zdjęcia ----------

def test_opis_i_kierunek_zdjecia_w_pliku():
    wynik = odczytaj_plik(plik("K", punkt(zdjecie_opis="  elewacja  frontowa ", zdjecie_kierunek=45),
                               punkt("bezzdjecia1", zdjecie=None, zdjecie_opis="nie zapisze się", zdjecie_kierunek=90),
                               punkt("starszy0001")), "K", POLA)
    assert (wynik[0]["zdjecie_opis"], wynik[0]["zdjecie_kierunek"]) == ("elewacja frontowa", 45)
    assert (wynik[1]["zdjecie_opis"], wynik[1]["zdjecie_kierunek"]) == ("", None)  # bez zdjęcia — pomijamy
    assert (wynik[2]["zdjecie_opis"], wynik[2]["zdjecie_kierunek"]) == ("", None)  # plik ze starszego formularza
    for zly in (30, 360, "pn", True, 45.5):
        with pytest.raises(BladDanych, match="kierunek zdjęcia"):
            odczytaj_plik(plik("K", punkt(zdjecie_kierunek=zly)), "K", POLA)
    with pytest.raises(BladDanych, match="opis zdjęcia"):
        odczytaj_plik(plik("K", punkt(zdjecie_opis="x" * 201)), "K", POLA)


def test_opis_i_kierunek_zdjecia_w_warsztacie(client):
    client.post("/teren/projekty", data={"nazwa": "Zieleń", "wzor": "zielen"})
    html = client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)
    assert 'id="zdjecie-kierunek"' in html and '<option value="315">NW (315°)</option>' in html
    klucz = re.search(r'"klucz": "([^"]+)"', html).group(1)
    tresc = json.dumps(plik(klucz, punkt(zdjecie_opis="brama wjazdowa", zdjecie_kierunek=135))).encode()
    client.post("/teren/projekty/1/import", content_type="multipart/form-data", data={"plik": (io.BytesIO(tresc), "t.json")})
    p = client.get("/teren/projekty/1/punkty").get_json()[0]
    assert (p["zdjecie_opis"], p["zdjecie_kierunek"], p["kierunek_opis"]) == ("brama wjazdowa", 135, "↘ SE")
    raport = client.get("/teren/projekty/1/raport").get_data(as_text=True)
    assert "brama wjazdowa" in raport and "widok ↘ SE" in raport
    wl = json.loads(client.get("/teren/projekty/1.geojson").data)["features"][0]["properties"]
    assert (wl["zdjecie_opis"], wl["zdjecie_kierunek"]) == ("brama wjazdowa", 135)
    assert "zdjecie_opis;zdjecie_kierunek" in client.get("/teren/projekty/1.csv").get_data(as_text=True).splitlines()[0]

    url = f"/teren/projekty/1/punkty/{p['id']}"
    p = client.put(url, json={"wartosci": {}, "uwagi": "", "zdjecie_opis": "brama", "zdjecie_kierunek": None}).get_json()
    assert (p["zdjecie_opis"], p["zdjecie_kierunek"], p["kierunek_opis"]) == ("brama", None, "")
    p = client.put(url, json={"wartosci": {}, "uwagi": "x"}).get_json()  # bez kluczy — podpis zostaje
    assert p["zdjecie_opis"] == "brama"
    assert client.put(url, json={"wartosci": {}, "zdjecie_kierunek": 10}).status_code == 400


def test_raport_bez_opisu_zdjecia_nie_pisze_none(client):
    client.post("/teren/projekty", data={"nazwa": "Zieleń", "wzor": "zielen"})
    klucz = re.search(r'"klucz": "([^"]+)"', client.get("/teren/projekty/1/formularz.html").get_data(as_text=True)).group(1)
    tresc = json.dumps(plik(klucz, punkt(zdjecie_kierunek=45))).encode()
    client.post("/teren/projekty/1/import", content_type="multipart/form-data", data={"plik": (io.BytesIO(tresc), "t.json")})
    raport = client.get("/teren/projekty/1/raport").get_data(as_text=True)
    assert "widok ↗ NE" in raport and "None" not in raport


# ---------- ETAP 220: import CSV ----------

def test_odczytaj_csv_polski_arkusz():
    from teren.projekt import odczytaj_csv
    tekst = ("lat;lng;Obiekt;stan;obwód pnia [cm];uwagi;właściciel\n"
             "52,4064;16,9252;drzewo;dobry;120,5;przy ławce;gmina\n"
             ";;krzew;;;bez GPS;\n"
             "\n")
    punkty, niedopasowane = odczytaj_csv(tekst.encode("cp1250"), POLA)  # Excel po polsku zapisuje w Windows-1250
    assert niedopasowane == ["właściciel"]
    p = punkty[0]
    assert (p["lat"], p["lng"]) == (52.4064, 16.9252)
    assert p["wartosci"] == {"obiekt": "drzewo", "stan": "dobry", "obwód pnia [cm]": 120.5}
    assert p["uwagi"] == "przy ławce; właściciel: gmina" and p["uid"].startswith("csv_")
    assert punkty[1]["lat"] is None and punkty[1]["wartosci"] == {"obiekt": "krzew"}
    # ten sam plik drugi raz — te same identyfikatory (import pominie)
    assert [x["uid"] for x in odczytaj_csv(tekst.encode("cp1250"), POLA)[0]] == [x["uid"] for x in punkty]


def test_odczytaj_csv_przecinek_i_eksport_warsztatu():
    from teren.projekt import odczytaj_csv
    punkty, _ = odczytaj_csv('﻿szerokosc,dlugosc,obiekt,id,zdjecie\n52.4,16.9,"drzewo",7,7.jpg\n'.encode(), POLA)
    assert punkty[0]["wartosci"] == {"obiekt": "drzewo"} and punkty[0]["uwagi"] == ""  # kolumny eksportu pominięte


@pytest.mark.parametrize("tekst, komunikat", [
    ("", "pusty"),
    ("x;y\n1;2\n", "Brak kolumn ze współrzędnymi"),
    ("jedna\n1\n", "separatora"),
    ("lat;lng\n5240;1690\n", "Wiersz 2: współrzędne nie wyglądają na stopnie"),
    ("lat;lng\n52.4;\n", "Wiersz 2, długość"),
    ("lat;lng;obiekt\n52.4;16.9;słoń\n", "Wiersz 2"),
    ("lat;lng\n52.4;16.9;nadmiar\n", "więcej wartości"),
])
def test_odczytaj_csv_odrzuca(tekst, komunikat):
    from teren.projekt import odczytaj_csv
    with pytest.raises(BladDanych, match=komunikat):
        odczytaj_csv(tekst.encode(), POLA)


def test_import_csv_przez_strone(client):
    client.post("/teren/projekty", data={"nazwa": "Zieleń", "wzor": "zielen"})
    tresc = "lat;lng;obiekt;notatka\n52.4;16.9;drzewo;stare\n52.41;16.91;krzew;\n".encode()

    def importuj(nazwa="punkty.csv"):
        return client.post("/teren/projekty/1/import", content_type="multipart/form-data",
                           data={"plik": (io.BytesIO(tresc), nazwa)}).get_json()

    assert importuj() == {"dodane": 2, "pominiete": 0, "niedopasowane": []}
    assert importuj()["pominiete"] == 2
    assert client.get("/teren/projekty/1/punkty").get_json()[0]["uwagi"] == "stare"
    assert "blad" in client.post("/teren/projekty/1/import", content_type="multipart/form-data",
                                 data={"plik": (io.BytesIO(b"a;b\n1;2"), "x.csv")}).get_json()


def test_geojson_uid_bez_zmian_po_przebudowie():
    """Refaktoryzacja w ETAPie 220 nie może zmienić identyfikatorów z ETAPu 133 —
    inaczej ponowny import starego GeoJSON zdublowałby punkty."""
    import hashlib
    from teren.projekt import odczytaj_geojson
    atr = {"obiekt": "drzewo"}
    punkty, _ = odczytaj_geojson({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [16.9, 52.4]}, "properties": atr}]}, POLA)
    stary = "gj_" + hashlib.sha1(json.dumps([16.9, 52.4, atr], sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:24]
    assert punkty[0]["uid"] == stary
