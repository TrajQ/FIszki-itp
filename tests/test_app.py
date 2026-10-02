import pathlib

import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


def test_strona_glowna(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.parametrize("sciezka", ["/atlas/", "/mpzp/", "/fiszki/", "/dostepnosc/"])
def test_placeholdery_modulow(client, sciezka):
    response = client.get(sciezka)
    assert response.status_code == 200


# ---------- ETAP 14: pulpit na stronie głównej ----------

import io
import json


@pytest.fixture
def czysty_client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_pulpit_pokazuje_podsumowania_modulow(czysty_client):
    c = czysty_client
    c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), "a.pdf")}, content_type="multipart/form-data")
    for _ in range(3):
        c.post(
            "/fiszki/1/fiszki",
            data=json.dumps({"strona": 1, "fragment_tekstu": "f", "pytanie": "P?", "odpowiedz": "O."}),
            content_type="application/json",
        )
    with c.application.app_context():
        from mpzp.baza import zapisz_w_historii

        zapisz_w_historii("306401_1.0051.AR_18.14", "1MN", 52.4, 16.9)

    strona = c.get("/").get_data(as_text=True)
    assert "3 do powtórki dziś" in strona
    assert "306401_1.0051.AR_18.14" in strona
    assert "1MN" in strona


def test_pulpit_dziala_mimo_bledu_modulu(czysty_client, monkeypatch):
    import fiszki.routes

    def zepsute():
        raise RuntimeError("symulowany błąd")

    monkeypatch.setattr(fiszki.routes, "podsumowanie", zepsute)
    assert czysty_client.get("/").status_code == 200


def test_favicon(czysty_client):
    odpowiedz = czysty_client.get("/favicon.ico")
    assert odpowiedz.status_code == 302
    assert odpowiedz.headers["Location"].endswith("/static/favicon.svg")


# ---------- ETAP 32: kopia zapasowa ----------


def test_kopia_zapasowa_zawiera_dane_i_pomija_cache(czysty_client, tmp_path):
    import os
    import sqlite3
    import zipfile

    c = czysty_client
    c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), "wyklad.pdf")}, content_type="multipart/form-data")
    c.post(
        "/fiszki/1/fiszki",
        data=json.dumps({"strona": 1, "fragment_tekstu": "f", "pytanie": "Kopia?", "odpowiedz": "Tak."}),
        content_type="application/json",
    )
    granice = os.path.join(c.application.instance_path, "atlas", "granice")
    os.makedirs(granice, exist_ok=True)
    with open(os.path.join(granice, "gminy_12.geojson"), "w") as plik:
        plik.write("{}")

    odp = c.get("/kopia-zapasowa")
    assert odp.mimetype == "application/zip"
    assert "warsztat_kopia_" in odp.headers["Content-Disposition"]

    with zipfile.ZipFile(io.BytesIO(odp.data)) as z:
        nazwy = z.namelist()
        assert "PRZYWRACANIE.txt" in nazwy
        assert "instance/fiszki/fiszki.db" in nazwy
        assert any(n.startswith("instance/fiszki/pliki/") and n.endswith("wyklad.pdf") for n in nazwy)
        assert not any("granice" in n for n in nazwy)
        # baza w kopii jest poprawna i zawiera fiszkę
        z.extract("instance/fiszki/fiszki.db", tmp_path)
    db = sqlite3.connect(tmp_path / "instance" / "fiszki" / "fiszki.db")
    assert db.execute("SELECT pytanie FROM fiszki").fetchall() == [("Kopia?",)]
    db.close()

    assert "Pobierz kopię zapasową" in c.get("/").get_data(as_text=True)


# ---------- ETAP 86: kalendarz i pomoc ----------


def test_kalendarz_dziala_mimo_bledu_modulu(czysty_client, monkeypatch):
    import teren.routes

    def zepsute():
        raise RuntimeError("symulowany błąd")

    monkeypatch.setattr(teren.routes, "terminy", zepsute)
    assert czysty_client.get("/").status_code == 200


