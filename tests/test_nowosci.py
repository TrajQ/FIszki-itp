"""„Co nowego” po aktualizacji (ETAP 159)."""

import nowosci
from app import create_app

CHANGELOG = """# Changelog

## ETAP 1 — 2026-09-24
- Dodano szkielet aplikacji
  w kilku liniach.
- Dodano testy.

## ETAP 3 — 2026-09-26
- Fiszki z luką

## ETAP 2 — 2026-09-25
- Atlas: kartogram
"""


def test_wpisy_i_nowe(tmp_path):
    plik = tmp_path / "CHANGELOG.md"
    plik.write_text(CHANGELOG, encoding="utf-8")
    w = nowosci.wpisy(str(plik))
    assert [x["etap"] for x in w] == [3, 2, 1]  # od najnowszego, także gdy w pliku nie po kolei
    assert w[2]["punkty"] == ["Dodano szkielet aplikacji w kilku liniach.", "Dodano testy."]
    instancja = str(tmp_path / "instance")
    assert nowosci.nowe(instancja, str(plik)) == []  # pierwsze uruchomienie — bez paska
    assert nowosci.widziany(instancja) == 3
    nowosci.zapisz_widziany(instancja, 1)  # „aktualizacja” z ETAPu 1
    assert [x["etap"] for x in nowosci.nowe(instancja, str(plik))] == [3, 2]
    assert nowosci.wpisy(str(tmp_path / "nie_ma.md")) == []


def test_pasek_i_strona(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        assert "Zobacz, co nowego" not in c.get("/").get_data(as_text=True)  # nowa instalacja
        ostatni = nowosci.wpisy()[0]["etap"]
        nowosci.zapisz_widziany(str(tmp_path), ostatni - 2)  # jak po aktualizacji o dwa ETAPy
        glowna = c.get("/").get_data(as_text=True)
        assert "Warsztat zaktualizowany — 2 nowe ETAPy" in glowna and "Zobacz, co nowego" in glowna
        strona = c.get("/co-nowego").get_data(as_text=True)
        assert f"ETAP {ostatni}" in strona and strona.count(">nowe</span>") == 2
        assert "Zobacz, co nowego" not in c.get("/").get_data(as_text=True)  # obejrzane — pasek znika
