"""Warstwa Gemini (dane/gemini.py) bez sieci: podmieniony klient google-genai.

Sprawdza, co trafia do modelu (treść, instrukcja systemowa, JSON) i jak
odpowiedzi modelu są czytane i odrzucane (ETAP 144)."""

import google.genai
import pytest
from google.genai import errors

from dane import gemini


class Odpowiedz:
    def __init__(self, text):
        self.text = text


@pytest.fixture
def model(monkeypatch):
    """Udawany model: `model.odpowiedz` — tekst albo wyjątek; `model.zapytania` — co dostał."""
    class Udawany:
        odpowiedz = ""
        zapytania = []

    class Modele:
        def generate_content(self, **kw):
            Udawany.zapytania.append(kw)
            if isinstance(Udawany.odpowiedz, Exception):
                raise Udawany.odpowiedz
            return Odpowiedz(Udawany.odpowiedz)

    class Klient:
        def __init__(self, api_key):
            assert api_key == "klucz-testowy"
            self.models = Modele()

    monkeypatch.setattr(gemini.Config, "GEMINI_API_KEY", "klucz-testowy")
    monkeypatch.setattr(google.genai, "Client", Klient)
    Udawany.zapytania = []
    return Udawany


def test_brak_klucza(monkeypatch):
    monkeypatch.setattr(gemini.Config, "GEMINI_API_KEY", "")
    for wywolanie in (lambda: gemini.zaproponuj_fiszke("x"), lambda: gemini.zaproponuj_fiszki_ze_strony("x"),
                      lambda: gemini.opisz_wskaznik(["a"]), lambda: gemini.odpowiedz_z_przepisow("p", ["f"]),
                      lambda: gemini.opisz_gmine(["a"]), lambda: gemini.zaproponuj_fiszki_z_przepisu("t", "Art. 1")):
        with pytest.raises(gemini.BladGemini, match="GEMINI_API_KEY"):
            wywolanie()


def test_blad_api_zamieniony_na_czytelny(model):
    model.odpowiedz = errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid", "status": "INVALID_ARGUMENT"}})
    with pytest.raises(gemini.BladGemini, match="Błąd Gemini API: API key not valid"):
        gemini.zaproponuj_fiszke("Plan miejscowy jest aktem prawa miejscowego.")


def test_fiszka_z_fragmentu(model):
    model.odpowiedz = "PYTANIE: Czym jest plan miejscowy?\nODPOWIEDZ: Aktem prawa\nmiejscowego."
    assert gemini.zaproponuj_fiszke("fragment") == {"pytanie": "Czym jest plan miejscowy?", "odpowiedz": "Aktem prawa\nmiejscowego."}
    z = model.zapytania[0]
    assert z["contents"] == "fragment" and z["config"].system_instruction == gemini.PROMPT_SYSTEMOWY
    # wstęp przed etykietami i małe litery etykiet są w porządku
    model.odpowiedz = "Oto fiszka:\npytanie: Kto uchwala plan?\nodpowiedz: Rada gminy."
    assert gemini.zaproponuj_fiszke("f")["odpowiedz"] == "Rada gminy."
    for zla in ("PYTANIE: tylko pytanie", "bez etykiet", "", "PYTANIE:\nODPOWIEDZ: odp"):
        model.odpowiedz = zla
        with pytest.raises(gemini.BladGemini, match="sparsować"):
            gemini.zaproponuj_fiszke("f")


def test_lista_fiszek_ze_strony_i_z_przepisu(model):
    model.odpowiedz = '```json\n[{"pytanie": "P1", "odpowiedz": "O1", "fragment": "F1"}, {"pytanie": "P2", "odpowiedz": ""}, "śmieć"]\n```'
    assert gemini.zaproponuj_fiszki_ze_strony("tekst", liczba=3) == [{"pytanie": "P1", "odpowiedz": "O1", "fragment": "F1"}]
    z = model.zapytania[-1]
    assert "od 1 do 3 fiszek" in z["config"].system_instruction and z["config"].response_mime_type == "application/json"
    model.odpowiedz = '{"fiszki": [{"pytanie": "P", "odpowiedz": "O", "fragment": "F"}]}'
    assert len(gemini.zaproponuj_fiszki_z_przepisu("Art. 15. …", "Art. 15", liczba=2)) == 1
    assert "Art. 15" in model.zapytania[-1]["config"].system_instruction
    model.odpowiedz = '"napis"'
    with pytest.raises(gemini.BladGemini, match="nieoczekiwany format"):
        gemini.zaproponuj_fiszki_ze_strony("t")
    model.odpowiedz = "to nie JSON"
    with pytest.raises(gemini.BladGemini, match="JSON"):
        gemini.zaproponuj_fiszki_z_przepisu("t", "Art. 1")


def test_opisy_bez_obcych_liczb(model):
    fakty = ["Najwyżej: Kraków — 1 234,5 zł", "Najniżej: Wieliczka — 800 zł"]
    model.odpowiedz = "Najwyżej jest Kraków (1 234,5 zł), najniżej Wieliczka (800 zł)."
    assert gemini.opisz_wskaznik(fakty).startswith("Najwyżej")
    assert model.zapytania[-1]["contents"] == "Fakty:\n- Najwyżej: Kraków — 1 234,5 zł\n- Najniżej: Wieliczka — 800 zł"
    assert gemini.opisz_gmine(fakty) and model.zapytania[-1]["config"].system_instruction == gemini.PROMPT_RAPORTU_GMINY
    model.odpowiedz = "Różnica wynosi 434,5 zł."  # policzone przez model — zakazane
    for funkcja in (gemini.opisz_wskaznik, gemini.opisz_gmine):
        with pytest.raises(gemini.BladGemini, match=r"434\.5"):  # liczby porównywane po sprowadzeniu do jednej postaci
            funkcja(fakty)
    model.odpowiedz = "   "
    with pytest.raises(gemini.BladGemini, match="pusty opis"):
        gemini.opisz_gmine(fakty)


def test_odpowiedz_z_przepisow(model):
    model.odpowiedz = '```json\n{"odpowiedz": "Wójt.", "brak_odpowiedzi": false, "cytaty": [{"fragment": 2, "cytat": "Wójt sporządza"}]}\n```'
    d = gemini.odpowiedz_z_przepisow("Kto sporządza plan?", ["Art. 14 …", "Art. 15. Wójt sporządza projekt planu."])
    assert d["cytaty"][0]["fragment"] == 2
    assert model.zapytania[-1]["contents"] == "PYTANIE: Kto sporządza plan?\n\nFRAGMENTY:\n\n[1] Art. 14 …\n\n[2] Art. 15. Wójt sporządza projekt planu."
    model.odpowiedz = "[1, 2]"
    with pytest.raises(gemini.BladGemini, match="nieoczekiwany format"):
        gemini.odpowiedz_z_przepisow("p", ["f"])
    model.odpowiedz = "{zepsuty"
    with pytest.raises(gemini.BladGemini, match="JSON"):
        gemini.odpowiedz_z_przepisow("p", ["f"])
