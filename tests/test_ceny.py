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


# ---------- ETAP 104: transakcje z Rejestru Cen Nieruchomości ----------

import io  # noqa: E402
import math  # noqa: E402
import sqlite3  # noqa: E402
import struct  # noqa: E402

from shapely.geometry import Point, Polygon  # noqa: E402

from ceny import rcn, trasy_rcn  # noqa: E402
from mpzp import uklady  # noqa: E402


def geometria_gpkg(lat, lon, koperta=True):
    """Blob GeoPackage: nagłówek „GP”, opcjonalna koperta, WKB punktu w PL-1992 (x = wschód)."""
    p = uklady.pl1992(lat, lon)
    x, y = p["y"], p["x"]
    naglowek = b"GP" + bytes([0, 0b011 if koperta else 0b001]) + struct.pack("<i", 2180)
    if koperta:
        naglowek += struct.pack("<4d", x - 5, x + 5, y - 5, y + 5)
    return naglowek + Point(x, y).wkb


def plik_rcn(sciezka, wiersze, tabela="transakcje_lokale"):
    db = sqlite3.connect(sciezka)
    db.execute("CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, srs_id INTEGER)")
    db.execute("INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', 2180)", (tabela,))
    kolumny = ["tran_lokalny_id_iip", "lok_id_lokalu", "dok_data", "tran_rodzaj_trans", "tran_rodzaj_rynku", "nier_udzial",
               "lok_funkcja", "lok_cena_brutto", "nier_cena_brutto", "tran_cena_brutto", "lok_pow_uzyt", "lok_liczba_izb", "lok_nr_kond", "geom"]
    db.execute(f"CREATE TABLE {tabela} ({', '.join(kolumny)})")
    for w in wiersze:
        db.execute(f"INSERT INTO {tabela} VALUES ({', '.join('?' * len(kolumny))})", [w.get(k) for k in kolumny])
    db.commit()
    db.close()


def lokal(nr, **zmiany):
    w = {"tran_lokalny_id_iip": f"T{nr}", "lok_id_lokalu": f"L{nr}", "dok_data": "2024-05-10", "tran_rodzaj_trans": "wolnyRynek",
         "tran_rodzaj_rynku": "wtorny", "nier_udzial": "1/1", "lok_funkcja": "mieszkalna", "lok_cena_brutto": 600000,
         "lok_pow_uzyt": 50, "lok_liczba_izb": 2, "geom": geometria_gpkg(50.06, 19.94)}
    w.update(zmiany)
    return w


def test_czytanie_pliku_rcn(tmp_path):
    sciezka = str(tmp_path / "rcn.gpkg")
    plik_rcn(sciezka, [
        lokal(1),
        lokal(2, lok_cena_brutto=None, nier_cena_brutto=None, tran_cena_brutto=450000, dok_data="2023-11-30", tran_rodzaj_rynku="pierwotny",
              geom=geometria_gpkg(50.07, 19.95, koperta=False)),
        lokal(3, lok_cena_brutto=None, tran_cena_brutto=900000),  # transakcja z dwoma lokalami — cena dotyczy obu
        lokal(3, lok_id_lokalu="L3b", lok_cena_brutto=None, tran_cena_brutto=900000),
        lokal(4, lok_funkcja="użytkowa"),
        lokal(5, nier_udzial="1/2"),
        lokal(6, lok_pow_uzyt=3),
        lokal(7, lok_cena_brutto=1000),  # 20 zł/m²
        lokal(8, dok_data=None),
        lokal(1),  # ten sam lokal w tej samej transakcji drugi raz
    ])
    w = rcn.czytaj_plik(sciezka)
    assert [(l["cena_m2"], l["rynek"], l["kwartal"]) for l in w["lokale"]] == [(12000.0, "wtórny", 2), (9000.0, "pierwotny", 4)]
    assert w["odrzucone"] == {"niemieszkalne": 1, "udział w lokalu": 1, "bez ceny lokalu": 2, "brak daty": 1,
                              "nierealna powierzchnia": 1, "nierealna cena za m²": 1}
    l1, l2 = w["lokale"]
    assert l1["lat"] == pytest.approx(50.06, abs=1e-6) and l1["lng"] == pytest.approx(19.94, abs=1e-6)  # koperta
    assert l2["lat"] == pytest.approx(50.07, abs=1e-6)  # bez koperty — z WKB
    zly = str(tmp_path / "zly.gpkg")
    plik_rcn(zly, [lokal(1)], tabela="transakcje_budynki")
    with pytest.raises(rcn.BladPliku, match="nie ma tabeli"):
        rcn.czytaj_plik(zly)
    (tmp_path / "tekst.gpkg").write_text("to nie baza")
    with pytest.raises(rcn.BladPliku):
        rcn.czytaj_plik(str(tmp_path / "tekst.gpkg"))


