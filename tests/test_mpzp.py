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


@pytest.fixture(autouse=True)
def bez_prawdziwego_wfs(monkeypatch):
    # Udziały przeznaczeń (ETAP 20) pytają WFS o wszystkie wydzielenia
    # działki — w testach domyślnie pusto, konkretne testy podmieniają.
    monkeypatch.setattr(mpzp_routes, "znajdz_wydzielenia_dzialki", lambda gmina, geometria: [])
    # Gminy bez WFS pytają krajową integrację planów — w testach bez sieci.
    monkeypatch.setattr(mpzp_routes, "plan_krajowy", lambda lat, lon: [])


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
    assert dane["blad"].startswith("Krajowa integracja planów nie ma planu")
    assert "wydzielenie" not in dane and "plan_krajowy" not in dane


def _dzialka_warszawa():
    return Dzialka(
        id="146501_1.0001.AR_1.1",
        geometria=Polygon([(21.0, 52.2), (21.01, 52.2), (21.01, 52.21), (21.0, 52.21)]),
        teryt_gminy="146501",
    )


def test_sprawdz_gmina_bez_wfs_bierze_plan_z_integracji_krajowej(client, monkeypatch):
    from mpzp.krajowe import ObiektPlanu

    wolania = []
    obiekty = [
        ObiektPlanu("wektor-pow", {"symbol": "MN/U", "tytul": "Plan Wilanów Zachód", "tekst": "https://bip.example/uchwala.pdf"}),
    ]
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_warszawa())
    monkeypatch.setattr(mpzp_routes, "plan_krajowy", lambda lat, lon: wolania.append((lat, lon)) or obiekty)

    dane = client.get("/mpzp/sprawdz?lat=52.205&lon=21.005").get_json()

    assert wolania == [(52.205, 21.005)]
    plan = dane["plan_krajowy"]
    assert plan["przeznaczenie"] == "MN/U"
    assert [o["symbol"] for o in plan["opis_przeznaczenia"]] == ["MN", "U"]
    assert plan["tytul"] == "Plan Wilanów Zachód"
    assert plan["linki"] == ["https://bip.example/uchwala.pdf"]
    assert "blad" not in dane
    historia = client.get("/mpzp/historia").get_json()
    assert historia[0]["przeznaczenie"] == "MN/U"


def test_sprawdz_blad_integracji_krajowej(client, monkeypatch):
    from mpzp.krajowe import BladKIMPZP

    def podnies(lat, lon):
        raise BladKIMPZP("Błąd połączenia z krajową integracją planów (GUGiK): timeout.")

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_warszawa())
    monkeypatch.setattr(mpzp_routes, "plan_krajowy", podnies)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.205&lon=21.005")

    assert odpowiedz.status_code == 502
    assert "GUGiK" in odpowiedz.get_json()["blad"]
    assert odpowiedz.get_json()["dzialka"]["id"] == "146501_1.0001.AR_1.1"


def test_raport_gminy_bez_wfs_pokazuje_atrybuty_planu(client, monkeypatch):
    from mpzp.krajowe import ObiektPlanu

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke_po_id", lambda i: _dzialka_warszawa())
    monkeypatch.setattr(mpzp_routes, "plan_krajowy", lambda lat, lon: [ObiektPlanu("wektor-pow", {"oznaczenie": "1ZP", "nr_uchwaly": "XII/34/2019"})])

    html = client.get("/mpzp/raport?id=146501_1.0001.AR_1.1").get_data(as_text=True)

    assert "1ZP" in html and "XII/34/2019" in html
    assert "krajowej integracji planów" in html


def test_warstwy_krajowe_z_zapasowa_lista(client, monkeypatch):
    from mpzp import krajowe

    def podnies():
        raise krajowe.BladKIMPZP("brak sieci")

    monkeypatch.setattr(krajowe, "warstwy", podnies)
    dane = client.get("/mpzp/warstwy-krajowe").get_json()

    assert dane["plany"]["z_uslugi"] is False
    assert dane["plany"]["warstwy"] == ",".join(krajowe.WARSTWY_ZAPASOWE)
    assert dane["dzialki"]["warstwy"] == "dzialki,numery_dzialek"


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


