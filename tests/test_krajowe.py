"""mpzp/krajowe.py — krajowa integracja planów (KIMPZP), bez sieci."""

import pytest

from mpzp import krajowe
from mpzp.krajowe import BladKIMPZP, ObiektPlanu

CAPABILITIES = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Capability><Layer><Name>KIMPZP</Name><Title>Plany</Title><CRS>EPSG:2180</CRS><CRS>epsg:4326</CRS>
    <Layer queryable="1"><Name>wektor-pow</Name><Title>Przeznaczenie terenu</Title></Layer>
    <Layer queryable="0"><Name>raster</Name><Title>Rysunki planów</Title></Layer>
    <Layer queryable="1"><Name>granice</Name></Layer>
  </Layer></Capability>
</WMS_Capabilities>"""

GML_MAPSERVER = """<?xml version="1.0" encoding="UTF-8"?>
<msGMLOutput xmlns:gml="http://www.opengis.net/gml">
  <wektor-pow_layer>
    <gml:name>wektor-pow</gml:name>
    <wektor-pow_feature>
      <gml:boundedBy><gml:Box><gml:coordinates>21,52 21.1,52.1</gml:coordinates></gml:Box></gml:boundedBy>
      <przeznaczenie>MW</przeznaczenie>
      <opis_przeznaczenia>Tereny zabudowy mieszkaniowej wielorodzinnej z usługami w parterach budynków od strony ulicy</opis_przeznaczenia>
      <tytul>Miejscowy plan „Śródmieście Północ”</tytul>
      <uchwala>https://bip.example/u1.pdf</uchwala>
      <puste></puste>
    </wektor-pow_feature>
  </wektor-pow_layer>
  <granice_layer>
    <granice_feature><uchwala>https://bip.example/u1.pdf</uchwala><status>obowiązujący</status></granice_feature>
  </granice_layer>
</msGMLOutput>"""

TEKST_MAPSERVER = """GetFeatureInfo results:

Layer 'wektor-pow'
  Feature 1234:
    Symbol = '3MN'
    Pusty = ''
Layer 'granice'
  Feature 7:
    Status = 'obowiązujący'
