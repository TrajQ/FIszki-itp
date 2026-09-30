"""Moduł ceny: ceny mieszkań z GUS BDL dla powiatów (ETAP 103)."""

import pytest

from app import create_app
from ceny import analiza
from dane import bdl

WOJ = "011200000000"
KRAKOW = "011212161000"  # miasto na prawach powiatu (TERYT 1261)
WIELICKI = "011212119000"  # powiat ziemski (TERYT 1219)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(bdl, "wojewodztwa", lambda: [bdl.Jednostka(WOJ, "małopolskie", "12")])
    monkeypatch.setattr(bdl, "powiaty_wojewodztwa", lambda woj: [bdl.Jednostka(WIELICKI, "Powiat wielicki", "1219"), bdl.Jednostka(KRAKOW, "Powiat m. Kraków", "1261")])
    monkeypatch.setattr(bdl, "szukaj_zmiennych", lambda fraza, poziom=6: [bdl.Zmienna(633, f"Mediana cen za 1 m2 lokali mieszkalnych (poziom {poziom})", "zł")])
    monkeypatch.setattr(bdl, "pobierz_zmienna", lambda zid: bdl.Zmienna(zid, "Mediana cen za 1 m2 lokali mieszkalnych", "zł"))
    szeregi = {KRAKOW: [{"rok": r, "wartosc": 6000 + 500 * (r - 2015)} for r in range(2015, 2025)], WIELICKI: [{"rok": 2023, "wartosc": 7000.0}, {"rok": 2024, "wartosc": 7700.0}]}
    monkeypatch.setattr(bdl, "szereg_gminy", lambda zid, jid: szeregi.get(jid, []))
    monkeypatch.setattr(bdl, "wartosci_dla_powiatow", lambda zid, rok, woj: [
        bdl.Wartosc(KRAKOW, "1261", "Powiat m. Kraków", 10500.0), bdl.Wartosc(WIELICKI, "1219", "Powiat wielicki", 7700.0), bdl.Wartosc("011212111000", "1211", "Powiat inny", 7700.0)])
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_analiza():
    assert analiza.miasto_na_prawach_powiatu("1261") and not analiza.miasto_na_prawach_powiatu("1219")
    s = analiza.podsumuj([{"rok": 2014, "wartosc": 5000.0}, {"rok": 2019, "wartosc": 6000.0}, {"rok": 2023, "wartosc": 9000.0}, {"rok": 2024, "wartosc": 10000.0}])
    assert (s["rok"], s["wartosc"]) == (2024, 10000.0)
    assert s["rok_do_roku"]["zmiana_proc"] == pytest.approx(100 / 9, abs=1e-6)
    assert s["w_5_lat"]["od"] == 2019 and s["w_5_lat"]["zmiana"] == 4000
    assert s["od_poczatku"]["zmiana_proc"] == pytest.approx(100) and s["srednio_rocznie_proc"] == pytest.approx(100 * (2 ** 0.1 - 1))
    assert analiza.podsumuj([{"rok": 2024, "wartosc": 1.0}])["rok_do_roku"] is None and analiza.podsumuj([]) is None
    r = analiza.ranking([{"bdl_id": "a", "teryt": "1261", "nazwa": "A", "wartosc": 3.0}, {"bdl_id": "b", "teryt": "1219", "nazwa": "B", "wartosc": 5.0},
                         {"bdl_id": "c", "teryt": "1218", "nazwa": "C", "wartosc": 5.0}])
    assert [(p["nazwa"], p["miejsce"]) for p in r["pozycje"]] == [("B", 1), ("C", 1), ("A", 3)] and r["mediana"] == 5.0 and r["pozycje"][2]["miasto"]


def test_obieg_modulu(client):
    c = client
    assert "Nie wybrano" in c.get("/ceny/").get_data(as_text=True)
    assert c.get("/ceny/szereg/" + KRAKOW).status_code == 409  # najpierw wskaźnik
    assert c.get("/ceny/zmienne?q=mediana").get_json()[0]["nazwa"].endswith("(poziom 5)")  # szukamy dla powiatów
    assert c.put("/ceny/zmienna", json={"id": 633}).get_json()["jednostka"] == "zł"
    assert "Mediana cen za 1 m2" in c.get("/ceny/").get_data(as_text=True)
    assert "Wskaźnik: Mediana cen" in c.get("/").get_data(as_text=True)  # karta na stronie głównej
    powiaty = c.get(f"/ceny/powiaty/{WOJ}").get_json()
    assert [(p["nazwa"], p["miasto"]) for p in powiaty] == [("Powiat m. Kraków", True), ("Powiat wielicki", False)]
    s = c.get(f"/ceny/szereg/{KRAKOW}").get_json()
    assert s["podsumowanie"]["wartosc"] == 10500 and s["podsumowanie"]["w_5_lat"]["od"] == 2019
    r = c.get(f"/ceny/ranking?woj={WOJ}&rok=2024").get_json()
    assert r["pozycje"][0]["nazwa"] == "Powiat m. Kraków" and r["mediana"] == 7700.0 and r["liczba"] == 3
    csv = c.get(f"/ceny/porownanie.csv?id={KRAKOW}&nazwa=Kraków&id={WIELICKI}&nazwa=wielicki").get_data(as_text=True)
    assert csv.startswith("﻿rok;Kraków;wielicki") and "2023;10000;7000.0" in csv and "2015;6000;" in csv
    assert c.get("/ceny/szereg/123").status_code == 400
    assert c.get(f"/ceny/ranking?woj={WOJ}").status_code == 400
    assert c.get("/ceny/zmienne?q=a").status_code == 400


def test_klient_bdl_powiaty(monkeypatch):
    zapytania = []

    def pobierz(sciezka, parametry):
        zapytania.append((sciezka, parametry))
        if sciezka == "/units":
            return {"totalRecords": 1, "results": [{"id": KRAKOW, "name": "Powiat m. Kraków"}]}
        return {"totalRecords": 1, "results": [{"id": KRAKOW, "name": "Powiat m. Kraków", "values": [{"year": "2024", "val": 10500}]}]}

    monkeypatch.setattr(bdl, "_pobierz", pobierz)
    assert bdl.powiaty_wojewodztwa(WOJ)[0].teryt == "1261"
    assert bdl.wartosci_dla_powiatow(633, 2024, WOJ)[0].wartosc == 10500.0
    assert zapytania[0][1]["level"] == 5 and zapytania[1][1]["unit-level"] == 5
    assert bdl.teryt_powiatu("011212161011") == "1261"