# ---------- ETAP 20: powierzchnia, podział na przeznaczenia, raport ----------

from shapely.geometry import box

from mpzp import wfs as mpzp_wfs
from mpzp.geometria import metry_na_stopien, powierzchnia_m2, szkic_svg
from mpzp.gminy import GMINA_PILOTAZOWA


def test_powierzchnia_m2_zgodna_z_rachunkiem_recznym():
    mx, my = metry_na_stopien(52.4)
    assert 67_900 < mx < 68_100  # ok. 68 km na 1° długości na szer. Poznania
    assert 111_200 < my < 111_300
    pole = powierzchnia_m2(box(16.9, 52.4, 16.901, 52.401))
    assert pole == pytest.approx(0.001 * mx * 0.001 * my, rel=0.002)


def _dzialka_kwadrat():
    # ok. 68 m x 111 m; lewa połowa w MN, prawa w KDD
    return Dzialka(id="306401_1.0051.AR_18.14", geometria=box(16.900, 52.400, 16.901, 52.401), teryt_gminy="306401")


def _dwa_wydzielenia():
    return [
        Wydzielenie(box(16.899, 52.399, 16.9005, 52.402), {"symb_t": "1MN"}),
        Wydzielenie(box(16.9005, 52.399, 16.902, 52.402), {"symb_t": "2KDD"}),
        Wydzielenie(box(16.95, 52.45, 16.96, 52.46), {"symb_t": "ZP"}),  # daleko
    ]


def test_wydzielenia_dzialki_z_indeksu(monkeypatch):
    monkeypatch.setitem(mpzp_wfs._cache, GMINA_PILOTAZOWA.teryt_prefiks, mpzp_wfs._WarstwaGminy(_dwa_wydzielenia()))
    pary = mpzp_wfs.wydzielenia_dzialki(GMINA_PILOTAZOWA, _dzialka_kwadrat().geometria)
    assert sorted(w.atrybuty["symb_t"] for w, _ in pary) == ["1MN", "2KDD"]


def test_sprawdz_zwraca_powierzchnie_i_udzialy(client, monkeypatch):
    wydzielenia = _dwa_wydzielenia()
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_kwadrat())
    monkeypatch.setattr(mpzp_routes, "znajdz_przeznaczenie", lambda g, p: wydzielenia[0])
    monkeypatch.setattr(
        mpzp_routes,
        "znajdz_wydzielenia_dzialki",
        lambda g, geom: [(w, w.geometria.intersection(geom)) for w in wydzielenia if w.geometria.intersects(geom)],
    )

    dane = client.get("/mpzp/sprawdz?lat=52.4005&lon=16.9002").get_json()

    assert dane["dzialka"]["powierzchnia_m2"] == pytest.approx(powierzchnia_m2(_dzialka_kwadrat().geometria), rel=0.001)
    assert [u["przeznaczenie"] for u in dane["udzialy"]] == ["1MN", "2KDD"] or [u["przeznaczenie"] for u in dane["udzialy"]] == ["2KDD", "1MN"]
    assert sum(u["procent"] for u in dane["udzialy"]) == pytest.approx(100, abs=0.2)
    assert dane["udzialy"][0]["opis"][0]["opis"] is not None


def test_drobny_styk_z_sasiednim_wydzieleniem_pomijany(client, monkeypatch):
    dzialka = _dzialka_kwadrat()
    glowne = Wydzielenie(box(16.899, 52.399, 16.902, 52.402), {"symb_t": "MN"})
    styk = Wydzielenie(box(16.90099, 52.399, 16.902, 52.402), {"symb_t": "KDL"})  # ok. 1% działki
    monkeypatch.setattr(
        mpzp_routes, "znajdz_wydzielenia_dzialki", lambda g, geom: [(glowne, dzialka.geometria), (styk, styk.geometria.intersection(dzialka.geometria))]
    )
    wynik = mpzp_routes.udzialy_przeznaczen(GMINA_PILOTAZOWA, dzialka)
    assert [u["przeznaczenie"] for u in wynik] == ["MN", "KDL"]
    styk_maly = Wydzielenie(box(16.900999, 52.399, 16.902, 52.402), {"symb_t": "KDL"})  # 0,1%
    monkeypatch.setattr(
        mpzp_routes, "znajdz_wydzielenia_dzialki", lambda g, geom: [(glowne, dzialka.geometria), (styk_maly, styk_maly.geometria.intersection(dzialka.geometria))]
    )
    assert [u["przeznaczenie"] for u in mpzp_routes.udzialy_przeznaczen(GMINA_PILOTAZOWA, dzialka)] == ["MN"]