"""


@pytest.fixture(autouse=True)
def czysty_cache():
    krajowe._warstwy_cache.update(czas=0.0, warstwy=None, uklady=None, glowna=None)
    yield
    krajowe._warstwy_cache.update(czas=0.0, warstwy=None, uklady=None, glowna=None)


def test_capabilities_daje_tylko_liscie_z_flaga_zapytywalnosci():
    warstwy = krajowe.sparsuj_capabilities(CAPABILITIES)
    assert [(w["nazwa"], w["zapytywalna"]) for w in warstwy] == [("wektor-pow", True), ("raster", False), ("granice", True)]
    assert warstwy[2]["tytul"] == "granice"  # brak tytułu → nazwa


def test_gml_mapservera_bez_geometrii_i_pustych_pol():
    obiekty = krajowe.sparsuj_gml(GML_MAPSERVER)
    assert [o.warstwa for o in obiekty] == ["wektor-pow", "granice"]
    assert "boundedBy" not in obiekty[0].atrybuty and "coordinates" not in obiekty[0].atrybuty
    assert "puste" not in obiekty[0].atrybuty
    assert obiekty[0].atrybuty["przeznaczenie"] == "MW"


def test_rozpoznanie_symbolu_tytulu_i_linkow():
    obiekty = krajowe.sparsuj_gml(GML_MAPSERVER)
    # długi opis w polu „opis_przeznaczenia” nie jest brany za symbol
    assert krajowe.rozpoznaj_przeznaczenie(obiekty) == "MW"
    assert krajowe.tytul_planu(obiekty) == "Miejscowy plan „Śródmieście Północ”"
    assert krajowe.linki(obiekty) == ["https://bip.example/u1.pdf"]  # bez powtórzeń


def test_pole_symbol_ma_pierwszenstwo_przed_przeznaczeniem():
    obiekty = [ObiektPlanu("a", {"przeznaczenie": "teren zieleni"}), ObiektPlanu("b", {"SYMBOL": "ZP"})]
    assert krajowe.rozpoznaj_przeznaczenie(obiekty) == "ZP"
    assert krajowe.rozpoznaj_przeznaczenie([ObiektPlanu("a", {"status": "x"})]) is None


def test_tekst_mapservera():
    obiekty = krajowe.sparsuj_tekst(TEKST_MAPSERVER)
    assert [(o.warstwa, o.atrybuty) for o in obiekty] == [
        ("wektor-pow", {"Symbol": "3MN"}),
        ("granice", {"Status": "obowiązujący"}),
    ]


def test_blad_uslugi_w_xml():
    with pytest.raises(BladKIMPZP):
        krajowe.sparsuj_gml('<ServiceExceptionReport><ServiceException>LayerNotDefined</ServiceException></ServiceExceptionReport>')


def test_plan_w_punkcie_pyta_zapytywalne_warstwy_i_przechodzi_na_tekst(monkeypatch):
    zapytania = []

    def pobierz(url, parametry):
        zapytania.append(parametry)
        if parametry["request"] == "GetCapabilities":
            return CAPABILITIES
        if parametry["info_format"] == "application/vnd.ogc.gml":
            return "GetFeatureInfo results: to nie jest XML"
        return TEKST_MAPSERVER

    monkeypatch.setattr(krajowe, "_pobierz", pobierz)

    obiekty = krajowe.plan_w_punkcie(52.2, 21.0)

    assert obiekty[0].atrybuty == {"Symbol": "3MN"}
    info = zapytania[1]
    assert info["query_layers"] == "wektor-pow,granice"
    minx, miny, maxx, maxy = map(float, info["bbox"].split(","))
    assert minx < 21.0 < maxx and miny < 52.2 < maxy  # kolejność lon, lat (WMS 1.1.1)
    assert (info["x"], info["y"]) == (50, 50)
    assert zapytania[2]["info_format"] == "text/plain"

    krajowe.plan_w_punkcie(52.2, 21.0)
    assert sum(z["request"] == "GetCapabilities" for z in zapytania) == 1  # lista warstw z cache


def test_uklady_wspolrzednych_i_mercator(monkeypatch):
    assert krajowe.uklady_wspolrzednych(CAPABILITIES) == {"EPSG:2180", "EPSG:4326"}
    assert krajowe.czy_mercator() is True  # bez odpowiedzi usługi — domyślnie tak
    monkeypatch.setattr(krajowe, "_pobierz", lambda url, parametry: CAPABILITIES)
    krajowe.warstwy()
    assert krajowe.czy_mercator() is False


def test_nazwy_warstw_bez_uslugi_to_lista_zapasowa(monkeypatch):
    def pobierz(url, parametry):
        raise BladKIMPZP("brak sieci")

    monkeypatch.setattr(krajowe, "_pobierz", pobierz)
    assert krajowe.nazwy_warstw() == (krajowe.WARSTWY_ZAPASOWE, False)


def test_blad_uslugi_w_odpowiedzi_tekstowej_to_nie_brak_planu():
    with pytest.raises(BladKIMPZP):
        krajowe.sparsuj_tekst("msWMSGetFeatureInfo(): WMS server error. Invalid layer(s)")


def test_duzo_warstw_zastepuje_warstwa_glowna(monkeypatch):
    liscie = "".join(f'<Layer queryable="1"><Name>gmina_{i}</Name></Layer>' for i in range(40))
    capabilities = (
        '<WMS_Capabilities xmlns="http://www.opengis.net/wms"><Capability>'
        f'<Layer queryable="1"><Name>plany</Name>{liscie}</Layer></Capability></WMS_Capabilities>'
    )
    zapytania = []

    def pobierz(url, parametry):
        zapytania.append(parametry)
        return capabilities if parametry["request"] == "GetCapabilities" else "<msGMLOutput/>"

    monkeypatch.setattr(krajowe, "_pobierz", pobierz)

    assert krajowe.nazwy_warstw() == (["plany"], True)
    assert krajowe.plan_w_punkcie(52.0, 19.0) == []
    assert zapytania[-1]["query_layers"] == "plany"


def test_malo_warstw_zostaja_liscie():
    assert krajowe.warstwa_glowna(CAPABILITIES) == {"nazwa": "KIMPZP", "zapytywalna": False}
    assert krajowe._ogranicz(["a", "b"], {"nazwa": "KIMPZP", "zapytywalna": False}) == ["a", "b"]
