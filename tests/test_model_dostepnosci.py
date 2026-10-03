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


# ---------- ETAP 49: dodanie punktów do istniejących usług ----------


def test_polacz_z_istniejacymi():
    polaczone, lepiej = model.polacz_z_istniejacymi([10.0, 3.0, None], [5.0, 8.0, 7.0])
    assert polaczone == [5.0, 3.0, 7.0] and lepiej == [True, False, True]


def test_nowa_szkola_obok_obecnych_daje_porownywalny_scenariusz(client):
    import os

    sciezka = os.path.join(os.path.dirname(__file__), "..", "dostepnosc", "przyklad", PRZYKLAD)
    with open(sciezka, encoding="utf-8") as plik:
        przed = wyniki.wczytaj_csv(plik.read())
    punkt_luki = h3.cell_to_latlng(przed["komorki"][max(range(len(przed["komorki"])), key=lambda i: przed["kolumny"]["czas_szkola_min"][i])])

    dane = client.post(
        "/dostepnosc/z-punktow",
        json={"usluga": "szkola", "punkty": [list(punkt_luki)], "baza": PRZYKLAD, "polacz": True},
    ).get_json()
    assert dane["polaczone"] is True
    po = client.get(f"/dostepnosc/plik/{dane['plik']}/czas_szkola_min").get_json()
    przed_czasy = dict(zip(przed["komorki"], przed["kolumny"]["czas_szkola_min"]))
    for cecha in po["geojson"]["features"]:
        assert cecha["properties"]["wartosc"] <= przed_czasy[cecha["properties"]["h3"]] + 1e-9  # nigdy gorzej
    assert dane["obszary"][0]["ludnosc"] > 0  # mieszkańcy, którzy zyskali

    porownanie = client.get(f"/dostepnosc/porownanie?przed={PRZYKLAD}&po={dane['plik']}&kolumna=czas_szkola_min")
    assert porownanie.status_code == 200 and porownanie.get_json()["statystyki"]["poprawa"] > 0


def test_polacz_bez_takiej_kolumny_to_czytelny_blad(client):
    odpowiedz = client.post(
        "/dostepnosc/z-punktow", json={"usluga": "basen", "punkty": [list(SRODEK)], "baza": PRZYKLAD, "polacz": True}
    )
    assert odpowiedz.status_code == 400 and "nie ma z czym połączyć" in odpowiedz.get_json()["blad"]


# ---------- ETAP 55: punkty usług z pliku CSV ----------

import io  # noqa: E402


def test_punkty_z_csv_naglowki_przecinek_i_kolejnosc():
    punkty, bledy = model.punkty_z_csv("nazwa;lat;lon\nSP 1;52,40;16,92\nzły;a;b\n")
    assert punkty == [{"lat": 52.40, "lon": 16.92, "nazwa": "SP 1", "usluga": ""}]
    assert bledy == ["wiersz 3: brak liczbowych współrzędnych"]
    # bez nagłówka, kolejność x,y (długość, szerokość) — rozpoznana po zakresie
    punkty, _ = model.punkty_z_csv("16.92,52.40,Szkoła\n")
    assert punkty == [{"lat": 52.40, "lon": 16.92, "nazwa": "Szkoła", "usluga": ""}]
    # nagłówek QGIS: X = długość, Y = szerokość
    assert model.punkty_z_csv("X,Y,name\n16.9,52.4,A\n")[0][0] == {"lat": 52.4, "lon": 16.9, "nazwa": "A", "usluga": ""}
    # ETAP 223: kolumna usługi
    assert [p["usluga"] for p in model.punkty_z_csv("lat;lon;nazwa;rodzaj\n52,4;16,9;SP 1;szkoła\n52,41;16,91;P 7;przedszkole\n")[0]] == ["szkoła", "przedszkole"]


def test_punkty_z_csv_bledy():
    with pytest.raises(model.BladModelu):
        model.punkty_z_csv("")
    with pytest.raises(model.BladModelu):
        model.punkty_z_csv("lat,lon\n500000,300000\n")  # PL-1992 zamiast stopni — nic nie przechodzi
    with pytest.raises(model.BladModelu):
        model.punkty_z_csv("\n".join(f"52.{i:03d},16.9" for i in range(model.MAKS_PUNKTOW + 1)))


def test_endpoint_punktow_z_pliku_i_nazwy_w_obszarach(client):
    odpowiedz = client.post(
        "/dostepnosc/punkty-z-pliku",
        data={"plik": (io.BytesIO("lat;lon;nazwa\n52,4064;16,9252;SP 1\n".encode("utf-8")), "szkoly.csv")},
        content_type="multipart/form-data",
    )
    punkty = odpowiedz.get_json()["punkty"]
    assert punkty == [{"lat": 52.4064, "lon": 16.9252, "nazwa": "SP 1", "usluga": ""}]

    wynik = client.post(
        "/dostepnosc/z-punktow",
        json={"usluga": "szkoła", "punkty": [[p["lat"], p["lon"]] for p in punkty], "nazwy": ["SP 1"], "baza": PRZYKLAD},
    ).get_json()
    assert wynik["obszary"][0]["nazwa"] == "SP 1"
    raport = client.get(f"/dostepnosc/raport?plik={wynik['plik']}&kolumna=czas_szkola_min").get_data(as_text=True)
    assert "1. SP 1" in raport

    zly = client.post("/dostepnosc/punkty-z-pliku", data={"plik": (io.BytesIO("ą".encode("cp1250")), "x.csv")}, content_type="multipart/form-data")
    assert zly.status_code == 400
    assert client.post("/dostepnosc/punkty-z-pliku", data={}, content_type="multipart/form-data").status_code == 400


