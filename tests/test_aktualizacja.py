"""Aktualizacja z ZIP-a (ETAP 71): dane i klucze nietknięte, stare pliki usunięte."""

import os
import zipfile

import pytest

import aktualizacja as akt

PRAWDZIWE_ZALEZNOSCI = akt.zaleznosci  # fikstura `projekt` je podmienia


def zrob_zip(sciezka, pliki: dict[str, str]):
    with zipfile.ZipFile(sciezka, "w") as z:
        for nazwa, tresc in pliki.items():
            z.writestr(nazwa, tresc)
    return str(sciezka)


@pytest.fixture
def projekt(tmp_path, monkeypatch):
    katalog = tmp_path / "warsztat"
    (katalog / "instance" / "fiszki").mkdir(parents=True)
    (katalog / "instance" / "fiszki" / "fiszki.db").write_text("MOJE FISZKI")
    (katalog / ".env").write_text("GEMINI_API_KEY=tajny\n")
    (katalog / "app.py").write_text("stara wersja")
    (katalog / "CLAUDE.md").write_text("ETAP: 70 (stary)\n")
    monkeypatch.setattr(akt, "aplikacja_dziala", lambda port: False)
    monkeypatch.setattr(akt, "zaleznosci", lambda katalog: None)
    return katalog


def test_pierwsza_i_druga_aktualizacja(projekt, tmp_path):
    dom = tmp_path / "dom"
    (dom / "Pobrane").mkdir(parents=True)
    zrob_zip(dom / "Pobrane" / "warsztat_etap71_x.zip", {
        "warsztat/app.py": "nowa wersja", "warsztat/CLAUDE.md": "ETAP: 71 (nowy)\n",
        "warsztat/modul/stary.py": "x", "warsztat/uruchom.sh": "#!/bin/sh\n",
    })
    assert akt.main([], katalog=str(projekt), dom=str(dom)) == 0
    assert (projekt / "app.py").read_text() == "nowa wersja" and (projekt / "modul" / "stary.py").exists()
    assert (projekt / "instance" / "fiszki" / "fiszki.db").read_text() == "MOJE FISZKI"
    assert (projekt / ".env").read_text() == "GEMINI_API_KEY=tajny\n"
    assert os.access(projekt / "uruchom.sh", os.X_OK)
    kopie = list((dom / "warsztat_kopie").iterdir())
    assert len(kopie) == 1
    with zipfile.ZipFile(kopie[0]) as z:
        assert {"warsztat/app.py", "warsztat/.env", "warsztat/instance/fiszki/fiszki.db"} <= set(z.namelist())
        assert z.read("warsztat/app.py") == b"stara wersja"  # kopia sprzed podmiany

    # druga wersja nie ma modul/stary.py — plik znika; wskazany ZIP ma pierwszeństwo
    druga = zrob_zip(tmp_path / "druga.zip", {"warsztat/app.py": "wersja 72", "warsztat/uruchom.sh": "#!/bin/sh\n"})
    assert akt.main([druga], katalog=str(projekt), dom=str(dom)) == 0
    assert not (projekt / "modul" / "stary.py").exists() and (projekt / "app.py").read_text() == "wersja 72"
    assert (projekt / "instance" / "fiszki" / "fiszki.db").exists() and (projekt / ".env").exists()


@pytest.mark.parametrize(
    "pliki, komunikat",
    [
        ({"inny/app.py": "x"}, "brak katalogu warsztat"),
        ({"warsztat/README.md": "x"}, "brak app.py"),
        ({"warsztat/app.py": "x", "warsztat/../zlo.py": "x"}, "Podejrzana"),
    ],
)
def test_zly_zip(projekt, tmp_path, pliki, komunikat, capsys):
    sciezka = zrob_zip(tmp_path / "zly.zip", pliki)
    assert akt.main([sciezka], katalog=str(projekt), dom=str(tmp_path)) == 1
    assert komunikat in capsys.readouterr().out
    assert (projekt / "app.py").read_text() == "stara wersja"


def test_chronione_w_zipie_pomijane_i_dzialajaca_aplikacja(projekt, tmp_path, monkeypatch, capsys):
    sciezka = zrob_zip(tmp_path / "a.zip", {"warsztat/app.py": "n", "warsztat/.env": "PODMIENIONY", "warsztat/instance/x.db": "!"})
    assert akt.pliki_w_zipie(sciezka) == ["app.py"]
    monkeypatch.setattr(akt, "aplikacja_dziala", lambda port: True)
    assert akt.main([sciezka], katalog=str(projekt), dom=str(tmp_path)) == 1
    assert "jest uruchomiony" in capsys.readouterr().out and (projekt / "app.py").read_text() == "stara wersja"


def test_brak_zipa_i_zepsuty_zip(projekt, tmp_path, capsys):
    assert akt.main([], katalog=str(projekt), dom=str(tmp_path)) == 1
    assert "Nie znalazłem" in capsys.readouterr().out
    zepsuty = tmp_path / "zepsuty.zip"
    zepsuty.write_bytes(b"PK\x03\x04niepelne")
    assert akt.main([str(zepsuty)], katalog=str(projekt), dom=str(tmp_path)) == 1
    assert "niepełne pobieranie" in capsys.readouterr().out


# ---------- ETAP 144: zależności i port ----------


def _udawany_pip(katalog, kod_wyjscia: int):
    """.venv/bin/pip jako skrypt powłoki — zapisuje argumenty i kończy się podanym kodem."""
    pip = katalog / ".venv" / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.write_text(f'#!/bin/sh\necho "$@" > "{katalog}/pip_argumenty.txt"\nexit {kod_wyjscia}\n')
    pip.chmod(0o755)


def test_zaleznosci_zapisuja_sume_jak_uruchom_sh(tmp_path, capsys):
    import hashlib
    (tmp_path / "requirements.txt").write_text("flask\n")
    PRAWDZIWE_ZALEZNOSCI(str(tmp_path))
    assert "Brak .venv" in capsys.readouterr().out  # bez .venv tylko podpowiedź
    _udawany_pip(tmp_path, 0)
    PRAWDZIWE_ZALEZNOSCI(str(tmp_path))
    assert "-r" in (tmp_path / "pip_argumenty.txt").read_text()
    assert (tmp_path / ".venv" / ".requirements.sha256").read_text().strip() == hashlib.sha256(b"flask\n").hexdigest()


def test_nieudana_instalacja_zaleznosci(projekt, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(akt, "zaleznosci", PRAWDZIWE_ZALEZNOSCI)
    (projekt / "requirements.txt").write_text("flask\n")
    _udawany_pip(projekt, 1)
    sciezka = zrob_zip(tmp_path / "warsztat_etap99.zip", {"warsztat/app.py": "nowa", "warsztat/requirements.txt": "flask\n"})
    assert akt.main([sciezka], katalog=str(projekt), dom=str(tmp_path)) == 1
    assert "instalacja zależności się nie udała" in capsys.readouterr().out
    assert (projekt / "app.py").read_text() == "nowa"  # pliki już podmienione — komunikat mówi, co dalej


def test_port_z_env(tmp_path):
    assert akt.port_z_env(str(tmp_path)) == 5000  # bez .env — domyślny
    (tmp_path / ".env").write_text("GEMINI_API_KEY=x\nPORT=5123\n")
    assert akt.port_z_env(str(tmp_path)) == 5123
