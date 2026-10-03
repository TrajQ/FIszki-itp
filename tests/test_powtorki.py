import io
import json
from datetime import date

import pytest

from app import create_app
from fiszki import powtorki

PDF_MINIMALNY = b"%PDF-1.4\n%testowy plik\n"


# ---------- logika Leitnera ----------


def test_umiem_przesuwa_do_nastepnego_pudelka():
    assert powtorki.nastepny_stan(1, "umiem", date(2026, 10, 1)) == (2, date(2026, 10, 3))
    assert powtorki.nastepny_stan(4, "umiem", date(2026, 10, 1)) == (5, date(2026, 10, 17))


def test_umiem_w_ostatnim_pudelku_zostaje_w_nim():
    assert powtorki.nastepny_stan(5, "umiem", date(2026, 10, 1)) == (5, date(2026, 10, 17))


def test_nie_umiem_cofa_do_pudelka_1_na_dzis():
    assert powtorki.nastepny_stan(4, "nie_umiem", date(2026, 10, 1)) == (1, date(2026, 10, 1))


def test_nieznany_wynik_to_blad():
    with pytest.raises(ValueError):
        powtorki.nastepny_stan(1, "moze", date(2026, 10, 1))


# ---------- endpointy ----------


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    ustaw_dzis(monkeypatch, date(2026, 10, 1))
    with app.test_client() as client:
        yield client


def ustaw_dzis(monkeypatch, dzien):
    monkeypatch.setattr(powtorki, "dzisiaj", lambda: dzien)


def wgraj_pdf(client, nazwa="test.pdf"):
    return client.post(
        "/fiszki/upload",
        data={"plik": (io.BytesIO(PDF_MINIMALNY), nazwa)},
        content_type="multipart/form-data",
    )


def dodaj_fiszke(client, pdf_id=1, pytanie="P?"):
    odpowiedz = client.post(
        f"/fiszki/{pdf_id}/fiszki",
        data=json.dumps({"strona": 1, "fragment_tekstu": "frag", "pytanie": pytanie, "odpowiedz": "O."}),
        content_type="application/json",
    )
    return odpowiedz.get_json()["id"]


def ocen(client, fiszka_id, wynik):
    return client.post(
        f"/fiszki/powtorka/{fiszka_id}", data=json.dumps({"wynik": wynik}), content_type="application/json"
    )


def kolejka(client, pdf_id=None):
    adres = "/fiszki/powtorka/kolejka" + (f"?pdf_id={pdf_id}" if pdf_id else "")
    return client.get(adres).get_json()


def test_nowa_fiszka_jest_od_razu_do_powtorki(client):
    wgraj_pdf(client)
    fiszka_id = dodaj_fiszke(client)

    dane = kolejka(client)
    assert [f["id"] for f in dane] == [fiszka_id]
    assert dane[0]["pudelko"] == 1
    assert dane[0]["nazwa_oryginalna"] == "test.pdf"


def test_umiem_znika_z_kolejki_i_wraca_po_terminie(client, monkeypatch):
    wgraj_pdf(client)
    fiszka_id = dodaj_fiszke(client)

    odpowiedz = ocen(client, fiszka_id, "umiem")
    assert odpowiedz.status_code == 200
    assert odpowiedz.get_json() == {"fiszka_id": fiszka_id, "pudelko": 2, "nastepna_powtorka": "2026-10-03"}
    assert kolejka(client) == []

    ustaw_dzis(monkeypatch, date(2026, 10, 3))
    assert [f["pudelko"] for f in kolejka(client)] == [2]


def test_nie_umiem_zostaje_w_kolejce_z_pudelkiem_1(client):
    wgraj_pdf(client)
    fiszka_id = dodaj_fiszke(client)
    ocen(client, fiszka_id, "umiem")
    ocen(client, fiszka_id, "umiem")  # ponowna ocena tego samego dnia: pudełko 3

    odpowiedz = ocen(client, fiszka_id, "nie_umiem")
    assert odpowiedz.get_json()["pudelko"] == 1
    assert [f["id"] for f in kolejka(client)] == [fiszka_id]


