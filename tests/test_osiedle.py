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
    assert bilans(kolekcja()) == {"obszar_m2": None, "funkcje": [], "razem_m2": 0.0, "kontrole": {}, "wskazniki": None, "zgodnosc": [], "program": None, "koszty": None}


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

# ---------- ETAP 58: wskaźniki zabudowy i zgodność z planem ----------


def test_wskazniki_z_domyslnymi_i_wlasnymi_parametrami():
    b = bilans(
        kolekcja(
            prostokat(0, 0, 100, 100, "obszar"),  # 10 000 m²
            prostokat(0, 0, 40, 100, "MW"),  # 4000 m², domyślnie 30% × 5 kondygnacji, PBC 30%
            prostokat(40, 0, 20, 100, "MN", zabudowa_proc=25, kondygnacje=2, pbc_proc="60"),  # 2000 m²
            prostokat(60, 0, 30, 100, "ZP"),  # 3000 m², PBC 90%
        )
    )
    w = b["wskazniki"]
    # zabudowa: 4000·0,3 + 2000·0,25 = 1700; całkowita: 1200·5 + 500·2 = 7000
    assert w["powierzchnia_zabudowy_m2"] == pytest.approx(1700, rel=1e-3)
    assert w["powierzchnia_calkowita_m2"] == pytest.approx(7000, rel=1e-3)
    assert w["zabudowa_proc"] == pytest.approx(17.0, abs=0.1)
    assert w["intensywnosc"] == pytest.approx(0.70, abs=0.01)
    # PBC: 4000·0,3 + 2000·0,6 + 3000·0,9 = 5100 → 51%
    assert w["pbc_proc"] == pytest.approx(51.0, abs=0.1)
    assert w["max_kondygnacje"] == 5
    assert b["zgodnosc"] == [] and b["kontrole"]["parametry_ponad_100"] == 0


def test_zgodnosc_z_planem_i_teren_ponad_100_proc():
    b = bilans(
        kolekcja(prostokat(0, 0, 100, 100, "obszar"), prostokat(0, 0, 100, 100, "MW", zabudowa_proc=40, pbc_proc=70)),
        {"plan": {"max_zabudowa_proc": 35, "min_pbc_proc": 25, "max_intensywnosc": "0.5", "min_intensywnosc": None}},
    )
    wynik = {z["ustalenie"]: z["spelnione"] for z in b["zgodnosc"]}
    assert wynik == {"max_zabudowa_proc": False, "min_pbc_proc": True, "max_intensywnosc": False}
    assert b["kontrole"]["parametry_ponad_100"] == 1


@pytest.mark.parametrize(
    "wlasciwosci, ustawienia",
    [
        ({"zabudowa_proc": 120}, None),
        ({"kondygnacje": "dużo"}, None),
        ({"pbc_proc": float("nan")}, None),
        ({}, {"plan": {"max_zabudowa_proc": -1}}),
        ({}, {"plan": {"nieznane": 1}}),
        ({}, {"plan": {"min_intensywnosc": 2, "max_intensywnosc": 1}}),
    ],
)
def test_zle_parametry_i_ustalenia(wlasciwosci, ustawienia):
    with pytest.raises(BladKoncepcji):
        bilans(kolekcja(prostokat(0, 0, 10, 10, "MW", **wlasciwosci)), ustawienia)


def test_api_ustawienia_planu_walidowane_i_zapisane(client):
    k = client.post("/osiedle/koncepcje", json={"nazwa": "Plan"}).get_json()
    url = f"/osiedle/koncepcje/{k['id']}"
    client.put(url, json={"geojson": kolekcja(prostokat(0, 0, 100, 100, "obszar"), prostokat(0, 0, 50, 100, "MW"))})
    assert client.put(url, json={"ustawienia": {"plan": {"max_zabudowa_proc": "x"}}}).status_code == 400
    odp = client.put(url, json={"ustawienia": {"plan": {"max_zabudowa_proc": 10}}}).get_json()
    assert odp["ustawienia"]["plan"]["max_zabudowa_proc"] == 10
    assert odp["bilans"]["zgodnosc"][0]["spelnione"] is False  # 15% > 10%
    # zapis samego rysunku bierze ustalenia zapisane wcześniej
    odp = client.put(url, json={"geojson": kolekcja(prostokat(0, 0, 100, 100, "obszar"), prostokat(0, 0, 20, 100, "MW"))}).get_json()
    assert odp["bilans"]["zgodnosc"][0]["spelnione"] is True  # 6%
    assert client.get(url).get_json()["bilans"]["wskazniki"]["zabudowa_proc"] == pytest.approx(6.0, abs=0.1)


