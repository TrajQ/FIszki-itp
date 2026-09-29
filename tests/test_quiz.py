import io
import json
import random
from datetime import date

import pytest

from app import create_app
from fiszki import powtorki
from fiszki.quiz import ZaMaloFiszek, uloz_quiz


def fiszka(i, pdf_id=1, odpowiedz=None):
    return {"id": i, "pdf_id": pdf_id, "strona": 1, "pytanie": f"P{i}?", "odpowiedz": odpowiedz or f"O{i}"}


def test_quiz_ma_poprawna_i_trzy_rozne_bledne():
    pula = [fiszka(i) for i in range(1, 7)]
    pytania = uloz_quiz(pula, pula, 5, random.Random(1))
    assert len(pytania) == 5
    for p in pytania:
        assert len(p["odpowiedzi"]) == 4
        assert len(set(p["odpowiedzi"])) == 4
        assert p["odpowiedzi"][p["poprawna"]] == f"O{p['fiszka_id']}"


def test_dystraktory_najpierw_z_tego_samego_pdf():
    pula = [fiszka(i, pdf_id=1) for i in range(1, 5)] + [fiszka(i, pdf_id=2) for i in range(5, 10)]
    zakres = [f for f in pula if f["pdf_id"] == 1]
    for p in uloz_quiz(zakres, pula, 4, random.Random(3)):
        # w PDF 1 są 4 fiszki → 3 błędne odpowiedzi to dokładnie pozostałe z PDF 1
        assert all(o in {"O1", "O2", "O3", "O4"} for o in p["odpowiedzi"])


def test_identyczne_odpowiedzi_nie_sa_dystraktorami():
    pula = [fiszka(1, odpowiedz="Rada gminy."), fiszka(2, odpowiedz="rada  gminy."), fiszka(3), fiszka(4), fiszka(5)]
    p = uloz_quiz([pula[0]], pula, 1, random.Random(0))[0]
    assert sum(1 for o in p["odpowiedzi"] if o.casefold().replace("  ", " ") == "rada gminy.") == 1


def test_za_malo_fiszek():
    with pytest.raises(ZaMaloFiszek):
        uloz_quiz([fiszka(1)], [fiszka(i) for i in range(1, 4)], 1, random.Random(0))
    same_te_same = [fiszka(i, odpowiedz="Tak") for i in range(1, 6)]
    with pytest.raises(ZaMaloFiszek):
        uloz_quiz(same_te_same, same_te_same, 3, random.Random(0))


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    monkeypatch.setattr(powtorki, "dzisiaj", lambda: date(2026, 10, 10))
    with app.test_client() as c:
        for n in ("a.pdf", "b.pdf"):
            c.post("/fiszki/upload", data={"plik": (io.BytesIO(b"%PDF-1.4\n"), n)}, content_type="multipart/form-data")
        for i, pdf_id in enumerate([1, 1, 1, 2, 2], start=1):
            c.post(
                f"/fiszki/{pdf_id}/fiszki",
                data=json.dumps({"strona": i, "fragment_tekstu": "f", "pytanie": f"P{i}?", "odpowiedz": f"O{i}"}),
                content_type="application/json",
            )
        yield c


def test_endpoint_quizu(client):
    wszystkie = client.get("/fiszki/quiz/pytania?ziarno=1&liczba=10").get_json()
    assert len(wszystkie) == 5
    z_pdf = client.get("/fiszki/quiz/pytania?pdf_id=2&ziarno=1").get_json()
    assert {p["pdf_id"] for p in z_pdf} == {2} and len(z_pdf) == 2
    # powtarzalne dla tego samego ziarna
    assert client.get("/fiszki/quiz/pytania?ziarno=7").get_json() == client.get("/fiszki/quiz/pytania?ziarno=7").get_json()
    assert client.get("/fiszki/quiz").status_code == 200
    assert client.get("/fiszki/quiz?pdf_id=9").status_code == 404


def test_najtrudniejsze_fiszki(client):
    def ocen(fid, wynik):
        client.post(f"/fiszki/powtorka/{fid}", data=json.dumps({"wynik": wynik}), content_type="application/json")

    for w in ["nie_umiem", "nie_umiem", "umiem"]:
        ocen(3, w)
    ocen(1, "nie_umiem")
    ocen(2, "umiem")

    strona = client.get("/fiszki/").get_data(as_text=True)
    assert "Najtrudniejsze fiszki" in strona
    assert strona.index("P3?") < strona.index("P1?")
    assert "„nie umiem”: 2 z 3" in strona
    assert "Quiz ABCD" in strona
