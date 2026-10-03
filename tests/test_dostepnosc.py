import io

import h3
import pytest

import dostepnosc.routes as dostepnosc_routes
from app import create_app
from dostepnosc import wyniki
from dostepnosc.wyniki import BladWynikow

SRODEK = h3.latlng_to_cell(52.4064, 16.9252, 9)
SASIEDZI = sorted(h3.grid_disk(SRODEK, 1))  # 7 komórek


def csv_testowy(separator=",", przecinek=False):
    wiersze = [separator.join(["h3", "czas_przystanek_min", "gestosc"])]
    for i, komorka in enumerate(SASIEDZI):
        czas = str(i * 3.5)  # 0, 3.5, 7, 10.5, 14, 17.5, 21
        if przecinek:
            czas = czas.replace(".", ",")
        gestosc = "" if i == 0 else str(100 * i)
        wiersze.append(separator.join([komorka, czas, gestosc]))
    return "\n".join(wiersze)


# ---------- wczytywanie ----------


def test_wczytaj_csv():
    dane = wyniki.wczytaj_csv(csv_testowy())
    assert dane["komorki"] == SASIEDZI
    assert dane["rozdzielczosc"] == 9
    assert dane["kolumny"]["czas_przystanek_min"][1] == 3.5
    assert dane["kolumny"]["gestosc"][0] is None


def test_wczytaj_csv_srednik_i_przecinek_dziesietny():
    dane = wyniki.wczytaj_csv("﻿" + csv_testowy(separator=";", przecinek=True))
    assert dane["kolumny"]["czas_przystanek_min"][1] == 3.5


@pytest.mark.parametrize(
    "tekst,fragment",
    [
        ("", "pusty"),
        ("id,czas_min\n1,2", "Brak kolumny"),
        ("h3\n" + SRODEK, "żadnych kolumn"),
        ("h3,czas_min\nabc,2", "poprawnym indeksem"),
        (f"h3,czas_min\n{SRODEK},dużo", "nie jest liczbą"),
        (f"h3,czas_min\n{SRODEK},\n", "Żadna kolumna"),
        (f"h3,czas_min\n{SRODEK},1\n{h3.cell_to_parent(SRODEK, 8)},2", "różne rozdzielczości"),
    ],
)
def test_wczytaj_csv_bledy(tekst, fragment):
    with pytest.raises(BladWynikow, match=fragment):
        wyniki.wczytaj_csv(tekst)


# ---------- analiza ----------


def test_analiza_kolumny_minut():
    analiza = wyniki.analiza_kolumny(wyniki.wczytaj_csv(csv_testowy()), "czas_przystanek_min")

    assert analiza["minuty"] is True
    assert analiza["progi"] == [5, 10, 15, 20, 30]
    klasy = [c["properties"]["klasa"] for c in analiza["geojson"]["features"]]
    assert klasy == [0, 0, 1, 2, 2, 3, 4]  # 0; 3.5; 7; 10.5; 14; 17.5; 21

    s = analiza["statystyki"]
    assert s["liczba_komorek"] == 7
    assert s["mediana"] == 10.5
    udzialy = {u["prog"]: u for u in s["udzialy"]}
    assert udzialy[15]["procent"] == pytest.approx(100 * 5 / 7)
    assert udzialy[5]["powierzchnia_km2"] == pytest.approx(2 * h3.average_hexagon_area(9, unit="km^2"))

    wielokat = analiza["geojson"]["features"][0]["geometry"]["coordinates"][0]
    assert wielokat[0] == wielokat[-1]  # pierścień domknięty
    lon, lat = wielokat[0]
    assert 16 < lon < 18 and 52 < lat < 53  # kolejność (lon, lat)


def test_analiza_kolumny_innej_pomija_braki_i_uzywa_kwantyli():
    analiza = wyniki.analiza_kolumny(wyniki.wczytaj_csv(csv_testowy()), "gestosc")
    assert analiza["minuty"] is False
    assert "udzialy" not in analiza["statystyki"]
    assert analiza["statystyki"]["komorki_bez_wartosci"] == 1
    assert len(analiza["geojson"]["features"]) == 6
    assert analiza["progi"] == sorted(analiza["progi"])


def test_czy_minuty():
    assert wyniki.czy_minuty("czas_szkola")
    assert wyniki.czy_minuty("przystanek_min")
    assert not wyniki.czy_minuty("gestosc")


# ---------- endpointy ----------


