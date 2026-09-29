import dane.uldk as uldk


class _FejkowaOdpowiedz:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_znajduje_dzialke(monkeypatch):
    tekst = (
        "0\n"
        "306401_1.0051.AR_18.14|SRID=4326;POLYGON((16.93 52.40,16.94 52.40,"
        "16.94 52.41,16.93 52.41,16.93 52.40))"
    )
    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: _FejkowaOdpowiedz(tekst))

    dzialka = uldk.znajdz_dzialke(52.405, 16.935)

    assert dzialka is not None
    assert dzialka.id == "306401_1.0051.AR_18.14"
    assert dzialka.teryt_gminy == "306401"
    minx, miny, maxx, maxy = dzialka.geometria.bounds
    assert minx == 16.93 and maxx == 16.94
    assert miny == 52.40 and maxy == 52.41


def test_brak_dzialki_pod_punktem(monkeypatch):
    tekst = (
        "-1 brak wyników\n"
        "błędny format odpowiedzi XML, usługa zwróciła odpowiedź"
        "Zbiorcza baza danych obsłużyła zapytanie. "
    )
    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: _FejkowaOdpowiedz(tekst))

    assert uldk.znajdz_dzialke(54.6, 14.0) is None


def test_blad_polaczenia_podnosi_blad_uldk(monkeypatch):
    def podnies_wyjatek(*a, **k):
        raise uldk.requests.RequestException("connection refused")

    monkeypatch.setattr(uldk.requests, "get", podnies_wyjatek)

    try:
        uldk.znajdz_dzialke(52.4, 16.9)
        assert False, "oczekiwano BladULDK"
    except uldk.BladULDK:
        pass


def test_niepoprawna_odpowiedz_podnosi_blad_uldk(monkeypatch):
    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: _FejkowaOdpowiedz("0\nto nie jest poprawny wiersz"))

    try:
        uldk.znajdz_dzialke(52.4, 16.9)
        assert False, "oczekiwano BladULDK"
    except uldk.BladULDK:
        pass


def test_dzialka_po_id(monkeypatch):
    zapytania = []
    tekst = "0\n306401_1.0051.AR_18.14|SRID=4326;POLYGON((16.93 52.40,16.94 52.40,16.94 52.41,16.93 52.40))"

    def falszywy_get(url, params, timeout):
        zapytania.append(params)
        return _FejkowaOdpowiedz(tekst)

    monkeypatch.setattr(uldk.requests, "get", falszywy_get)
    dzialka = uldk.znajdz_dzialke_po_id(" 306401_1.0051.AR_18.14 ")

    assert dzialka.id == "306401_1.0051.AR_18.14"
    assert zapytania[0]["request"] == "GetParcelById"
    assert zapytania[0]["id"] == "306401_1.0051.AR_18.14"


def test_dzialka_po_id_zly_format(monkeypatch):
    import pytest

    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: pytest.fail("nie powinno pytać ULDK"))
    for zly in ["", "18/14", "Poznań 18/14", "30640_1.0051.1"]:
        with pytest.raises(ValueError):
            uldk.znajdz_dzialke_po_id(zly)


# ---------- ETAP 16: wyszukiwanie po obrębie i numerze ----------


def test_szukaj_dzialek_wiele_wynikow(monkeypatch):
    zapytania = []
    tekst = (
        "2\n"
        "306401_1.0051.AR_18.14|Poznań|Jeżyce|14\n"
        "306401_1.0051.AR_22.14|Poznań|Jeżyce|14\n"
    )

    def falszywy_get(url, params, timeout):
        zapytania.append(params)
        return _FejkowaOdpowiedz(tekst)

    monkeypatch.setattr(uldk.requests, "get", falszywy_get)
    wyniki = uldk.szukaj_dzialek("  Jeżyce   14 ")

    assert [w.id for w in wyniki] == ["306401_1.0051.AR_18.14", "306401_1.0051.AR_22.14"]
    assert wyniki[0].obreb == "Jeżyce" and wyniki[0].numer == "14" and wyniki[0].gmina == "Poznań"
    assert zapytania[0]["request"] == "GetParcelByIdOrNr"
    assert zapytania[0]["id"] == "Jeżyce 14"  # nadmiarowe spacje usunięte


def test_szukaj_dzialek_status_zero_i_brak_wynikow(monkeypatch):
    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: _FejkowaOdpowiedz("0\n306401_1.0051.AR_18.14|Poznań|Jeżyce|14"))
    assert len(uldk.szukaj_dzialek("Jeżyce 14")) == 1

    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: _FejkowaOdpowiedz("-1 brak wyników"))
    assert uldk.szukaj_dzialek("Nigdzie 1") == []


def test_szukaj_dzialek_limit(monkeypatch):
    linie = "\n".join(f"306401_1.0051.{i}|Poznań|Jeżyce|{i}" for i in range(40))
    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: _FejkowaOdpowiedz(f"40\n{linie}"))
    assert len(uldk.szukaj_dzialek("Jeżyce 1")) == uldk.MAKS_PODPOWIEDZI


def test_blad_sieci_ma_czytelny_komunikat(monkeypatch):
    import pytest
    import requests

    def brak_sieci(*a, **k):
        raise requests.ConnectionError("HTTPSConnectionPool(host='uldk.gugik.gov.pl'): Max retries exceeded (ProxyError)")

    monkeypatch.setattr(uldk.requests, "get", brak_sieci)
    with pytest.raises(uldk.BladULDK) as blad:
        uldk.znajdz_dzialke(52.4, 16.9)
    assert "brak połączenia z usługą" in str(blad.value)
    assert "HTTPSConnectionPool" not in str(blad.value)
