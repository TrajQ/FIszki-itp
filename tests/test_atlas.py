import json
import os

import pytest
import requests

import atlas.routes as atlas_routes
from app import create_app
from atlas import granice, statystyki
from dane import bdl
from dane.gemini import BladGemini, liczby_w_tekscie, sprawdz_liczby

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


# ---------- dane/bdl.py ----------


class FalszywaOdpowiedz:
    def __init__(self, dane, status=200):
        self._dane = dane
        self.status_code = status

    def json(self):
        return self._dane

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_teryt_z_id_bdl():
    assert bdl.teryt_z_id_bdl("011212161011") == "1261011"  # Kraków
    assert bdl.teryt_z_id_bdl("071412865011") == "1465011"  # Warszawa
    assert bdl.teryt_z_id_bdl("011200000000") == "12"  # województwo małopolskie
    with pytest.raises(bdl.BladBDL):
        bdl.teryt_z_id_bdl("123")


def test_szukaj_zmiennych_sklada_nazwe_z_poziomow(monkeypatch):
    zapytania = []

    def falszywy_get(url, params, headers, timeout):
        zapytania.append((url, params))
        return FalszywaOdpowiedz(
            {"results": [{"id": 72305, "n1": "ogółem", "n2": "ludność", "n3": None, "measureUnitName": "osoba"}]}
        )

    monkeypatch.setattr(bdl.requests, "get", falszywy_get)
    wynik = bdl.szukaj_zmiennych("ludność")

    assert wynik == [bdl.Zmienna(id=72305, nazwa="ogółem — ludność", jednostka="osoba")]
    assert zapytania[0][0].endswith("/variables/search")
    assert zapytania[0][1]["level"] == 6


def test_wartosci_dla_gmin_stronicuje_i_pomija_braki_oraz_czesci_gmin(monkeypatch):
    strony = {
        0: {
            "totalRecords": 3,
            "results": [
                {"id": "011212161011", "name": "Kraków", "values": [{"year": "2023", "val": 804237}]},
                {"id": "011212106034", "name": "Wieliczka - miasto", "values": [{"year": "2023", "val": 1}]},
            ],
        },
        1: {
            "totalRecords": 3,
            "results": [{"id": "011212106032", "name": "Wieliczka", "values": [{"year": "2023", "val": None}]}],
        },
    }
    monkeypatch.setattr(bdl, "ROZMIAR_STRONY", 2)
    monkeypatch.setattr(
        bdl.requests, "get", lambda url, params, headers, timeout: FalszywaOdpowiedz(strony[params["page"]])
    )

    wynik = bdl.wartosci_dla_gmin(72305, 2023, "011200000000")

    assert wynik == [bdl.Wartosc(bdl_id="011212161011", teryt="1261011", nazwa="Kraków", wartosc=804237.0)]


def test_bledy_bdl(monkeypatch):
    monkeypatch.setattr(bdl.requests, "get", lambda *a, **k: FalszywaOdpowiedz({}, status=429))
    with pytest.raises(bdl.BladBDL, match="limit"):
        bdl.wojewodztwa()

    def zerwane(*a, **k):
        raise requests.ConnectionError("brak sieci")

    monkeypatch.setattr(bdl.requests, "get", zerwane)
    with pytest.raises(bdl.BladBDL, match="połączenia"):
        bdl.wojewodztwa()


# ---------- atlas/statystyki.py ----------

GMINY = [
    {"nazwa": "A", "wartosc": 10.0},
    {"nazwa": "B", "wartosc": 20.0},
    {"nazwa": "C", "wartosc": 30.0},
    {"nazwa": "D", "wartosc": 40.0},
    {"nazwa": "E", "wartosc": 1000.5},
]


def test_statystyki():
    s = statystyki.statystyki(GMINY)
    assert s["liczba_gmin"] == 5
    assert s["min"] == {"nazwa": "A", "wartosc": 10.0}
    assert s["max"] == {"nazwa": "E", "wartosc": 1000.5}
    assert s["mediana"] == 30.0
    assert [g["nazwa"] for g in s["najwyzsze"]] == ["E", "D", "C"]
    assert statystyki.statystyki([]) == {"liczba_gmin": 0}


def test_progi_klas_rosnace_i_wewnatrz_zakresu():
    progi = statystyki.progi_klas([float(x) for x in range(1, 101)])
    assert len(progi) == 4
    assert progi == sorted(progi)
    assert statystyki.progi_klas([5.0, 5.0, 5.0]) == []


