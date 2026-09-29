import pytest
from shapely.geometry import Point, Polygon

from app import create_app
import mpzp.routes as mpzp_routes
from dane.uldk import BladULDK, Dzialka
from mpzp.wfs import BladWFS, Wydzielenie


@pytest.fixture
def app(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


def _dzialka_poznan():
    return Dzialka(
        id="306401_1.0051.AR_18.14",
        geometria=Polygon([(16.93, 52.40), (16.94, 52.40), (16.94, 52.41), (16.93, 52.41)]),
        teryt_gminy="306401",
    )


def test_sprawdz_bez_wspolrzednych(client):
    odpowiedz = client.get("/mpzp/sprawdz")
    assert odpowiedz.status_code == 400
    assert "blad" in odpowiedz.get_json()


def test_sprawdz_niepoprawne_wspolrzedne(client):
    odpowiedz = client.get("/mpzp/sprawdz?lat=abc&lon=16.9")
    assert odpowiedz.status_code == 400


def test_sprawdz_brak_dzialki(client, monkeypatch):
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: None)

    odpowiedz = client.get("/mpzp/sprawdz?lat=54.6&lon=14.0")

    assert odpowiedz.status_code == 404
    assert odpowiedz.get_json()["blad"] == "Brak działki w tym miejscu."


def test_sprawdz_blad_uldk(client, monkeypatch):
    def podnies(lat, lon):
        raise BladULDK("Błąd połączenia z ULDK: timeout")

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", podnies)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.4&lon=16.9")

    assert odpowiedz.status_code == 502
    assert "blad" in odpowiedz.get_json()


def test_sprawdz_inna_gmina(client, monkeypatch):
    dzialka = Dzialka(
        id="999999_1.0001.AR_1.1",
        geometria=Polygon([(21.0, 52.2), (21.01, 52.2), (21.01, 52.21), (21.0, 52.21)]),
        teryt_gminy="999999",
    )
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: dzialka)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.2&lon=21.0")
    dane = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert dane["dzialka"]["id"] == "999999_1.0001.AR_1.1"
    assert dane["blad"] == "Ta gmina nie jest jeszcze obsługiwana (pilotaż: Poznań)."
    assert "wydzielenie" not in dane


def test_sprawdz_brak_planu(client, monkeypatch):
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_poznan())
    monkeypatch.setattr(mpzp_routes, "znajdz_przeznaczenie", lambda gmina, punkt: None)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.405&lon=16.935")
    dane = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert dane["blad"] == "Brak planu miejscowego dla tej działki."
    assert "wydzielenie" not in dane


def test_sprawdz_sukces(client, monkeypatch):
    wydzielenie = Wydzielenie(
        geometria=Polygon([(16.93, 52.40), (16.94, 52.40), (16.94, 52.41), (16.93, 52.41)]),
        atrybuty={"symb_t": "ZP", "kod_mpzp": "306401 9R1"},
    )
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_poznan())
    monkeypatch.setattr(mpzp_routes, "znajdz_przeznaczenie", lambda gmina, punkt: wydzielenie)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.405&lon=16.935")
    dane = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert "blad" not in dane
    assert dane["wydzielenie"]["atrybuty"]["symb_t"] == "ZP"
    assert dane["wydzielenie"]["przeznaczenie"] == "ZP"
    assert dane["dzialka"]["geometria"]["type"] == "Polygon"


def test_sprawdz_blad_wfs(client, monkeypatch):
    def podnies(gmina, punkt):
        raise BladWFS("Błąd połączenia z WFS gminy Poznań: timeout")

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_poznan())
    monkeypatch.setattr(mpzp_routes, "znajdz_przeznaczenie", podnies)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.405&lon=16.935")
    dane = odpowiedz.get_json()

    assert odpowiedz.status_code == 502
    assert "dzialka" in dane
    assert "blad" in dane


def test_odswiez_sukces(client, monkeypatch):
    wolania = []
    monkeypatch.setattr(mpzp_routes, "odswiez_warstwe", lambda gmina: wolania.append(gmina))

    odpowiedz = client.post("/mpzp/odswiez")

    assert odpowiedz.status_code == 200
    assert odpowiedz.get_json() == {"ok": True}
    assert len(wolania) == 1


def test_odswiez_blad(client, monkeypatch):
    def podnies(gmina):
        raise BladWFS("Błąd połączenia z WFS gminy Poznań: timeout")

    monkeypatch.setattr(mpzp_routes, "odswiez_warstwe", podnies)

    odpowiedz = client.post("/mpzp/odswiez")

    assert odpowiedz.status_code == 502
    assert "blad" in odpowiedz.get_json()


# ---------- ETAP 9: słownik symboli, wyszukiwanie po id, historia ----------

from mpzp import baza as mpzp_baza
from mpzp.symbole import opisz_symbol


@pytest.mark.parametrize(
    "symbol,oczekiwane",
    [
        ("1MN", ["MN"]),
        ("12KDL", ["KDL"]),
        ("MN/U", ["MN", "U"]),
        ("3MW,U", ["MW", "U"]),
        ("2MN1", ["MN"]),
        (None, []),
    ],
)
def test_opisz_symbol_rozpoznaje_litery(symbol, oczekiwane):
    assert [o["symbol"] for o in opisz_symbol(symbol)] == oczekiwane


def test_opisz_symbol_opisy():
    assert opisz_symbol("1MN")[0]["opis"] == "tereny zabudowy mieszkaniowej jednorodzinnej"
    assert opisz_symbol("QQ")[0]["opis"] is None