@pytest.fixture
def client(tmp_path):
    dostepnosc_routes._cache.clear()
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def wgraj(client, tekst, nazwa="moje.csv"):
    return client.post(
        "/dostepnosc/wgraj",
        data={"plik": (io.BytesIO(tekst.encode("utf-8")), nazwa)},
        content_type="multipart/form-data",
    )


def test_przyklad_jest_dostepny_od_razu(client):
    strona = client.get("/dostepnosc/").get_data(as_text=True)
    assert "przyklad_poznan_syntetyczny.csv" in strona
    assert "dane syntetyczne" in strona

    meta = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv").get_json()
    assert meta["przyklad"] is True
    assert [k["nazwa"] for k in meta["kolumny"]][0] == "czas_przystanek_min"

    analiza = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/czas_przystanek_min").get_json()
    assert analiza["statystyki"]["liczba_komorek"] == meta["liczba_komorek"]


def test_wgranie_analiza_i_usuniecie(client):
    odpowiedz = wgraj(client, csv_testowy())
    assert odpowiedz.status_code == 302
    assert "plik=moje.csv" in odpowiedz.headers["Location"]

    meta = client.get("/dostepnosc/plik/moje.csv").get_json()
    assert meta["liczba_komorek"] == 7
    assert client.get("/dostepnosc/plik/moje.csv/nie_ma").status_code == 404

    assert client.post("/dostepnosc/plik/moje.csv/usun").status_code == 302
    assert client.get("/dostepnosc/plik/moje.csv").status_code == 404


def test_wgranie_zlego_pliku_nie_zapisuje_go(client):
    odpowiedz = wgraj(client, "id,x\n1,2")
    assert "blad=" in odpowiedz.headers["Location"]
    assert client.get("/dostepnosc/plik/moje.csv").status_code == 404
    assert "blad=" in wgraj(client, csv_testowy(), nazwa="dane.txt").headers["Location"]


def test_nie_da_sie_usunac_przykladu_ani_wyjsc_poza_folder(client):
    assert client.post("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/usun").status_code == 400
    assert client.get("/dostepnosc/plik/..%2Fconfig.py").status_code == 404


# ---------- ETAP 13: wskaźnik łączny ----------


def test_analiza_laczna_bierze_maksimum_i_liczy_najslabsze_ogniwo():
    komorki = SASIEDZI[:4]
    tekst = "h3,czas_a_min,czas_b_min,gestosc\n" + "\n".join(
        [
            f"{komorki[0]},3,12,1",  # łącznie 12 (b)
            f"{komorki[1]},20,4,1",  # 20 (a)
            f"{komorki[2]},2,,1",  # brak b → brak łącznego
            f"{komorki[3]},8,9,1",  # 9 (b)
        ]
    )
    analiza = wyniki.analiza_laczna(wyniki.wczytaj_csv(tekst))

    wartosci = [c["properties"]["wartosc"] for c in analiza["geojson"]["features"]]
    assert wartosci == [12, 20, 9]
    assert analiza["minuty"] is True
    assert analiza["statystyki"]["komorki_bez_wartosci"] == 1
    assert analiza["skladowe"] == ["czas_a_min", "czas_b_min"]
    ogniwa = {o["kolumna"]: o["komorki"] for o in analiza["najslabsze_ogniwo"]}
    assert ogniwa == {"czas_b_min": 2, "czas_a_min": 1}
    assert analiza["najslabsze_ogniwo"][0]["procent"] == pytest.approx(200 / 3)


def test_analiza_laczna_wymaga_dwoch_kolumn_czasu():
    with pytest.raises(BladWynikow, match="dwóch"):
        wyniki.analiza_laczna(wyniki.wczytaj_csv(csv_testowy()))


def test_endpoint_laczny(client):
    meta = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv").get_json()
    assert meta["laczny_dostepny"] is True
    analiza = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/laczny").get_json()
    assert len(analiza["najslabsze_ogniwo"]) == 3

    wgraj(client, csv_testowy())
    assert client.get("/dostepnosc/plik/moje.csv").get_json()["laczny_dostepny"] is False
    assert client.get("/dostepnosc/plik/moje.csv/laczny").status_code == 422


# ---------- ETAP 15: poprawki z przeglądu kodu ----------


def test_wgranie_pliku_z_wielkimi_literami_w_rozszerzeniu(client):
    odpowiedz = wgraj(client, csv_testowy(), nazwa="Wyniki.CSV")
    assert "plik=Wyniki.csv" in odpowiedz.headers["Location"]
    assert client.get("/dostepnosc/plik/Wyniki.csv").status_code == 200
    assert "Wyniki.csv" in client.get("/dostepnosc/").get_data(as_text=True)
    assert client.post("/dostepnosc/plik/Wyniki.csv/usun").status_code == 302


