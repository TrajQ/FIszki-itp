import json

import pytest

from app import create_app
from mpzp import skala


def test_przeliczenia_dlugosci_i_powierzchni():
    assert skala.dlugosc_w_terenie(4, "cm", 1000) == pytest.approx(40)
    assert skala.dlugosc_w_terenie(15, "mm", 500) == pytest.approx(7.5)
    assert skala.dlugosc_na_rysunku(250, "m", 2000) == pytest.approx(125)
    assert skala.dlugosc_na_rysunku(1, "km", 10000) == pytest.approx(100)
    assert skala.powierzchnia_w_terenie(1, 1000) == pytest.approx(100)  # 1 cm² przy 1:1000 = 100 m²
    assert skala.powierzchnia_na_rysunku(1, "ha", 1000) == pytest.approx(100)
    assert skala.powierzchnia_na_rysunku(1, "km2", 10000) == pytest.approx(100)


def test_dobor_skali():
    d = skala.dobierz_skale(600, 400, "A3")
    assert d["mianownik"] == 2000 and d["orientacja"] == "pozioma"
    assert d["rysunek_mm"] == (pytest.approx(300), pytest.approx(200))
    # mały teren — najdokładniejsza skala z listy
    assert skala.dobierz_skale(50, 80, "A4")["mianownik"] == 500
    # za duży teren nawet na 1:100 000
    assert skala.dobierz_skale(500_000, 500_000, "A4")["mianownik"] is None


def test_bledy_skali():
    with pytest.raises(skala.BladSkali):
        skala.dlugosc_w_terenie(1, "cm", 0)
    with pytest.raises(skala.BladSkali):
        skala.dobierz_skale(-1, 5, "A4")
    with pytest.raises(skala.BladSkali):
        skala.dobierz_skale(10, 5, "A9")
    with pytest.raises(skala.BladSkali):
        skala.dobierz_skale(10, 5, "A4", margines_mm=200)


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_endpoint_skali(client):
    assert client.get("/mpzp/skala").status_code == 200
    dane = {"mianownik": "1 000", "dlugosc_rysunek": "4,5", "jednostka_rysunek": "cm", "pow_teren": "1", "jednostka_pow": "ha",
            "teren_szer_m": "600", "teren_wys_m": "400", "arkusz": "A3"}
    w = client.post("/mpzp/skala/licz", data=json.dumps(dane), content_type="application/json").get_json()
    assert w["dlugosc_teren_m"] == pytest.approx(45)
    assert w["pow_rysunek_cm2"] == pytest.approx(100)
    assert w["dobor"]["mianownik"] == 2000
    assert "dlugosc_rysunek_mm" not in w  # puste pole — nie liczymy

    for zle in [{"mianownik": ""}, {"mianownik": "abc"}, {"mianownik": "1000", "dlugosc_rysunek": "1", "jednostka_rysunek": "stopa"}]:
        assert client.post("/mpzp/skala/licz", data=json.dumps(zle), content_type="application/json").status_code == 400


def test_margines_zero_i_ujemny(client):
    baza = {"mianownik": "1000", "teren_szer_m": "280", "teren_wys_m": "190", "arkusz": "A4"}
    # 280 × 190 m przy 1:1000 = 280 × 190 mm — mieści się na A4 (297 × 210) tylko bez
    # marginesu; z marginesem 20 mm pole ma 257 × 170 mm, więc potrzeba 1:2000
    zero = client.post("/mpzp/skala/licz", data=json.dumps({**baza, "margines_mm": "0"}), content_type="application/json").get_json()
    assert zero["dobor"]["mianownik"] == 1000
    domyslny = client.post("/mpzp/skala/licz", data=json.dumps(baza), content_type="application/json").get_json()
    assert domyslny["dobor"]["mianownik"] == 2000
    ujemny = client.post("/mpzp/skala/licz", data=json.dumps({**baza, "margines_mm": "-50"}), content_type="application/json")
    assert ujemny.status_code == 400


@pytest.mark.parametrize("zla", ["nan", "inf", "1e400", "-inf"])
def test_liczby_nieskonczone_odrzucone(client, zla):
    odp = client.post("/mpzp/skala/licz", data=json.dumps({"mianownik": zla}), content_type="application/json")
    assert odp.status_code == 400 and odp.get_json()["blad"] == "Wpisz liczby (np. 4,5)."
    kalk = {"powierzchnia_dzialki": zla, "budynki": [], "ustalenia": {}}
    assert client.post("/mpzp/kalkulator/licz", data=json.dumps(kalk), content_type="application/json").status_code == 400