def test_statystyki_rcn():
    lokale = [{"data": f"2024-0{k}-01", "rok": 2024, "kwartal": (k - 1) // 3 + 1, "rynek": "wtórny", "rodzaj": "", "pow_m2": 50.0,
               "cena": c * 50, "cena_m2": float(c), "izby": i, "lat": 50.0 + k / 100, "lng": 19.9} for k, c, i in
              [(1, 10000, 1), (2, 11000, 2), (4, 12000, 2), (5, 13000, 3), (7, 20000, 5)]]
    s = rcn.statystyki(lokale)
    assert s["liczba"] == 5 and s["mediana_m2"] == 12000 and (s["q1_m2"], s["q3_m2"]) == (11000, 13000)
    assert [(t["kwartal"], t["liczba"], t["mediana_m2"]) for t in s["trend"]] == [(1, 2, 10500), (2, 2, 12500), (3, 1, 20000)]
    assert [(i["nazwa"], i["liczba"]) for i in s["grupy"]] == [("1", 1), ("2", 2), ("3", 1), ("4+", 1)]
    assert sum(h["liczba"] for h in s["histogram"]) >= 4
    m = rcn.punkty_mapy(lokale)
    assert len(m["punkty"]) == 5 and len(m["progi"]) == 4 and m["punkty"][0][3] == "2024-07-01"  # najnowsze najpierw
    assert rcn.statystyki([]) is None


def test_trasy_transakcji(client, tmp_path, monkeypatch):
    pobrane = tmp_path / "Pobrane"
    pobrane.mkdir()
    plik_rcn(str(pobrane / "rcn_1261.gpkg"), [lokal(i, lok_cena_brutto=500000 + 10000 * i, dok_data=f"202{3 + i % 2}-0{1 + i % 9}-15",
                                                     tran_rodzaj_rynku="pierwotny" if i % 3 == 0 else "wtorny") for i in range(1, 30)])
    monkeypatch.setattr(trasy_rcn, "katalogi_pobranych", lambda: [str(pobrane)])
    strona = client.get("/ceny/transakcje").get_data(as_text=True)
    assert "rcn_1261.gpkg" in strona and "Importuj" in strona
    assert client.post("/ceny/transakcje/import", data={"sciezka": "/etc/passwd"}).status_code == 400  # tylko pliki z listy
    odp = client.post("/ceny/transakcje/import", data={"sciezka": str(pobrane / "rcn_1261.gpkg")})
    assert odp.status_code == 302 and "plik=1" in odp.headers["Location"]
    d = client.get("/ceny/transakcje/1/dane").get_json()
    assert d["statystyki"]["liczba"] == 29 and d["lata"] == [2023, 2024] and d["listy"]["rodzaj"][0]["wartosc"] == "wolnyRynek"
    pierwotny = client.get("/ceny/transakcje/1/dane?rynek=pierwotny&od=2024").get_json()["statystyki"]
    assert 0 < pierwotny["liczba"] < 29
    assert client.get("/ceny/transakcje/1/dane?rynek=x").status_code == 400
    csv = client.get("/ceny/transakcje/1.csv?rynek=pierwotny").get_data(as_text=True)
    wszystkie_pierwotne = client.get("/ceny/transakcje/1/dane?rynek=pierwotny").get_json()["statystyki"]["liczba"]
    assert csv.startswith("﻿data;rynek;") and csv.count(";pierwotny;") == wszystkie_pierwotne
    # wgranie przez przeglądarkę (mały plik)
    dane = (pobrane / "rcn_1261.gpkg").read_bytes()
    odp = client.post("/ceny/transakcje/import", data={"plik": (io.BytesIO(dane), "maly.gpkg")}, content_type="multipart/form-data")
    assert "plik=2" in odp.headers["Location"]
    assert client.post("/ceny/transakcje/2/usun").status_code == 302 and client.get("/ceny/transakcje/2/dane").status_code == 404
    assert "Transakcje (RCN)" in client.get("/ceny/").get_data(as_text=True)


# ---------- ETAP 105: obszary do porównania i raport ----------


def prostokat(lng1, lat1, lng2, lat2):
    return {"type": "Polygon", "coordinates": [[[lng1, lat1], [lng2, lat1], [lng2, lat2], [lng1, lat2], [lng1, lat1]]]}