def test_format_liczby_po_polsku():
    assert statystyki.format_liczby(804237) == "804 237"
    assert statystyki.format_liczby(1234.5) == "1 234,5"
    assert statystyki.format_liczby(2.5) == "2,5"
    assert statystyki.format_liczby(-3.14159) == "-3,14"


# ---------- strażnik liczb w opisie Gemini ----------


def test_straznik_przepuszcza_liczby_z_faktow():
    fakty = ["Rok: 2023", "Wartość najwyższa: Kraków — 804 237 osoba", "3 gminy o najwyższej wartości: ..."]
    sprawdz_liczby("W 2023 r. najwięcej osób mieszkało w Krakowie (804 237), a 3 gminy...", fakty)


def test_straznik_odrzuca_wymyslone_liczby():
    fakty = ["Rok: 2023", "Mediana: 12 345,5 osoba"]
    with pytest.raises(BladGemini, match="12345.6"):
        sprawdz_liczby("Mediana wynosi około 12 345,6 osoby.", fakty)
    with pytest.raises(BladGemini):
        sprawdz_liczby("To o 40% więcej niż w 2023.", fakty)


def test_liczby_w_tekscie_rozpoznaje_zapis_polski():
    assert liczby_w_tekscie("804 237 i 1 234,5 oraz 0,75") == {"804237", "1234.5", "0.75"}


# ---------- atlas/granice.py ----------


def test_granice_parsuja_gml_filtrujac_wojewodztwo_i_zamieniajac_osie(tmp_path, monkeypatch):
    with open(os.path.join(FIXTURES, "prg_gminy.xml"), encoding="utf-8") as plik:
        gml = plik.read()
    wywolania = []
    monkeypatch.setattr(granice, "_pobierz_gml", lambda teryt: wywolania.append(teryt) or gml)

    kolekcja = granice.granice_gmin("12", str(tmp_path))

    assert [c["properties"]["teryt"] for c in kolekcja["features"]] == ["1206032", "1261011"]
    krakow = kolekcja["features"][1]
    lon, lat = krakow["geometry"]["coordinates"][0][0]
    assert 19 < lon < 21 and 49 < lat < 51  # osie zamienione na (lon, lat)

    # Drugie wywołanie idzie z pliku cache, bez pobierania.
    granice.granice_gmin("12", str(tmp_path))
    assert wywolania == ["12"]


def test_granice_blad_serwisu(tmp_path, monkeypatch):
    monkeypatch.setattr(
        granice, "_pobierz_gml", lambda teryt: "<ows:ExceptionReport xmlns:ows='x'>zły filtr</ows:ExceptionReport>"
    )
    with pytest.raises(granice.BladGranic):
        granice.granice_gmin("12", str(tmp_path))


# ---------- endpointy ----------

WOJ = [{"bdl_id": "011200000000", "nazwa": "małopolskie", "teryt": "12"}]


@pytest.fixture
def client(tmp_path, monkeypatch):
    licznik = {"dane": 0}

    def wartosci(zmienna_id, rok, woj):
        licznik["dane"] += 1
        if rok == 2013:  # rok bazowy w testach porównania; Wieliczki brak
            return [bdl.Wartosc("011212161011", "1261011", "Kraków", 758334.0)]
        return [
            bdl.Wartosc("011212161011", "1261011", "Kraków", 804237.0),
            bdl.Wartosc("011212106032", "1206032", "Wieliczka", 63000.0),
        ]

    monkeypatch.setattr(atlas_routes.bdl, "wojewodztwa", lambda: [bdl.Jednostka(**w) for w in WOJ])
    monkeypatch.setattr(atlas_routes.bdl, "pobierz_zmienna", lambda i: bdl.Zmienna(i, "ludność ogółem", "osoba"))
    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_gmin", wartosci)
    monkeypatch.setattr(atlas_routes.bdl, "szukaj_zmiennych", lambda f: [bdl.Zmienna(72305, "ludność", "osoba")])

    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.licznik = licznik
        yield c


ZAPYTANIE = "zmienna=72305&rok=2023&woj=011200000000"


def test_strona_atlasu(client):
    assert client.get("/atlas/").status_code == 200


def test_zmienne(client):
    assert client.get("/atlas/zmienne?q=lu").status_code == 400
    assert client.get("/atlas/zmienne?q=ludność").get_json() == [
        {"id": 72305, "nazwa": "ludność", "jednostka": "osoba"}
    ]


