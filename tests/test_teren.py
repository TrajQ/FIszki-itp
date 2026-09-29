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
    assert client.get(punkty[0]["zdjecie"]).data == JPEG

    geo = json.loads(client.get("/teren/projekty/1.geojson").data)
    assert len(geo["features"]) == 2 and geo["features"][0]["properties"]["obiekt"] == "drzewo"
    csv = client.get("/teren/projekty/1.csv").get_data(as_text=True)
    assert csv.startswith("﻿id;czas;szerokosc;dlugosc;dokladnosc_m;obiekt;gatunek;obwód pnia [cm];stan;uwagi;zdjecie")

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