def test_powtorzone_nazwy_kolumn_odrzucone():
    with pytest.raises(BladWynikow, match="Powtórzone"):
        wyniki.wczytaj_csv(f"h3,x_min,x_min\n{SRODEK},2,3")


def test_laczny_bez_zadnej_pelnej_komorki_to_czytelny_blad(client):
    k = SASIEDZI
    tekst = f"h3,czas_a_min,czas_b_min\n{k[0]},3,\n{k[1]},,4"
    with pytest.raises(BladWynikow, match="Żadna komórka"):
        wyniki.analiza_laczna(wyniki.wczytaj_csv(tekst))

    wgraj(client, tekst, nazwa="dziury.csv")
    odpowiedz = client.get("/dostepnosc/plik/dziury.csv/laczny")
    assert odpowiedz.status_code == 422
    assert "Żadna komórka" in odpowiedz.get_json()["blad"]


# ---------- ETAP 21: ludność i porównanie scenariuszy ----------


def csv_z_ludnoscia(czasy, ludnosc=None, kolumna="czas_szkola_min"):
    naglowek = f"h3,{kolumna}" + (",ludnosc" if ludnosc else "")
    wiersze = [naglowek]
    for i, czas in enumerate(czasy):
        pola = [SASIEDZI[i], "" if czas is None else str(czas)]
        if ludnosc:
            pola.append(str(ludnosc[i]))
        wiersze.append(",".join(pola))
    return "\n".join(wiersze)


def test_ludnosc_to_waga_a_nie_wskaznik():
    dane = wyniki.wczytaj_csv(csv_z_ludnoscia([3, 12, 20], [100, 300, 600]))
    assert list(dane["kolumny"]) == ["czas_szkola_min"]
    assert dane["ludnosc"] == [100, 300, 600]

    udzialy = {u["prog"]: u for u in wyniki.analiza_kolumny(dane, "czas_szkola_min")["statystyki"]["udzialy"]}
    assert udzialy[5]["ludnosc"] == 100
    assert udzialy[15]["ludnosc"] == 400
    assert udzialy[15]["procent_ludnosci"] == pytest.approx(40.0)
    assert udzialy[15]["procent"] == pytest.approx(200 / 3)  # powierzchnia (komórki) inaczej niż ludność


def test_bez_ludnosci_brak_pol_ludnosci():
    udzialy = wyniki.analiza_kolumny(wyniki.wczytaj_csv(csv_z_ludnoscia([3, 12])), "czas_szkola_min")["statystyki"]["udzialy"]
    assert "procent_ludnosci" not in udzialy[0]


def test_ujemna_ludnosc_odrzucona():
    with pytest.raises(BladWynikow, match="ujemne"):
        wyniki.wczytaj_csv(csv_z_ludnoscia([3], [-5]))


def test_porownanie_scenariuszy():
    przed = wyniki.wczytaj_csv(csv_z_ludnoscia([20, 18, 7, 12, None], [100, 200, 300, 400, 500]))
    po = wyniki.wczytaj_csv(csv_z_ludnoscia([9, 17.5, 7, 17, 3], [100, 200, 300, 400, 500]))
    wynik = wyniki.porownaj_scenariusze(przed, po, "czas_szkola_min")
    s = wynik["statystyki"]

    assert s["liczba_komorek"] == 4  # piąta komórka bez wartości „przed”
    assert (s["poprawa"], s["pogorszenie"], s["bez_zmian"]) == (1, 1, 2)
    assert s["najwieksza_poprawa"] == -11
    assert s["komorki_weszly_15"] == 1 and s["komorki_wypadly_15"] == 1
    assert s["ludnosc_weszla_15"] == 100 and s["ludnosc_wypadla_15"] == 400
    assert s["procent_15_przed"] == pytest.approx(50.0) and s["procent_15_po"] == pytest.approx(50.0)
    klasy = [c["properties"]["klasa"] for c in wynik["geojson"]["features"]]
    assert klasy == [0, 2, 2, 3]  # −11 → szybciej ≥5; −0,5 i 0 → bez zmian; +5 → wolniej 1–5


