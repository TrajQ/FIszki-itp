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


GML_WOJEWODZTW = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:ms="http://mapserver.gis.umn.edu/mapserver">
  <wfs:member><ms:A01_Granice_wojewodztw gml:id="w1"><ms:msGeometry>
    <gml:Polygon gml:id="p1"><gml:exterior><gml:LinearRing>
      <gml:posList>49.2 19.0 49.2 21.4 50.5 21.4 50.5 19.0 49.2 19.0</gml:posList>
    </gml:LinearRing></gml:exterior></gml:Polygon></ms:msGeometry>
    <ms:JPT_KOD_JE>12</ms:JPT_KOD_JE><ms:JPT_NAZWA_>małopolskie</ms:JPT_NAZWA_>
  </ms:A01_Granice_wojewodztw></wfs:member>
  <wfs:member><ms:A01_Granice_wojewodztw gml:id="w2"><ms:msGeometry>
    <gml:Polygon gml:id="p2"><gml:exterior><gml:LinearRing>
      <gml:posList>49.4 21.4 49.4 23.5 50.8 23.5 50.8 21.4 49.4 21.4</gml:posList>
    </gml:LinearRing></gml:exterior></gml:Polygon></ms:msGeometry>
    <ms:JPT_KOD_JE>18</ms:JPT_KOD_JE><ms:JPT_NAZWA_>podkarpackie</ms:JPT_NAZWA_>
  </ms:A01_Granice_wojewodztw></wfs:member>
