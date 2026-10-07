"""Ochrona lokalnej aplikacji przed innymi stronami otwartymi w przeglądarce.

Aplikacja słucha tylko na 127.0.0.1, ale przeglądarka użytkownika łączy
się z nią także wtedy, gdy każe jej to OBCA strona:

1. Formularz POST z obcej strony (CSRF) — np. ukryty formularz na
   dowolnej stronie mógłby wysłać POST /fiszki/1/usun. Dlatego zapytania
   zmieniające stan (POST/PUT/DELETE/PATCH) z obcym nagłówkiem Origin
   (albo Referer, gdy Origin brak) są odrzucane.
2. DNS rebinding — obca domena, która nagle wskazuje na 127.0.0.1, dla
   przeglądarki jest „tą samą stroną” i mogłaby czytać nasze dane.
   Dlatego przyjmujemy tylko nagłówek Host równy 127.0.0.1 albo localhost.
3. Osadzenie aplikacji w niewidocznej ramce i podsunięcie kliknięcia
   (clickjacking) — blokuje nagłówek X-Frame-Options.

Zapytania bez Origin i Referer (curl, testy) przepuszczamy: nie wysyła
ich przeglądarka na polecenie obcej strony.
"""

from urllib.parse import urlsplit

from flask import abort, current_app, jsonify, request

DOZWOLONE_HOSTY = {"127.0.0.1", "localhost"}
METODY_ZMIENIAJACE_STAN = {"POST", "PUT", "DELETE", "PATCH"}


def _nazwa_hosta(host_z_portem: str) -> str:
    # „127.0.0.1:5000” → „127.0.0.1”; urlsplit radzi sobie też z [::1]:5000
    return (urlsplit(f"//{host_z_portem}").hostname or "").lower()


def sprawdz_zapytanie():
    """before_request: odrzuca zapytania, które nie mogą pochodzić od nas."""
    # ETAP 251: na serwerze także domena z WARSZTAT_DOMENA (Caddy przekazuje oryginalny Host)
    dozwolone = DOZWOLONE_HOSTY | ({current_app.config["WARSZTAT_DOMENA"]} if current_app.config.get("WARSZTAT_DOMENA") else set())
    if _nazwa_hosta(request.host) not in dozwolone:
        abort(403, "Nieznany nagłówek Host — aplikacja działa tylko pod 127.0.0.1.")

    if request.method not in METODY_ZMIENIAJACE_STAN:
        return

    zrodlo = request.headers.get("Origin") or request.headers.get("Referer")
    if zrodlo is None:
        return
    # Origin „null” wysyłają m.in. ramki sandbox i przekierowania — też obce.
    if zrodlo == "null" or urlsplit(zrodlo).netloc.lower() != request.host.lower():
        abort(403, "Zapytanie z obcej strony zostało zablokowane.")


def dodaj_naglowki(odpowiedz):
    """after_request: nagłówki bezpieczeństwa dla każdej odpowiedzi."""
    odpowiedz.headers.setdefault("X-Frame-Options", "DENY")
    odpowiedz.headers.setdefault("X-Content-Type-Options", "nosniff")
    odpowiedz.headers.setdefault("Referrer-Policy", "same-origin")
    # ETAP 229: CSP bez blokowania skryptów w szablonach (są w nich bloki
    # <script>) — za to: fetch tylko do aplikacji (dane nie wyjdą do obcej
    # domeny), formularze tylko do aplikacji, bez wtyczek, bez <base>, bez ramek.
    odpowiedz.headers.setdefault(
        "Content-Security-Policy",
        "connect-src 'self'; form-action 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    )
    return odpowiedz


def za_duzy_plik(blad):
    """ETAP 229: plik ponad MAX_CONTENT_LENGTH — po polsku, JSON dla fetch."""
    komunikat = ("Plik jest za duży (limit 50 MB). Kopię zapasową większą niż limit "
                 "przywróć z listy kopii w folderze kopii, nie przez wgrywanie.")
    if "text/html" in request.headers.get("Accept", ""):
        return f"<!doctype html><meta charset=utf-8><title>Za duży plik</title><p>{komunikat}</p><p><a href=\"/\">Strona główna</a></p>", 413
    return jsonify({"blad": komunikat}), 413