def test_porownanie_wskaznika_lacznego_i_bledy():
    k = SASIEDZI
    przed = wyniki.wczytaj_csv(f"h3,czas_a_min,czas_b_min\n{k[0]},5,20\n{k[1]},4,6")
    po = wyniki.wczytaj_csv(f"h3,czas_a_min,czas_b_min\n{k[0]},5,8\n{k[1]},4,6")
    s = wyniki.porownaj_scenariusze(przed, po, wyniki.NAZWA_LACZNEGO)["statystyki"]
    assert s["najwieksza_poprawa"] == -12  # łącznie 20 → 8

    with pytest.raises(BladWynikow, match="czasu"):
        wyniki.porownaj_scenariusze(wyniki.wczytaj_csv(csv_testowy()), wyniki.wczytaj_csv(csv_testowy()), "gestosc")
    inna_rozdz = wyniki.wczytaj_csv(f"h3,czas_a_min\n{h3.cell_to_parent(k[0], 8)},5")
    with pytest.raises(BladWynikow, match="rozdzielczości"):
        wyniki.porownaj_scenariusze(przed, inna_rozdz, "czas_a_min")


def test_endpoint_porownania_na_przykladach(client):
    strona = client.get("/dostepnosc/").get_data(as_text=True)
    assert "przyklad_poznan_nowa_szkola_syntetyczny.csv" in strona

    adres = "/dostepnosc/porownanie?przed=przyklad_poznan_syntetyczny.csv&po=przyklad_poznan_nowa_szkola_syntetyczny.csv"
    s = client.get(adres + "&kolumna=czas_szkola_min").get_json()["statystyki"]
    assert s["poprawa"] > 0 and s["pogorszenie"] == 0
    assert s["ludnosc_weszla_15"] > 0
    assert client.get(adres + "&kolumna=laczny").status_code == 200
    assert client.get(adres + "&kolumna=nie_ma_min").status_code == 422
    assert client.get("/dostepnosc/porownanie?przed=a.csv&po=a.csv&kolumna=x").status_code == 400
    assert client.post("/dostepnosc/plik/przyklad_poznan_nowa_szkola_syntetyczny.csv/usun").status_code == 400

    meta = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv").get_json()
    assert meta["ma_ludnosc"] is True


# ---------- ETAP 24: eksport GeoJSON ----------


def test_eksport_geojson_dostepnosci(client):
    import json as _json

    przyklad = "przyklad_poznan_syntetyczny.csv"
    odp = client.get(f"/dostepnosc/eksport.geojson?plik={przyklad}&kolumna=czas_szkola_min")
    assert odp.mimetype == "application/geo+json"
    assert "attachment" in odp.headers["Content-Disposition"]
    dane = _json.loads(odp.data)
    cecha = dane["features"][0]
    assert cecha["geometry"]["type"] == "Polygon"
    assert {"h3", "wartosc", "klasa", "wskaznik"} <= set(cecha["properties"])

    laczny = _json.loads(client.get(f"/dostepnosc/eksport.geojson?plik={przyklad}&kolumna=laczny").data)
    assert laczny["features"][0]["properties"]["wskaznik"] == "czas_laczny_min"

    porownanie = client.get(
        f"/dostepnosc/eksport.geojson?plik={przyklad}&po=przyklad_poznan_nowa_szkola_syntetyczny.csv&kolumna=czas_szkola_min"
    )
    assert {"przed", "po", "zmiana"} <= set(_json.loads(porownanie.data)["features"][0]["properties"])
    assert "_porownanie_" in porownanie.headers["Content-Disposition"]
    assert client.get(f"/dostepnosc/eksport.geojson?plik={przyklad}&kolumna=nie_ma").status_code == 404


# ---------- ETAP 38: krzywa, luki, komórka ----------


def _z_ludnoscia():
    wiersze = ["h3,czas_szkola_min,czas_sklep_min,ludnosc"]
    # czasy: 0, 3.5, 7, 10.5, 14, 17.5, 21; ludność: 10, 20, …, 70
    for i, komorka in enumerate(SASIEDZI):
        wiersze.append(f"{komorka},{i * 3.5},{i},{10 * (i + 1)}")
    return wyniki.wczytaj_csv("\n".join(wiersze))


def test_krzywa_dostepnosci_skumulowana_do_pelnego_pokrycia():
    stat = wyniki.analiza_kolumny(_z_ludnoscia(), "czas_szkola_min")["statystyki"]
    krzywa = stat["krzywa"]
    assert [p["minuty"] for p in krzywa] == list(range(22))  # do ceil(21)
    assert krzywa[0]["procent"] == pytest.approx(100 / 7)  # tylko komórka z czasem 0
    assert krzywa[7]["procent"] == pytest.approx(300 / 7)  # 0, 3.5, 7
    assert krzywa[7]["ludnosc"] == 60 and krzywa[7]["procent_ludnosci"] == pytest.approx(60 / 280 * 100)
    assert krzywa[-1]["procent"] == pytest.approx(100)
    # ta sama liczba co kafelek „do 15 min”
    assert krzywa[15]["procent"] == pytest.approx(stat["udzialy"][2]["procent"])


