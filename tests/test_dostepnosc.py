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


# ---------- ETAP 13: wskaźnik łączny ----------


def test_analiza_laczna_bierze_maksimum_i_liczy_najslabsze_ogniwo():
    komorki = SASIEDZI[:4]
    tekst = "h3,czas_a_min,czas_b_min,gestosc\n" + "\n".join(
        [
            f"{komorki[0]},3,12,1",  # łącznie 12 (b)
            f"{komorki[1]},20,4,1",  # 20 (a)
            f"{komorki[2]},2,,1",  # brak b → brak łącznego
            f"{komorki[3]},8,9,1",  # 9 (b)
        ]
    )
    analiza = wyniki.analiza_laczna(wyniki.wczytaj_csv(tekst))

    wartosci = [c["properties"]["wartosc"] for c in analiza["geojson"]["features"]]
    assert wartosci == [12, 20, 9]
    assert analiza["minuty"] is True
    assert analiza["statystyki"]["komorki_bez_wartosci"] == 1
    assert analiza["skladowe"] == ["czas_a_min", "czas_b_min"]
    ogniwa = {o["kolumna"]: o["komorki"] for o in analiza["najslabsze_ogniwo"]}
    assert ogniwa == {"czas_b_min": 2, "czas_a_min": 1}
    assert analiza["najslabsze_ogniwo"][0]["procent"] == pytest.approx(200 / 3)


def test_analiza_laczna_wymaga_dwoch_kolumn_czasu():
    with pytest.raises(BladWynikow, match="dwóch"):
        wyniki.analiza_laczna(wyniki.wczytaj_csv(csv_testowy()))


def test_endpoint_laczny(client):
    meta = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv").get_json()
    assert meta["laczny_dostepny"] is True
    analiza = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/laczny").get_json()
    assert len(analiza["najslabsze_ogniwo"]) == 3

    wgraj(client, csv_testowy())
    assert client.get("/dostepnosc/plik/moje.csv").get_json()["laczny_dostepny"] is False
    assert client.get("/dostepnosc/plik/moje.csv/laczny").status_code == 422


# ---------- ETAP 15: poprawki z przeglądu kodu ----------


def test_wgranie_pliku_z_wielkimi_literami_w_rozszerzeniu(client):
    odpowiedz = wgraj(client, csv_testowy(), nazwa="Wyniki.CSV")
    assert "plik=Wyniki.csv" in odpowiedz.headers["Location"]
    assert client.get("/dostepnosc/plik/Wyniki.csv").status_code == 200
    assert "Wyniki.csv" in client.get("/dostepnosc/").get_data(as_text=True)
    assert client.post("/dostepnosc/plik/Wyniki.csv/usun").status_code == 302


def test_powtorzone_nazwy_kolumn_odrzucone():
    with pytest.raises(BladWynikow, match="Powtórzone"):
        wyniki.wczytaj_csv(f"h3,x_min,x_min\n{SRODEK},2,3")


def test_laczny_bez_zadnej_pelnej_komorki_to_czytelny_blad(client):
    k = SASIEDZI
    tekst = f"h3,czas_a_min,czas_b_min\n{k[0]},3,\n{k[1]},,4"
    with pytest.raises(BladWynikow, match="Żadna komórka"):
        wyniki.analiza_laczna(wyniki.wczytaj_csv(tekst))

    wgraj(client, tekst, nazwa="dziury.csv")
    odpowiedz = client.get("/dostepnosc/plik/dziury.csv/laczny")
    assert odpowiedz.status_code == 422
    assert "Żadna komórka" in odpowiedz.get_json()["blad"]


# ---------- ETAP 21: ludność i porównanie scenariuszy ----------


def csv_z_ludnoscia(czasy, ludnosc=None, kolumna="czas_szkola_min"):
    naglowek = f"h3,{kolumna}" + (",ludnosc" if ludnosc else "")
    wiersze = [naglowek]
    for i, czas in enumerate(czasy):
        pola = [SASIEDZI[i], "" if czas is None else str(czas)]
        if ludnosc:
            pola.append(str(ludnosc[i]))
        wiersze.append(",".join(pola))
    return "\n".join(wiersze)


