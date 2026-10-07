"""Logowanie w trybie serwerowym — Warsztat w chmurze (ETAP 251).

Lokalnie (bez WARSZTAT_DOMENA w .env) nic się nie zmienia: aplikacja
działa na 127.0.0.1 bez logowania. Na serwerze (WARSZTAT_DOMENA ustawiona)
każda strona wymaga zalogowania jednym hasłem — Warsztat ma jednego
użytkownika. W .env jest tylko skrót hasła (WARSZTAT_HASLO_HASH,
werkzeug: scrypt z solą), nigdy samo hasło; skrót tworzy
narzedzia/ustaw_haslo.py.

Ochrona przed zgadywaniem: po MAKS_PROB nieudanych próbach z jednego
adresu IP logowanie z niego jest zablokowane na BLOKADA_S sekund. Licznik
jest w pamięci procesu (gunicorn działa w jednym procesie z wątkami —
deploy/warsztat.service), więc restart go zeruje — to wystarcza przy
haśle, którego nie da się zgadnąć w kilka prób na kwadrans.
"""

import threading
import time
from datetime import timedelta
from urllib.parse import urlsplit

from flask import jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

MAKS_PROB = 5
BLOKADA_S = 15 * 60
SESJA_DNI = 30
# Bez logowania: sama strona logowania, jej styl i ikona.
WOLNE_ENDPOINTY = {"logowanie", "static", "favicon"}

_proby: dict[str, list[float]] = {}
_zamek = threading.Lock()


def tryb_serwerowy(app) -> bool:
    return bool(app.config.get("WARSZTAT_DOMENA"))


def _adres() -> str:
    return request.remote_addr or "?"


def zablokowany(adres: str, teraz: float | None = None) -> bool:
    teraz = time.time() if teraz is None else teraz
    with _zamek:
        proby = [t for t in _proby.get(adres, []) if teraz - t < BLOKADA_S]
        _proby[adres] = proby
        return len(proby) >= MAKS_PROB


def zapisz_nieudana(adres: str, teraz: float | None = None):
    with _zamek:
        _proby.setdefault(adres, []).append(time.time() if teraz is None else teraz)


def wyczysc_proby():
    with _zamek:
        _proby.clear()


def _bezpieczny_cel(dalej: str | None) -> str:
    """Po zalogowaniu wracamy tylko na adres w tej aplikacji (bez otwartego przekierowania)."""
    if not dalej:
        return url_for("index")
    czesci = urlsplit(dalej)
    if czesci.scheme or czesci.netloc or not dalej.startswith("/") or dalej.startswith("//"):
        return url_for("index")
    return dalej


def wymagaj_logowania():
    """before_request w trybie serwerowym: bez sesji — strona logowania."""
    if request.endpoint in WOLNE_ENDPOINTY or session.get("zalogowany"):
        return None
    # fetch z JavaScriptu, obrazki i pliki: 401 zamiast strony logowania
    if request.method != "GET" or "text/html" not in request.headers.get("Accept", ""):
        return jsonify({"blad": "Sesja wygasła — zaloguj się ponownie."}), 401
    return redirect(url_for("logowanie", dalej=request.full_path.rstrip("?")))


def zarejestruj(app):
    """Trasy /logowanie i /wylogowanie; ochrona wszystkich stron w trybie serwerowym."""
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=SESJA_DNI),
    )
    app.before_request(wymagaj_logowania)

    @app.route("/logowanie", methods=["GET", "POST"])
    def logowanie():
        blad = None
        if request.method == "POST":
            if zablokowany(_adres()):
                blad = f"Za dużo nieudanych prób — spróbuj za {BLOKADA_S // 60} minut."
                return render_template("logowanie.html", blad=blad), 429
            haslo = request.form.get("haslo", "")
            skrot = app.config.get("WARSZTAT_HASLO_HASH", "")
            if skrot and haslo and check_password_hash(skrot, haslo):
                session.clear()
                session.permanent = True
                session["zalogowany"] = True
                return redirect(_bezpieczny_cel(request.args.get("dalej")))
            zapisz_nieudana(_adres())
            blad = "Złe hasło."
            return render_template("logowanie.html", blad=blad), 401
        return render_template("logowanie.html", blad=blad)

    @app.route("/wylogowanie", methods=["POST"])
    def wylogowanie():
        session.clear()
        return redirect(url_for("logowanie"))