# ---------- ETAP 59: program osiedla ----------


def test_program_mieszkania_parkingi_dzieci():
    b = bilans(
        kolekcja(
            prostokat(0, 0, 100, 100, "obszar"),  # 1 ha
            prostokat(0, 0, 50, 100, "MW"),  # 5000 m² · 30% · 5 kond. = 7500 m² PC
            prostokat(50, 0, 20, 100, "MN"),  # 2000 m² · 30% · 2 = 1200 m² PC
            prostokat(70, 0, 10, 100, "U", kondygnacje=1),  # 1000 m² · 40% · 1 = 400 m² PC
            prostokat(80, 0, 10, 100, "KS"),  # 1000 m² / 25 = 40 miejsc
            prostokat(90, 0, 10, 100, "ZP"),
        )
    )
    p = b["program"]
    # MW: 7500 · 0,7 / 55 = 95,45 → 95; MN: 1200 · 0,7 / 120 = 7
    assert (p["mieszkania_mw"], p["mieszkania_mn"], p["mieszkania"]) == (95, 7, 102)
    assert p["mieszkancy"] == 245  # 102 · 2,4 = 244,8
    assert p["gestosc_os_na_ha"] == pytest.approx(245, abs=0.5)
    # 95 · 1,2 + 7 · 2 + 0,4 · 25 = 114 + 14 + 10 = 138
    assert p["miejsca_potrzebne"] == 138 and p["miejsca_na_terenach_ks"] == 40 and p["miejsca_brakuje"] == 98
    assert (p["dzieci_przedszkole"], p["oddzialy_przedszkolne"]) == (10, 1)  # 4% z 245 = 9,8
    assert (p["dzieci_szkola"], p["oddzialy_szkolne"]) == (22, 1)  # 9% z 245 = 22,05
    assert p["zielen_na_mieszkanca_m2"] == pytest.approx(1000 / 245, abs=0.05)


def test_program_z_wlasnymi_zalozeniami_i_bledy():
    rysunek = kolekcja(prostokat(0, 0, 100, 100, "MW"))  # 15 000 m² PC
    p = bilans(rysunek, {"program": {"metraz_mw_m2": 75, "udzial_mieszkan_proc": "", "osoby_na_mieszkanie": 2}})["program"]
    assert p["mieszkania"] == 140 and p["mieszkancy"] == 280  # 15 000 · 0,7 / 75
    assert p["gestosc_os_na_ha"] is None and p["zalozenia"]["metraz_mw_m2"] == 75
    for zle in ({"metraz_mw_m2": 0}, {"nieznane": 1}, {"osoby_na_mieszkanie": True}, {"dzieci_w_oddziale": "x"}):
        with pytest.raises(BladKoncepcji):
            bilans(rysunek, {"program": zle})
    with pytest.raises(BladKoncepcji):
        bilans(kolekcja(), {"program": {"metraz_mw_m2": -5}})


# ---------- ETAP 60: raport, szkic SVG, porównanie wariantów ----------


def test_szkic_svg_skala_i_bez_tekstu_uzytkownika():
    from osiedle.rysunek_svg import skala_dla, szkic_svg, zasieg_m

    maly = kolekcja(prostokat(0, 0, 100, 50, "obszar"), prostokat(0, 0, 50, 50, "MW"))
    duzy = kolekcja(prostokat(0, 0, 400, 200, "MN"))
    assert zasieg_m(maly) == pytest.approx((100, 50), rel=1e-3)
    skala = skala_dla([maly, duzy], 360, 260)
    assert skala == pytest.approx(400 / (360 - 48), rel=1e-3)  # większy decyduje
    svg = szkic_svg(maly, 360, 260, skala)
    assert svg.startswith("<svg") and "stroke-dasharray" in svg and "#ff9f0a" in svg
    assert " m</text>" in svg and ">N</text>" in svg
    assert "pusty rysunek" in szkic_svg(kolekcja())