def test_ludnosc_to_waga_a_nie_wskaznik():
    dane = wyniki.wczytaj_csv(csv_z_ludnoscia([3, 12, 20], [100, 300, 600]))
    assert list(dane["kolumny"]) == ["czas_szkola_min"]
    assert dane["ludnosc"] == [100, 300, 600]

    udzialy = {u["prog"]: u for u in wyniki.analiza_kolumny(dane, "czas_szkola_min")["statystyki"]["udzialy"]}
    assert udzialy[5]["ludnosc"] == 100
    assert udzialy[15]["ludnosc"] == 400
    assert udzialy[15]["procent_ludnosci"] == pytest.approx(40.0)
    assert udzialy[15]["procent"] == pytest.approx(200 / 3)  # powierzchnia (komórki) inaczej niż ludność


def test_bez_ludnosci_brak_pol_ludnosci():
    udzialy = wyniki.analiza_kolumny(wyniki.wczytaj_csv(csv_z_ludnoscia([3, 12])), "czas_szkola_min")["statystyki"]["udzialy"]
    assert "procent_ludnosci" not in udzialy[0]


def test_ujemna_ludnosc_odrzucona():
    with pytest.raises(BladWynikow, match="ujemne"):
        wyniki.wczytaj_csv(csv_z_ludnoscia([3], [-5]))


def test_porownanie_scenariuszy():
    przed = wyniki.wczytaj_csv(csv_z_ludnoscia([20, 18, 7, 12, None], [100, 200, 300, 400, 500]))
    po = wyniki.wczytaj_csv(csv_z_ludnoscia([9, 17.5, 7, 17, 3], [100, 200, 300, 400, 500]))
    wynik = wyniki.porownaj_scenariusze(przed, po, "czas_szkola_min")
    s = wynik["statystyki"]

    assert s["liczba_komorek"] == 4  # piąta komórka bez wartości „przed”
    assert (s["poprawa"], s["pogorszenie"], s["bez_zmian"]) == (1, 1, 2)
    assert s["najwieksza_poprawa"] == -11
    assert s["komorki_weszly_15"] == 1 and s["komorki_wypadly_15"] == 1
    assert s["ludnosc_weszla_15"] == 100 and s["ludnosc_wypadla_15"] == 400
    assert s["procent_15_przed"] == pytest.approx(50.0) and s["procent_15_po"] == pytest.approx(50.0)
    klasy = [c["properties"]["klasa"] for c in wynik["geojson"]["features"]]
    assert klasy == [0, 2, 2, 3]  # −11 → szybciej ≥5; −0,5 i 0 → bez zmian; +5 → wolniej 1–5


def test_porownanie_wskaznika_lacznego_i_bledy():
    k = SASIEDZI
    przed = wyniki.wczytaj_csv(f"h3,czas_a_min,czas_b_min\n{k[0]},5,20\n{k[1]},4,6")
    po = wyniki.wczytaj_csv(f"h3,czas_a_min,czas_b_min\n{k[0]},5,8\n{k[1]},4,6")
    s = wyniki.porownaj_scenariusze(przed, po, wyniki.NAZWA_LACZNEGO)["statystyki"]
    assert s["najwieksza_poprawa"] == -12  # łącznie 20 → 8

    with pytest.raises(BladWynikow, match="czasu"):
        wyniki.porownaj_scenariusze(wyniki.wczytaj_csv(csv_testowy()), wyniki.wczytaj_csv(csv_testowy()), "gestosc")
    inna_rozdz = wyniki.wczytaj_csv(f"h3,czas_a_min\n{h3.cell_to_parent(k[0], 8)},5")
    with pytest.raises(BladWynikow, match="rozdzielczości"):
        wyniki.porownaj_scenariusze(przed, inna_rozdz, "czas_a_min")


def test_endpoint_porownania_na_przykladach(client):
    strona = client.get("/dostepnosc/").get_data(as_text=True)
    assert "przyklad_poznan_nowa_szkola_syntetyczny.csv" in strona

    adres = "/dostepnosc/porownanie?przed=przyklad_poznan_syntetyczny.csv&po=przyklad_poznan_nowa_szkola_syntetyczny.csv"
    s = client.get(adres + "&kolumna=czas_szkola_min").get_json()["statystyki"]
    assert s["poprawa"] > 0 and s["pogorszenie"] == 0
    assert s["ludnosc_weszla_15"] > 0
    assert client.get(adres + "&kolumna=laczny").status_code == 200
    assert client.get(adres + "&kolumna=nie_ma_min").status_code == 422
    assert client.get("/dostepnosc/porownanie?przed=a.csv&po=a.csv&kolumna=x").status_code == 400
    assert client.post("/dostepnosc/plik/przyklad_poznan_nowa_szkola_syntetyczny.csv/usun").status_code == 400

    meta = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv").get_json()
    assert meta["ma_ludnosc"] is True
