from pathlib import Path

import pytest
from shapely.geometry import Point

import mpzp.wfs as wfs
from mpzp.gminy import GMINA_PILOTAZOWA

FIXTURES = Path(__file__).parent / "fixtures"


class _FejkowaOdpowiedz:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


@pytest.fixture(autouse=True)
def wyczysc_cache():
    wfs._cache.clear()
    yield
    wfs._cache.clear()


def _mockuj_jedna_strone(monkeypatch, tekst_xml):
    monkeypatch.setattr(wfs.requests, "get", lambda *a, **k: _FejkowaOdpowiedz(tekst_xml))


def test_znajduje_wydzielenie_w_pierwszym_kwadracie(monkeypatch):
    tekst = (FIXTURES / "wfs_dwa_wydzielenia.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.905, 52.405))

    assert wynik is not None
    assert wynik.atrybuty["symb_t"] == "MN"


def test_znajduje_wydzielenie_w_drugim_kwadracie(monkeypatch):
    tekst = (FIXTURES / "wfs_dwa_wydzielenia.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.925, 52.405))

    assert wynik is not None
    assert wynik.atrybuty["symb_t"] == "ZP"


def test_punkt_miedzy_wydzieleniami_zwraca_none(monkeypatch):
    tekst = (FIXTURES / "wfs_dwa_wydzielenia.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.915, 52.405))

    assert wynik is None


def test_punkt_dokladnie_na_granicy_jest_pokryty(monkeypatch):
    tekst = (FIXTURES / "wfs_dwa_wydzielenia.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    # (16.910, 52.405) leży dokładnie na prawej krawędzi pierwszego kwadratu.
    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.910, 52.405))

    assert wynik is not None
    assert wynik.atrybuty["symb_t"] == "MN"


def test_dziura_w_wydzieleniu_jest_wykluczona(monkeypatch):
    tekst = (FIXTURES / "wfs_dziura.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    w_obwarzanku = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.902, 52.502))
    w_dziurze = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.910, 52.510))

    assert w_obwarzanku is not None
    assert w_dziurze is None


def test_multisurface_obie_czesci_naleza_do_tej_samej_cechy(monkeypatch):
    tekst = (FIXTURES / "wfs_multisurface.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    czesc_a = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.902, 52.602))
    czesc_b = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.952, 52.602))

    assert czesc_a is not None and czesc_a.atrybuty["symb_t"] == "MN"
    assert czesc_b is not None and czesc_b.atrybuty["symb_t"] == "MN"


def test_pusta_warstwa_zwraca_none(monkeypatch):
    tekst = (FIXTURES / "wfs_pusta.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.905, 52.405))

    assert wynik is None


def test_blad_polaczenia_podnosi_blad_wfs(monkeypatch):
    def podnies_wyjatek(*a, **k):
        raise wfs.requests.RequestException("connection refused")

    monkeypatch.setattr(wfs.requests, "get", podnies_wyjatek)

    try:
        wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.905, 52.405))
        assert False, "oczekiwano BladWFS"
    except wfs.BladWFS:
        pass


def test_niepoprawny_xml_podnosi_blad_wfs(monkeypatch):
    _mockuj_jedna_strone(monkeypatch, "to nie jest xml")

    try:
        wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.905, 52.405))
        assert False, "oczekiwano BladWFS"
    except wfs.BladWFS:
        pass


def test_stronicowanie_pobiera_wszystkie_strony(monkeypatch):
    strona_1 = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
        'xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:app="https://gis.mpu.pl/app" '
        'numberMatched="2" numberReturned="1">'
        '<wfs:member><app:MPZP><app:symb_t>MN</app:symb_t><app:shape>'
        '<gml:MultiSurface srsName="urn:ogc:def:crs:EPSG::4326"><gml:surfaceMember>'
        '<gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>'
        "52.400 16.900 52.400 16.910 52.410 16.910 52.410 16.900 52.400 16.900"
        "</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"
        "</gml:surfaceMember></gml:MultiSurface></app:shape></app:MPZP></wfs:member>"
        "</wfs:FeatureCollection>"
    )
    strona_2 = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
        'xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:app="https://gis.mpu.pl/app" '
        'numberMatched="2" numberReturned="1">'
        '<wfs:member><app:MPZP><app:symb_t>ZP</app:symb_t><app:shape>'
        '<gml:MultiSurface srsName="urn:ogc:def:crs:EPSG::4326"><gml:surfaceMember>'
        '<gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>'
        "52.400 16.920 52.400 16.930 52.410 16.930 52.410 16.920 52.400 16.920"
        "</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"
        "</gml:surfaceMember></gml:MultiSurface></app:shape></app:MPZP></wfs:member>"
        "</wfs:FeatureCollection>"
    )

    wolania = []

    def fejkowe_get(url, params, timeout):
        wolania.append(params["startIndex"])
        tekst = strona_1 if params["startIndex"] == 0 else strona_2
        return _FejkowaOdpowiedz(tekst)

    monkeypatch.setattr(wfs.requests, "get", fejkowe_get)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.925, 52.405))

    assert wynik is not None
    assert wynik.atrybuty["symb_t"] == "ZP"
    assert wolania == [0, 1]