def test_krzywa_bez_ludnosci_i_obcieta_do_60_minut():
    dane = wyniki.wczytaj_csv("h3,czas_min\n" + "\n".join(f"{k},{90 if i else 2}" for i, k in enumerate(SASIEDZI)))
    krzywa = wyniki.analiza_kolumny(dane, "czas_min")["statystyki"]["krzywa"]
    assert len(krzywa) == 61 and "ludnosc" not in krzywa[0]
    assert krzywa[-1]["procent"] == pytest.approx(100 / 7)  # reszta > 60 min


def test_luki_najpierw_najwiecej_mieszkancow():
    luki = wyniki.analiza_kolumny(_z_ludnoscia(), "czas_szkola_min")["statystyki"]["luki"]
    # powyżej 15 min: 17.5 (60 os.) i 21 (70 os.)
    assert [(l["wartosc"], l["ludnosc"]) for l in luki] == [(21.0, 70.0), (17.5, 60.0)]
    assert 52 < luki[0]["lat"] < 53 and 16 < luki[0]["lon"] < 17


def test_luki_bez_ludnosci_po_czasie():
    luki = wyniki.analiza_kolumny(wyniki.wczytaj_csv(csv_testowy()), "czas_przystanek_min")["statystyki"]["luki"]
    assert [l["wartosc"] for l in luki] == [21.0, 17.5] and "ludnosc" not in luki[0]


def test_komorka_wszystkie_wskazniki():
    dane = _z_ludnoscia()
    wynik = wyniki.komorka(dane, SASIEDZI[2].upper())
    assert wynik["wartosci"] == {"czas_szkola_min": 7.0, "czas_sklep_min": 2.0}
    assert wynik["czas_laczny"] == 7.0 and wynik["ludnosc"] == 30.0
    with pytest.raises(KeyError):
        wyniki.komorka(dane, "8928308280fffff")


def test_endpoint_komorki(client):
    odpowiedz = client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/komorka/891e24a1003ffff")
    assert odpowiedz.status_code == 200
    assert odpowiedz.get_json()["wartosci"]["czas_przystanek_min"] == 27.1
    assert client.get("/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/komorka/zly").status_code == 404


# ---------- ETAP 78: gdzie nowa placówka ----------

import h3  # noqa: E402

from dostepnosc import lokalizacja  # noqa: E402


def test_najlepsze_lokalizacje_maksymalne_pokrycie():
    srodek = h3.latlng_to_cell(52.40, 16.92, 9)
    komorki = sorted(h3.grid_disk(srodek, 6))
    # obecna usługa obsługuje tylko zachodnią połowę; wschód bez dojścia
    czasy = [5.0 if h3.cell_to_latlng(k)[1] < 16.915 else 40.0 for k in komorki]
    ludnosc = [100.0] * len(komorki)
    w = lokalizacja.najlepsze_lokalizacje(komorki, czasy, ludnosc, prog_min=10, ile=2)
    assert w["z_ludnoscia"] and len(w["propozycje"]) == 2
    p1, p2 = w["propozycje"]
    assert p1["lng"] > 16.915  # pierwsza propozycja po stronie bez usług
    assert p1["obejmie"] >= p2["obejmie"] > 0  # zachłannie: najpierw największy zysk
    assert w["w_zasiegu_po_proc"] == pytest.approx(w["w_zasiegu_przed_proc"] + p1["obejmie_proc"] + p2["obejmie_proc"], abs=0.2)
    # wszystko w zasięgu — brak propozycji
    assert lokalizacja.najlepsze_lokalizacje(komorki, [1.0] * len(komorki), ludnosc, 10)["propozycje"] == []
    # bez ludności: każda komórka waży 1, brak czasu = poza zasięgiem
    bez = lokalizacja.najlepsze_lokalizacje(komorki, [None] * len(komorki), None, 10)
    assert bez["w_zasiegu_przed_proc"] == 0 and bez["propozycje"][0]["obejmie"] == bez["propozycje"][0]["komorki"]
    for zle in ({"prog_min": 0}, {"prog_min": 10, "ile": 9}):
        with pytest.raises(lokalizacja.BladLokalizacji):
            lokalizacja.najlepsze_lokalizacje(komorki, czasy, ludnosc, **zle)


