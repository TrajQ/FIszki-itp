"""dostepnosc/model.py i /dostepnosc/z-punktow — szybki model z punktów (ETAP 47)."""

import h3
import pytest

from app import create_app
from dostepnosc import model, wyniki

SRODEK = (52.4064, 16.9252)


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_nazwa_kolumny():
    assert model.nazwa_kolumny("Szkoła podstawowa") == "czas_szkola_podstawowa_min"
    assert wyniki.czy_minuty(model.nazwa_kolumny("żłobek"))
    with pytest.raises(model.BladModelu):
        model.nazwa_kolumny("  !!! ")


def test_czas_dojscia_zgodny_z_modelem_przykladow():
    # komórka 1 km na wschód od punktu: 1000 m × 1,3 / 80 m/min = 16,25 min
    komorka = h3.latlng_to_cell(SRODEK[0], SRODEK[1] + 0.0147, 12)  # ~1 km na tej szerokości
    lat, lon = h3.cell_to_latlng(komorka)
    odleglosc = model._odleglosc_m(SRODEK[0], SRODEK[1], lat, lon)
    czasy, najblizsze = model.czasy_dojscia([komorka], [SRODEK], 4.8, 1.3)
    assert czasy[0] == pytest.approx(odleglosc * 1.3 / 80, abs=0.05)
    assert 990 < odleglosc < 1010 and najblizsze == [0]


def test_najblizszy_punkt_i_obszary_obslugi():
    komorki = sorted(h3.grid_disk(h3.latlng_to_cell(*SRODEK, 9), 3))
    daleki = (SRODEK[0], SRODEK[1] + 0.2)
    czasy, najblizsze = model.czasy_dojscia(komorki, [SRODEK, daleki], 4.8, 1.3)
    assert set(najblizsze) == {0}  # wszystkie komórki bliżej pierwszego punktu
    obszary = model.obszary_obslugi([SRODEK, daleki], czasy, najblizsze, [10.0] * len(komorki))
    assert obszary[0]["komorki"] == len(komorki) and obszary[0]["ludnosc"] == 10 * len(komorki)
    assert obszary[1]["komorki"] == 0 and obszary[1]["sredni_czas_min"] is None


@pytest.mark.parametrize(
    "punkty,predkosc,kretosc",
    [([], 4.8, 1.3), ([[52, "x"]], 4.8, 1.3), ([[95, 16]], 4.8, 1.3), ([[52, 16]], 20, 1.3), ([[52, 16]], 4.8, 3), ([[52, 16]] * 101, 4.8, 1.3)],
)
def test_zle_parametry(punkty, predkosc, kretosc):
    with pytest.raises(model.BladModelu):
        model.sprawdz_parametry(punkty, predkosc, kretosc)


def test_siatka_obszaru_i_limit():
    komorki = model.siatka_obszaru(52.40, 16.90, 52.42, 16.95)
    assert komorki and all(h3.get_resolution(k) == 9 for k in komorki)
    with pytest.raises(model.BladModelu):
        model.siatka_obszaru(50, 14, 55, 24)  # pół Polski — za dużo komórek


def test_endpoint_na_bazie_przykladu_zachowuje_kolumny_i_ludnosc(client):
    odpowiedz = client.post(
        "/dostepnosc/z-punktow",
        json={"usluga": "Szkoła", "punkty": [list(SRODEK)], "baza": "przyklad_poznan_syntetyczny.csv", "predkosc_kmh": "4,8"},
    )
    assert odpowiedz.status_code == 200, odpowiedz.get_json()
    dane = odpowiedz.get_json()
    assert dane["plik"] == "przyklad_poznan_syntetyczny_szkola.csv"
    assert dane["obszary"][0]["ludnosc"] > 0

    opis = client.get(f"/dostepnosc/plik/{dane['plik']}").get_json()
    kolumny = [k["nazwa"] for k in opis["kolumny"]]
    assert "czas_szkola_min" in kolumny and "czas_przystanek_min" in kolumny
    assert opis["ma_ludnosc"] and opis["punkty"]["usluga"] == "Szkoła"
    # analiza nowej kolumny działa jak dla wgranego pliku
    assert client.get(f"/dostepnosc/plik/{dane['plik']}/czas_szkola_min").status_code == 200

    # drugi raz ta sama nazwa — nie nadpisujemy
    drugi = client.post("/dostepnosc/z-punktow", json={"usluga": "Szkoła", "punkty": [list(SRODEK)], "baza": "przyklad_poznan_syntetyczny.csv"})
    assert drugi.get_json()["plik"] == "przyklad_poznan_syntetyczny_szkola_2.csv"

    # usunięcie pliku usuwa też plik punktów
    client.post(f"/dostepnosc/plik/{dane['plik']}/usun")
    assert client.get(f"/dostepnosc/plik/{dane['plik']}").status_code == 404