</wfs:FeatureCollection>"""


def test_granice_wojewodztw_bez_filtra_i_z_cache(tmp_path, monkeypatch):
    wywolania = []
    monkeypatch.setattr(granice, "_pobierz_gml_wojewodztw", lambda: wywolania.append(1) or GML_WOJEWODZTW)

    kolekcja = granice.granice_wojewodztw(str(tmp_path))

    assert [c["properties"]["teryt"] for c in kolekcja["features"]] == ["12", "18"]
    assert kolekcja["features"][1]["properties"]["nazwa"] == "podkarpackie"
    granice.granice_wojewodztw(str(tmp_path))
    assert wywolania == [1]  # drugie wywołanie z pliku


def test_granice_wojewodztw_pusta_odpowiedz_to_blad(tmp_path, monkeypatch):
    pusta = '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"/>'
    monkeypatch.setattr(granice, "_pobierz_gml_wojewodztw", lambda: pusta)
    with pytest.raises(granice.BladGranic):
        granice.granice_wojewodztw(str(tmp_path))
    assert not os.listdir(tmp_path)  # pustego wyniku nie zapisujemy


def test_tlo_wojewodztw_endpoint(client, monkeypatch):
    monkeypatch.setattr(atlas_routes.granice, "granice_wojewodztw", lambda folder: {"type": "FeatureCollection", "features": []})
    assert client.get("/atlas/tlo-wojewodztw").get_json()["type"] == "FeatureCollection"

    def blad(folder):
        raise granice.BladGranic("brak sieci")

    monkeypatch.setattr(atlas_routes.granice, "granice_wojewodztw", blad)
    odpowiedz = client.get("/atlas/tlo-wojewodztw")
    assert odpowiedz.status_code == 502 and odpowiedz.get_json()["blad"] == "brak sieci"


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


# ---------- ETAP 25: korelacja ----------


def _g(wartosci):
    return [{"teryt": str(i), "nazwa": f"G{i}", "wartosc": float(v)} for i, v in enumerate(wartosci)]


def test_korelacja_wartosci_podrecznikowe():
    k = statystyki.korelacja(_g([1, 2, 3, 4, 5]), _g([2, 4, 5, 4, 5]))
    assert k["pearson"] == pytest.approx(0.7746, abs=1e-4)
    assert k["r2"] == pytest.approx(0.6, abs=1e-4)
    assert k["regresja"] == {"nachylenie": pytest.approx(0.6), "wyraz_wolny": pytest.approx(2.2)}
    assert k["opis"] == "bardzo silna, dodatnia"


def test_spearman_odporny_na_wartosc_skrajna():
    # zależność monotoniczna, ale z jedną ogromną wartością
    k = statystyki.korelacja(_g([1, 2, 3, 4, 5, 6]), _g([1, 2, 3, 4, 5, 1000]))
    assert k["spearman"] == pytest.approx(1.0)
    assert k["pearson"] < 0.8


def test_rangi_z_remisami():
    assert statystyki._rangi([3, 1, 2, 2]) == [4.0, 1.0, 2.5, 2.5]


@pytest.mark.parametrize("r,opis", [(0.05, "brak związku"), (-0.2, "słaba, ujemna"), (0.45, "umiarkowana, dodatnia"), (-0.65, "silna, ujemna"), (None, "nie da się")])
def test_opis_sily(r, opis):
    assert statystyki.opis_sily(r).startswith(opis)


def test_korelacja_przypadki_brzegowe():
    assert statystyki.korelacja(_g([1, 2]), _g([3, 4]))["pearson"] is None  # za mało gmin
    stala = statystyki.korelacja(_g([1, 2, 3]), _g([5, 5, 5]))
    assert stala["pearson"] is None and "stały" in stala["opis"]
    # łączenie po TERYT — gminy spoza drugiego zestawu pominięte
    assert statystyki.korelacja(_g([1, 2, 3, 4]), _g([1, 2, 3]))["n"] == 3


def test_endpoint_korelacji(client, monkeypatch):
    def wartosci(zmienna_id, rok, woj):
        baza = [("011212161011", "1261011", "Kraków"), ("011212106032", "1206032", "Wieliczka"), ("011212101011", "1201011", "Bochnia")]
        v = [10, 20, 30] if zmienna_id == 72305 else [1, 3, 2]
        return [bdl.Wartosc(b, t, n, float(x)) for (b, t, n), x in zip(baza, v)]

    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_gmin", wartosci)
    dane = client.get(f"/atlas/korelacja?{ZAPYTANIE}&zmienna2=60559").get_json()
    assert dane["n"] == 3 and dane["pearson"] == pytest.approx(0.5)
    assert dane["zmienna_y"]["id"] == 60559
    assert client.get(f"/atlas/korelacja?{ZAPYTANIE}").status_code == 400
    assert client.get(f"/atlas/korelacja?{ZAPYTANIE}&zmienna2=72305").status_code == 400


def test_korelacja_czytelny_blad_bez_zmienna2(client):
    odp = client.get(f"/atlas/korelacja?{ZAPYTANIE}&zmienna2=abc")
    assert odp.status_code == 400 and odp.get_json()["blad"] == "Wymagany parametr zmienna2 (liczba)."


# ---------- ETAP 28: miary zróżnicowania i histogram ----------


def test_gini_wartosci_wzorcowe():
    assert statystyki.gini([5, 5, 5, 5]) == pytest.approx(0)
    assert statystyki.gini([0, 0, 0, 10]) == pytest.approx(0.75)  # maksimum dla n=4: (n−1)/n
    assert statystyki.gini([1, 2, 3, 4]) == pytest.approx(0.25)


def test_zroznicowanie():
    z = statystyki.zroznicowanie([2, 4, 4, 4, 5, 5, 7, 9])
    assert z["odchylenie_std"] == pytest.approx(2.0)  # klasyczny przykład: σ = 2
    assert z["wspolczynnik_zmiennosci"] == pytest.approx(40.0)
    assert z["ocena_zmiennosci"] == "przeciętne"
    assert z["max_do_min"] == pytest.approx(4.5)
    assert z["q1"] <= z["q3"]


def test_zroznicowanie_przypadki_brzegowe():
    z = statystyki.zroznicowanie([-5, 5, 10])  # ujemne: bez Giniego i max/min
    assert "gini" not in z and "max_do_min" not in z
    assert "wspolczynnik_zmiennosci" not in statystyki.zroznicowanie([-1, 1])  # średnia 0
    assert statystyki.zroznicowanie([3])["odchylenie_std"] == 0


def test_histogram_przedzialy():
    h = statystyki.histogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], przedzialy=5)
    assert [p["liczba"] for p in h] == [2, 2, 2, 2, 3]  # maksimum w ostatnim, domkniętym przedziale
    assert h[0]["od"] == 0 and h[-1]["do"] == 10
    assert statystyki.histogram([7, 7, 7]) == [{"od": 7, "do": 7, "liczba": 3}]


def test_fakty_opisu_zawieraja_cv_i_gini():
    stat = statystyki.statystyki(GMINY)
    fakty = statystyki.fakty_do_opisu({"nazwa": "x", "jednostka": "osoba"}, 2023, "małopolskie", stat)
    assert any(f.startswith("Współczynnik zmienności") for f in fakty)
    assert any(f.startswith("Współczynnik Giniego") for f in fakty)


# ---------- ETAP 29: wskaźniki względne ----------


def test_podziel_na_1000_i_pomija_zero():
    licznik = [{"teryt": "1", "nazwa": "A", "wartosc": 50.0}, {"teryt": "2", "nazwa": "B", "wartosc": 5.0}, {"teryt": "3", "nazwa": "C", "wartosc": 1.0}]
    mian = [{"teryt": "1", "wartosc": 10000.0}, {"teryt": "2", "wartosc": 0.0}]
    wynik = statystyki.podziel(licznik, mian, 1000)
    assert wynik == [{"teryt": "1", "nazwa": "A", "wartosc": 5.0}]


def test_podziel_szeregi_po_roku():
    s = statystyki.podziel_szeregi(
        [{"rok": 2020, "wartosc": 10.0}, {"rok": 2021, "wartosc": 12.0}, {"rok": 2022, "wartosc": 9.0}],
        [{"rok": 2020, "wartosc": 1000.0}, {"rok": 2021, "wartosc": 1200.0}],
        100,
    )
    assert s == [{"rok": 2020, "wartosc": 1.0}, {"rok": 2021, "wartosc": 1.0}]


def test_dane_ze_wskaznikiem_wzglednym(client, monkeypatch):
    def wartosci(zmienna_id, rok, woj):
        if zmienna_id == 1000:  # mianownik: ludność
            return [bdl.Wartosc("011212161011", "1261011", "Kraków", 800000.0), bdl.Wartosc("011212106032", "1206032", "Wieliczka", 60000.0)]
        return [bdl.Wartosc("011212161011", "1261011", "Kraków", 4000.0), bdl.Wartosc("011212106032", "1206032", "Wieliczka", 600.0)]

    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_gmin", wartosci)
    dane = client.get(f"/atlas/dane?{ZAPYTANIE}&mianownik=1000&mnoznik=1000").get_json()
    wartosci_gmin = {g["nazwa"]: g["wartosc"] for g in dane["gminy"]}
    assert wartosci_gmin == {"Kraków": pytest.approx(5.0), "Wieliczka": pytest.approx(10.0)}
    assert [g["nazwa"] for g in dane["gminy"]] == ["Wieliczka", "Kraków"]  # ranking po wartości względnej
    assert "na 1 000" in dane["zmienna"]["nazwa"] and dane["zmienna"]["mnoznik"] == 1000
    assert dane["zmienna"]["jednostka"] == "osoba / 1 000 osoba"
    # ETAP 153: iloraz lokalizacji z sum (4600 / 860 000), nie ze średniej wskaźników
    lq = {g["teryt"]: g["lq"] for g in dane["lq"]["gminy"]}
    assert dane["lq"]["udzial_wojewodztwa"] == pytest.approx(4600 / 860000)
    assert lq["1261011"] == pytest.approx(0.005 / (4600 / 860000)) and lq["1206032"] == pytest.approx(0.01 / (4600 / 860000))
    assert "lq" not in client.get(f"/atlas/dane?{ZAPYTANIE}").get_json()
    # mapa LQ do druku
    cechy = [{"type": "Feature", "properties": {"teryt": t, "nazwa": t},
              "geometry": {"type": "Polygon", "coordinates": [[[19 + i, 50], [20 + i, 50], [20 + i, 51], [19 + i, 51], [19 + i, 50]]]}}
             for i, t in enumerate(["1261011", "1206032"])]
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda teryt, folder: {"type": "FeatureCollection", "features": cechy})
    svg = client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&mianownik=1000&mnoznik=1000&tryb=lq").get_data(as_text=True)
    assert "Iloraz lokalizacji, gminy" in svg and "jak w województwie (0,8–1,2)" in svg and "(5,35)" in svg
    assert client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&tryb=lq").status_code == 400  # bez mianownika

    # korelacja i opis też używają wartości względnych
    kor = client.get(f"/atlas/korelacja?{ZAPYTANIE}&zmienna2=2000&mianownik=1000&mnoznik=1000").get_json()
    assert sorted(p["x"] for p in kor["punkty"]) == [pytest.approx(5.0), pytest.approx(10.0)]


@pytest.mark.parametrize("zapytanie", ["&mianownik=72305", "&mianownik=1000&mnoznik=7", "&mianownik=abc"])
def test_zle_parametry_wzgledne(client, zapytanie):
    assert client.get(f"/atlas/dane?{ZAPYTANIE}{zapytanie}").status_code == 400


def test_profil_gminy_wzgledny(client, monkeypatch):
    def szereg(zmienna, gmina):
        if zmienna == 1000:
            return [{"rok": 2020, "wartosc": 1000.0}, {"rok": 2021, "wartosc": 2000.0}]
        return [{"rok": 2020, "wartosc": 10.0}, {"rok": 2021, "wartosc": 10.0}]

    monkeypatch.setattr(atlas_routes.bdl, "szereg_gminy", szereg)
    dane = client.get("/atlas/gmina/011212161011?zmienna=72305&mianownik=1000&mnoznik=1000").get_json()
    assert [p["wartosc"] for p in dane["szereg"]] == [pytest.approx(10.0), pytest.approx(5.0)]


# ---------- ETAP 40: metody klasyfikacji ----------

TRZY_SKUPISKA = [1.0, 2.0, 3.0, 10.0, 11.0, 12.0, 20.0, 21.0, 22.0]


def test_jenks_znajduje_naturalne_skupiska():
    assert statystyki.progi_jenks(TRZY_SKUPISKA, 3) == [3.0, 12.0]


def test_jenks_ma_najwyzsze_gvf():
    import random

    random.seed(7)
    liczby = [random.lognormvariate(9, 0.8) for _ in range(150)]
    gvf = {m: statystyki.klasyfikuj(liczby, m, 5)["gvf"] for m in statystyki.METODY_KLASYFIKACJI}
    assert gvf["jenks"] == max(gvf.values())
    assert 0 < gvf["kwantyle"] < 1


def test_rowne_przedzialy_i_odchylenie():
    assert statystyki.progi_rowne([0.0, 10.0, 100.0], 4) == [25.0, 50.0, 75.0]
    liczby = [float(x) for x in range(1, 101)]  # średnia 50,5, σ ≈ 28,87
    progi = statystyki.progi_odchylenia(liczby, 4)
    assert progi == pytest.approx([50.5 - 28.866, 50.5, 50.5 + 28.866], abs=0.01)
    # 7 klas: granice ±2,5σ wypadają poza zakres — zostają tylko wewnętrzne
    assert len(statystyki.progi_odchylenia(liczby, 7)) == 4


def test_klasyfikuj_liczebnosci_i_bledy():
    wynik = statystyki.klasyfikuj(TRZY_SKUPISKA, "jenks", 3)
    assert wynik["liczebnosci"] == [3, 3, 3]
    assert wynik["gvf"] == pytest.approx(1 - 6 / sum((v - 34 / 3) ** 2 for v in TRZY_SKUPISKA))
    assert statystyki.klasyfikuj([5.0, 5.0], "jenks", 3)["progi"] == []
    with pytest.raises(ValueError):
        statystyki.klasyfikuj(TRZY_SKUPISKA, "magia", 3)
    with pytest.raises(ValueError):
        statystyki.klasyfikuj(TRZY_SKUPISKA, "jenks", 9)


def test_dane_i_klasy_z_metoda(client):
    dane = client.get(f"/atlas/dane?{ZAPYTANIE}&metoda=rowne&klasy=3").get_json()
    assert dane["klasyfikacja"]["metoda"] == "rowne" and dane["klasyfikacja"]["klasy"] == 3
    assert sum(dane["klasyfikacja"]["liczebnosci"]) == len(dane["gminy"])

    klasy = client.get(f"/atlas/klasy?{ZAPYTANIE}&metoda=jenks&klasy=4").get_json()
    assert klasy["metoda"] == "jenks"
    assert client.licznik["dane"] == 1  # /klasy korzysta z cache BDL

    assert client.get(f"/atlas/klasy?{ZAPYTANIE}&metoda=x").status_code == 400
    assert client.get(f"/atlas/dane?{ZAPYTANIE}&klasy=2").status_code == 400


# ---------- ETAP 41: autokorelacja przestrzenna ----------

from atlas import autokorelacja  # noqa: E402


def _siatka(n=6):
    """n×n kwadratowych „gmin” z wartością rosnącą na wschód (skupiska)."""
    cechy, wartosci = [], {}
    for i in range(n):
        for j in range(n):
            teryt = f"12{i:02d}{j:02d}1"
            cechy.append(
                {
                    "type": "Feature",
                    "properties": {"teryt": teryt, "nazwa": teryt},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[20 + i * 0.1, 50 + j * 0.1], [20.1 + i * 0.1, 50 + j * 0.1], [20.1 + i * 0.1, 50.1 + j * 0.1], [20 + i * 0.1, 50.1 + j * 0.1], [20 + i * 0.1, 50 + j * 0.1]]],
                    },
                }
            )
            wartosci[teryt] = float(i)
    return {"type": "FeatureCollection", "features": cechy}, wartosci


def test_sasiedztwo_queen_z_tolerancja_szczelin():
    kolekcja, _ = _siatka(3)
    # szczelina 50 m między kolumnami (jak po uproszczeniu granic) nie przerywa sąsiedztwa
    for cecha in kolekcja["features"]:
        pierscien = cecha["geometry"]["coordinates"][0]
        cecha["geometry"]["coordinates"][0] = [[x + 0.0002, y] if x > 20.05 else [x, y] for x, y in pierscien]
    s = autokorelacja.sasiedzi(kolekcja)
    assert len(s["1201011"]) == 8  # środek siatki 3×3
    assert len(s["1200001"]) == 3  # narożnik


def test_moran_dodatni_dla_trendu_i_zgodny_z_pysal():
    kolekcja, wartosci = _siatka(6)
    wynik = autokorelacja.analiza(wartosci, autokorelacja.sasiedzi(kolekcja))
    # wartość wzorcowa policzona raz biblioteką PySAL (esda.Moran), wagi queen, standaryzacja wierszami
    assert wynik["moran_i"] == pytest.approx(0.822222, abs=1e-5)
    assert wynik["p"] == 0.001 and wynik["oczekiwane_i"] == pytest.approx(-1 / 35)
    assert wynik["interpretacja"].startswith("Dodatnia")
    kategorie = {l["teryt"]: l["kategoria"] for l in wynik["lisa"]}
    assert kategorie["1205021"] == "HH" and kategorie["1200021"] == "LL"


def test_szachownica_daje_ujemna_autokorelacje():
    kolekcja, _ = _siatka(6)
    wartosci = {c["properties"]["teryt"]: float((int(c["properties"]["teryt"][2:4]) + int(c["properties"]["teryt"][4:6])) % 2) for c in kolekcja["features"]}
    sasiedzi = autokorelacja.sasiedzi(kolekcja)
    # przy sąsiedztwie queen szachownica też daje I poniżej oczekiwanego
    wynik = autokorelacja.analiza(wartosci, sasiedzi)
    assert wynik["moran_i"] < wynik["oczekiwane_i"]


def test_autokorelacja_bledy_i_wyspy():
    kolekcja, wartosci = _siatka(2)
    with pytest.raises(ValueError):
        autokorelacja.analiza(wartosci, autokorelacja.sasiedzi(kolekcja))  # 4 gminy to za mało
    kolekcja, wartosci = _siatka(4)
    wartosci["9999999"] = 5.0  # gmina bez granic = wyspa
    wynik = autokorelacja.analiza(wartosci, autokorelacja.sasiedzi(kolekcja))
    assert wynik["pominiete"] == 1 and wynik["liczba_gmin"] == 16
    with pytest.raises(ValueError):
        autokorelacja.analiza({t: 1.0 for t in wartosci}, autokorelacja.sasiedzi(kolekcja))


def test_endpoint_autokorelacji(client, monkeypatch):
    kolekcja, _ = _siatka(2)
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda teryt, folder: kolekcja)
    atlas_routes._sasiedzi_wojewodztw.clear()
    # dane testowe mają 2 gminy — za mało: czytelny błąd 422
    odpowiedz = client.get(f"/atlas/autokorelacja?{ZAPYTANIE}")
    assert odpowiedz.status_code == 422 and "Za mało" in odpowiedz.get_json()["blad"]
    assert client.get("/atlas/autokorelacja?zmienna=x").status_code == 400
    atlas_routes._sasiedzi_wojewodztw.clear()


# ---------- ETAP 42: mapa do druku ----------

from atlas import mapa_svg  # noqa: E402


def test_autokorelacja_nie_zalezy_od_kolejnosci_danych():
    kolekcja, wartosci = _siatka(5)
    sasiedzi = autokorelacja.sasiedzi(kolekcja)
    odwrotnie = dict(reversed(list(wartosci.items())))
    a, b = autokorelacja.analiza(wartosci, sasiedzi), autokorelacja.analiza(odwrotnie, sasiedzi)
    assert a["p"] == b["p"] and a["lisa"] == b["lisa"]


def test_podzialka_ladna_dlugosc():
    assert mapa_svg.dlugosc_podzialki_km(0.5) == 50  # 50 km = 100 px ≤ 180 px
    assert mapa_svg.dlugosc_podzialki_km(0.1) == 10
    assert mapa_svg.dlugosc_podzialki_km(10) == 200  # mała skala: najdłuższa z listy
    assert mapa_svg.dlugosc_podzialki_km(0.001) == 1  # nic się nie mieści: najkrótsza


def test_kartogram_svg_ma_elementy_mapy():
    kolekcja, _ = _siatka(2)
    svg = mapa_svg.kartogram_svg(
        kolekcja, {"1200001": "#ff0000"}, "Tytuł <&>", "Podtytuł", [("#ff0000", "0 – 10", 1)], "osoba", ["Źródło: GUS"]
    )
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "Tytuł &lt;&amp;&gt;" in svg  # znaki specjalne escapowane
    assert svg.count("<path") == 4 and 'fill="#ff0000"' in svg and mapa_svg.KOLOR_BRAK in svg
    assert " km</text>" in svg and ">N</text>" in svg and "Źródło: GUS" in svg


def test_endpoint_mapy_do_druku(client, monkeypatch):
    cechy = [
        {"type": "Feature", "properties": {"teryt": t, "nazwa": n},
         "geometry": {"type": "Polygon", "coordinates": [[[19 + i, 50], [20 + i, 50], [20 + i, 51], [19 + i, 51], [19 + i, 50]]]}}
        for i, (t, n) in enumerate([("1261011", "Kraków"), ("1206032", "Wieliczka")])
    ]
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda teryt, folder: {"type": "FeatureCollection", "features": cechy})

    odpowiedz = client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&metoda=rowne&klasy=3")
    assert odpowiedz.status_code == 200 and odpowiedz.mimetype == "image/svg+xml"
    svg = odpowiedz.get_data(as_text=True)
    assert "małopolskie" in svg and "równe przedziały" in svg

    pobranie = client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&pobierz=1")
    assert "attachment" in pobranie.headers["Content-Disposition"]
    assert client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&tryb=zmiana").status_code == 400  # bez roku bazowego
    assert client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&tryb=cos").status_code == 400
    # ETAP 144: mapa zmiany i klastrów LISA do druku
    zmiana = client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&tryb=zmiana&rok_bazowy=2013")
    assert zmiana.status_code == 200
    svg = zmiana.get_data(as_text=True)
    assert "Zmiana 2013–2023" in svg and "Zmiana wartości" in svg and "%" in svg
    lisa = client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&tryb=lisa")  # dwie gminy to za mało na autokorelację
    assert lisa.status_code == 400 and "co najmniej 5" in lisa.get_json()["blad"]
    strona = client.get(f"/atlas/druk?{ZAPYTANIE}&tryb=wartosc").get_data(as_text=True)
    assert "Pobierz SVG" in strona and "mapa.svg?" in strona


def test_mapa_lisa_do_druku(client, monkeypatch):
    """ETAP 144: kartogram klastrów LISA — siatka 3 × 3 gmin, bogaty róg."""
    siatka = [(f"12{i:02d}011", i % 3, i // 3) for i in range(9)]
    cechy = [{"type": "Feature", "properties": {"teryt": t, "nazwa": f"Gmina {t}"},
              "geometry": {"type": "Polygon", "coordinates": [[[19 + x, 50 + y], [20 + x, 50 + y], [20 + x, 51 + y], [19 + x, 51 + y], [19 + x, 50 + y]]]}}
             for t, x, y in siatka]
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda teryt, folder: {"type": "FeatureCollection", "features": cechy})
    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_gmin", lambda z, rok, woj: [
        bdl.Wartosc(f"0112{t}", t, f"Gmina {t}", float(100 - 10 * (x + y))) for t, x, y in siatka])
    # sąsiedztwo gmin jest pamiętane per województwo na czas działania aplikacji —
    # inne testy liczyły je dla innych „granic” tego samego województwa
    atlas_routes._sasiedzi_wojewodztw.clear()
    odp = client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&tryb=lisa")
    atlas_routes._sasiedzi_wojewodztw.clear()
    assert odp.status_code == 200
    svg = odp.get_data(as_text=True)
    assert "Klastry LISA (p &lt; 0,05)" in svg or "Klastry LISA (p < 0,05)" in svg
    assert "I Morana = 0," in svg and "permutacji), sąsiedztwo queen." in svg
    atlas_routes._sasiedzi_wojewodztw.clear()
    svg = client.get(f"/atlas/mapa.svg?{ZAPYTANIE}&tryb=gi").get_data(as_text=True)  # ETAP 152
    atlas_routes._sasiedzi_wojewodztw.clear()
    assert "Gorące i zimne punkty Gi*" in svg and "gorący punkt (99%)" in svg and "Getis-Ord Gi*" in svg


# ---------- ETAP 52: na tle kraju ----------


def test_wartosci_dla_wojewodztw_z_bdl(monkeypatch):
    odpowiedz = {
        "results": [
            {"id": "011200000000", "name": "MAŁOPOLSKIE", "values": [{"year": "2023", "val": 3.4}]},
            {"id": "051400000000", "name": "MAZOWIECKIE", "values": [{"year": "2023", "val": 5.5}]},
            {"id": "042200000000", "name": "POMORSKIE", "values": []},
        ]
    }
    zapytania = []
    monkeypatch.setattr(bdl, "_pobierz", lambda sciezka, parametry: zapytania.append(parametry) or odpowiedz)
    wynik = bdl.wartosci_dla_wojewodztw(1, 2023)
    assert [(w.teryt, w.nazwa, w.wartosc) for w in wynik] == [("12", "małopolskie", 3.4), ("14", "mazowieckie", 5.5)]
    assert zapytania[0]["unit-level"] == 2


def test_endpoint_porownania_wojewodztw(client, monkeypatch):
    wojewodztwa = [
        bdl.Wartosc("011200000000", "12", "małopolskie", 3_400_000.0),
        bdl.Wartosc("051400000000", "14", "mazowieckie", 5_500_000.0),
        bdl.Wartosc("042200000000", "22", "pomorskie", 2_300_000.0),
    ]
    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_wojewodztw", lambda z, rok: wojewodztwa)
    dane = client.get(f"/atlas/wojewodztwa-porownanie?{ZAPYTANIE}").get_json()
    assert [w["nazwa"] for w in dane["wojewodztwa"]] == ["mazowieckie", "małopolskie", "pomorskie"]
    assert dane["wybrane"]["miejsce"] == 2 and dane["mediana"] == 3_400_000.0

    # wskaźnik względny: dzielimy przez tę samą zmienną-mianownik województw
    wzgledny = client.get(f"/atlas/wojewodztwa-porownanie?{ZAPYTANIE}&mianownik=99&mnoznik=100").get_json()
    assert all(w["wartosc"] == 100 for w in wzgledny["wojewodztwa"])

    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_wojewodztw", lambda z, rok: [])
    assert client.get("/atlas/wojewodztwa-porownanie?zmienna=5&rok=2023&woj=011200000000").status_code == 404
    assert client.get("/atlas/wojewodztwa-porownanie?zmienna=x").status_code == 400


# ---------- ETAP 63: raport gminy ----------

from atlas import raport as raport_gminy  # noqa: E402

GMINA = "011212161011"
WOJ_RAPORTU = "011200000000"


def test_wojewodztwo_gminy_i_lista_gmin(monkeypatch):
    assert bdl.wojewodztwo_gminy(GMINA) == WOJ_RAPORTU
    strony = [
        {"totalRecords": 3, "results": [{"id": "011212161011", "name": "Kraków"}, {"id": "011212105054", "name": "Część"}]},
        {"totalRecords": 3, "results": [{"id": "011212105033", "name": "Alwernia"}]},
    ]
    zapytania = []

    def falszywy_get(url, params=None, **kw):
        zapytania.append(params)
        return FalszywaOdpowiedz(strony[params["page"]])

    monkeypatch.setattr(bdl, "ROZMIAR_STRONY", 2)
    monkeypatch.setattr(bdl.requests, "get", falszywy_get)
    gminy = bdl.gminy_wojewodztwa(WOJ_RAPORTU)
    assert [g.nazwa for g in gminy] == ["Alwernia", "Kraków"]  # część gminy (5) pominięta, po nazwie
    assert zapytania[0]["parent-id"] == WOJ_RAPORTU and zapytania[0]["level"] == 6


def test_podsumowanie_wskaznika_gminy():
    szereg = [{"rok": r, "wartosc": w} for r, w in [(2008, 50.0), (2013, 80.0), (2018, 90.0), (2023, 100.0)]]
    gminy = [{"bdl_id": GMINA, "wartosc": 100.0}, {"bdl_id": "a", "wartosc": 150.0}, {"bdl_id": "b", "wartosc": 100.0}, {"bdl_id": "c", "wartosc": 20.0}]
    s = raport_gminy.podsumuj(szereg, gminy, GMINA)
    assert (s["rok"], s["wartosc"], s["pozycja"], s["liczba_gmin"], s["mediana_wojewodztwa"]) == (2023, 100.0, 2, 4, 100.0)
    # 10 lat wstecz od 2023 → pierwszy rok ≥ 2013
    assert s["zmiana"]["od"] == 2013 and s["zmiana"]["zmiana_proc"] == pytest.approx(25.0)
    assert raport_gminy.podsumuj([], gminy, GMINA) is None
    jeden = raport_gminy.podsumuj([{"rok": 2023, "wartosc": 5.0}], [], GMINA)
    assert jeden["zmiana"] is None and jeden["pozycja"] is None and jeden["mediana_wojewodztwa"] is None

    fakty = raport_gminy.fakty_raportu("Kraków", "małopolskie", [{"nazwa": "Ludność", "jednostka": "osoba", "podsumowanie": s}, {"nazwa": "X", "jednostka": "", "podsumowanie": None}])
    assert fakty[1] == ("Ludność: 100 osoba w 2023 r. W 2013 r. było 80 osoba, zmiana o 25%. "
                        "Miejsce 2 na 4 gmin województwa (mediana województwa: 100 osoba).")
    assert len(fakty) == 2


@pytest.fixture
def raport_client(client, monkeypatch):
    """Klient z podmienionym BDL: jedno województwo, dwie gminy, zmienne 1 (ludność) i 2 (bezrobotni)."""
    monkeypatch.setattr(atlas_routes, "_wojewodztwa", lambda: [{"bdl_id": WOJ_RAPORTU, "nazwa": "małopolskie", "teryt": "12"}])
    monkeypatch.setattr(bdl, "gminy_wojewodztwa", lambda woj: [bdl.Jednostka(GMINA, "Kraków", "1261011"), bdl.Jednostka("011212105033", "Alwernia", "1212033")])
    monkeypatch.setattr(bdl, "pobierz_zmienna", lambda zid: bdl.Zmienna(zid, {1: "ludność ogółem", 2: "bezrobotni"}[zid], "osoba"))
    szeregi = {1: [{"rok": 2013, "wartosc": 1000.0}, {"rok": 2023, "wartosc": 800.0}], 2: [{"rok": 2023, "wartosc": 40.0}]}
    monkeypatch.setattr(bdl, "szereg_gminy", lambda zid, gid: szeregi[zid])
    wartosci = {1: [(GMINA, 800.0), ("011212105033", 5000.0)], 2: [(GMINA, 40.0), ("011212105033", 50.0)]}
    monkeypatch.setattr(atlas_routes, "_wartosci", lambda zid, rok, woj, poziom="gminy": [
        {"bdl_id": b, "teryt": b, "nazwa": b, "wartosc": w} for b, w in wartosci[zid]])
    return client


def test_raport_gminy_zestaw_i_dane(raport_client):
    c = raport_client
    assert "Zestaw wskaźników raportu jest pusty" in c.get(f"/atlas/raport-gminy/{GMINA}").get_data(as_text=True)
    w1 = c.post("/atlas/raport-wskazniki", json={"zmienna": 1}).get_json()["id"]
    odp = c.post("/atlas/raport-wskazniki", json={"zmienna": 2, "mianownik": 1, "mnoznik": 1000})
    assert odp.status_code == 201
    w2 = odp.get_json()["id"]
    assert odp.get_json()["wskazniki"][1]["nazwa_pelna"] == "bezrobotni na 1 000 (ludność ogółem)"
    assert c.post("/atlas/raport-wskazniki", json={"zmienna": "x"}).status_code == 400
    assert c.post("/atlas/raport-wskazniki", json={"zmienna": 2, "mianownik": 2}).status_code == 400

    html = c.get(f"/atlas/raport-gminy/{GMINA}").get_data(as_text=True)
    assert "Kraków" in html and "małopolskie" in html and f'data-wskaznik="{w2}"' in html
    assert c.get("/atlas/raport-gminy/011212105099").status_code == 404

    s = c.get(f"/atlas/raport-gminy/{GMINA}/wskaznik/{w1}").get_json()["podsumowanie"]
    assert (s["wartosc"], s["pozycja"], s["liczba_gmin"], s["zmiana"]["zmiana_proc"]) == (800.0, 2, 2, pytest.approx(-20.0))
    s = c.get(f"/atlas/raport-gminy/{GMINA}/wskaznik/{w2}").get_json()["podsumowanie"]
    assert s["wartosc"] == pytest.approx(50.0) and s["pozycja"] == 1  # 40/800·1000 = 50 > 50/5000·1000 = 10

    zestaw = c.post(f"/atlas/raport-wskazniki/{w2}/przesun", json={"o": -1}).get_json()["wskazniki"]
    assert [w["id"] for w in zestaw] == [w2, w1]
    assert c.delete(f"/atlas/raport-wskazniki/{w1}").get_json()["wskazniki"][0]["id"] == w2
    assert c.get("/atlas/gminy/" + WOJ_RAPORTU).get_json()[0]["nazwa"] == "Kraków"


def test_raport_gminy_opis_sprawdza_liczby(raport_client, monkeypatch):
    c = raport_client
    c.post("/atlas/raport-wskazniki", json={"zmienna": 1})
    przekazane = {}

    class Odpowiedz:
        text = "Kraków ma 800 mieszkańców, o 20% mniej niż w 2013 r."

    class Modele:
        def generate_content(self, **kw):
            przekazane["tresc"] = kw["contents"]
            return Odpowiedz()

    class Klient:
        def __init__(self, api_key):
            self.models = Modele()

    from dane import gemini
    monkeypatch.setattr(gemini.Config, "GEMINI_API_KEY", "test")
    import google.genai  # dane/gemini.py ładuje bibliotekę dopiero przy zapytaniu (ETAP 143)
    monkeypatch.setattr(google.genai, "Client", Klient)
    r = c.post(f"/atlas/raport-gminy/{GMINA}/opis")
    assert r.status_code == 200 and "Miejsce 2 na 2 gmin" in przekazane["tresc"]  # fakty z kodu

    Odpowiedz.text = "Kraków ma 900 mieszkańców."  # liczba spoza faktów
    r = c.post(f"/atlas/raport-gminy/{GMINA}/opis")
    assert r.status_code == 502 and "900" in r.get_json()["blad"] and r.get_json()["fakty"]


# ---------- ETAP 73: mapa położenia gminy ----------


def _kwadrat(teryt, x, y, nazwa="G"):
    return {"type": "Feature", "properties": {"teryt": teryt, "nazwa": nazwa},
            "geometry": {"type": "Polygon", "coordinates": [[[x, y], [x + 0.2, y], [x + 0.2, y + 0.1], [x, y + 0.1], [x, y]]]}}


def test_polozenie_gminy_svg():
    from atlas import mapa_svg

    kolekcja = {"type": "FeatureCollection", "features": [_kwadrat("1261011", 19.9, 50.0, "Kraków <&>"), _kwadrat("1212033", 19.5, 50.0)]}
    svg = mapa_svg.polozenie_gminy_svg(kolekcja, "1261011")
    assert svg.count("<path") == 2 and mapa_svg.KOLOR_GMINY in svg and mapa_svg.KOLOR_TLA_GMIN in svg
    assert "Kraków &lt;&amp;&gt;" in svg and " km</text>" in svg
    assert svg.index(mapa_svg.KOLOR_TLA_GMIN) < svg.index(mapa_svg.KOLOR_GMINY)  # wybrana na wierzchu
    with pytest.raises(ValueError):
        mapa_svg.polozenie_gminy_svg(kolekcja, "9999999")


def test_trasa_mapy_raportu_gminy(raport_client, monkeypatch):
    from atlas import granice

    kolekcja = {"type": "FeatureCollection", "features": [_kwadrat("1261011", 19.9, 50.0), _kwadrat("1212033", 19.5, 50.0)]}
    wywolania = []
    monkeypatch.setattr(granice, "granice_gmin", lambda teryt, folder: wywolania.append(teryt) or kolekcja)
    r = raport_client.get(f"/atlas/raport-gminy/{GMINA}/mapa.svg")
    assert r.status_code == 200 and r.mimetype == "image/svg+xml" and wywolania == ["12"]
    assert f"/atlas/raport-gminy/{GMINA}/mapa.svg" in raport_client.get(f"/atlas/raport-gminy/{GMINA}").get_data(as_text=True)

    def blad(teryt, folder):
        raise granice.BladGranic("Błąd połączenia z PRG")

    monkeypatch.setattr(granice, "granice_gmin", blad)
    r = raport_client.get(f"/atlas/raport-gminy/{GMINA}/mapa.svg")
    assert r.status_code == 502 and "PRG" in r.get_data(as_text=True)


# ---------- ETAP 76: porównanie z drugą gminą i CSV ----------


def test_raport_gminy_porownanie_i_csv(raport_client):
    c = raport_client
    c.post("/atlas/raport-wskazniki", json={"zmienna": 1})
    c.post("/atlas/raport-wskazniki", json={"zmienna": 2, "mianownik": 1, "mnoznik": 1000})
    druga = "011212105033"
    html = c.get(f"/atlas/raport-gminy/{GMINA}?porownaj={druga}").get_data(as_text=True)
    assert "Porównanie z: <strong>Alwernia</strong>" in html and 'data-pole="druga-wartosc"' in html
    assert f"/atlas/raport-gminy/{druga}/wskaznik/" in html
    assert c.get(f"/atlas/raport-gminy/{GMINA}?porownaj=011212105099").status_code == 404
    assert "Porównanie z" not in c.get(f"/atlas/raport-gminy/{GMINA}?porownaj={GMINA}").get_data(as_text=True)

    r = c.get(f"/atlas/raport-gminy/{GMINA}.csv?porownaj={druga}")
    assert r.headers["Content-Disposition"] == "attachment; filename=raport_1261011_1212033.csv"
    wiersze = r.get_data(as_text=True).lstrip("﻿").strip().split("\r\n")
    assert wiersze[0].startswith("wskaznik;jednostka;Kraków: rok;Kraków: wartosc;") and "Alwernia: wartosc" in wiersze[0]
    assert wiersze[1].startswith("ludność ogółem;osoba;2023;800,0;-20,0;2013;2;2;")
    assert wiersze[2].startswith("bezrobotni na 1 000 (ludność ogółem);;2023;50,0;")
    assert len(c.get(f"/atlas/raport-gminy/{GMINA}.csv").get_data(as_text=True).splitlines()[0].split(";")) == 9


# ---------- ETAP 84: wskaźnik złożony ----------


def _skladowa(nazwa, kierunek, wartosci, waga=1):
    return {"nazwa": nazwa, "kierunek": kierunek, "waga": waga,
            "gminy": [{"teryt": t, "nazwa": t.upper(), "wartosc": w} for t, w in wartosci.items()]}


def test_wskaznik_zlozony_unitaryzacja_i_kierunek():
    from atlas import zlozony
    mieszkania = _skladowa("mieszkania", 1, {"a": 10, "b": 20, "c": 30, "d": 5})
    bezrobocie = _skladowa("bezrobocie", -1, {"a": 2, "b": 4, "c": 6}, waga=3)  # d bez danych
    wynik = zlozony.wskaznik_zlozony([mieszkania, bezrobocie])
    # a: (0 + 3·1)/4 = 0,75; b: (0,5 + 3·0,5)/4 = 0,5; c: (1 + 0)/4 = 0,25
    assert [(g["teryt"], g["wartosc"], g["miejsce"]) for g in wynik["gminy"]] == [("a", 0.75, 1), ("b", 0.5, 2), ("c", 0.25, 3)]
    assert wynik["gminy"][0]["surowe"] == [10, 2] and wynik["gminy"][0]["skladowe"] == [0.0, 1.0]
    assert wynik["pominiete"] == ["D"]


def test_wskaznik_zlozony_standaryzacja_i_bledy():
    from atlas import zlozony
    a = _skladowa("x", 1, {"a": 1, "b": 2, "c": 3})
    b = _skladowa("y", 1, {"a": 3, "b": 2, "c": 1})
    wynik = zlozony.wskaznik_zlozony([a, b], "standaryzacja")
    assert all(g["wartosc"] == pytest.approx(0) for g in wynik["gminy"])  # przeciwne składowe znoszą się
    assert wynik["gminy"][0]["skladowe"][0] == pytest.approx(-1.2247, abs=1e-4)  # (1 − 2) / 0,8165
    with pytest.raises(zlozony.BladWskaznika, match="nic nie różnicuje"):
        zlozony.wskaznik_zlozony([a, _skladowa("stała", 1, {"a": 5, "b": 5, "c": 5})])
    with pytest.raises(zlozony.BladWskaznika, match="od 2"):
        zlozony.wskaznik_zlozony([a])
    with pytest.raises(zlozony.BladWskaznika, match="Za mało gmin"):
        zlozony.wskaznik_zlozony([a, _skladowa("z", 1, {"a": 1, "b": 2})])
    with pytest.raises(zlozony.BladWskaznika, match="waga"):
        zlozony.wskaznik_zlozony([a, {**b, "waga": 0}])
    with pytest.raises(zlozony.BladWskaznika, match="Metoda"):
        zlozony.wskaznik_zlozony([a, b], "mediana")


def test_wskaznik_zlozony_trasy(raport_client, monkeypatch):
    c = raport_client
    trzecia = "011212105044"
    TERYTY = {GMINA: "1261011", "011212105033": "1212033", trzecia: "1212044"}
    wartosci = {1: [(GMINA, 800.0), ("011212105033", 5000.0), (trzecia, 2000.0)],
                2: [(GMINA, 40.0), ("011212105033", 50.0), (trzecia, 10.0)]}
    monkeypatch.setattr(atlas_routes, "_wartosci", lambda zid, rok, woj, poziom="gminy": [
        {"bdl_id": b, "teryt": TERYTY[b], "nazwa": b, "wartosc": w} for b, w in wartosci[zid]])
    assert "co najmniej dwa" in c.get("/atlas/wskaznik-zlozony").get_data(as_text=True)
    w1 = c.post("/atlas/raport-wskazniki", json={"zmienna": 1}).get_json()["id"]
    w2 = c.post("/atlas/raport-wskazniki", json={"zmienna": 2, "mianownik": 1, "mnoznik": 1000}).get_json()["id"]
    html = c.get("/atlas/wskaznik-zlozony").get_data(as_text=True)
    assert f'data-id="{w2}"' in html and "bezrobotni na 1 000 (ludność ogółem)" in html

    zapytanie = f"woj={WOJ_RAPORTU}&rok=2023&s={w1}:1:1,{w2}:-1:2"
    wynik = c.get(f"/atlas/wskaznik-zlozony/wynik?{zapytanie}").get_json()
    # ludność: Kraków 0, Alwernia 1, trzecia 0,286; bezrobotni na 1000: 50, 10, 5 → destymulanta: 0, 0,889, 1
    assert [g["nazwa"] for g in wynik["gminy"]] == ["011212105033", trzecia, GMINA]
    assert wynik["gminy"][0]["wartosc"] == pytest.approx((1 + 2 * 40 / 45) / 3, abs=1e-4)
    assert wynik["wojewodztwo"]["nazwa"] == "małopolskie" and wynik["skladowe"][1]["kierunek"] == -1

    assert c.get(f"/atlas/wskaznik-zlozony/wynik?woj={WOJ_RAPORTU}&rok=2023&s={w1}:1:1").status_code == 400
    assert c.get(f"/atlas/wskaznik-zlozony/wynik?woj={WOJ_RAPORTU}&rok=2023&s={w1}:1:1,999:1:1").status_code == 400
    assert c.get(f"/atlas/wskaznik-zlozony/wynik?woj={WOJ_RAPORTU}&rok=2023&s={w1}:1:1,{w1}:1:1").status_code == 400
    assert c.get(f"/atlas/wskaznik-zlozony/wynik?woj={WOJ_RAPORTU}&rok=2023&s=x").status_code == 400

    csv_tekst = c.get(f"/atlas/wskaznik-zlozony.csv?{zapytanie}").get_data(as_text=True)
    assert csv_tekst.startswith("﻿miejsce;teryt;gmina;wskaźnik złożony;ludność ogółem;")
    assert "\r\n1;1212033;011212105033;" in csv_tekst and "- 2;" not in csv_tekst and "- 2.0" not in csv_tekst

    granica = {"type": "Polygon", "coordinates": [[[19.9, 50.0], [20.0, 50.0], [20.0, 50.1], [19.9, 50.0]]]}
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda teryt, folder: {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"teryt": t, "nazwa": t}, "geometry": granica}
                     for t in ("1261011", "1212033", "1212044", "1299999")]})
    svg = c.get(f"/atlas/wskaznik-zlozony/mapa.svg?{zapytanie}&pobierz=1")
    assert svg.mimetype == "image/svg+xml" and "attachment" in svg.headers["Content-Disposition"]
    tekst = svg.get_data(as_text=True)
    assert "Wskaźnik złożony" in tekst and "brak danych" in tekst and "unitaryzacja zerowana" in tekst


# ---------- ETAP 91: metoda Hellwiga ----------


def test_wskaznik_zlozony_hellwig():
    from atlas import zlozony
    a = _skladowa("mieszkania", 1, {"a": 1, "b": 2, "c": 3})
    b = _skladowa("bezrobocie", -1, {"a": 3, "b": 2, "c": 1})
    wynik = zlozony.wskaznik_zlozony([a, b], "hellwig")
    # z: a = (−1,22; −1,22), b = (0; 0), c = (1,22; 1,22) = wzorzec; d = (3,46; 1,73; 0)
    # d0 = 1,73 + 2·1,41 = 4,56; m = 1 − d/d0 = (0,24; 0,62; 1)
    m = {g["teryt"]: g["wartosc"] for g in wynik["gminy"]}
    assert m["c"] == 1.0 and m["b"] == pytest.approx(0.6202, abs=1e-3) and m["a"] == pytest.approx(0.2404, abs=1e-3)
    assert [g["teryt"] for g in wynik["gminy"]] == ["c", "b", "a"]
    # waga przesuwa wynik: ważniejsza składowa, w której gmina jest słaba, obniża miarę
    c = _skladowa("zieleń", 1, {"a": 3, "b": 1, "c": 2})
    rowne = {g["teryt"]: g["wartosc"] for g in zlozony.wskaznik_zlozony([a, c], "hellwig")["gminy"]}
    wazone = {g["teryt"]: g["wartosc"] for g in zlozony.wskaznik_zlozony([a, {**c, "waga": 5}], "hellwig")["gminy"]}
    assert wazone["a"] > rowne["a"] and wazone["c"] < rowne["c"]


def test_wskaznik_zlozony_hellwig_na_stronie(raport_client, monkeypatch):
    c = raport_client
    w1 = c.post("/atlas/raport-wskazniki", json={"zmienna": 1}).get_json()["id"]
    w2 = c.post("/atlas/raport-wskazniki", json={"zmienna": 2}).get_json()["id"]
    trzecia = "011212105044"
    wartosci = {1: [(GMINA, 800.0), ("011212105033", 5000.0), (trzecia, 2000.0)], 2: [(GMINA, 40.0), ("011212105033", 50.0), (trzecia, 10.0)]}
    monkeypatch.setattr(atlas_routes, "_wartosci", lambda zid, rok, woj, poziom="gminy": [{"bdl_id": b, "teryt": b, "nazwa": b, "wartosc": w} for b, w in wartosci[zid]])
    assert "metoda Hellwiga" in c.get("/atlas/wskaznik-zlozony").get_data(as_text=True)
    wynik = c.get(f"/atlas/wskaznik-zlozony/wynik?woj={WOJ_RAPORTU}&rok=2023&metoda=hellwig&s={w1}:1:1,{w2}:-1:1").get_json()
    assert wynik["metoda"] == "hellwig" and wynik["gminy"][0]["wartosc"] <= 1


# ---------- ETAP 92: ekstrapolacja trendu w raporcie gminy ----------


def test_prognoza_trendu():
    from atlas import raport
    rosnacy = [{"rok": r, "wartosc": 1000 + 20 * (r - 2013)} for r in range(2013, 2024)]
    p = raport.prognoza_trendu(rosnacy)
    assert (p["od"], p["do"], p["rok"]) == (2013, 2023, 2028)
    assert p["wartosc"] == pytest.approx(1300) and p["zmiana_roczna"] == pytest.approx(20) and p["r2"] == pytest.approx(1) and p["stabilny"]
    # tylko ostatnie 10 lat, a nie cały szereg
    assert raport.prognoza_trendu([{"rok": 1995, "wartosc": 99999}] + rosnacy)["od"] == 2013
    skaczacy = [{"rok": r, "wartosc": 100 + (15 if r % 2 else -15)} for r in range(2016, 2024)]
    assert not raport.prognoza_trendu(skaczacy)["stabilny"]
    assert raport.prognoza_trendu(rosnacy[:4]) is None  # za krótki szereg
    stala = [{"rok": r, "wartosc": 5} for r in range(2015, 2024)]
    assert raport.prognoza_trendu(stala)["r2"] == 1.0
    assert raport.podsumuj(rosnacy, [], GMINA)["prognoza"]["rok"] == 2028


# ---------- ETAP 124: typologia gmin ----------


def test_typologia_k_srednich():
    from atlas import typologia
    # dwie wyraźne grupy po 3 gminy
    a = [(1.0, 10.0), (1.2, 11.0), (0.9, 9.5), (5.0, 50.0), (5.2, 52.0), (4.9, 49.0)]
    skladowe = [{"nazwa": n, "gminy": [{"teryt": f"t{i}", "nazwa": f"g{i}", "wartosc": p[j]} for i, p in enumerate(a)]}
                for j, n in enumerate(["mieszkania", "dochody"])]
    skladowe[0]["gminy"].append({"teryt": "t9", "nazwa": "bez danych", "wartosc": 3.0})
    w = typologia.typologia(skladowe, 2)
    assert [t["liczba"] for t in w["typy"]] == [3, 3] and w["pominiete"] == ["bez danych"]
    typ = {g["nazwa"]: g["typ"] for g in w["gminy"]}
    assert typ["g0"] == typ["g1"] == typ["g2"] != typ["g3"] == typ["g4"] == typ["g5"]
    wysoki = next(t for t in w["typy"] if t["profil_z"][0] > 0)
    assert wysoki["opis"] == "wysoki: mieszkania; wysoki: dochody" and wysoki["srednie"][1] == pytest.approx(151 / 3)
    assert w["sylwetka"] > 0.9
    assert typologia.typologia(skladowe, 2) == w  # deterministycznie
    with pytest.raises(typologia.BladTypologii):
        typologia.typologia(skladowe, 4)  # 6 gmin na 4 typy — za mało
    with pytest.raises(typologia.BladTypologii):
        typologia.typologia(skladowe[:1], 2)
    stala = [skladowe[0], {"nazwa": "stała", "gminy": [{"teryt": f"t{i}", "nazwa": "x", "wartosc": 1.0} for i in range(6)]}]
    with pytest.raises(typologia.BladTypologii, match="nic nie różnicuje"):
        typologia.typologia(stala, 2)


def test_typologia_trasy(raport_client, monkeypatch):
    c = raport_client
    bdl_id = [f"0112121050{i:02d}" for i in range(6)]
    wartosci = {1: [(b, v) for b, v in zip(bdl_id, (100.0, 110.0, 90.0, 900.0, 950.0, 880.0))],
                2: [(b, v) for b, v in zip(bdl_id, (5.0, 6.0, 5.5, 50.0, 52.0, 49.0))]}
    monkeypatch.setattr(atlas_routes, "_wartosci", lambda zid, rok, woj, poziom="gminy": [
        {"bdl_id": b, "teryt": "12" + b[-5:], "nazwa": "gmina " + b[-2:], "wartosc": w} for b, w in wartosci[zid]])
    assert "co najmniej dwa" in c.get("/atlas/typologia").get_data(as_text=True)
    w1 = c.post("/atlas/raport-wskazniki", json={"zmienna": 1}).get_json()["id"]
    w2 = c.post("/atlas/raport-wskazniki", json={"zmienna": 2}).get_json()["id"]
    assert f'value="{w2}"' in c.get("/atlas/typologia").get_data(as_text=True)
    zapytanie = f"woj={WOJ_RAPORTU}&rok=2023&k=2&s={w1}:1:1,{w2}:1:1"
    d = c.get(f"/atlas/typologia/wynik?{zapytanie}").get_json()
    assert d["k"] == 2 and [t["liczba"] for t in d["typy"]] == [3, 3] and len(d["kolory"]) == 2
    assert c.get(f"/atlas/typologia/wynik?{zapytanie.replace('k=2', 'k=9')}").status_code == 400
    assert c.get(f"/atlas/typologia/wynik?{zapytanie.replace('k=2', 'k=x')}").status_code == 400
    csv_tekst = c.get(f"/atlas/typologia.csv?{zapytanie}").get_data(as_text=True)
    assert csv_tekst.startswith("﻿typ;teryt;gmina;") and "Typ 1 (3 gmin)" in csv_tekst
    granica = {"type": "Polygon", "coordinates": [[[19.9, 50.0], [20.0, 50.0], [20.0, 50.1], [19.9, 50.0]]]}
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda teryt, folder: {
        "type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"teryt": "12" + b[-5:], "nazwa": b}, "geometry": granica} for b in bdl_id]})
    svg = c.get(f"/atlas/typologia/mapa.svg?{zapytanie}").get_data(as_text=True)
    assert "Typologia gmin" in svg and ">Typ 1<" in svg and "Typ 1: " in svg and "k-średnich (k = 2)" in svg


# ---------- ETAP 125: dobór liczby typów ----------


def test_sylwetki_dla_k():
    from atlas import typologia
    # trzy wyraźne grupy po 4 gminy → najlepsze k = 3
    a = [(0.0, 0.0), (0.1, 0.2), (0.2, 0.1), (0.1, 0.0), (5.0, 5.0), (5.1, 5.2), (5.2, 5.1), (5.1, 5.0),
         (0.0, 9.0), (0.1, 9.2), (0.2, 9.1), (0.1, 9.0)]
    skladowe = [{"nazwa": n, "gminy": [{"teryt": f"t{i}", "nazwa": f"g{i}", "wartosc": p[j]} for i, p in enumerate(a)]} for j, n in enumerate("AB")]
    s = typologia.sylwetki(skladowe)
    assert [w["k"] for w in s] == [2, 3, 4, 5, 6]  # 12 gmin → najwyżej 6 typów
    assert [w["k"] for w in s if w["najlepsza"]] == [3] and s[1]["sylwetka"] > 0.9


def test_trasa_sylwetek(raport_client, monkeypatch):
    c = raport_client
    bdl_id = [f"0112121050{i:02d}" for i in range(6)]
    wartosci = {1: list(zip(bdl_id, (100.0, 110.0, 90.0, 900.0, 950.0, 880.0))), 2: list(zip(bdl_id, (5.0, 6.0, 5.5, 50.0, 52.0, 49.0)))}
    monkeypatch.setattr(atlas_routes, "_wartosci", lambda zid, rok, woj, poziom="gminy": [
        {"bdl_id": b, "teryt": "12" + b[-5:], "nazwa": b, "wartosc": w} for b, w in wartosci[zid]])
    w1 = c.post("/atlas/raport-wskazniki", json={"zmienna": 1}).get_json()["id"]
    w2 = c.post("/atlas/raport-wskazniki", json={"zmienna": 2}).get_json()["id"]
    s = c.get(f"/atlas/typologia/sylwetki?woj={WOJ_RAPORTU}&rok=2023&s={w1}:1:1,{w2}:1:1").get_json()
    assert [w["k"] for w in s] == [2, 3] and s[0]["najlepsza"]
    assert c.get(f"/atlas/typologia/sylwetki?woj={WOJ_RAPORTU}&rok=2023&s={w1}:1:1").status_code == 400
    assert "Porównaj liczbę typów" in c.get("/atlas/typologia").get_data(as_text=True)


# ---------- ETAP 152: gorące punkty Getisa-Orda Gi* ----------


def test_gi_star_zgodne_z_pysal():
    """Wartości referencyjne z PySAL (esda.G_Local, star=True, wagi binarne) dla tej samej siatki."""
    from atlas import autokorelacja
    pos = {f"g{x}{y}": (x, y) for y in range(5) for x in range(6)}
    sas = {i: sorted(j for j in pos if j != i and max(abs(pos[i][0] - pos[j][0]), abs(pos[i][1] - pos[j][1])) == 1) for i in pos}
    wart = {i: 100 - 8 * (x + y) + (x * 7 + y * 3) % 5 for i, (x, y) in pos.items()}
    gi = {g["teryt"]: g for g in autokorelacja.gi_star(wart, sas)}
    for teryt, z_pysal in [("g00", 3.2482092832), ("g22", 0.7294864219), ("g54", -3.3376095387), ("g30", 1.2915853341)]:
        assert gi[teryt]["z"] == pytest.approx(z_pysal, abs=1e-9)
    assert gi["g00"]["kategoria"] == "H99" and gi["g54"]["kategoria"] == "C99" and gi["g22"]["kategoria"] == "ns"
    assert gi["g30"]["p"] == pytest.approx(0.1965, abs=1e-3)  # dwustronne z rozkładu normalnego
    # analiza zwraca Gi* razem z LISA
    wynik = autokorelacja.analiza(wart, {k: set(v) for k, v in sas.items()})
    assert len(wynik["gi"]) == 30 and wynik["kategorie_gi"]["H95"] == "gorący punkt (95%)"


# ---------- ETAP 153: iloraz lokalizacji ----------


def test_iloraz_lokalizacji():
    licznik = [{"teryt": "a", "wartosc": 30}, {"teryt": "b", "wartosc": 10}, {"teryt": "c", "wartosc": 5}, {"teryt": "d", "wartosc": 1}]
    mianownik = [{"teryt": "a", "wartosc": 100}, {"teryt": "b", "wartosc": 100}, {"teryt": "c", "wartosc": 0}, {"teryt": "d", "wartosc": 200}]
    w = statystyki.iloraz_lokalizacji(licznik, mianownik)
    assert w["udzial_wojewodztwa"] == pytest.approx(41 / 400)  # gmina c pominięta (mianownik 0)
    lq = {g["teryt"]: g for g in w["gminy"]}
    assert lq["a"]["lq"] == pytest.approx(0.3 / (41 / 400)) and lq["a"]["klasa"] == 4  # > 2
    assert lq["b"]["lq"] == pytest.approx(0.1 / (41 / 400)) and lq["b"]["klasa"] == 2  # 0,8–1,2
    assert lq["d"]["klasa"] == 0 and "c" not in lq
    assert statystyki.iloraz_lokalizacji(licznik, []) is None



# ---------- ETAP 161: ten sam wskaźnik w kilku latach ----------


def test_mapy_w_latach(client, monkeypatch):
    cechy = [{"type": "Feature", "properties": {"teryt": t, "nazwa": n},
              "geometry": {"type": "Polygon", "coordinates": [[[19 + i, 50], [20 + i, 50], [20 + i, 51], [19 + i, 51], [19 + i, 50]]]}}
             for i, (t, n) in enumerate([("1261011", "Kraków"), ("1206032", "Wieliczka")])]
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda teryt, folder: {"type": "FeatureCollection", "features": cechy})
    odp = client.get(f"/atlas/lata.svg?{ZAPYTANIE}&lata=2013,2023")
    assert odp.status_code == 200 and odp.mimetype == "image/svg+xml"
    svg = odp.get_data(as_text=True)
    assert ">2013</text>" in svg and ">2023</text>" in svg and "wspólnych dla wszystkich lat" in svg
    assert svg.count("<path") == 4  # 2 gminy × 2 mapy
    assert "#c7c7cc" in svg  # Wieliczka bez danych w 2013
    for zle in ("2023", "2013,2014,2015,2016,2017,2018,2019", "abc", "1900,2023"):
        assert client.get(f"/atlas/lata.svg?{ZAPYTANIE}&lata={zle}").status_code == 400
    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_gmin", lambda z, rok, woj: [] if rok != 2023 else [bdl.Wartosc("011212161011", "1261011", "Kraków", 1.0)])
    assert client.get(f"/atlas/lata.svg?{ZAPYTANIE}&lata=2016,2023").status_code == 404  # 2016 bez danych (2023 z cache) — jeden rok to za mało
    strona = client.get(f"/atlas/lata?{ZAPYTANIE}").get_data(as_text=True)
    assert 'value="2014,2017,2020,2023"' in strona and "stopka-wydruku" in strona


# ---------- ETAP 171: kilka gmin w czasie ----------


def test_wykres_gmin_svg():
    from atlas.wykres_svg import _ladna_os, wykres_gmin_svg

    serie = [{"szereg": [{"rok": r, "wartosc": v} for r, v in [(2015, 10.0), (2016, 12.0), (2017, 15.0)]], "kolor": "#0071e3"},
             {"szereg": [{"rok": r, "wartosc": v} for r, v in [(2015, 2.0), (2017, 3.0)]], "kolor": "#ff9500"}]
    svg = wykres_gmin_svg(serie)
    assert svg.count("<polyline") == 1  # druga seria bez 2016 — linia przerwana, same punkty
    assert svg.count("<circle") == 5 and ">2016</text>" in svg and ">0</text>" in svg  # oś od zera (dane blisko zera)
    assert ">1</text>" in svg and ">2</text>" in svg  # numery linii
    assert "za mało lat" in wykres_gmin_svg([{"szereg": [{"rok": 2020, "wartosc": 1.0}], "kolor": "#000"}])
    assert _ladna_os(803, 1217) == (800, 1300, 100)


def test_strona_gmin_w_czasie(client, monkeypatch):
    szeregi = {"011212161011": [{"rok": 2021, "wartosc": 800000.0}, {"rok": 2022, "wartosc": 802000.0}, {"rok": 2023, "wartosc": 804237.0}],
               "011212106032": [{"rok": 2021, "wartosc": 60000.0}, {"rok": 2023, "wartosc": 63000.0}]}
    monkeypatch.setattr(atlas_routes.bdl, "szereg_gminy", lambda zid, gid: szeregi[gid])
    url = f"/atlas/gminy-w-czasie?{ZAPYTANIE}"
    pusta = client.get(url).get_data(as_text=True)
    assert 'id="lista-gmin"' in pusta and "Kraków (1261011)" in pusta and "tabela-gmin-czasu" not in pusta
    strona = client.get(url + "&gminy=011212161011,011212106032,zly,011212161011").get_data(as_text=True)
    assert 'id="tabela-gmin-czasu"' in strona and "<polyline" in strona and "stopka-wydruku" in strona
    assert "+0,5%" in strona and "+5,0%" in strona  # zmiana 2021→2023: Kraków, Wieliczka
    assert strona.count('data-usun="') == 2  # duplikat i zły identyfikator pominięte
    csv_ = client.get(url + "&gminy=011212106032&format=csv")
    tekst = csv_.data.decode("utf-8-sig")
    assert csv_.mimetype == "text/csv" and tekst.splitlines()[0] == "teryt,gmina,wartosc_2021,wartosc_2023"
    assert "1206032,Wieliczka,60000.0,63000.0" in tekst
    assert client.get("/atlas/gminy-w-czasie?zmienna=x").status_code == 400
    assert 'id="link-gminy-czas"' in client.get("/atlas/").get_data(as_text=True)


# ---------- ETAP 177: gminy podobne do wybranej ----------


def test_gminy_podobne():
    from atlas import typologia
    a = [(1.0, 10.0), (1.2, 11.0), (0.9, 9.5), (5.0, 50.0), (5.2, 52.0), (4.9, 49.0)]
    skladowe = [{"nazwa": n, "gminy": [{"teryt": f"t{i}", "nazwa": f"g{i}", "wartosc": p[j]} for i, p in enumerate(a)]}
                for j, n in enumerate(["mieszkania", "dochody"])]
    w = typologia.podobne(skladowe, "t0", ile=3)
    assert w["gmina"]["nazwa"] == "g0" and w["liczba_gmin"] == 6
    assert [g["nazwa"] for g in w["podobne"]] == ["g2", "g1", "g5"]  # najpierw własna grupa
    assert w["podobne"][0]["odleglosc"] < w["podobne"][2]["odleglosc"]
    assert w["podobne"][2]["najwieksza_roznica"]["z"] > 0 and w["podobne"][2]["surowe"] == [4.9, 49.0]
    with pytest.raises(typologia.BladTypologii):
        typologia.podobne(skladowe, "brak")


def test_trasa_podobnych(raport_client, monkeypatch):
    c = raport_client
    bdl_id = [f"0112121050{i:02d}" for i in range(6)]
    wartosci = {1: list(zip(bdl_id, (100.0, 110.0, 90.0, 900.0, 950.0, 880.0))), 2: list(zip(bdl_id, (5.0, 6.0, 5.5, 50.0, 52.0, 49.0)))}
    monkeypatch.setattr(atlas_routes, "_wartosci", lambda zid, rok, woj, poziom="gminy": [
        {"bdl_id": b, "teryt": "12" + b[-5:], "nazwa": "gmina " + b[-2:], "wartosc": w} for b, w in wartosci[zid]])
    w1 = c.post("/atlas/raport-wskazniki", json={"zmienna": 1}).get_json()["id"]
    w2 = c.post("/atlas/raport-wskazniki", json={"zmienna": 2}).get_json()["id"]
    zapytanie = f"woj={WOJ_RAPORTU}&rok=2023&k=2&s={w1}:1:1,{w2}:1:1"
    d = c.get(f"/atlas/typologia/podobne?{zapytanie}&gmina=1205003").get_json()
    assert d["gmina"]["nazwa"] == "gmina 03" and d["podobne"][0]["nazwa"] in ("gmina 04", "gmina 05") and len(d["skladowe"]) == 2
    assert c.get(f"/atlas/typologia/podobne?{zapytanie}&gmina=9999999").status_code == 400
    assert 'id="pole-podobne"' in c.get("/atlas/typologia").get_data(as_text=True)


# ---------- ETAP 178: trend w gminach ----------


def test_trendy_gmin():
    from atlas.trasy_trend import trendy_gmin

    lata = {r: [{"teryt": "A", "nazwa": "Rosnąca", "wartosc": 100.0 + 10 * (r - 2015)},
                {"teryt": "B", "nazwa": "Malejąca", "wartosc": 200.0 - 4 * (r - 2015) + (5 if r % 2 else -5)},
                *([{"teryt": "C", "nazwa": "Krótka", "wartosc": 1.0}] if r > 2020 else [])] for r in range(2015, 2024)}
    t = trendy_gmin(lata)
    assert [g["nazwa"] for g in t] == ["Rosnąca", "Malejąca"]  # „Krótka” — za mało lat
    assert t[0]["zmiana_roczna"] == pytest.approx(10) and t[0]["zmiana_roczna_proc"] == pytest.approx(10 / 140 * 100) and t[0]["stabilny"]
    assert t[1]["zmiana_roczna"] < 0 and t[1]["r2"] < 1


def test_strona_trendu(client, monkeypatch):
    from atlas import trasy_trend

    monkeypatch.setattr(trasy_trend, "_wartosci_wskaznika", lambda zid, rok, woj, m, mn: [
        {"bdl_id": "011212161011", "teryt": "1261011", "nazwa": "Kraków", "wartosc": 800000.0 + 1000 * (rok - 2013)},
        {"bdl_id": "011212106032", "teryt": "1206032", "nazwa": "Wieliczka", "wartosc": 60000.0 + 2000 * (rok - 2013)}])
    cechy = [{"type": "Feature", "properties": {"teryt": t, "nazwa": n},
              "geometry": {"type": "Polygon", "coordinates": [[[19 + i, 50], [20 + i, 50], [20 + i, 51], [19 + i, 51], [19 + i, 50]]]}}
             for i, (t, n) in enumerate([("1261011", "Kraków"), ("1206032", "Wieliczka"), ("1206000", "Bez danych")])]
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda teryt, folder: {"type": "FeatureCollection", "features": cechy})
    strona = client.get(f"/atlas/trend?{ZAPYTANIE}").get_data(as_text=True)
    assert 'value="2013"' in strona and "Najszybszy wzrost" in strona and "Wieliczka" in strona and "stopka-wydruku" in strona
    svg = client.get(f"/atlas/trend.svg?{ZAPYTANIE}&od=2013&do=2023").get_data(as_text=True)
    assert "trend 2013–2023" in svg and "wzrost ponad 3%" in svg and "mniej niż 5 lat danych" in svg
    for zle in ("od=2020&do=2023", "od=2000&do=2023", "od=x&do=2023"):
        assert client.get(f"/atlas/trend.svg?{ZAPYTANIE}&{zle}").status_code == 400
    assert 'id="link-trend"' in client.get("/atlas/").get_data(as_text=True)


# ---------- ETAP 188: arkusz ODS ----------


def test_eksport_ods_atlasu(client):
    odp = client.get("/atlas/eksport.ods?zmienna=72305&rok=2023&woj=011200000000")
    assert odp.mimetype == "application/vnd.oasis.opendocument.spreadsheet" and ".ods" in odp.headers["Content-Disposition"]
    import io, zipfile
    from xml.dom import minidom
    doc = minidom.parseString(zipfile.ZipFile(io.BytesIO(odp.data)).read("content.xml"))
    tekst = doc.toxml()
    assert "Kraków" in tekst and 'office:value="804237.0"' in tekst and "Bank Danych Lokalnych" in tekst
    assert client.get("/atlas/eksport.ods?zmienna=x").status_code == 400


# ---------- ETAP 193: gminy podobne w raporcie gminy ----------


def test_raport_gminy_podobne(raport_client, monkeypatch):
    c = raport_client
    assert c.get(f"/atlas/raport-gminy/{GMINA}/podobne").status_code == 400  # pusty zestaw
    gminy = [(GMINA, "1261011", "Kraków", 800.0, 40.0), ("011212105033", "1212033", "Alwernia", 5000.0, 50.0),
             ("011212105034", "1212034", "Bliska", 820.0, 41.0), ("011212105035", "1212035", "Daleka", 9000.0, 900.0)]
    monkeypatch.setattr(atlas_routes, "_wartosci", lambda zid, rok, woj, poziom="gminy": [
        {"bdl_id": b, "teryt": t, "nazwa": n, "wartosc": (v1 if zid == 1 else v2)} for b, t, n, v1, v2 in gminy])
    c.post("/atlas/raport-wskazniki", json={"zmienna": 1})
    c.post("/atlas/raport-wskazniki", json={"zmienna": 2})
    d = c.get(f"/atlas/raport-gminy/{GMINA}/podobne").get_json()
    assert d["gmina"]["nazwa"] == "Kraków" and d["podobne"][0]["nazwa"] == "Bliska" and d["rok"] == 2023 and len(d["skladowe"]) == 2
    assert 'id="sekcja-podobnych"' in c.get(f"/atlas/raport-gminy/{GMINA}").get_data(as_text=True)


# ---------- ETAP 194: stabilność rankingu wskaźnika złożonego ----------


def test_stabilnosc_rankingu():
    from atlas import zlozony

    def wynik(wartosci):
        return {"gminy": [{"teryt": t, "nazwa": t.upper(), "wartosc": v} for t, v in wartosci.items()]}

    s = zlozony.stabilnosc({2023: wynik({"a": 0.9, "b": 0.5, "c": 0.1, "d": 0.3}), 2015: wynik({"a": 0.2, "b": 0.8, "c": 0.1}),
                            2019: wynik({"a": 0.5, "b": 0.6, "c": 0.4, "e": 1.0})})
    assert s["lata"] == [2015, 2019, 2023] and s["liczba_gmin"] == 3  # „d” i „e” nie we wszystkich latach
    a = next(g for g in s["gminy"] if g["teryt"] == "a")
    assert a["miejsca"] == {2015: 2, 2019: 2, 2023: 1} and a["zmiana"] == 1
    assert [g["teryt"] for g in s["gminy"]] == ["a", "b", "c"]  # kolejność wg ostatniego roku
    assert s["rho"] == pytest.approx(0.5)
    with pytest.raises(zlozony.BladWskaznika):
        zlozony.stabilnosc({2020: wynik({"a": 1, "b": 2}), 2021: wynik({"a": 1, "b": 2})})


def test_trasa_stabilnosci(raport_client, monkeypatch):
    c = raport_client
    teryty = {GMINA: "1261011", "011212105033": "1212033", "011212105044": "1212044"}
    monkeypatch.setattr(atlas_routes, "_wartosci", lambda zid, rok, woj, poziom="gminy": [
        {"bdl_id": b, "teryt": t, "nazwa": t, "wartosc": ((rok - 2011) * 10 if b == GMINA else (i + 1) * 10) + zid} for i, (b, t) in enumerate(teryty.items())])
    w1 = c.post("/atlas/raport-wskazniki", json={"zmienna": 1}).get_json()["id"]
    w2 = c.post("/atlas/raport-wskazniki", json={"zmienna": 2}).get_json()["id"]
    zapytanie = f"woj={WOJ_RAPORTU}&rok=2023&s={w1}:1:1,{w2}:1:1"
    d = c.get(f"/atlas/wskaznik-zlozony/lata?{zapytanie}&lata=2012,2023").get_json()
    assert d["lata"] == [2012, 2023] and d["liczba_gmin"] == 3
    assert next(g for g in d["gminy"] if g["teryt"] == "1261011")["zmiana"] == 2  # z 3. miejsca na 1.
    assert c.get(f"/atlas/wskaznik-zlozony/lata?{zapytanie}&lata=2023").status_code == 400
    assert 'id="formularz-lat"' in c.get("/atlas/wskaznik-zlozony").get_data(as_text=True)


# ---------- ETAP 215: powiaty ----------


def test_granice_powiatow_z_gmin(tmp_path, monkeypatch):
    from shapely.geometry import box, mapping, shape

    # powiat 1206: dwie gminy obok siebie z wąską szczeliną (jak po osobnym uproszczeniu); 1261: miasto (jedna gmina)
    gminy = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"teryt": "1206012", "nazwa": "A"}, "geometry": mapping(box(19.0, 50.0, 19.1, 50.1))},
        {"type": "Feature", "properties": {"teryt": "1206022", "nazwa": "B"}, "geometry": mapping(box(19.10005, 50.0, 19.2, 50.1))},
        {"type": "Feature", "properties": {"teryt": "1261011", "nazwa": "Kraków"}, "geometry": mapping(box(19.9, 50.0, 20.0, 50.1))},
    ]}
    wywolania = []
    monkeypatch.setattr(granice, "granice_gmin", lambda teryt, folder: wywolania.append(teryt) or gminy)
    k = granice.granice_powiatow("12", str(tmp_path))
    assert [c["properties"]["teryt"] for c in k["features"]] == ["1206", "1261"]
    assert [c["properties"]["nazwa"] for c in k["features"]] == ["", "Kraków"]
    powiat = shape(k["features"][0]["geometry"])
    assert powiat.geom_type == "Polygon" and not list(powiat.interiors)  # szczelina domknięta — jeden wielobok
    assert powiat.area == pytest.approx(0.02, rel=0.01)
    granice.granice_powiatow("12", str(tmp_path))
    assert wywolania == ["12"]  # drugi raz z pliku cache
    assert granice.granice_powiatow("12", str(tmp_path / "nowy" / "folder"))["features"]  # folder cache tworzony w razie potrzeby


def test_dane_dla_powiatow(client, monkeypatch):
    wywolania = []

    def wartosci(zid, rok, woj, poziom="gminy"):
        wywolania.append(poziom)
        return [{"bdl_id": f"0112{i:08d}", "teryt": f"12{i:02d}", "nazwa": f"Powiat {i}", "wartosc": 100.0 * i} for i in range(1, 6)]

    monkeypatch.setattr(atlas_routes, "_wartosci", wartosci)
    monkeypatch.setattr(atlas_routes, "_wojewodztwa", lambda: [{"bdl_id": "011200000000", "nazwa": "MAŁOPOLSKIE", "teryt": "12"}])
    monkeypatch.setattr(atlas_routes, "_opis_zmiennej", lambda *a: {"id": 1, "nazwa": "ludność", "jednostka": "osoba"})
    d = client.get("/atlas/dane?zmienna=1&rok=2023&woj=011200000000&poziom=powiaty").get_json()
    assert d["poziom"] == "powiaty" and [g["teryt"] for g in d["gminy"]][:2] == ["1205", "1204"] and wywolania == ["powiaty"]
    assert client.get("/atlas/dane?zmienna=1&rok=2023&woj=011200000000&poziom=wsie").status_code == 400
    csv_tekst = client.get("/atlas/eksport.csv?zmienna=1&rok=2023&woj=011200000000&poziom=powiaty").get_data(as_text=True)
    assert "Powiat 5" in csv_tekst
    monkeypatch.setattr(atlas_routes.granice, "granice_powiatow", lambda teryt, folder: {"type": "FeatureCollection", "features": []})
    assert client.get("/atlas/granice-powiatow/12").status_code == 200 and client.get("/atlas/granice-powiatow/x1").status_code == 400


# ---------- ETAP 216: powiaty na stronie Atlasu ----------


def test_powiaty_klasy_autokorelacja_eksport_druk_opis(client, monkeypatch):
    from shapely.geometry import box, mapping

    def wartosci(zid, rok, woj, poziom="gminy"):
        assert poziom == "powiaty"
        return [{"bdl_id": f"0112{i:08d}", "teryt": f"12{i:02d}", "nazwa": f"Powiat {i}", "wartosc": float(v)}
                for i, v in zip(range(1, 7), [10, 12, 30, 33, 50, 55])]

    powiaty = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"teryt": f"12{i:02d}", "nazwa": ""}, "geometry": mapping(box(19 + (i - 1) % 3 * 0.1, 50 + (i - 1) // 3 * 0.1,
                                                                                                         19.1 + (i - 1) % 3 * 0.1, 50.1 + (i - 1) // 3 * 0.1))}
        for i in range(1, 7)]}
    monkeypatch.setattr(atlas_routes, "_wartosci", wartosci)
    monkeypatch.setattr(atlas_routes, "_wojewodztwa", lambda: [{"bdl_id": "011200000000", "nazwa": "MAŁOPOLSKIE", "teryt": "12"}])
    monkeypatch.setattr(atlas_routes, "_opis_zmiennej", lambda *a: {"id": 1, "nazwa": "ludność", "jednostka": "osoba"})
    monkeypatch.setattr(atlas_routes.granice, "granice_powiatow", lambda teryt, folder: powiaty)
    monkeypatch.setattr(atlas_routes.granice, "granice_gmin", lambda *a: (_ for _ in ()).throw(AssertionError("gminy nie powinny być pobierane")))
    p = "zmienna=1&rok=2023&woj=011200000000&poziom=powiaty"
    assert client.get(f"/atlas/klasy?{p}&metoda=kwantyle&klasy=3").status_code == 200
    moran = client.get(f"/atlas/autokorelacja?{p}").get_json()
    assert moran["liczba_gmin"] == 6 and moran["pominiete"] == 0  # sąsiedztwo z granic powiatów (gminy nie są pobierane)
    geo = client.get(f"/atlas/eksport.geojson?{p}").get_json()
    assert len(geo["features"]) == 6 and geo["features"][0]["properties"]["teryt"] == "1201"
    druk = client.get(f"/atlas/mapa.svg?{p}").get_data(as_text=True)
    assert "Powiaty województwa MAŁOPOLSKIE" in druk
    otrzymane = []
    monkeypatch.setattr(atlas_routes, "opisz_wskaznik", lambda fakty: otrzymane.extend(fakty) or "Opis.")
    client.post("/atlas/opis", json={"zmienna": 1, "rok": 2023, "woj": "011200000000", "poziom": "powiaty"})
    assert "Obszar: powiaty województwa MAŁOPOLSKIE" in otrzymane and any(f.startswith("3 powiaty o najwyższej") for f in otrzymane)
    assert 'id="pole-poziom"' in client.get("/atlas/").get_data(as_text=True)


# ---------- ETAP 228: granice — zapytania do PRG i nietypowy GML ----------


class _OdpPRG:
    def __init__(self, tekst="", status=200):
        self.text, self.status_code = tekst, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def test_zapytania_do_prg_maja_warstwe_i_filtr(monkeypatch):
    zapytania = []
    monkeypatch.setattr(granice.requests, "get", lambda url, params=None, **k: zapytania.append(params) or _OdpPRG("<x/>"))
    assert granice._pobierz_gml("12") == "<x/>"
    assert granice._pobierz_gml_wojewodztw() == "<x/>"
    gminy, wojewodztwa = zapytania
    assert gminy["typeNames"] == granice.WARSTWA_GMIN and "<fes:Literal>12*</fes:Literal>" in gminy["filter"]
    assert granice.POLE_TERYT in gminy["filter"] and gminy["srsName"] == "EPSG:4326"
    assert wojewodztwa["typeNames"] == granice.WARSTWA_WOJEWODZTW and "filter" not in wojewodztwa


@pytest.mark.parametrize("blad", [requests.ConnectionError("brak sieci"), None])
def test_blad_polaczenia_z_prg(monkeypatch, blad):
    def get(*a, **k):
        if blad:
            raise blad
        return _OdpPRG(status=503)
    monkeypatch.setattr(granice.requests, "get", get)
    with pytest.raises(granice.BladGranic, match="Błąd połączenia z PRG"):
        granice._pobierz_gml("12")


def test_gminy_pusta_odpowiedz_i_zly_xml(tmp_path, monkeypatch):
    monkeypatch.setattr(granice, "_pobierz_gml", lambda teryt: '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"/>')
    with pytest.raises(granice.BladGranic, match="żadnej gminy"):
        granice.granice_gmin("12", str(tmp_path))
    assert not os.listdir(tmp_path)
    with pytest.raises(granice.BladGranic, match="sparsować"):
        granice._sparsuj_gml("<niedomknięty", "12")


def test_gml_bez_geometrii_bez_obwodu_i_kolejnosc_lon_lat():
    gml = """<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:ms="m">
      <wfs:member><ms:A03 gml:id="a"><ms:JPT_KOD_JE>1201011</ms:JPT_KOD_JE><ms:JPT_NAZWA_>bez geometrii</ms:JPT_NAZWA_></ms:A03></wfs:member>
      <wfs:member><ms:A03 gml:id="b"><ms:g><gml:Polygon><gml:interior/></gml:Polygon></ms:g>
        <ms:JPT_KOD_JE>1201022</ms:JPT_KOD_JE><ms:JPT_NAZWA_>wielobok bez obwodu</ms:JPT_NAZWA_></ms:A03></wfs:member>
      <wfs:member><ms:A03 gml:id="c"><ms:g><gml:Polygon><gml:exterior><gml:LinearRing>
        <gml:posList>19.0 50.0 19.1 50.0 19.1 50.1 19.0 50.0</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></ms:g>
        <ms:JPT_KOD_JE>1201033</ms:JPT_KOD_JE><ms:JPT_NAZWA_>długość pierwsza</ms:JPT_NAZWA_></ms:A03></wfs:member>
    </wfs:FeatureCollection>"""
    k = granice._sparsuj_gml(gml, "12")
    assert [c["properties"]["teryt"] for c in k["features"]] == ["1201033"]  # dwie pierwsze bez geometrii — pominięte
    lon, lat = k["features"][0]["geometry"]["coordinates"][0][0]
    assert (lon, lat) == (19.0, 50.0)  # kolejność lon, lat rozpoznana i zostawiona


# ---------- ETAP 228: raport gminy — ścieżki błędów ----------


def _blad_bdl(*a, **k):
    raise bdl.BladBDL("BDL nie odpowiada")


def test_raport_gminy_walidacja_zestawu(raport_client):
    c = raport_client
    assert c.get("/atlas/gminy/123").status_code == 400
    assert c.get("/atlas/raport-gminy/12345").status_code == 404  # identyfikator nie ma 12 cyfr
    assert c.delete("/atlas/raport-wskazniki/999").status_code == 404
    w = c.post("/atlas/raport-wskazniki", json={"zmienna": 1}).get_json()["id"]
    assert c.post(f"/atlas/raport-wskazniki/{w}/przesun", json={"o": 2}).status_code == 400
    assert c.post("/atlas/raport-wskazniki/999/przesun", json={"o": 1}).status_code == 404
    assert c.get(f"/atlas/raport-gminy/{GMINA}/wskaznik/999").status_code == 404
    from atlas import baza as baza_atlasu
    for _ in range(baza_atlasu.MAKS_WSKAZNIKOW_RAPORTU - 1):
        c.post("/atlas/raport-wskazniki", json={"zmienna": 1})
    r = c.post("/atlas/raport-wskazniki", json={"zmienna": 2})
    assert r.status_code == 400 and "najwyżej" in r.get_json()["blad"]


def test_raport_gminy_blad_bdl_to_502(raport_client, monkeypatch):
    c = raport_client
    w = c.post("/atlas/raport-wskazniki", json={"zmienna": 1}).get_json()["id"]
    c.post("/atlas/raport-wskazniki", json={"zmienna": 2})  # „podobne” potrzebuje co najmniej dwóch
    monkeypatch.setattr(bdl, "szereg_gminy", _blad_bdl)
    assert c.get(f"/atlas/raport-gminy/{GMINA}/wskaznik/{w}").status_code == 502
    assert c.get(f"/atlas/raport-gminy/{GMINA}.csv").status_code == 502
    assert c.post(f"/atlas/raport-gminy/{GMINA}/opis").status_code == 502
    assert c.get(f"/atlas/raport-gminy/{GMINA}/podobne").status_code == 502
    monkeypatch.setattr(bdl, "pobierz_zmienna", _blad_bdl)
    assert c.post("/atlas/raport-wskazniki", json={"zmienna": 77}).status_code == 502  # zmiennej nie ma jeszcze w cache
    monkeypatch.setattr(bdl, "gminy_wojewodztwa", _blad_bdl)
    assert c.get("/atlas/gminy/011212000000").status_code == 502
    strona = c.get("/atlas/raport-gminy/021412345011")  # inne województwo — listy gmin nie ma w cache
    assert strona.status_code == 502 and "BDL nie odpowiada" in strona.get_data(as_text=True)


def test_raport_gminy_opis_bez_danych(raport_client, monkeypatch):
    c = raport_client
    c.post("/atlas/raport-wskazniki", json={"zmienna": 1})
    monkeypatch.setattr(bdl, "szereg_gminy", lambda zid, gid: [])
    r = c.post(f"/atlas/raport-gminy/{GMINA}/opis")
    assert r.status_code == 404 and "Brak danych" in r.get_json()["blad"]


# ---------- ETAP 235: odtwarzanie lat na mapie ----------


def test_odtwarzanie_lat(client, monkeypatch):
    dane = {2021: [("011212161011", "1261011", 10.0), ("011212105033", "1206032", 30.0)],
            2022: [("011212161011", "1261011", 20.0), ("011212105033", "1206032", 30.0)],
            2023: [("011212161011", "1261011", 40.0), ("011212105033", "1206032", 35.0)]}
    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_gmin",
                        lambda z, rok, woj: [bdl.Wartosc(i, t, t, w) for i, t, w in dane.get(rok, [])])
    w = client.get(f"/atlas/odtwarzanie?{ZAPYTANIE}&od=2020&do=2023&klasy=3&metoda=rowne").get_json()
    assert w["lata"] == [2021, 2022, 2023] and w["brakujace"] == [2020]
    assert w["wartosci"]["2021"] == {"1261011": 10.0, "1206032": 30.0}
    # wspólne klasy z wartości wszystkich lat (10–40, równe przedziały): ten sam kolor = ta sama klasa w każdym roku
    assert w["kolory"]["2021"]["1261011"] != w["kolory"]["2023"]["1261011"]
    assert w["kolory"]["2021"]["1206032"] == w["kolory"]["2022"]["1206032"]
    assert len(w["legenda"]) == 3 and w["legenda"][0][1].startswith("10")
    for zle in ("od=2023&do=2023", "od=2000&do=2023", "od=abc&do=2023", "do=2023"):
        assert client.get(f"/atlas/odtwarzanie?{ZAPYTANIE}&{zle}").status_code == 400
    monkeypatch.setattr(atlas_routes.bdl, "wartosci_dla_gmin", lambda z, rok, woj: [])
    assert client.get(f"/atlas/odtwarzanie?{ZAPYTANIE}&od=2010&do=2012").status_code == 404