def test_dane_z_statystykami_i_cache(client):
    dane = client.get(f"/atlas/dane?{ZAPYTANIE}").get_json()
    assert [g["nazwa"] for g in dane["gminy"]] == ["Kraków", "Wieliczka"]
    assert dane["statystyki"]["max"]["nazwa"] == "Kraków"
    assert dane["wojewodztwo"]["nazwa"] == "małopolskie"
    assert dane["zmienna"]["jednostka"] == "osoba"

    client.get(f"/atlas/dane?{ZAPYTANIE}")
    assert client.licznik["dane"] == 1  # drugie zapytanie z cache


@pytest.mark.parametrize(
    "zapytanie,status",
    [("zmienna=x&rok=2023&woj=011200000000", 400), ("zmienna=1&rok=2023&woj=12", 400), ("zmienna=1&rok=2023&woj=999999999999", 404)],
)
def test_dane_bledne_parametry(client, zapytanie, status):
    assert client.get(f"/atlas/dane?{zapytanie}").status_code == status


def test_dane_blad_bdl(client, monkeypatch):
    def blad(*a):
        raise bdl.BladBDL("BDL nie odpowiada")

    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_gmin", blad)
    odpowiedz = client.get(f"/atlas/dane?{ZAPYTANIE}")
    assert odpowiedz.status_code == 502
    assert odpowiedz.get_json()["blad"] == "BDL nie odpowiada"


def test_granice_endpoint(client, monkeypatch):
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda teryt, folder: {"type": "FeatureCollection", "features": []})
    assert client.get("/atlas/granice/12").status_code == 200
    assert client.get("/atlas/granice/1").status_code == 400


def test_opis_liczy_fakty_na_serwerze(client, monkeypatch):
    otrzymane = []

    def falszywy_opis(fakty):
        otrzymane.extend(fakty)
        return "Najwięcej mieszkańców ma Kraków (804 237 osoba)."

    monkeypatch.setattr(atlas_routes, "opisz_wskaznik", falszywy_opis)
    odpowiedz = client.post("/atlas/opis", data=json.dumps({"zmienna": 72305, "rok": 2023, "woj": "011200000000"}), content_type="application/json")

    assert odpowiedz.status_code == 200
    assert "Kraków — 804 237 osoba" in " ".join(otrzymane)
    assert odpowiedz.get_json()["opis"].startswith("Najwięcej")


def test_opis_blad_gemini_zwraca_fakty(client, monkeypatch):
    def blad(fakty):
        raise BladGemini("Opis odrzucony: model podał liczby, których nie ma w danych (42).")

    monkeypatch.setattr(atlas_routes, "opisz_wskaznik", blad)
    odpowiedz = client.post("/atlas/opis", data=json.dumps({"zmienna": 72305, "rok": 2023, "woj": "011200000000"}), content_type="application/json")

    assert odpowiedz.status_code == 502
    assert "fakty" in odpowiedz.get_json()



# ---------- ETAP 10: porównanie lat i eksport ----------


def test_porownaj_liczy_zmiane_i_pomija_braki():
    teraz = [
        {"teryt": "1", "nazwa": "A", "wartosc": 110.0},
        {"teryt": "2", "nazwa": "B", "wartosc": 90.0},
        {"teryt": "3", "nazwa": "C", "wartosc": 5.0},
        {"teryt": "4", "nazwa": "D", "wartosc": 7.0},
    ]
    wtedy = [
        {"teryt": "1", "nazwa": "A", "wartosc": 100.0},
        {"teryt": "2", "nazwa": "B", "wartosc": 100.0},
        {"teryt": "3", "nazwa": "C", "wartosc": 0.0},
    ]
    wynik = statystyki.porownaj(teraz, wtedy)

    assert [g["nazwa"] for g in wynik] == ["A", "B", "C"]  # D bez roku bazowego; C (0 → 5) na końcu
    assert wynik[0]["zmiana"] == 10.0 and wynik[0]["zmiana_proc"] == pytest.approx(10.0)
    assert wynik[1]["zmiana_proc"] == pytest.approx(-10.0)
    assert wynik[2]["zmiana_proc"] is None

    s = statystyki.statystyki_zmiany(wynik)
    assert (s["wzrosty"], s["spadki"], s["bez_zmian"]) == (2, 1, 0)
    assert s["najwiekszy_wzrost"]["nazwa"] == "A"
    assert s["najwiekszy_spadek"]["nazwa"] == "B"
    assert s["mediana_zmiany_proc"] == pytest.approx(0.0)