def test_obszary_rcn():
    with pytest.raises(rcn.BladPliku):
        rcn.sprawdz_obszar({"type": "Point", "coordinates": [19.9, 50.0]})
    with pytest.raises(rcn.BladPliku):
        rcn.sprawdz_obszar(prostokat(2.0, 48.0, 2.1, 48.1))  # Paryż
    with pytest.raises(rcn.BladPliku):
        rcn.sprawdz_obszar("nie geometria")
    # „kokarda” (samoprzecięcie) zostaje naprawiona, a nie odrzucona
    kokarda = {"type": "Polygon", "coordinates": [[[19.9, 50.0], [20.0, 50.1], [20.0, 50.0], [19.9, 50.1], [19.9, 50.0]]]}
    assert rcn.sprawdz_obszar(kokarda)["type"] in ("Polygon", "MultiPolygon")

    lokale = [{"rok": r, "cena_m2": float(c), "pow_m2": 50.0, "cena": c * 50, "lat": lat, "lng": 19.95}
              for r, c, lat in [(2023, 10000, 50.01), (2024, 12000, 50.02), (2024, 14000, 50.03),
                                (2023, 20000, 50.11), (2024, 22000, 50.12), (2024, 9000, None)]]
    poludnie = {"id": 1, "nazwa": "Południe", "geometria": prostokat(19.9, 50.0, 20.0, 50.05)}
    polnoc = {"id": 2, "nazwa": "Północ", "geometria": prostokat(19.9, 50.1, 20.0, 50.15)}
    puste = {"id": 3, "nazwa": "Puste", "geometria": prostokat(21.0, 52.0, 21.1, 52.1)}
    assert len(rcn.w_obszarze(lokale, poludnie["geometria"])) == 3  # lokal bez położenia pominięty
    p = rcn.porownanie(lokale, [poludnie, polnoc, puste])
    assert p["calosc"]["liczba"] == 6 and p["calosc"]["mediana_m2"] == 13000
    a, b, c = p["obszary"]
    assert (a["liczba"], a["mediana_m2"], a["lata"]) == (3, 12000, {2023: 10000, 2024: 13000})
    assert a["wobec_calosci_proc"] == pytest.approx(100 * (12000 / 13000 - 1))
    assert (b["liczba"], b["mediana_m2"]) == (2, 21000) and b["kolor"] != a["kolor"]
    assert c["liczba"] == 0 and "wobec_calosci_proc" not in c
    assert p["lata"] == [2023, 2024]

    svg = rcn.mapa_svg(lokale, [poludnie, polnoc], [11000, 13000, 15000, 21000], rcn.KOLORY_KLAS)
    assert svg.startswith("<svg") and svg.count("<circle") == 5 + 2 and svg.count("<path") >= 2 + 1
    assert "Południe" not in svg  # nazwy tylko w legendzie
    assert "brak transakcji" in rcn.mapa_svg([], [], [], rcn.KOLORY_KLAS)


def test_trasy_obszarow_i_raport(client, tmp_path, monkeypatch):
    pobrane = tmp_path / "Pobrane"
    pobrane.mkdir()
    plik_rcn(str(pobrane / "rcn.gpkg"), [lokal(i, lok_cena_brutto=500000 + 10000 * i,
                                              geom=geometria_gpkg(50.01 + (0.1 if i > 5 else 0), 19.95)) for i in range(1, 11)])
    monkeypatch.setattr(trasy_rcn, "katalogi_pobranych", lambda: [str(pobrane)])
    client.post("/ceny/transakcje/import", data={"sciezka": str(pobrane / "rcn.gpkg")})
    url = "/ceny/transakcje/1/obszary"
    assert client.post(url, json={"nazwa": "Stare Miasto", "geometria": prostokat(19.9, 50.0, 20.0, 50.05)}).status_code == 201
    assert client.post(url, json={"nazwa": "  ", "geometria": prostokat(19.9, 50.0, 20.0, 50.05)}).status_code == 400
    assert client.post(url, json={"nazwa": "X", "geometria": prostokat(2.0, 48.0, 2.1, 48.1)}).status_code == 400
    assert client.post("/ceny/transakcje/99/obszary", json={"nazwa": "X", "geometria": prostokat(19.9, 50.0, 20.0, 50.05)}).status_code == 404
    d = client.get("/ceny/transakcje/1/dane").get_json()
    assert [o["nazwa"] for o in d["obszary"]] == ["Stare Miasto"] and d["porownanie"]["obszary"][0]["liczba"] == 5
    obszar_id = d["obszary"][0]["id"]
    assert client.put(f"/ceny/transakcje/obszary/{obszar_id}", json={"nazwa": "Kazimierz"}).status_code == 200
    assert client.put("/ceny/transakcje/obszary/999", json={"nazwa": "X"}).status_code == 404
    for i in range(rcn.MAKS_OBSZAROW - 1):
        client.post(url, json={"nazwa": f"O{i}", "geometria": prostokat(19.9, 50.1, 20.0, 50.15)})
    odp = client.post(url, json={"nazwa": "za dużo", "geometria": prostokat(19.9, 50.1, 20.0, 50.15)})
    assert odp.status_code == 400 and "Najwyżej" in odp.get_json()["blad"]

    raport = client.get("/ceny/transakcje/1/raport?rynek=wtórny").get_data(as_text=True)
    assert "Porównanie obszarów" in raport and "Kazimierz" in raport and "<svg" in raport and "rynek wtórny" in raport
    assert client.get("/ceny/transakcje/1/raport?izby=9").status_code == 400
    assert client.get("/ceny/transakcje/99/raport").status_code == 404

    assert client.delete(f"/ceny/transakcje/obszary/{obszar_id}").status_code == 200
    assert client.delete(f"/ceny/transakcje/obszary/{obszar_id}").status_code == 404
    client.post("/ceny/transakcje/1/usun")  # obszary znikają razem z plikiem (ON DELETE CASCADE)
    from ceny import baza
    with client.application.app_context():
        assert baza.obszary_rcn(1) == []


# ---------- ETAP 106: działki ----------


def wielobok_gpkg(lat, lon, bok):
    """Blob GeoPackage: kwadrat bok × bok metrów w PL-1992 (x = wschód), z kopertą."""
    p = uklady.pl1992(lat, lon)
    x, y = p["y"], p["x"]
    kwadrat = Polygon([(x, y), (x + bok, y), (x + bok, y + bok), (x, y + bok)])
    naglowek = b"GP" + bytes([0, 0b011]) + struct.pack("<i", 2180) + struct.pack("<4d", x, x + bok, y, y + bok)
    return naglowek + kwadrat.wkb