def test_raport_svg_i_porownanie(client):
    ids = []
    for nazwa, szer in (("Wariant <A>", 50), ("Wariant B", 80)):
        k = client.post("/osiedle/koncepcje", json={"nazwa": nazwa}).get_json()
        client.put(f"/osiedle/koncepcje/{k['id']}", json={
            "geojson": kolekcja(prostokat(0, 0, 100, 100, "obszar"), prostokat(0, 0, szer, 100, "MW")),
            "ustawienia": {"plan": {"max_zabudowa_proc": 20}},
        })
        ids.append(k["id"])
    r = client.get(f"/osiedle/koncepcje/{ids[0]}/raport")
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Wariant &lt;A&gt;" in html and "<svg" in html and "Program osiedla" in html
    assert "✓ zgodne" in html  # 15% ≤ 20%
    # ETAP 115: ceny w okolicy obszaru opracowania (geometria obszaru, nie terenu MW)
    assert 'id="ceny-okolicy"' in html and "/ceny/okolica" in html and html.count('"type": "Polygon"') == 1
    bez_obszaru = client.post("/osiedle/koncepcje", json={"nazwa": "Bez obszaru"}).get_json()
    assert "const geometria = null;" in client.get(f"/osiedle/koncepcje/{bez_obszaru['id']}/raport").get_data(as_text=True)
    r = client.get(f"/osiedle/koncepcje/{ids[0]}.svg")
    assert r.mimetype == "image/svg+xml" and "attachment" in r.headers["Content-Disposition"]
    assert client.get("/osiedle/koncepcje/999/raport").status_code == 404

    html = client.get(f"/osiedle/porownanie?id={ids[0]}&id={ids[1]}&id=x&id=999").get_data(as_text=True)
    assert html.count("<svg") == 2 and "Wariant B" in html
    assert "1 z 1" in html and "0 z 1" in html  # B: 24% > 20%
    assert "Zaznacz co najmniej dwie" in client.get(f"/osiedle/porownanie?id={ids[0]}").get_data(as_text=True)


# ---------- ETAP 67: punkty z modułu Teren ----------


def test_projekt_terenu_w_ustawieniach(client):
    k = client.post("/osiedle/koncepcje", json={"nazwa": "Z terenem"}).get_json()
    url = f"/osiedle/koncepcje/{k['id']}"
    assert client.put(url, json={"ustawienia": {"teren_projekt": 3}}).get_json()["ustawienia"]["teren_projekt"] == 3
    assert client.put(url, json={"ustawienia": {"teren_projekt": None}}).status_code == 200
    for zle in ("3", True, 2.5):
        assert client.put(url, json={"ustawienia": {"teren_projekt": zle}}).status_code == 400
    client.post("/teren/projekty", data={"nazwa": "Zieleń", "wzor": "zielen"})
    assert client.get("/teren/projekty.json").get_json() == [{"id": 1, "nazwa": "Zieleń", "liczba_punktow": 0}]
    assert "/teren/projekty.json" in client.get("/osiedle/").get_data(as_text=True)


# ---------- ETAP 75: obszar z działek ewidencyjnych ----------