def test_punkty_pliku_mowia_czy_baza_istnieje(client, tmp_path):
    """ETAP 222: „Edytuj te punkty” liczy ponownie na pliku bazowym — strona musi wiedzieć, czy jest."""
    baza = client.post("/dostepnosc/z-punktow", json={"usluga": "x", "punkty": [list(SRODEK)], "obszar": [52.40, 16.91, 52.41, 16.94]}).get_json()["plik"]
    meta = client.get(f"/dostepnosc/plik/{baza}").get_json()
    assert meta["punkty"]["baza"] is None and meta["punkty"]["baza_istnieje"] is False
    wynik = client.post("/dostepnosc/z-punktow", json={"usluga": "Szkoła", "punkty": [list(SRODEK)], "nazwy": ["SP 1"], "baza": baza}).get_json()["plik"]
    punkty = client.get(f"/dostepnosc/plik/{wynik}").get_json()["punkty"]
    assert (punkty["baza"], punkty["baza_istnieje"], punkty["obszary"][0]["nazwa"]) == (baza, True, "SP 1")
    (tmp_path / "dostepnosc" / "wyniki" / baza).unlink()
    assert client.get(f"/dostepnosc/plik/{wynik}").get_json()["punkty"]["baza_istnieje"] is False
    przyklad = client.post("/dostepnosc/z-punktow", json={"usluga": "Szkoła", "punkty": [list(SRODEK)], "baza": PRZYKLAD}).get_json()["plik"]
    assert client.get(f"/dostepnosc/plik/{przyklad}").get_json()["punkty"]["baza_istnieje"] is True
    assert 'id="lista-punktow-modelu"' in client.get("/dostepnosc/").get_data(as_text=True)


# ---------- ETAP 223: kilka rodzajów usług w jednym liczeniu ----------


def test_grupy_uslug():
    p = [SRODEK] * 4
    grupy = model.grupy_uslug(p, "Szkoła", ["", "przedszkole", "szkola", None])
    assert [(g["usluga"], g["kolumna"], g["indeksy"]) for g in grupy] == [
        ("Szkoła", "czas_szkola_min", [0, 2, 3]), ("przedszkole", "czas_przedszkole_min", [1])]
    assert len(model.grupy_uslug(p, "x", None)) == 1
    with pytest.raises(model.BladModelu):
        model.grupy_uslug(p, "", ["a", "", "", ""])  # punkt bez usługi i puste pole „Usługa”
    with pytest.raises(model.BladModelu, match="Najwyżej"):
        model.grupy_uslug([SRODEK] * 9, "x", [f"u{i}" for i in range(9)])


def test_kilka_uslug_daje_kilka_kolumn_i_wskaznik_laczny(client):
    daleko = (SRODEK[0] + 0.01, SRODEK[1] + 0.01)
    dane = client.post("/dostepnosc/z-punktow", json={
        "usluga": "Szkoła", "punkty": [list(SRODEK), list(daleko), list(daleko)],
        "uslugi": ["", "przedszkole", ""], "nazwy": ["SP 1", "P 7", "SP 2"], "baza": PRZYKLAD}).get_json()
    assert dane["plik"] == "przyklad_poznan_syntetyczny_2_uslugi.csv"
    assert [g["kolumna"] for g in dane["grupy"]] == ["czas_szkola_min", "czas_przedszkole_min"]
    assert [o["nazwa"] for o in dane["grupy"][0]["obszary"]] == ["SP 1", "SP 2"] and dane["grupy"][1]["obszary"][0]["nazwa"] == "P 7"
    assert dane["kolumna"] == "czas_szkola_min" and dane["obszary"] == dane["grupy"][0]["obszary"]  # wierzch jak przed ETAPem 223
    meta = client.get(f"/dostepnosc/plik/{dane['plik']}").get_json()
    nazwy = [k["nazwa"] for k in meta["kolumny"]]
    assert "czas_szkola_min" in nazwy and "czas_przedszkole_min" in nazwy and meta["laczny_dostepny"]
    # raport drugiej usługi bierze jej obszary obsługi
    raport = client.get(f"/dostepnosc/raport?plik={dane['plik']}&kolumna=czas_przedszkole_min").get_data(as_text=True)
    assert "Obszary obsługi — przedszkole" in raport and "P 7" in raport and "SP 1" not in raport
    # łączenie wymaga każdej kolumny w pliku bazowym
    r = client.post("/dostepnosc/z-punktow", json={"usluga": "Szkoła", "punkty": [list(SRODEK)] * 2, "uslugi": ["", "basen"],
                                                   "baza": PRZYKLAD, "polacz": True})
    assert r.status_code == 400 and "czas_basen_min" in r.get_json()["blad"]


def test_plik_punktow_sprzed_etapu_223_dziala_w_raporcie():
    from dostepnosc.routes import grupa_kolumny
    stary = {"usluga": "x", "kolumna": "czas_x_min", "obszary": [{"nr": 1}]}
    assert grupa_kolumny(stary, "czas_x_min") is stary and grupa_kolumny(stary, "czas_y_min") is None and grupa_kolumny(None, "a") is None
