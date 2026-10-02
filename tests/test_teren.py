"""Moduł teren: pola projektu, plik z telefonu, import i eksport (ETAP 65)."""

import base64
import io
import json
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
    assert list((tmp_path / "teren" / "zdjecia").iterdir()) == []


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
    assert "Park Wilsona" not in client.get("/").get_data(as_text=True).split('class="siatka-kart"')[0]


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
