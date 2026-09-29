"""MPZP: Kronika zmian — lata ortofotomap z opisu usługi WMS (ETAP 64)."""

import pytest
import requests
from shapely.geometry import box

from app import create_app
from dane import ortofoto
from dane.uldk import Dzialka
from mpzp import routes as mpzp_routes

WMS_130_CZAS = b"""<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability><Layer><Title>Ortofotomapa archiwalna</Title>
    <Layer><Name>Raster</Name><Title>Ortofotomapa</Title>
      <Dimension name="time" units="ISO8601" default="2023-06-01">1997-05-01,2004-07-12,2004-09-01,2010-06-15,2023-06-01</Dimension>
    </Layer>
  </Layer></Capability>
</WMS_Capabilities>"""

WMS_PRZEDZIAL = b"""<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms"><Capability>
  <Layer><Name>Orto</Name><Title>x</Title><Dimension name="TIME">2019-01-01/2021-12-31/P1D</Dimension></Layer>
</Capability></WMS_Capabilities>"""

WMS_111_WARSTWY = b"""<WMT_MS_Capabilities version="1.1.1"><Capability><Layer><Title>Archiwum</Title>
  <Layer><Name>orto_2015</Name><Title>Ortofotomapa</Title></Layer>
  <Layer><Name>ORTO_A</Name><Title>Ortofotomapa z roku 2009</Title></Layer>
  <Layer><Name>granice</Name><Title>Granice</Title></Layer>
</Layer></Capability></WMT_MS_Capabilities>"""


def test_lata_z_wymiaru_czasu():
    wynik = ortofoto.odczytaj_capabilities(WMS_130_CZAS)
    assert wynik["wersja"] == "1.3.0"
    assert [(r["rok"], r["time"], r["warstwa"]) for r in wynik["lata"]] == [
        (1997, "1997-05-01", "Raster"),
        (2004, "2004-09-01", "Raster"),  # z dwóch dat w roku — późniejsza
        (2010, "2010-06-15", "Raster"),
        (2023, "2023-06-01", "Raster"),
    ]
    assert not any(r["przedzial"] for r in wynik["lata"])


def test_lata_z_przedzialu_i_z_warstw():
    lata = ortofoto.odczytaj_capabilities(WMS_PRZEDZIAL)["lata"]
    assert [(r["rok"], r["time"], r["przedzial"]) for r in lata] == [
        (2019, "2019-01-01/2019-12-31", True), (2020, "2020-01-01/2020-12-31", True), (2021, "2021-01-01/2021-12-31", True)]
    wynik = ortofoto.odczytaj_capabilities(WMS_111_WARSTWY)
    assert wynik["wersja"] == "1.1.1"
    assert [(r["rok"], r["warstwa"], r["time"]) for r in wynik["lata"]] == [(2009, "ORTO_A", None), (2015, "orto_2015", None)]


@pytest.mark.parametrize("xml", [b"<html>nie</html>", b"to nie xml <<"])
def test_zly_opis_uslugi(xml):
    with pytest.raises(ortofoto.BladOrtofoto):
        ortofoto.odczytaj_capabilities(xml)


@pytest.fixture
def client(tmp_path, monkeypatch):
    ortofoto._pamiec.clear()
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


class Odpowiedz:
    def __init__(self, tresc, status=200):
        self.content, self.status_code = tresc, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def test_trasa_lat_i_pamiec(client, monkeypatch):
    zapytania = []

    def falszywy_get(url, params=None, timeout=None):
        zapytania.append((url, params))
        return Odpowiedz(WMS_130_CZAS)

    monkeypatch.setattr(ortofoto.requests, "get", falszywy_get)
    dane = client.get("/mpzp/kronika/lata").get_json()
    assert dane["url"] == ortofoto.Config.ORTO_ARCHIWALNA_WMS and len(dane["lata"]) == 4
    client.get("/mpzp/kronika/lata")
    assert len(zapytania) == 1 and zapytania[0][1]["REQUEST"] == "GetCapabilities"  # drugi raz z pamięci


def test_trasa_lat_bledy(client, monkeypatch):
    monkeypatch.setattr(ortofoto.requests, "get", lambda *a, **k: Odpowiedz(b"", 503))
    r = client.get("/mpzp/kronika/lata")
    assert r.status_code == 502 and "503" in r.get_json()["blad"]
    monkeypatch.setattr(ortofoto.requests, "get", lambda *a, **k: Odpowiedz(b'<WMS_Capabilities version="1.3.0"><Capability><Layer><Name>x</Name></Layer></Capability></WMS_Capabilities>'))
    r = client.get("/mpzp/kronika/lata")
    assert r.status_code == 502 and "ORTO_ARCHIWALNA_WMS" in r.get_json()["blad"]


def test_strona_kroniki_z_dzialka(client, monkeypatch):
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke_po_id", lambda i: Dzialka(i, box(16.9, 52.4, 16.901, 52.401), "3064011") if i == "306401_1.0001.1" else None)
    html = client.get("/mpzp/kronika?id=306401_1.0001.1").get_data(as_text=True)
    assert "306401_1.0001.1" in html and '"type": "Polygon"' in html
    assert "ULDK nie zna działki" in client.get("/mpzp/kronika?id=306401_1.0001.2").get_data(as_text=True)
    html = client.get("/mpzp/kronika?lat=52.2&lng=21.0").get_data(as_text=True)
    assert "const PUNKT = [52.2, 21.0]" in html
    assert "const PUNKT = null" in client.get("/mpzp/kronika?lat=10&lng=10").get_data(as_text=True)
