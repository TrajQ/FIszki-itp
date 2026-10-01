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
    assert "SUMMARY:Egzamin: Kolokwium\\, prawo\; część 1" in rozlozone
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
