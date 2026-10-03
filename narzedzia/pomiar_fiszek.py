"""Pomiar czasu stron Fiszek na dużej bazie (ETAP 226).

Tworzy w katalogu tymczasowym bazę jak po roku intensywnej nauki
(domyślnie 40 PDF-ów, 20 tys. fiszek w 30 tematach, 300 tys. odpowiedzi
w dzienniku, 3 egzaminy) i mierzy czas odpowiedzi stron (drugie wywołanie
— bez rozgrzewania). Dane są losowe, ale powtarzalne (stałe ziarno).

Narzędzie dla autora, nie część aplikacji; nie dotyka prawdziwej bazy:
    python narzedzia/pomiar_fiszek.py
    python narzedzia/pomiar_fiszek.py --fiszki 5000 --odpowiedzi 50000
"""

import argparse
import os
import random
import sys
import tempfile
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402

STRONY = [
    "/fiszki/",
    "/fiszki/statystyki",
    "/fiszki/powtorka/kolejka",
    "/fiszki/powtorka/kolejka?temat=temat%203",
    "/fiszki/5/fiszki",
    "/",
]


def wypelnij(app, pliki: int, fiszki: int, odpowiedzi: int) -> None:
    random.seed(1)
    dzis = date.today()
    with app.app_context():
        from fiszki.baza import get_db

        db = get_db()
        db.executemany("INSERT INTO pdfy (id, nazwa_pliku, nazwa_oryginalna, data_dodania) VALUES (?, ?, ?, '2026-01-01')",
                       [(i, f"p{i}.pdf", f"Wykład {i}.pdf") for i in range(1, pliki + 1)])
        db.executemany("INSERT INTO fiszki (id, pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, data_utworzenia) "
                       "VALUES (?, ?, 1, 'f', ?, 'O.', '2026-01-01')",
                       [(i, random.randint(1, pliki), f"Pytanie {i}?") for i in range(1, fiszki + 1)])
        db.executemany("INSERT INTO powtorki (fiszka_id, pudelko, nastepna_powtorka, liczba_powtorek) VALUES (?, ?, ?, 3)",
                       [(i, random.randint(1, 5), (dzis + timedelta(days=random.randint(-5, 20))).isoformat()) for i in range(1, fiszki + 1)])
        db.executemany("INSERT INTO tematy_fiszek (fiszka_id, temat) VALUES (?, ?)", [(i, f"temat {i % 30}") for i in range(1, fiszki + 1)])
        db.executemany("INSERT INTO dziennik_powtorek (fiszka_id, data, wynik) VALUES (?, ?, ?)",
                       [(random.randint(1, fiszki), (dzis - timedelta(days=random.randint(0, 365))).isoformat(),
                         random.choice(["umiem", "umiem", "trudne", "nie_umiem"])) for _ in range(odpowiedzi)])
        db.executemany("INSERT INTO egzaminy (nazwa, data, temat, pdf_id) VALUES (?, ?, ?, ?)",
                       [("Kolokwium", (dzis + timedelta(days=14)).isoformat(), "temat 3", None),
                        ("Egzamin z pliku", (dzis + timedelta(days=30)).isoformat(), None, min(5, pliki)),
                        ("Sesja", (dzis + timedelta(days=40)).isoformat(), None, None)])
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pliki", type=int, default=40)
    parser.add_argument("--fiszki", type=int, default=20_000)
    parser.add_argument("--odpowiedzi", type=int, default=300_000)
    a = parser.parse_args()
    app = create_app(instance_path=tempfile.mkdtemp())
    print(f"Baza: {a.pliki} PDF, {a.fiszki} fiszek, {a.odpowiedzi} odpowiedzi w dzienniku…")
    wypelnij(app, a.pliki, a.fiszki, a.odpowiedzi)
    klient = app.test_client()
    for strona in STRONY:
        klient.get(strona)  # pierwsze wywołanie — m.in. zapamiętanie krzywej zapominania
        start = time.perf_counter()
        odp = klient.get(strona)
        print(f"{(time.perf_counter() - start) * 1000:8.0f} ms  {odp.status_code}  {strona}")


if __name__ == "__main__":
    main()
