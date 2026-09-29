# Postęp prac

## ETAP 1 — Szkielet aplikacji
Data: 2026-09-24
Status: zamknięty

Zrobione:
- Aplikacja Flask (app factory w `app.py`), bindowana na 127.0.0.1
- 4 blueprinty-placeholdery: atlas, mpzp, fiszki, dostepnosc
- Strona startowa z linkami do modułów
- Konfiguracja przez `.env` / `.env.example`
- Testy smoke (pytest)
- `DECISIONS.md` z D-001

Testy: 5 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap1_20260924.zip

## ETAP 2 — Moduł fiszki (upload PDF, tworzenie fiszek z kotwicą)
Data: 2026-09-24
Status: zamknięty

Zrobione:
- Baza sqlite3 modułu (`fiszki/baza.py`): tabele `pdfy` i `fiszki`,
  `instance/fiszki/fiszki.db`, pliki PDF w `instance/fiszki/pliki/`
- Warstwa Gemini (`dane/gemini.py`): `zaproponuj_fiszke(fragment_tekstu)`,
  pracuje wyłącznie na dostarczonym fragmencie, błędy jako `BladGemini`
- Endpointy `fiszki/routes.py`: lista PDF-ów + upload (walidacja
  rozszerzenia i nagłówka `%PDF-`), widok PDF-a, serwowanie pliku, JSON
  listy fiszek, szkic fiszki przez Gemini, zapis fiszki, usuwanie fiszki
- Widok PDF-a (`pdf.html` + `fiszki.js`): renderowanie stron przez
  wektorowany lokalnie `pdf.js` (warstwa tekstowa do zaznaczania myszką),
  przycisk "Zaproponuj fiszkę", panel tworzenia/edycji fiszki, lista fiszek
  z "pokaż w źródle" (podświetlenie fragmentu na właściwej stronie) i "usuń"
- Testy (mockowany Gemini, bez realnych wywołań API): upload poprawnego i
  niepoprawnego PDF-a, szkic fiszki (sukces i błąd Gemini → czytelny JSON,
  nie 500), zapis i usuwanie fiszki
- `DECISIONS.md`: D-002 (google-genai), D-003 (pdf.js lokalnie),
  D-004 (surowy sqlite3, bez ORM)

Poza zakresem (świadomie odłożone): system powtórek (spaced repetition),
edycja treści fiszki po zapisaniu, eksport (Anki/CSV).

Testy: 11 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap2_20260924.zip

## ETAP 3 — Moduł mpzp (działka → przeznaczenie, gmina pilotażowa Poznań)
Data: 2026-09-25
Status: zamknięty

Zrobione:
- Klient ULDK (`dane/uldk.py`): `znajdz_dzialke(lat, lon)`, parsuje
  odpowiedź tekstową ULDK (sukces/brak wyników/błąd), zwraca geometrię
  jako obiekt shapely, błędy jako `BladULDK`
- Rejestr gmin (`mpzp/gminy.py`): jedna pozycja — Poznań (WFS
  `gis.mpu.pl`, warstwa `WydzieleniePlanistyczne.MPZP`, atrybut
  przeznaczenia `symb_t`)
- Klient WFS (`mpzp/wfs.py`): pobiera całą warstwę gminy raz (WFS
  Poznania nie honoruje filtrów przestrzennych — zwracały 0 wyników w
  rozpoznaniu), parsuje GML (obsługa dziur i wielokątów złożonych z kilku
  części), indeksuje `shapely.STRtree`, point-in-polygon przez `covers()`
  (żeby kliknięcie dokładnie na granicy też trafiało), błędy jako
  `BladWFS`
- Endpointy `mpzp/routes.py`: `GET /mpzp/sprawdz?lat=..&lon=..` (działka +
  przeznaczenie albo czytelny komunikat błędu), `POST /mpzp/odswiez`
  (wymuszenie ponownego pobrania warstwy WFS)
