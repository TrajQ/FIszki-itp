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
