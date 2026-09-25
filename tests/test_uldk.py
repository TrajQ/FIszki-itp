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