def test_fakty_zmiany_przechodza_przez_straznika():
    s = statystyki.statystyki_zmiany(
        statystyki.porownaj(
            [{"teryt": "1", "nazwa": "A", "wartosc": 112.5}, {"teryt": "2", "nazwa": "B", "wartosc": 95.0}],
            [{"teryt": "1", "nazwa": "A", "wartosc": 100.0}, {"teryt": "2", "nazwa": "B", "wartosc": 100.0}],
        )
    )
    fakty = statystyki.fakty_zmiany(2013, 2023, s)
    assert "Największy wzrost procentowy: A (12,5%)" in fakty
    sprawdz_liczby("Od 2013 do 2023 najbardziej wzrosła gmina A (12,5%), a spadła B (-5%).", fakty)


def test_dane_z_porownaniem(client):
    dane = client.get(f"/atlas/dane?{ZAPYTANIE}&rok_bazowy=2013").get_json()
    p = dane["porownanie"]
    assert p["rok_bazowy"] == 2013
    assert [g["nazwa"] for g in p["gminy"]] == ["Kraków"]
    assert p["gminy"][0]["zmiana"] == 804237.0 - 758334.0
    assert p["statystyki"]["wzrosty"] == 1
    assert p["progi_zmiany_proc"] == statystyki.PROGI_ZMIANY_PROC


@pytest.mark.parametrize("rok_bazowy", ["2023", "2030", "abc"])
def test_dane_zly_rok_bazowy(client, rok_bazowy):
    assert client.get(f"/atlas/dane?{ZAPYTANIE}&rok_bazowy={rok_bazowy}").status_code == 400


def test_eksport_csv_wartosci_i_porownania(client):
    import csv as csv_mod
    import io as io_mod

    odpowiedz = client.get(f"/atlas/eksport.csv?{ZAPYTANIE}")
    assert odpowiedz.mimetype == "text/csv"
    wiersze = list(csv_mod.reader(io_mod.StringIO(odpowiedz.data.decode("utf-8-sig"))))
    assert wiersze[0] == ["teryt", "gmina", "wartosc_2023"]
    assert wiersze[1] == ["1261011", "Kraków", "804237.0"]
    assert "atlas_72305_12_2023.csv" in odpowiedz.headers["Content-Disposition"]

    odpowiedz = client.get(f"/atlas/eksport.csv?{ZAPYTANIE}&rok_bazowy=2013")
    wiersze = list(csv_mod.reader(io_mod.StringIO(odpowiedz.data.decode("utf-8-sig"))))
    assert wiersze[0] == ["teryt", "gmina", "wartosc_2013", "wartosc_2023", "zmiana", "zmiana_proc"]
    assert wiersze[1][:2] == ["1261011", "Kraków"]
    assert float(wiersze[1][5]) == pytest.approx(round((804237 - 758334) / 758334 * 100, 2))

    assert client.get("/atlas/eksport.csv?zmienna=1").status_code == 400


def test_opis_z_porownaniem_dostaje_fakty_zmiany(client, monkeypatch):
    otrzymane = []
    monkeypatch.setattr(atlas_routes, "opisz_wskaznik", lambda fakty: otrzymane.extend(fakty) or "Opis.")
    client.post(
        "/atlas/opis",
        data=json.dumps({"zmienna": 72305, "rok": 2023, "woj": "011200000000", "rok_bazowy": 2013}),
        content_type="application/json",
    )
    assert "Porównanie z rokiem: 2013" in otrzymane


# ---------- ETAP 15: poprawki z przeglądu kodu ----------


def test_bez_spadkow_nie_ma_najwiekszego_spadku():
    teraz = [{"teryt": "1", "nazwa": "A", "wartosc": 110.0}, {"teryt": "2", "nazwa": "B", "wartosc": 101.0}]
    wtedy = [{"teryt": "1", "nazwa": "A", "wartosc": 100.0}, {"teryt": "2", "nazwa": "B", "wartosc": 100.0}]
    s = statystyki.statystyki_zmiany(statystyki.porownaj(teraz, wtedy))
    assert s["najwiekszy_wzrost"]["nazwa"] == "A"
    assert s["najwiekszy_spadek"] is None

    fakty = statystyki.fakty_zmiany(2013, 2023, s)
    assert not any("spadek procentowy" in f for f in fakty)
    assert any("wzrost procentowy: A" in f for f in fakty)