def test_pomoc_ma_wszystkie_moduly_i_dzialajace_linki(czysty_client):
    import re

    c = czysty_client
    html = c.get("/pomoc").get_data(as_text=True)
    for kotwica in ("start", "atlas", "mpzp", "fiszki", "dostepnosc", "osiedle", "przepisy", "teren"):
        assert f'id="{kotwica}"' in html and f'href="#{kotwica}"' in html
    assert 'href="/pomoc"' in c.get("/").get_data(as_text=True)  # w menu
    linki = set(re.findall(r'href="(/[^"#]*)', html)) - {"/static/style.css", "/static/favicon.svg"}
    assert len(linki) >= 8
    for link in linki:
        assert c.get(link).status_code == 200, link


# ---------- ETAP 97: kopia automatyczna przy starcie ----------


def test_kopia_automatyczna_co_tydzien_i_5_najnowszych(tmp_path):
    import os
    import zipfile

    from kopia import kopia_automatyczna, ostatnia_kopia_automatyczna

    instance, kopie = tmp_path / "instance", tmp_path / "kopie"
    assert kopia_automatyczna(str(instance), str(kopie)) is None  # brak danych — nic do kopiowania
    (instance / "fiszki").mkdir(parents=True)
    (instance / "fiszki" / "notatka.txt").write_text("dane")
    dzien = 86400
    start = 1_790_000_000
    pierwsza = kopia_automatyczna(str(instance), str(kopie), teraz=start)
    assert pierwsza and zipfile.ZipFile(pierwsza).read("instance/fiszki/notatka.txt") == b"dane"
    assert kopia_automatyczna(str(instance), str(kopie), teraz=start + 6 * dzien) is None  # za wcześnie
    for tydzien in range(1, 8):
        assert kopia_automatyczna(str(instance), str(kopie), teraz=start + tydzien * 7 * dzien)
    pliki = sorted(os.listdir(kopie))
    assert len(pliki) == 5 and not any(p.endswith(".tmp") for p in pliki)
    assert ostatnia_kopia_automatyczna(str(kopie))["sciezka"].endswith(pliki[-1])
    (kopie / "warsztat_kopia_reczna.zip").write_bytes(b"x")  # kopia z przeglądarki zostaje nietknięta
    kopia_automatyczna(str(instance), str(kopie), teraz=start + 70 * dzien)
    assert "warsztat_kopia_reczna.zip" in os.listdir(kopie)
    assert kopia_automatyczna(str(instance), str(kopie), co_ile_dni=0, teraz=start + 200 * dzien) is None  # wyłączona


def test_strona_glowna_pokazuje_kopie_automatyczna(czysty_client, tmp_path):
    from kopia import kopia_automatyczna

    c = czysty_client
    c.application.config["AUTO_KOPIA_FOLDER"] = str(tmp_path / "kopie")
    assert "jeszcze nie zrobiona" in c.get("/").get_data(as_text=True)
    c.get("/fiszki/")  # tworzy bazę w instance/
    kopia_automatyczna(c.application.instance_path, str(tmp_path / "kopie"))
    assert "warsztat_auto_" in c.get("/").get_data(as_text=True)
    c.application.config["AUTO_KOPIA_DNI"] = 0
    assert "wyłączona" in c.get("/").get_data(as_text=True)


def test_pomoc_opisuje_funkcje_z_etapow_88_97(czysty_client):
    html = czysty_client.get("/pomoc").get_data(as_text=True)
    for fraza in ("Pobierz z Dziennika Ustaw", "Plan ogólny gminy", "Ceny transakcyjne (RCN)", "metodę Hellwiga",
                  "trend niestabilny", "Ankieta: przestrzeń publiczna", "wielokrotny wybór", "Odległości i cień", "AUTO_KOPIA_DNI"):
        assert fraza in html, fraza


# ---------- ETAP 102: terminy do kalendarza (.ics) ----------


