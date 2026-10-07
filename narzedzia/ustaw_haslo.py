"""Ustawia hasło logowania Warsztatu na serwerze (ETAP 251).

    .venv/bin/python narzedzia/ustaw_haslo.py

Pyta o hasło dwa razy (nie widać go na ekranie), zapisuje w .env tylko
jego skrót (WARSZTAT_HASLO_HASH), a gdy w .env nie ma losowego
SECRET_KEY — dopisuje go. Po zmianie: sudo systemctl restart warsztat.
"""

import getpass
import os
import re
import secrets
import sys

from werkzeug.security import generate_password_hash

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLIK_ENV = os.path.join(KATALOG, ".env")
MIN_DLUGOSC = 12


def ustaw(tekst_env: str, klucz: str, wartosc: str) -> str:
    """Podmienia (albo dopisuje) linię KLUCZ=… w treści pliku .env."""
    linia = f"{klucz}={wartosc}"
    if re.search(rf"^{klucz}=.*$", tekst_env, flags=re.M):
        return re.sub(rf"^{klucz}=.*$", lambda _: linia, tekst_env, flags=re.M)
    return tekst_env.rstrip("\n") + "\n" + linia + "\n"


def main():
    haslo = getpass.getpass("Nowe hasło do Warsztatu: ")
    if len(haslo) < MIN_DLUGOSC:
        sys.exit(f"Hasło musi mieć co najmniej {MIN_DLUGOSC} znaków.")
    if getpass.getpass("Powtórz hasło: ") != haslo:
        sys.exit("Hasła się różnią — nic nie zmieniono.")
    tekst = open(PLIK_ENV, encoding="utf-8").read() if os.path.exists(PLIK_ENV) else ""
    tekst = ustaw(tekst, "WARSZTAT_HASLO_HASH", generate_password_hash(haslo))
    obecny = re.search(r"^SECRET_KEY=(.*)$", tekst, flags=re.M)
    if not obecny or len(obecny.group(1).strip()) < 32 or "zmien" in obecny.group(1):
        tekst = ustaw(tekst, "SECRET_KEY", secrets.token_urlsafe(48))
    with open(PLIK_ENV, "w", encoding="utf-8") as plik:
        plik.write(tekst)
    os.chmod(PLIK_ENV, 0o600)
    print("Zapisano skrót hasła w .env. Uruchom ponownie: sudo systemctl restart warsztat")


if __name__ == "__main__":
    main()