KOLUMNY_DZIALEK = ["tran_lokalny_id_iip", "dzi_id_dzialki", "dok_data", "tran_rodzaj_trans", "tran_rodzaj_rynku", "nier_udzial",
                   "nier_rodzaj", "dzi_cena_brutto", "nier_cena_brutto", "tran_cena_brutto", "dzi_pow_ewid", "dzi_przezn_wmpzp",
                   "dzi_sposob_uzyt", "geom"]


def dodaj_dzialki(sciezka, wiersze):
    """Dopisuje do pliku RCN tabelę transakcje_dzialki (plik może już mieć lokale)."""
    db = sqlite3.connect(sciezka)
    db.execute("CREATE TABLE IF NOT EXISTS gpkg_geometry_columns (table_name TEXT, column_name TEXT, srs_id INTEGER)")
    db.execute("INSERT INTO gpkg_geometry_columns VALUES ('transakcje_dzialki', 'geom', 2180)")
    db.execute(f"CREATE TABLE transakcje_dzialki ({', '.join(KOLUMNY_DZIALEK)})")
    for w in wiersze:
        db.execute(f"INSERT INTO transakcje_dzialki VALUES ({', '.join('?' * len(KOLUMNY_DZIALEK))})", [w.get(k) for k in KOLUMNY_DZIALEK])
    db.commit()
    db.close()


def dzialka(tran, nr, bok=30, **zmiany):
    w = {"tran_lokalny_id_iip": tran, "dzi_id_dzialki": f"121201_1.0001.{nr}", "dok_data": "2024-03-01", "tran_rodzaj_trans": "wolnyRynek",
         "tran_rodzaj_rynku": "wtorny", "nier_udzial": "1/1", "nier_rodzaj": "gruntowaNiezabudowana",
         "dzi_przezn_wmpzp": "budownictwoMieszkanioweJednorodzinne", "dzi_sposob_uzyt": "B", "dzi_pow_ewid": 0.09,
         "geom": wielobok_gpkg(50.0 + nr / 1000, 19.9, bok)}
    w.update(zmiany)
    return w


def test_czytanie_dzialek(tmp_path):
    sciezka = str(tmp_path / "rcn.gpkg")
    plik_rcn(sciezka, [lokal(1)])
    dodaj_dzialki(sciezka, [
        dzialka("T1", 1, dzi_cena_brutto=200000),                          # 900 m², własna cena
        dzialka("T1", 1, dzi_cena_brutto=200000),                          # ta sama działka drugi raz
        dzialka("T2", 2, bok=20, tran_cena_brutto=160000),                 # dwie działki sprzedane razem: 800 m²
        dzialka("T2", 3, bok=20, tran_cena_brutto=160000, dzi_przezn_wmpzp="zieleń"),
        dzialka("T3", 4, bok=50, nier_cena_brutto=50000, tran_cena_brutto=999999, nier_rodzaj="gruntowaZabudowana"),  # jedna działka: cena nieruchomości
        dzialka("T4", 5, dzi_cena_brutto=90000),
        dzialka("T4", 6, tran_cena_brutto=300000),                         # cena transakcji obejmuje też działkę 5 — nie do rozdzielenia
        dzialka("T5", 7, nier_udzial="1/2", dzi_cena_brutto=100000),
        dzialka("T6", 8, geom=None, dzi_cena_brutto=100000),
        dzialka("T7", 9, bok=100, dzi_cena_brutto=100),                     # 0,01 zł/m²
        dzialka("T8", 10, dok_data=None, dzi_cena_brutto=100000),
    ])
    w = rcn.czytaj_plik(sciezka)
    assert len(w["lokale"]) == 1
    assert sorted(round(x["pow_m2"]) for x in w["dzialki"]) == [800, 900, 900, 2500]  # T1 i działka 5 z T4
    d = {round(x["pow_m2"]): x for x in w["dzialki"]}
    t2 = d[800]
    assert (t2["cena_m2"], t2["dzialek"], t2["przeznaczenie"]) == (200.0, 2, "różne")
    assert d[2500]["cena_m2"] == 20.0 and d[2500]["nieruchomosc"] == "gruntowa zabudowana"
    t1 = next(x for x in w["dzialki"] if x["cena"] == 200000)
    assert t1["cena_m2"] == pytest.approx(222.22, abs=0.01) and t1["przeznaczenie"] == "budownictwo mieszkaniowe jednorodzinne"
    assert t1["lat"] == pytest.approx(50.001, abs=0.001) and t1["lng"] == pytest.approx(19.9, abs=0.001)
    assert w["odrzucone_dzialki"] == {"udział w działce": 1, "brak daty": 1, "brak obrysu działki": 1, "bez ceny działki": 1,
                                      "nierealna cena za m²": 1}
    # sam plik działek (bez tabeli lokali) też się czyta
    tylko = str(tmp_path / "dzialki.gpkg")
    dodaj_dzialki(tylko, [dzialka("T1", 1, dzi_cena_brutto=200000)])
    assert len(rcn.czytaj_plik(tylko)["dzialki"]) == 1 and rcn.czytaj_plik(tylko)["lokale"] == []
    s = rcn.statystyki(w["dzialki"])
    assert [g["nazwa"] for g in s["grupy"]][0] == "budownictwo mieszkaniowe jednorodzinne"