def test_endpoint_nowa_siatka_i_bledy(client):
    ok = client.post(
        "/dostepnosc/z-punktow",
        json={"usluga": "przystanek", "punkty": [list(SRODEK)], "obszar": [52.40, 16.91, 52.41, 16.94], "nazwa_pliku": "moj wariant"},
    )
    assert ok.status_code == 200 and ok.get_json()["plik"] == "moj_wariant.csv"
    assert "ludnosc" not in ok.get_json()["obszary"][0]

    assert client.post("/dostepnosc/z-punktow", json={"usluga": "x", "punkty": [list(SRODEK)]}).status_code == 400  # bez obszaru
    assert client.post("/dostepnosc/z-punktow", json={"usluga": "", "punkty": [list(SRODEK)], "obszar": [52.40, 16.91, 52.41, 16.94]}).status_code == 400
    assert client.post("/dostepnosc/z-punktow", json={"usluga": "x", "punkty": [list(SRODEK)], "obszar": [52.40, 16.91, 52.41, 16.94], "kretosc": "nan"}).status_code == 400
    assert client.post("/dostepnosc/z-punktow", json={"usluga": "x", "punkty": [list(SRODEK)], "baza": "../../etc.csv"}).status_code == 404


# ---------- ETAP 48: raport i mapa do druku ----------

from dostepnosc import druk  # noqa: E402

PRZYKLAD = "przyklad_poznan_syntetyczny.csv"


def test_legenda_minut_liczy_komorki_w_klasach():
    dane = wyniki.wczytaj_csv("h3,czas_min\n" + "\n".join(
        f"{k},{t}" for k, t in zip(sorted(h3.grid_disk(h3.latlng_to_cell(*SRODEK, 9), 1)), [1, 4, 7, 12, 18, 25, 40])
    ))
    legenda = druk.legenda(wyniki.analiza_kolumny(dane, "czas_min"))
    assert [opis for _, opis, _ in legenda] == ["≤ 5 min", "5 – 10 min", "10 – 15 min", "15 – 20 min", "20 – 30 min", "> 30 min"]
    assert [ile for _, _, ile in legenda] == [2, 1, 1, 1, 1, 1]
    assert legenda[0][0] == druk.KOLORY_MINUT[0]


def test_podzialka_w_metrach():
    assert druk.dlugosc_podzialki_m(10) == 1000  # 1 km = 100 px
    assert druk.dlugosc_podzialki_m(0.1) == 100  # nic się nie mieści: najkrótsza


def test_mapa_svg_i_raport_z_punktami(client):
    odpowiedz = client.get(f"/dostepnosc/mapa.svg?plik={PRZYKLAD}&kolumna=czas_szkola_min")
    assert odpowiedz.status_code == 200 and odpowiedz.mimetype == "image/svg+xml"
    svg = odpowiedz.get_data(as_text=True)
    assert svg.count("<polygon") > 600 and "Dane syntetyczne" in svg and ">N</text>" in svg

    laczny = client.get(f"/dostepnosc/raport?plik={PRZYKLAD}&kolumna=laczny").get_data(as_text=True)
    assert "Najsłabsze ogniwo" in laczny and "≤ 15 min" in laczny and "Mieszkańcy" in laczny

    nowy = client.post(
        "/dostepnosc/z-punktow", json={"usluga": "Żłobek", "punkty": [list(SRODEK)], "baza": PRZYKLAD}
    ).get_json()["plik"]
    raport = client.get(f"/dostepnosc/raport?plik={nowy}&kolumna=czas_zlobek_min").get_data(as_text=True)
    assert "Obszary obsługi — Żłobek" in raport
    svg = client.get(f"/dostepnosc/mapa.svg?plik={nowy}&kolumna=czas_zlobek_min&pobierz=1")
    assert "attachment" in svg.headers["Content-Disposition"]
    assert "punkt usługi" in svg.get_data(as_text=True) and "Szybki model" in svg.get_data(as_text=True)

    assert client.get(f"/dostepnosc/mapa.svg?plik={PRZYKLAD}&kolumna=brak").status_code == 404
    assert client.get(f"/dostepnosc/raport?plik={PRZYKLAD}&kolumna=brak").status_code == 404
