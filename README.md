# Warsztat

Lokalna aplikacja (Flask + vanilla JS) z siedmioma narzędziami do
gospodarki przestrzennej. Działa wyłącznie na `127.0.0.1`.

| Moduł | Co robi |
|---|---|
| **Atlas** | Wskaźniki GUS BDL dla gmin województwa: kartogram, ranking, porównanie lat, profil gminy z wykresem w czasie, korelacja dwóch wskaźników (Pearson, Spearman), miary zróżnicowania (σ, współczynnik zmienności, Gini) i histogram, metody klasyfikacji (kwantyle, Jenks, równe przedziały, odchylenie) z GVF, autokorelacja przestrzenna (I Morana, klastry LISA), mapa do druku (SVG/PDF z legendą, podziałką, strzałką północy i źródłem), na tle kraju (ranking 16 województw), wskaźniki względne („na 1000 mieszkańców”), raport gminy (własny zestaw wskaźników: wartość, zmiana w 10 lat, miejsce w województwie, mediana, trend, charakterystyka Gemini, druk), opis Gemini ze sprawdzaniem liczb, eksport CSV/GeoJSON |
| **MPZP** | Działka (klik, obręb + numer z podpowiedziami) → przeznaczenie w planie, podział działki na przeznaczenia (m², %), raport do druku/PDF, kalkulator wskaźników zabudowy ze zgodnością z planem, kalkulator skali mapy (rysunek ↔ teren, dobór skali do arkusza), historia, GeoJSON, „Moje działki” z notatkami (CSV) i porównaniem działek obok siebie (szkice w jednej skali), słownik symboli planu z rozszyfrowywaniem, wymiary działki (boki na mapie, szerokość × głębokość, zwartość), obszar analizowany do decyzji WZ, współrzędne punktu w PL-1992/PL-2000, pomiar odległości i powierzchni na mapie, link do Geoportalu, kronika zmian (ortofotomapy archiwalne na suwaku lat albo dwa lata obok siebie, z granicą działki). Cała Polska przez krajową integrację planów GUGiK (KIMPZP) + nakładki planów i działek na mapie; dla Poznania dodatkowo podział działki z WFS gminy |
| **Fiszki** | Fiszki z zaznaczenia albo z całej strony PDF (Gemini, cytat sprawdzany w tekście), kotwica w źródle, powtórki Leitnera (umiem / trudne / nie umiem, tryb wpisywania odpowiedzi, tryb „przed egzaminem”), prognoza powtórek na 7 dni, tematy fiszek (powtórka, quiz i druk z jednego tematu), egzaminy z postępem i planem dziennym, powtórka odwrócona, quiz ABCD, statystyki nauki, najtrudniejsze fiszki, wyszukiwarka, karty do druku, eksport i import CSV/Anki/Quizlet |
| **Osiedle** | Koncepcja osiedla rysowana na mapie (Leaflet.draw): obszar opracowania i tereny o funkcjach MN, MW, U, ZP, KD, KS, WS, bilans terenu na bieżąco (m², %, pasek), kontrola nakładania się i terenów poza obszarem, wskaźniki zabudowy z parametrów terenów (zabudowa %, kondygnacje, PBC) — powierzchnia zabudowy i całkowita, intensywność, PBC — ze zgodnością z wpisanymi ustaleniami planu, program osiedla (mieszkania, mieszkańcy, gęstość, miejsca postojowe, przedszkola i szkoły, zieleń na mieszkańca) z jawnymi założeniami, raport do druku/PDF ze szkicem, porównanie wariantów obok siebie (szkice w jednej skali), eksport GeoJSON i SVG |
| **Przepisy** | Ustawy i rozporządzenia z PDF (np. z ISAP) podzielone na artykuły i paragrafy, strona aktu ze spisem i odnośnikiem do strony PDF, wyszukiwarka pełnotekstowa odporna na brak polskich znaków i odmianę, frazy dokładne, skok do „art. 15” / „§ 4”, pytania do Gemini z odpowiedzią opartą wyłącznie na dosłownych cytatach sprawdzanych w tekście (z artykułem i stroną PDF), historia pytań |
| **Teren** | Inwentaryzacja w terenie: projekt z polami formularza (wzory: zieleń, stan zabudowy, przestrzeń publiczna), samodzielny formularz HTML na telefon działający bez internetu (GPS, zdjęcie, uwagi), import pliku z telefonu bez dublowania, mapa punktów z kolorem wg pola, tabela, eksport GeoJSON/CSV |
| **Dostępność** | Wyniki na siatce H3: klasy czasu dojścia, miasto 15-minutowe (wszystkie usługi naraz, najsłabsze ogniwo), udziały w mieszkańcach, porównanie scenariuszy przed/po, raport do druku (mapa A4 SVG/PDF + tabele), szybki model z punktów usług wstawionych na mapie albo wczytanych z CSV (nowy plik, obszary obsługi z mieszkańcami na placówkę), krzywa dostępności z własnym progiem, luki w dostępności, szczegóły komórki, eksport GeoJSON |