def test_plik_ics_zgodny_z_rfc5545():
    from datetime import datetime, timezone

    from kalendarz import plik_ics

    terminy = [{"data": "2026-10-02", "rodzaj": "egzamin", "nazwa": "Kolokwium, prawo; część 1", "opis": "wszystkie fiszki: utrwalone 40%\nok. 5 dziennie", "url": "/fiszki/#egzaminy"},
               {"data": "2026-10-12", "rodzaj": "teren", "nazwa": "Zieleń — " + "Park Wilsona " * 8, "opis": "punkty: 0", "url": "/teren/projekty/1"}]
    ics = plik_ics(terminy, "http://127.0.0.1:5000", datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc))
    linie = ics.split("\r\n")
    assert linie[0] == "BEGIN:VCALENDAR" and linie[-2] == "END:VCALENDAR" and linie[-1] == ""
    assert "\n" not in ics.replace("\r\n", "")  # tylko CRLF
    assert all(len(l.encode("utf-8")) <= 75 for l in linie)
    rozlozone = ics.replace("\r\n ", "")  # złożenie łamanych linii
    assert "SUMMARY:Egzamin: Kolokwium\\, prawo\\; część 1" in rozlozone
    assert "DESCRIPTION:wszystkie fiszki: utrwalone 40%\\nok. 5 dziennie" in rozlozone
    assert "DTSTART;VALUE=DATE:20261002\r\nDTEND;VALUE=DATE:20261003" in ics and "DTSTAMP:20260930T080000Z" in ics
    assert rozlozone.count("BEGIN:VEVENT") == 2 and "URL:http://127.0.0.1:5000/teren/projekty/1" in rozlozone
    # UID stały — ponowny import aktualizuje zamiast dublować
    assert plik_ics(terminy, "x").split("UID:")[1][:20] == ics.split("UID:")[1][:20]


def test_trasa_kalendarza(czysty_client):
    from datetime import date, timedelta

    c = czysty_client
    c.post("/fiszki/egzaminy", data={"nazwa": "Egzamin z planowania", "data": (date.today() + timedelta(days=5)).isoformat()})
    odp = c.get("/kalendarz.ics")
    assert odp.mimetype == "text/calendar" and "warsztat_terminy.ics" in odp.headers["Content-Disposition"]
    assert "SUMMARY:Egzamin: Egzamin z planowania" in odp.get_data(as_text=True)
    assert 'href="/kalendarz.ics"' in c.get("/").get_data(as_text=True)


# ---------- ETAP 126: diagnostyka ----------


def test_diagnostyka_strona_bez_kluczy(tmp_path, monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "GEMINI_API_KEY", "tajny-klucz-123")
    app = create_app(instance_path=str(tmp_path))
    (tmp_path / "fiszki").mkdir(exist_ok=True)
    (tmp_path / "fiszki" / "fiszki.db").write_bytes(b"x" * 2000)
    with app.test_client() as c:
        html = c.get("/diagnostyka").get_data(as_text=True)
    assert "✓ ustawiony" in html and "tajny-klucz-123" not in html  # klucz nie trafia na stronę
    assert "fiszki.db" in html and "GUS — Bank Danych Lokalnych" in html and "nie sprawdzono" in html


def test_diagnostyka_uslug(tmp_path, monkeypatch):
    import requests

    import diagnostyka

    wywolane = []

    class Odp:
        def __init__(self, status):
            self.status_code = status

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def get(adres, **kw):
        wywolane.append((adres, kw.get("timeout"), kw.get("headers")))
        if "uldk" in adres:
            raise requests.Timeout()
        if "sejm" in adres:
            raise requests.ConnectionError()
        return Odp(404 if "generativelanguage" in adres else 200)

    monkeypatch.setattr(diagnostyka.requests, "get", get)
    app = create_app(instance_path=str(tmp_path))
    with app.test_client() as c:
        wyniki = {u["nazwa"]: u for u in c.get("/diagnostyka/uslugi").get_json()}
    assert len(wyniki) == len(diagnostyka.USLUGI) == len(wywolane)
    assert wyniki["GUS — Bank Danych Lokalnych"]["osiagalna"] and wyniki["GUS — Bank Danych Lokalnych"]["status"] == 200
    assert wyniki["Google — Gemini"]["osiagalna"] and wyniki["Google — Gemini"]["status"] == 404  # serwer odpowiada
    assert not wyniki["GUGiK — ULDK (działki)"]["osiagalna"] and "brak odpowiedzi" in wyniki["GUGiK — ULDK (działki)"]["blad"]
    assert "brak połączenia" in wyniki["Sejm — API Dziennika Ustaw (ELI)"]["blad"]
    assert all(t == diagnostyka.LIMIT_CZASU_S and "key" not in str(h).lower() for _, t, h in wywolane)  # bez kluczy w zapytaniach