def test_pusty_wynik_bdl_nie_trafia_do_cache(client, monkeypatch):
    wywolania = []

    def pusto_potem_dane(zmienna_id, rok, woj):
        wywolania.append(rok)
        if len(wywolania) == 1:
            return []  # GUS jeszcze nie opublikował
        return [bdl.Wartosc("011212161011", "1261011", "Kraków", 1.0)]

    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_gmin", pusto_potem_dane)
    assert client.get(f"/atlas/dane?{ZAPYTANIE}").get_json()["gminy"] == []
    assert len(client.get(f"/atlas/dane?{ZAPYTANIE}").get_json()["gminy"]) == 1


# ---------- ETAP 19: profil gminy ----------


def test_szereg_gminy_parsuje_i_sortuje(monkeypatch):
    zapytania = []

    def falszywy_get(url, params, headers, timeout):
        zapytania.append((url, params))
        return FalszywaOdpowiedz(
            {
                "unitId": "011212161011",
                "results": [
                    {"id": 72305, "values": [{"year": "2021", "val": 780000}, {"year": "2019", "val": 779115}, {"year": "2020", "val": None}]},
                    {"id": 99, "values": [{"year": "2021", "val": 1}]},
                ],
            }
        )

    monkeypatch.setattr(bdl.requests, "get", falszywy_get)
    szereg = bdl.szereg_gminy(72305, "011212161011")

    assert szereg == [{"rok": 2019, "wartosc": 779115.0}, {"rok": 2021, "wartosc": 780000.0}]
    assert zapytania[0][0].endswith("/data/by-unit/011212161011")
    assert zapytania[0][1]["var-id"] == 72305


def test_zmiana_w_szeregu():
    assert statystyki.zmiana_w_szeregu([{"rok": 2010, "wartosc": 100.0}]) is None
    z = statystyki.zmiana_w_szeregu([{"rok": 2010, "wartosc": 100.0}, {"rok": 2020, "wartosc": 120.0}])
    assert z == {"od": 2010, "do": 2020, "zmiana": 20.0, "zmiana_proc": pytest.approx(20.0)}


def test_profil_gminy_endpoint_z_cache(client, monkeypatch):
    wywolania = []

    def szereg(zmienna, gmina):
        wywolania.append(gmina)
        return [{"rok": 2013, "wartosc": 758334.0}, {"rok": 2023, "wartosc": 804237.0}]

    monkeypatch.setattr(atlas_routes.bdl, "szereg_gminy", szereg)
    dane = client.get("/atlas/gmina/011212161011?zmienna=72305").get_json()
    assert len(dane["szereg"]) == 2
    assert dane["zmiana"]["od"] == 2013
    client.get("/atlas/gmina/011212161011?zmienna=72305")
    assert wywolania == ["011212161011"]

    assert client.get("/atlas/gmina/011212161011").status_code == 400
    assert client.get("/atlas/gmina/123?zmienna=1").status_code == 400


# ---------- ETAP 24: eksport GeoJSON ----------


def test_eksport_geojson_atlasu(client, monkeypatch):
    granica = {"type": "Polygon", "coordinates": [[[19.9, 50.0], [20.0, 50.0], [20.0, 50.1], [19.9, 50.0]]]}
    monkeypatch.setattr(
        atlas_routes.granice,
        "granice_gmin",
        lambda teryt, folder: {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"teryt": "1261011", "nazwa": "Kraków"}, "geometry": granica},
                {"type": "Feature", "properties": {"teryt": "1299999", "nazwa": "Bez danych"}, "geometry": granica},
            ],
        },
    )
    odp = client.get(f"/atlas/eksport.geojson?{ZAPYTANIE}&rok_bazowy=2013")
    assert odp.mimetype == "application/geo+json"
    cechy = json.loads(odp.data)["features"]
    krakow = cechy[0]["properties"]
    assert krakow["wartosc"] == 804237.0 and krakow["wartosc_bazowa"] == 758334.0
    assert krakow["jednostka"] == "osoba" and krakow["rok_bazowy"] == 2013
    assert cechy[1]["properties"]["wartosc"] is None  # gmina bez danych zostaje, z pustą wartością

    def blad(teryt, folder):
        raise atlas_routes.granice.BladGranic("PRG nie odpowiada")

    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", blad)
    assert client.get(f"/atlas/eksport.geojson?{ZAPYTANIE}").status_code == 502