def _wydzielenie_zp():
    return Wydzielenie(
        geometria=Polygon([(16.93, 52.40), (16.94, 52.40), (16.94, 52.41), (16.93, 52.41)]),
        atrybuty={"symb_t": "4ZP/US"},
    )


def test_sprawdz_zwraca_opis_symbolu_i_zapisuje_historie(client, monkeypatch):
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_poznan())
    monkeypatch.setattr(mpzp_routes, "znajdz_przeznaczenie", lambda gmina, punkt: _wydzielenie_zp())

    dane = client.get("/mpzp/sprawdz?lat=52.405&lon=16.935").get_json()

    assert [o["symbol"] for o in dane["wydzielenie"]["opis_przeznaczenia"]] == ["ZP", "US"]
    historia = client.get("/mpzp/historia").get_json()
    assert historia[0]["dzialka_id"] == "306401_1.0051.AR_18.14"
    assert historia[0]["przeznaczenie"] == "4ZP/US"
    assert historia[0]["lat"] == 52.405


def test_historia_bez_duplikatow_i_z_limitem(client, monkeypatch):
    monkeypatch.setattr(mpzp_baza, "LIMIT_HISTORII", 3)
    with client.application.app_context():
        for i in range(5):
            mpzp_baza.zapisz_w_historii(f"306401_1.0051.{i}", "MN", 52.4, 16.9)
        mpzp_baza.zapisz_w_historii("306401_1.0051.4", "MN", 52.4, 16.9)
        ids = [w["dzialka_id"] for w in mpzp_baza.historia()]
    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert ids == ["306401_1.0051.4", "306401_1.0051.3", "306401_1.0051.2"]


def test_dzialka_po_id_sukces_uzywa_punktu_wewnatrz(client, monkeypatch):
    punkty = []
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke_po_id", lambda i: _dzialka_poznan())

    def przeznaczenie(gmina, punkt):
        punkty.append(punkt)
        return _wydzielenie_zp()

    monkeypatch.setattr(mpzp_routes, "znajdz_przeznaczenie", przeznaczenie)

    odpowiedz = client.get("/mpzp/dzialka?id=306401_1.0051.AR_18.14")

    assert odpowiedz.status_code == 200
    assert odpowiedz.get_json()["wydzielenie"]["przeznaczenie"] == "4ZP/US"
    assert _dzialka_poznan().geometria.contains(punkty[0])


def test_dzialka_po_id_bledy(client, monkeypatch):
    assert client.get("/mpzp/dzialka?id=Poznań 18/14").status_code == 400
    assert client.get("/mpzp/dzialka").status_code == 400

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke_po_id", lambda i: None)
    assert client.get("/mpzp/dzialka?id=306401_1.0051.AR_99.1").status_code == 404

    def podnies(i):
        raise BladULDK("Błąd połączenia z ULDK: timeout")

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke_po_id", podnies)
    assert client.get("/mpzp/dzialka?id=306401_1.0051.AR_99.1").status_code == 502


# ---------- ETAP 16: podpowiedzi przy wpisywaniu ----------

from dane.uldk import Podpowiedz


def test_podpowiedzi_z_historii_i_uldk_bez_duplikatow(client, monkeypatch):
    with client.application.app_context():
        mpzp_baza.zapisz_w_historii("306401_1.0051.AR_18.14", "1MN", 52.4, 16.9)
    monkeypatch.setattr(
        mpzp_routes,
        "szukaj_dzialek",
        lambda fraza: [
            Podpowiedz("306401_1.0051.AR_18.14", "Poznań", "Jeżyce", "14"),
            Podpowiedz("306401_1.0051.AR_22.14", "Poznań", "Jeżyce", "14"),
        ],
    )

    dane = client.get("/mpzp/podpowiedzi?q=AR_18").get_json()
    assert [p["id"] for p in dane["z_historii"]] == ["306401_1.0051.AR_18.14"]
    assert [p["id"] for p in dane["z_uldk"]] == ["306401_1.0051.AR_22.14"]
    assert dane["z_uldk"][0]["opis"] == "Poznań, obręb Jeżyce, działka 14"


def test_podpowiedzi_pelny_identyfikator_bez_pytania_uldk(client, monkeypatch):
    monkeypatch.setattr(mpzp_routes, "szukaj_dzialek", lambda f: pytest.fail("nie powinno pytać ULDK"))
    dane = client.get("/mpzp/podpowiedzi?q=306401_1.0051.AR_18.14").get_json()
    assert dane["z_uldk"] == [{"id": "306401_1.0051.AR_18.14", "opis": "identyfikator działki"}]


def test_podpowiedzi_bez_numeru_daje_wskazowke(client, monkeypatch):
    monkeypatch.setattr(mpzp_routes, "szukaj_dzialek", lambda f: pytest.fail("nie powinno pytać ULDK"))
    dane = client.get("/mpzp/podpowiedzi?q=Jeżyce").get_json()
    assert "numer" in dane["wskazowka"]
    assert client.get("/mpzp/podpowiedzi?q=Je").get_json() == {"z_historii": [], "z_uldk": []}


def test_podpowiedzi_blad_uldk(client, monkeypatch):
    def podnies(f):
        raise BladULDK("Błąd połączenia z ULDK: timeout")

    monkeypatch.setattr(mpzp_routes, "szukaj_dzialek", podnies)
    odpowiedz = client.get("/mpzp/podpowiedzi?q=Jeżyce 14")
    assert odpowiedz.status_code == 502
    assert "ULDK" in odpowiedz.get_json()["blad"]