def test_trasa_nowej_placowki(client):
    url = "/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/lokalizacja"
    w = client.get(url, query_string={"kolumna": "czas_przystanek_min", "prog": 15, "ile": 3}).get_json()
    assert len(w["propozycje"]) == 3 and w["w_zasiegu_po_proc"] > w["w_zasiegu_przed_proc"]
    assert client.get(url, query_string={"kolumna": "ludnosc"}).status_code == 400
    assert client.get(url, query_string={"kolumna": "czas_szkola_min", "prog": 500}).status_code == 422


# ---------- ETAP 85: zasięg z punktu ----------

from dostepnosc import model, zasieg  # noqa: E402


def test_zasieg_punktu_okregi_i_nowi():
    srodek = h3.latlng_to_cell(52.40, 16.92, 9)
    komorki = sorted(h3.grid_disk(srodek, 12))
    lat, lng = h3.cell_to_latlng(srodek)
    ludnosc = [10.0] * len(komorki)
    czasy = [3.0 if k == srodek else None for k in komorki]
    w = zasieg.zasieg_punktu(komorki, ludnosc, lat, lng, czasy)
    p5, p10, p15 = w["progi"]
    # 80 m/min / 1,3 → promień 5 min ≈ 308 m
    assert (p5["minuty"], p5["promien_m"]) == (5, 308) and p15["promien_m"] == 923
    assert 0 < p5["ludnosc"] < p10["ludnosc"] < p15["ludnosc"] <= w["razem"]
    assert p5["nowi"] == p5["ludnosc"] - 10  # komórka środka ma dziś 3 min — nie jest „nowa”
    # w zasięgu = komórki, których środek leży w okręgu
    assert p5["komorki"] == sum(1 for k in komorki if model._odleglosc_m(lat, lng, *h3.cell_to_latlng(k)) <= 5 * 80 / 1.3)
    # bez ludności i bez czasów: liczymy komórki, brak „nowi”
    bez = zasieg.zasieg_punktu(komorki, None, lat, lng)
    assert bez["progi"][0]["ludnosc"] == bez["progi"][0]["komorki"] and "nowi" not in bez["progi"][0]
    # daleko od siatki
    assert zasieg.zasieg_punktu(komorki, ludnosc, 50.0, 20.0)["w_siatce"] is False
    with pytest.raises(model.BladModelu):
        zasieg.zasieg_punktu(komorki, ludnosc, lat, lng, predkosc_kmh=20)


def test_trasa_zasiegu(client):
    url = "/dostepnosc/plik/przyklad_poznan_syntetyczny.csv/zasieg"
    w = client.get(url, query_string={"lat": 52.4064, "lng": 16.9252, "kolumna": "czas_przystanek_min"}).get_json()
    assert w["kolumna"] == "czas_przystanek_min" and w["w_siatce"] and "nowi" in w["progi"][2]
    bez_kolumny = client.get(url, query_string={"lat": 52.4064, "lng": 16.9252, "kolumna": "ludnosc"}).get_json()
    assert bez_kolumny["kolumna"] is None and "nowi" not in bez_kolumny["progi"][0]
    assert client.get(url, query_string={"lat": "x", "lng": 1}).status_code == 400
    assert client.get(url, query_string={"lat": 52.4, "lng": 16.9, "kretosc": 5}).status_code == 422


# ---------- ETAP 163: wyniki w narysowanych obszarach ----------