# ---------- ETAP 127: dziennik błędów ----------


def test_dziennik_bledow(tmp_path):
    import dziennik
    import kopia

    app = create_app(instance_path=str(tmp_path))
    try:
        raise ValueError("zepsuty moduł")
    except ValueError:
        app.logger.exception("Nie udało się policzyć podsumowania modułu %s", "atlas")
    app.logger.warning("Uwaga: usługa wolno odpowiada")
    app.logger.info("informacja — do pliku nie trafia")
    wpisy = dziennik.ostatnie(str(tmp_path))
    assert [w["poziom"] for w in wpisy] == ["WARNING", "ERROR"]  # najnowsze na górze
    assert wpisy[1]["tresc"] == "Nie udało się policzyć podsumowania modułu atlas"
    assert "ValueError: zepsuty moduł" in wpisy[1]["szczegoly"] and "Traceback" in wpisy[1]["szczegoly"]
    with app.test_client() as c:
        html = c.get("/diagnostyka").get_data(as_text=True)
        assert "Ostatnie błędy" in html and "zepsuty moduł" in html
        # dziennik nie trafia do kopii zapasowej
        nazwy = __import__("zipfile").ZipFile(__import__("io").BytesIO(kopia.utworz_kopie(str(tmp_path)))).namelist()
        assert not any("logi" in n for n in nazwy)
        assert c.post("/diagnostyka/dziennik/wyczysc").status_code == 302
    assert dziennik.ostatnie(str(tmp_path)) == []
    # kolejna aplikacja (np. w testach) zastępuje plik dziennika, nie dokłada drugiego
    create_app(instance_path=str(tmp_path / "inna"))
    assert sum(1 for h in app.logger.handlers if getattr(h, "warsztat", False)) == 1


# ---------- ETAP 128: wyszukiwarka globalna ----------


def test_wyszukiwarka_globalna(tmp_path, monkeypatch):
    app = create_app(instance_path=str(tmp_path))
    with app.app_context():
        from ceny import baza as ceny_baza
        from osiedle import baza as osiedle_baza
        from przepisy import baza as przepisy_baza
        from teren import baza as teren_baza

        osiedle_baza.utworz("Kazimierz — wariant A")
        teren_baza.utworz_projekt("Inwentaryzacja Kazimierza", [])
        przepisy_baza.dodaj_akt("Ustawa o planowaniu", "u.pdf", 1, [
            {"oznaczenie": "Art. 15", "naglowek": None, "strona_od": 1, "strona_do": 1, "tekst": "Art. 15. Maksymalna intensywność zabudowy na Kazimierzu."}])
        plik_id = ceny_baza.zapisz_plik_rcn("krakow.gpkg", [], {})
        ceny_baza.dodaj_obszar_rcn(plik_id, "Kazimierz", {"type": "Polygon", "coordinates": [[[19.9, 50.0], [20.0, 50.0], [20.0, 50.1], [19.9, 50.0]]]})
    with app.test_client() as c:
        html = c.get("/szukaj?q=kazimier").get_data(as_text=True)
        for oczekiwane in ("Kazimierz — wariant A", "/osiedle/?koncepcja=1", "Inwentaryzacja Kazimierza", "/teren/projekty/1",
                           "Art. 15 — Ustawa o planowaniu", "/przepisy/akty/1#j", "obszar porównania w pliku krakow.gpkg", "/ceny/transakcje?plik=1"):
            assert oczekiwane in html, oczekiwane
        assert "\x02" not in html  # znaczniki trafień z wyszukiwarki przepisów usunięte
        assert "Nic nie znaleziono" in c.get("/szukaj?q=zzzzqqq").get_data(as_text=True)
        assert "co najmniej 2 znaki" in c.get("/szukaj?q=a").get_data(as_text=True)  # za krótka fraza — bez szukania
        # błąd jednego modułu nie blokuje pozostałych
        import teren.routes

        monkeypatch.setattr(teren.routes, "wyszukaj", lambda fraza: 1 / 0)
        html = c.get("/szukaj?q=kazimier").get_data(as_text=True)
        assert "Nie udało się przeszukać: Teren" in html and "Kazimierz — wariant A" in html
        assert 'href="/szukaj"' in c.get("/pomoc").get_data(as_text=True)  # link w nawigacji


