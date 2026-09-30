"""Terminy z kalendarza strony głównej jako plik iCalendar (ETAP 102).

Format wg RFC 5545: wydarzenia całodniowe (DTSTART;VALUE=DATE, DTEND
dzień później), linie zakończone CRLF i łamane po 75 bajtach, znaki
specjalne w tekście (\\ ; , i nowa linia) poprzedzone ukośnikiem. UID
zależy od rodzaju, daty i nazwy, więc ponowny import tego samego pliku
aktualizuje wydarzenia zamiast je dublować.
"""

import hashlib
from datetime import date, datetime, timedelta, timezone


def _tekst(wartosc: str) -> str:
    tekst = str(wartosc).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return tekst.replace("\r\n", "\\n").replace("\n", "\\n")


def _zlam(linia: str) -> list[str]:
    """Linie dłuższe niż 75 bajtów łamiemy; kontynuacja zaczyna się spacją.
    Nie tniemy w środku znaku UTF-8."""
    wynik, biezaca, dlugosc = [], "", 0
    for znak in linia:
        bajty = len(znak.encode("utf-8"))
        if dlugosc + bajty > 75:
            wynik.append(biezaca)
            biezaca, dlugosc = " ", 1
        biezaca += znak
        dlugosc += bajty
    wynik.append(biezaca)
    return wynik


def plik_ics(terminy: list[dict], adres_aplikacji: str, teraz: datetime | None = None) -> str:
    teraz = teraz or datetime.now(timezone.utc)
    znacznik = teraz.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    linie = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Warsztat//Kalendarz terminów//PL", "CALSCALE:GREGORIAN"]
    for t in terminy:
        dzien = date.fromisoformat(t["data"])
        uid = hashlib.sha1(f"{t['rodzaj']}|{t['data']}|{t['nazwa']}".encode("utf-8")).hexdigest()[:20]
        tytul = ("Egzamin: " if t["rodzaj"] == "egzamin" else "Teren: ") + t["nazwa"]
        linie += [
            "BEGIN:VEVENT",
            f"UID:{uid}@warsztat.local",
            f"DTSTAMP:{znacznik}",
            f"DTSTART;VALUE=DATE:{dzien:%Y%m%d}",
            f"DTEND;VALUE=DATE:{dzien + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_tekst(tytul)}",
            f"DESCRIPTION:{_tekst(t['opis'])}",
            f"URL:{adres_aplikacji}{t['url']}",
            "END:VEVENT",
        ]
    linie.append("END:VCALENDAR")
    return "".join(czesc + "\r\n" for linia in linie for czesc in _zlam(linia))