def test_kolejka_filtruje_po_pdf_i_zaczyna_od_nizszych_pudelek(client, monkeypatch):
    wgraj_pdf(client)
    wgraj_pdf(client, nazwa="drugi.pdf")
    a = dodaj_fiszke(client, pytanie="A")
    b = dodaj_fiszke(client, pytanie="B")
    c = dodaj_fiszke(client, pdf_id=2, pytanie="C")
    ocen(client, a, "umiem")  # a -> pudełko 2, termin 3.10

    ustaw_dzis(monkeypatch, date(2026, 10, 5))
    assert [f["id"] for f in kolejka(client)] == [b, c, a]
    assert [f["id"] for f in kolejka(client, pdf_id=2)] == [c]


def test_bledne_dane_powtorki(client):
    wgraj_pdf(client)
    fiszka_id = dodaj_fiszke(client)
    assert ocen(client, fiszka_id, "moze").status_code == 400
    assert ocen(client, 999, "umiem").status_code == 404


def test_usuniecie_fiszki_usuwa_stan_powtorki(client):
    wgraj_pdf(client)
    fiszka_id = dodaj_fiszke(client)
    ocen(client, fiszka_id, "umiem")

    client.delete(f"/fiszki/1/fiszki/{fiszka_id}")

    from fiszki.baza import get_db

    with client.application.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM powtorki").fetchone()[0] == 0


def test_strony_powtorki_i_licznik_na_liscie(client):
    wgraj_pdf(client)
    dodaj_fiszke(client)
    dodaj_fiszke(client)

    assert client.get("/fiszki/powtorka").status_code == 200
    assert client.get("/fiszki/powtorka?pdf_id=1").status_code == 200
    assert client.get("/fiszki/powtorka?pdf_id=9").status_code == 404

    strona = client.get("/fiszki/").get_data(as_text=True)
    assert "2 do powtórki" in strona
    assert "Zacznij powtórkę" in strona


# ---------- ETAP 39: „trudne”, tryb przed egzaminem ----------


def test_trudne_zostaje_w_pudelku_i_wraca_jutro():
    assert powtorki.nastepny_stan(3, "trudne", date(2026, 10, 1)) == (3, date(2026, 10, 2))
    assert powtorki.nastepny_stan(1, "trudne", date(2026, 10, 1)) == (1, date(2026, 10, 2))


def test_endpoint_przyjmuje_trudne(client):
    wgraj_pdf(client)
    fiszka_id = dodaj_fiszke(client)
    odpowiedz = ocen(client, fiszka_id, "trudne")
    assert odpowiedz.status_code == 200
    assert odpowiedz.get_json()["pudelko"] == 1
    # jutro, więc dziś już nie ma jej w kolejce
    assert client.get("/fiszki/powtorka/kolejka").get_json() == []


def test_kolejka_przed_egzaminem_ma_wszystkie_fiszki(client):
    wgraj_pdf(client)
    pierwsza = dodaj_fiszke(client)
    druga = dodaj_fiszke(client)
    ocen(client, pierwsza, "umiem")  # zaplanowana za kilka dni

    zwykla = client.get("/fiszki/powtorka/kolejka").get_json()
    egzamin = client.get("/fiszki/powtorka/kolejka?wszystkie=1").get_json()

    assert [f["id"] for f in zwykla] == [druga]
    assert sorted(f["id"] for f in egzamin) == sorted([pierwsza, druga])
    html = client.get("/fiszki/powtorka?wszystkie=1").get_data(as_text=True)
    assert "Przed egzaminem" in html and "TRYB_EGZAMINU = true" in html


# ---------- ETAP 206: przeplatanie tematów ----------


def test_przeplec_kolejnosc():
    fiszki = [{"id": i, "g": g} for i, g in enumerate("AAAABBC")]
    wynik = powtorki.przeplec(fiszki, lambda f: f["g"])
    assert [f["g"] for f in wynik] == list("ABABACA") and sorted(f["id"] for f in wynik) == list(range(7))
    assert [f["id"] for f in wynik if f["g"] == "A"] == [0, 1, 2, 3]  # w grupie kolejność wejściowa
    assert powtorki.przeplec([], lambda f: 1) == []
    assert [f["id"] for f in powtorki.przeplec(fiszki[:3], lambda f: f["g"])] == [0, 1, 2]  # jedna grupa — bez zmian