def test_obszar_z_dzialek(client, monkeypatch):
    from shapely.geometry import shape

    from dane.uldk import BladULDK, Dzialka
    from osiedle import routes as osiedle_routes

    dzialki = {
        "306401_1.0001.1": shape(prostokat(0, 0, 50, 100, "x")["geometry"]),
        "306401_1.0001.2": shape(prostokat(50, 0, 50, 100, "x")["geometry"]),
    }

    def znajdz(dzialka_id):
        if dzialka_id == "zly":
            raise ValueError("Zły format identyfikatora.")
        if dzialka_id == "awaria":
            raise BladULDK("ULDK nie odpowiada")
        return Dzialka(dzialka_id, dzialki[dzialka_id], "3064011") if dzialka_id in dzialki else None

    monkeypatch.setattr(osiedle_routes, "znajdz_dzialke_po_id", znajdz)
    k = client.post("/osiedle/koncepcje", json={"nazwa": "Z działek"}).get_json()
    url = f"/osiedle/koncepcje/{k['id']}"
    client.put(url, json={"geojson": kolekcja(prostokat(0, 0, 10, 10, "obszar"), prostokat(0, 0, 30, 100, "MW"))})

    odp = client.post(url + "/obszar-z-dzialek", json={"dzialki": ["306401_1.0001.1", " 306401_1.0001.2 ", "306401_1.0001.1"]}).get_json()
    assert odp["bilans"]["obszar_m2"] == pytest.approx(10_000, rel=1e-3)  # dwie przyległe działki, duplikat pominięty
    obszary = [c for c in odp["geojson"]["features"] if c["properties"]["funkcja"] == "obszar"]
    assert len(obszary) == 1 and obszary[0]["properties"]["dzialki"] == ["306401_1.0001.1", "306401_1.0001.2"]
    assert any(c["properties"]["funkcja"] == "MW" for c in odp["geojson"]["features"])  # tereny zostają

    assert client.post(url + "/obszar-z-dzialek", json={"dzialki": ["306401_1.0001.9"]}).status_code == 404
    assert client.post(url + "/obszar-z-dzialek", json={"dzialki": ["zly"]}).status_code == 400
    assert client.post(url + "/obszar-z-dzialek", json={"dzialki": ["awaria"]}).status_code == 502
    assert client.post(url + "/obszar-z-dzialek", json={"dzialki": []}).status_code == 400


# ---------- ETAP 138: obszar opracowania z pliku GeoJSON ----------


def _plik(dane, nazwa="granica.geojson"):
    import io
    import json
    tekst = dane if isinstance(dane, str) else json.dumps(dane)
    return {"plik": (io.BytesIO(tekst.encode()), nazwa)}