def test_trasy_dzialek(client, tmp_path, monkeypatch):
    pobrane = tmp_path / "Pobrane"
    pobrane.mkdir()
    sciezka = str(pobrane / "rcn.gpkg")
    plik_rcn(sciezka, [lokal(1)])
    dodaj_dzialki(sciezka, [dzialka(f"T{i}", i, dzi_cena_brutto=100000 + 20000 * i, dok_data=f"202{3 + i % 2}-05-01",
                                     dzi_przezn_wmpzp="zieleń" if i % 4 == 0 else "budownictwoMieszkaniowe",
                                     nier_rodzaj="gruntowaZabudowana" if i % 5 == 0 else "gruntowaNiezabudowana") for i in range(1, 21)])
    monkeypatch.setattr(trasy_rcn, "katalogi_pobranych", lambda: [str(pobrane)])
    odp = client.post("/ceny/transakcje/import", data={"sciezka": sciezka})
    assert "plik=1" in odp.headers["Location"]
    strona = client.get("/ceny/transakcje?plik=1&co=dzialki").get_data(as_text=True)
    assert "Przeznaczenie w planie" in strona and "1 lokali · 20 działek" in strona and "name=\"izby\"" not in strona
    d = client.get("/ceny/transakcje/1/dane?co=dzialki").get_json()
    assert d["statystyki"]["liczba"] == 20 and d["co"] == "dzialki"
    assert [w["wartosc"] for w in d["listy"]["przeznaczenie"]] == ["budownictwo mieszkaniowe", "zieleń"]
    assert d["statystyki"]["grupy"][0] == {**d["statystyki"]["grupy"][0], "nazwa": "budownictwo mieszkaniowe", "liczba": 15}
    zielen = client.get("/ceny/transakcje/1/dane?co=dzialki&przeznaczenie=zieleń&nieruchomosc=gruntowa niezabudowana").get_json()
    assert zielen["statystyki"]["liczba"] == 4  # 4, 8, 12, 16 — bez 20 (zabudowana)
    assert client.get("/ceny/transakcje/1/dane").get_json()["statystyki"]["liczba"] == 1  # lokale dalej osobno
    assert client.get("/ceny/transakcje/1/dane?co=budynki").status_code == 400
    csv = client.get("/ceny/transakcje/1.csv?co=dzialki").get_data(as_text=True)
    assert "przeznaczenie;uzytek;nieruchomosc;dzialek" in csv and csv.count("zieleń") == 5
    client.post("/ceny/transakcje/1/obszary", json={"nazwa": "Południe", "geometria": prostokat(19.8, 49.9, 20.0, 50.01)})
    raport = client.get("/ceny/transakcje/1/raport?co=dzialki&nieruchomosc=gruntowa niezabudowana").get_data(as_text=True)
    assert "Ceny transakcyjne działek" in raport and "Według przeznaczenia w planie" in raport and "Południe" in raport
    assert "nieruchomość: gruntowa niezabudowana" in raport


def test_migracja_starej_bazy(tmp_path):
    """Baza z ETAPu 104/105 (rcn_pliki bez kolumn działek) dostaje je przy starcie."""
    (tmp_path / "ceny").mkdir()
    db = sqlite3.connect(tmp_path / "ceny" / "ceny.db")
    db.execute("CREATE TABLE rcn_pliki (id INTEGER PRIMARY KEY AUTOINCREMENT, nazwa TEXT NOT NULL, data_importu TEXT NOT NULL, liczba INTEGER NOT NULL, odrzucone TEXT NOT NULL)")
    db.execute("INSERT INTO rcn_pliki (nazwa, data_importu, liczba, odrzucone) VALUES ('stary.gpkg', '2026-09-01T10:00:00', 5, '{}')")
    db.commit()
    db.close()
    app = create_app(instance_path=str(tmp_path))
    with app.app_context():
        from ceny import baza
        stary = baza.plik_rcn(1)
    assert stary["liczba_dzialek"] == 0 and stary["odrzucone_dzialki"] == {}
    with app.test_client() as c:
        assert "W tym imporcie nie ma działek" in c.get("/ceny/transakcje?plik=1&co=dzialki").get_data(as_text=True)


# ---------- ETAP 107: podobne transakcje ----------