Każda mapa ma eksport **GeoJSON do QGIS**. Kopia zapasowa wszystkich
danych jednym kliknięciem na stronie głównej. Liczby zawsze liczy kod —
model językowy tylko opisuje i proponuje treść do zatwierdzenia.

Uruchomienie na Linux Mint: [docs/URUCHOMIENIE.md](docs/URUCHOMIENIE.md).
Postęp prac: [docs/PROGRESS.md](docs/PROGRESS.md), decyzje:
[DECISIONS.md](DECISIONS.md), zasady pracy: [CLAUDE.md](CLAUDE.md).

Testy: `.venv/bin/python -m pytest -q`

## Gdzie co jest w kodzie

Każdy moduł to osobny katalog z blueprintem Flaska. Plik `routes.py`
tworzy blueprint i ma główne trasy; większe grupy tras są w plikach
`trasy_*.py`, które rejestrują się na tym samym blueprincie. Obliczenia
są w osobnych plikach bez Flaska — łatwo je czytać i testować.

| Moduł | Trasy | Obliczenia i dane |
|---|---|---|
| `atlas/` | `routes.py` (dane, klasy, autokorelacja, profil, korelacja, eksport), `trasy_druk.py` (mapa do druku), `trasy_raport.py` (raport gminy) | `statystyki.py`, `autokorelacja.py`, `raport.py`, `granice.py` (PRG), `mapa_svg.py`, `baza.py` (cache) |
| `mpzp/` | `routes.py` (działka, plan, raport, porównanie), `trasy_narzedzia.py` (kalkulatory, pomiar, obszar WZ, symbole), `trasy_zapisane.py` (Moje działki), `trasy_kronika.py` (kronika zmian) | `wfs.py` (Poznań), `krajowe.py` (KIMPZP), `geometria.py`, `uklady.py`, `zabudowa.py`, `skala.py`, `symbole.py`, `liczby.py`, `baza.py` |
| `fiszki/` | `routes.py` (pliki PDF, fiszki, szkice Gemini), `trasy_nauka.py` (powtórki, quiz, egzaminy), `trasy_wymiana.py` (druk, eksport, import, wyszukiwarka) | `powtorki.py`, `tematy.py`, `egzaminy.py`, `quiz.py`, `importer.py`, `statystyki_nauki.py`, `strona.py`, `baza.py` |
| `osiedle/` | `routes.py` (koncepcje), `trasy_druk.py` (raport, szkic SVG, porównanie) | `bilans.py` (bilans terenu), `wskazniki.py` (wskaźniki zabudowy, zgodność z planem), `program.py` (mieszkańcy, parkingi, szkoły), `rysunek_svg.py` (szkic), `baza.py` (koncepcje) |
| `przepisy/` | `routes.py` | `tekst.py` (PDF → artykuły), `baza.py` (akty, wyszukiwarka FTS5, historia pytań), `pytania.py` (sprawdzanie cytatów i liczb) |
| `teren/` | `routes.py` | `projekt.py` (pola, sprawdzanie pliku z telefonu), `baza.py` (projekty, punkty, zdjęcia), szablon `telefon.html` (formularz na telefon) |
| `dostepnosc/` | `routes.py` | `wyniki.py` (CSV H3), `model.py` (szybki model), `druk.py` (raport) |

Wspólne dla aplikacji: `app.py`, `ochrona.py` (tylko 127.0.0.1, ochrona
przed obcymi stronami), `kopia.py` (kopia zapasowa), `dane/` (klienci
usług: GUS BDL, ULDK, Gemini, ortofotomapy archiwalne).
