"""Tryb serwerowy: logowanie jednym hasłem, domena, HTTPS za Caddy (ETAP 251)."""

import pytest
from werkzeug.security import generate_password_hash

import logowanie
from app import create_app
from config import Config

DOMENA = "warsztat-test.duckdns.org"
HASLO = "bardzo-dlugie-haslo-123"


@pytest.fixture
def serwer(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "WARSZTAT_DOMENA", DOMENA)
    monkeypatch.setattr(Config, "WARSZTAT_HASLO_HASH", generate_password_hash(HASLO))
    monkeypatch.setattr(Config, "SECRET_KEY", "x" * 40)
    logowanie.wyczysc_proby()
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    # jak za Caddy: oryginalny Host i protokół https
    with app.test_client() as c:
        c.environ_base.update({"HTTP_HOST": DOMENA, "HTTP_X_FORWARDED_PROTO": "https", "wsgi.url_scheme": "https"})
        yield c


def test_bez_logowania_przekierowanie_i_401(serwer):
    odp = serwer.get("/fiszki/", headers={"Accept": "text/html"})
    assert odp.status_code == 302 and "/logowanie?dalej=/fiszki/" in odp.headers["Location"]
    assert serwer.get("/fiszki/powtorka/kolejka", headers={"Accept": "*/*"}).status_code == 401
    assert serwer.post("/samouczek/przyklady").status_code == 401
    assert serwer.get("/logowanie").status_code == 200
    css = serwer.get("/static/style.css")
    assert css.status_code == 200
    css.close()


def test_logowanie_haslem_i_wylogowanie(serwer):
    assert serwer.post("/logowanie", data={"haslo": "zle"}).status_code == 401
    odp = serwer.post("/logowanie?dalej=/teren/", data={"haslo": HASLO})
    assert odp.status_code == 302 and odp.headers["Location"].endswith("/teren/")
    ciasteczko = odp.headers["Set-Cookie"]
    assert "Secure" in ciasteczko and "HttpOnly" in ciasteczko and "SameSite=Lax" in ciasteczko
    strona = serwer.get("/", headers={"Accept": "text/html"}).get_data(as_text=True)
    assert "Wyloguj" in strona
    serwer.post("/wylogowanie")
    assert serwer.get("/", headers={"Accept": "text/html"}).status_code == 302


def test_przekierowanie_tylko_w_aplikacji(serwer):
    for zly in ("https://zla.strona/", "//zla.strona/x", "javascript:alert(1)"):
        logowanie.wyczysc_proby()
        odp = serwer.post("/logowanie", query_string={"dalej": zly}, data={"haslo": HASLO})
        assert odp.headers["Location"].endswith("/"), zly
        serwer.post("/wylogowanie")


def test_blokada_po_nieudanych_probach(serwer):
    for _ in range(logowanie.MAKS_PROB):
        assert serwer.post("/logowanie", data={"haslo": "zle"}).status_code == 401
    assert serwer.post("/logowanie", data={"haslo": HASLO}).status_code == 429  # nawet dobre hasło czeka
    assert logowanie.zablokowany("127.0.0.1")
    assert not logowanie.zablokowany("127.0.0.1", teraz=__import__("time").time() + logowanie.BLOKADA_S + 1)


def test_obcy_host_i_obce_origin(serwer):
    assert serwer.get("/logowanie", headers={"Host": "inna.domena.pl"}).status_code == 403
    assert serwer.post("/logowanie", data={"haslo": HASLO}, headers={"Origin": "https://zla.strona"}).status_code == 403


def test_tryb_serwerowy_wymaga_klucza_i_hasla(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "WARSZTAT_DOMENA", DOMENA)
    monkeypatch.setattr(Config, "WARSZTAT_HASLO_HASH", generate_password_hash(HASLO))
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(instance_path=str(tmp_path))
    monkeypatch.setattr(Config, "SECRET_KEY", "y" * 40)
    monkeypatch.setattr(Config, "WARSZTAT_HASLO_HASH", "")
    with pytest.raises(RuntimeError, match="hasło"):
        create_app(instance_path=str(tmp_path))


def test_lokalnie_bez_zmian(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    with app.test_client() as c:
        assert c.get("/fiszki/").status_code == 200 and "Wyloguj" not in c.get("/").get_data(as_text=True)
        assert c.get("/logowanie").status_code == 404


def test_ustaw_haslo_w_env():
    import importlib.util, os
    spec = importlib.util.spec_from_file_location("ustaw_haslo", os.path.join(os.path.dirname(__file__), "..", "narzedzia", "ustaw_haslo.py"))
    modul = importlib.util.module_from_spec(spec); spec.loader.exec_module(modul)
    assert modul.ustaw("A=1\nWARSZTAT_HASLO_HASH=stary\n", "WARSZTAT_HASLO_HASH", "scrypt:x$y$z") == "A=1\nWARSZTAT_HASLO_HASH=scrypt:x$y$z\n"
    assert modul.ustaw("A=1", "SECRET_KEY", "abc") == "A=1\nSECRET_KEY=abc\n"


def test_za_tailscale_host_lokalny_origin_domeny(tmp_path, monkeypatch):
    """ETAP 252: Tailscale Serve może podać Host 127.0.0.1:8002, a przeglądarka Origin z *.ts.net:8443."""
    monkeypatch.setattr(Config, "WARSZTAT_DOMENA", "serwer.tail1234.ts.net")
    monkeypatch.setattr(Config, "WARSZTAT_HASLO_HASH", generate_password_hash(HASLO))
    monkeypatch.setattr(Config, "SECRET_KEY", "z" * 40)
    logowanie.wyczysc_proby()
    app = create_app(instance_path=str(tmp_path))
    with app.test_client() as c:
        c.environ_base.update({"HTTP_HOST": "127.0.0.1:8002"})
        odp = c.post("/logowanie", data={"haslo": HASLO}, headers={"Origin": "https://serwer.tail1234.ts.net:8443"})
        assert odp.status_code == 302
        assert c.post("/logowanie", data={"haslo": HASLO}, headers={"Origin": "https://zla.strona"}).status_code == 403