def test_obszar_z_pliku_geojson(client):
    from mpzp.uklady import pl1992, pl2000
    k = client.post("/osiedle/koncepcje", json={"nazwa": "Z pliku"}).get_json()
    url = f"/osiedle/koncepcje/{k['id']}/obszar-z-pliku"
    client.put(url.replace("/obszar-z-pliku", ""), json={"geojson": kolekcja(prostokat(0, 0, 30, 100, "MW"))})

    # WGS84, dwa przyległe wieloboki → jeden obszar 100 × 100 m; teren MW zostaje
    odp = client.post(url, data=_plik(kolekcja(prostokat(0, 0, 50, 100, "x"), prostokat(50, 0, 50, 100, "x"))), content_type="multipart/form-data")
    d = odp.get_json()
    assert odp.status_code == 200 and d["bilans"]["obszar_m2"] == pytest.approx(10_000, rel=1e-3)
    obszar = [c for c in d["geojson"]["features"] if c["properties"]["funkcja"] == "obszar"]
    assert len(obszar) == 1 and obszar[0]["properties"]["uklad_pliku"] == "WGS84" and obszar[0]["geometry"]["type"] == "Polygon"
    assert any(c["properties"]["funkcja"] == "MW" for c in d["geojson"]["features"])

    # PL-1992 bez „crs” (rozpoznany po liczbach): prostokąt 100 × 200 m w Krakowie;
    # osobna koncepcja — bilans liczy skalę z szerokości wszystkich terenów (MW leży na 52°N)
    url = f"/osiedle/koncepcje/{client.post('/osiedle/koncepcje', json={'nazwa': 'Kraków'}).get_json()['id']}/obszar-z-pliku"
    s = pl1992(50.06, 19.94)
    e, n = s["y"], s["x"]
    pierscien = [[e, n], [e + 100, n], [e + 100, n + 200], [e, n + 200], [e, n]]
    d = client.post(url, data=_plik({"type": "Polygon", "coordinates": [pierscien]}), content_type="multipart/form-data").get_json()
    assert d["bilans"]["obszar_m2"] == pytest.approx(20_000, rel=2e-3)  # zniekształcenie PL-1992 ok. 0,1%
    assert d["geojson"]["features"][0]["properties"]["uklad_pliku"] == "PL-1992"

    # PL-2000 z „crs” jak z QGIS
    s = pl2000(50.06, 19.94)
    e, n = s["y"], s["x"]
    plik = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::2178"}},
            "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[e, n], [e + 100, n], [e + 100, n + 100], [e, n + 100], [e, n]]]}}]}
    d = client.post(url, data=_plik(plik), content_type="multipart/form-data").get_json()
    assert d["bilans"]["obszar_m2"] == pytest.approx(10_000, rel=1e-3) and d["geojson"]["features"][0]["properties"]["uklad_pliku"] == "PL-2000"

    def blad(dane):
        odp = client.post(url, data=_plik(dane), content_type="multipart/form-data")
        assert odp.status_code == 400
        return odp.get_json()["blad"]

    assert "wieloboków" in blad(kolekcja({"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [17, 52]}}))
    assert "poza Polską" in blad({"type": "Polygon", "coordinates": [[[2, 48], [2.01, 48], [2.01, 48.01], [2, 48]]]})
    assert "EPSG:3857" in blad({**plik, "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::3857"}}})
    assert "Nie rozpoznaję" in blad({"type": "Polygon", "coordinates": [[[1e7, 1e7], [1e7 + 1, 1e7], [1e7, 1e7 + 1], [1e7, 1e7]]]})
    assert "JSON" in blad("to nie json")
    assert client.post(url, data={}, content_type="multipart/form-data").status_code == 400
    assert client.post("/osiedle/koncepcje/999/obszar-z-pliku", data=_plik(plik), content_type="multipart/form-data").status_code == 404


# ---------- ETAP 81: plan miejscowy pod rysunkiem ----------


def test_strona_osiedla_ma_nakladki_planow(client):
    html = client.get("/osiedle/").get_data(as_text=True)
    assert 'URL_WARSTWY_KRAJOWE = "/mpzp/warstwy-krajowe"' in html


# ---------- ETAP 94: odległości od granicy i cień ----------

from osiedle import cien  # noqa: E402


def test_polozenie_slonca():
    wys, az = cien.polozenie_slonca(52.0, 0.0, 12)
    assert wys == pytest.approx(38.0) and az == pytest.approx(180.0)  # równonoc: 90° − φ, na południu
    assert cien.polozenie_slonca(52.0, 23.44, 12)[0] == pytest.approx(61.44)
    rano, wieczor = cien.polozenie_slonca(52.0, 0.0, 9), cien.polozenie_slonca(52.0, 0.0, 15)
    assert rano[0] == pytest.approx(wieczor[0]) and 90 < rano[1] < 180 < wieczor[1] < 270  # symetria wokół południa


def test_cien_pada_na_polnoc_i_odleglosc_od_granicy():
    # blok MW 5 kondygnacji (15 m) w środku; MN 10 m na północ i 20 m na południe (cień w równonoc sięga ok. 19 m)
    geojson = kolekcja(
        prostokat(0, 0, 200, 200, "obszar"),
        prostokat(80, 80, 40, 40, "MW", kondygnacje=5),
        prostokat(80, 130, 40, 30, "MN"),
        prostokat(80, 10, 40, 50, "MN"),
        prostokat(0, 0, 30, 30, "U", kondygnacje=1),
    )
    w = cien.analiza(geojson, "rownonoc")
    mw = next(t for t in w["tereny"] if t["funkcja"] == "MW")
    assert mw["wysokosc_m"] == 15 and mw["cien_w_poludnie_m"] == pytest.approx(15 / 0.7813, abs=0.2)  # tg 38° ≈ 0,78
    assert mw["od_granicy_m"] == pytest.approx(80, abs=0.5)
    u = next(t for t in w["tereny"] if t["funkcja"] == "U")
    assert u["od_granicy_m"] == 0  # teren usług w narożniku obszaru
    zacienione = {z["nr"]: z for z in w["zacienione"]}
    assert 2 in zacienione and 3 not in zacienione  # (numery bez obszaru) cień bloku sięga MN od północy, nie od południa
    assert w["strefa"]["type"] in ("Polygon", "MultiPolygon")
    zima = cien.analiza(geojson, "zima")
    assert {z["nr"]: z for z in zima["zacienione"]}[2]["w_cieniu_m2"] > zacienione[2]["w_cieniu_m2"]  # zimą cień dłuższy
    with pytest.raises(cien.BladCienia):
        cien.analiza(geojson, "jesien")


def test_trasa_cienia(client):
    k = client.post("/osiedle/koncepcje", json={"nazwa": "Cień"}).get_json()
    client.put(f"/osiedle/koncepcje/{k['id']}", json={"geojson": kolekcja(prostokat(0, 0, 40, 40, "MW"), prostokat(0, 50, 40, 20, "ZP"))})
    w = client.get(f"/osiedle/koncepcje/{k['id']}/cien").get_json()
    assert w["tereny"][0]["od_granicy_m"] is None and w["zacienione"][0]["funkcja"] == "ZP"
    assert client.get(f"/osiedle/koncepcje/{k['id']}/cien?dzien=x").status_code == 400
    assert client.get("/osiedle/koncepcje/999/cien").status_code == 404


# ---------- ETAP 100: odległości i cień w raporcie ----------


def test_raport_z_cieniem(client):
    k = client.post("/osiedle/koncepcje", json={"nazwa": "Raport"}).get_json()
    client.put(f"/osiedle/koncepcje/{k['id']}", json={"geojson": kolekcja(
        prostokat(0, 0, 100, 100, "obszar"), prostokat(20, 20, 40, 30, "MW", kondygnacje=6), prostokat(20, 55, 40, 30, "MN"))})
    html = client.get(f"/osiedle/koncepcje/{k['id']}/raport").get_data(as_text=True)
    assert "Odległości i cień" in html and "Tereny w strefie możliwego cienia" in html
    assert 'stroke-dasharray="4 3"' in html and ">2</text>" in html  # strefa i numery terenów na szkicu
    zima = client.get(f"/osiedle/koncepcje/{k['id']}/raport?cien=zima").get_data(as_text=True)
    assert "przesilenie zimowe" in zima and 'value="zima" selected' in zima
    bez = client.get(f"/osiedle/koncepcje/{k['id']}/raport?cien=nie").get_data(as_text=True)
    assert "Tereny w strefie" not in bez and 'stroke-dasharray="4 3"' not in bez and "Pokaż odległości i cień" in bez
    # porównanie wariantów bez zmian: szkic bez numerów i cienia
    assert 'stroke-dasharray="4 3"' not in client.get(f"/osiedle/porownanie?id={k['id']}&id={k['id']}").get_data(as_text=True)


# ---------- ETAP 122: DXF ----------


def _pary_dxf(tekst):
    wiersze = tekst.split("\n")
    assert wiersze[-1] == ""  # plik kończy się nowym wierszem
    return list(zip(wiersze[0:-1:2], wiersze[1:-1:2]))


def test_dxf_koncepcji(client):
    from mpzp.uklady import pl2000
    k = client.post("/osiedle/koncepcje", json={"nazwa": "Wariant ąę"}).get_json()
    client.put(f"/osiedle/koncepcje/{k['id']}", json={"geojson": kolekcja(
        prostokat(0, 0, 100, 100, "obszar"), prostokat(10, 10, 40, 30, "MW", kondygnacje=5), prostokat(60, 10, 30, 30, "ZP"))})
    odp = client.get(f"/osiedle/koncepcje/{k['id']}.dxf")
    assert odp.status_code == 200 and odp.headers["X-Uklad-Wspolrzednych"] == "PL-2000 strefa 6 (EPSG:2177)"
    assert ".dxf" in odp.headers["Content-Disposition"]
    pary = _pary_dxf(odp.get_data(as_text=True))
    assert ("  1", "AC1009") in pary and pary[-1] == ("  0", "EOF")
    warstwy = [w for k_, w in pary if k_ == "  8"]
    assert {"OSIEDLE_OBSZAR", "OSIEDLE_MW", "OSIEDLE_ZP", "OSIEDLE_OPISY"} <= set(warstwy)
    assert [w for k_, w in pary if k_ == "  1"][1:] == ["MW 1", "ZP 2"]  # opisy: symbol i numer jak w raporcie
    # pierwszy wierzchołek obszaru = (17°E, 52°N) w PL-2000 strefie 6: X = wschód, Y = północ
    wzor = pl2000(52.0, 17.0)
    i = next(n for n, p in enumerate(pary) if p == ("  0", "VERTEX"))
    x, y = float(pary[i + 2][1]), float(pary[i + 3][1])
    assert x == pytest.approx(wzor["y"], abs=0.01) and y == pytest.approx(wzor["x"], abs=0.01)
    assert sum(1 for p in pary if p == ("  0", "VERTEX")) == 12  # trzy prostokąty po 4 wierzchołki (bez powtórzenia pierwszego)
    p92 = _pary_dxf(client.get(f"/osiedle/koncepcje/{k['id']}.dxf?uklad=pl1992").get_data(as_text=True))
    i = next(n for n, p in enumerate(p92) if p == ("  0", "VERTEX"))
    assert 300_000 < float(p92[i + 2][1]) < 900_000 and 100_000 < float(p92[i + 3][1]) < 800_000
    assert client.get(f"/osiedle/koncepcje/{k['id']}.dxf?uklad=wgs84").status_code == 400
    pusta = client.post("/osiedle/koncepcje", json={"nazwa": "Pusta"}).get_json()
    assert _pary_dxf(client.get(f"/osiedle/koncepcje/{pusta['id']}.dxf").get_data(as_text=True))[-1] == ("  0", "EOF")


def test_obszar_z_geojson_przypadki_brzegowe():
    """ETAP 144: formy pliku i błędy rozpoznawania układu (bez trasy)."""
    from mpzp.uklady import pl2000
    from osiedle.obszar_z_pliku import MAKS_OBIEKTOW, obszar_z_geojson

    kwadrat = prostokat(0, 0, 100, 100, "x")
    # pojedynczy Feature, crs CRS84 i EPSG:4326 → WGS84
    assert obszar_z_geojson(kwadrat)[1] == "WGS84"
    for nazwa in ("urn:ogc:def:crs:OGC:1.3:CRS84", "EPSG:4326"):
        assert obszar_z_geojson({**kolekcja(kwadrat), "crs": {"type": "name", "properties": {"name": nazwa}}})[1] == "WGS84"
    # MultiPolygon i wielobok z dziurą zostają powierzchnią
    multi = {"type": "MultiPolygon", "coordinates": [kwadrat["geometry"]["coordinates"], prostokat(200, 0, 50, 50, "x")["geometry"]["coordinates"]]}
    assert obszar_z_geojson(multi)[0].geom_type == "MultiPolygon"
    for zly, komunikat in [
        ([1, 2], "nie jest plik"),
        ({"type": "FeatureCollection", "features": "x"}, "nie jest plik"),
        (kolekcja(*[kwadrat] * (MAKS_OBIEKTOW + 1)), "Najwyżej"),
        ({"type": "Polygon", "coordinates": [[[1, 2]]]}, "Uszkodzona"),
        ({"type": "Polygon", "coordinates": []}, "puste"),
        # wschód 9 xxx xxx — strefa PL-2000 „9” nie istnieje
        ({"type": "Polygon", "crs": {"type": "name", "properties": {"name": "EPSG:2178"}},
          "coordinates": [[[9_400_000, 5_550_000], [9_400_100, 5_550_000], [9_400_100, 5_550_100], [9_400_000, 5_550_000]]]}, "strefy PL-2000"),
    ]:
        with pytest.raises(BladKoncepcji, match=komunikat):
            obszar_z_geojson(zly)
    # PL-2000 rozpoznany po liczbach (bez crs)
    s = pl2000(52.4, 16.9)
    e, n = s["y"], s["x"]
    assert obszar_z_geojson({"type": "Polygon", "coordinates": [[[e, n], [e + 50, n], [e + 50, n + 50], [e, n]]]})[1] == "PL-2000"


# ---------- ETAP 155: szacunek kosztów ----------


def test_koszty_koncepcji(client):
    # obszar 100 × 100 m; MW 50 × 40 m, zabudowa 30%, 5 kondygnacji → 3000 m² pow. całkowitej; KD 50 × 10 m; KS 20 × 10 m
    geo = kolekcja(prostokat(0, 0, 100, 100, "obszar"),
                   prostokat(0, 0, 50, 40, "MW", zabudowa_proc=30, kondygnacje=5),
                   prostokat(0, 40, 50, 10, "KD"), prostokat(0, 50, 20, 10, "KS"))
    assert bilans(geo)["koszty"] is None  # bez stawek nie ma szacunku
    b = bilans(geo, {"koszty": {"budowa_mw": 6000, "drogi_kd": 400, "miejsce_podziemne": 80000, "grunt": "", "zielen_zp": None}})
    k = b["koszty"]
    poz = {p["klucz"]: p for p in k["pozycje"]}
    assert list(poz) == ["budowa_mw", "drogi_kd", "miejsce_podziemne"]  # puste stawki pominięte, kolejność stała
    assert poz["budowa_mw"]["ilosc"] == pytest.approx(3000, rel=1e-3) and poz["budowa_mw"]["koszt"] == pytest.approx(18_000_000, rel=1e-3)
    assert poz["drogi_kd"]["koszt"] == pytest.approx(200_000, rel=1e-3)
    assert poz["miejsce_podziemne"]["ilosc"] == b["program"]["miejsca_brakuje"] > 0
    assert k["razem"] == sum(p["koszt"] for p in k["pozycje"])
    assert k["na_mieszkanie"] == round(k["razem"] / b["program"]["mieszkania"])
    assert k["na_m2_calkowitej"] == pytest.approx(k["razem"] / 3000, rel=1e-3)
    for zle in ({"koszty": {"budowa_mw": -1}}, {"koszty": {"nieznana": 1}}, {"koszty": {"grunt": True}}, {"koszty": [1]}):
        with pytest.raises(BladKoncepcji):
            bilans(geo, zle)
    # zapis przez trasę jak inne ustawienia
    k_id = client.post("/osiedle/koncepcje", json={"nazwa": "Koszty"}).get_json()["id"]
    odp = client.put(f"/osiedle/koncepcje/{k_id}", json={"geojson": geo, "ustawienia": {"koszty": {"budowa_mw": 6000}}}).get_json()
    assert odp["bilans"]["koszty"]["razem"] == pytest.approx(18_000_000, rel=1e-3)
    assert client.put(f"/osiedle/koncepcje/{k_id}", json={"ustawienia": {"koszty": {"budowa_mw": "dużo"}}}).status_code == 400


def test_koszty_w_raporcie_i_porownaniu(client):
    geo = kolekcja(prostokat(0, 0, 100, 100, "obszar"), prostokat(0, 0, 50, 40, "MW", zabudowa_proc=30, kondygnacje=5))
    ids = []
    for nazwa, stawka in [("A", 6000), ("B", None)]:
        k = client.post("/osiedle/koncepcje", json={"nazwa": nazwa}).get_json()["id"]
        client.put(f"/osiedle/koncepcje/{k}", json={"geojson": geo, "ustawienia": {"koszty": {"budowa_mw": stawka} if stawka else {}}})
        ids.append(k)
    raport = client.get(f"/osiedle/koncepcje/{ids[0]}/raport").get_data(as_text=True)
    assert "Szacunek kosztów" in raport and "budowa zabudowy wielorodzinnej MW" in raport and "koszty ze stawek autora" in raport
    assert "Szacunek kosztów" not in client.get(f"/osiedle/koncepcje/{ids[1]}/raport").get_data(as_text=True)
    por = client.get(f"/osiedle/porownanie?id={ids[0]}&id={ids[1]}").get_data(as_text=True)
    assert "Koszty (stawki z każdej koncepcji)" in por and "17 999" in por  # pole z geometrii — ok. 18 mln