# ---------- ETAP 129: przywracanie kopii ----------


def _kopia_z_danymi(tmp_path):
    import kopia

    app = create_app(instance_path=str(tmp_path / "instance"))
    with app.app_context():
        from osiedle import baza as ob
        ob.utworz("Koncepcja z kopii")
    return app, kopia.utworz_kopie(str(tmp_path / "instance"))


def test_przywracanie_kopii(tmp_path, monkeypatch):
    import io
    import os

    app, dane = _kopia_z_danymi(tmp_path)
    app.config["AUTO_KOPIA_FOLDER"] = str(tmp_path / "kopie")
    with app.app_context():
        from osiedle import baza as ob
        ob.utworz("Koncepcja po kopii")  # zmiana po zrobieniu kopii — zniknie po przywróceniu
    with app.test_client() as c:
        assert c.post("/kopia-zapasowa/przywroc", data={"plik": (io.BytesIO(dane), "k.zip")}, content_type="multipart/form-data").status_code == 400  # bez potwierdzenia
        odp = c.post("/kopia-zapasowa/przywroc", data={"plik": (io.BytesIO(dane), "k.zip"), "potwierdzam": "tak"}, content_type="multipart/form-data")
        assert odp.status_code == 200 and "Przywrócono dane z kopii" in odp.get_data(as_text=True)
        with app.app_context():
            from osiedle import baza as ob
            assert [k["nazwa"] for k in ob.lista()] == ["Koncepcja z kopii"]
        stare = [n for n in os.listdir(tmp_path) if n.startswith("instance_stary_")]
        assert len(stare) == 1 and os.path.exists(tmp_path / stare[0] / "osiedle")  # poprzednie dane przeniesione, nie usunięte
        przed = [n for n in os.listdir(tmp_path / "kopie") if n.startswith("warsztat_przed_przywroceniem_")]
        assert len(przed) == 1
        assert os.path.isdir(tmp_path / "instance" / "logi")  # dziennik zostaje
        # przywrócenie z listy kopii w folderze (tylko nazwy z listy)
        assert przed[0] in c.get("/kopia-zapasowa/przywroc").get_data(as_text=True)
        assert c.post("/kopia-zapasowa/przywroc", data={"z_folderu": "../../etc/passwd", "potwierdzam": "tak"}).status_code == 400
        odp = c.post("/kopia-zapasowa/przywroc", data={"z_folderu": przed[0], "potwierdzam": "tak"})
        assert odp.status_code == 200
        with app.app_context():
            from osiedle import baza as ob
            assert {k["nazwa"] for k in ob.lista()} == {"Koncepcja z kopii", "Koncepcja po kopii"}


def test_przywracanie_odrzuca_zle_kopie(tmp_path):
    import io
    import os
    import zipfile

    import kopia

    folder = tmp_path / "instance"
    folder.mkdir()
    (folder / "plik.txt").write_text("obecne")

    def zip_z(pliki):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            for n, t in pliki.items():
                z.writestr(n, t)
        b.seek(0)
        return b

    for zle, komunikat in [
        (io.BytesIO(b"to nie zip"), "nie jest plik ZIP"),
        (zip_z({"instance/a.txt": "x"}), "PRZYWRACANIE.txt"),
        (zip_z({"PRZYWRACANIE.txt": "", "instance/../../zlo.txt": "x"}), "Niedozwolona ścieżka"),
        (zip_z({"PRZYWRACANIE.txt": "", "inne/a.txt": "x"}), "Niedozwolona ścieżka"),
        (zip_z({"PRZYWRACANIE.txt": "", "instance/fiszki/fiszki.db": "nie baza"}), "uszkodzona"),
    ]:
        with pytest.raises(kopia.BladKopii, match=komunikat):
            kopia.przywroc_kopie(str(folder), zle, str(tmp_path / "kopie"))
    assert (folder / "plik.txt").read_text() == "obecne"  # nic nie ruszone
    assert not (tmp_path / "zlo.txt").exists()
    assert not [n for n in os.listdir(tmp_path) if n.startswith((".przywracanie_", "instance_stary_"))]  # sprzątnięte


# ---------- ETAP 141: „Wróć do pracy” — ostatnio używane ----------