def test_kolejka_z_przeplataniem(client):
    wgraj_pdf(client)
    ids = []
    for i, temat in enumerate(["planowanie", "planowanie", "planowanie", "prawo", "prawo", ""]):
        odp = client.post("/fiszki/1/fiszki", json={"strona": 1, "fragment_tekstu": "f", "pytanie": f"P{i}?", "odpowiedz": "O.", "tematy": temat})
        ids.append(odp.get_json()["id"])
    zwykla = client.get("/fiszki/powtorka/kolejka").get_json()
    assert [f["id"] for f in zwykla] == ids and zwykla[0]["tematy"] == ["planowanie"] and zwykla[5]["tematy"] == []
    przeplatana = client.get("/fiszki/powtorka/kolejka?przeplatanie=1").get_json()
    grupy = [f["tematy"][0] if f["tematy"] else "plik" for f in przeplatana]
    assert all(a != b for a, b in zip(grupy, grupy[1:])) and sorted(f["id"] for f in przeplatana) == sorted(ids)
    # przy filtrze tematu przeplatanie nie działa (jedna grupa)
    assert [f["id"] for f in client.get("/fiszki/powtorka/kolejka?przeplatanie=1&temat=prawo").get_json()] == ids[3:5]
    assert "tryb-przeplatania" in client.get("/fiszki/powtorka").get_data(as_text=True)
    assert "tryb-przeplatania" not in client.get("/fiszki/powtorka?temat=prawo").get_data(as_text=True)


# ---------- ETAP 207: wyjaśnienie po odsłonięciu ----------


def test_wyjasnienie_wlasne_i_gemini(client, monkeypatch):
    from types import SimpleNamespace

    from config import Config
    from dane import gemini

    wgraj_pdf(client)
    odp = client.post("/fiszki/1/fiszki", json={"strona": 1, "fragment_tekstu": "Plan miejscowy uchwala rada gminy w 2 etapach.",
                                                 "pytanie": "Kto uchwala plan?", "odpowiedz": "Rada gminy."})
    fid = odp.get_json()["id"]
    assert client.get("/fiszki/powtorka/kolejka").get_json()[0]["wyjasnienie"] is None
    assert client.post(f"/fiszki/wyjasnienie/{fid}", json={"tekst": "  Bo   uchwała  "}).get_json() == {"tekst": "Bo uchwała", "zrodlo": "wlasne"}
    assert client.get("/fiszki/powtorka/kolejka").get_json()[0]["wyjasnienie"]["tekst"] == "Bo uchwała"
    assert client.post(f"/fiszki/wyjasnienie/{fid}", json={"tekst": " "}).status_code == 400
    assert client.post(f"/fiszki/wyjasnienie/{fid}", json={"tekst": "x" * 1501}).status_code == 400
    assert client.post("/fiszki/wyjasnienie/999", json={"tekst": "a"}).status_code == 404
    # Gemini: liczba ze źródła przechodzi, obca — odrzucona; bez klucza — komunikat
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "test")
    odpowiedzi = iter(["Plan uchwala rada gminy w 2 etapach, więc to ona.", "Rada gminy, 3 razy w roku."])
    monkeypatch.setattr(gemini, "_generuj", lambda *a, **k: SimpleNamespace(text=next(odpowiedzi)))
    w = client.post(f"/fiszki/wyjasnienie/{fid}/gemini").get_json()
    assert w["zrodlo"] == "gemini" and "2 etapach" in w["tekst"]
    r = client.post(f"/fiszki/wyjasnienie/{fid}/gemini")
    assert r.status_code == 502 and "3" in r.get_json()["blad"]
    assert client.get("/fiszki/powtorka/kolejka").get_json()[0]["wyjasnienie"]["zrodlo"] == "gemini"  # odrzucone nie nadpisuje
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    assert "GEMINI_API_KEY" in client.post(f"/fiszki/wyjasnienie/{fid}/gemini").get_json()["blad"]
    assert client.delete(f"/fiszki/wyjasnienie/{fid}").status_code == 204
    assert client.get("/fiszki/powtorka/kolejka").get_json()[0]["wyjasnienie"] is None
    # usunięcie fiszki usuwa wyjaśnienie (ON DELETE CASCADE)
    client.post(f"/fiszki/wyjasnienie/{fid}", json={"tekst": "a"})
    client.delete(f"/fiszki/1/fiszki/{fid}")
    with client.application.app_context():
        from fiszki.baza import get_db
        assert get_db().execute("SELECT COUNT(*) FROM wyjasnienia_fiszek").fetchone()[0] == 0
