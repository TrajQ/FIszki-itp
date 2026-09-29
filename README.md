# Warsztat

Lokalna aplikacja (Flask + vanilla JS) z czterema narzędziami do
gospodarki przestrzennej. Działa wyłącznie na `127.0.0.1`.

| Moduł | Co robi |
|---|---|
| **Atlas** | Wskaźniki GUS BDL dla gmin województwa: kartogram, ranking, statystyki, opis przez Gemini (liczby sprawdzane przez kod) |
| **MPZP** | Klik na mapie → działka (ULDK) → przeznaczenie w planie miejscowym (WFS; pilotaż: Poznań) |
| **Fiszki** | Fiszki z zaznaczonych fragmentów PDF, kotwica w źródle, powtórki (Leitner), eksport CSV/Anki |
| **Dostępność** | Gotowe wyniki dostępności pieszej na siatce H3: mapa, klasy czasu, udziały w zasięgu 5/10/15 min |

Uruchomienie na Linux Mint: [docs/URUCHOMIENIE.md](docs/URUCHOMIENIE.md).
Postęp prac: [docs/PROGRESS.md](docs/PROGRESS.md), decyzje:
[DECISIONS.md](DECISIONS.md), zasady pracy: [CLAUDE.md](CLAUDE.md).

Testy: `.venv/bin/python -m pytest -q`
