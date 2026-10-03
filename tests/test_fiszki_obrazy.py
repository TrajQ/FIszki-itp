"""Fiszka z wycinkiem rysunku z PDF (ETAP 154)."""

import base64
import io
import os
import re
import struct
import zlib

import pytest

from app import create_app


def png(szer=4, wys=3) -> bytes:
    """Najmniejszy poprawny PNG (szary)."""
    def blok(typ, dane):
        return struct.pack(">I", len(dane)) + typ + dane + struct.pack(">I", zlib.crc32(typ + dane))
    surowe = b"".join(b"\x00" + b"\x80" * szer for _ in range(wys))
    return b"\x89PNG\r\n\x1a\n" + blok(b"IHDR", struct.pack(">IIBBBBB", szer, wys, 8, 0, 0, 0, 0)) + blok(b"IDAT", zlib.compress(surowe)) + blok(b"IEND", b"")


def data_url(dane: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(dane).decode()


@pytest.fixture
def client(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4 atrapa"), "wyklad.pdf")}, content_type="multipart/form-data")
        c.tmp = tmp_path
        yield c


def fiszka(client, **zmiany):
    dane = {"strona": 2, "fragment_tekstu": "[wycinek rysunku, s. 2]", "pytanie": "Co oznacza symbol MN?", "odpowiedz": "Zabudowa jednorodzinna"}
    return client.post("/fiszki/1/fiszki", json={**dane, **zmiany})


def test_fiszka_z_wycinkiem_wszedzie(client):
    odp = fiszka(client, obraz=data_url(png()))
    assert odp.status_code == 201
    url = odp.get_json()["obraz"]
    assert re.fullmatch(r"/fiszki/obrazy/[0-9a-f]{32}\.png", url)
    obraz = client.get(url)
    assert obraz.status_code == 200 and obraz.mimetype == "image/png" and obraz.data == png()
    obraz.close()  # plik wysyłany strumieniem — odpowiedź trzeba zamknąć
    fiszka(client)  # zwykła fiszka — bez obrazu
    lista = client.get("/fiszki/1/fiszki").get_json()
    assert [f["obraz"] for f in lista] == [url, None]
    assert client.get("/fiszki/powtorka/kolejka").get_json()[0]["obraz"] == url
    assert url in client.get("/fiszki/druk").get_data(as_text=True)
    telefon = client.get("/fiszki/telefon.html").get_data(as_text=True)
    assert data_url(png()) in telefon  # osadzony — telefon działa bez Warsztatu
    for i in range(3):  # quiz potrzebuje kilku różnych odpowiedzi
        fiszka(client, odpowiedz=f"inna {i}")
    pytania = client.get("/fiszki/quiz/pytania?ziarno=1&liczba=50").get_json()
    assert {p["obraz"] for p in pytania if p["fiszka_id"] == 1} == {url}


def test_zly_obraz_i_sprzatanie(client):
    for zly in ["data:image/jpeg;base64,AAAA", data_url(b"nie png"), "data:image/png;base64,!!!", 5]:
        odp = fiszka(client, obraz=zly)
        assert odp.status_code == 400, zly
    assert client.get("/fiszki/1/fiszki").get_json() == []  # nic nie zapisane
    duzy = data_url(png() + b"\x00" * 2_100_000)
    assert "za duży" in fiszka(client, obraz=duzy).get_json()["blad"]
    assert client.get("/fiszki/obrazy/..%2Fapp.py").status_code == 404
    assert client.get("/fiszki/obrazy/nie-ma.png").status_code == 404

    folder = client.tmp / "fiszki" / "obrazy"
    pierwsza = fiszka(client, obraz=data_url(png())).get_json()
    druga = fiszka(client, obraz=data_url(png(8, 8))).get_json()
    assert len(os.listdir(folder)) == 2
    client.delete(f"/fiszki/1/fiszki/{pierwsza['id']}")
    assert len(os.listdir(folder)) == 1 and client.get(pierwsza["obraz"]).status_code == 404
    client.post("/fiszki/1/usun")  # usunięcie PDF-a usuwa fiszki i ich wycinki
    assert os.listdir(folder) == [] and client.get(druga["obraz"]).status_code == 404


# ---------- ETAP 185: zasłonięte fragmenty obrazu ----------


def test_zasloniete_fragmenty(client):
    wzor = fiszka(client, obraz=data_url(png()), tematy=["planowanie"]).get_json()
    url = wzor["obraz"]
    adres = f"/fiszki/1/fiszki/{wzor['id']}/zaslony"
    odp = client.post(adres, json={"prostokaty": [[0.1, 0.2, 0.3, 0.1], [0.5, 0.5, 0.2, 0.2]], "odpowiedzi": ["Warta", " Cytadela "]})
    assert odp.status_code == 201 and odp.get_json()["liczba"] == 2
    lista = client.get("/fiszki/1/fiszki").get_json()
    nowe = [f for f in lista if f["zaslona"]]
    assert [f["odpowiedz"] for f in nowe] == ["Warta", "Cytadela"] and {f["obraz"] for f in nowe} == {url}  # ten sam plik
    assert nowe[0]["zaslona"] == [0.1, 0.2, 0.3, 0.1] and nowe[0]["pytanie"] == "Co jest w zasłoniętym miejscu?"
    assert nowe[0]["tematy"] == ["planowanie"] and nowe[0]["strona"] == 2
    assert next(f for f in lista if f["id"] == wzor["id"])["zaslona"] is None  # wzór bez zmian
    assert any(f.get("zaslona") for f in client.get("/fiszki/powtorka/kolejka").get_json())
    druk = client.get("/fiszki/druk").get_data(as_text=True)
    assert 'class="zaslona" style="left: 10.0%' in druk
    assert '"zaslona": [0.1, 0.2, 0.3, 0.1]' in client.get("/fiszki/telefon.html").get_data(as_text=True)
    # usunięcie wzoru nie kasuje pliku, bo używają go fiszki z zasłonami
    client.delete(f"/fiszki/1/fiszki/{wzor['id']}")
    obraz = client.get(url)
    assert obraz.status_code == 200
    obraz.close()
    for zle in ({"prostokaty": [[0.9, 0.9, 0.3, 0.3]], "odpowiedzi": ["x"]}, {"prostokaty": [[0.1, 0.1, 0.001, 0.2]], "odpowiedzi": ["x"]},
                {"prostokaty": [], "odpowiedzi": []}, {"prostokaty": [[0.1, 0.1, 0.2, 0.2]], "odpowiedzi": [" "]},
                {"prostokaty": [[0.1, 0.1, 0.2, 0.2]] * 13, "odpowiedzi": ["x"] * 13}, {"prostokaty": [[0.1, 0.1, True, 0.2]], "odpowiedzi": ["x"]}):
        assert client.post(f"/fiszki/1/fiszki/{nowe[0]['id']}/zaslony", json=zle).status_code == 400, zle
    bez_obrazu = fiszka(client).get_json()
    assert client.post(f"/fiszki/1/fiszki/{bez_obrazu['id']}/zaslony", json={"prostokaty": [[0.1, 0.1, 0.2, 0.2]], "odpowiedzi": ["x"]}).status_code == 404


# ---------- ETAP 212: kosz ----------


def test_kosz_fiszki_i_pdf(client):
    from datetime import datetime, timedelta

    from fiszki import kosz
    from fiszki.baza import get_db

    f1 = fiszka(client, obraz=data_url(png()), tematy="planowanie").get_json()
    f2 = fiszka(client, pytanie="Drugie?").get_json()
    client.post(f"/fiszki/powtorka/{f1['id']}", json={"wynik": "umiem"})
    client.post(f"/fiszki/wyjasnienie/{f1['id']}", json={"tekst": "Bo tak."})
    plik_obrazu = f1["obraz"].rsplit("/", 1)[1]
    folder_obrazow = os.path.join(str(client.tmp), "fiszki", "obrazy")
    # usunięcie fiszki → kosz, plik obrazu przeniesiony; przywrócenie — wszystko wraca
    kosz_id = client.delete(f"/fiszki/1/fiszki/{f1['id']}").get_json()["kosz_id"]
    assert not os.path.exists(os.path.join(folder_obrazow, plik_obrazu))
    assert [f["id"] for f in client.get("/fiszki/1/fiszki").get_json()] == [f2["id"]]
    assert "Kosz (1)" in client.get("/fiszki/").get_data(as_text=True)
    r = client.post(f"/fiszki/kosz/{kosz_id}/przywroc", headers={"Accept": "application/json"})
    assert r.get_json() == {"rodzaj": "fiszka", "pdf_id": 1}
    przywrocona = next(f for f in client.get("/fiszki/1/fiszki").get_json() if f["id"] == f1["id"])
    assert przywrocona["tematy"] == ["planowanie"] and przywrocona["obraz"] == f1["obraz"]
    assert os.path.exists(os.path.join(folder_obrazow, plik_obrazu))
    kolejka = {f["id"]: f for f in client.get("/fiszki/powtorka/kolejka?wszystkie=1").get_json()}
    assert kolejka[f1["id"]]["pudelko"] == 2 and kolejka[f1["id"]]["wyjasnienie"]["tekst"] == "Bo tak."
    assert client.post(f"/fiszki/kosz/{kosz_id}/przywroc", headers={"Accept": "application/json"}).status_code == 400
    # usunięcie całego PDF-a i przywrócenie
    client.post("/fiszki/egzaminy", data={"nazwa": "Kolokwium", "data": "2030-01-10", "pdf_id": "1"})
    client.delete(f"/fiszki/1/fiszki/{f2['id']}")  # fiszka w koszu osobno
    client.post("/fiszki/1/usun")
    folder_pdf = os.path.join(str(client.tmp), "fiszki", "pliki")
    assert os.listdir(folder_pdf) == [] and client.get("/fiszki/1/").status_code == 404
    wpisy = client.get("/fiszki/").get_data(as_text=True)
    assert "wyklad.pdf — fiszek: 1" in wpisy
    with client.application.app_context():
        lista = kosz.lista(get_db())
    pdf_wpis = next(k for k in lista if k["rodzaj"] == "pdf")
    fiszka_wpis = next(k for k in lista if k["rodzaj"] == "fiszka")
    r = client.post(f"/fiszki/kosz/{fiszka_wpis['id']}/przywroc", headers={"Accept": "application/json"})
    assert r.status_code == 400 and "najpierw przywróć plik" in r.get_json()["blad"]
    assert client.post(f"/fiszki/kosz/{pdf_wpis['id']}/przywroc").headers["Location"].endswith("/fiszki/1/")
    assert len(os.listdir(folder_pdf)) == 1 and len(client.get("/fiszki/1/fiszki").get_json()) == 1
    assert "Kolokwium" in client.get("/fiszki/").get_data(as_text=True)
    client.post(f"/fiszki/kosz/{fiszka_wpis['id']}/przywroc")
    assert len(client.get("/fiszki/1/fiszki").get_json()) == 2
    # po 30 dniach wpis i plik znikają
    client.delete(f"/fiszki/1/fiszki/{f1['id']}")
    with client.application.app_context():
        assert kosz.wyczysc_stare(get_db(), datetime.now() + timedelta(days=31)) == 1
        assert kosz.lista(get_db()) == [] and os.listdir(kosz.folder()) == []


def test_kosz_obejmuje_wszystkie_tabele_fiszek(client):
    """Nowa tabela z fiszka_id albo pdf_id musi być w kosz.TABELE_* — inaczej przywrócenie by ją gubiło."""
    from fiszki import kosz
    from fiszki.baza import get_db

    znane = {t for t, _ in kosz.TABELE_PDF} | set(kosz.TABELE_FISZKI) | set(kosz.TABELE_ZOSTAJA)
    with client.application.app_context():
        db = get_db()
        for (tabela,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
            kolumny = {w[1] for w in db.execute(f"PRAGMA table_info({tabela})")}
            if kolumny & {"fiszka_id", "pdf_id"}:
                assert tabela in znane, tabela