def test_kiedy_opis():
    from datetime import datetime

    from app import kiedy_opis
    teraz = datetime(2026, 10, 2, 15, 0)
    assert kiedy_opis("2026-10-02T09:05:00", teraz) == "dziś, 9:05"
    assert kiedy_opis("2026-10-01T23:59:59.123456", teraz) == "wczoraj, 23:59"
    assert kiedy_opis("2026-09-28T10:00:00", teraz) == "4 dni temu"
    assert kiedy_opis("2026-09-01T10:00:00", teraz) == "01.09.2026"
    assert kiedy_opis("", teraz) == "" and kiedy_opis(None, teraz) == ""


def test_wroc_do_pracy(czysty_client, monkeypatch):
    c = czysty_client
    assert "Wróć do pracy" not in c.get("/").get_data(as_text=True)  # pusta instalacja — bez sekcji
    c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), "wyklad.pdf")}, content_type="multipart/form-data")
    c.post("/osiedle/koncepcje", json={"nazwa": "Wariant B"})
    c.post("/teren/projekty", data={"nazwa": "Inwentaryzacja zieleni"})
    strona = c.get("/").get_data(as_text=True)
    assert "Wróć do pracy" in strona and "wyklad.pdf" in strona and "Wariant B" in strona and "dziś," in strona
    assert "/osiedle/?koncepcja=1" in strona and "/fiszki/1/" in strona

    import osiedle.routes

    def zepsute(limit=3):
        raise RuntimeError("symulowany błąd")
    monkeypatch.setattr(osiedle.routes, "ostatnie", zepsute)
    strona = c.get("/").get_data(as_text=True)
    assert "wyklad.pdf" in strona and "/osiedle/?koncepcja=1" not in strona  # błąd jednego modułu nie psuje reszty


# ---------- ETAP 143: szybki start ----------


def test_start_nie_laduje_biblioteki_gemini():
    """google-genai to ok. 0,4 s importu — ładowana dopiero przy pierwszym zapytaniu do modelu."""
    import subprocess
    import sys
    wynik = subprocess.run([sys.executable, "-c", "import sys, tempfile, app; app.create_app(instance_path=tempfile.mkdtemp()); "
                            "print('google.genai' in sys.modules)"], capture_output=True, text=True, cwd=str(pathlib.Path(__file__).parent.parent))
    assert wynik.stdout.strip().splitlines()[-1] == "False", wynik.stderr[-500:]


# ---------- ETAP 146: pierwsze kroki ----------


def test_pierwsze_kroki_tylko_w_pustej_instalacji(czysty_client):
    c = czysty_client
    c.application.config["GEMINI_API_KEY"] = ""
    c.application.config["GUS_BDL_API_KEY"] = "klucz"
    strona = c.get("/").get_data(as_text=True)
    assert "Pierwsze kroki" in strona and "GEMINI_API_KEY=…" in strona and "Klucz GUS jest ustawiony" in strona
    assert "pierwsze-kroki__stan--ok" in strona  # GUS — tak, Gemini — nie
    c.application.config["GEMINI_API_KEY"] = "x"
    assert "Klucz Gemini jest ustawiony" in c.get("/").get_data(as_text=True)
    c.post("/osiedle/koncepcje", json={"nazwa": "Pierwsza"})
    assert "Pierwsze kroki" not in c.get("/").get_data(as_text=True)  # coś zapisane — karta znika


# ---------- ETAP 167: skróty klawiszowe ----------


def test_okno_skrotow(client):
    glowna = client.get("/").get_data(as_text=True)
    assert 'id="okno-skrotow"' in glowna and "skroty.js" in glowna and 'data-url-szukaj="/szukaj"' in glowna
    powtorka = client.get("/fiszki/powtorka").get_data(as_text=True)
    assert "nie umiem / trudne / umiem" in powtorka  # skróty strony w oknie
    assert "nie umiem / trudne / umiem" not in glowna
    for strona in ("/atlas/", "/mpzp/", "/fiszki/", "/przepisy/", "/szukaj"):
        assert "data-skrot-szukaj" in client.get(strona).get_data(as_text=True), strona
    assert 'id="skroty"' in client.get("/pomoc").get_data(as_text=True)
