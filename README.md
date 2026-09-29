# Warsztat

Lokalna aplikacja (Flask + vanilla JS) z czterema narzędziami do
gospodarki przestrzennej. Działa wyłącznie na `127.0.0.1`.

| Moduł | Co robi |
|---|---|
| **Atlas** | Wskaźniki GUS BDL dla gmin województwa: kartogram, ranking, porównanie lat, profil gminy z wykresem w czasie, korelacja dwóch wskaźników (Pearson, Spearman), miary zróżnicowania (σ, współczynnik zmienności, Gini) i histogram, wskaźniki względne („na 1000 mieszkańców”), opis Gemini ze sprawdzaniem liczb, eksport CSV/GeoJSON |
| **MPZP** | Działka (klik, obręb + numer z podpowiedziami) → przeznaczenie w planie, podział działki na przeznaczenia (m², %), raport do druku/PDF, kalkulator wskaźników zabudowy ze zgodnością z planem, kalkulator skali mapy (rysunek ↔ teren, dobór skali do arkusza), historia, GeoJSON, współrzędne punktu w PL-1992/PL-2000, pomiar odległości i powierzchni na mapie, link do Geoportalu. Cała Polska przez krajową integrację planów GUGiK (KIMPZP) + nakładki planów i działek na mapie; dla Poznania dodatkowo podział działki z WFS gminy |
| **Fiszki** | Fiszki z zaznaczenia albo z całej strony PDF (Gemini, cytat sprawdzany w tekście), kotwica w źródle, powtórki Leitnera, quiz ABCD, statystyki nauki, najtrudniejsze fiszki, wyszukiwarka, karty do druku, eksport CSV/Anki |
| **Dostępność** | Wyniki na siatce H3: klasy czasu dojścia, miasto 15-minutowe (wszystkie usługi naraz, najsłabsze ogniwo), udziały w mieszkańcach, porównanie scenariuszy przed/po, eksport GeoJSON |

Każda mapa ma eksport **GeoJSON do QGIS**. Kopia zapasowa wszystkich
danych jednym kliknięciem na stronie głównej. Liczby zawsze liczy kod —
model językowy tylko opisuje i proponuje treść do zatwierdzenia.

Uruchomienie na Linux Mint: [docs/URUCHOMIENIE.md](docs/URUCHOMIENIE.md).
Postęp prac: [docs/PROGRESS.md](docs/PROGRESS.md), decyzje:
[DECISIONS.md](DECISIONS.md), zasady pracy: [CLAUDE.md](CLAUDE.md).

Testy: `.venv/bin/python -m pytest -q`