def test_podobne():
    assert rcn.odleglosc_m(50.0, 19.9, 50.009, 19.9) == pytest.approx(1000.8, abs=1)  # 0,009° szerokości ≈ 1 km
    assert rcn.odleglosc_m(50.0, 19.9, 50.0, 20.0) == pytest.approx(7147, rel=0.002)  # 0,1° długości na 50° N
    rekordy = [{"data": f"2024-0{i}-01", "rynek": "wtórny", "pow_m2": p, "cena": c * p, "cena_m2": float(c), "izby": 2,
                "lat": 50.0 + d / 111_195, "lng": 19.9} for i, (p, c, d) in enumerate(
                    [(50, 10000, 100), (52, 12000, 300), (45, 11000, 600), (80, 20000, 200), (48, 30000, 1500)], start=1)]
    rekordy.append({**rekordy[0], "lat": None, "lng": None})
    w = rcn.podobne(rekordy, 50.0, 19.9, 1000, 50, 0.2)
    assert w["liczba"] == 3 and not w["wystarczy"]  # 80 m² poza tolerancją, 1,5 km poza promieniem, bez położenia pominięty
    assert [t["odleglosc_m"] for t in w["transakcje"]] == [100, 300, 600]
    assert w["mediana_m2"] == 11000 and w["szacunek"] == 11000 * 50 and (w["q1_m2"], w["q3_m2"]) == (10500, 11500)
    pusto = rcn.podobne(rekordy, 52.2, 21.0, 1000, 50, 0.2)  # Warszawa — nic w promieniu
    assert pusto["liczba"] == 0 and pusto["transakcje"] == [] and "mediana_m2" not in pusto


def test_trasa_podobnych(client, tmp_path, monkeypatch):
    pobrane = tmp_path / "Pobrane"
    pobrane.mkdir()
    sciezka = str(pobrane / "rcn.gpkg")
    plik_rcn(sciezka, [lokal(i, lok_pow_uzyt=50 + i, lok_liczba_izb=2 + i % 2, lok_cena_brutto=(50 + i) * 10000,
                             geom=geometria_gpkg(50.06 + i / 10000, 19.94)) for i in range(1, 11)])
    dodaj_dzialki(sciezka, [dzialka(f"T{i}", i, dzi_cena_brutto=100000) for i in range(1, 4)])
    monkeypatch.setattr(trasy_rcn, "katalogi_pobranych", lambda: [str(pobrane)])
    client.post("/ceny/transakcje/import", data={"sciezka": sciezka})
    url = "/ceny/transakcje/1/podobne?lat=50.06&lng=19.94&pow=55&promien=500&tolerancja=0.2"
    w = client.get(url).get_json()
    assert w["liczba"] == 10 and w["wystarczy"] and w["mediana_m2"] == 10000
    assert client.get(url + "&izby=3").get_json()["liczba"] == 5  # filtry strony obowiązują
    assert client.get(url.replace("promien=500", "promien=333")).status_code == 400
    assert client.get(url.replace("lat=50.06", "lat=40")).status_code == 400
    assert client.get(url.replace("pow=55", "pow=")).status_code == 400
    assert client.get("/ceny/transakcje/9/podobne").status_code == 404
    dz = client.get("/ceny/transakcje/1/podobne?co=dzialki&lat=50.002&lng=19.9&pow=900&promien=1000&tolerancja=0.3").get_json()
    assert dz["liczba"] == 3 and dz["transakcje"][0]["przeznaczenie"] == "budownictwo mieszkaniowe jednorodzinne"
    assert "Podobne transakcje" in client.get("/ceny/transakcje?plik=1").get_data(as_text=True)


# ---------- ETAP 108: heksagony H3 ----------


def test_heksagony():
    import h3
    # 6 transakcji w jednym miejscu, 2 obok (osobna komórka), 1 bez położenia
    rekordy = [{"cena_m2": float(c), "lat": 50.06, "lng": 19.94} for c in (10000, 11000, 12000, 13000, 14000, 30000)]
    rekordy += [{"cena_m2": 9000.0, "lat": 50.1, "lng": 20.1}] * 2 + [{"cena_m2": 1.0, "lat": None, "lng": None}]
    w = rcn.heksagony(rekordy, 8, 5)
    assert len(w["komorki"]) == 1 and w["ukryte"] == 1 and w["transakcji_w_ukrytych"] == 2
    k = w["komorki"][0]
    assert k["h3"] == h3.latlng_to_cell(50.06, 19.94, 8) and k["liczba"] == 6 and k["mediana_m2"] == 12500
    assert len(k["granica"]) == 6 and w["krawedz_m"] == 530 and w["progi"] == []  # za mało komórek na kwintyle
    assert len(rcn.heksagony(rekordy, 8, 2)["komorki"]) == 2


def test_trasa_heksagonow(client, tmp_path, monkeypatch):
    pobrane = tmp_path / "Pobrane"
    pobrane.mkdir()
    sciezka = str(pobrane / "rcn.gpkg")
    plik_rcn(sciezka, [lokal(i, lok_cena_brutto=500000 + 1000 * i, tran_rodzaj_rynku="pierwotny" if i < 4 else "wtorny",
                             geom=geometria_gpkg(50.06 + (i % 3) * 0.02, 19.94)) for i in range(1, 16)])
    monkeypatch.setattr(trasy_rcn, "katalogi_pobranych", lambda: [str(pobrane)])
    client.post("/ceny/transakcje/import", data={"sciezka": sciezka})
    w = client.get("/ceny/transakcje/1/heksagony?rozdzielczosc=8&minimum=5").get_json()
    assert [k["liczba"] for k in w["komorki"]] == [5, 5, 5]
    assert client.get("/ceny/transakcje/1/heksagony?rozdzielczosc=8&minimum=5&rynek=pierwotny").get_json()["ukryte"] == 3  # filtry strony
    assert client.get("/ceny/transakcje/1/heksagony?rozdzielczosc=12&minimum=5").status_code == 400
    assert client.get("/ceny/transakcje/1/heksagony?rozdzielczosc=8&minimum=4").status_code == 400
    assert client.get("/ceny/transakcje/9/heksagony?rozdzielczosc=8&minimum=5").status_code == 404
    assert "heksagony (mediana)" in client.get("/ceny/transakcje?plik=1").get_data(as_text=True)