- Frontend (`mpzp.js` + `index.html` + `mpzp.css`): mapa Leaflet
  wektorowana lokalnie, klik na mapie, rysowanie działki i wydzielenia,
  panel wyniku z surowymi atrybutami WFS, przycisk odświeżenia danych
  gminy
- Testy (mockowane ULDK i WFS, zero realnych wywołań sieciowych):
  parsowanie odpowiedzi ULDK (sukces/brak/błąd), parsowanie GML z WFS
  (proste wydzielenia, dziura w wydzieleniu, wielokąt złożony z kilku
  części, stronicowanie, pusta warstwa, błędy sieci/XML), wszystkie
  ścieżki endpointu `/mpzp/sprawdz` (brak współrzędnych, brak działki,
  inna gmina, brak planu, sukces, błędy ULDK/WFS jako 502) i
  `/mpzp/odswiez`
- `DECISIONS.md`: D-005 (`requests`, `shapely`), D-006 (Leaflet lokalnie)

Poza zakresem (świadomie odłożone): obsługa więcej niż jednej gminy,
słownik symboli MPZP (tłumaczenie `ZP`/`MN`/itd.), użycie Gemini w mpzp,
historia sprawdzonych działek, wybór działki po numerze ewidencyjnym,
naprawa filtra przestrzennego WFS (obejście: pobranie całej warstwy).

Testy: 38 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap3_20260925.zip

Następny krok (po ETAPie 3): wybrano dokończenie modułu fiszki.

## ETAP 4 — Fiszki: edycja i eksport (CSV, Anki)
Data: 2026-09-29
Status: zamknięty

Zrobione:
- Endpoint `PUT /fiszki/<pdf_id>/fiszki/<id>`: edycja pytania i
  odpowiedzi. Strona i fragment (kotwica w źródle) celowo nieedytowalne.
  Puste pola → 400, fiszka nieistniejąca albo z innego PDF-a → 404
- Eksport `GET /fiszki/<pdf_id>/eksport.csv` (UTF-8 z BOM, nagłówek,
  kolumny: strona, pytanie, odpowiedz, fragment_tekstu, data_utworzenia)
- Eksport `GET /fiszki/<pdf_id>/eksport.txt` dla Anki (Plik → Importuj):
  rozdzielany tabulatorami, nagłówki `#separator:tab` i `#html:true`,
  kolumny: pytanie, odpowiedź, źródło („plik.pdf, s. N”), znaki HTML
  escapowane, nowe linie jako `<br>`
- Frontend: przycisk „edytuj” przy każdej fiszce (edycja w miejscu),
  linki eksportu nad listą fiszek
- Poprawka błędu z ETAPu 2: `pdfjsLib.getDocument(URL_PLIK)` →
  `getDocument({ url: URL_PLIK })` — pdf.js 6.x nie przyjmuje już samego
  stringa, więc PDF w ogóle się nie wczytywał
- Testy: edycja (sukces, puste pola, 404 dla cudzej/nieistniejącej
  fiszki), eksport CSV, eksport Anki (escapowanie HTML, tabulatorów,
  nowych linii), eksport dla nieistniejącego PDF-a
- `DECISIONS.md`: D-007 (eksport do Anki jako TSV, bez genanki)
- Poprawka po zgłoszeniu (PDF nie wyświetlał się na Linux Mint):
  najpierw polyfill `Map.getOrInsertComputed` (D-008) — nie wystarczył,
  bo nowoczesny build pdf.js 6.3 wymaga wielu świeżych API. Ostatecznie
  podmiana na build legacy tej samej wersji (D-009), polyfill usunięty.
  Błąd wczytania PDF-a jest teraz widoczny na stronie (`#blad-pdf`).
  Sprawdzone w Chromium z usuniętymi nowymi API
- Skrypt startowy `uruchom.sh` i `zainstaluj_ikone.sh` (ikona na
  pulpicie i w menu), instrukcja `docs/URUCHOMIENIE.md` (D-010)
