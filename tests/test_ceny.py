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
import sqlite3  # noqa: E402
import struct  # noqa: E402

from shapely.geometry import Point  # noqa: E402

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
               "lok_funkcja", "lok_cena_brutto", "nier_cena_brutto", "tran_cena_brutto", "lok_pow_uzyt", "lok_liczba_izb", "geom"]
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
    plik_rcn(zly, [lokal(1)], tabela="transakcje_dzialki")
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
    assert [(i["izby"], i["liczba"]) for i in s["izby"]] == [("1", 1), ("2", 2), ("3", 1), ("4+", 1)]
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
    assert d["statystyki"]["liczba"] == 29 and d["lata"] == [2023, 2024] and d["rodzaje"][0]["rodzaj"] == "wolnyRynek"
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