# ---------- ETAP 109: ceny w okolicy działki i obszaru ----------


def test_okolica():
    rekordy = [{"cena_m2": float(c), "pow_m2": 50.0, "data": f"202{r}-01-01", "rok": 2020 + r, "lat": 50.0 + d / 111_195, "lng": 19.9}
               for c, r, d in [(10000, 3, 0), (12000, 4, 50), (14000, 4, 400), (50000, 4, 1200)]]
    rekordy.append({**rekordy[0], "lat": None, "lng": None})
    dzialka_ = rcn.ksztalt_okolicy(prostokat(19.8995, 49.9999, 19.9005, 50.0001))  # ok. 70 × 22 m wokół pierwszej transakcji
    w = rcn.okolica(rekordy, dzialka_, 500)
    assert (w["liczba"], w["w_srodku"], w["mediana_m2"]) == (3, 1, 12000) and w["lata"] == {2023: 10000, 2024: 13000}
    assert rcn.okolica(rekordy, dzialka_, 2000)["liczba"] == 4
    punkt = rcn.ksztalt_okolicy({"type": "Point", "coordinates": [19.9, 50.0]})
    assert rcn.okolica(rekordy, punkt, 250)["liczba"] == 2
    assert rcn.okolica(rekordy, rcn.ksztalt_okolicy({"type": "Point", "coordinates": [21.0, 52.2]}), 2000) is None
    with pytest.raises(rcn.BladPliku):
        rcn.ksztalt_okolicy({"type": "Point", "coordinates": [2.3, 48.8]})
    lat_min, lat_max, lng_min, lng_max = rcn.prostokat_okolicy(punkt, 1000)
    assert lat_min < 50.0 - 0.009 and lng_max > 19.9 + 0.009 / math.cos(math.radians(50))


def test_trasa_okolicy(client, tmp_path, monkeypatch):
    pobrane = tmp_path / "Pobrane"
    pobrane.mkdir()
    krakow, wieliczka = str(pobrane / "krakow.gpkg"), str(pobrane / "wieliczka.gpkg")
    plik_rcn(krakow, [lokal(i, lok_cena_brutto=600000 + 10000 * i, geom=geometria_gpkg(50.0 + i / 20000, 19.9)) for i in range(1, 7)])
    dodaj_dzialki(krakow, [dzialka(f"T{i}", i, dzi_cena_brutto=90000 * i) for i in range(1, 4)])  # działki ok. 50,001–50,003
    plik_rcn(wieliczka, [lokal(i, geom=geometria_gpkg(50.0, 19.9 + i / 50000)) for i in range(1, 3)])
    monkeypatch.setattr(trasy_rcn, "katalogi_pobranych", lambda: [str(pobrane)])
    url = "/ceny/okolica"
    punkt = {"type": "Point", "coordinates": [19.9, 50.0]}
    assert client.post(url, json={"geometria": punkt, "promien": 500}).get_json()["plik"] is None  # nic nie zaimportowano
    for s in (krakow, wieliczka):
        client.post("/ceny/transakcje/import", data={"sciezka": s})
    w = client.post(url, json={"geometria": punkt, "promien": 500}).get_json()
    assert w["plik"]["nazwa"] == "krakow.gpkg" and w["lokale"]["liczba"] == 6 and w["dzialki"]["liczba"] == 3  # plik z największą liczbą
    assert w["pliki_zaimportowane"] == 2 and w["plik"]["url"].endswith("plik=1")
    assert client.post(url, json={"geometria": punkt, "promien": 300}).status_code == 400
    assert client.post(url, json={"geometria": {"type": "Point", "coordinates": [2.3, 48.8]}, "promien": 500}).status_code == 400
    obszar = client.post(url, json={"geometria": prostokat(19.899, 49.999, 19.901, 50.0002), "promien": 250}).get_json()
    assert obszar["lokale"]["w_srodku"] == 3  # 50,00005 / 50,0001 / 50,00015 w obszarze (do 50,0002)
    # MPZP i osiedle wołają tę trasę
    for strona in ("/mpzp/", "/osiedle/"):
        assert 'URL_CENY_OKOLICA = "/ceny/okolica"' in client.get(strona).get_data(as_text=True)


# ---------- ETAP 110: trend cen w obszarach ----------


def test_wykres_lat():
    lokale = [{"rok": r, "cena_m2": float(c), "pow_m2": 50.0, "cena": c * 50, "lat": 50.01, "lng": 19.95}
              for r, c in [(2022, 10000)] * 6 + [(2023, 11000)] * 2 + [(2024, 13000)] * 5]
    obszar = {"id": 1, "nazwa": "A", "geometria": prostokat(19.9, 50.0, 20.0, 50.05)}
    por = rcn.porownanie(lokale, [obszar])
    assert por["obszary"][0]["lata_liczba"] == {2022: 6, 2023: 2, 2024: 5}
    svg = rcn.wykres_lat_svg(por)
    assert svg.count("<polyline") == 2 and 'stroke-dasharray="6 4"' in svg  # obszar + cały plik
    assert svg.count('fill="#ffffff" stroke="#0071e3"') == 1  # 2023: dwie transakcje — pusty punkt
    assert ">10 000<" in svg and ">2023<" in svg
    assert "za mało lat" in rcn.wykres_lat_svg(rcn.porownanie(lokale[:6], [obszar]))
    assert rcn._ladna_os(10234, 13870) == (10000, 14000, 1000)


