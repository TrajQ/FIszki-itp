import io

import h3
import pytest

import dostepnosc.routes as dostepnosc_routes
from app import create_app
from dostepnosc import wyniki
from dostepnosc.wyniki import BladWynikow

SRODEK = h3.latlng_to_cell(52.4064, 16.9252, 9)
SASIEDZI = sorted(h3.grid_disk(SRODEK, 1))  # 7 komórek


def csv_testowy(separator=",", przecinek=False):
    wiersze = [separator.join(["h3", "czas_przystanek_min", "gestosc"])]
    for i, komorka in enumerate(SASIEDZI):
        czas = str(i * 3.5)  # 0, 3.5, 7, 10.5, 14, 17.5, 21
        if przecinek:
            czas = czas.replace(".", ",")
        gestosc = "" if i == 0 else str(100 * i)
        wiersze.append(separator.join([komorka, czas, gestosc]))
    return "\n".join(wiersze)


# ---------- wczytywanie ----------


def test_wczytaj_csv():
    dane = wyniki.wczytaj_csv(csv_testowy())
    assert dane["komorki"] == SASIEDZI
    assert dane["rozdzielczosc"] == 9
    assert dane["kolumny"]["czas_przystanek_min"][1] == 3.5
    assert dane["kolumny"]["gestosc"][0] is None


def test_wczytaj_csv_srednik_i_przecinek_dziesietny():
    dane = wyniki.wczytaj_csv("﻿" + csv_testowy(separator=";", przecinek=True))
    assert dane["kolumny"]["czas_przystanek_min"][1] == 3.5


@pytest.mark.parametrize(
    "tekst,fragment",
    [
        ("", "pusty"),
        ("id,czas_min\n1,2", "Brak kolumny"),
        ("h3\n" + SRODEK, "żadnych kolumn"),
        (f"h3,czas_min\nabc,2", "poprawnym indeksem"),
        (f"h3,czas_min\n{SRODEK},dużo", "nie jest liczbą"),
        (f"h3,czas_min\n{SRODEK},\n", "Żadna kolumna"),
        (f"h3,czas_min\n{SRODEK},1\n{h3.cell_to_parent(SRODEK, 8)},2", "różne rozdzielczości"),
    ],
)
def test_wczytaj_csv_bledy(tekst, fragment):
    with pytest.raises(BladWynikow, match=fragment):
        wyniki.wczytaj_csv(tekst)


# ---------- analiza ----------


def test_analiza_kolumny_minut():
    analiza = wyniki.analiza_kolumny(wyniki.wczytaj_csv(csv_testowy()), "czas_przystanek_min")

    assert analiza["minuty"] is True
    assert analiza["progi"] == [5, 10, 15, 20, 30]
    klasy = [c["properties"]["klasa"] for c in analiza["geojson"]["features"]]
    assert klasy == [0, 0, 1, 2, 2, 3, 4]  # 0; 3.5; 7; 10.5; 14; 17.5; 21

    s = analiza["statystyki"]
    assert s["liczba_komorek"] == 7
    assert s["mediana"] == 10.5
    udzialy = {u["prog"]: u for u in s["udzialy"]}
    assert udzialy[15]["procent"] == pytest.approx(100 * 5 / 7)
    assert udzialy[5]["powierzchnia_km2"] == pytest.approx(2 * h3.average_hexagon_area(9, unit="km^2"))

    wielokat = analiza["geojson"]["features"][0]["geometry"]["coordinates"][0]
    assert wielokat[0] == wielokat[-1]  # pierścień domknięty
    lon, lat = wielokat[0]
    assert 16 < lon < 18 and 52 < lat < 53  # kolejność (lon, lat)


def test_analiza_kolumny_innej_pomija_braki_i_uzywa_kwantyli():
    analiza = wyniki.analiza_kolumny(wyniki.wczytaj_csv(csv_testowy()), "gestosc")
    assert analiza["minuty"] is False
    assert "udzialy" not in analiza["statystyki"]
    assert analiza["statystyki"]["komorki_bez_wartosci"] == 1
    assert len(analiza["geojson"]["features"]) == 6
    assert analiza["progi"] == sorted(analiza["progi"])


def test_czy_minuty():
    assert wyniki.czy_minuty("czas_szkola")
    assert wyniki.czy_minuty("przystanek_min")
    assert not wyniki.czy_minuty("gestosc")


# ---------- endpointy ----------


@pytest.fixture
def client(tmp_path):
    dostepnosc_routes._cache.clear()
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def wgraj(client, tekst, nazwa="moje.csv"):
    return client.post(
        "/dostepnosc/wgraj",
        data={"plik": (io.BytesIO(tekst.encode("utf-8")), nazwa)},
        content_type="multipart/form-data",
    )


def test_przyklad_jest_dostepny_od_razu(client):
    strona = client.get("/dostepnosc/").get_data(as_text=True)
    assert "przyklad_poznan_syntetyczny.csv" in strona
    assert "dane syntetyczne" in strona

    meta = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv").get_json()
    assert meta["przyklad"] is True
    assert [k["nazwa"] for k in meta["kolumny"]][0] == "czas_przystanek_min"

    analiza = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/czas_przystanek_min").get_json()
    assert analiza["statystyki"]["liczba_komorek"] == meta["liczba_komorek"]


def test_wgranie_analiza_i_usuniecie(client):
    odpowiedz = wgraj(client, csv_testowy())
    assert odpowiedz.status_code == 302
    assert "plik=moje.csv" in odpowiedz.headers["Location"]

    meta = client.get("/dostepnosc/plik/moje.csv").get_json()
    assert meta["liczba_komorek"] == 7
    assert client.get("/dostepnosc/plik/moje.csv/nie_ma").status_code == 404

    assert client.post("/dostepnosc/plik/moje.csv/usun").status_code == 302
    assert client.get("/dostepnosc/plik/moje.csv").status_code == 404


def test_wgranie_zlego_pliku_nie_zapisuje_go(client):
    odpowiedz = wgraj(client, "id,x\n1,2")
    assert "blad=" in odpowiedz.headers["Location"]
    assert client.get("/dostepnosc/plik/moje.csv").status_code == 404
    assert "blad=" in wgraj(client, csv_testowy(), nazwa="dane.txt").headers["Location"]


def test_nie_da_sie_usunac_przykladu_ani_wyjsc_poza_folder(client):
    assert client.post("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/usun").status_code == 400
    assert client.get("/dostepnosc/plik/..%2Fconfig.py").status_code == 404
