"""Moduł osiedle: bilans terenu i koncepcje (ETAP 57)."""

import pytest

from app import create_app
from osiedle.bilans import BladKoncepcji, bilans, metry_na_stopien

MX, MY = metry_na_stopien(52.0)


def prostokat(x0, y0, szer, wys, funkcja, **wlasciwosci):
    """Prostokąt w metrach od punktu (17°E, 52°N) jako obiekt GeoJSON."""
    def p(x, y):
        return [17 + x / MX, 52 + y / MY]

    pierscien = [p(x0, y0), p(x0 + szer, y0), p(x0 + szer, y0 + wys), p(x0, y0 + wys), p(x0, y0)]
    return {"type": "Feature", "properties": {"funkcja": funkcja, **wlasciwosci}, "geometry": {"type": "Polygon", "coordinates": [pierscien]}}


def kolekcja(*cechy):
    return {"type": "FeatureCollection", "features": list(cechy)}


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_bilans_z_obszarem_nakladaniem_i_wolnym_terenem():
    b = bilans(
        kolekcja(
            prostokat(0, 0, 100, 100, "obszar"),
            prostokat(0, 0, 50, 100, "MW"),
            prostokat(50, 0, 30, 100, "ZP"),
            prostokat(70, 0, 20, 100, "KD"),  # 10 m zachodzi na ZP
        )
    )
    assert b["obszar_m2"] == pytest.approx(10_000, rel=1e-3)
    assert [(f["funkcja"], f["procent"]) for f in b["funkcje"]] == [("MW", 50.0), ("ZP", 30.0), ("KD", 20.0)]
    k = b["kontrole"]
    assert k["nakladanie_m2"] == pytest.approx(1000, rel=1e-3)
    assert k["niezagospodarowane_m2"] == pytest.approx(1000, rel=1e-3) and k["niezagospodarowane_proc"] == pytest.approx(10, abs=0.1)
    assert k["poza_obszarem_m2"] == pytest.approx(0, abs=0.5)


def test_bilans_bez_obszaru_procent_od_sumy_i_pusty():
    b = bilans(kolekcja(prostokat(0, 0, 30, 10, "MN"), prostokat(40, 0, 10, 10, "ZP")))
    assert b["obszar_m2"] is None and [f["procent"] for f in b["funkcje"]] == [75.0, 25.0]
    assert bilans(kolekcja()) == {"obszar_m2": None, "funkcje": [], "razem_m2": 0.0, "kontrole": {}}


def test_teren_poza_obszarem():
    b = bilans(kolekcja(prostokat(0, 0, 10, 10, "obszar"), prostokat(20, 0, 10, 10, "U")))
    assert b["kontrole"]["poza_obszarem_m2"] == pytest.approx(100, rel=1e-3)


@pytest.mark.parametrize(
    "geojson",
    [
        {"type": "Feature"},
        kolekcja({"type": "Feature", "properties": {"funkcja": "MW"}, "geometry": {"type": "Point", "coordinates": [17, 52]}}),
        kolekcja(prostokat(0, 0, 10, 10, "XYZ")),
        kolekcja({"type": "Feature", "properties": {"funkcja": "MW"}, "geometry": {"type": "Polygon", "coordinates": "zle"}}),
        kolekcja(prostokat(0, 0, 10_000, 10_000, "obszar")),  # 100 km²
    ],
)
def test_zle_koncepcje(geojson):
    with pytest.raises(BladKoncepcji):
        bilans(geojson)


def test_koncepcje_przez_api(client):
    assert client.get("/osiedle/").status_code == 200
    assert client.post("/osiedle/koncepcje", json={"nazwa": "  "}).status_code == 400
    nowa = client.post("/osiedle/koncepcje", json={"nazwa": "Jeżyce — wariant A"}).get_json()
    assert nowa["geojson"]["features"] == []

    rysunek = kolekcja(prostokat(0, 0, 100, 100, "obszar"), prostokat(0, 0, 60, 100, "MW", kondygnacje=5))
    zapis = client.put(f"/osiedle/koncepcje/{nowa['id']}", json={"geojson": rysunek}).get_json()
    assert zapis["bilans"]["funkcje"][0]["procent"] == 60.0

    wczytana = client.get(f"/osiedle/koncepcje/{nowa['id']}").get_json()
    assert wczytana["geojson"]["features"][1]["properties"]["kondygnacje"] == 5  # właściwości zostają
    assert client.put(f"/osiedle/koncepcje/{nowa['id']}", json={"geojson": {"type": "zle"}}).status_code == 400
    assert client.get(f"/osiedle/koncepcje/{nowa['id']}").get_json()["bilans"]["funkcje"]  # zły zapis nic nie zepsuł

    client.put(f"/osiedle/koncepcje/{nowa['id']}", json={"nazwa": "wariant B"})
    assert client.get("/osiedle/koncepcje").get_json()[0]["nazwa"] == "wariant B"

    eksport = client.get(f"/osiedle/koncepcje/{nowa['id']}.geojson")
    assert "attachment" in eksport.headers["Content-Disposition"]
    assert eksport.get_json()["features"][1]["properties"]["nazwa_funkcji"] == "zabudowa mieszkaniowa wielorodzinna"

    assert client.delete(f"/osiedle/koncepcje/{nowa['id']}").status_code == 200
    assert client.get(f"/osiedle/koncepcje/{nowa['id']}").status_code == 404
    assert "Osiedle" in client.get("/").get_data(as_text=True)