def test_raport_dzialki(client, monkeypatch):
    # zły format sprawdza prawdziwa funkcja ULDK — zanim cokolwiek podmienimy
    assert client.get("/mpzp/raport?id=zly").status_code == 400

    wydzielenia = _dwa_wydzielenia()
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke_po_id", lambda i: _dzialka_kwadrat())
    monkeypatch.setattr(
        mpzp_routes,
        "znajdz_wydzielenia_dzialki",
        lambda g, geom: [(w, w.geometria.intersection(geom)) for w in wydzielenia if w.geometria.intersects(geom)],
    )
    strona = client.get("/mpzp/raport?id=306401_1.0051.AR_18.14").get_data(as_text=True)
    assert "Raport działki ewidencyjnej" in strona
    assert "0051" in strona and "AR_18.14" in strona
    assert "1MN" in strona and "2KDD" in strona
    assert "nie jest wypisem" in strona
    assert "<path" in strona

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke_po_id", lambda i: None)
    assert client.get("/mpzp/raport?id=306401_1.0051.AR_18.14").status_code == 404


def test_szkic_svg_ma_sciezki():
    szkic = szkic_svg(box(16.9, 52.4, 16.901, 52.401), [(box(16.8995, 52.3995, 16.9005, 52.4015), 0)])
    assert szkic["dzialka"].startswith("M ")
    assert len(szkic["czesci"]) == 1
    assert szkic["viewbox"].startswith("0 0 ")


# ---------- poprawki z przeglądu ETAPów 18–21 ----------


def test_parser_naprawia_wielokat_przecinajacy_sam_siebie():
    gml = """<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2"
      xmlns:app="x" numberMatched="1" numberReturned="1"><wfs:member><app:W>
      <app:shape><gml:Polygon><gml:exterior><gml:LinearRing>
        <gml:posList>52.399 16.899 52.402 16.902 52.399 16.902 52.402 16.899 52.399 16.899</gml:posList>
      </gml:LinearRing></gml:exterior></gml:Polygon></app:shape><app:symb_t>MN</app:symb_t>
    </app:W></wfs:member></wfs:FeatureCollection>"""
    wydzielenia, _, _ = mpzp_wfs._sparsuj_kolekcje(gml, "shape")
    assert wydzielenia[0].geometria.is_valid


def test_wydzielenia_dzialki_nie_wywraca_sie_na_zlej_geometrii(monkeypatch):
    from shapely.geometry import Polygon as P

    kokarda = P([(16.899, 52.399), (16.902, 52.402), (16.902, 52.399), (16.899, 52.402)])
    dobre = Wydzielenie(box(16.899, 52.399, 16.902, 52.402), {"symb_t": "ZP"})
    monkeypatch.setitem(
        mpzp_wfs._cache, GMINA_PILOTAZOWA.teryt_prefiks, mpzp_wfs._WarstwaGminy([Wydzielenie(kokarda, {"symb_t": "MN"}), dobre])
    )
    pary = mpzp_wfs.wydzielenia_dzialki(GMINA_PILOTAZOWA, box(16.9, 52.4, 16.901, 52.401))
    assert [w.atrybuty["symb_t"] for w, _ in pary] == ["ZP"]


# ---------- ETAP 24: eksport GeoJSON ----------