def test_wyniki_w_obszarach(client):
    import h3
    from dostepnosc import wyniki as wyniki_h3
    from dostepnosc.routes import PLIK_PRZYKLADU, _wczytaj
    url = f"/dostepnosc/plik/{PLIK_PRZYKLADU}/obszary"
    with client.application.app_context():
        dane = _wczytaj(PLIK_PRZYKLADU)
    srodki = [h3.cell_to_latlng(k) for k in dane["komorki"]]
    lat_sr = sorted(s[0] for s in srodki)[len(srodki) // 2]
    polnoc = {"type": "Polygon", "coordinates": [[[10, lat_sr], [30, lat_sr], [30, 60], [10, 60], [10, lat_sr]]]}
    caly = {"type": "Polygon", "coordinates": [[[10, 40], [30, 40], [30, 60], [10, 60], [10, 40]]]}
    odp = client.post(url, json={"kolumna": "czas_szkola_min", "obszary": [{"nazwa": " Północ  ", "geometria": polnoc}, {"nazwa": "", "geometria": caly}]})
    w = odp.get_json()
    assert odp.status_code == 200 and [o["nazwa"] for o in w["obszary"]] == ["Północ", "obszar"]
    # ręcznie: komórki ze środkiem na północ od mediany szerokości, czas ważony ludnością
    idx = [i for i, (la, _) in enumerate(srodki) if la > lat_sr and dane["kolumny"]["czas_szkola_min"][i] is not None]
    czasy = [dane["kolumny"]["czas_szkola_min"][i] for i in idx]
    ludn = [dane["ludnosc"][i] for i in idx]
    p = w["obszary"][0]
    assert p["komorek"] == len(idx) and p["mieszkancy"] == pytest.approx(sum(ludn))
    assert p["srednia"] == pytest.approx(sum(c * l for c, l in zip(czasy, ludn)) / sum(ludn))
    assert p["w_zasiegu_proc"] == pytest.approx(100 * sum(l for c, l in zip(czasy, ludn) if c <= 15) / sum(ludn))
    assert w["obszary"][1]["komorek"] == w["calosc"]["komorek"] and w["minuty"] is True
    laczny = client.post(url, json={"kolumna": "laczny", "obszary": [{"nazwa": "x", "geometria": caly}]}).get_json()
    assert laczny["obszary"][0]["komorek"] <= w["calosc"]["komorek"]
    assert client.post(url, json={"kolumna": "nie_ma", "obszary": [{"geometria": caly}]}).status_code == 404
    assert client.post(url, json={"kolumna": "czas_szkola_min", "obszary": []}).status_code == 400
    assert client.post(url, json={"kolumna": "czas_szkola_min", "obszary": [{"geometria": {"type": "Point", "coordinates": [17, 52]}}]}).status_code == 400
    assert client.post("/dostepnosc/plik/nie_ma.csv/obszary", json={}).status_code == 404
    assert wyniki_h3.PROG_MIASTA_15 == 15


# ---------- ETAP 183: zasięgi jako wieloboki ----------


def test_kontury_zasiegow(client):
    import json as _json

    import h3

    from dostepnosc import wyniki as w

    srodek = h3.latlng_to_cell(52.40, 16.92, 9)
    pierscien1 = [k for k in h3.grid_disk(srodek, 1) if k != srodek]
    daleko = h3.latlng_to_cell(52.50, 16.92, 9)
    wyniki = {"komorki": [srodek, *pierscien1, daleko], "kolumny": {"czas_min": [3.0] + [8.0] * 6 + [40.0], "liczba": [1.0] * 8},
              "ludnosc": [100.0] * 8}
    k = w.kontury(wyniki, "czas_min")
    assert [c["properties"]["minuty"] for c in k["features"]] == [30, 20, 15, 10, 5]  # od największego
    pierwszy, piec = k["features"][0], k["features"][-1]
    assert pierwszy["properties"]["komorek"] == 7 and pierwszy["properties"]["mieszkancy"] == 700
    assert piec["properties"]["komorek"] == 1 and pierwszy["geometry"]["type"] == "Polygon"  # 7 sąsiednich komórek — jeden wielobok
    assert pierwszy["properties"]["powierzchnia_km2"] == pytest.approx(7 * h3.cell_area(srodek, unit="km^2"), rel=0.01)
    with pytest.raises(w.BladWynikow):
        w.kontury(wyniki, "liczba")  # nie czas dojścia
    przyklad = "przyklad_poznan_syntetyczny.csv"
    odp = client.get(f"/dostepnosc/kontury.geojson?plik={przyklad}&kolumna=czas_szkola_min")
    assert odp.mimetype == "application/geo+json" and "_zasiegi.geojson" in odp.headers["Content-Disposition"]
    dane = _json.loads(odp.data)
    assert dane["features"] and {"minuty", "komorek", "powierzchnia_km2", "wskaznik"} <= set(dane["features"][0]["properties"])
    assert client.get(f"/dostepnosc/kontury.geojson?plik={przyklad}&kolumna=laczny").status_code == 200
    assert client.get(f"/dostepnosc/kontury.geojson?plik={przyklad}&kolumna=nie_ma").status_code == 404


# ---------- ETAP 184: dzielnice w porównaniu scenariuszy ----------


def test_dzielnice_w_porownaniu(client):
    import h3

    from dostepnosc import obszary

    komorki = [h3.latlng_to_cell(52.40 + i * 0.003, 16.92, 9) for i in range(4)]
    przed = {"komorki": komorki, "kolumny": {"czas_min": [10.0, 20.0, 30.0, 12.0]}, "ludnosc": [100.0, 100.0, 100.0, 100.0]}
    po = {"komorki": komorki, "kolumny": {"czas_min": [8.0, 12.0, 30.0, 12.0]}, "ludnosc": [100.0, 100.0, 100.0, 100.0]}
    caly = {"nazwa": "wszystko", "geometria": {"type": "Polygon", "coordinates": [[[16.9, 52.39], [16.95, 52.39], [16.95, 52.42], [16.9, 52.42], [16.9, 52.39]]]}}
    w = obszary.porownanie_w_obszarach(przed, po, "czas_min", [caly])
    o = w["obszary"][0]
    assert w["porownanie"] and o["przed"]["srednia"] == 18.0 and o["po"]["srednia"] == 15.5 and o["zmiana_srednia"] == -2.5
    assert o["zmiana_w_zasiegu_proc"] == pytest.approx(25.0)  # 2 z 4 → 3 z 4 mieszkańców do 15 min
    przyklad = "przyklad_poznan_syntetyczny.csv"
    obszar = {"nazwa": "Jeżyce", "geometria": {"type": "Polygon", "coordinates": [[[16.85, 52.38], [16.95, 52.38], [16.95, 52.44], [16.85, 52.44], [16.85, 52.38]]]}}
    d = client.post(f"/dostepnosc/plik/{przyklad}/obszary", json={"kolumna": "czas_szkola_min", "obszary": [obszar],
                                                                   "po": "przyklad_poznan_nowa_szkola_syntetyczny.csv"}).get_json()
    assert d["porownanie"] and "zmiana_srednia" in d["obszary"][0] and d["obszary"][0]["po"]["srednia"] <= d["obszary"][0]["przed"]["srednia"]
    assert client.post(f"/dostepnosc/plik/{przyklad}/obszary", json={"kolumna": "czas_szkola_min", "obszary": [obszar], "po": "nie_ma.csv"}).status_code >= 400


# ---------- ETAP 204: grupy mieszkańców ----------


def csv_z_grupami():
    wiersze = ["h3,czas_szkola_min,ludnosc,ludnosc_0_14,ludnosc_65+"]
    for i, komorka in enumerate(SASIEDZI):  # czasy 0, 4, 8, 12, 16, 20, 24
        dzieci, seniorzy = (100, 0) if i < 3 else (0, 50)
        wiersze.append(f"{komorka},{'' if i == 6 else i * 4},{dzieci + seniorzy + 10},{dzieci},{seniorzy}")
    return "\n".join(wiersze)


def test_grupy_mieszkancow(client):
    w = wyniki.wczytaj_csv(csv_z_grupami())
    assert set(w["kolumny"]) == {"czas_szkola_min"} and list(w["grupy"]) == ["ludnosc_0_14", "ludnosc_65+"]
    g = {x["nazwa"]: x for x in wyniki.analiza_kolumny(w, "czas_szkola_min")["statystyki"]["grupy"]}
    dzieci, seniorzy = g["ludnosc_0_14"], g["ludnosc_65+"]
    assert dzieci["razem"] == 300 and dzieci["udzialy"][1] == {"prog": 10, "ludnosc": 300, "procent": 100.0} and dzieci["mediana_min"] == 4
    # seniorzy w komórkach 12, 16, 20 min (komórka bez czasu pominięta): ≤15 min — 50 z 150
    assert seniorzy["razem"] == 150 and seniorzy["udzialy"][2]["procent"] == pytest.approx(100 / 3) and seniorzy["mediana_min"] == 16
    assert "grupy" not in wyniki.analiza_kolumny(wyniki.wczytaj_csv(csv_testowy()), "czas_przystanek_min")["statystyki"]
    with pytest.raises(BladWynikow, match="ujemne"):
        wyniki.wczytaj_csv(csv_z_grupami().replace(",100,0", ",-1,0", 1))
    with pytest.raises(BladWynikow, match="Najwyżej 8"):
        wyniki.wczytaj_csv("h3,czas_min," + ",".join(f"wiek_{i}" for i in range(9)) + f"\n{SRODEK},1," + ",".join("1" * 9))
    # szybki model przepisuje grupy do nowego pliku
    from dostepnosc import model
    ponownie = wyniki.wczytaj_csv(model.csv_wynikow(w["komorki"], w["kolumny"], w["ludnosc"], w["grupy"]))
    assert ponownie["grupy"] == w["grupy"]
    # trasa i raport
    wgraj(client, csv_z_grupami(), "grupy.csv")
    analiza = client.get("/dostepnosc/plik/grupy.csv/czas_szkola_min").get_json()
    assert [x["nazwa"] for x in analiza["statystyki"]["grupy"]] == ["ludnosc_0_14", "ludnosc_65+"]
    raport = client.get("/dostepnosc/raport?plik=grupy.csv&kolumna=czas_szkola_min").get_data(as_text=True)
    assert "ludnosc_65+" in raport and "33,3%" in raport