# ---------- ETAP 111: zmiana cen w heksagonach ----------


def test_zmiana_heksagonow():
    def rek(rok, cena, lat=50.06):
        return {"rok": rok, "cena_m2": float(cena), "lat": lat, "lng": 19.94}
    rekordy = [rek(2021, c) for c in (10000, 10000, 11000)] + [rek(2024, c) for c in (12000, 12100, 13000)]
    rekordy += [rek(2021, 9000, 50.2)] * 3 + [rek(2024, 9000, 50.2)]  # druga komórka: za mało w okresie B
    rekordy += [rek(2022, 99999)] * 5  # rok poza okresami
    w = rcn.zmiana_heksagonow(rekordy, 8, 3, (2021, 2021), (2024, 2025))
    assert len(w["komorki"]) == 1 and w["pominiete"] == 1
    k = w["komorki"][0]
    assert (k["mediana_a"], k["mediana_b"], k["liczba_a"], k["liczba_b"]) == (10000, 12100, 3, 3)
    assert k["zmiana_proc"] == pytest.approx(21.0) and w["mediana_zmian"] == pytest.approx(21.0)
    assert len(rcn.KOLORY_ZMIANY) == len(rcn.PROGI_ZMIANY) + 1


def test_trasa_zmiany(client, tmp_path, monkeypatch):
    pobrane = tmp_path / "Pobrane"
    pobrane.mkdir()
    sciezka = str(pobrane / "rcn.gpkg")
    plik_rcn(sciezka, [lokal(i, dok_data=f"{2021 + 3 * (i % 2)}-05-01", lok_cena_brutto=500000 + 100000 * (i % 2)) for i in range(1, 13)])
    monkeypatch.setattr(trasy_rcn, "katalogi_pobranych", lambda: [str(pobrane)])
    client.post("/ceny/transakcje/import", data={"sciezka": sciezka})
    url = "/ceny/transakcje/1/zmiana-heksagonow?rozdzielczosc=8&minimum=5&a_od=2021&a_do=2021&b_od=2024&b_do=2024"
    w = client.get(url).get_json()
    assert len(w["komorki"]) == 1 and w["komorki"][0]["zmiana_proc"] == pytest.approx(20.0)  # 10 000 → 12 000 zł/m²
    assert client.get(url + "&od=2024").get_json()["komorki"]  # filtr lat strony nie obowiązuje
    assert client.get(url.replace("b_od=2024", "b_od=2021")).status_code == 400  # wspólny rok
    assert client.get(url.replace("a_od=2021&a_do=2021", "a_od=2022&a_do=2021")).status_code == 400
    assert client.get(url.replace("&a_od=2021", "")).status_code == 400


# ---------- ETAP 112: piętro lokalu ----------


def test_kondygnacja():
    assert [rcn._kondygnacja(w) for w in (3, "3", "parter", "Parter", "-1", "", None, "poddasze", 500)] == [3, 3, 0, 0, -1, None, None, None, None]
    assert [rcn.przedzial_pietra(k) for k in (-1, 0, 2, 4, 9, 10, None)] == ["parter", "parter", "1-3", "4-9", "4-9", "10+", None]


def test_trasy_pietra(client, tmp_path, monkeypatch):
    pobrane = tmp_path / "Pobrane"
    pobrane.mkdir()
    sciezka = str(pobrane / "rcn.gpkg")
    pietra = ["parter", 1, 2, 5, 11, None, 12, 3]
    plik_rcn(sciezka, [lokal(i, lok_nr_kond=k, lok_cena_brutto=500000 + 10000 * i) for i, k in enumerate(pietra, start=1)])
    monkeypatch.setattr(trasy_rcn, "katalogi_pobranych", lambda: [str(pobrane)])
    client.post("/ceny/transakcje/import", data={"sciezka": sciezka})
    st = client.get("/ceny/transakcje/1/dane").get_json()["statystyki"]
    assert [(p["pietro"], p["liczba"]) for p in st["pietra"]] == [("parter", 1), ("1-3", 3), ("4-9", 1), ("10+", 2), (None, 1)]
    assert client.get("/ceny/transakcje/1/dane?pietro=10%2B").get_json()["statystyki"]["liczba"] == 2
    assert client.get("/ceny/transakcje/1/dane?pietro=5").status_code == 400
    assert ";kondygnacja;" in client.get("/ceny/transakcje/1.csv").get_data(as_text=True)
    raport = client.get("/ceny/transakcje/1/raport?pietro=1-3").get_data(as_text=True)
    assert "Według piętra" in raport and "1–3 piętro" in raport
    assert "Piętro" in client.get("/ceny/transakcje?plik=1").get_data(as_text=True)