- `DECISIONS.md`: D-008 (zastąpiona), D-009, D-010

Poza zakresem (świadomie odłożone): system powtórek (planowany ETAP 5),
eksport .apkg, eksport wszystkich PDF-ów naraz.

Testy: 45 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap4_20260929.zip

Następny krok: na prośbę autora — wspólny wygląd aplikacji (ETAP 5),
potem powtórki (ETAP 6), atlas (ETAP 7), dostępność (ETAP 8). Autor
zlecił pracę bez dopytywania o każdy krok.

## ETAP 5 — Wspólny wygląd (styl Apple, grid i flexbox)
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `templates/base.html`: wspólny szkielet stron — półprzezroczysty,
  przyklejony pasek nawigacji z wyróżnionym aktywnym modułem, bloki
  `tytul`, `head`, `tresc`, `skrypty`; wszystkie szablony modułów
  dziedziczą po nim
- `static/style.css` przepisany: tokeny kolorów (zmienne CSS) z trybem
  ciemnym (`prefers-color-scheme`), systemowa czcionka, karty, przyciski
  w kształcie pigułki (główny, drugi, tekstowy, niebezpieczny),
  formularze, tabele, etykiety, komunikaty; siatka kart
  `grid auto-fill`
- Strona główna: nagłówek „hero” + siatka czterech kart modułów z
  ikonami SVG
- Fiszki: lista PDF-ów jako karty z liczbą fiszek (nowe zapytanie z
  `COUNT`), widok PDF-a w układzie grid (PDF + przyklejony panel fiszek),
  fiszki jako karty z akcjami i numerem strony
- MPZP: grid mapa + panel; panel pokazuje identyfikator działki i
  wyróżniony symbol przeznaczenia (nowe pole `przeznaczenie` w JSON
  `/mpzp/sprawdz`), atrybuty w tabeli
- Układ responsywny: poniżej ~1000/900 px kolumny przechodzą jedna pod
  drugą
- Testy: liczba fiszek na liście plików, pole `przeznaczenie` w mpzp
- `DECISIONS.md`: D-011

Testy: 46 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap5_20260929.zip

## ETAP 6 — Fiszki: powtórki (system Leitnera)
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `fiszki/powtorki.py`: 5 pudełek, odstępy 1/2/4/8/16 dni; „umiem” →
  następne pudełko, „nie umiem” → pudełko 1 z powtórką jeszcze dziś;
  `dzisiaj()` jako osobna funkcja (podmieniana w testach)
- Tabela `powtorki` (osobna, z `ON DELETE CASCADE`) — stare bazy działają
  bez migracji; fiszka bez wpisu = nowa, do powtórki od razu
- Endpointy: `GET /fiszki/powtorka` (strona sesji, opcjonalnie
  `?pdf_id=`), `GET /fiszki/powtorka/kolejka` (JSON, najpierw niższe
  pudełka), `POST /fiszki/powtorka/<id>` (`{"wynik": "umiem"|"nie_umiem"}`)
- Sesja powtórki (`powtorka.html`, `powtorka.js`): karta z pytaniem,
  odsłanianie odpowiedzi i fragmentu źródła, skróty klawiszowe
  (spacja / 1 / 2), pasek postępu, „nie umiem” wraca na koniec sesji,
  link do źródła otwiera PDF z podświetlonym fragmentem
  (`/fiszki/<pdf>/?fiszka=<id>`)
- Lista plików: karta „Do powtórki dziś” z wykresem pudełek, licznik
  fiszek do powtórki na karcie każdego PDF-a; w widoku PDF-a przycisk
  „Powtórz fiszki z tego pliku”
- Testy: logika Leitnera, kolejka (nowe, termin, kolejność, filtr PDF),
  zapis oceny, błędy 400/404, kaskadowe usuwanie, strony i liczniki
- `DECISIONS.md`: D-012

Testy: 57 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap6_20260929.zip
