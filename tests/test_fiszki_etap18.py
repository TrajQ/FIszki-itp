import io
import json
from datetime import date

import pytest

import fiszki.routes as fiszki_routes
from app import create_app
from dane.gemini import BladGemini, sparsuj_liste_fiszek
from fiszki import powtorki
from fiszki.strona import fragment_na_stronie, zakotwiczone

STRONA = (
    "Miejscowy plan zagospodarowania przestrzennego jest aktem prawa\n"
    "miejscowego uchwalanym przez radę gminy. Ład przestrzenny to takie "
    "ukształtowanie przestrzeni, które tworzy harmonijną całość."
)


# ---------- parser odpowiedzi modelu ----------


def test_sparsuj_liste_fiszek_rozne_formaty():
    lista = '[{"pytanie": "P?", "odpowiedz": "O.", "fragment": "F"}]'
    assert sparsuj_liste_fiszek(lista) == [{"pytanie": "P?", "odpowiedz": "O.", "fragment": "F"}]
    assert len(sparsuj_liste_fiszek("```json\n" + lista + "\n```")) == 1
    assert len(sparsuj_liste_fiszek('{"fiszki": ' + lista + "}")) == 1
    # niepełne pozycje pomijane
    assert sparsuj_liste_fiszek('[{"pytanie": "P?", "odpowiedz": ""}, "x"]') == []
    with pytest.raises(BladGemini):
        sparsuj_liste_fiszek("to nie JSON")


# ---------- kotwica w źródle ----------


def test_fragment_na_stronie_ignoruje_biale_znaki():
    assert fragment_na_stronie("aktem prawa miejscowego uchwalanym", STRONA)  # przez nową linię
    assert fragment_na_stronie("aktem  prawa\n\nmiejscowego", STRONA)
    assert not fragment_na_stronie("aktem prawa krajowego", STRONA)
    assert not fragment_na_stronie("   ", STRONA)


def test_zakotwiczone_odrzuca_wymyslone_cytaty():
    propozycje = [
        {"pytanie": "A?", "odpowiedz": "a", "fragment": "Ład przestrzenny to takie ukształtowanie"},
        {"pytanie": "B?", "odpowiedz": "b", "fragment": "Plan uchwala wojewoda."},
    ]
    dobre, odrzucone = zakotwiczone(propozycje, STRONA)
    assert [p["pytanie"] for p in dobre] == ["A?"]
    assert odrzucone == 1


# ---------- endpointy ----------


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    monkeypatch.setattr(powtorki, "dzisiaj", lambda: date(2026, 10, 10))
    with app.test_client() as c:
        c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), "a.pdf")}, content_type="multipart/form-data")
        yield c


def test_szkice_strony_zwracaja_tylko_zakotwiczone(client, monkeypatch):
    otrzymany_tekst = []

    def falszywy_gemini(tekst):
        otrzymany_tekst.append(tekst)
        return [
            {"pytanie": "Czym jest MPZP?", "odpowiedz": "Aktem prawa miejscowego.", "fragment": "jest aktem prawa miejscowego"},
            {"pytanie": "Zmyślone?", "odpowiedz": "Tak.", "fragment": "cytat, którego nie ma"},
        ]

    monkeypatch.setattr(fiszki_routes, "zaproponuj_fiszki_ze_strony", falszywy_gemini)
    odpowiedz = client.post("/fiszki/1/szkice-strony", data=json.dumps({"strona": 1, "tekst": STRONA}), content_type="application/json")

    assert odpowiedz.status_code == 200
    dane = odpowiedz.get_json()
    assert [p["pytanie"] for p in dane["propozycje"]] == ["Czym jest MPZP?"]
    assert dane["odrzucone"] == 1
    assert otrzymany_tekst == [STRONA]


def test_szkice_strony_bledy(client, monkeypatch):
    assert client.post("/fiszki/1/szkice-strony", data=json.dumps({"tekst": "krótko"}), content_type="application/json").status_code == 400
    assert client.post("/fiszki/9/szkice-strony", data=json.dumps({"tekst": STRONA}), content_type="application/json").status_code == 404

    def blad(tekst):
        raise BladGemini("Brak GEMINI_API_KEY w konfiguracji (.env).")

    monkeypatch.setattr(fiszki_routes, "zaproponuj_fiszki_ze_strony", blad)
    odpowiedz = client.post("/fiszki/1/szkice-strony", data=json.dumps({"tekst": STRONA}), content_type="application/json")
    assert odpowiedz.status_code == 502
    assert "GEMINI_API_KEY" in odpowiedz.get_json()["blad"]


# ---------- statystyki nauki ----------


def dodaj_fiszke(client):
    return client.post(
        "/fiszki/1/fiszki",
        data=json.dumps({"strona": 1, "fragment_tekstu": "f", "pytanie": "P?", "odpowiedz": "O."}),
        content_type="application/json",
    ).get_json()["id"]


def ocen(client, fiszka_id, wynik):
    client.post(f"/fiszki/powtorka/{fiszka_id}", data=json.dumps({"wynik": wynik}), content_type="application/json")


def test_statystyki_nauki_seria_aktywnosc_skutecznosc(client, monkeypatch):
    a, b = dodaj_fiszke(client), dodaj_fiszke(client)
    for dzien, wyniki in [(8, ["umiem"]), (9, ["umiem", "nie_umiem"]), (10, ["umiem", "umiem", "nie_umiem"])]:
        monkeypatch.setattr(powtorki, "dzisiaj", lambda d=dzien: date(2026, 10, d))
        for i, w in enumerate(wyniki):
            ocen(client, [a, b][i % 2], w)

    s = client.get("/fiszki/statystyki").get_json()
    assert s["seria_dni"] == 3
    assert s["dzis"] == 3
    assert s["powtorki_30_dni"] == 6
    assert s["skutecznosc_proc"] == pytest.approx(100 * 4 / 6)
    assert len(s["aktywnosc"]) == 30
    assert s["aktywnosc"][-1] == {"data": "2026-10-10", "powtorki": 3}
    assert "dni z rzędu" in client.get("/fiszki/").get_data(as_text=True)


def test_seria_nie_przerywa_sie_przed_koncem_dnia_ale_po_przerwie_tak(client, monkeypatch):
    a = dodaj_fiszke(client)
    monkeypatch.setattr(powtorki, "dzisiaj", lambda: date(2026, 10, 9))
    ocen(client, a, "umiem")

    monkeypatch.setattr(powtorki, "dzisiaj", lambda: date(2026, 10, 10))
    assert client.get("/fiszki/statystyki").get_json()["seria_dni"] == 1  # dziś jeszcze nic, wczoraj było

    monkeypatch.setattr(powtorki, "dzisiaj", lambda: date(2026, 10, 12))
    s = client.get("/fiszki/statystyki").get_json()
    assert s["seria_dni"] == 0
    assert s["skutecznosc_proc"] == 100


def test_bez_powtorek_statystyki_puste_i_karta_ukryta(client):
    s = client.get("/fiszki/statystyki").get_json()
    assert s["powtorki_30_dni"] == 0 and s["skutecznosc_proc"] is None and s["seria_dni"] == 0
    assert "dni z rzędu" not in client.get("/fiszki/").get_data(as_text=True)
