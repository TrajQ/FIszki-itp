"""Dziennik błędów w pliku (ETAP 127).

Błędy i ostrzeżenia aplikacji (np. wyjątek przy liczeniu podsumowania
modułu, nieobsłużony błąd strony) trafiają do instance/logi/warsztat.log
— zostają po zamknięciu okna terminala. Plik ma najwyżej 1 MB; starsze
wpisy przechodzą do warsztat.log.1 … .3 (RotatingFileHandler), więc
dziennik nie rośnie bez końca. Podgląd ostatnich wpisów: /diagnostyka.

Dziennik nie trafia do kopii zapasowej (kopia.py) — to nie są dane
użytkownika.
"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler

FOLDER = "logi"
PLIK = "warsztat.log"
MAKS_BAJTOW = 1_000_000
KOPII = 3
FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_POCZATEK_WPISU = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ (WARNING|ERROR|CRITICAL) \[([^\]]*)\] (.*)$")


def sciezka(folder_instance: str) -> str:
    return os.path.join(folder_instance, FOLDER, PLIK)


def wlacz(app) -> None:
    """Plik dziennika dla loggera aplikacji. Flask ma jeden logger na nazwę
    modułu, więc kolejne create_app (np. w testach) zastępują poprzedni plik."""
    os.makedirs(os.path.join(app.instance_path, FOLDER), exist_ok=True)
    for h in [h for h in app.logger.handlers if getattr(h, "warsztat", False)]:
        app.logger.removeHandler(h)
        h.close()
    plik = RotatingFileHandler(sciezka(app.instance_path), maxBytes=MAKS_BAJTOW, backupCount=KOPII, encoding="utf-8", delay=True)
    plik.warsztat = True
    plik.setLevel(logging.WARNING)
    plik.setFormatter(logging.Formatter(FORMAT))
    app.logger.addHandler(plik)
    if app.logger.level == logging.NOTSET or app.logger.level > logging.WARNING:
        app.logger.setLevel(logging.WARNING)


def ostatnie(folder_instance: str, ile: int = 30) -> list[dict]:
    """Najnowsze wpisy (od najnowszego): czas, poziom, źródło, treść, szczegóły (traceback)."""
    wpisy: list[dict] = []
    for nr in range(KOPII, -1, -1):  # od najstarszego pliku do bieżącego
        p = sciezka(folder_instance) + (f".{nr}" if nr else "")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as plik:
            for wiersz in plik:
                m = _POCZATEK_WPISU.match(wiersz.rstrip("\n"))
                if m:
                    wpisy.append({"czas": m.group(1), "poziom": m.group(2), "zrodlo": m.group(3), "tresc": m.group(4), "szczegoly": ""})
                elif wpisy:
                    wpisy[-1]["szczegoly"] += wiersz
    for w in wpisy:
        w["szczegoly"] = w["szczegoly"].strip()[-4000:]
    return wpisy[::-1][:ile]


def wyczysc(folder_instance: str) -> None:
    for nr in range(KOPII + 1):
        p = sciezka(folder_instance) + (f".{nr}" if nr else "")
        if os.path.exists(p):
            open(p, "w").close() if nr == 0 else os.remove(p)