def test_eksport_geojson_dzialki(client, monkeypatch):
    import json as _json

    wydzielenia = _dwa_wydzielenia()
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke_po_id", lambda i: _dzialka_kwadrat())
    monkeypatch.setattr(
        mpzp_routes,
        "znajdz_wydzielenia_dzialki",
        lambda g, geom: [(w, w.geometria.intersection(geom)) for w in wydzielenia if w.geometria.intersects(geom)],
    )
    odp = client.get("/mpzp/eksport.geojson?id=306401_1.0051.AR_18.14")
    assert odp.mimetype == "application/geo+json"
    cechy = _json.loads(odp.data)["features"]
    assert [c["properties"]["warstwa"] for c in cechy] == ["dzialka", "czesc_w_przeznaczeniu", "czesc_w_przeznaczeniu"]
    assert {c["properties"].get("przeznaczenie") for c in cechy[1:]} == {"1MN", "2KDD"}
    assert cechy[1]["properties"]["wfs_symb_t"] in {"1MN", "2KDD"}
    assert "dzialka_306401_1_0051_AR_18_14.geojson" in odp.headers["Content-Disposition"]


# ---------- ETAP 36: współrzędne i pomiar ----------


def test_sprawdz_podaje_wspolrzedne_w_ukladach_polskich(client, monkeypatch):
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_warszawa())

    dane = client.get("/mpzp/sprawdz?lat=52.2319&lon=21.0067").get_json()

    uklady = {w["epsg"]: w for w in dane["wspolrzedne"]}
    assert set(uklady) == {4326, 2180, 2178}
    # wartości referencyjne z pyproj (EPSG:2180 i 2178), X = północ
    assert uklady[2180]["x"] == pytest.approx(486991.39, abs=0.01)
    assert uklady[2180]["y"] == pytest.approx(636999.96, abs=0.01)
    assert uklady[2178]["uklad"] == "PL-2000 strefa 7"


def test_pomiar_prostokata_100_na_50_m(client):
    from mpzp.geometria import metry_na_stopien

    mx, my = metry_na_stopien(52.0)
    dx, dy = 100 / mx, 50 / my
    punkty = [[52.0, 17.0], [52.0, 17.0 + dx], [52.0 + dy, 17.0 + dx], [52.0 + dy, 17.0]]

    dwa = client.post("/mpzp/pomiar", json={"punkty": punkty[:2]}).get_json()
    assert dwa["dlugosc_m"] == pytest.approx(100, abs=0.05)
    assert "powierzchnia_m2" not in dwa

    cztery = client.post("/mpzp/pomiar", json={"punkty": punkty}).get_json()
    assert cztery["dlugosc_m"] == pytest.approx(250, abs=0.2)
    assert cztery["ostatni_odcinek_m"] == pytest.approx(100, abs=0.1)
    assert cztery["powierzchnia_m2"] == pytest.approx(5000, abs=5)
    assert cztery["obwod_m"] == pytest.approx(300, abs=0.2)
    assert "uwaga" not in cztery


def test_pomiar_obrys_przecinajacy_sie_ma_uwage(client):
    punkty = [[52.0, 17.0], [52.001, 17.001], [52.0, 17.001], [52.001, 17.0]]  # „kokardka”
    assert "uwaga" in client.post("/mpzp/pomiar", json={"punkty": punkty}).get_json()


@pytest.mark.parametrize(
    "tresc",
    [{}, {"punkty": [[52, 17]]}, {"punkty": [[52, 17], ["x", 17]]}, {"punkty": [[52, 17], [95, 17]]}, {"punkty": [[52, 17], [52, "nan"]]}, {"punkty": "abc"}],
)
def test_pomiar_zle_dane(client, tresc):
    odpowiedz = client.post("/mpzp/pomiar", json=tresc)
    assert odpowiedz.status_code == 400 and "blad" in odpowiedz.get_json()


def test_eksport_geojson_gminy_bez_wfs_ma_przeznaczenie_z_kimpzp(client, monkeypatch):
    from mpzp.krajowe import ObiektPlanu

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke_po_id", lambda i: _dzialka_warszawa())
    monkeypatch.setattr(mpzp_routes, "plan_krajowy", lambda lat, lon: [ObiektPlanu("w", {"symbol": "U", "tytul": "Plan X"})])

    cechy = client.get("/mpzp/eksport.geojson?id=146501_1.0001.AR_1.1").get_json()["features"]

    assert len(cechy) == 1
    assert cechy[0]["properties"]["przeznaczenie_kimpzp"] == "U"
    assert cechy[0]["properties"]["plan_kimpzp"] == "Plan X"
