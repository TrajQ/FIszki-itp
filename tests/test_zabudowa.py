import json

import pytest

from app import create_app
from mpzp.zabudowa import BladDanych, Budynek, Ustalenia, policz

PLAN = Ustalenia(max_zabudowa_proc=30, min_intensywnosc=0.1, max_intensywnosc=0.6, min_pbc_proc=50, max_wysokosc_m=9, max_kondygnacje=2)


def test_wskazniki_dla_dwoch_budynkow():
    w = policz(1000, [Budynek(150, 2, 8.5), Budynek(50, 1, 4)], 500, PLAN)["wskazniki"]
    assert w["powierzchnia_zabudowy_m2"] == 200
    assert w["powierzchnia_calkowita_m2"] == 350
    assert w["zabudowa_proc"] == pytest.approx(20)
    assert w["intensywnosc"] == pytest.approx(0.35)
    assert w["pbc_proc"] == pytest.approx(50)
    assert w["max_kondygnacje"] == 2 and w["max_wysokosc_m"] == 8.5


def test_zgodnosc_wskazuje_przekroczenia():
    wynik = policz(1000, [Budynek(350, 3, 11)], 400, PLAN)
    niespelnione = {(z["parametr"], z["rodzaj"]) for z in wynik["zgodnosc"] if not z["spelnione"]}
    assert niespelnione == {
        ("Powierzchnia zabudowy", "max"),
        ("Intensywność zabudowy", "max"),
        ("Powierzchnia biologicznie czynna", "min"),
        ("Wysokość zabudowy", "max"),
        ("Liczba kondygnacji", "max"),
    }


def test_granica_rowna_limitowi_jest_spelniona():
    wynik = policz(1000, [Budynek(300, 2)], 500, Ustalenia(max_zabudowa_proc=30, max_intensywnosc=0.6, min_pbc_proc=50))
    assert all(z["spelnione"] for z in wynik["zgodnosc"])


def test_zapas_ogranicza_najostrzejszy_limit():
    # działka 1000, zabudowa 200, PBC 400; limit 30% → +100, min PBC 50% → +300; wygrywa 100
    zapas = policz(1000, [Budynek(200, 2)], 400, PLAN)["zapas"]
    assert zapas["rzut_m2"] == pytest.approx(100)
    assert zapas["powierzchnia_calkowita_m2"] == pytest.approx(200)  # 0,6 × 1000 − 400
    # przekroczony limit → zapas 0, nie ujemny
    assert policz(1000, [Budynek(400, 1)], 0, Ustalenia(max_zabudowa_proc=30))["zapas"]["rzut_m2"] == 0
    # bez ustaleń → brak limitu
    assert policz(1000, [Budynek(100, 1)], 0, Ustalenia())["zapas"] == {"rzut_m2": None, "powierzchnia_calkowita_m2": None}


def test_bledne_dane():
    with pytest.raises(BladDanych):
        policz(0, [], 0, Ustalenia())
    with pytest.raises(BladDanych, match="przekraczają"):
        policz(100, [Budynek(80, 1)], 50, Ustalenia())
    with pytest.raises(BladDanych):
        policz(100, [Budynek(-5, 1)], 0, Ustalenia())


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_endpoint_kalkulatora(client):
    strona = client.get("/mpzp/kalkulator?powierzchnia=812.4&dzialka=306401_1.0051.AR_18.14").get_data(as_text=True)
    assert 'value="812"' in strona and "306401_1.0051.AR_18.14" in strona

    dane = {
        "powierzchnia_dzialki": "1000",
        "pbc_m2": "400",
        "budynki": [{"rzut_m2": "200", "kondygnacje": "2", "wysokosc_m": ""}],
        "ustalenia": {"max_zabudowa_proc": "30", "max_intensywnosc": "0.6", "min_pbc_proc": "", "max_kondygnacje": "2"},
    }
    wynik = client.post("/mpzp/kalkulator/licz", data=json.dumps(dane), content_type="application/json").get_json()
    assert wynik["wskazniki"]["intensywnosc"] == pytest.approx(0.4)
    assert len(wynik["zgodnosc"]) == 3

    dane["powierzchnia_dzialki"] = "abc"
    zle = client.post("/mpzp/kalkulator/licz", data=json.dumps(dane), content_type="application/json")
    assert zle.status_code == 400 and "liczby" in zle.get_json()["blad"]
    dane["powierzchnia_dzialki"] = "100"
    zle = client.post("/mpzp/kalkulator/licz", data=json.dumps(dane), content_type="application/json")
    assert "przekraczają" in zle.get_json()["blad"]


def test_brak_kondygnacji_przy_rzucie_to_blad(client):
    dane = {"powierzchnia_dzialki": "1000", "pbc_m2": "", "budynki": [{"rzut_m2": "200", "kondygnacje": "", "wysokosc_m": ""}], "ustalenia": {}}
    odp = client.post("/mpzp/kalkulator/licz", data=json.dumps(dane), content_type="application/json")
    assert odp.status_code == 400 and "kondygnacji" in odp.get_json()["blad"]
