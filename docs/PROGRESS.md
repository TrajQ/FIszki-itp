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

## ETAP 7 — Atlas (GUS BDL: kartogram, ranking, opis)
Data: 2026-09-29
Status: zamknięty (bez weryfikacji na żywym API — patrz „Znane ryzyka”)

Zrobione:
- `dane/bdl.py`: klient API BDL v1 — wyszukiwanie zmiennych dostępnych
  dla gmin, lista województw, wartości zmiennej dla gmin województwa
  w danym roku (stronicowanie, pomijanie braków i części gmin
  miejsko-wiejskich), TERYT wyciągany z 12-znakowego id BDL, opcjonalny
  klucz `GUS_BDL_API_KEY` (nagłówek `X-ClientId`), błędy jako `BladBDL`
- `atlas/baza.py`: `instance/atlas/atlas.db` — cache odpowiedzi BDL na
  30 dni (limity zapytań API)
- `atlas/granice.py`: granice gmin z PRG (WFS GUGiK), filtr po TERYT
  województwa, łączenie rekordów jednej gminy, uproszczenie geometrii
  (~50 m), automatyczne rozpoznanie kolejności osi, cache GeoJSON w
  `instance/atlas/granice/`
- `atlas/statystyki.py`: liczba gmin, min, max, mediana, średnia, 3
  najwyższe/najniższe, progi 5 klas kwantylowych, polski zapis liczb,
  lista faktów dla modelu
- `dane/gemini.py`: `opisz_wskaznik(fakty)` + strażnik liczb
  `sprawdz_liczby` — opis z liczbą spoza faktów jest odrzucany
- Endpointy: `/atlas/zmienne`, `/atlas/wojewodztwa`, `/atlas/dane`,
  `/atlas/granice/<teryt>`, `POST /atlas/opis` (fakty liczone na
  serwerze, nie przyjmowane z przeglądarki)
- Frontend: wyszukiwarka wskaźników z podpowiedziami, wybór
  województwa i roku, kartogram Leaflet z legendą i dymkami, kafelki
  statystyk, ranking gmin jako wykres słupkowy (filtr, podświetlanie
  mapa ↔ ranking, klik = przybliżenie), opis z podglądem faktów
  przekazanych modelowi; brak granic nie blokuje rankingu i statystyk
- Leaflet przeniesiony z `mpzp/static/leaflet/` do `static/leaflet/`
  (używają go mpzp, atlas i dostępność)
- Testy: 22 nowe (klient BDL na fałszywych odpowiedziach HTTP, TERYT,
  statystyki, strażnik liczb, parser GML granic + cache, endpointy)
- `DECISIONS.md`: D-013, D-014

Znane ryzyka (nie dało się sprawdzić — sieć środowiska, w którym
powstawał ETAP, blokuje bdl.stat.gov.pl i geoportal.gov.pl):
- nazwy parametrów/pól API BDL i warstwy PRG (`ms:A03_Granice_gmin`,
  `JPT_KOD_JE`, `JPT_NAZWA_`) przyjęte według dokumentacji; przy
  pierwszym uruchomieniu u autora sprawdzić, czy kartogram się rysuje
- format filtra WFS (FES 2.0 `PropertyIsLike`) — jeśli PRG go odrzuci,
  komunikat błędu pojawi się nad mapą

Testy: 79 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap7_20260929.zip

## ETAP 8 — Dostępność (wyniki na siatce H3)
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `dostepnosc/wyniki.py`: wczytywanie CSV z kolumną `h3` i kolumnami
  liczbowymi (separator `,` lub `;`, przecinek dziesiętny, BOM, puste =
  brak wartości), walidacja indeksów H3 i jednej rozdzielczości, limit
  100 000 komórek; kolumny czasu (`*_min`, `czas*`) → stałe klasy
  5/10/15/20/30 min i udziały + powierzchnia w zasięgu 5/10/15 min
  („miasto 15-minutowe”); pozostałe kolumny → klasy kwantylowe;
  geometria heksagonów z biblioteki `h3`
- Endpointy: `/dostepnosc/` (lista plików), `POST /dostepnosc/wgraj`
  (walidacja przed zapisem), `/dostepnosc/plik/<nazwa>` (metadane),
  `/dostepnosc/plik/<nazwa>/<kolumna>` (GeoJSON + klasy + statystyki),
  `POST /dostepnosc/plik/<nazwa>/usun`; pliki w
  `instance/dostepnosc/wyniki/`, ochrona przed `../` w nazwie
- Plik przykładowy `dostepnosc/przyklad/przyklad_poznan_syntetyczny.csv`
  (631 komórek, rozdzielczość 9) + skrypt, który go generuje —
  wyraźnie opisany jako dane SYNTETYCZNE (zmyślone punkty, odległość w
  linii prostej × 1,3)
- Frontend: lista plików + wgrywanie, wybór wskaźnika, kafelki (udziały,
  km², mediana, maksimum, liczba komórek), mapa heksagonów z legendą i
  dymkami
- Poprawka stylu: przyciski zoomu Leafleta w trybie ciemnym
- Testy: 16 nowych (wczytywanie i błędy formatu, klasy, udziały,
  powierzchnie, kolejność współrzędnych, endpointy, bezpieczeństwo nazw)
- Nowa zależność `h3==4.5.0`; `DECISIONS.md`: D-015
- `uruchom.sh` sam doinstalowuje zależności, gdy zmieni się
  `requirements.txt` (suma kontrolna w `.venv/`); `README.md`;
  `docs/URUCHOMIENIE.md` uzupełnione o aktualizację i klucze

Testy: 95 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap8_20260929.zip

## ETAP 9 — MPZP: słownik symboli, wyszukiwanie po identyfikatorze, historia
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `mpzp/symbole.py`: słownik oznaczeń przeznaczenia (rozporządzenie z
  2003 r. + kilka powszechnych), rozbiór symboli typu `1MN`, `12KDL`,
  `MN/U`, `MW,U`; nieznany symbol → „brak w słowniku”; w panelu
  przypis, że opis jest orientacyjny, a rozstrzyga uchwała
- `dane/uldk.py`: `znajdz_dzialke_po_id` (ULDK `GetParcelById`) z
  walidacją formatu identyfikatora przed zapytaniem
- `GET /mpzp/dzialka?id=` — ta sama ścieżka co kliknięcie (wspólna
  funkcja `_wynik_dla_dzialki`), punkt do sprawdzenia planu to
  `representative_point()` działki (zawsze wewnątrz wielokąta)
- `mpzp/baza.py` (`instance/mpzp/mpzp.db`): historia 20 ostatnio
  sprawdzonych działek bez duplikatów, `GET /mpzp/historia`
- `/mpzp/sprawdz` zwraca dodatkowo `punkt` i
  `wydzielenie.opis_przeznaczenia`
- Frontend: pole wyszukiwania działki, opis symbolu z etykietami, lista
  „Ostatnio sprawdzane” (klik = ponowne sprawdzenie i przybliżenie)
- Test wykrył błąd kolejności historii przy kilku sprawdzeniach w tej
  samej sekundzie — poprawione (kolejność po `rowid`)
- Testy: 13 nowych; `DECISIONS.md`: D-016

Testy: 108 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap9_20260929.zip

## ETAP 10 — Atlas: porównanie lat i eksport CSV
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `atlas/statystyki.py`: `porownaj` (zmiana bezwzględna i procentowa dla
  gmin obecnych w obu latach; przy wartości bazowej 0 procent = brak),
  `statystyki_zmiany` (wzrosty, spadki, mediana zmiany, największy
  wzrost/spadek), `fakty_zmiany` dla opisu, stałe progi klas zmiany
  −10 / −2 / +2 / +10%
- `/atlas/dane` i `POST /atlas/opis` przyjmują opcjonalny `rok_bazowy`
  (musi być wcześniejszy niż rok badany); opis dostaje fakty o zmianie
  — strażnik liczb obowiązuje nadal
- `GET /atlas/eksport.csv` — tabela gmin (wartości albo porównanie),
  UTF-8 z BOM
- Frontend: pole „Porównaj z”, przełącznik segmentowy Wartość/Zmiana,
  kartogram rozbieżny (spadek pomarańczowy, wzrost niebieski), kafelki
  zmiany, ranking po zmianie procentowej (kolor +/−, dymek „przed →
  po”), przycisk „Pobierz CSV”
- Poprawka: przy pierwszym wczytaniu kartogram mógł się przybliżać do
  maksimum (mapa w ukrytym kontenerze) — `invalidateSize()` przed
  dopasowaniem widoku
- Testy: 8 nowych; `DECISIONS.md`: D-017

Testy: 116 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap10_20260929.zip

## ETAP 11 — Fiszki: wyszukiwarka, eksport wszystkiego, usuwanie PDF-a
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `GET /fiszki/szukaj?q=` — przeszukuje pytanie, odpowiedź i fragment
  we wszystkich plikach, bez rozróżniania wielkości liter także dla
  polskich znaków (`casefold` w Pythonie), maks. 50 wyników
- `GET /fiszki/eksport.csv` i `/fiszki/eksport.txt` — wszystkie fiszki
  naraz (CSV z dodatkową kolumną `plik`); eksport jednego PDF-a bez
  zmian — wspólne funkcje `_odpowiedz_csv` / `_odpowiedz_anki`
- `POST /fiszki/<pdf_id>/usun` — usuwa PDF, jego fiszki, stan powtórek
  (kaskada) i plik z dysku; przycisk „Usuń plik” z potwierdzeniem
- Lista plików: karta „Szukaj w fiszkach” z wyróżnieniem frazy
  (`<mark>`, bez `innerHTML`), wynik otwiera PDF z podświetlonym
  fragmentem; linki „Wszystkie do CSV / Anki”
- Testy: 3 nowe; `DECISIONS.md`: D-018

Testy: 119 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap11_20260929.zip

## ETAP 12 — Bezpieczeństwo: ochrona przed obcymi stronami (CSRF, DNS rebinding)
Data: 2026-09-29
Status: zamknięty

Audyt: aplikacja słucha tylko na 127.0.0.1, ale każda strona otwarta w
tej samej przeglądarce mogła wysłać do niej zwykły formularz POST (bez
pytania wstępnego CORS). Narażone były: `POST /fiszki/<id>/usun`,
`/fiszki/upload`, `/dostepnosc/wgraj`, `/dostepnosc/plik/<n>/usun`,
`/mpzp/odswiez`. Endpointy JSON (`application/json`) były bezpieczne —
przeglądarka nie wyśle takiego zapytania do obcego serwera bez zgody
CORS. Dodatkowo możliwy był DNS rebinding (obca domena wskazująca na
127.0.0.1 = pełny dostęp do odczytu). `innerHTML` z danymi użytkownika:
brak (jedyne użycie to stały tekst).

Zrobione:
- `ochrona.py` + rejestracja w `app.py`:
  - nagłówek `Host` musi być `127.0.0.1` albo `localhost` (każda
    metoda) — blokuje DNS rebinding,
  - POST/PUT/DELETE/PATCH z obcym `Origin` (albo `Referer`, gdy brak
    `Origin`; także `Origin: null` i inny port) → 403; zapytania bez
    obu nagłówków (curl, testy) przechodzą,
  - nagłówki `X-Frame-Options: DENY` (clickjacking),
    `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`
- Sprawdzone w przeglądarce, że własne formularze i zapytania
  (usuwanie PDF, powtórki, edycja PUT, wgrywanie/usuwanie CSV,
  wyszukiwanie działki) działają dalej
- Testy: 9 nowych; `DECISIONS.md`: D-019

Testy: 128 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap12_20260929.zip

## ETAP 13 — Dostępność: wskaźnik łączny „miasta 15-minutowego”
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `dostepnosc/wyniki.py`: `analiza_laczna` — czas dojścia do wszystkich
  usług naraz = maksimum z kolumn czasu w komórce (brak w dowolnej
  kolumnie → brak wartości), te same klasy i udziały 5/10/15 min co dla
  pojedynczej usługi; „najsłabsze ogniwo” — która usługa najczęściej
  jest najdalej (liczba i procent komórek)
- `GET /dostepnosc/plik/<nazwa>/laczny`; metadane pliku mają
  `laczny_dostepny` (co najmniej dwie kolumny czasu)
- Frontend: opcja „★ Wszystkie usługi naraz” (domyślna, gdy dostępna),
  blok „Najsłabsze ogniwo” z paskami
- Testy: 3 nowe; `DECISIONS.md`: D-020

Testy: 131 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap13_20260929.zip

## ETAP 14 — Pulpit na stronie głównej, ikona aplikacji
Data: 2026-09-29
Status: zamknięty

Zrobione:
- Karty modułów na stronie głównej pokazują żywe podsumowania: fiszki
  do powtórki dziś, ostatnio sprawdzona działka z symbolem planu,
  liczba własnych plików dostępności, liczba zestawów danych atlasu w
  cache
- Każdy moduł ma własną funkcję podsumowania (`podsumowanie()` w
  `fiszki/`, `mpzp/`, `dostepnosc/routes.py`,
  `liczba_zapisanych_zestawow()` w `atlas/baza.py`); `app.py` tylko je
  woła, a błąd jednego modułu nie blokuje strony głównej (log + karta
  bez podsumowania)
- Ikona aplikacji `static/favicon.svg` (+ przekierowanie `/favicon.ico`,
  koniec błędów 404 w konsoli)
- Testy: 3 nowe; `DECISIONS.md`: D-021

Testy: 134 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap14_20260929.zip

## ETAP 15 — Poprawki z przeglądu kodu (ETAPy 4–14)
Data: 2026-09-29
Status: zamknięty

Przegląd całej zmiany od ETAPu 3 wykazał 7 błędów — wszystkie naprawione,
do każdego (poza skryptem powłoki i wyścigiem w JS, sprawdzonymi ręcznie)
test, który go odtwarza:
1. Dostępność: plik `Wyniki.CSV` był zapisywany, ale niewidoczny i nie do
   otwarcia (lista i odczyt szukały małego `.csv`) → rozszerzenie
   normalizowane przy zapisie
2. Dostępność: wskaźnik łączny bez żadnej pełnej komórki kończył się
   błędem 500 → czytelny komunikat (422)
3. Dostępność: powtórzone nazwy kolumn po cichu przesuwały wartości
   między komórkami → plik odrzucany z komunikatem
4. MPZP: dwa szybkie kliknięcia zostawiały na mapie wielokąty nie do
   usunięcia i pokazywały odpowiedź na starsze kliknięcie → numer
   zapytania, starsze odpowiedzi ignorowane (sprawdzone w przeglądarce
   z opóźnioną pierwszą odpowiedzią)
5. Atlas: „największy spadek” był ostatnią pozycją listy nawet przy
   samych wzrostach (i trafiał do faktów dla Gemini) → tylko prawdziwy
   spadek/wzrost, inaczej brak (kafelek „żadna gmina nie spadła”)
6. Atlas: pusty wynik BDL (rok jeszcze nieopublikowany) trafiał do cache
   na 30 dni → pustych wyników nie zapisujemy
7. `uruchom.sh`: brak linii `PORT=` w `.env` zamykał skrypt bez
   komunikatu (`set -e` + nieudany `grep`) → `|| true` (sprawdzone:
   serwer wstaje na domyślnym 5000)

Testy: 139 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap15_20260929.zip

## ETAP 16 — MPZP: wyszukiwanie działki po obrębie i numerze z podpowiedziami
Data: 2026-09-29
Status: zamknięty (format odpowiedzi ULDK niesprawdzony na żywo — patrz niżej)

Prośba autora: wpisuję działkę i od razu wyskakuje, bez znajomości
pełnego identyfikatora.

Zrobione:
- `dane/uldk.py`: `szukaj_dzialek(fraza)` — ULDK `GetParcelByIdOrNr`
  („<obręb> <numer>” albo pełny identyfikator), wynik: identyfikator,
  gmina, obręb, numer; maks. 15 podpowiedzi
- `GET /mpzp/podpowiedzi?q=` — najpierw pasujące wpisy z historii, potem
  działki z ULDK (bez duplikatów); pełny identyfikator nie wymaga
  zapytania; bez cyfry we frazie — wskazówka „dopisz numer działki”
- Frontend: lista podpowiedzi pojawia się sama po wpisaniu 3 znaków
  (opóźnienie 400 ms, starsze odpowiedzi ignorowane), sekcje „Ostatnio
  sprawdzane” i „Ewidencja gruntów (ULDK)”, obsługa myszy i klawiatury
  (↑ ↓ Enter Esc); wybór od razu pokazuje działkę i przeznaczenie
- Testy: 7 nowych (parser w obu wariantach statusu, limit, endpoint)

Do sprawdzenia u autora: parser akceptuje oba spotykane warianty
pierwszej linii odpowiedzi ULDK (liczba wyników albo „0”); jeśli
podpowiedzi nie pojawią się mimo poprawnej nazwy obrębu — przysłać
komunikat z listy.

Testy: 146 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap16_20260929.zip

## ETAP 17 — Połączenie z main, test „od zera”, czytelne błędy sieci
Data: 2026-09-29
Status: zamknięty

Diagnoza zgłoszenia „brzydkie strony, fiszki nie działają”: gałąź `main`
na GitHubie kończyła się na ETAPie 3 (commit „tak”) — autor uruchamiał
starą wersję. Cała praca z ETAPów 4–16 była na gałęzi
`claude/vibrant-knuth-1b5loa`.

Zrobione:
- Za zgodą autora `main` przesunięty (fast-forward, bez konfliktów) do
  najnowszej wersji — zwykły `git pull` daje teraz wszystko
- Test „jak u autora”: świeży klon `main` z GitHuba, czyste venv, instalacja
  `requirements.txt`, start przez `uruchom.sh` (sam tworzy `.env`), pełny
  scenariusz w Chromium na 6-stronicowym PDF-ie z polskimi znakami:
  wgranie, wyświetlenie, zaznaczenie tekstu, szkic (bez klucza —
  czytelny komunikat), zapis fiszki, zmiana strony, „pokaż w źródle”,
  powtórka — wszystko działa; 146 testów zielonych w czystym środowisku
- `dane/siec.py`: `opis_bledu_sieci` — zamiast „HTTPSConnectionPool…
  ProxyError…” jedno zdanie po polsku (brak połączenia / przekroczony
  czas / błąd usługi); używane w BDL, ULDK, PRG i WFS
- Poprawka: podwójna kropka w komunikacie „Gemini nie odpowiedział”
- Test: 1 nowy

Testy: 147 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap17_20260929.zip

## ETAP 18 — Fiszki: propozycje z całej strony, statystyki nauki, naprawa kotwicy
Data: 2026-09-29
Status: zamknięty

Zrobione:
- Przycisk „✦ Fiszki z tej strony”: tekst strony z pdf.js →
  `POST /fiszki/<pdf_id>/szkice-strony` → Gemini (`zaproponuj_fiszki_ze_strony`,
  odpowiedź JSON) proponuje do 5 fiszek, każdą z dosłownym cytatem;
  `fiszki/strona.py` sprawdza, czy cytat naprawdę jest na stronie —
  propozycje bez kotwicy są odrzucane (liczba odrzuconych w komunikacie)
- Panel propozycji: zaznaczanie, edycja pytania i odpowiedzi, klik w
  cytat podświetla go w PDF-ie, „Zapisz zaznaczone”
- **Naprawiony błąd kotwicy** (odtworzony w przeglądarce przed poprawką):
  fiszka z zaznaczenia przez kilka linii nie podświetlała się w „Pokaż w
  źródle” (zaznaczenie zawiera „\n”, sklejone spany nie) — dopasowanie z
  pominięciem białych znaków, po stronie przeglądarki i serwera
- Tabela `dziennik_powtorek` + `fiszki/statystyki_nauki.py`: seria dni
  nauki (dzień bieżący nie przerywa serii przed jego końcem), powtórki
  dziś, skuteczność „umiem” z 30 dni, liczba opanowanych (pudełko 5),
  aktywność 30 dni; `GET /fiszki/statystyki`; karta na liście plików z
  „kalendarzem aktywności”
- Testy: 8 nowych; `DECISIONS.md`: D-025

Testy: 155 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap18_20260929.zip

## ETAP 19 — Atlas: profil gminy z wykresem w czasie
Data: 2026-09-29
Status: zamknięty (endpoint BDL `/data/by-unit` niesprawdzony na żywo)

Zrobione:
- `dane/bdl.py`: `szereg_gminy(zmienna, gmina)` — wartości zmiennej dla
  jednej gminy we wszystkich latach (BDL `/data/by-unit/{id}?var-id=`),
  rosnąco, bez braków
- `GET /atlas/gmina/<bdl_id>?zmienna=` (cache 30 dni) + zmiana od
  pierwszego do ostatniego roku (`statystyki.zmiana_w_szeregu`)
- Karta „profil gminy” po kliknięciu gminy na mapie albo w rankingu:
  miejsce w województwie, wartość, różnica od mediany województwa,
  zmiana w całym okresie, wykres liniowy (`atlas/static/wykres_gminy.js`,
  czyste SVG: linia 2 px, dyskretna siatka, etykieta ostatniej wartości,
  przerywana linia mediany województwa, celownik z dymkiem), tabela
  wartości dla dostępności; kolory z tokenów CSS (jasny/ciemny motyw)
- Testy: 3 nowe; `DECISIONS.md`: D-026

Testy: 158 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap19_20260929.zip

## ETAP 20 — MPZP: powierzchnia, podział działki na przeznaczenia, raport do druku
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `mpzp/geometria.py`: powierzchnia w m² z geometrii WGS84 (lokalna skala
  metrów na stopień wg elipsoidy WGS84, błąd < 0,1% dla działek — bez
  pyproj); szkic SVG działki na tle wydzieleń (proporcje w metrach,
  północ u góry)
- `mpzp/wfs.py`: `wydzielenia_dzialki` — wszystkie wydzielenia
  przecinające działkę (indeks STRtree + część wspólna), wspólna funkcja
  `_warstwa` dla cache
- `/mpzp/sprawdz` i `/mpzp/dzialka` zwracają `dzialka.powierzchnia_m2`
  oraz `udzialy` — podział działki na przeznaczenia (m², %; ten sam
  symbol sumowany, części < 0,5% pomijane jako niedokładność granic)
- Panel: powierzchnia, „Podział działki” (pasek proporcji + lista z
  opisem), gdy działka leży w więcej niż jednym przeznaczeniu; etykieta
  „przeznaczenie w klikniętym punkcie”
- `GET /mpzp/raport?id=` — raport działki do wydruku / PDF: dane działki,
  powierzchnia (m², ha), szkic, tabela przeznaczeń z udziałami i opisami,
  źródła i zastrzeżenie „nie jest wypisem ani wyrysem”; style `@media
  print` (bez nawigacji i przycisków, kolory zachowane)
- Testy: 6 nowych; `DECISIONS.md`: D-027

Testy: 164 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap20_20260929.zip

## ETAP 21 — Dostępność: ludność i porównanie scenariuszy
Data: 2026-09-29
Status: zamknięty

Zrobione:
- Kolumna `ludnosc` / `populacja` / `mieszkancy` w CSV jest wagą komórek,
  a nie wskaźnikiem: udziały 5/10/15 min liczone także jako % i liczba
  mieszkańców (kafelki: „25,3% mieszk. · 33 799 os. · 12,7% pow.”);
  ujemna ludność odrzucana
- `porownaj_scenariusze(przed, po, kolumna)`: zmiana czasu dojścia w
  komórkach wspólnych dla obu plików (także dla wskaźnika łącznego):
  poprawa / pogorszenie / bez zmian (±1 min), mediana i największa
  poprawa, udział w zasięgu 15 min przed → po, komórki i mieszkańcy,
  którzy weszli w zasięg 15 min albo z niego wypadli; klasy rozbieżne
  −5 / −1 / +1 / +5 min
- `GET /dostepnosc/porownanie?przed=&po=&kolumna=` (kolumna=laczny dla
  wskaźnika łącznego)
- Frontend: karta „Porównaj scenariusze”, mapa zmian (niebieski:
  szybciej, pomarańczowy: wolniej), kafelki scenariusza, legenda,
  „Zakończ”; zmiana wskaźnika w trybie porównania przelicza porównanie
- Drugi plik przykładowy `przyklad_poznan_nowa_szkola_syntetyczny.csv`
  (ten sam obszar + jedna nowa szkoła) i kolumna ludności w obu —
  SYNTETYCZNE, generowane skryptem
- Testy: 6 nowych; `DECISIONS.md`: D-028

Testy: 170 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap21_20260929.zip

## ETAP 22 — Poprawki z przeglądu kodu (ETAPy 18–21)
Data: 2026-09-29
Status: zamknięty

Przegląd ETAPów 18–21 wykazał 2 błędy — oba odtworzone i naprawione:
1. MPZP: wielokąt planu przecinający sam siebie (częsty w danych gmin)
   powodował `GEOSException` przy liczeniu podziału działki → błąd 500
   także dla kliknięć, które wcześniej działały. Geometrie z WFS są
   teraz naprawiane (`make_valid`) przy wczytywaniu, a przecięcie jest
   zabezpieczone — nienaprawialne wydzielenie jest pomijane, reszta działa
   (także w raporcie)
2. Fiszki: przy częściowo nieudanym zapisie propozycji ze strony lista
   była czyszczona i niezapisane propozycje przepadały; przy zerwanym
   połączeniu przycisk zostawał zablokowany. Teraz zapisane znikają,
   nieudane zostają oznaczone na czerwono do ponownej próby, przycisk
   zawsze wraca (`try/finally`) — sprawdzone w przeglądarce z
   przechwyconym błędem 500
- Testy: 2 nowe

Testy: 172 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap22_20260929.zip

## ETAP 23 — MPZP: kalkulator wskaźników zabudowy
Data: 2026-09-29
Status: zamknięty

Analiza potrzeb (student GP, 2. rok): projekty z urbanistyki i
planowania wymagają ciągłego liczenia wskaźników zabudowy i sprawdzania
ich z ustaleniami planu — dotąd ręcznie w arkuszu.

Zrobione:
- `mpzp/zabudowa.py`: wskaźnik powierzchni zabudowy [%], intensywność
  (powierzchnia całkowita kondygnacji nadziemnych / działka), udział
  PBC [%], maks. wysokość i kondygnacje; zgodność z ustaleniami planu
  (każde ustalenie osobno, równość z limitem = spełnione); „ile jeszcze
  można zabudować” — najostrzejszy z limitów (% zabudowy, min. PBC,
  maks. intensywność), nigdy ujemny; walidacja danych
- `GET /mpzp/kalkulator` (opcjonalnie `?powierzchnia=&dzialka=` z panelu
  działki) i `POST /mpzp/kalkulator/licz`; przecinek dziesiętny
- Strona kalkulatora: działka, lista budynków (dodawanie/usuwanie),
  ustalenia planu, wyniki na bieżąco (kafelki, lista ✓/✗, zapas);
  link „Kalkulator zabudowy” w panelu działki (z jej powierzchnią) i w
  nagłówku mapy
- Testy: 6 nowych; `DECISIONS.md`: D-030

Testy: 178 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap23_20260929.zip

## ETAP 24 — Eksport do QGIS (GeoJSON) ze wszystkich map
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `GET /atlas/eksport.geojson` — granice gmin z wartością, rokiem,
  wskaźnikiem, jednostką (i zmianą przy porównaniu lat); gminy bez danych
  zostają z pustą wartością
- `GET /mpzp/eksport.geojson?id=` — działka (z powierzchnią) i jej części
  w przeznaczeniach planu (symbol, m², %, atrybuty WFS z prefiksem
  `wfs_`)
- `GET /dostepnosc/eksport.geojson?plik=&kolumna=[&po=]` — heksagony z
  wartością i klasą, wskaźnik łączny (`kolumna=laczny`) albo porównanie
  scenariuszy (przed, po, zmiana)
- Przyciski „GeoJSON do QGIS” w atlasie, panelu działki i dostępności —
  zawsze eksportują to, co jest na mapie
- Format RFC 7946 (WGS84), `application/geo+json`, jako załącznik
- Testy: 3 nowe; `DECISIONS.md`: D-031

Testy: 181 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap24_20260929.zip

## ETAP 25 — Atlas: korelacja dwóch wskaźników
Data: 2026-09-29
Status: zamknięty

Analiza potrzeb: statystyka na 2. roku GP — zależności między zjawiskami
w gminach (np. ludność a mieszkania oddane, bezrobocie a dochody).

Zrobione:
- `atlas/statystyki.py`: `korelacja` — łączenie gmin po TERYT, r
  Pearsona, rho Spearmana (rangi z uśrednianiem remisów), R², prosta
  regresji (`statistics.linear_regression`), opis siły wg stałych progów
  |r| 0,1 / 0,3 / 0,5 / 0,7 z kierunkiem; przypadki brzegowe (< 3 gminy,
  wskaźnik stały → brak wyniku z wyjaśnieniem)
- `GET /atlas/korelacja?zmienna=&zmienna2=&rok=&woj=` (dane z cache BDL)
- Karta „Korelacja z innym wskaźnikiem”: wyszukiwarka drugiego
  wskaźnika, wykres rozrzutu SVG (punkty z większym polem trafienia,
  dymek z nazwą gminy, przerywana linia regresji, opisane osie; oś nie
  schodzi poniżej zera dla danych nieujemnych), liczby, opis słowny i
  przypomnienie „korelacja ≠ przyczynowość”; `atlas.js` przekazuje dane
  zdarzeniem `atlas:dane`, więc `korelacja.js` jest niezależnym plikiem
- Testy: 10 nowych (m.in. wartość podręcznikowa r = 0,7746,
  odporność Spearmana na wartość skrajną); `DECISIONS.md`: D-032

Testy: 191 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap25_20260929.zip

## ETAP 26 — Fiszki: quiz ABCD i najtrudniejsze fiszki
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `fiszki/quiz.py`: `uloz_quiz(zakres, pula, liczba, losowanie)` — pytania z
  wybranego zakresu (PDF albo wszystko), 3 błędne odpowiedzi z innych
  fiszek (najpierw z tego samego PDF-a — podobny temat), bez duplikatów
  treści (porównanie bez wielkości liter i nadmiarowych spacji);
  wymaga co najmniej 4 fiszek z różnymi odpowiedziami; nic nie generuje
  model — quiz składa się tylko z zatwierdzonych fiszek
- `najtrudniejsze(db)` — fiszki z największą liczbą „nie umiem” w
  dzienniku powtórek (i najgorszym stosunkiem błędów do prób)
- `GET /fiszki/quiz[?pdf_id=]`, `GET /fiszki/quiz/pytania[?pdf_id=&liczba=&ziarno=]`
- Strona quizu: odpowiedzi A–D (klawisze 1–4 / A–D, Enter = dalej),
  natychmiastowa informacja poprawna/błędna, pasek postępu, wynik z
  listą pomyłek prowadzących do źródła w PDF-ie
- Lista plików: karta „Najtrudniejsze fiszki”, przycisk „Quiz ABCD”;
  widok PDF-a: przycisk „Quiz”
- Testy: 6 nowych; `DECISIONS.md`: D-033

Testy: 197 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap26_20260929.zip

## ETAP 27 — Poprawki z przeglądu kodu (ETAPy 23–26)
Data: 2026-09-29
Status: zamknięty

Przegląd wykazał 6 problemów — wszystkie naprawione:
1. Atlas: brak/niepoprawny `zmienna2` w `/atlas/korelacja` dawał surowy
   komunikat Pythona zamiast czytelnego (odwrócony warunek)
2. Kalkulator: budynek z rzutem bez liczby kondygnacji liczył się po
   cichu jako 0 kondygnacji (intensywność 0, zawyżony zapas) → czytelny
   błąd „Podaj liczbę kondygnacji”
3. Kalkulator: wyczyszczenie powierzchni działki nie unieważniało
   trwającego przeliczenia (stary wynik nadpisywał komunikat)
4. Korelacja: odpowiedzi nie były dopasowane do ostatniego zapytania
   (wolniejsza odpowiedź dla wskaźnika A nadpisywała B)
5. Korelacja: przy nieudanym wczytaniu granic panel korelacji liczył dla
   poprzednich danych — zdarzenie `atlas:dane` wysyłane teraz od razu
   po wczytaniu danych, przed granicami
6. Quiz: Ctrl+C / Cmd+A itd. były traktowane jako wybór odpowiedzi C / A
- Sprawdzone w przeglądarce (quiz, kalkulator); testy: 2 nowe

Testy: 199 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap27_20260929.zip

## ETAP 28 — Atlas: miary zróżnicowania i histogram
Data: 2026-09-29
Status: zamknięty

Analiza potrzeb: statystyka i geografia społeczno-ekonomiczna — ocena
zróżnicowania zjawiska między gminami.

Zrobione:
- `atlas/statystyki.py`: `zroznicowanie` — odchylenie standardowe
  (populacyjne — gminy to cała populacja województwa), współczynnik
  zmienności z oceną (< 25% słabe, 25–45% przeciętne, 45–100% silne,
  > 100% bardzo silne), kwartyle i rozstęp kwartylowy, relacja max/min,
  współczynnik Giniego (dla wartości nieujemnych); `histogram` — 10
  przedziałów równej szerokości; przypadki brzegowe (średnia 0, wartości
  ujemne, jedna gmina, wszystkie równe)
- CV i Gini trafiają do faktów dla opisu Gemini (strażnik liczb działa)
- Karta „Zróżnicowanie / Rozkład gmin”: miary z objaśnieniami w dymkach,
  histogram SVG (słupki z odstępem 2 px, dymek z przedziałem i liczbą
  gmin, linia mediany)
- Testy: 5 nowych (m.in. σ = 2 dla klasycznego przykładu, Gini 0,75 dla
  [0,0,0,10]); `DECISIONS.md`: D-035

Testy: 204 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap28_20260929.zip

## ETAP 29 — Atlas: wskaźniki względne („na 1000 mieszkańców”)
Data: 2026-09-29
Status: zamknięty

Analiza potrzeb: wiele zmiennych GUS to liczby bezwzględne (mieszkania,
bezrobotni, podmioty) — porównanie gmin ma sens dopiero po odniesieniu
do liczby mieszkańców albo powierzchni.

Zrobione:
- `atlas/statystyki.py`: `podziel` (licznik / mianownik × mnożnik po
  TERYT, mianownik 0 pomijany), `podziel_szeregi` (to samo dla lat)
- Parametry `mianownik` i `mnoznik` (1, 100, 1000, 10 000) w `/atlas/dane`,
  `/atlas/opis`, eksporcie CSV/GeoJSON, porównaniu lat, korelacji i
  profilu gminy; nazwa i jednostka wskaźnika budowane automatycznie
  („… na 1 000 (ludność ogółem)”, „mieszk. / 1 000 osoba”); walidacja
  (mianownik ≠ licznik, dozwolony mnożnik)
- Formularz: drugi wiersz „Przelicz na (opcjonalnie)” z wyszukiwarką
  mianownika, mnożnikiem i przyciskiem „bez przeliczenia”; pod
  formularzem pełny opis tego, co jest na mapie
- Testy: 7 nowych; `DECISIONS.md`: D-036

Testy: 211 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap29_20260929.zip

## ETAP 30 — MPZP: kalkulator skali mapy
Data: 2026-09-29
Status: zamknięty

Analiza potrzeb: rysunki planistyczne i inwentaryzacje w skalach 1:500 –
1:10 000 — ciągłe przeliczanie wymiarów i dobór skali do arkusza.

Zrobione:
- `mpzp/skala.py`: długość rysunek ↔ teren (mm/cm ↔ m/km), powierzchnia
  rysunek ↔ teren (cm² ↔ m²/ha/km², skalowanie kwadratem mianownika),
  dobór najdokładniejszej skali standardowej (1:500 … 1:100 000), w której
  teren zmieści się na arkuszu A4–A0 z marginesem, w orientacji pionowej
  albo poziomej, z procentem wypełnienia arkusza
- `GET /mpzp/skala`, `POST /mpzp/skala/licz` (puste pole = tej części nie
  liczymy; przecinek i spacje w liczbach)
- Strona: skala z szybkimi przyciskami skal standardowych, trzy karty
  (długość, powierzchnia, dobór do arkusza), wyniki na bieżąco; link z
  nagłówka mapy MPZP
- Testy: 4 nowe; `DECISIONS.md`: D-037

Testy: 215 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap30_20260929.zip

## ETAP 31 — Fiszki do druku
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `GET /fiszki/druk[?pdf_id=]` — karty do wycięcia i złożenia na pół:
  pytanie | odpowiedź, obrys ciągły (cięcie), linia przerywana (zgięcie),
  numer karty na obu połówkach, źródło (plik, strona) w rogu; druk
  jednostronny, bez dopasowywania stron przy druku dwustronnym
- Style druku: A4, margines 10 mm, 2 karty w rzędzie (ok. 44 mm
  wysokości), karty nie dzielą się między strony; przyciski „Drukuj
  karty” na liście plików i w widoku PDF-a
- Test: 1 nowy; `DECISIONS.md`: D-038

Testy: 216 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap31_20260929.zip

## ETAP 32 — Kopia zapasowa danych
Data: 2026-09-29
Status: zamknięty

Zrobione:
- `kopia.py`: ZIP folderu `instance/` — bazy SQLite kopiowane przez
  `sqlite3.backup()` (spójne nawet w trakcie zapisu), PDF-y, pliki
  wyników; pomijane: cache granic PRG, pliki tymczasowe SQLite; w środku
  `PRZYWRACANIE.txt` z instrukcją
- `GET /kopia-zapasowa` (nazwa z datą i godziną); sekcja „Twoje dane”
  na stronie głównej; instrukcja w `docs/URUCHOMIENIE.md`
- `.env` (klucze API) nigdy nie trafia do kopii — nie leży w `instance/`
- Test: 1 nowy (zawartość ZIP, poprawność bazy z kopii, brak cache);
  `DECISIONS.md`: D-039

Testy: 217 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap32_20260929.zip

## ETAP 33 — Poprawki z przeglądu kodu (ETAPy 28–32)
Data: 2026-09-29
Status: zamknięty

Przegląd wykazał 4 błędy — wszystkie naprawione:
1. Atlas: ręczne skasowanie lub zmiana tekstu mianownika nie wyłączała
   go — mapa, eksport, profil i opis dalej dzieliły przez niewidoczny
   wskaźnik; teraz edycja pola = rezygnacja z mianownika
2. Skala: margines 0 był traktowany jak „nie podano” (20 mm), a ujemny
   margines powiększał pole arkusza ponad papier → 0 działa, ujemny jest
   błędem
3. Skala i kalkulator zabudowy: „nan”, „inf”, „1e400” przechodziły jako
   liczby i psuły odpowiedź JSON → wspólna `_liczba_skonczona`
   odrzuca liczby nieskończone z czytelnym komunikatem
4. Skala: po błędzie zostawały stare wyniki, które wyglądały jak wynik dla
   nowych danych → czyszczone do „—”
- Testy: 5 nowych

Testy: 222 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap33_20260929.zip

## ETAP 34 — Mapy bez „Access blocked”
Data: 2026-09-29
Status: zamknięty

- Atlas: zamiast kafelków OSM białe tło + szare województwa (PRG
  A01, cache na dysku), nazwy sąsiednich województw; nazwa wybranego
  chowa się pod kartogramem
- MPZP, Dostępność: `referrerPolicy` na warstwie OSM + przełącznik
  podkładów (OSM / ortofotomapa GUGiK / bez podkładu)
- Sprawdzone w przeglądarce na danych testowych (jasny i ciemny motyw);
  prawdziwe usługi niedostępne z kontenera
- `DECISIONS.md`: D-041

Testy: 225 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap34_20260929.zip

## ETAP 35 — MPZP dla wszystkich gmin
Data: 2026-09-29
Status: zamknięty

- `mpzp/krajowe.py`: GetCapabilities (warstwy, CRS, cache doba),
  GetFeatureInfo (GML → zapasowo text/plain), rozpoznanie symbolu,
  tytułu i linków
- `/sprawdz`, `/dzialka`, `/raport`: gmina bez WFS → plan krajowy
  zamiast „gmina nieobsługiwana”; historia zapisuje rozpoznany symbol
- Mapa: nakładki WMS planów (KIMPZP) i działek (KIEG)
- Sprawdzone w przeglądarce na danych testowych; prawdziwa usługa
  niedostępna z kontenera (D-042)
- `DECISIONS.md`: D-042

Testy: 238 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap35_20260929.zip

## ETAP 36 — Narzędzia mapy MPZP
Data: 2026-09-29
Status: zamknięty

- Współrzędne punktu: WGS84 + PL-1992 + PL-2000 (strefa wg długości),
  zgodne z pyproj co do mm; kopiowanie do schowka
- Pomiar: łamana, ostatni odcinek, powierzchnia i obwód wieloboku;
  ostrzeżenie przy obrysie przecinającym się; numerowanie zapytań
- Link do działki w Geoportalu
- Sprawdzone w przeglądarce (jasny i ciemny motyw)
- `DECISIONS.md`: D-043

Testy: 254 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap36_20260929.zip

## ETAP 37 — Poprawki z przeglądu kodu (ETAPy 34–36)
Data: 2026-09-29
Status: zamknięty

Przegląd wykazał 4 problemy — wszystkie naprawione:
1. Atlas: gdy tło województw (pierwsze pobranie z PRG) przyszło po
   kartogramie, nazwa wybranego województwa zasłaniała mapę → tło po
   wczytaniu chowa nazwę województwa z kartogramu (`terytNaMapie`,
   brane z danych, nie z listy, którą można już było zmienić)
2. KIMPZP: raport błędu w formacie tekstowym dawał pustą listę, czyli
   komunikat „brak planu” → teraz błąd usługi
3. KIMPZP: przy >30 warstwach w GetCapabilities adres WMS byłby bardzo
   długi → pytamy o nazwaną warstwę główną (grupę)
4. Eksport GeoJSON dla gmin bez WFS miał samą działkę → dochodzą
   `przeznaczenie_kimpzp` i `plan_kimpzp`
- Testy: 4 nowe

Testy: 258 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap37_20260929.zip

## ETAP 38 — Dostępność: krzywa, luki, szczegóły komórki
Data: 2026-09-29
Status: zamknięty

- `wyniki.krzywa_dostepnosci`, `wyniki.luki`, `wyniki.komorka`
- Krzywa rysowana w SVG (bez biblioteki wykresów), suwak progu
- Luki w dostępności z przybliżeniem mapy; okienko komórki z numeracją
  zapytań
- Sprawdzone w przeglądarce (jasny i ciemny motyw)
- `DECISIONS.md`: D-044

Testy: 264 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap38_20260929.zip

## ETAP 39 — Fiszki: trudne, pisanie, przed egzaminem, prognoza
Data: 2026-09-29
Status: zamknięty

- `powtorki.nastepny_stan`: wynik „trudne”
- `/powtorka?wszystkie=1` + `/powtorka/kolejka?wszystkie=1` (losowo, bez
  zapisu ocen po stronie przeglądarki)
- `statystyki_nauki.prognoza` (zaległe i nowe liczone na dziś)
- Sprawdzone w przeglądarce (jasny i ciemny motyw)
- `DECISIONS.md`: D-045

Testy: 269 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap39_20260929.zip

## ETAP 40 — Atlas: metody klasyfikacji
Data: 2026-09-29
Status: zamknięty

- `statystyki.klasyfikuj` (+ `progi_rowne`, `progi_odchylenia`,
  `progi_jenks`, `liczebnosci_klas`, `gvf`)
- `/atlas/dane?metoda=&klasy=`, `/atlas/klasy` (z cache BDL, bez
  przeładowania strony); numerowanie zapytań o klasy
- Szybki wybór: frazy, nie identyfikatory zmiennych (bez zgadywania ID)
- Sprawdzone w przeglądarce: Jenks ma najwyższe GVF
- `DECISIONS.md`: D-046

Testy: 274 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap40_20260929.zip

## ETAP 41 — Atlas: autokorelacja przestrzenna (Moran, LISA)
Data: 2026-09-29
Status: zamknięty

- `atlas/autokorelacja.py`: `sasiedzi` (queen, STRtree, tolerancja
  szczelin), `analiza` (I Morana, permutacje, LISA)
- Sąsiedztwo województwa liczone raz na uruchomienie (pamięć procesu)
- Tryb mapy „Klastry LISA”, przełącznik widoczny też bez porównania lat
- Zgodność z PySAL sprawdzona (globalne i lokalne I)
- `DECISIONS.md`: D-047

Testy: 279 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap41_20260929.zip

## ETAP 42 — Atlas: mapa do druku (SVG/PDF)
Data: 2026-09-29
Status: zamknięty

- `atlas/mapa_svg.py`: kartogram, legenda, podziałka („ładne” długości),
  strzałka północy
- `/atlas/mapa.svg` (tryb, metoda, klasy; `pobierz=1` → załącznik),
  `/atlas/druk` (podgląd + druk A4 poziomo)
- Link „Mapa do druku” odpowiada bieżącemu widokowi
- Naprawione przy okazji: kolejność gmin a permutacje (różne klastry na
  ekranie i na wydruku), „p = 0” w przypisie
- Sprawdzone w przeglądarce (wartość z Jenksem, LISA)
- `DECISIONS.md`: D-048

Testy: 283 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap42_20260929.zip

## ETAP 43 — MPZP: wymiary działki, obszar analizowany WZ
Data: 2026-09-29
Status: zamknięty

- `geometria.wymiary`, `geometria.obszar_analizowany`
- `POST /mpzp/obszar-analizowany` (walidacja typu geometrii, rozmiaru,
  liczb skończonych)
- Podpisy boków jako stałe dymki Leafleta, ukryte przy małym przybliżeniu
  i dla granic z ponad 40 bokami; numerowanie zapytań o obszar
- Sprawdzone w przeglądarce (działka w kształcie litery L)
- `DECISIONS.md`: D-049

Testy: 288 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap43_20260929.zip

## ETAP 44 — MPZP: Moje działki
Data: 2026-09-29
Status: zamknięty

- `baza.zapisane/zapisana/zapisz_dzialke/usun_zapisana`, tabela
  `zapisane` (CREATE IF NOT EXISTS — stare bazy działają bez migracji)
- `GET/POST/DELETE /mpzp/zapisane`, `/mpzp/zapisane.csv`
- Sprawdzone w przeglądarce: zapis, notatka, przeładowanie, odznaczenie
- `DECISIONS.md`: D-050

Testy: 296 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap44_20260929.zip

## ETAP 45 — MPZP: słownik symboli planu
Data: 2026-09-29
Status: zamknięty

- `symbole.SLOWNIK_ZWYCZAJOWY`, `GRUPY`, `wszystkie_symbole`; flaga
  `zwyczajowe` w `opisz_symbol`
- `/mpzp/symbole`, `/mpzp/symbole/rozszyfruj`, `static/symbole.js`
- Sprawdzone w przeglądarce (jasny i ciemny motyw)
- `DECISIONS.md`: D-051

Testy: 298 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap45_20260929.zip

## ETAP 46 — Poprawki z przeglądu kodu (ETAPy 43–45)
Data: 2026-09-29
Status: zamknięty

Przegląd wykazał 2 problemy — oba naprawione:
1. „Moje działki”: zmiana notatki i od razu klik w gwiazdkę — zapis
   notatki (po wyjściu z pola) mógł dojść po usunięciu i przywrócić
   działkę → usunięcie czeka na trwający zapis
2. `POST /mpzp/obszar-analizowany`: nieznany typ geometrii albo zła
   struktura współrzędnych dawały 500 → łapiemy `ShapelyError`, 400
- Testy: 4 nowe

Testy: 302 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap46_20260929.zip

## ETAP 47 — Dostępność: szybki model z punktów usług
Data: 2026-09-29
Status: zamknięty

- `model.nazwa_kolumny`, `siatka_obszaru` (szacunek liczby komórek przed
  liczeniem), `czasy_dojscia`, `obszary_obslugi`, `csv_wynikow`
- `POST /dostepnosc/z-punktow`; plik `.punkty.json` usuwany razem z CSV;
  `opis_pliku` zwraca punkty
- Sprawdzone w przeglądarce: wstawianie, usuwanie punktu, zapis, analiza
  nowej kolumny, obszary obsługi (jasny i ciemny motyw)
- `DECISIONS.md`: D-052

Testy: 314 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap47_20260929.zip

## ETAP 48 — Dostępność: raport do druku
Data: 2026-09-29
Status: zamknięty

- `druk.kolory_klas`, `druk.legenda`, `druk.mapa_svg` (limit 30 000
  komórek), `/dostepnosc/mapa.svg`, `/dostepnosc/raport`
- Link „Raport do druku” odpowiada bieżącemu wskaźnikowi; ukryty w
  trybie porównania scenariuszy
- Sprawdzone w przeglądarce (plik z punktami usług)
- `DECISIONS.md`: D-053

Testy: 317 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap48_20260929.zip

## ETAP 49 — Dostępność: nowe usługi obok istniejących
Data: 2026-09-29
Status: zamknięty

- `model.polacz_z_istniejacymi`, maska w `model.obszary_obslugi`
- Znalezione w przeglądzie ETAPów 47–48: bez tego „nowa szkoła” liczyła
  czas tylko do nowych punktów — porównanie ze stanem obecnym było
  bezużyteczne
- Sprawdzone w przeglądarce i testem: wynik nigdy gorszy niż stan
  wyjściowy, porównanie scenariuszy działa
- `DECISIONS.md`: D-054

Testy: 320 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap49_20260929.zip

## ETAP 50 — Fiszki: tematy
Data: 2026-09-29
Status: zamknięty

- `tematy.normalizuj/ustaw/tematy_fiszek/wszystkie`, tabela
  `tematy_fiszek` (ON DELETE CASCADE)
- Filtr `temat` w `/powtorka`, `/powtorka/kolejka`, `/quiz`,
  `/quiz/pytania`, `/druk`
- Przy okazji: ręczny zapis fiszki nie sprawdzał odpowiedzi serwera
- Sprawdzone w przeglądarce (lista tematów, edycja, zapamiętany temat
  nowych fiszek, powtórka z tematu)
- `DECISIONS.md`: D-055

Testy: 324 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap50_20260929.zip

## ETAP 51 — Fiszki: egzaminy, postęp, odwrócona powtórka
Data: 2026-09-29
Status: zamknięty

- `egzaminy.dodaj/usun/lista/postep/utrwalone_w_plikach`, tabela
  `egzaminy` (usunięcie PDF-a usuwa jego egzaminy)
- `POST /fiszki/egzaminy`, `POST /fiszki/egzaminy/<id>/usun`; błędy
  formularza wracają jako komunikat na stronie
- Powtórka odwrócona: tylko prezentacja, ta sama fiszka i harmonogram
- Sprawdzone w przeglądarce (dwa egzaminy, pasek przy pliku, odwrócenie
  w trakcie sesji)
- `DECISIONS.md`: D-056

Testy: 331 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap51_20260929.zip

## ETAP 52 — Atlas: na tle kraju
Data: 2026-09-29
Status: zamknięty

- `bdl.wartosci_dla_wojewodztw`, `/atlas/wojewodztwa-porownanie`,
  `static/wojewodztwa.js` (numerowanie zapytań)
- Sprawdzone w przeglądarce (jasny i ciemny motyw); BDL na żywo
  niedostępny z kontenera
- `DECISIONS.md`: D-057

Testy: 333 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap52_20260929.zip

## ETAP 53 — MPZP: porównanie działek
Data: 2026-09-29
Status: zamknięty

- `/mpzp/porownanie` (GET z listą `id`, do 4), szablon `porownanie.html`
- Błąd ULDK/planu jednej działki nie psuje pozostałych kolumn
- Sprawdzone w przeglądarce (trzy działki o różnym kształcie)
- `DECISIONS.md`: D-058

Testy: 335 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap53_20260929.zip

## ETAP 54 — Fiszki: import z pliku
Data: 2026-09-29
Status: zamknięty

- `importer.wczytaj`, `POST /fiszki/<pdf_id>/import`
- Strona 0 obsłużona w: liście fiszek, powtórce, quizie, wyszukiwarce,
  najtrudniejszych, druku, eksporcie Anki
- Sprawdzone w przeglądarce (import z Anki z błędnym wierszem, powtórka)
- `DECISIONS.md`: D-059

Testy: 341 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap54_20260929.zip

## ETAP 55 — Dostępność: punkty usług z CSV
Data: 2026-09-29
Status: zamknięty

- `model.punkty_z_csv`, `POST /dostepnosc/punkty-z-pliku`, pole `nazwy`
  w `/dostepnosc/z-punktow`
- Sprawdzone w przeglądarce: plik z błędnym wierszem, połączenie z
  istniejącymi szkołami, nazwy w tabeli
- `DECISIONS.md`: D-060

Testy: 344 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap55_20260929.zip

## ETAP 56 — Porządki w kodzie
Data: 2026-09-29
Status: zamknięty

- mpzp/routes.py 730 → 490 linii (+ `trasy_narzedzia.py`,
  `trasy_zapisane.py`, `liczby.py`); fiszki/routes.py 640 → 314
  (+ `trasy_nauka.py`, `trasy_wymiana.py`); atlas/routes.py 614 → 492
  (+ `trasy_druk.py`)
- pyflakes: czysto (poza celowym `from . import trasy_*`); wszystkie
  pliki JS przechodzą `node --check`; wszystkie strony odpowiadają 200
- Funkcje bez zmian — pilnują tego testy (344)
- `DECISIONS.md`: D-061

Testy: 344 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap56_20260929.zip

## ETAP 57 — Osiedle: moduł, rysowanie, bilans terenu
Data: 2026-09-29
Status: zamknięty

- `osiedle/`: `bilans.py`, `baza.py`, `routes.py` (koncepcje: lista,
  nowa, odczyt, zapis, usunięcie, GeoJSON), szablon, `osiedle.js`,
  `osiedle.css`
- Leaflet.draw po polsku; ikony narzędzi przywrócone mimo wspólnego
  stylu przycisków mapy
- Sprawdzone w przeglądarce: rysowanie prostokątów, zmiana funkcji,
  zapis i odczyt po przeładowaniu (jasny i ciemny motyw)
- `DECISIONS.md`: D-063

Testy: 353 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap57_20260929.zip

## ETAP 58 — Osiedle: wskaźniki zabudowy i zgodność z planem
Data: 2026-09-29
Status: zamknięty

- `osiedle/wskazniki.py` (parametry terenów, wskaźniki, ustalenia planu,
  zgodność); `bilans()` przyjmuje ustawienia koncepcji
- Zapis PUT waliduje rysunek i ustawienia razem (brakującą część bierze
  z bazy)
- Panel: pola parametrów terenu zależne od funkcji, tabela wskaźników
  z granicami planu
- Sprawdzone w przeglądarce: liczby zgodne z ręcznym rachunkiem,
  zapis parametrów i ustaleń po przeładowaniu (jasny i ciemny motyw)
- `DECISIONS.md`: D-064

## ETAP 59 — Osiedle: program (mieszkańcy, parkingi, usługi)
Data: 2026-09-29
Status: zamknięty

- `osiedle/program.py` (założenia z walidacją, program); wynik w
  `bilans()["program"]`, założenia w `ustawienia.program`
- Panel: tabela programu, ostrzeżenie o brakujących miejscach
  postojowych, rozwijane założenia
- Sprawdzone w przeglądarce: liczby zgodne z ręcznym rachunkiem, zmiana
  założenia przelicza program, zapis po przeładowaniu
- `DECISIONS.md`: D-065

## ETAP 60 — Osiedle: warianty, raport i eksport
Data: 2026-09-29
Status: zamknięty

- `osiedle/rysunek_svg.py` (szkic, wspólna skala), `osiedle/trasy_druk.py`
  (raport, SVG, porównanie), szablony `raport.html`, `porownanie.html`,
  `_liczby.html`
- Sprawdzone w przeglądarce: raport (jasny i ciemny motyw, podgląd
  druku), porównanie dwóch wariantów
- Moduł Osiedle ukończony (ETAPy 57–60)
- `DECISIONS.md`: D-066

## ETAP 61 — Przepisy: moduł, biblioteka aktów, wyszukiwarka
Data: 2026-09-29
Status: zamknięty

- `przepisy/`: `tekst.py` (PDF → strony → jednostki), `baza.py` (akty,
  jednostki, FTS5, wyszukiwanie, podgląd), `routes.py`, szablony
  `index.html`, `akt.html`, `przepisy.js`, `akt.js`, `przepisy.css`
- Test z prawdziwym PDF-em (minimalny PDF budowany w teście) i z
  PDF-em ustawy wydrukowanym przez przeglądarkę
- Sprawdzone w przeglądarce: wgranie PDF, spis i filtr, wyszukiwanie
  „intensywnosc zabudowy dzialki”, „art. 2” → skok do artykułu
- `DECISIONS.md`: D-067

## ETAP 62 — Przepisy: pytania z cytatami i kotwicą w źródle
Data: 2026-09-29
Status: zamknięty

- `przepisy/pytania.py` (kandydaci, fragmenty dla modelu, sprawdzenie
  cytatów i liczb), tabela `pytania`, trasy POST `/przepisy/pytanie` i
  DELETE `/przepisy/pytania/<id>`, `pytania.js`
- Sprawdzone w przeglądarce z podstawionym modelem: odpowiedź z dwoma
  cytatami (trzeci, zmyślony — odrzucony), odrzucenie odpowiedzi bez
  cytatów, historia po przeładowaniu (jasny i ciemny motyw)
- Nie sprawdzone tutaj: prawdziwe Gemini (brak klucza w tym środowisku)
- `DECISIONS.md`: D-068

## ETAP 63 — Atlas: Raport gminy
Data: 2026-09-29
Status: zamknięty

- `atlas/raport.py` (podsumowanie wskaźnika, fakty do opisu),
  `atlas/trasy_raport.py` (wybór, gminy województwa, zestaw, raport,
  opis), tabela `raport_wskazniki`, szablony `raport_wybor.html`,
  `raport_gminy.html`, skrypty `raport_wybor.js`, `raport_gminy.js`
- Sprawdzone w przeglądarce z podstawionymi danymi BDL: układanie
  zestawu (także wskaźnik względny), wybór gminy, raport (jasny i
  ciemny motyw)
- Nie sprawdzone tutaj: prawdziwe API BDL (sieć zablokowana), w tym
  nowe zapytanie o listę gmin — do sprawdzenia u autora
- `DECISIONS.md`: D-069

## ETAP 64 — MPZP: Kronika zmian
Data: 2026-09-29
Status: zamknięty

- `dane/ortofoto.py` (GetCapabilities → lata), `mpzp/trasy_kronika.py`,
  szablon `kronika.html`, `kronika.js`, style w `mpzp.css`
- Sprawdzone w przeglądarce z atrapą usługi WMS (kafelki z rokiem z
  parametru TIME): suwak, przyciski, dwa lata obok siebie, granica
  działki (jasny i ciemny motyw)
- Nie sprawdzone tutaj: prawdziwa usługa GUGiK (sieć zablokowana) —
  do sprawdzenia u autora; jeśli lat nie ma, komunikat wskazuje
  ustawienie ORTO_ARCHIWALNA_WMS
- `DECISIONS.md`: D-070

## ETAP 65 — Teren: inwentaryzacja w terenie
Data: 2026-09-29
Status: zamknięty

- `teren/`: `projekt.py` (pola, wzory, sprawdzanie pliku z telefonu),
  `baza.py` (projekty, punkty, zdjęcia), `routes.py`, szablony
  `index.html`, `projekt.html`, `telefon.html` (samodzielny formularz),
  `teren.js`, `teren.css`
- Sprawdzone w przeglądarce cały obieg: projekt → pobranie formularza →
  otwarcie pliku lokalnie w emulacji telefonu z GPS → 2 punkty (jeden ze
  zdjęciem) → przeładowanie (punkty zostają) → eksport → import (2
  dodane) → ponowny import (2 pominięte) → mapa, legenda, dymek, tabela
  (jasny i ciemny motyw)
- Nie sprawdzone tutaj: prawdziwy telefon (otwieranie pliku HTML z
  pamięci telefonu i zgoda na GPS zależą od przeglądarki) — do
  sprawdzenia u autora
- `DECISIONS.md`: D-071

## ETAP 66 — Przegląd i porządki po nowych modułach
Data: 2026-09-29
Status: zamknięty

- pyflakes na całym projekcie: czysto (poza celowymi importami plików z
  trasami), `node --check` na wszystkich skryptach: czysto
- Błąd utraty rysunku w Osiedlu odtworzony w przeglądarce (koncepcja A:
  0 obiektów zamiast 1) i naprawiony (A: 1 obiekt)
- Szerokość stron sprawdzona w trzech rozmiarach okna
- Testy: jeden nowy przypadek (historia pytań po usunięciu aktu)
- `DECISIONS.md`: D-072

## ETAP 67 — Osiedle: punkty z Terenu na mapie koncepcji
Data: 2026-09-29
Status: zamknięty

- `osiedle.js`: warstwa punktów terenowych, `ustawienia.teren_projekt`
  (walidacja w `osiedle/routes.py`), `teren/routes.py: lista_projektow`
- Sprawdzone w przeglądarce: 8 punktów z importu, dymek, wybór po
  przeładowaniu zachowany
- `DECISIONS.md`: D-073

## ETAP 68 — Przepisy → Fiszki
Data: 2026-09-29
Status: zamknięty

- `fiszki/zewnetrzne.py`, trasa POST `/przepisy/pytania/<id>/fiszka`,
  `tekst.teksty_stron`, `pytania.strona_cytatu`, formularz w `pytania.js`
- Sprawdzone w przeglądarce na PDF-ie ustawy: pytanie → „+ Fiszka” →
  fiszka ze stroną 2 → w Fiszkach „Pokaż w źródle” podświetla cytat
- Znaleziony przy okazji i naprawiony błąd podglądu PDF w fiszkach
  (lewy brzeg strony poza obszarem przewijania)
- `DECISIONS.md`: D-074

## ETAP 69 — Teren: raport do druku
Data: 2026-09-29
Status: zamknięty

- `teren/raport.py` (numeracja, zestawienie, mapa SVG), trasa
  `/teren/projekty/<id>/raport`, szablon `raport.html`, style w `teren.css`
- Sprawdzone w przeglądarce: 12 punktów, 8 zdjęć JPEG, kolor wg „stan”,
  jasny i ciemny motyw, wydruk do PDF (4 strony A4)
- `DECISIONS.md`: D-075

## ETAP 70 — Teren: kolory dobry–zły
Data: 2026-09-29
Status: zamknięty

- `projekt.py` (klucz `skala`, wzory), `raport.py: kolor_skali`,
  `teren.js` (kolory mapy, pole w edytorze)
- Sprawdzone w przeglądarce: mapa projektu, raport, edytor (jasny i
  ciemny motyw)
- Projekty utworzone przed tym ETAPem: skalę zaznacza się w edytorze pól
- `DECISIONS.md`: D-076

## ETAP 71 — Aktualizacja jednym poleceniem
Data: 2026-09-29
Status: zamknięty

- `aktualizacja.py` + `aktualizuj.sh`; `.pliki_wersji` w `.gitignore`;
  opis ikony bez listy modułów
- Sprawdzone na prawdziwej instalacji w katalogu tymczasowym: ZIP z
  Pobranych, kopia zapasowa, dane i `.env` nietknięte, stary plik
  usunięty, zależności przez `.venv/bin/pip`, suma dla `uruchom.sh`
- `DECISIONS.md`: D-077

## ETAP 72 — Teren: poprawianie punktów
Data: 2026-09-29
Status: zamknięty

- `projekt.sprawdz_poprawke`, `baza.popraw_punkt` + dopisywanie kolumn,
  trasa PUT, panel „Popraw punkt” w `teren.js`
- Sprawdzone w przeglądarce: zmiana stanu i uwag, przeciągnięcie o 23 m,
  zapis, oznaczenie ręczne (jasny i ciemny motyw); test starej bazy
- `DECISIONS.md`: D-078

## ETAP 73 — Atlas: mapa położenia w raporcie gminy
Data: 2026-09-29
Status: zamknięty

- `mapa_svg.polozenie_gminy_svg`, trasa `.../mapa.svg`, nagłówek raportu
  z mapą, obsługa błędu w `raport_gminy.js`
- Sprawdzone w przeglądarce z podstawionymi granicami i z błędem PRG
- Nie sprawdzone tutaj: prawdziwe granice PRG (sieć zablokowana)
- `DECISIONS.md`: D-079

## ETAP 74 — Fiszki na telefon bez internetu
Data: 2026-09-29
Status: zamknięty

- `fiszki/telefon.py` (eksport, odczyt i zastosowanie wyników), tabele
  `ustawienia`, `powtorki_z_telefonu`, szablon `telefon.html`, sekcja na
  stronie Fiszek
- Sprawdzone w przeglądarce cały obieg: pobranie (temat) → plik otwarty
  lokalnie w emulacji telefonu → 4 oceny (fiszka „nie umiem” wraca w
  sesji) → przeładowanie (stan zachowany) → eksport → import (4) →
  ponowny import (0 nowych, 4 pominięte)
- `DECISIONS.md`: D-080; D-081 — zgoda autora na samodzielny wybór ETAPów

## ETAP 75 — Osiedle: obszar z działek
Data: 2026-09-29
Status: zamknięty

- trasa `obszar-z-dzialek` w `osiedle/routes.py`, pole w panelu, obsługa w
  `osiedle.js`
- Sprawdzone w przeglądarce z podstawionym ULDK: dwie działki → obszar
  15 000 m², nieznana działka → komunikat
- Nie sprawdzone tutaj: prawdziwe ULDK (sieć zablokowana)
- `DECISIONS.md`: D-082

## ETAP 76 — Atlas: porównanie gmin i CSV w raporcie
Data: 2026-09-29
Status: zamknięty

- `trasy_raport.py` (`?porownaj=`, trasa `.csv`), kolumny w szablonie,
  wybór gminy i pobieranie drugiej gminy w `raport_gminy.js`
- Sprawdzone w przeglądarce z podstawionym BDL (jasny i ciemny motyw),
  pobranie CSV
- `DECISIONS.md`: D-083

## ETAP 77 — Przepisy: porównanie wersji aktu
Data: 2026-09-29
Status: zamknięty

- `przepisy/porownanie.py`, trasa `/przepisy/porownanie`, szablon
  `porownanie.html`
- Sprawdzone w przeglądarce na dwóch PDF-ach ustawy (usunięty art. 2,
  zmieniony art. 15, dodany art. 15b)
- `DECISIONS.md`: D-084

## ETAP 78 — Dostępność: gdzie nowa placówka
Data: 2026-09-29
Status: zamknięty

- `dostepnosc/lokalizacja.py`, trasa `/dostepnosc/plik/<nazwa>/lokalizacja`,
  blok w panelu wyników, znaczniki w `dostepnosc.js`
- Sprawdzone w przeglądarce na pliku przykładowym (przystanki, 15 min:
  48% → 62% mieszkańców z 3 placówkami)
- `DECISIONS.md`: D-085

## ETAP 79 — Przegląd po ETAPach 67–78
Data: 2026-09-30
Status: zamknięty

- 24 strony × 3 szerokości okna w przeglądarce: bez błędów JS, bez
  poziomego przewijania po poprawkach
- `DECISIONS.md`: D-086

## ETAP 80 — MPZP: karta działki
Data: 2026-09-30
Status: zamknięty

- `mpzp/karta.py` (położenie, prostokąt EPSG:3857, adres GetMap, obrys),
  rozbudowany szablon `raport.html`, link „Karta działki” w panelu
- Sprawdzone w przeglądarce z atrapami WMS (obecna i archiwalna 1997)
- Nie sprawdzone tutaj: prawdziwe obrazy GUGiK i dopasowanie obrysu na
  prawdziwym zdjęciu (sieć zablokowana)
- `DECISIONS.md`: D-087

## ETAP 81 — Osiedle: plan miejscowy pod rysunkiem
Data: 2026-09-30
Status: zamknięty

- nakładki WMS w `osiedle.js`, adres trasy MPZP w szablonie
- Sprawdzone w przeglądarce: nakładki w przełączniku, zapamiętanie po
  przeładowaniu, zapytania do usługi GUGiK wysyłane
- Nie sprawdzone tutaj: obraz planów (sieć zablokowana)
- `DECISIONS.md`: D-088

## ETAP 82 — Przepisy: fiszki z artykułu
Data: 2026-09-30
Status: zamknięty

- `gemini.zaproponuj_fiszki_z_przepisu`, `pytania.sprawdz_propozycje_fiszek`,
  trasy `/przepisy/jednostki/<id>/szkice-fiszek` i `/fiszki`, panel w
  `akt.js`
- Sprawdzone w przeglądarce z podstawionym modelem na PDF-ie ustawy
  (2 propozycje, 1 odrzucona, 1 zapisana)
- `DECISIONS.md`: D-089

## ETAP 83 — Teren: mapa offline w formularzu
Data: 2026-09-30
Status: zamknięty

- obszar prac (trasa PUT, karta na stronie projektu), podkład w
  formularzu, płótno mapy w `telefon.html`
- Sprawdzone w przeglądarce cały obieg z podstawionym obrazem: za duży
  obszar odrzucony, obszar 1269 × 815 m, formularz 56 kB, mapa na
  „telefonie” z punktem i pozycją
- Znaleziony i naprawiony błąd GPS w formularzu (śledzenie po zapisie)
- Nie sprawdzone tutaj: prawdziwy obraz GUGiK (sieć zablokowana)
- `DECISIONS.md`: D-090

## ETAP 84 — Atlas: wskaźnik złożony
Data: 2026-09-30
Status: zamknięty

- `atlas/zlozony.py` (unitaryzacja zerowana, standaryzacja, średnia
  ważona), `atlas/trasy_zlozony.py` (strona, wynik, kartogram SVG, CSV),
  `zlozony.html`, `zlozony.js`
- Sprawdzone w przeglądarce z podstawionym BDL (30 gmin, 3 składowe,
  destymulanta, waga 2, 3 gminy pominięte): ranking, kartogram, szerokość
  telefonu 390 px bez poziomego przewijania strony
- `DECISIONS.md`: D-091

## ETAP 85 — Dostępność: zasięg z punktu
Data: 2026-09-30
Status: zamknięty

- `dostepnosc/zasieg.py`, trasa `/dostepnosc/plik/<nazwa>/zasieg`,
  blok „Zasięg z punktu” (okręgi na mapie, tabela)
- Sprawdzone w przeglądarce na pliku przykładowym: klik w trybie rysuje
  okręgi i nie otwiera okienka komórki, zwykły klik — jak dawniej;
  390 px bez poziomego przewijania (poprawiona szerokość tabeli)
- `DECISIONS.md`: D-092

## ETAP 86 — Strona główna: kalendarz nauki i pomoc
Data: 2026-09-30
Status: zamknięty

- `fiszki.routes.terminy`, `teren.routes.terminy`, kolumna
  `projekty.termin` z trasą `/teren/projekty/<id>/termin` i kartą „Termin
  w terenie”; sekcja „Najbliższe terminy” na stronie głównej
- strona `/pomoc` („jak zrobić…” dla każdego modułu) i link w menu;
  opisy sprawdzone z etykietami w kodzie
- Sprawdzone w przeglądarce: kalendarz z 4 terminami (dziś, za 2, 12 i 30
  dni), 390 px bez poziomego przewijania (wpis układa się w pionie)
- `DECISIONS.md`: D-093, D-094

## ETAP 87 — Opis projektu do portfolio
Data: 2026-09-30
Status: zamknięty

- `docs/PORTFOLIO.md`: moduły i umiejętności, zasady projektu, jak
  powstał, liczby, lista zrzutów do zrobienia na prawdziwych danych,
  streszczenie po angielsku; katalog `docs/portfolio/` na zrzuty
- Bez zmian w kodzie; testy bez zmian (448)
- `DECISIONS.md`: D-095

## ETAP 88 — Przepisy: akty z Dziennika Ustaw przez API Sejmu
Data: 2026-09-30
Status: zamknięty

- `dane/sejm.py` (wyszukiwanie po tytule, pobieranie urzędowego PDF),
  trasy `/przepisy/sejm/szukaj` i `/przepisy/sejm/pobierz`, blok „Pobierz
  z Dziennika Ustaw”, `sejm.js`; wspólna funkcja `_zapisz_akt` dla PDF
  wgranego i pobranego
- Format odpowiedzi API ustalony z dokumentacji i kodu kilku otwartych
  projektów (tu API jest zablokowane przez sieć); kod nie zakłada obecności
  pól
- Sprawdzone w przeglądarce z podstawionym API i prawdziwym PDF-em ustawy:
  3 wyniki, oznaczony tekst jednolity, pobranie → strona aktu z artykułami
- Nie sprawdzone tutaj: prawdziwe API Sejmu
- `DECISIONS.md`: D-096

## ETAP 89 — MPZP: plan ogólny gminy
Data: 2026-09-30
Status: zamknięty

- `mpzp/uslugi.py` (inne usługi WMS GUGiK: warstwy i formaty z
  GetCapabilities, GetFeatureInfo w GML, tekście albo HTML), trasy
  `/mpzp/usluga/<klucz>/warstwa` i `/punkt`
- MPZP: nakładka „Plany ogólne gmin (strefy)” i rozwijana sekcja „Plan
  ogólny gminy” w panelu działki; Osiedle: nakładka „Plan ogólny gminy”
  (przebudowane zapamiętywanie nakładek)
- Adres usługi potwierdzony w komunikatach GUGiK; nazw warstw nie
  wpisujemy — przychodzą z GetCapabilities
- Sprawdzone w przeglądarce z podstawioną usługą; prawdziwa usługa
  niedostępna z tego środowiska
- `DECISIONS.md`: D-097

## ETAP 90 — MPZP: ceny transakcyjne z Rejestru Cen Nieruchomości
Data: 2026-09-30
Status: zamknięty

- usługa „ceny” w `mpzp/uslugi.py` (WMS RCN GUGiK), nakładka „Ceny
  transakcyjne (RCN)” i sekcja w panelu działki
- Naprawiony błąd znaleziony testem: tabela HTML z nagłówkiem i dwiema
  kolumnami była czytana jak pary „nazwa | wartość”
- Sprawdzone w przeglądarce z podstawioną usługą; prawdziwa usługa
  niedostępna z tego środowiska
- `DECISIONS.md`: D-098

## ETAP 91 — Atlas: metoda Hellwiga we wskaźniku złożonym
Data: 2026-09-30
Status: zamknięty

- `atlas/zlozony.py`: metoda „hellwig” (standaryzacja, wzorzec rozwoju,
  ważona odległość, d0 = średnia + 2σ); przypis kartogramu bez „średniej
  ważonej” dla tej metody
- Test zgodny z obliczeniem ręcznym (m = 0,24; 0,62; 1) i test wpływu wag
- Sprawdzone w przeglądarce (wybór metody, ranking, kartogram)
- `DECISIONS.md`: D-099

## ETAP 92 — Atlas: ekstrapolacja trendu w raporcie gminy
Data: 2026-09-30
Status: zamknięty

- `raport.prognoza_trendu` (trend liniowy MNK z ostatnich 10 lat, min.
  5 punktów, R², wartość za 5 lat) w podsumowaniu każdego wskaźnika;
  podpis pod wykresem trendu, przypis z objaśnieniem
- Poprawka po sprawdzeniu w przeglądarce: wartość zaokrąglona do 3 cyfr
  znaczących (było „~1 109 923,91”)
- Ekstrapolacja nie trafia do faktów dla Gemini (model nie dostaje
  prognoz do opisu)
- `DECISIONS.md`: D-100

## ETAP 93 — Teren: tryb ankiety i wielokrotny wybór
Data: 2026-09-30
Status: zamknięty

- rodzaj projektu (`projekty.rodzaj`: inwentaryzacja / ankieta), wzór
  „Ankieta: przestrzeń publiczna”, przełącznik na stronie projektu
- nowy typ pola „wiele” (wielokrotny wybór; wartość = lista opcji w ich
  kolejności): sprawdzanie pliku, formularz na telefon, poprawka punktu,
  zestawienie (procent odpowiedzi, suma > 100%), CSV („a; b”)
- formularz ankiety: najpierw pytania, miejsce i zdjęcie w rozwijanej
  sekcji, bez pytania o brak położenia, bez mapy (chyba że jest obszar
  prac); raport „Wyniki ankiety”, bez mapy przy braku położeń
- Sprawdzone w przeglądarce: odpowiedź na „telefonie” (390 px) → eksport
  → import → raport → poprawka z dodaniem opcji
- `DECISIONS.md`: D-101

## ETAP 94 — Osiedle: odległości od granicy i strefa możliwego cienia
Data: 2026-09-30
Status: zamknięty

- `osiedle/cien.py`: położenie słońca (wzory astronomiczne, czas
  słoneczny 9–15, równonoc i przesilenia), wysokość = kondygnacje × 3 m,
  ślad cienia jako suma Minkowskiego terenu z wektorem cienia, tereny MN,
  MW i ZP w strefie, odległość terenów zabudowy od granicy obszaru
- trasa `/osiedle/koncepcje/<id>/cien`, karta „Odległości i cień”
  (strefa na mapie, tabela, klik → zaznaczenie terenu, ostrzeżenie przy
  terenie sięgającym granicy)
- Test znalazł błąd w samym teście (odstęp 20 m > cień 19 m w równonoc) —
  kod liczył poprawnie
- `DECISIONS.md`: D-102

## ETAP 95 — Fiszki: tematy jako tagi w eksporcie Anki i eksport jednego tematu
Data: 2026-09-30
Status: zamknięty

- Przy przeglądzie okazało się, że eksport do Anki już istniał (plik
  tekstowy z nagłówkami, linki na stronach, testy) — punkt z listy
  pomysłów był nietrafiony. Uzupełnione to, czego brakowało:
- kolumna tagów (`#tags column:4`) z tematami fiszek (spacje → „_”),
  eksport jednego tematu (`/fiszki/eksport.txt?temat=`) i link „Anki”
  przy temacie; akapit w Pomocy
- Test „eksport → import” potwierdza, że własny import czyta nowy plik
- `DECISIONS.md`: D-103

## ETAP 96 — Przegląd kodu 79–95 i testy wydajności
Data: 2026-09-30
Status: zamknięty

- pyflakes na wszystkich plikach zmienionych od ETAPu 78: czysto (poza
  zamierzonymi importami rejestrującymi trasy); usunięty zbędny import w
  teście MPZP
- 16 głównych stron w szerokości 390 i 1300 px: bez błędów JS, bez
  przewijania w poziomie
- Pomiary na dużych danych (ten kontener):

  | Operacja | Czas |
  |---|---|
  | Dostępność: zasięg z punktu, 20 tys. komórek | 0,05 s |
  | Dostępność: szybki model, 5 punktów, 20 tys. komórek | 0,18 s |
  | Dostępność: gdzie nowa placówka, 20 tys. komórek, 15 / 30 min | 3,5 → 2,4 s / 8,4 → 5,5 s |
  | Atlas: wskaźnik złożony, 300 gmin × 12 składowych (3 metody) | 0,01 s |
  | Przepisy: zapis aktu z 3000 artykułami / 20 wyszukiwań | 0,84 s / 0,49 s |
  | Osiedle: cień, 149 terenów (równonoc / zima) | 0,52 / 0,62 s |
  | Teren: import / raport 3000 punktów | 0,22 / 0,25 s |

- „Gdzie nowa placówka”: aktualizacja punktów kandydatów przyrostowo
  zamiast od nowa w każdej rundzie i porównanie odległości przed
  arcsinusem; wynik identyczny ze starą wersją (sprawdzone na 16
  zestawach). Resztę czasu zajmuje przejście po ok. 1,8 mln par
  sąsiadów — dalsze przyspieszenie wymagałoby wektoryzacji (numpy)
- `DECISIONS.md`: D-104

## ETAP 97 — Automatyczna kopia zapasowa przy starcie
Data: 2026-09-30
Status: zamknięty

- `kopia.kopia_automatyczna` (co N dni, domyślnie 7; 5 najnowszych
  `warsztat_auto_*.zip`; zapis przez plik `.tmp`; kopii ręcznych nie
  rusza) i `ostatnia_kopia_automatyczna`; wywołanie w tle przy
  `python app.py`; ustawienia `AUTO_KOPIA_DNI`, `AUTO_KOPIA_FOLDER`
  (`.env.example`)
- strona główna: data i ścieżka ostatniej kopii automatycznej; Pomoc
- Sprawdzone: prawdziwe uruchomienie `python app.py` zrobiło kopię w
  podanym folderze
- `DECISIONS.md`: D-105

## ETAP 98 — Pomoc: uzupełnienie o funkcje z ETAPów 88–97
Data: 2026-09-30
Status: zamknięty

- strona Pomoc: Dziennik Ustaw w Przepisach, plan ogólny i ceny RCN w
  MPZP, metoda Hellwiga i przedłużenie trendu w Atlasie, ankieta i
  wielokrotny wybór w Terenie, odległości i cień w Osiedlu (kopia
  automatyczna była już dopisana w ETAPie 97)
- test pilnujący, że Pomoc wymienia te funkcje (etykiety jak w
  interfejsie)
- `DECISIONS.md`: D-106

## ETAP 99 — Teren: paski wykresu w zestawieniu raportu
Data: 2026-09-30
Status: zamknięty

- `raport.zestawienie`: kolor paska dla każdej wartości (skala: od
  zielonego do czerwonego, inaczej jeden kolor); w raporcie kolumna z
  paskiem długości procentu, drukowana w kolorze
- poprawki po sprawdzeniu w przeglądarce: bez kreski przy 0%, szersze
  kolumny zestawienia (etykiety się nie łamią)
- `DECISIONS.md`: D-107

## ETAP 100 — Osiedle: odległości i cień w raporcie do druku
Data: 2026-09-30
Status: zamknięty

- raport koncepcji: sekcja „Odległości i cień” (dzień z listy, domyślnie
  równonoc, „bez analizy cienia”), strefa cienia i numery terenów na
  szkicu, pozycja w legendzie; lista wyboru ukryta przy druku
- `szkic_svg(…, strefa_cienia, numery)` — porównanie wariantów bez zmian;
  `_sciezka` rysuje też wieloboki z kolekcji geometrii
- Sprawdzone w przeglądarce (także zmiana dnia i wydruk do PDF)
- `DECISIONS.md`: D-108

## ETAP 101 — Przepisy: sprawdzanie, czy jest nowszy tekst jednolity
Data: 2026-09-30
Status: zamknięty

- `sejm.adres_i_przedmiot` (adres Dz.U. i przedmiot ustawy z nazwy aktu:
  „o …” albo np. „Prawo budowlane”; obwieszczenia i ustawy) i
  `sejm.nowsze_teksty_jednolite` (wyszukiwanie po przedmiocie, tylko
  obwieszczenia z tekstem jednolitym tej samej ustawy, nowsze niż akt)
- trasa `/przepisy/akty/<id>/aktualnosc`, przycisk „Czy jest nowszy
  tekst?” na stronie aktu z Dziennika Ustaw, pobranie jednym kliknięciem;
  akapit w Pomocy
- Sprawdzone w przeglądarce z podstawionym API (także 390 px)
- `DECISIONS.md`: D-109

## ETAP 102 — Kalendarz: eksport terminów do pliku .ics
Data: 2026-09-30
Status: zamknięty

- `kalendarz.py` (RFC 5545: wydarzenia całodniowe, CRLF, łamanie linii po
  75 bajtach bez cięcia znaków UTF-8, escapowanie, stały UID), trasa
  `/kalendarz.ics` ze wszystkimi nadchodzącymi terminami (wspólna funkcja
  `wszystkie_terminy` ze stroną główną), link „Dodaj do kalendarza (.ics)”,
  akapit w Pomocy
- Poprawka przy okazji (znaleziona przez ostrzeżenie w testach):
  niezamknięty iterator `os.scandir` w kopii automatycznej (ETAP 97)
- `DECISIONS.md`: D-110

## ETAP 103 — Ceny: nowy moduł — ceny mieszkań z GUS
Data: 2026-09-30
Status: zamknięty

- `dane/bdl.py`: poziom powiatu (`powiaty_wojewodztwa`,
  `wartosci_dla_powiatow`, `teryt_powiatu`, wyszukiwanie zmiennych dla
  danego poziomu)
- `ceny/`: `analiza.py` (zmiany r/r, w 5 lat, od początku, średnie roczne
  tempo, ranking z miejscami i medianą, miasta na prawach powiatu po TERYT
  ≥ 61), `baza.py` (wybrany wskaźnik, cache BDL 30 dni), `routes.py`,
  strona z wykresem SVG, tabelą, rankingiem i CSV
- rejestracja: menu, karta na stronie głównej („Osiem narzędzi”), Pomoc,
  README, CLAUDE.md (lista modułów), portfolio, instrukcja kopii
- Poprawki po sprawdzeniu w przeglądarce: układ listy powiatów, „ładne”
  podziałki osi, podświetlenie wybranych miast w rankingu
- Nie sprawdzone tutaj: prawdziwe API BDL (zablokowane) — nazwy wskaźników
  GUS i dostępne lata trzeba zobaczyć u siebie
- `DECISIONS.md`: D-111

## ETAP 104 — Ceny: transakcje z Rejestru Cen Nieruchomości
Data: 2026-09-30
Status: zamknięty

- `ceny/rcn.py`: czytanie GeoPackage RCN przez sqlite3 (tabela
  `transakcje_lokale`, nazwy kolumn z kodu kilku otwartych projektów,
  sprawdzane w pliku), cena lokalu → nieruchomości → transakcji (tylko
  jednolokalowej), odrzucanie z licznikami, środek geometrii z nagłówka
  GeoPackage (koperta albo WKB) w PL-1992 → WGS84; statystyki (mediana i
  kwartyle za m², trend kwartalny, izby, histogram), punkty mapy z
  kwintylami
- `mpzp/uklady.py`: przeliczenie odwrotne PL-1992 → WGS84 (szeregi
  Krügera) z testem „tam i z powrotem” w 5 miejscach Polski
- baza modułu: `rcn_pliki`, `rcn_lokale`; `ceny/trasy_rcn.py`: strona
  „Transakcje (RCN)”, import z katalogu Pobrane (tylko pliki z listy) albo
  wgranie, dane z filtrami, CSV, usuwanie
- Sprawdzone w przeglądarce na syntetycznym pliku (800 transakcji +
  12 niemieszkalnych); poprawione przepełnienie układu na 390 px
- Nie sprawdzone: prawdziwy plik z Geoportalu (nazwy kolumn i wartości
  rynku trzeba potwierdzić na pierwszym imporcie)
- `DECISIONS.md`: D-112

## ETAP 105 — Ceny: porównanie obszarów z mapy i raport do druku
Data: 2026-09-30
Status: zamknięty

- `ceny/rcn.py`: `sprawdz_obszar` (wielobok GeoJSON, naprawa samoprzecięć
  `make_valid`, tylko w Polsce), `w_obszarze`, `porownanie` (cały plik +
  obszary: liczba, mediana za m² z kwartylami, mediana powierzchni i ceny,
  różnica wobec całości w %, mediany w latach), `mapa_svg` (punkty w klasach
  ceny, obrysy obszarów z numerami, podziałka, strzałka północy)
- `ceny/baza.py`: tabela `rcn_obszary` (kasowana razem z plikiem)
- `ceny/trasy_rcn.py`: obszary POST/PUT/DELETE (limit 8), `dane` zwraca
  obszary i porównanie, `/ceny/transakcje/<id>/raport` z filtrami
- Strona transakcji: rysowanie Leaflet.draw (wielobok, prostokąt), lista
  obszarów ze zmianą nazwy i usuwaniem, tabela porównania, link „Raport do
  druku”; raport: dwie strony A4 (`@media print`)
- Sprawdzone w przeglądarce: rysowanie prostokąta myszą, tabela, raport
  1300 i 390 px, PDF A4; poprawione: ikony Leaflet.draw (jak w osiedlu),
  szerokość raportu na telefonie
- Testy: walidacja obszaru, porównanie na znanych liczbach, trasy obszarów
  i raportu (limit, 404, kaskada)
- `DECISIONS.md`: D-113

## ETAP 106 — Ceny: transakcje działek z Rejestru Cen Nieruchomości
Data: 2026-09-30
Status: zamknięty

- `ceny/rcn.py`: `czytaj_plik` czyta tabelę lokali i tabelę
  `transakcje_dzialki` (którakolwiek jest w pliku); `_dzialki`: cena
  działki, a bez niej cena transakcji na łączną powierzchnię jej działek
  (cena nieruchomości przy jednej działce), powierzchnia z obrysu w pliku
  (PL-1992, m²), odrzucone z powodami (udział, brak daty, brak obrysu,
  cena nie do rozdzielenia, wartości nierealne); słownikowe wartości RCN
  czytelnie („budownictwoMieszkaniowe” → „budownictwo mieszkaniowe”)
- `statystyki`: tabela grup — lokale według izb, działki według
  przeznaczenia w planie (10 najczęstszych + „pozostałe”); klucz `grupy`
- `ceny/baza.py`: tabela `rcn_dzialki`, kolumny `liczba_dzialek`,
  `odrzucone_dzialki` w `rcn_pliki` dopisywane do starych baz,
  `dzialki_rcn` z filtrami, `wartosci_pola` do list w filtrach
- Trasy: parametr `co=lokale|dzialki` w danych, CSV i raporcie; strona z
  przełącznikiem „Mieszkania | Działki”, filtry przeznaczenia i
  nieruchomości, komunikat dla plików zaimportowanych przed ETAPem 106
- Sprawdzone w przeglądarce na pliku syntetycznym (800 lokali, 400
  działek): 1400 i 390 px, raport działek
- Nazwy tabeli i kolumn działek z kodu dwóch otwartych projektów; jednostki
  `dzi_pow_ewid` się w nich różnią — dlatego powierzchnia z geometrii
- `DECISIONS.md`: D-114

## ETAP 107 — Ceny: podobne transakcje — wycena porównawcza
Data: 2026-09-30
Status: zamknięty

- `ceny/rcn.py`: `odleglosc_m` (przybliżenie równoodległościowe),
  `podobne` — transakcje w promieniu o powierzchni ± tolerancja, od
  najbliższych; mediana za m² z kwartylami, orientacyjna cena = mediana ×
  powierzchnia (i przedział z kwartyli), ostrzeżenie poniżej 5 transakcji,
  lista 30 najbliższych
- Trasa `/ceny/transakcje/<id>/podobne`: filtry strony (co, rynek, lata,
  izby / przeznaczenie, nieruchomość) + miejsce, powierzchnia, promień
  (250 m – 5 km), tolerancja (±10–50%); walidacja miejsca w Polsce
- Strona: karta „Podobne transakcje”, miejsce kliknięciem na mapie
  (znacznik, okrąg promienia, zaznaczone transakcje), przeliczenie po
  zmianie filtrów; klik kończący rysowanie obszaru nie przestawia miejsca
  (poprawione po sprawdzeniu w przeglądarce)
- Działa dla mieszkań i działek
- `DECISIONS.md`: D-115

## ETAP 108 — Ceny: mapa cen w heksagonach H3
Data: 2026-09-30
Status: zamknięty

- `ceny/rcn.py`: `heksagony` — mediana ceny za m² w komórkach H3
  (rozdzielczość 7, 8 albo 9), komórki z mniej niż 3/5/10 transakcjami
  ukryte (z licznikiem ukrytych komórek i transakcji w nich), progi kolorów
  z kwintyli median; `krawedz_h3_m` — średnia krawędź z biblioteki h3
- Trasa `/ceny/transakcje/<id>/heksagony` z filtrami strony (lokale i
  działki), walidacja rozdzielczości i minimum
- Strona: nad mapą widok „punkty | heksagony (mediana)”, wielkość
  heksagonu, minimum transakcji; legenda z długością krawędzi i ukrytymi
- Poprawione po sprawdzeniu: opisy wielkości heksagonów wpisałem z pamięci
  (460 m) — h3 4.5 podaje 531 m, teraz opis liczy biblioteka; polska
  odmiana w legendzie
- Bez nowej zależności: `h3==4.5.0` jest od D-015
- `DECISIONS.md`: D-116

## ETAP 109 — Ceny: ceny w okolicy działki (MPZP) i obszaru osiedla
Data: 2026-09-30
Status: zamknięty

- `ceny/rcn.py`: `ksztalt_okolicy` (punkt albo wielobok w Polsce),
  `prostokat_okolicy` (zakres do zapytania SQL), `okolica` — transakcje w
  odległości do promienia od kształtu (w lokalnym układzie metrycznym),
  liczba, w tym wewnątrz, mediana za m² z kwartylami, lata
- `ceny/baza.py`: `w_prostokacie` — transakcje wszystkich plików w
  prostokącie współrzędnych, pogrupowane po pliku
- Trasa POST `/ceny/okolica`: plik RCN z największą liczbą transakcji w
  zasięgu (pliki powiatów się nie mieszają), mieszkania i działki
- MPZP: pod wynikiem działki sekcja „Ceny w okolicy — Twój plik RCN”
  (pobierana po rozwinięciu, promień 250 m – 2 km)
- Osiedle: karta „Ceny w okolicy” wokół obszaru opracowania
- Sprawdzone w przeglądarce (MPZP z podstawioną odpowiedzią działki, bo
  ULDK jest tu zablokowane): poprawiona szerokość tabel na telefonie; w
  osiedlu kolumna panelu rozpychała stronę — `minmax(0, 1fr)`
- `DECISIONS.md`: D-117

## ETAP 110 — Ceny: trend cen w narysowanych obszarach
Data: 2026-10-01
Status: zamknięty

- `ceny/rcn.py`: `porownanie` podaje też liczbę transakcji w latach
  (`lata_liczba`); `wykres_lat_svg` — wykres liniowy median w latach do
  raportu (obszary w ich kolorach, cały plik przerywaną, pusty punkt przy
  mniej niż 5 transakcjach w roku), `_ladna_os` — „ładne” podziałki osi
- Strona transakcji: ten sam wykres pod tabelą porównania obszarów
- Raport do druku: wykres nad tabelą median w latach
- Sprawdzone w przeglądarce (strona, raport 1300/390 px); poszerzony
  prawy margines, bo ostatni rok dotykał krawędzi
- Kod wypchnięty w osobnym commicie przed wpisami w dokumentacji (błąd
  składni w skrypcie zamykającym ETAP) — wpisy dopisane commitem obok
- `DECISIONS.md`: D-118

## ETAP 111 — Ceny: zmiana cen w heksagonach między dwoma okresami
Data: 2026-10-01
Status: zamknięty

- `ceny/rcn.py`: `zmiana_heksagonow` — mediana ceny za m² w komórce H3 w
  okresie A i B, zmiana w %, tylko komórki z minimum transakcji w obu
  okresach; stałe klasy `PROGI_ZMIANY` / `KOLORY_ZMIANY` (niebieskie —
  spadek, szare — bez zmian, pomarańczowe — wzrost); mediana zmian
- Trasa `/ceny/transakcje/<id>/zmiana-heksagonow`: okresy A i B zastępują
  filtr lat, pozostałe filtry strony obowiązują; walidacja (A przed B,
  bez wspólnych lat)
- Strona: trzeci widok mapy „zmiana między okresami”, wybór okresów
  (domyślnie pierwsze i ostatnie dwa lata), legenda z klasami i opisem
- Sprawdzone w przeglądarce (1400 i 390 px, zły okres, powrót do punktów)
- `DECISIONS.md`: D-119

## ETAP 112 — Ceny: piętro lokalu (kondygnacja)
Data: 2026-10-01
Status: zamknięty

- `ceny/rcn.py`: `_kondygnacja` czyta `lok_nr_kond` (liczba albo
  „parter”; inne zapisy — brak danych), przedziały `PIETRA` (parter i
  niżej, 1–3, 4–9, 10+), `przedzial_pietra`, tabela `pietra` w statystykach
- `ceny/baza.py`: kolumna `kondygnacja` w `rcn_lokale` (dopisywana do
  starych baz), filtr `pietro` w `lokale_rcn`
- Filtr „Piętro” na stronie, w danych, CSV (kolumna `kondygnacja`),
  raporcie, podobnych transakcjach i heksagonach (wspólne `_filtry`)
- Tabela „Według piętra” na stronie i w raporcie; komunikat, gdy plik nie
  ma numerów kondygnacji (np. zaimportowany wcześniej)
- Nazwa kolumny z dwóch otwartych projektów; zapis wartości do
  potwierdzenia na prawdziwym pliku
- `DECISIONS.md`: D-120

## ETAP 113 — Ceny: karta wyceny porównawczej do druku
Data: 2026-10-01
Status: zamknięty

- Trasa `/ceny/transakcje/<id>/wycena` — te same parametry i liczby co
  `/podobne` (wspólne `_parametry_wyceny`, `_wynik_wyceny`)
- `ceny/templates/ceny/wycena.html`: parametry i filtry, kafelki (liczba,
  mediana za m² z przedziałem, cena orientacyjna), schemat SVG, tabela
  podobnych transakcji z piętrem (lokale) albo przeznaczeniem (działki),
  wprost „To nie jest operat szacunkowy” i opis metody
- `ceny/rcn.py`: `mapa_wyceny_svg` — okrąg promienia, miejsce, numery
  transakcji jak w tabeli, podziałka, strzałka północy; lista podobnych
  ma też `kondygnacja`
- Strona transakcji: przycisk „Karta wyceny do druku ↗” przy wyniku
- Sprawdzone w przeglądarce (1300 i 390 px, PDF A4): odległości na
  schemacie zgadzają się z tabelą
- `DECISIONS.md`: D-121

## ETAP 114 — Ceny: eksport GeoJSON do QGIS
Data: 2026-10-01
Status: zamknięty

- Trasy `/ceny/transakcje/<id>.geojson` (punkty, atrybuty jak w CSV;
  działki z przeznaczeniem i rodzajem nieruchomości, lokale z izbami i
  piętrem), `/heksagony.geojson` (wielokąty H3 z liczbą i medianą),
  `/obszary.geojson` (narysowane obszary ze statystykami porównania)
- Filtry strony obowiązują; GeoJSON wg RFC 7946 (WGS84, lon, lat),
  `application/geo+json`, nazwy plików z rodzajem i numerem pliku
- Strona: linki „Pobierz do QGIS” pod mapą, aktualizowane z filtrami i
  wielkością heksagonów
- Sprawdzone w przeglądarce: pobranie trzech plików, geometrie poprawne
  (shapely), 390 px
- `DECISIONS.md`: D-122

## ETAP 115 — Ceny w okolicy na karcie działki (MPZP) i w raporcie koncepcji (osiedle)
Data: 2026-10-01
Status: zamknięty

- Karta działki do druku (MPZP) i raport koncepcji (osiedle): sekcja
  „Ceny w okolicy” — mieszkania i działki do 500 m od działki / obszaru
  opracowania: liczba, mediana za m², przedział połowy transakcji, lata,
  źródło z nazwą i datą importu pliku
- Liczby z modułu ceny przez POST `/ceny/okolica` (D-117); raport podaje
  tylko geometrię (działka, obszar opracowania); bez zaimportowanego
  pliku albo bez obszaru sekcja jest ukryta
- Kod sekcji w dwóch raportach celowo osobno (bez wspólnego komponentu)
- Sprawdzone w przeglądarce (1300 i 390 px; MPZP z podstawioną działką,
  bo ULDK jest tu zablokowane): poprawiona szerokość tabeli na telefonie
  i rozmiar przypisów
- `DECISIONS.md`: D-123

## ETAP 116 — Ceny: dostępność cenowa mieszkań (m² za przeciętne wynagrodzenie)
Data: 2026-10-01
Status: zamknięty

- `ceny/analiza.py`: `dostepnosc` — z szeregów GUS ceny 1 m² i
  przeciętnego wynagrodzenia brutto, w latach z oboma: m² za jedno
  wynagrodzenie, wynagrodzeń na 50 m², zmiana od pierwszego wspólnego roku
- `ceny/routes.py`: drugi wybierany wskaźnik GUS (`wynagrodzenie`) przez
  tę samą wyszukiwarkę (`PUT /ceny/zmienna` z `rodzaj`), trasa
  `/ceny/dostepnosc/<powiat>` (409, gdy wskaźnik nie wybrany)
- Strona Cen: sekcja „5. Dostępność cenowa” — wybór wskaźnika
  wynagrodzenia, wykres m² za wynagrodzenie w latach, tabela dla wybranych
  miast, opis uproszczeń
- Sprawdzone w przeglądarce na podstawionym BDL (1300 i 390 px);
  prawdziwych nazw wskaźników wynagrodzeń tu nie widać (API zablokowane)
- `DECISIONS.md`: D-124

## ETAP 117 — Ceny: wydajność przy dużym pliku RCN (100 tys. lokali, 20 tys. działek)
Data: 2026-10-01
Status: zamknięty

- Pomiar na pliku syntetycznym 19 MB (100 000 lokali, 20 000 działek):
  import 5 s; strony i dane zwykle 0,2–1,4 s
- Błąd znaleziony pomiarem: mapa w raporcie rysowała WSZYSTKIE punkty
  (opis mówił „najwyżej 4000 najnowszych”) — raport 180,8 s i 8,8 MB;
  teraz te same 4000 najnowszych co mapa strony: 1,7 s i 0,37 MB
- `w_obszarze` i `okolica`: jedno wywołanie `shapely.contains_xy` dla
  wszystkich punktów zamiast obiektu `Point` na transakcję — dane z 3
  obszarami 5,1 → 1,4 s, okolica obszaru 2 km 1,4 → 0,56 s
- `dane`: lata z zapytania `GROUP BY rok` zamiast drugiego wczytania
  wszystkich transakcji — 1,8 → 1,2 s
- Bez nowej zależności (shapely 2.1 już jest; listy zamiast numpy)
- Testy: mapa raportu tylko najnowsze, `w_obszarze` wektorowo
- `DECISIONS.md`: D-125

## ETAP 118 — Przegląd kodu i wszystkich stron
Data: 2026-10-01
Status: zamknięty

- `narzedzia/przeglad_stron.py`: przegląd stron w przeglądarce — lista z
  tablicy tras Flaska (każda strona HTML bez parametrów) + strony z
  parametrami na danych testowych (projekt terenu, koncepcja, plik RCN z
  obszarem, raporty, karta wyceny); telefon 390 px ciemny i komputer
  1300 px jasny; zgłasza kody ≥ 400, błędy JS i przewijanie poziome;
  sieć zewnętrzna odcięta. Wynik: 61 stron, 0 problemów
- Lint (pyflakes) całego repozytorium: tylko celowe importy rejestrujące
  trasy (`noqa`); moduł ceny bez martwego kodu
- Testy bez ostrzeżeń: zamknięte pliki i odpowiedzi z plikami w trzech
  testach (ResourceWarning)
- Sprawdzone: aplikacja nie słucha na 0.0.0.0, brak `debug=True`;
  ochrona przed CSRF / DNS rebinding / clickjacking jest od wcześniej
  (`ochrona.py`)
- `DECISIONS.md`: D-126

## ETAP 119 — Dokumentacja: portfolio i README po rozbudowie modułu ceny
Data: 2026-10-01
Status: zamknięty

- `docs/PORTFOLIO.md`: wiersz modułu Ceny (RCN: transakcje mieszkań i
  działek, dzielnice, heksagony i zmiany cen, wycena porównawcza, ceny w
  okolicy, QGIS; dostępność cenowa z GUS), liczby policzone z repo
  (ETAP 119: 14 800 wierszy Pythona, 8 000 JS, 505 testów, 127 decyzji),
  dwa nowe zrzuty do zrobienia (mapa cen, karta wyceny), streszczenie
  angielskie
- README: dostępność cenowa w opisie modułu Ceny
- Pomoc była uzupełniana w każdym ETAPie 110–117 (sprawdzone: opisuje
  trend w obszarach, zmiany w heksagonach, piętro, kartę wyceny, QGIS,
  ceny w raportach, dostępność cenową)
- `DECISIONS.md`: D-127

## ETAP 120 — Przepisy: słowniczek definicji ustawowych
Data: 2026-10-01
Status: zamknięty

- `przepisy/slowniczek.py`: definicje z artykułów „Ilekroć w ustawie
  jest mowa o: N) pojęcie – należy przez to rozumieć …” (także „Użyte w
  ustawie określenia oznaczają”), z podpunktami a), b) w treści; skróty
  „zwany dalej „…””; sortowanie wg polskiego alfabetu bez zależności od
  locale systemu
- Strona aktu: rozwijany „Słowniczek — N pojęć” z wyszukiwarką i
  odnośnikiem do artykułu i punktu; trasa JSON `/akty/<id>/slowniczek`
- Pojęcia w formie z tekstu (bez odmiany — mogłaby zmienić sens)
- Sprawdzone na prawdziwym PDF ustawy (pypdf) w przeglądarce: 1300 i
  390 px, filtr, przejście do artykułu
- Pomoc: opis
- `DECISIONS.md`: D-128

## ETAP 121 — Przepisy: klikalne odesłania do artykułów
Data: 2026-10-01
Status: zamknięty

- `przepisy/odeslania.py`: „art. N ust. … pkt … lit. …” i „§ N” w
  treści → odnośnik do jednostki tego aktu z podglądem jej początku
  (`title`); bez odesłań do innych aktów („ustawy z dnia …”, „ustawy o
  …”, „ustawy – Prawo …”, „rozporządzenia Ministra …”, Kodeks,
  Konstytucja, dyrektywa), bez odesłania do samego siebie i nagłówków
  „Art. 15.”; tekst zabezpieczony (`markupsafe.escape`)
- Strona aktu: odnośniki podkreślone kropkami, artykuł docelowy
  obrysowany (`:target`), także po kliknięciu w słowniczku
- Błąd złapany w teście: „§ 3” nie było rozpoznawane (`\b` przed „§”) —
  zamiana na lookbehind
- `DECISIONS.md`: D-129

## ETAP 122 — Osiedle: eksport koncepcji do DXF (AutoCAD)
Data: 2026-10-01
Status: zamknięty

- `dane/dxf.py`: zapis DXF R12 (tekstowy, otwiera go każdy program CAD):
  warstwy z kolorami ACI, zamknięte polilinie, teksty; nazwy ASCII;
  współrzędne z dokładnością do 1 mm; bez nowej zależności
- `osiedle/dxf_koncepcji.py`: warstwa na funkcję terenu (OSIEDLE_MN …),
  OSIEDLE_OBSZAR, OSIEDLE_OPISY („MW 1” — numeracja jak w raporcie),
  otwory wieloboków jako osobne polilinie; PL-2000 (jedna strefa wg
  środka koncepcji) albo PL-1992; X = wschód, Y = północ
- Trasa `/osiedle/koncepcje/<id>.dxf?uklad=`, link „DXF” przy koncepcji
- Sprawdzone niezależnie biblioteką ezdxf (tylko w środowisku testowym,
  nie zależność aplikacji): audyt bez błędów, polilinie zamknięte, pola
  1200,0 m² (PL-2000) i 1198,9 m² (PL-1992 — zniekształcenie 0,9993)
- `DECISIONS.md`: D-130

## ETAP 123 — MPZP: działka i części w przeznaczeniach do DXF
Data: 2026-10-01
Status: zamknięty

- `mpzp/dxf_dzialki.py`: obrys działki (DZIALKA), części w
  przeznaczeniach z WFS gminy (PRZEZN_<symbol>, kolory jak w raporcie),
  opisy (numer działki jak w raporcie — po jednostce i obrębie — z
  powierzchnią, symbole przeznaczeń, przeznaczenie z KIMPZP); PL-2000
  albo PL-1992
- `mpzp/routes.py`: wspólne `_cechy_eksportu` dla GeoJSON i DXF (ta sama
  obsługa błędów ULDK/WFS); trasa `/mpzp/eksport.dxf?id=&uklad=`; link
  „DXF” przy wyniku działki
- `dane/dxf.py`: osobne czyszczenie nazw warstw (bez spacji i nawiasów)
  i tekstów opisów (drukowalne ASCII) — błąd złapany w teście
- Sprawdzone ezdxf: audyt bez błędów, suma części = pole działki
  (7573,6 vs 7573,7 m²)
- `DECISIONS.md`: D-131

## ETAP 124 — Atlas: typologia gmin metodą k-średnich
Data: 2026-10-01
Status: zamknięty

- `atlas/typologia.py`: standaryzacja (z, odchylenie populacyjne),
  k-średnich (Lloyd) ze startem deterministycznym (najbliższa średniej,
  potem maximin), puste skupienie przejmuje punkt najdalszy; typy od
  najliczniejszego; profil (średnie surowe i z), opis z profilu
  („wysoki/niski: …” od |z| ≥ 0,5); średnia sylwetka; gminy bez danych
  pominięte
- `atlas/trasy_typologia.py`: strona `/atlas/typologia`, wynik JSON,
  kartogram SVG (kolory kategorii, w legendzie „Typ N”, opisy typów w
  przypisach), CSV; parametry jak we wskaźniku złożonym (`_parametry`)
- `atlas/mapa_svg.py`: arkusz rośnie, gdy przypisów jest więcej niż 3
  (po sprawdzeniu: opisy typów ucinały źródło)
- Strona: wybór wskaźników i k (2–8), jakość podziału słownie, profile,
  lista gmin; link z Atlasu
- Sprawdzone w przeglądarce na 48 gminach z trzema podstawionymi grupami
  (1300 i 390 px)
- `DECISIONS.md`: D-132

## ETAP 125 — Atlas: dobór liczby typów w typologii (sylwetka)
Data: 2026-10-01
Status: zamknięty

- `atlas/typologia.py`: wspólne `_dane` (standaryzacja) dla typologii i
  `sylwetki` — średnia sylwetka dla k = 2…8 (do połowy liczby gmin),
  najlepsza oznaczona (remis — mniejsze k)
- Trasa `/atlas/typologia/sylwetki`; przycisk „Porównaj liczbę typów” —
  tabela z paskami, kliknięcie (albo Enter) wybiera k i liczy typologię
- Sprawdzone w przeglądarce (1300 i 390 px)
- `DECISIONS.md`: D-133

## ETAP 126 — Diagnostyka: stan usług, konfiguracji i danych
Data: 2026-10-01
Status: zamknięty

- `diagnostyka.py`: lista usług z adresami ze stałych modułów (GUS BDL,
  ULDK, KIMPZP, PRG, ortofotomapa, API Sejmu, Gemini), sprawdzenie
  równoległe jednym GET z limitem 6 s (każda odpowiedź HTTP = serwer
  osiągalny); stan: klucze Gemini i GUS (tylko czy są), folder danych,
  rozmiar danych modułów i ich bazy, wolne miejsce, kopia automatyczna,
  wersje Pythona i bibliotek
- Strona `/diagnostyka` (link w Pomocy), usługi na żądanie
  (`/diagnostyka/uslugi`) — samo otwarcie strony nie łączy się z siecią
- Do Gemini bez klucza i bez zapytania do modelu (bez kosztów)
- Sprawdzone w przeglądarce w tym środowisku: Gemini odpowiada, usługi
  polskie zablokowane przez proxy — strona to pokazuje
- Testy: klucz nie trafia na stronę, wyniki przy timeout / braku
  połączenia / 404, zapytania bez kluczy
- `DECISIONS.md`: D-134

## ETAP 127 — Dziennik błędów w pliku i podgląd w diagnostyce
Data: 2026-10-01
Status: zamknięty

- `dziennik.py`: błędy i ostrzeżenia aplikacji do
  `instance/logi/warsztat.log` (RotatingFileHandler: 1 MB, 3 kopie,
  od WARNING), podgląd ostatnich 30 wpisów z tracebackiem, czyszczenie
- Kolejne `create_app` (testy) zastępują plik dziennika zamiast dokładać
  drugi uchwyt do wspólnego loggera Flaska
- `/diagnostyka`: sekcja „Ostatnie błędy” (traceback rozwijany),
  „Wyczyść dziennik” (POST, chroniony jak inne zapytania — `ochrona.py`)
- Dziennik nie trafia do kopii zapasowej (`kopia.POMIJANE`)
- Sprawdzone: nieobsłużony wyjątek strony (500) trafia do pliku z pełnym
  tracebackiem, a nadal widać go w terminalu
- `DECISIONS.md`: D-135

## ETAP 128 — Wyszukiwarka globalna
Data: 2026-10-02
Status: zamknięty

- Każdy moduł ma `wyszukaj(fraza)` (najwyżej 10 wyników `{tytul, opis,
  url}`): fiszki (pytanie, odpowiedź, fragment), przepisy (wyszukiwarka
  pełnotekstowa modułu, bez znaczników trafień), MPZP (zapisane działki →
  karta działki), osiedle (koncepcje → edytor), teren (projekty), ceny
  (pliki RCN i narysowane obszary)
- `app.py`: strona `/szukaj` zbiera wyniki jak strona główna podsumowania
  — błąd jednego modułu trafia do dziennika i nie blokuje reszty
- Osiedle otwiera koncepcję z adresu `?koncepcja=<id>`
- Menu: „⌕ Szukaj”; pole z fokusem; fraza od 2 znaków
- Sprawdzone w przeglądarce (1300 i 390 px): wynik → otwarta koncepcja
- `DECISIONS.md`: D-136

## ETAP 129 — Przywracanie kopii zapasowej w aplikacji
Data: 2026-10-02
Status: zamknięty

- `kopia.py`: `przywroc_kopie` — rozpakowanie do folderu tymczasowego,
  sprawdzenie (PRZYWRACANIE.txt, tylko `instance/…`, bez `..` i ścieżek
  bezwzględnych, limit rozmiaru i liczby plików, `PRAGMA integrity_check`
  każdej bazy), kopia bezpieczeństwa obecnych danych
  (`warsztat_przed_przywroceniem_…zip`), przeniesienie obecnych danych do
  `instance_stary_…` (nic nie usuwamy), wstawienie danych z kopii; logi/
  zostaje; nazwy unikalne przy dwóch przywróceniach w tej samej sekundzie
  (błąd złapany w teście); `kopie_do_przywrocenia` — lista z folderu kopii
- Strona `/kopia-zapasowa/przywroc` (link przy kopii na stronie głównej):
  kopia z listy (tylko nazwy z listy) albo wgrany ZIP, obowiązkowe
  potwierdzenie; wpis w dzienniku
- Instrukcja w ZIP wskazuje przywracanie w aplikacji
- Sprawdzone w przeglądarce: pobranie kopii → zmiana → przywrócenie;
  poprawione łamanie długich ścieżek na telefonie
- `DECISIONS.md`: D-137

## ETAP 130 — Dostępność: etykiety pól, nazwy przycisków, obsługa klawiatury
Data: 2026-10-02
Status: zamknięty

- `narzedzia/przeglad_stron.py`: sprawdzanie dostępności na każdej
  stronie — `lang`, obrazy bez `alt`, pola bez etykiety (label /
  aria-label / title / placeholder), przyciski i linki bez nazwy,
  powtórzone `id`; pierwszy przebieg: 7 stron z problemami
- Poprawione: etykiety (`aria-label`) pól wyboru pliku w fiszkach (3),
  przepisach, dostępności (2), cenach i terenie; nazwa i typ pola w
  edytorze formularza terenu (pola tworzone w JS)
- `base.html`: link „Przejdź do treści” (pierwszy po Tab, omija menu),
  `main` jako cel fokusu; wyraźna ramka fokusu z klawiatury
  (`:focus-visible`) dla linków, przycisków i rozwijanych sekcji
- Wynik przeglądu: 69 stron, 0 problemów; sprawdzona obsługa klawiaturą
- `DECISIONS.md`: D-138

## ETAP 131 — Kontrast kolorów w obu motywach (WCAG AA)
Data: 2026-10-02
Status: zamknięty

- Pomiar kontrastu par tekst/tło z tokenów `static/style.css` (wzór WCAG):
  za mało w jasnym — tekst drugorzędny na tle wyciszonym 4,46, linki na
  tle strony 4,31, kolor sukcesu 4,42; w ciemnym — biały na niebieskim
  przycisku 3,02
- Jasny: akcent `#0066cc` (5,1 na tle), tekst drugorzędny `#6a6a6f`,
  sukces `#1a7f35`; nowy token `--akcent-wypelnienie` (tło pod białym
  tekstem): jasny `#0066cc`, ciemny `#0a6ed1` (5,0), najechanie przyciemnia
  (`#0058b0` / `#0b62bb`) zamiast rozjaśniać
- Przyciski, przełączniki (kronika MPZP, mieszkania/działki), „Przejdź do
  treści” i formularze na telefon (teren, fiszki) na nowym tokenie;
  aktywny przycisk pomiaru w MPZP: ciemny tekst na pomarańczowym
- `tests/test_kontrast.py`: kontrast par z tokenów w obu motywach ≥ 4,5
  — zmiana koloru, która go obniży, zatrzyma testy
- Poprawione przy okazji: brzeg linku „Przejdź do treści” widoczny w
  rogu, odstęp formularza wyszukiwarki od wyników
- `DECISIONS.md`: D-139

## ETAP 132 — Teren: rozmieszczenie punktów w heksagonach H3 w raporcie
Data: 2026-10-02
Status: zamknięty

- `teren/raport.py`: `heksagony` — punkty z położeniem w komórkach H3,
  rozdzielczość dobierana (11 → 10 → 9, krawędź ok. 30 / 75 / 200 m):
  najdrobniejsza z co najmniej 2 punktami średnio na komórkę; dla pola
  wybranego do kolorowania — wartość najczęstsza z udziałem; od 10 punktów
- `heksagony_svg`: komórki w pięciu odcieniach według liczby punktów,
  liczba i numer komórki (jak w tabeli), podziałka; bez podkładu
- Raport projektu: sekcja „Rozmieszczenie punktów” (mapa + tabela:
  komórka, liczba, numery punktów, najczęstsza wartość)
- Sprawdzone w przeglądarce (40 punktów w trzech skupiskach); tabela
  przewija się na telefonie (poprawione po sprawdzeniu)
- `DECISIONS.md`: D-140

## ETAP 133 — Teren: import punktów z GeoJSON (QGIS)
Data: 2026-10-02
Status: zamknięty

- `teren/projekt.py`: `odczytaj_geojson` — FeatureCollection punktów
  WGS84; atrybuty dopasowane do pól projektu po nazwie bez wielkości
  liter, przeliczenie typów (tak/nie z tak/1/true, wielokrotny wybór z
  „a; b”, liczba z przecinkiem), walidacja jak dla pliku z telefonu
  (`_wartosci`); „opis/uwagi” i atrybuty bez pola do uwag; czas z
  atrybutu „czas/data” albo chwila importu; identyfikator z położenia i
  atrybutów — ponowny import pomija istniejące; czytelny błąd dla
  współrzędnych w metrach (zapisz w EPSG:4326) i obiektów innych niż punkt
- Trasa importu rozpoznaje GeoJSON po zawartości; odpowiedź z listą
  atrybutów bez pola (format odpowiedzi dla pliku z telefonu bez zmian)
- Strona projektu: opis importu, komunikat z niedopasowanymi atrybutami
- Sprawdzone w przeglądarce (5 punktów, ponowny import w teście)
- `DECISIONS.md`: D-141

## ETAP 134 — Teren: nowy projekt na wzór istniejącego
Data: 2026-10-02
Status: zamknięty

- Trasa POST `/teren/projekty/<id>/podobny`: nowy projekt „<nazwa>
  (kopia)” z tymi samymi polami, rodzajem i obszarem mapy offline; bez
  punktów i terminu; nowy klucz pliku z telefonu (pliki z dwóch projektów
  się nie pomylą)
- Przycisk „Utwórz podobny” na stronie projektu
- Test: pola, rodzaj, obszar skopiowane; punkty nie; osobny klucz; 404
- Przegląd stron: 69 stron, 0 problemów
- `DECISIONS.md`: D-142

## ETAP 135 — Ceny: rynek pierwotny i wtórny w porównaniu obszarów
Data: 2026-10-02
Status: zamknięty

- `rcn._rynki`: mediana za m² i liczba transakcji osobno dla rynku
  pierwotnego i wtórnego, „premia pierwotnego” w % (tylko gdy oba rynki
  mają co najmniej `MIN_W_RYNKU = 5` transakcji); dołączane do każdego
  wiersza `porownanie`
- Strona Transakcje: tabela pod porównaniem obszarów (tylko mieszkania,
  tylko gdy w danych są transakcje z rynku pierwotnego)
- Raport do druku: sekcja „Rynek pierwotny i wtórny”
- Test premii; fikstury z polem `rynek`
- Sprawdzone w przeglądarce 1300/390 px: tabela, raport bez przelewania
- `DECISIONS.md`: D-143

## ETAP 136 — Ceny: zastąpienie pliku RCN nowszym z zachowaniem obszarów
Data: 2026-10-02
Status: zamknięty

- `baza.zapisz_plik_rcn(..., zastap=id)`: aktualizuje wiersz pliku i
  podmienia transakcje lokali i działek w jednej transakcji bazy; id
  pliku i narysowane obszary zostają
- Formularze importu (z Pobranych i wgrywanie): wybór „jako: nowy plik /
  nowsza wersja: <nazwa>”; nieistniejący plik do zastąpienia → 404
- Komunikat po zastąpieniu: liczba lokali i działek przed i po
- Test: obszar zostaje, nowe lata, jedna pozycja na liście, komunikat
- Sprawdzone w przeglądarce 1300/390 px, jasny i ciemny
- `DECISIONS.md`: D-144

## ETAP 137 — Ceny: raport porównania miast GUS do druku
Data: 2026-10-02
Status: zamknięty

- Trasa `/ceny/raport?id=…&nazwa=…` (te same parametry co CSV): tabela
  zmian (rok do roku, w 5 lat, od początku, średnio rocznie), wykres w
  latach (SVG z serwera, ten sam co w raporcie transakcji), dane rok po
  roku, dostępność cenowa, gdy wybrano wskaźnik wynagrodzenia
- Błąd GUS dla jednego miasta → komunikat w jego wierszu, reszta raportu
  działa; bez wybranego wskaźnika → przekierowanie na stronę modułu
- `rcn.wykres_lat_svg`: najwyżej ~12 podpisów lat (długie szeregi GUS)
- Link „Raport do druku ↗” obok CSV
- Testy: liczby, wykres, dostępność, błąd BDL, 400/302
- Sprawdzone w przeglądarce 1300/390 px, jasny i ciemny, PDF
- `DECISIONS.md`: D-145

## ETAP 138 — Osiedle: import obszaru opracowania z GeoJSON
Data: 2026-10-02
Status: zamknięty

- `osiedle/obszar_z_pliku.py`: FeatureCollection / Feature / geometria →
  suma wieloboków w WGS84; układ z pola `crs` (EPSG:4326, 2180, 2176–2179)
  albo z zakresu liczb; inne EPSG → czytelny błąd; kontrola „w Polsce”
- `mpzp/uklady.wgs84_z_pl2000` (odwrotność PL-2000, strefa z numeru)
- Trasa POST `/osiedle/koncepcje/<id>/obszar-z-pliku` (multipart);
  wspólna z obszarem z działek funkcja `_zastap_obszar`
- Panel: „Obszar opracowania z pliku GeoJSON”; `zapytaj` w osiedle.js
  wysyła FormData bez nagłówka JSON
- Test: WGS84 (dwa wieloboki → jeden), PL-1992 bez crs, PL-2000 z crs,
  błędy (punkty, Paryż, EPSG:3857, nie-JSON, brak pliku, 404)
- Sprawdzone w przeglądarce 1300/390 px: pole jak z obliczenia ręcznego
- `DECISIONS.md`: D-146

## ETAP 139 — Fiszki: fiszki z luką (cloze)
Data: 2026-10-02
Status: zamknięty

- `fiszki/luki.py`: tekst z `[[lukami]]` → po jednej fiszce na lukę
  (pytanie z „[…]”, pozostałe luki odsłonięte); walidacja: brak luk,
  pusta / niedomknięta / zagnieżdżona luka, tekst tylko z luk, limity
- Trasa POST `/fiszki/<pdf>/luki`: zapis wszystkich fiszek z tą samą
  kotwicą (strona, fragment) i tematami; wspólna funkcja `_wstaw_fiszke`
- Przy zaznaczeniu w PDF obok „✦ Zaproponuj fiszkę” przycisk „[…] Z
  luką”; formularz z „Ukryj zaznaczone” i podglądem fiszek
- Bez zmian w bazie: to zwykłe fiszki (powtórki, telefon, quiz, druk)
- Testy: funkcja i trasa; sprawdzone w przeglądarce 1300/390 px
- `DECISIONS.md`: D-147

## ETAP 140 — Przepisy: notatki przy artykułach
Data: 2026-10-02
Status: zamknięty

- Tabela `notatki` (jedna na jednostkę, z `akt_id`); `baza.notatki_aktu`,
  `zapisz_notatke` (pusty tekst usuwa), `szukaj_w_notatkach` (bez
  polskich znaków); usunięcie aktu usuwa notatki
- Trasa PUT `/przepisy/jednostki/<id>/notatka` (limit 5000 znaków)
- Strona aktu: „✎ Dodaj notatkę / Notatka” przy jednostce, edytor w
  miejscu, notatka pod tekstem, ✎ w spisie
- Wyszukiwarka globalna: wyniki „Notatka: Art. … — akt”
- Pasek jednostki na wąskim ekranie: numer bez łamania
- Test; sprawdzone w przeglądarce 1300/390 px, jasny i ciemny
- `DECISIONS.md`: D-148

## ETAP 141 — Strona główna: ostatnio używane („Wróć do pracy”)
Data: 2026-10-02
Status: zamknięty

- Funkcja `ostatnie(limit)` w routes modułów fiszki, przepisy, mpzp,
  osiedle, teren i ceny (jak `wyszukaj`, D-136); w fiszkach i przepisach
  „ostatnio” = także nowa fiszka / powtórka / notatka, w terenie — import
  punktów (`teren.baza.ostatnio_zmienione`, `przepisy.baza.ostatnio_uzywane`)
- `app.ostatnio_uzywane`: łączy i sortuje, najwyżej 6; błąd modułu nie
  psuje strony; `kiedy_opis`: „dziś, 9:05” / „wczoraj” / „4 dni temu” / data
- Sekcja „Wróć do pracy” nad kalendarzem (pusta instalacja — bez sekcji)
- Testy: opis czasu, sekcja, odporność na błąd modułu; test kalendarza
  w Terenie zawężony do sekcji terminów
- Sprawdzone w przeglądarce 1300/390 px, jasny i ciemny
- `DECISIONS.md`: D-149

## ETAP 142 — Wydruki: spójna stopka
Data: 2026-10-02
Status: zamknięty

- `templates/_wydruk.html`: makro `stopka_wydruku(modul, zrodlo)` —
  „Warsztat · moduł …”, źródło danych, „Wygenerowano dd.mm.rrrr, gg:mm”
  (globalna funkcja Jinja `teraz_wydruku`)
- Stopka na 10 stronach do druku: Atlas (raport gminy, mapa do druku),
  MPZP, Fiszki, Dostępność, Osiedle, Teren, Ceny (raport, wycena, raport
  miast); usunięte powtarzające się dopiski „Raport z modułu…” /
  „Opracowanie: Warsztat, data” i data wstawiana przez JS w raporcie gminy
- Test: każda strona z „Drukuj” ma stopkę; treść i format daty
- Przegląd stron: 70 stron, 0 problemów
- `DECISIONS.md`: D-150

## ETAP 143 — Wydajność: szybszy start aplikacji
Data: 2026-10-02
Status: zamknięty

- Pomiar (`python -X importtime`): z ok. 0,87 s startu 0,4 s to import
  `google.genai`, potrzebny dopiero przy pytaniu do modelu
- `dane/gemini.py`: sześć identycznych bloków wywołania zebrane w
  `_generuj(contents, **konfiguracja)`, które importuje bibliotekę przy
  pierwszym zapytaniu; zachowanie i komunikaty błędów bez zmian
  (sprawdzone na żywym API: zły klucz → czytelny BladGemini)
- Start (import + `create_app`): 0,87 s → 0,42 s
- Statyczne: Flask wysyła ETag z `no-cache` — przeglądarka dostaje 304,
  zmiany po aktualizacji widać od razu; bez zmian
- Test: start nie ładuje `google.genai`; test opisu gminy podmienia
  klienta w `google.genai`
- `DECISIONS.md`: D-151

## ETAP 144 — Testy: pokrycie i luki
Data: 2026-10-02
Status: zamknięty

- Pomiar `coverage` (osobne środowisko, nie zależność projektu): 94% →
  95% instrukcji; najsłabszy plik 48% → 85%
- `tests/test_gemini.py`: warstwa Gemini z udawanym klientem —
  co trafia do modelu (treść, instrukcja, JSON), parser „PYTANIE/ODPOWIEDZ”
  (wcześniej bez testu), listy fiszek, odrzucanie obcych liczb, błąd API
  → BladGemini, brak klucza we wszystkich 6 funkcjach
- Atlas: mapa do druku w trybie zmiany i LISA (siatka 3×3 gmin);
  w teście czyszczony cache sąsiedztwa per województwo
- Osiedle: przypadki brzegowe importu obszaru (Feature, MultiPolygon,
  CRS84, za dużo obiektów, uszkodzona geometria, zła strefa PL-2000)
- Aktualizacja: zapis sumy requirements jak w `uruchom.sh`, nieudany pip,
  port z `.env`
- Instrukcja pomiaru w README
- `DECISIONS.md`: D-152

## ETAP 145 — Dokumentacja: architektura
Data: 2026-10-02
Status: zamknięty

- `docs/ARCHITEKTURA.md`: obraz całości (start → `create_app` →
  blueprinty → `dane/` → `instance/`), konfiguracja i ochrona, układ
  modułu, haki dla stron wspólnych (`podsumowanie`, `terminy`,
  `wyszukaj`, `ostatnie`), powiązania między modułami (sprawdzone
  w importach), warstwa `dane/`, zasady pilnowane przez kod (liczby z
  danych, cytaty w źródle, kotwice, SVG z serwera, nietykalne dane),
  frontend, testy i narzędzia, kolejność czytania kodu
- Odnośniki do decyzji sprawdzone z `DECISIONS.md`
- Stan faktyczny: geometria jako GeoJSON w SQLite + shapely; SpatiaLite
  (wymieniony w stosie w CLAUDE.md) nie jest używany
- Link w README
- `DECISIONS.md`: D-153

## ETAP 146 — Strona główna: pierwsze kroki
Data: 2026-10-02
Status: zamknięty

- Karta „Pierwsze kroki” w pustej instalacji (brak „ostatnio używanych”,
  zestawów Atlasu i własnych wyników Dostępności): stan klucza Gemini
  (co bez niego nie działa), nieobowiązkowy klucz GUS, co wypróbować bez
  własnych danych, Pomoc i diagnostyka; znika po pierwszym zapisie
- Znacznik „gotowe” jako obwódka w kolorze sukcesu (biały na
  jasnozielonym w trybie ciemnym byłby nieczytelny)
- Test: karta tylko w pustej instalacji, stany kluczy
- Sprawdzone w przeglądarce 1300/390 px, jasny i ciemny
- `DECISIONS.md`: D-154

## ETAP 147 — Przegląd kodu
Data: 2026-10-02
Status: zamknięty

- Niestabilne „1 warning” w testach: przyczyna — test kontrastu
  (ETAP 131) otwierał `static/style.css` bez zamknięcia; poprawione
- `pytest.ini`: `ResourceWarning` i nieobsłużone wyjątki w `__del__` to
  błąd testu — trzy pełne przebiegi czyste
- Połączenia SQLite: `kopia.py` (sprawdzanie kopii) zamyka połączenie
  przez `closing()` — `with sqlite3.connect()` tylko zatwierdza transakcję;
  `ceny/rcn.czytaj_plik` zamyka połączenie, gdy plik nie jest bazą.
  Python 3.11 o tym nie ostrzega (od 3.13 tak)
- Dymki Leaflet z tekstem spoza kodu (nazwa obszaru od użytkownika, nazwa
  punktu z CSV, nazwa gminy z pliku granic, data z pliku RCN) jako węzeł z
  `textContent` — wcześniej Leaflet wstawiał je jako HTML
- Bez zmian po sprawdzeniu: pyflakes (tylko celowe importy tras), brak
  sekretów i TODO, nasłuch tylko 127.0.0.1, szerokie `except` uzasadnione
  (shapely, wycofanie zapisu z ponownym zgłoszeniem), `innerHTML` tylko
  ze stałym tekstem
- ARCHITEKTURA.md: zasada dymków i `pytest.ini`
- Przegląd stron: 70 stron, 0 problemów
- `DECISIONS.md`: D-155

## ETAP 148 — Przegląd stron
Data: 2026-10-02
Status: zamknięty

- `narzedzia/przeglad_stron.py`: dane także dla stron z ETAPów 120–147
  (PDF z tekstem i fiszką z luką, akt z notatką, raport miast GUS z
  podmienioną usługą, wyszukiwarka z wynikami, osiedle z `?koncepcja=`);
  `/ceny/raport` bez parametrów na liście stron wymagających parametrów;
  opcja `ZRZUTY=katalog` — zrzut każdej strony do przejrzenia oczami
- Wynik: 75 stron × 2 szerokości, 0 problemów; zrzuty przejrzane
- Znalezione przy oglądaniu: wyszukiwarka przepisów nie znajdowała „plan”
  w „planu / planie” — słowa 4-literowe szukane teraz po początku (krótsze
  dokładnie, żeby skróty nie zalewały wyników); „1 kart.” na wydruku fiszek
  → poprawna odmiana (karta / karty / kart)
- Testy: krótkie słowo z odmianą, odmiana liczby kart
- `DECISIONS.md`: D-156

## ETAP 149 — Dokumentacja: portfolio, Pomoc, README po ETAPach 120–148
Data: 2026-10-02
Status: zamknięty

- README: „ośmioma” narzędziami (było „siedmioma”); funkcje z ETAPów
  120–148 w opisach modułów (typologia, DXF, fiszki z luką, obszar z
  GeoJSON, słowniczek, odesłania, notatki, heksagony i import w Terenie,
  projekt na wzór, piętro, premia rynku pierwotnego, nowsza wersja pliku
  RCN, raport miast); wspólne: wyszukiwarka, „Wróć do pracy”, „Pierwsze
  kroki”, diagnostyka, przywracanie kopii, stopka wydruków; tabela „Gdzie
  co jest w kodzie” uzupełniona o nowe pliki
- PORTFOLIO: moduły i umiejętności, zasady (import/eksport GIS i CAD),
  liczby (stan: ETAP 149 — 16,5 tys. wierszy Pythona, 554 testy, pokrycie
  95%, 75 stron w przeglądzie), dwa nowe zrzuty do zrobienia, English summary
- Pomoc: wpisy do funkcji z ETAPów 120–148 dodawane na bieżąco — sprawdzone
- `DECISIONS.md`: D-157

## ETAP 150 — Podsumowanie ETAPów 110–150 i plan 151–200
Data: 2026-10-02
Status: zamknięty

- `docs/PODSUMOWANIE_110-150.md`: liczby przed i po (testy 494 → 554,
  pokrycie 95%, decyzje 117 → 158, przegląd 75 stron, start 0,87 → 0,42 s),
  co doszło w każdym module, błędy znalezione przez przeglądy i testy,
  sprawy otwarte dla autora (SpatiaLite w CLAUDE.md, zrzuty i akapit
  w portfolio, pierwsze uruchomienie na prawdziwych usługach)
- Plan: ETAPy 151–170 konkretnie (z uzasadnieniem), 171–200 jako kierunki
  do doprecyzowania po przeglądzie w ETAPie 170
- Link w README
- `DECISIONS.md`: D-158

## ETAP 151 — Wygląd: przełącznik motywu
Data: 2026-10-02
Status: zamknięty

- Przycisk w menu: jak w systemie (◐) → jasny (☀) → ciemny (☾);
  wybór w localStorage (ustawienie wyglądu), atrybut `data-motyw` na
  `<html>` ustawiany skryptem w `<head>` przed narysowaniem strony
- `style.css`: tryb ciemny systemu wyłączany przez `data-motyw="jasny"`,
  osobny blok tokenów dla `data-motyw="ciemny"` (+ `color-scheme`)
- Test: oba bloki ciemne mają identyczne tokeny (kontrast liczony raz)
- Sprawdzone w przeglądarce 1300/390 px: kolejność, przeładowanie,
  podpowiedź; przegląd stron 75/0
- `DECISIONS.md`: D-159

## ETAP 152 — Atlas: gorące punkty Getisa-Orda Gi*
Data: 2026-10-02
Status: zamknięty

- `atlas/autokorelacja.gi_star`: Gi* (Ord i Getis 1995) z wagami
  binarnymi i samą gminą, z-score, p dwustronne z rozkładu normalnego,
  kategorie 90/95/99% gorące i zimne; liczone w `analiza` na tym samym
  oczyszczonym sąsiedztwie co LISA
- Wynik sprawdzony z PySAL (esda.G_Local, star=True): różnica < 1e-13;
  wartości referencyjne w teście
- Mapa: widok „Gorące punkty” (legenda z liczebnościami, dymek z z),
  mapa do druku `tryb=gi`
- Sprawdzone w przeglądarce (jasny i ciemny)
- `DECISIONS.md`: D-160

## ETAP 153 — Atlas: iloraz lokalizacji (LQ)
Data: 2026-10-02
Status: zamknięty

- `statystyki.iloraz_lokalizacji`: LQ_i = (x_i/X_i)/(Σx/ΣX) z surowych
  wartości licznika i mianownika (gminy z oboma, X_i > 0), stałe klasy
  0,5 / 0,8 / 1,2 / 2
- `/atlas/dane` z mianownikiem zwraca `lq`; widok mapy „Iloraz
  lokalizacji” (legenda z liczebnościami, dymek), mapa do druku `tryb=lq`
  (400 bez mianownika)
- Testy: wzór, pominięcie gminy z mianownikiem 0, trasa (Kraków /
  Wieliczka), wydruk
- Sprawdzone w przeglądarce (jasny i ciemny)
- `DECISIONS.md`: D-161

## ETAP 154 — Fiszki: fiszka z wycinkiem rysunku z PDF
Data: 2026-10-02
Status: zamknięty

- Tryb „✂ Wycinek rysunku” w widoku PDF: prostokąt przeciągnięty na
  stronie → PNG z płótna pdf.js (szersze niż 1400 px zmniejszane),
  podgląd w formularzu nowej fiszki; kotwica: strona
- `fiszki/obrazy.py`: sprawdzenie data URL (PNG, sygnatura, do 2 MB),
  zapis pod losową nazwą w `instance/fiszki/obrazy/`, tabela
  `obrazy_fiszek` (kaskada z fiszką), sprzątanie osieroconych plików po
  usunięciu fiszki lub PDF-a, trasa `/fiszki/obrazy/<nazwa>`
- Obraz przy pytaniu: lista fiszek (miniatura), powtórka (w trybie
  odwróconym z tyłu karty), quiz, druk, plik na telefon (data URL w pliku)
- Przy okazji: komentarz do importu tras wrócił nad import (rozdzielony
  w ETAPie 141)
- Testy: wszystkie miejsca wyświetlania, złe obrazy, limit, ścieżki,
  sprzątanie; sprawdzone w przeglądarce 1300/390 px
- `DECISIONS.md`: D-162

## ETAP 155 — Osiedle: szacunek kosztów ze stawek użytkownika
Data: 2026-10-02
Status: zamknięty

- `osiedle/koszty.py`: osiem stawek (budowa MW/MN/U za m² pow.
  całkowitej, KD/KS/ZP za m² terenu, garaż podziemny za brakujące
  miejsce, grunt za m² obszaru) bez wartości domyślnych; ilość × stawka,
  razem, na mieszkanie, na m² pow. całkowitej; walidacja 0–1 000 000
- `bilans` zwraca `koszty` (None bez stawek); stawki w `ustawienia.koszty`
- Panel: karta „Szacunek kosztów” (pozycja z wyliczeniem „ilość × stawka”
  i koszt — dwie kolumny mieszczą się na telefonie), raport do druku,
  porównanie wariantów (razem, na mieszkanie, na m²)
- Testy: wyliczenia, pominięte puste stawki, błędne stawki, trasa,
  raport, porównanie; sprawdzone w przeglądarce 1300/390 px
- `DECISIONS.md`: D-163

## ETAP 156 — Ceny: wpływ cech na cenę za m² (regresja)
Data: 2026-10-02
Status: zamknięty

- `rcn.najmniejsze_kwadraty`: OLS bez zależności (Gauss-Jordan dla XᵀX),
  błędy standardowe, R², RMSE; zgodność z numpy do 1e-10 (wartości
  referencyjne w teście); współliniowość → czytelny błąd
- `rcn.regresja_cen`: czas (lata od pierwszej transakcji), powierzchnia
  (na 10 m²), piętro (gdy znane w ≥ 80% transakcji), rynek pierwotny
  (gdy są oba rynki); 1% skrajnych cen z każdej strony pominięty;
  |t| ≥ 1,96 → „wyraźny związek”; min. 30 transakcji
- Trasa `/ceny/transakcje/<id>/regresja` z filtrami strony (tylko
  mieszkania); karta „Co wpływa na cenę za m²” z przyciskiem „Policz”
- 100 tys. transakcji: 0,6 s
- Testy: OLS vs numpy, odtworzenie znanych efektów, pomijanie zmiennych,
  trasa; sprawdzone w przeglądarce 1300/390 px
- `DECISIONS.md`: D-164

## ETAP 157 — Teren: porównanie dwóch inwentaryzacji
Data: 2026-10-02
Status: zamknięty

- `teren/porownanie.py`: wspólne pola (nazwa i typ), zestawienie A/B ze
  zmianą w p.p. i zmianą średniej, pary punktów wzajemnie najbliższych
  w promieniu 15 m (haversine), zmiany w tych samych miejscach dla pól
  na skali (lepiej / gorzej / bez zmian, z numerami punktów)
- Trasa `/teren/porownanie?a=&b=` (strona do druku, stopka), formularz
  „Porównaj” na stronie projektu
- Testy: pary (w tym punkt przesunięty o 40 m), zmiana p.p., projekt bez
  wspólnych pól, błędy; sprawdzone w przeglądarce 1300/390 px
- `DECISIONS.md`: D-165

## ETAP 158 — Przepisy: druk notatek i wybranych artykułów
Data: 2026-10-02
Status: zamknięty

- Trasa `/przepisy/akty/<id>/druk`: `?notatki=1` — jednostki z notatkami,
  `?j=…&j=…` — wybrane; tekst z odesłaniami, strona PDF, nagłówek
  rozdziału, notatka; stopka wydruku
- Strona aktu: „Drukuj z notatkami” (gdy są notatki), pole „druk” przy
  każdej jednostce i „Drukuj zaznaczone (n)”
- Własne klasy wydruku w przepisy.css (bez pożyczania z modułu Ceny)
- Test; sprawdzone w przeglądarce 1300/390 px
- `DECISIONS.md`: D-166

## ETAP 159 — Co nowego po aktualizacji
Data: 2026-10-02
Status: zamknięty

- `nowosci.py`: wpisy z `docs/CHANGELOG.md` (nagłówki „## ETAP N —
  data”, punkty wieloliniowe sklejone), od najnowszego; numer ostatnio
  obejrzanego ETAPu w `instance/widziana_wersja.txt`; pierwsze
  uruchomienie zapisuje bieżący ETAP bez paska
- Strona `/co-nowego` (40 ostatnich ETAPów, nowe oznaczone); jej
  obejrzenie usuwa pasek „Warsztat zaktualizowany…” ze strony głównej
- Wpis w Pomocy
- Testy: parsowanie, pierwsze uruchomienie, pasek, oznaczenie, znikanie;
  sprawdzone w przeglądarce 1300/390 px
- `DECISIONS.md`: D-167

## ETAP 160 — Przegląd po ETAPach 151–159
Data: 2026-10-02
Status: zamknięty

- pyflakes czysty; pokrycie całości 95%, nowy kod 94–100%; testy
  z ostrzeżeniami o zasobach jako błędami — czyste
- Przegląd stron rozszerzony o strony z ETAPów 151–159 (porównanie
  inwentaryzacji, druk przepisów, koncepcja z terenami i kosztami, fiszka
  z wycinkiem): 81 stron × 2 szerokości, 0 problemów
- Znalezione: raport osiedla przewijał się poziomo na telefonie przez
  tabelę „Odległości i cień” (błąd z ETAPu 100, niewidoczny, bo
  koncepcja w przeglądzie nie miała terenów) — tabela w przewijanym
  kontenerze; klasa `przewijanie-osiedla` wspólna dla obu tabel
- Teren: parowanie punktów w porównaniu inwentaryzacji przez siatkę
  komórek 15 m — 1000+1000 punktów 1,14 s → 0,013 s, ten sam wynik
  (test równoważności z porównaniem każdy z każdym)
- `DECISIONS.md`: D-168

## ETAP 161 — Atlas: ten sam wskaźnik w kilku latach obok siebie
Data: 2026-10-02
Status: zamknięty

- `mapa_svg.male_mapy_svg`: arkusz A4 poziomo z 2–6 małymi
  kartogramami (2 albo 3 kolumny), wspólna legenda, podziałka i północ
- `/atlas/lata.svg?…&lata=2014,2018,2023`: klasy wspólne dla wszystkich
  lat (klasyfikacja wartości gmin ze wszystkich map razem), lata bez
  danych GUS pominięte z przypisem, mniej niż dwa lata z danymi → 404
- Strona `/atlas/lata` (pole lat, domyślnie co 3 lata wstecz, druk, SVG,
  stopka); link „Mapy w latach ↗” pod mapą Atlasu
- Testy: arkusz, gmina bez danych w jednym roku, złe lata, 404, strona
- Sprawdzone w przeglądarce 1300/390 px
- `DECISIONS.md`: D-169

## ETAP 162 — MPZP: zestawienie „Moich działek” do druku
Data: 2026-10-02
Status: zamknięty

- `mpzp/zestawienie.py`: działki z numerem (od najstarszego zapisu),
  opisem przeznaczenia ze słownika symboli i współrzędnymi PL-2000;
  suma powierzchni według przeznaczenia (nieznana powierzchnia to nie
  0 m²); schemat położenia SVG z numerami i podziałką
- Trasa `/mpzp/zapisane/druk` — z danych zapisanych, bez zapytań do
  ULDK i planów; link „Druk ↗” w panelu „Moje działki”; stopka wydruku
- Test; sprawdzone w przeglądarce 1300/390 px
- `DECISIONS.md`: D-170

## ETAP 163 — Dostępność: wyniki w narysowanych dzielnicach
Data: 2026-10-02
Status: zamknięty

- `dostepnosc/obszary.py`: komórki H3 ze środkiem w wieloboku
  (`shapely.contains_xy`), liczba komórek, mieszkańcy, średni czas ważony
  ludnością (gdy jest kolumna ludności), mediana, udział w zasięgu 15 min;
  także dla czasu „do wszystkich usług”; obok wynik całego pliku
- Trasa POST `/dostepnosc/plik/<nazwa>/obszary` (bezstanowa, do 8 obszarów)
- Mapa: rysowanie wieloboku / prostokąta (Leaflet.draw), karta
  „Dzielnice” z listą i tabelą; obszary w localStorage dla danego pliku;
  nazwy jako tekst (nie HTML) w dymkach i na liście
- Przy okazji: ikony Leaflet.draw przeniesione do `static/style.css`
  (wcześniej kopie w osiedle.css i ceny.css); siatka panelu Dostępności na
  telefonie `minmax(0, 1fr)` — szeroka tabela nie poszerza strony
- Test: wynik zgodny z liczeniem ręcznym; sprawdzone w przeglądarce
  1300/390 px (także Ceny i Osiedle — ikony rysowania)
- `DECISIONS.md`: D-171

## ETAP 164 — Osiedle: podpowiedź stawki gruntu z transakcji RCN
Data: 2026-10-02
Status: zamknięty

- Trasa `/ceny/okolica` przyjmuje `tylko_niezabudowane: true` — w
  podsumowaniu działek tylko rodzaj „gruntowa niezabudowana” (cena
  zabudowanej obejmuje budynek); stała `rcn.NIEZABUDOWANA`
- Osiedle, karta „Szacunek kosztów”: przycisk „Cena gruntu w okolicy
  (RCN)” — mediana zł/m² działek niezabudowanych do 1 km od obszaru,
  rozstęp kwartylny, liczba transakcji, lata, nazwa pliku; ostrzeżenie
  przy < 5 transakcjach; przycisk „Wpisz medianę jako stawkę gruntu”
  (wpisuje dopiero na kliknięcie)
- Test: filtr działek niezabudowanych (tylko wartość `true` włącza filtr);
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: akapit „Koszty”
- `DECISIONS.md`: D-172

## ETAP 165 — Ceny: kilka plików RCN (powiatów) w jednym zestawieniu
Data: 2026-10-02
Status: zamknięty

- `ceny/rcn.py`: `zestawienie_plikow` — dla każdego pliku `porownanie`
  (te same funkcje co porównanie obszarów), różnica mediany wobec
  pierwszego pliku, obszary pliku pod nim; `wykres_plikow_svg` — linia
  na plik (bez linii „cały plik”); `MAKS_PLIKOW_ZESTAWIENIA` = 4
- Trasa `/ceny/transakcje/zestawienie?pliki=…&co=&rynek=&od=&do=`:
  formularz wyboru plików i filtrów, tabela, wykres i tabela lat, stopka
  wydruku; bez wyboru — sam formularz; 1 plik albo > 4 — komunikat
- Link „Zestaw pliki obok siebie” przy liście zaimportowanych (od 2 plików)
- Testy: liczby zestawienia, wykres, trasa (formularz, błędy, wynik);
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: akapit „Kilka powiatów obok siebie”
- `DECISIONS.md`: D-173

## ETAP 166 — Teren: pola wymagane i zakresy liczb w formularzu na telefon
Data: 2026-10-02
Status: zamknięty

- `teren/projekt.py`: pole może mieć `wymagane` (każdy typ) i `min` / `max`
  (liczba); klucze zapisywane tylko, gdy ustawione — stare projekty bez
  zmian; min > max albo nie-liczba → błąd; `braki(wartosci, pola)` —
  opis braków wymaganych i liczb poza zakresem
- Formularz na telefon: gwiazdka przy polu wymaganym, zakres w etykiecie,
  atrybuty min/max; „Zapisz punkt” sprawdza reguły i przewija do pola
  z komunikatem
- Strona projektu: edytor pól — „wymagane” i „od / do” dla liczby; lista
  punktów ma `braki`, tabela oznacza punkt ⚠ z opisem, nad tabelą liczba
  punktów niezgodnych z regułami; po zapisie pól punkty liczone od nowa
- Import nie odrzuca punktów z brakami
- Testy: definicja pól, `braki`, trasa listy punktów, formularz;
  sprawdzone w przeglądarce (edytor 1300 px, tabela 1300/390 px, formularz
  telefonu 390 px ciemny: brak wymaganego, liczba za duża, zapis poprawny)
- Pomoc: „Pola wymagane i zakres liczb”
- `DECISIONS.md`: D-174

## ETAP 167 — Skróty klawiszowe: okno „?”, wyszukiwanie, mapa; lista w Pomocy
Data: 2026-10-02
Status: zamknięty

- `static/skroty.js` (każda strona): `?` — okno ze skrótami (wspólne +
  tej strony), `/` — pole wyszukiwania strony (atrybut `data-skrot-szukaj`:
  Atlas, MPZP — działka, symbole, Fiszki, Przepisy, akt — „Idź do”,
  Szukaj), gdzie go nie ma — strona Szukaj; `m` — fokus na pierwszej
  widocznej mapie Leaflet (strzałki i +/− działają od razu); bez działania
  w polach tekstowych i z Ctrl/Alt/Cmd; link do zwiniętej sekcji
  (`#kotwica` na `<details>`) ją rozwija
- `base.html`: `<dialog id="okno-skrotow">` z blokiem `skroty` — wiersze
  stron: powtórka (spacja, 1–3, Ctrl+Enter), quiz (1–4/A–D, Enter), MPZP
  (Esc — pomiar)
- Powtórka i quiz ignorują klawisze, gdy okno skrótów jest otwarte
- Pomoc → Na start: „Skróty klawiszowe” (`#skroty`) — pełna tabela
- Przy okazji: niepoprawna sekwencja `\;` w teście kalendarza
  (ostrzeżenie Pythona) poprawiona
- Test: okno i skróty strony, pola wyszukiwania, sekcja Pomocy;
  sprawdzone w przeglądarce 1300/390 px (?, Esc, /, m, Pomoc#skroty)
- `DECISIONS.md`: D-175

## ETAP 168 — Kopia zapasowa: sprawdzanie spójności i kopia poza komputerem
Data: 2026-10-02
Status: zamknięty

- `kopia.py`: `sprawdz_kopie` — `ZipFile.testzip()` (sumy CRC) i to samo
  sprawdzenie co przed przywróceniem (ścieżki, `PRAGMA integrity_check`
  baz) w folderze tymczasowym; kopia automatyczna sprawdzana przed
  zmianą nazwy z `.tmp` — nieudana jest usuwana, błąd trafia do konsoli
- Trasa POST `/kopia-zapasowa/sprawdz` (kopia z listy folderu albo
  wgrany ZIP) — przycisk „Tylko sprawdź kopię” na stronie przywracania
- Kopia poza komputerem: `instance/kopia_poza_dyskiem.txt` z datą
  potwierdzenia (POST `/kopia-zapasowa/poza-dyskiem`), na stronie głównej
  data, przypomnienie po 30 dniach (`PRZYPOMNIENIE_DNI`, tylko gdy są
  dane) i uwaga, gdy folder kopii jest na tym samym dysku co dane
  (`ten_sam_dysk` — `st_dev`)
- Testy: uszkodzony ZIP, kopia automatyczna nie zostaje, trasa
  sprawdzenia (bez zmiany danych, tylko nazwy z listy), przypomnienie;
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: „Czy kopia jest dobra i gdzie ją trzymać?”
- `DECISIONS.md`: D-176

## ETAP 169 — Dokumentacja po ETAPach 151–168
Data: 2026-10-02
Status: zamknięty

- README: tabela modułów uzupełniona o funkcje z ETAPów 151–168 (Gi*, LQ,
  małe mapy, zestawienie działek, obraz w fiszce, koszty i stawka gruntu,
  druk aktu, pola wymagane, porównanie projektów Terenu, regresja i
  zestawienie plików RCN, dzielnice w Dostępności), wspólne: motyw, Co
  nowego, skróty, sprawdzanie kopii; tabela „Gdzie co jest w kodzie” —
  nowe pliki (`obrazy.py`, `koszty.py`, `zestawienie.py`, `porownanie.py`,
  `obszary.py`, `nowosci.py`, `motyw.js`, `skroty.js`)
- ARCHITEKTURA: `/co-nowego`, pliki w `instance/`, sprawdzanie kopii
  (D-176), skróty (D-175), stawka gruntu przez `/ceny/okolica` (D-172)
- PORTFOLIO: liczby na ETAP 169 (17 800 wierszy Pythona, 8 600 testów,
  9 000 JS, 582 testy, 84 strony w przeglądzie)
- Przegląd stron w Chromium: 84 strony, 0 problemów
- Pomoc: wpisy dodawane na bieżąco w ETAPach 151–168 — sprawdzone
- `DECISIONS.md`: D-177

## ETAP 170 — Przegląd po ETAPach 151–169 i plan ETAPów 171–250
Data: 2026-10-02
Status: zamknięty

- Przegląd: testy 582/0, pokrycie 95% (najsłabsze `dane/uldk.py`,
  `atlas/granice.py` — gałęzie błędów usług), pyflakes — jedno ostrzeżenie
  (f-string bez pola w `mpzp/zestawienie.py`) poprawione, przegląd stron
  w Chromium: 84 strony, 0 problemów
- `docs/PLAN_171-250.md`: wyniki przeglądu, uwagi (podział `osiedle.js`,
  arkusz ODS bez zależności, luka w trybie pisania) i plan czterech serii
  po 20 ETAPów z przeglądem i dokumentacją na końcu każdej
- README: odnośnik do planu
- `DECISIONS.md`: D-178

## ETAP 171 — Atlas: kilka gmin na jednym wykresie w czasie
Data: 2026-10-02
Status: zamknięty

- `atlas/trasy_czas.py`: strona `/atlas/gminy-w-czasie` (parametry
  wskaźnika jak mapa do druku + `gminy` — identyfikatory BDL, do 5):
  szeregi z tego samego cache co profil gminy (`szereg:<zmienna>:<gmina>`),
  wskaźnik względny przez `podziel_szeregi`, tabela lat ze zmianą, CSV
  (jak `eksport.csv`: przecinek, UTF-8 z BOM)
- `atlas/wykres_svg.py`: `wykres_gmin_svg` — linie w kolorach serii,
  numery przy ostatnim punkcie, brak roku przerywa linię, oś od zera przy
  danych blisko zera; tylko liczby i kolory z kodu
- Wybór gmin: pole z podpowiedziami (nazwa + TERYT), dodawanie Enterem,
  ✕ usuwa (`gminy_w_czasie.js`); linki „Gminy w czasie ↗” pod mapą i
  „Porównaj z innymi gminami w czasie” w profilu gminy
- Testy: wykres (przerwana linia, oś, numery), strona, duplikaty i złe
  identyfikatory, CSV; sprawdzone w przeglądarce 1300/390 px
- Pomoc: „Gminy w czasie”
- `DECISIONS.md`: D-179

## ETAP 172 — Fiszki: fiszki z luką w trybie pisania
Data: 2026-10-02
Status: zamknięty

- `fiszki/static/powtorka.js`: przy trybie pisania (i bez odwrócenia)
  fiszka z jednym „[…]” ma pole wpisu w miejscu luki (fokus od razu,
  Enter — odsłonięcie); porównanie z całą odpowiedzią: dokładnie / bez
  polskich znaków / literówka (odległość edycji ≤ 1 na 8 znaków) / inaczej
  — bez wielkości liter i interpunkcji; zwykłe fiszki jak dotąd
  (porównanie słów, ETAP 39)
- Zmiana trybu pisania w trakcie rysuje bieżącą kartę od nowa
- `fiszki.css`: pole luki jako podkreślenie w tekście pytania
- Test: znak luki w JS taki sam jak `fiszki/luki.ZNAK_LUKI`; sprawdzone
  w przeglądarce 1300/390 px (literówka, bez znaków, inaczej, zwykła
  fiszka z polem tekstowym)
- Pomoc: „Luka w trybie pisania”
- `DECISIONS.md`: D-180

## ETAP 173 — Osiedle: budynki jako obrysy z liczbą kondygnacji
Data: 2026-10-02
Status: zamknięty

- `osiedle/bilans.py`: obiekt `funkcja: "budynek"` (nie funkcja terenu —
  pomijany w `wczytaj_tereny`, więc bilans, cień i program bez zmian);
  `wczytaj_budynki` (kondygnacje 1–50, puste = 2) i zestawienie w
  `bilans()["budynki"]`: rzut, kondygnacje, powierzchnia całkowita, teren
  pod większością budynku, kontrole „nie na terenie zabudowy” i „poza
  obszarem opracowania”
- Mapa: „budynek” w „Co rysujesz” i w funkcji zaznaczonego obiektu, pole
  kondygnacji, ciemny styl; obszar zawsze pod spodem, budynki na wierzchu
  (`ulozWarstwy`); karta „Budynki” z tabelą i kontrolami
- Szkic SVG (raport, porównanie): budynki nad terenami, numery tylko dla
  terenów (jak w tabeli cienia); GeoJSON: `nazwa_funkcji` „budynek”;
  DXF: warstwa `OSIEDLE_BUDYNEK` (domyślny kolor)
- Testy: zestawienie budynków, kontrole, walidacja kondygnacji, szkic,
  eksport; sprawdzone w przeglądarce 1300/390 px (klik w budynek, zmiana
  kondygnacji)
- Pomoc: „Budynki”
- `DECISIONS.md`: D-181

## ETAP 174 — Osiedle: wskaźniki zabudowy z narysowanych budynków
Data: 2026-10-02
Status: zamknięty

- `osiedle/wskazniki.py`: `wskazniki_budynkow` — powierzchnia zabudowy
  i całkowita, wskaźnik zabudowy, intensywność, najwyższa zabudowa z
  obrysów budynków (PBC tylko z terenów); `bilans()` zwraca
  `wskazniki_budynkow` i `zgodnosc_budynkow` (te same ustalenia planu)
- Panel: kolumna „Budynki” w tabeli wskaźników z ✓/✗ przy wartości,
  nagłówek „Tereny” zamiast „Koncepcja”, gdy obie kolumny są widoczne;
  tabela w przewijanym kontenerze (bez poziomego przewijania strony)
- Raport: kolumny „z terenów / z budynków” i zgodność „— z budynków”;
  porównanie wariantów: wiersze „z budynków: …”, gdy wariant ma budynki
- Testy: wskaźniki i zgodność z budynków, raport, porównanie;
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: akapit „Budynki”
- `DECISIONS.md`: D-182

## ETAP 175 — Osiedle: nieprzekraczalna linia zabudowy i kontrola budynków
Data: 2026-10-02
Status: zamknięty

- `osiedle/bilans.py`: obiekt `funkcja: "linia_zabudowy"` (łamana;
  pomijany przez `wczytaj_tereny`), `wczytaj_linie`; w zestawieniu
  budynków `przecina_linie`, `od_linii_m` (odległość w metrach) i liczba
  budynków przecinających linię
- Mapa: narzędzie łamanej (zawsze linia zabudowy; wielobok przy wybranej
  linii — komunikat), styl czerwony przerywany, linie na wierzchu;
  funkcji zaznaczonej linii nie da się zmienić na teren; kolumna „Od
  linii m” i kontrola w karcie „Budynki”; polskie podpowiedzi narzędzia
- Szkic SVG: linia czerwona przerywana nad budynkami; `dane/dxf.py`:
  obiekt `linia` (otwarta polilinia); DXF koncepcji: warstwa
  `OSIEDLE_LINIA_ZABUDOWY`; przy okazji numeracja opisów w DXF tylko dla
  terenów (od ETAPu 173 liczyła też budynki — inaczej niż raport);
  raport: ostrzeżenie o przecięciu
- Testy: przecięcie i odległość, walidacja łamanej, szkic, DXF, raport;
  sprawdzone w przeglądarce (rysowanie łamanej myszą) 1300/390 px
- Pomoc: „Linia zabudowy”
- `DECISIONS.md`: D-183

## ETAP 176 — MPZP: karta terenu — punkty z inwentaryzacji obok planu i cen
Data: 2026-10-03
Status: zamknięty

- `teren/okolica.py`: kształt z GeoJSON (punkt / wielobok, WGS84),
  punkty ze wszystkich projektów do 50/100/250 m od kształtu (odległość
  w lokalnym układzie metrycznym), od najbliższego, najwyżej 50
- Trasa POST `/teren/okolica` — jak `/ceny/okolica` (D-117): MPZP nie
  czyta bazy Terenu
- Karta działki: sekcja „Z inwentaryzacji w terenie” (100 m): odległość
  albo „w działce”, projekt, wartości pól, uwagi, data, miniatura
  zdjęcia; tekst z formularzy przez `textContent`; bez punktów — ukryta.
  Karta ma teraz plan, ceny w okolicy i punkty z terenu w jednym wydruku
  (pozycja 217 planu — „punkty z Terenu przy działce” — zrobiona tutaj)
- Testy: trasa (zasięg, kolejność, punkt bez położenia, złe dane), karta;
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: „Inwentaryzacja na karcie działki”
- `DECISIONS.md`: D-184

## ETAP 177 — Atlas: gminy podobne do wybranej
Data: 2026-10-03
Status: zamknięty

- `atlas/typologia.py`: `podobne(skladowe, teryt)` — 10 najbliższych
  gmin w przestrzeni z (te same standaryzowane wskaźniki co typologia),
  odległość euklidesowa, wskaźnik największej różnicy z kierunkiem
- Trasa `/atlas/typologia/podobne` (parametry typologii + `gmina`)
- Strona typologii: „Gminy podobne do wybranej” — lista gmin z wyniku,
  tabela z wybraną gminą na górze, odległością, różnicą i wartościami
- Testy: kolejność podobnych, różnica, brak gminy, trasa; sprawdzone w
  przeglądarce 1300/390 px
- Pomoc: „Gminy podobne”
- `DECISIONS.md`: D-185

## ETAP 178 — Atlas: trend liniowy w gminach jako kartogram
Data: 2026-10-03
Status: zamknięty

- `atlas/trasy_trend.py`: wartości wskaźnika (także względnego) z każdego
  roku okresu (5–11 lat, cache BDL jak mapa), `trendy_gmin` — dla gminy z
  co najmniej 5 latami `raport.prognoza_trendu` (nachylenie, R²,
  stabilność) i zmiana w % średniej gminy
- Kartogram SVG `/atlas/trend.svg`: 5 klas (spadek > 3%, spadek
  0,5–3%, stabilnie ±0,5%, wzrost 0,5–3%, wzrost > 3% rocznie), przypis
  z liczbą trendów niestabilnych, gminy bez danych szare
- Strona `/atlas/trend`: wybór lat, mapa, tabele 10 najszybszych
  wzrostów i spadków z R², druk i SVG; link „Trend ↗” pod mapą Atlasu
- Testy: trend gmin (krótki szereg pominięty), strona, SVG, złe lata;
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: „Trend w gminach”
- `DECISIONS.md`: D-186

## ETAP 179 — Teren: tabela krzyżowa dwóch pytań z testem chi-kwadrat
Data: 2026-10-03
Status: zamknięty

- `teren/raport.py`: `tabela_krzyzowa` — liczności dla pól
  jednokrotnego wyboru i tak/nie, sumy, procent wiersza, test chi-kwadrat
  niezależności (puste wiersze i kolumny pominięte), V Craméra, liczba
  komórek z licznością oczekiwaną < 5; `_p_chi2` — wartość p z
  regularyzowanej funkcji gamma (szereg i ułamek łańcuchowy), bez scipy
- Raport projektu: sekcja „Tabela krzyżowa” z wyborem wierszy i kolumn
  (`?krzyz_a=&krzyz_b=`), opis wyniku słowami z progów (p < 0,05; V
  0,2 / 0,4), ostrzeżenie o małych licznościach; bez wyboru — formularz
  ukryty w druku
- Testy: liczności, chi² = 20 (2×2), p i V z wartości referencyjnych
  (tablice chi-kwadrat, scipy `chi2.sf`), raport; sprawdzone w
  przeglądarce 1300/390 px
- Pomoc: „Czy odpowiedzi na dwa pytania są ze sobą związane?”
- `DECISIONS.md`: D-187

## ETAP 180 — Teren: wykres tabeli krzyżowej w raporcie ankiety
Data: 2026-10-03
Status: zamknięty

- `teren/raport.py`: `wykres_krzyzowy_svg` — skumulowane słupki 100%
  dla każdego wiersza z odpowiedziami, procenty w słupkach (od ok. 4%
  szerokości), oś 0–100%; `kolory_kolumn` — skala zielony→czerwony dla
  pola-skali (ETAP 70), inaczej paleta raportu
- Raport: „Rozkład odpowiedzi w grupach” pod tabelą krzyżową — legenda
  kolumn i opis numerów wierszy w HTML (tekst użytkownika poza SVG)
- Procenty w tabeli krzyżowej z jednym miejscem po przecinku
- Słupki pojedynczych pytań są w zestawieniu od ETAPu 99 — ten ETAP
  dokłada wykres zależności dwóch pytań
- Test: liczba słupków, procenty, kolory; sprawdzone w przeglądarce
  1300/390 px
- Pomoc: akapit o tabeli krzyżowej
- `DECISIONS.md`: D-188

## ETAP 181 — Ceny: indeks cen z rokiem bazowym
Data: 2026-10-03
Status: zamknięty

- `ceny/analiza.py`: `indeks(szereg, rok_bazowy)` — wartość ÷ wartość w
  roku bazowym × 100 (None bez danych w roku bazowym); trasa
  `/ceny/szereg/<id>?bazowy=` zwraca też `indeks`
- Strona Ceny: przełącznik „Wykres: ceny / indeks”, rok bazowy z lat
  wspólnych dla wybranych miast, linia odniesienia 100, oś od najmniejszej
  wartości indeksu, opis pod wykresem; indeksy w osobnej pamięci podręcznej
  strony (miasto + rok)
- Zestawienie plików RCN: `rok_bazowy` (pierwszy rok z medianą we
  wszystkich plikach) i `indeks_lat` każdego pliku; tabela „Indeks median”
- Testy: indeks, trasa, zestawienie; sprawdzone w przeglądarce
- Pomoc: „Które miasto drożeje najszybciej?”
- `DECISIONS.md`: D-189

## ETAP 182 — Ceny: nietypowe transakcje RCN do sprawdzenia
Data: 2026-10-03
Status: zamknięty

- `ceny/rcn.py`: `nietypowe` — iloraz ceny za m² do mediany roku (lata
  z co najmniej 5 transakcjami), logarytm, granice Tukeya (1,5 IQR;
  poza 3 IQR — „bardzo nietypowa”); najwyżej 50 najbardziej odstających
  z odchyleniem w % i medianą roku; dla mieszkań i działek
- Trasa `/ceny/transakcje/<id>/nietypowe` z filtrami strony
- Strona transakcji: karta „Nietypowe transakcje” — opis granic w % mediany,
  tabela, „na mapie” (czerwony okrąg i przybliżenie)
- Testy: wybór odstających, za mało danych, trasa; sprawdzone w
  przeglądarce 1300/390 px
- Pomoc: „Nietypowe transakcje”
- `DECISIONS.md`: D-190

## ETAP 183 — Dostępność: kontury klas czasu dojścia (GeoJSON)
Data: 2026-10-03
Status: zamknięty

- `dostepnosc/wyniki.py`: `kontury(wyniki, kolumna)` — dla progów
  5/10/15/20/30 min suma komórek H3 z czasem ≤ próg (`h3.cells_to_geo`),
  od największego zasięgu; właściwości: minuty, komórki, powierzchnia km²
  (`h3.cell_area`), mieszkańcy; tylko wskaźniki czasu (i łączny)
- Trasa `/dostepnosc/kontury.geojson?plik=&kolumna=`; link „Zasięgi
  (wieloboki)” przy „GeoJSON do QGIS” (ukryty dla wskaźników innych niż
  czas i przy porównaniu scenariuszy)
- Testy: kontury na ręcznej siatce (liczba komórek, mieszkańcy,
  powierzchnia, jeden wielobok), trasa na pliku przykładowym, błędy;
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: „Zasięgi jako wieloboki”
- `DECISIONS.md`: D-191

## ETAP 184 — Dostępność: dzielnice w porównaniu scenariuszy przed/po
Data: 2026-10-03
Status: zamknięty

- `dostepnosc/obszary.py`: `porownanie_w_obszarach` — te same obszary
  w dwóch plikach (`w_obszarach` dla każdego), zmiana średniej, mediany i
  udziału w zasięgu 15 min (punkty procentowe)
- Trasa POST `/dostepnosc/plik/<nazwa>/obszary` przyjmuje `po` (plik
  scenariusza)
- Karta „Dzielnice” w trybie porównania: „przed → po”, zmiana czasu
  (krótszy czas zielony, dłuższy czerwony) i zmiana zasięgu; odświeża się
  po „Porównaj”
- Testy: liczby porównania na ręcznej siatce, trasa na plikach
  przykładowych; sprawdzone w przeglądarce 1300/390 px
- Pomoc: akapit „Dzielnice”
- `DECISIONS.md`: D-192

## ETAP 185 — Fiszki: zasłonięte fragmenty obrazu (image occlusion)
Data: 2026-10-03
Status: zamknięty

- `fiszki/baza.py`: tabela `zaslony_fiszek` (prostokąt we współrzędnych
  względnych 0–1, jedna zasłona na fiszkę); `fiszki/obrazy.py`:
  `sprawdz_zaslony` (1–12 prostokątów, w granicach obrazu, min. 1% boku),
  `zaslony_fiszek`
- Trasa POST `/fiszki/<pdf>/fiszki/<id>/zaslony` — z fiszki z obrazem
  nowe fiszki (po jednej na prostokąt) z tym samym plikiem obrazu,
  kotwicą i tematami; pytanie wspólne (domyślne „Co jest w zasłoniętym
  miejscu?”), odpowiedź osobna dla każdego fragmentu
- `zaslona` w liście fiszek, kolejce powtórki, quizie, pliku na telefon
  i wydruku; `fiszki/static/zaslona.js` — nakładka na obraz (pełna przy
  pytaniu, obrys po odsłonięciu); w pliku na telefon ta sama logika
  wbudowana (plik działa bez Warsztatu)
- Lista fiszek: „Zasłoń fragmenty” — rysowanie prostokątów myszą/palcem
  (pointer events), numery, „Cofnij ostatni”, pola odpowiedzi
- Testy: tworzenie, walidacja, wspólny plik obrazu po usunięciu wzoru,
  zasłona w kolejce, druku i pliku na telefon; sprawdzone w przeglądarce
  (rysowanie, powtórka 1300/390 px)
- Pomoc: „Zasłoń fragmenty rysunku”
- `DECISIONS.md`: D-193

## ETAP 186 — Fiszki: krzywa zapominania z dziennika powtórek
Data: 2026-10-03
Status: zamknięty

- `fiszki/statystyki_nauki.py`: `krzywa_zapominania` — dla każdej
  powtórki odstęp od poprzedniej powtórki tej samej fiszki (dni; powtórki
  w tej samej sesji pominięte) i wynik; udział „umiem/trudne” w
  przedziałach 1, 2–3, 4–7, 8–14, 15–30, 31+ dni (procent od 5 powtórek)
- Strona Fiszek: tabela „Po ilu dniach pamiętasz” z paskami w sekcji
  statystyk nauki
- Test: przedziały, pominięcie tej samej sesji, mało danych; sprawdzone
  w przeglądarce 1300/390 px
- Pomoc: „Po ilu dniach pamiętasz”
- `DECISIONS.md`: D-194

## ETAP 187 — Przepisy: „Moje przepisy” — artykuły z wielu aktów w jednym zbiorze
Data: 2026-10-03
Status: zamknięty

- `przepisy/baza.py`: tabela `moje_przepisy` (jednostka, akt, data
  dodania; do 300 jednostek), `przelacz_moje`, `moje_w_akcie`,
  `moje_przepisy` (z nazwą aktu i notatką, w kolejności tekstu aktu);
  usunięcie aktu czyści jego wpisy
- Trasy: POST `/przepisy/jednostki/<id>/moje` (przełącza), strona
  `/przepisy/moje` — jednostki pogrupowane po aktach, notatki, odnośnik
  do artykułu w akcie, „Usuń”, druk ze stopką
- Strona aktu: „☆ Moje / ★ Moje” przy każdej jednostce (`aria-pressed`);
  strona Przepisów: link „★ Moje przepisy (N)”
- Test: przełączanie, kolejność, notatki, licznik, usunięcie aktu;
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: „Jak zebrać artykuły z kilku ustaw w jednym miejscu?”
- `DECISIONS.md`: D-195

## ETAP 188 — Arkusz ODS bez zależności (`dane/arkusz.py`), eksport Atlasu
Data: 2026-10-03
Status: zamknięty

- `dane/arkusz.py`: `arkusz_ods` — ZIP z `mimetype` (pierwszy, bez
  kompresji), `META-INF/manifest.xml` i `content.xml`; kilka arkuszy,
  liczby jako `float`, tekst escapowany, pogrubiony nagłówek, szerokości
  kolumn z najdłuższego tekstu, przypisy kursywą pod tabelą
- Atlas: `/atlas/eksport.ods` — te same wiersze co CSV (`_wiersze_eksportu`,
  wspólna funkcja), nazwa wskaźnika i źródło w przypisach; link „Arkusz
  ODS” obok „Pobierz CSV”
- Testy: struktura ODS (kolejność i kompresja `mimetype`, poprawny XML,
  typy komórek, escapowanie), eksport Atlasu; sprawdzone w przeglądarce
- Pomoc: „Arkusz ODS”
- `DECISIONS.md`: D-196

## ETAP 189 — Arkusz ODS w Cenach, Osiedlu i Terenie
Data: 2026-10-03
Status: zamknięty

- Ceny: `/ceny/porownanie.ods` — te same szeregi miast co CSV
  (`_tabela_porownania`, wspólna funkcja), link „ODS” obok „CSV”
- Teren: `/teren/projekty/<id>.ods` — tabela punktów jak CSV
  (`_wiersze_punktow`), link „ODS” na stronie projektu
- Osiedle: `/osiedle/koncepcje/<id>.ods` — zakładki Bilans, Wskaźniki
  (z terenów i z budynków, zgodność z planem), Program, Koszty, Budynki
  (`arkusze_koncepcji`); link „ODS” przy koncepcji
- CSV bez zmian w treści (wspólne funkcje wierszy dla obu formatów)
- Testy: arkusze Osiedla (nazwy zakładek, treść), Terenu (liczby jako
  liczby), Cen
- Pomoc: akapit „Arkusz ODS”
- `DECISIONS.md`: D-197

## ETAP 190 — Przegląd i dokumentacja po ETAPach 171–189
Data: 2026-10-03
Status: zamknięty

- Przegląd: testy 609/0, pokrycie 95% (najsłabsze jak dotąd: ULDK,
  granice PRG — gałęzie błędów usług), pyflakes: zbędny import `BUDYNEK`
  w `osiedle/dxf_koncepcji.py` usunięty
- Przegląd stron w Chromium: 90 stron, 0 problemów; `/atlas/gminy-w-czasie`
  dopisana do stron wymagających parametrów, dodany raport z tabelą
  krzyżową
- README: funkcje z ETAPów 171–189 w tabeli modułów, ODS w opisie
  eksportów, nowe pliki w „Gdzie co jest w kodzie”
- ARCHITEKTURA: `dane/arkusz.py`, powiązanie MPZP → `/teren/okolica`
- PORTFOLIO: liczby na ETAP 190 (18 900 wierszy Pythona, 9 200 testów,
  9 500 JS, 609 testów, 90 stron)
- PLAN 171–250: podsumowanie serii; pozycja 217 zastąpiona (punkty z
  Terenu przy działce zrobione w ETAPie 176)
- `DECISIONS.md`: D-198

## ETAP 191 — MPZP: hurtowe sprawdzenie listy działek
Data: 2026-10-03
Status: zamknięty

- `mpzp/trasy_hurtowe.py`: `wpisy_z_tekstu` (wiersze, średniki,
  tabulatory; przecinki tylko między pełnymi identyfikatorami; bez
  powtórzeń), `sprawdz_wpis` — działka po identyfikatorze albo „obręb
  numer” (ULDK; kilka trafień — „niejednoznaczny”), powierzchnia,
  przeznaczenie z WFS gminy albo krajowej integracji planów, stan i uwaga;
  błąd jednej działki nie przerywa listy
- Strona `/mpzp/hurtowo` (formularz, do 30 działek, zapytania po kolei,
  bez zapisu w historii): tabela z opisem symboli i linkiem do karty
  działki; link „Lista działek” na stronie MPZP
- Testy: rozbiór tekstu, stany (plan gminy, plan krajowy, bez trafienia,
  niejednoznaczny), limit, pusty wpis, brak zapisu w historii; sprawdzone
  w przeglądarce 1300/390 px (tabela przewijana w bok na telefonie)
- Pomoc: „Jak sprawdzić wiele działek naraz?”
- `DECISIONS.md`: D-199

## ETAP 192 — MPZP: wynik listy działek — druk i arkusz ODS
Data: 2026-10-03
Status: zamknięty

- Trasa POST `/mpzp/hurtowo.ods` — ta sama lista sprawdzona ponownie
  i zapisana jako arkusz (wpis, działka, powierzchnia, przeznaczenie, opis
  symbolu, źródło planu, stan, uwaga) z przypisem o źródłach
- Strona listy: przyciski „Arkusz ODS” i „Drukuj / zapisz PDF”, stopka
  wydruku; w druku bez formularza, tabela bez minimalnej szerokości
- Test: druk (stopka), ODS (liczby jako liczby, stany, źródło); sprawdzone
  w przeglądarce 1300/390 px
- Pomoc: akapit o liście działek
- `DECISIONS.md`: D-200

## ETAP 193 — Atlas: gminy o podobnym profilu w raporcie gminy
Data: 2026-10-03
Status: zamknięty

- Trasa `/atlas/raport-gminy/<id>/podobne` — wskaźniki zestawu raportu
  (co najmniej 2) w najnowszym roku, w którym gmina ma dane wszystkich,
  `typologia.podobne` (ETAP 177), 5 najbliższych gmin
- Raport gminy: sekcja „Gminy o podobnym profilu” wczytywana po tabeli
  (odległość i wskaźnik największej różnicy); bez danych — ukryta.
  Trend (prognoza z R²) był w raporcie od ETAPu 92, więc ETAP dokłada
  tylko podobieństwo
- Test: trasa (pusty zestaw, kolejność podobnych, rok); sprawdzone w
  przeglądarce 1300/390 px
- Pomoc: akapit „Gminy podobne”
- `DECISIONS.md`: D-201

## ETAP 194 — Atlas: stabilność rankingu wskaźnika złożonego
Data: 2026-10-03
Status: zamknięty

- `atlas/zlozony.py`: `stabilnosc` — miejsca gmin obecnych we wszystkich
  latach (przeliczone wśród nich), zmiana miejsca od pierwszego do
  ostatniego roku, rho Spearmana skrajnych lat z opisem siły
  (`statystyki._rangi`, `_pearson`, `opis_sily`)
- Trasa `/atlas/wskaznik-zlozony/lata?…&lata=` (2–6 lat) — ta sama
  procedura `_policz` dla każdego roku
- Strona wskaźnika złożonego: „Stabilność rankingu w latach” (domyślnie
  rok − 8, − 4, rok), tabela miejsc ze strzałkami zmian, opis rho
- Testy: przeliczanie miejsc, gminy spoza wszystkich lat, rho, trasa;
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: „Stabilność rankingu”
- `DECISIONS.md`: D-202

## ETAP 195 — Osiedle: cień od budynków zamiast od terenów
Data: 2026-10-03
Status: zamknięty

- `osiedle/cien.py`: gdy koncepcja ma budynki (ETAP 173), źródłem cienia
  są obrysy budynków z ich kondygnacjami; bez budynków — jak dotąd tereny
  MN/MW/U; obrysy budynków odejmowane od strefy cienia; wynik ma klucz
  `zrodlo` („budynki” albo „tereny”)
- Osiedle i raport: nagłówek „Budynek”, etykiety „budynek N”, opis źródła
  cienia nad tabelą
- Test: cień od budynku krótszy niż od terenu, źródło „budynki”;
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: akapit „Odległości od granicy i cień”
- `DECISIONS.md`: D-203

## ETAP 196 — Osiedle: etapy realizacji — program i koszty na etap
Data: 2026-10-03
Status: zamknięty

- `osiedle/etapy.py`: `etap_terenu` (numer 1–10 z właściwości terenu,
  `MAKS_ETAPOW`), `etapy` — dla każdego etapu program (`program.py`) i
  koszty (`koszty.py`) z terenów tego etapu, bez pozycji gruntu; sumy
  narastające mieszkań i kosztów; grupa „bez etapu”
- `bilans.py`: walidacja etapu razem z parametrami terenu, klucz `etapy`
- Osiedle: pole „Etap” przy zaznaczonym terenie, karta „Etapy realizacji”
  z ostrzeżeniami o brakujących miejscach postojowych w etapie
- Raport: tabela etapów; arkusz ODS: zakładka „Etapy”
- Test: dwa etapy i tereny bez etapu, grunt poza etapami, parking nie
  przechodzi między etapami, błędne numery, raport i ODS; sprawdzone w
  przeglądarce 1300/390 px (także zmiana etapu w panelu)
- Pomoc: akapit „Etapy realizacji”
- `DECISIONS.md`: D-204

## ETAP 197 — Osiedle: chłonność terenu wg ustaleń planu
Data: 2026-10-03
Status: zamknięty

- `osiedle/chlonnosc.py`: `chlonnosc` — dopuszczalna powierzchnia
  całkowita z max intensywności i z max wskaźnika zabudowy × max
  kondygnacji (decyduje mniejsza), minimum z min intensywności,
  wykorzystanie i zapas (z terenów i z budynków), mieszkania MW z
  założeń programu (`_w_dol` jak w `program.py`)
- `bilans.py`: klucz `chlonnosc` (ta sama podstawa co wskaźniki)
- Osiedle: blok „Chłonność terenu” w karcie wskaźników — pasek
  wykorzystania (czerwony przy przekroczeniu) i opis
- Raport: tabela chłonności pod zgodnością; ODS: wiersze w zakładce
  Wskaźniki
- Test: oba ograniczenia, minimum, budynki, przekroczenie, raport;
  sprawdzone w przeglądarce 1300/390 px (także zmiana ustalenia)
- Pomoc: akapit o ustaleniach planu
- `DECISIONS.md`: D-205

## ETAP 198 — Teren: trasa obchodu punktów
Data: 2026-10-03
Status: zamknięty

- `teren/trasa.py`: `odleglosc_m` (haversine), `trasa` — najbliższy
  sąsiad od startu (wybranego albo punktu najdalszego od środka) i
  poprawki 2-opt dla trasy otwartej; długość, odcinki, czas marszu
  (`PREDKOSC_KMH=4.5`), `MAKS_PUNKTOW_TRASY=200`; `gpx` — GPX 1.1 z
  punktami (wpt) i trasą (rte), numery kolejności jako nazwy
- Trasy `/teren/projekty/<id>/trasa` (JSON) i `/trasa.gpx`
  (`?punkty=` — puste: wszystkie z położeniem, `?start=`)
- Projekt: karta „Trasa obchodu” (punkty widoczne na mapie), numery
  przy punktach, przerywana linia, „Zacznij trasę tutaj” w dymku; zmiana
  filtra ukrywa nieaktualną trasę
- Testy: punkty na prostej, stały start, 2-opt nie wydłuża, limity,
  trasa i GPX (escape nazwy, poprawny XML); sprawdzone w przeglądarce
  1300/390 px
- Pomoc: „W jakiej kolejności obejść punkty?”
- `DECISIONS.md`: D-206

## ETAP 199 — Teren: punkty „do sprawdzenia” w formularzu na telefon
Data: 2026-10-03
Status: zamknięty

- `teren/routes.py`: `formularz.html?do_sprawdzenia=3,1,2` — punkty z
  położeniem w podanej kolejności (bez powtórzeń, do 200), krótki opis z
  wartości pól i początku uwag (`_opis_do_sprawdzenia`, liczby bez „.0”)
- Formularz na telefon: karta „Do sprawdzenia” (numer, opis, odległość
  od pozycji z GPS, przycisk ✓), fioletowe pierścienie z numerem na
  mapie offline (szare po sprawdzeniu); stan „sprawdzony” w
  localStorage telefonu (z try/catch)
- Projekt: link „Formularz z tymi punktami do sprawdzenia” po wyznaczeniu
  trasy (ETAP 198)
- Test: kolejność, duplikaty, punkty bez GPS, opis, zabezpieczenie
  tekstu w JSON, błędne numery; sprawdzone w przeglądarce 390/1300 px
  (symulowany GPS, ✓ po przeładowaniu)
- Pomoc: akapit „Punkty do sprawdzenia w telefonie”
- `DECISIONS.md`: D-207

## ETAP 200 — Półmetek: przegląd i podsumowanie ETAPów 151–199
Data: 2026-10-03
Status: zamknięty

- Przegląd: testy 621/0, pokrycie 95% (najsłabsze: `atlas/trasy_raport.py`,
  `dane/uldk.py`, `atlas/granice.py` — 85%, gałęzie błędów usług),
  pyflakes bez ostrzeżeń
- Przegląd stron w Chromium: 92 strony, 0 problemów
- README: funkcje z ETAPów 191–199 (lista działek naraz, gminy podobne
  w raporcie, stabilność wskaźnika złożonego, cień od budynków, etapy,
  chłonność, trasa obchodu, punkty do sprawdzenia) i nowe pliki
- ARCHITEKTURA: formaty pisane ręcznie poza `dane/` (GPX), dane wpisywane
  w plik formularza na telefon
- PORTFOLIO: liczby na ETAP 200 (19 500 wierszy Pythona, 9 500 testów,
  9 700 JS, 621 testów, 92 strony)
- PLAN 171–250: podsumowanie półmetka, plan 201–250 bez zmian
- `DECISIONS.md`: D-208

## ETAP 201 — Ceny: korekta cen na datę w wycenie porównawczej
Data: 2026-10-03
Status: zamknięty

- Przegląd planu: wycena porównawcza działki działa od ETAPu 107, a karta
  do druku od ETAPu 113 (szablon rozróżnia działki) — pozycje 201 i 202
  zastąpione (D-198): 201 → korekta na datę, 202 → zapisane wyceny
- `ceny/rcn.py`: `wspolczynniki_czasu` — mediany ceny m² w latach z co
  najmniej `MIN_W_ROKU_KOREKTY=10` transakcjami (te same filtry, cały
  plik), rok bazowy = ostatni; `podobne` zwraca `korekta` (mediana,
  kwartyle, szacunek po korekcie, współczynniki, pominięte) i
  `cena_m2_skorygowana` przy transakcjach
- Transakcje: wynik po korekcie pod kafelkami, współczynniki, kolumna
  „Za m² (rok)”; przy działkach uwaga o filtrze przeznaczenia
- Karta wyceny: wynik i współczynniki korekty, kolumna w tabeli, opis
  ograniczeń
- Testy: współczynniki, pominięte lata, mediana po korekcie, trasa i karta;
  sprawdzone w przeglądarce 1300 (działki) / 390 px (mieszkania)
- Pomoc: akapit o wycenie porównawczej; PLAN: pozycje 201–202
- `DECISIONS.md`: D-209

## ETAP 202 — Ceny: zapisane wyceny porównawcze
Data: 2026-10-03
Status: zamknięty

- `ceny/baza.py`: tabela `rcn_wyceny` (parametry jako zapytanie URL,
  dzień zapisu, liczba, mediana, szacunek, szacunek po korekcie; kasowana
  z plikiem), `wyceny_rcn`, `wycena_rcn`, `zapisz_wycene_rcn`,
  `usun_wycene_rcn`
- `ceny/trasy_rcn.py`: `GET/POST /ceny/transakcje/<id>/wyceny` (parametry
  w adresie jak w `/podobne`, tylko znane, niepuste pola — `POLA_WYCENY`;
  `MAKS_WYCEN=50`), `DELETE /ceny/transakcje/wyceny/<id>`; karta wyceny
  z `?zapisana=` pokazuje wynik z dnia zapisu obok dzisiejszego
- Transakcje: formularz „Zapisz wycenę” pod wynikiem, lista „Zapisane
  wyceny” (rodzaj, dzień, kwota, karta, usuń)
- Test: zapis, oczyszczone parametry, karta z zapisaną, błędy, usuwanie;
  sprawdzone w przeglądarce 1300/390 px
- Pomoc: akapit „Zapisane wyceny”
- `DECISIONS.md`: D-210

## ETAP 203 — Ceny: premia rynku pierwotnego w latach
Data: 2026-10-03
Status: zamknięty

- `ceny/rcn.py`: `premia_w_latach` — `_rynki` (ETAP 135) w każdym roku:
  mediany pierwotnego i wtórnego, premia przy co najmniej `MIN_W_RYNKU`
  transakcjach na obu rynkach; `statystyki` zwraca `premia_lat` (tylko
  mieszkania, pusta przy filtrze jednego rynku)
- Transakcje: tabela „Premia rynku pierwotnego w latach” z paskiem
  (ujemna premia innym kolorem) pod tabelą pięter
- Raport do druku: ta sama tabela, niezależnie od narysowanych obszarów
- Test: premia w latach, rok z za małą liczbą, filtr rynku, trasa i
  raport; sprawdzone w przeglądarce 1300/390 px
- Pomoc: zdanie przy tabeli pięter
- `DECISIONS.md`: D-211

## ETAP 204 — Dostępność: dostępność według grup mieszkańców (wiek)
Data: 2026-10-03
Status: zamknięty

- `dostepnosc/wyniki.py`: kolumny z prefiksami `PREFIKSY_GRUP`
  (`ludnosc_`, `mieszkancy_`, `wiek_`…) czytane jako wagi, nie wskaźniki
  (do `MAKS_GRUP=8`, bez wartości ujemnych); `udzialy_grup` — dla każdej
  grupy liczba i procent osób w zasięgu progów 5–30 min oraz mediana
  czasu ważona liczbą osób (`_mediana_wazona`); w statystykach czasu
  (także łącznego) klucz `grupy`
- `dostepnosc/model.py`: `csv_wynikow` przepisuje kolumny grup — szybki
  model ich nie gubi
- Strona: tabela „Grupy mieszkańców” pod kafelkami; raport do druku:
  wiersze grup w tabeli „Udział w zasięgu”; opis formatu pliku
- Test: wczytanie, udziały, mediana ważona, pominięte komórki bez czasu,
  limity, szybki model, trasa i raport; sprawdzone w przeglądarce
  1300/390 px na pliku przykładowym z dodanymi grupami
- Pomoc: „Dostępność dla dzieci, seniorów i innych grup”
- `DECISIONS.md`: D-212

## ETAP 205 — Dostępność: raport dzielnic do druku
Data: 2026-10-03
Status: zamknięty

- `dostepnosc/druk.py`: `mapa_svg(…, obszary=)` — kontury obszarów i
  numer w kółku (bez nazw w SVG), pozycja w legendzie
- `dostepnosc/obszary.py`: `kontury_do_mapy` — pierścienie zewnętrzne
  (także wieloboki złożone) i punkt na numer wewnątrz obszaru
- `dostepnosc/routes.py`: `GET /dostepnosc/raport-dzielnic` (strona) i
  `POST /dostepnosc/raport-dzielnic.svg` (mapa); obszary przysyła
  przeglądarka (localStorage, ETAP 163), tabela z istniejącego
  `POST /plik/<nazwa>/obszary`
- Szablon `raport_dzielnic.html`: mapa jako obraz z Bloba, tabela z
  nazwami przez `textContent`, opis metody, komunikat bez obszarów
- Dostępność: link „Raport dzielnic do druku” w karcie Dzielnice (ukryty
  w porównaniu scenariuszy)
- Test: kontury, strona, mapa bez nazw, błędy; sprawdzone w przeglądarce
  1300/390 px
- Pomoc: akapit o dzielnicach
- `DECISIONS.md`: D-213

## ETAP 206 — Fiszki: powtórka z przeplataniem tematów
Data: 2026-10-03
Status: zamknięty

- `fiszki/powtorki.py`: `przeplec` — kolejność, w której sąsiednie
  fiszki są z różnych grup (zachłannie: grupa inna niż poprzednia, z
  największą liczbą pozostałych; w grupie kolejność wejściowa)
- `fiszki/trasy_nauka.py`: kolejka zwraca `tematy` każdej fiszki;
  `?przeplatanie=1` (bez filtra tematu) — grupa = pierwszy temat, bez
  tematu plik PDF; działa też w trybie „przed egzaminem” (po losowaniu)
- Powtórka: przełącznik „Przeplataj tematy” (localStorage), zmiana w
  trakcie układa na nowo pozostałe karty (bieżąca z odpowiedzią zostaje),
  etykieta tematu na karcie
- Testy: kolejność i zachowanie kolejności w grupie, kolejka z
  przeplataniem, filtr tematu, przełącznik na stronie; sprawdzone w
  przeglądarce 1300/390 px
- Pomoc: akapit „Przeplataj tematy”
- `DECISIONS.md`: D-214

## ETAP 207 — Fiszki: wyjaśnienie po odsłonięciu odpowiedzi
Data: 2026-10-03
Status: zamknięty

- `fiszki/baza.py`: tabela `wyjasnienia_fiszek` (jedno na fiszkę, źródło
  „wlasne” albo „gemini”, kasowane z fiszką)
- `fiszki/wyjasnienia.py`: `wszystkie`, `zapisz` (normalizacja spacji, do
  1500 znaków), `usun`
- `dane/gemini.py`: `wyjasnij_fiszke` — prompt tylko z pytaniem,
  odpowiedzią i fragmentem źródła; `sprawdz_liczby` odrzuca liczby spoza
  nich
- `fiszki/trasy_nauka.py`: `POST/DELETE /fiszki/wyjasnienie/<id>` i
  `POST /fiszki/wyjasnienie/<id>/gemini`; kolejka powtórki zwraca
  `wyjasnienie`
- Powtórka: blok „Wyjaśnienie” po odsłonięciu (źródło przy nagłówku),
  przyciski Gemini i własnego, edycja i usuwanie
- Test: własne, walidacja, Gemini z liczbą ze źródła i obcą, brak klucza,
  usuwanie, kaskada; sprawdzone w przeglądarce 1300/390 px (Gemini
  podmieniony)
- Pomoc: akapit „Wyjaśnienie po odsłonięciu”
- `DECISIONS.md`: D-215

## ETAP 208 — Przepisy: przeniesienie notatek i „Moich przepisów” na nowszy tekst
Data: 2026-10-03
Status: zamknięty

- Przegląd planu: sprawdzanie nowszego tekstu jednolitego działa od
  ETAPu 101 — pozycja 208 zastąpiona (D-198) tym, czego po pobraniu
  nowszego tekstu brakowało: notatki zostawały przy starym akcie
- `przepisy/przeniesienie.py`: `przenies` — jednostki dopasowane po
  oznaczeniu (bez wielkości liter i nadmiarowych spacji); notatka
  kopiowana albo dopisywana pod istniejącą (bez dublowania przy
  powtórzeniu), „Moje przepisy” dodawane (z limitem zbioru); raport:
  liczby, bez odpowiednika, niejednoznaczne, zmieniony tekst
- `POST /przepisy/akty/<id>/przenies-z/<stary_id>`; strona aktu: karta
  przeniesienia ze źródłami (akty z notatkami albo „Moimi”), otwarta z
  `?z=` po pobraniu nowszego tekstu z Dziennika Ustaw
- Test: przeniesienie, dopisanie, uchylony i zmieniony artykuł, stary
  akt bez zmian, powtórzenie, błędy; sprawdzone w przeglądarce
  1300/390 px
- Pomoc: akapit „Notatki na nowy tekst”; PLAN: pozycja 208
- `DECISIONS.md`: D-216

## ETAP 209 — Przepisy: notatki do pliku tekstowego (Markdown)
Data: 2026-10-03
Status: zamknięty

- `przepisy/eksport_notatek.py`: `plik_markdown` — nagłówek, data
  eksportu, akt po akcie, przy jednostce oznaczenie, rozdział, strona
  PDF, tekst przepisu jako cytat (opcjonalnie) i notatka bez zmian
- Trasy `/przepisy/akty/<id>/notatki.md`, `/przepisy/notatki.md`
  (wszystkie akty), `/przepisy/moje.md` („Moje przepisy”); `?bez_tekstu=1`
  — same notatki
- Linki: „Notatki do pliku” na stronie aktu (gdy są notatki), „Wszystkie
  notatki do pliku” na stronie Przepisów, „Do pliku (.md)” w „Moich
  przepisach”
- Test: treść pliku, tylko jednostki z notatką, bez tekstu, wszystkie,
  moje, linki, 404; sprawdzone w przeglądarce 1300/390 px (pobranie
  plików)
- Pomoc: akapit „Notatki do pliku”
- `DECISIONS.md`: D-217

## ETAP 210 — Przegląd i dokumentacja po ETAPach 201–209
Data: 2026-10-03
Status: zamknięty

- Przegląd: testy 632/0, pokrycie 95% (najsłabsze bez zmian: raport
  gminy, ULDK, granice PRG — gałęzie błędów usług), pyflakes czysty
- Przegląd stron w Chromium: 96 stron, 0 problemów; `/dostepnosc/raport`
  i `/dostepnosc/raport-dzielnic` dopisane z parametrami; przegląd
  znalazł poziome przewijanie raportu Dostępności na 390 px (tabela
  „Udział w zasięgu” z sześcioma kolumnami) — tabele raportu w
  przewijanym kontenerze
- Poprawka dokumentacji ETAPu 209: usunięte niesprawdzone twierdzenie o
  otwieraniu plików .md w Wordzie (Pomoc, D-217, podpowiedzi linków)
- README: funkcje z ETAPów 201–209 i nowe pliki; ARCHITEKTURA: stan z
  przeglądarki w raporcie (D-213); PORTFOLIO: liczby na ETAP 210
- PLAN 171–250: podsumowanie serii 201–209
- `DECISIONS.md`: D-218

## ETAP 211 — Strona główna: przypięte rzeczy
Data: 2026-10-03
Status: zamknięty

- `przypiete.py`: lista w `instance/przypiete.json` (zapis przez plik
  tymczasowy i `os.replace`), `przypnij` (tylko adresy tej aplikacji —
  zaczynające się od „/”, bez „//”, „\\” i znaków sterujących; tytuł;
  bez duplikatów; `MAKS_PRZYPIETYCH=12`), `odepnij`, `wczytaj`
  (uszkodzony plik → pusta lista)
- `app.py`: `POST /przypiete`, `POST /przypiete/usun`; strona główna
  dostaje listę przypiętych i znacznik przy „Wróć do pracy”
- Strona główna: sekcja „Przypięte” z ✕, przycisk 📌 przy pozycjach
  „Wróć do pracy”, które nie są przypięte
- Test: przypinanie, duplikat, złe adresy, limit, odpinanie, uszkodzony
  plik; sprawdzone w przeglądarce 1300/390 px
- Pomoc: zdanie o przypinaniu
- `DECISIONS.md`: D-219

## ETAP 212 — Kosz: cofnięcie usunięcia (fiszki, koncepcje, projekty)
Data: 2026-10-03
Status: zamknięty

- `fiszki/kosz.py`: usunięty PDF albo fiszka — wiersze powiązanych tabel
  (`TABELE_PDF`, `TABELE_FISZKI`) jako JSON w tabeli `kosz`, pliki (PDF,
  wycinki) w `instance/fiszki/kosz/`; wycinek wspólny z innymi fiszkami
  (zasłony) kopiowany, nie przenoszony; przywrócenie z tymi samymi
  numerami; `TABELE_ZOSTAJA` — historia odpowiedzi i wyniki z telefonu
  (bez kaskady) zostają; `wyczysc_stare` po 30 dniach
- Fiszki: `DELETE` fiszki zwraca `kosz_id`, „Cofnij” po usunięciu,
  `POST /fiszki/kosz/<id>/przywroc`, sekcja „Kosz” na stronie Fiszek,
  potwierdzenie usunięcia pliku mówi o koszu
- Osiedle: kolumna `usunieto` (koncepcja znika z list, rysunek zostaje),
  `GET /osiedle/kosz`, `POST /osiedle/koncepcje/<id>/przywroc`, kosz w
  karcie koncepcji
- Teren: kolumna `usunieto` w projektach (punkty i zdjęcia zostają),
  `POST /teren/projekty/<id>/przywroc`, kosz na liście projektów;
  usunięcie na dobre (ze zdjęciami) po 30 dniach
- Testy: kosz fiszki i PDF-a (z tematami, powtórkami, wyjaśnieniem,
  egzaminem, obrazem), kolejność przywracania, wygaśnięcie, kontrola, że
  każda tabela z `fiszka_id`/`pdf_id` jest w koszu; kosz koncepcji i
  projektów; sprawdzone w przeglądarce 1300/390 px
- Pomoc: akapit „Kosz”
- `DECISIONS.md`: D-220

## ETAP 213 — Osiedle: koncepcja jako GeoPackage dla QGIS
Data: 2026-10-03
Status: zamknięty

- `dane/geopaczka.py`: zapis GeoPackage przez sqlite3 (bez GDAL):
  wymagane tabele (`gpkg_spatial_ref_sys` z EPSG:4326 i 2180,
  `gpkg_contents`, `gpkg_geometry_columns`), warstwy z blobem „GP” +
  WKB, tabela `layer_styles` ze stylem QML domyślnym dla warstwy
- `osiedle/gpkg_koncepcji.py`: warstwy tereny, budynki, obszar,
  linia_zabudowy w PL-1992 (`gauss_kruger` jak w DXF), atrybuty
  (funkcja, numer, parametry, etap, pole), style QML: tereny
  kategoryzowane po funkcji w kolorach aplikacji, budynki, kontur obszaru,
  czerwona przerywana linia
- Trasa `/osiedle/koncepcje/<id>.gpkg`, link „QGIS (GPKG)” przy koncepcji
- Sprawdzenie poza testami: plik czytany przez GDAL 3.12 (pyogrio w
  osobnym środowisku, nie zależność projektu) — warstwy, typy, EPSG:2180,
  atrybuty; przeliczenie PL-1992 zgodne z pyproj (poniżej 1 mm). Wygląd
  stylów w samym QGIS niesprawdzony (brak QGIS w środowisku)
- Test: struktura pliku, układ, nagłówek bloba, pola, style jako
  poprawny XML; sprawdzone w przeglądarce 1300/390 px
- Pomoc: akapit „Do QGIS”; PLAN: pozycje 213–214
- `DECISIONS.md`: D-221

## ETAP 214 — Teren i Ceny: GeoPackage ze stylami dla QGIS
Data: 2026-10-03
Status: zamknięty

- `dane/geopaczka.py`: klocki stylów QML (`symbol_wypelnienia`,
  `symbol_linii`, `symbol_punktu`, `styl_pojedynczy`, `styl_kategorie`,
  `styl_przedzialy`, `kolor_qml` — także kolory `hsl()` ze skali Terenu);
  nazwy tabel i kolumn w cudzysłowie SQL (nazwy pól wpisuje użytkownik);
  Osiedle (ETAP 213) przepisane na te klocki
- `teren/gpkg_projektu.py`: warstwa punkty w PL-1992, pola formularza jako
  kolumny (liczby jako liczby, nazwy kolidujące ze stałymi kolumnami z
  przyrostkiem), styl wg pierwszego pola wyboru (`kolory_pola` z raportu)
- `ceny/gpkg_rcn.py`: transakcje (filtry strony) w pięciu klasach ceny za
  m² (kwintyle, `KOLORY_KLAS`), obszary z konturami `KOLORY_OBSZAROW`
- Trasy `/teren/projekty/<id>.gpkg`, `/ceny/transakcje/<id>.gpkg`; linki
  na stronie projektu i pod mapą transakcji
- Sprawdzenie GDAL-em 3.12 (poza projektem): warstwy, EPSG:2180,
  położenie (Poznań, Kraków) poprawne
- Testy: kolumny, cudzysłów i kolizja nazw, punkty bez położenia, klasy
  i obszary, układ; sprawdzone w przeglądarce 1300/390 px
- Pomoc: zdania przy eksporcie Terenu i Cen
- `DECISIONS.md`: D-222

## ETAP 215 — Atlas: powiaty zamiast gmin — dane i granice (serwer)
Data: 2026-10-03
Status: zamknięty

- `atlas/routes.py`: parametr `poziom` (`gminy` domyślnie albo `powiaty`,
  `POZIOMY`) w `_parametry_zapytania`; `_wartosci`, `_wartosci_wskaznika`
  i `_policz_dane` przyjmują poziom — powiaty z `bdl.wartosci_dla_powiatow`
  (ETAP 103, TERYT 4-znakowy); wynik ma klucz `poziom`; eksport CSV/ODS i
  wydruk działają tak samo (ten sam słownik parametrów)
- `atlas/granice.py`: `granice_powiatow` — powiaty jako połączenie gmin z
  tych samych granic PRG (TERYT gminy zaczyna się od TERYT powiatu);
  domknięcie szczelin po osobnym uproszczeniu gmin (bufor ±0,0002°),
  usunięcie resztkowych dziur, cache w `instance/atlas/granice/`
- Trasa `/atlas/granice-powiatow/<teryt_woj>`
- Przełącznik na stronie Atlasu i kartogram — ETAP 216
- Testy: łączenie gmin ze szczeliną, nazwa miasta na prawach powiatu,
  cache, dane i CSV dla powiatów, błędny poziom; atrapy `_wartosci` w
  testach Atlasu przyjmują poziom; strona Atlasu sprawdzona w
  przeglądarce bez zmian 1300/390 px
- `DECISIONS.md`: D-223

## ETAP 216 — Atlas: przełącznik gminy/powiaty w kartogramie i rankingu
Data: 2026-10-03
Status: zamknięty

- Atlas: pole „Jednostki: gminy | powiaty”; w trybie powiatów dane z
  `poziom=powiaty`, granice z `/atlas/granice-powiatow/` (ETAP 215),
  nagłówek i wyszukiwarka rankingu „powiatów”, bez profilu gminy, „Gminy
  w czasie” i trendu (są dla gmin)
- `atlas/routes.py`: `_granice_poziomu`; poziom w `/klasy`,
  `/autokorelacja` (sąsiedztwo powiatów w osobnym kluczu cache),
  `/korelacja`, `/eksport.geojson`; opis Gemini z faktami o powiatach
  (`statystyki.fakty_do_opisu(…, poziom)`, `JEDNOSTKI_OPISU`)
- `atlas/trasy_druk.py`: mapa do druku i małe mapy w latach z granicami
  poziomu, podpis „Powiaty województwa …”, sąsiedztwo LISA/Gi* dla
  powiatów; usunięte zbędne importy
- `atlas/static/korelacja.js`: poziom w zapytaniu korelacji
- Poprawka z przeglądarki: `granice_powiatow` tworzy folder cache przed
  zapisem
- Testy: klasy, autokorelacja z granic powiatów (gminy nie są pobierane),
  GeoJSON, mapa do druku, fakty opisu, pole na stronie, folder cache;
  sprawdzone w przeglądarce 1300/390 px (przełączanie w obie strony)
- Pomoc: „Powiaty zamiast gmin”
- `DECISIONS.md`: D-224

## ETAP 217 — MPZP: „Moje działki” do arkusza ODS
Data: 2026-10-03
Status: zamknięty

- `mpzp/trasy_zapisane.py`: `/mpzp/zapisane.ods` — zakładka „Działki”
  (numeracja jak w zestawieniu do druku, przeznaczenie i opis symbolu,
  powierzchnia, WGS84 i PL-2000 jako liczby, notatka, data) i „Według
  przeznaczenia” (`zestawienie.wedlug_przeznaczenia`); zapis przez
  `dane/arkusz.py` (D-196)
- MPZP: link „ODS” obok „CSV” w panelu „Moje działki”
- Pozycja planu 217 zastąpiona w ETAPie 190 (D-198): punkty z Terenu przy
  działce są od ETAPu 176
- Test: obie zakładki, liczby, działka bez planu, link; sprawdzone w
  przeglądarce 1300/390 px
- Pomoc: zdanie przy zestawieniu działek
- `DECISIONS.md`: D-225

## ETAP 218 — Osiedle: własne zestawy założeń programu (normatywy)
Data: 2026-10-03
Status: zamknięty

- `osiedle/baza.py`: tabela `zestawy_zalozen` (nazwa unikalna, założenia
  JSON), `zestawy`, `zapisz_zestaw` (ta sama nazwa zastępuje),
  `usun_zestaw`, `MAKS_ZESTAWOW=30`
- `osiedle/routes.py`: `GET/POST /osiedle/zestawy`, `DELETE
  /osiedle/zestawy/<id>`; tylko wpisane założenia, walidacja kluczy i
  zakresów przez `program.zalozenia`
- Osiedle: w „Założeniach” lista zestawów, „Zastosuj” (wypełnia pola i
  zapisuje koncepcję — założenia zostają w jej ustawieniach), „Usuń”,
  „Zapisz bieżące jako zestaw…”
- Test: zapis, zastąpienie, walidacja, usuwanie; sprawdzone w
  przeglądarce 1300/390 px (zapis, wyczyszczenie, zastosowanie —
  przeliczony program)
- Pomoc: „Własne założenia programu (normatywy)”
- `DECISIONS.md`: D-226

## ETAP 219 — Teren: opis i kierunek zdjęcia, podpisy w galerii raportu
Data: 2026-10-03
Status: zamknięty

- Formularz na telefon: po zdjęciu pola „Opis zdjęcia” (do 200 znaków) i
  „Kierunek patrzenia” (8 stron świata, stopnie 0–315); zapisywane tylko
  przy zdjęciu, czyszczone z formularzem
- `teren/projekt.py`: `KIERUNKI`, `STRZALKI`, `kierunek_zdjecia`
  (walidacja), `opis_kierunku`; `odczytaj_plik` czyta nowe klucze
  (starsze pliki bez nich — puste), `sprawdz_poprawke` przyjmuje je
  opcjonalnie
- `teren/baza.py`: kolumny `zdjecie_opis`, `zdjecie_kierunek`
  (`KOLUMNY_DODANE` — stare bazy dostają je przy starcie)
- Strona projektu: podpis w dymku, pola w panelu „Popraw” (gdy punkt ma
  zdjęcie); raport: podpis zdjęcia „opis · widok ↗ NE”
- Eksport: nowe kolumny w CSV/ODS, GeoJSON i GeoPackage
- Testy: plik (walidacja, brak zdjęcia, starszy plik), import → strona,
  raport, eksporty, poprawka; raport bez opisu nie pisze „None” (błąd
  znaleziony w przeglądarce); sprawdzone w przeglądarce 1300/390 px
  (dymek, panel, raport, formularz na telefon)
- Pomoc: „Opis i kierunek zdjęcia”
- `DECISIONS.md`: D-227

## ETAP 220 — Teren: import punktów z tabeli CSV (kolumny lat/lng)
Data: 2026-10-03
Status: zamknięty

- `teren/projekt.py`: `odczytaj_csv` — separator z nagłówka (; , tab),
  UTF-8 albo Windows-1250, przecinek dziesiętny we współrzędnych, wiersz
  bez współrzędnych = punkt bez położenia, `KOLUMNY_SZEROKOSCI`,
  `KOLUMNY_DLUGOSCI`, `KOLUMNY_POMIJANE` (kolumny eksportu Warsztatu)
- Wspólna część z GeoJSON wydzielona do `_punkt_z_atrybutow`
  (dopasowanie do pól, uwagi, czas, identyfikator); identyfikatory GeoJSON
  bez zmian (test porównuje ze wzorem z ETAPu 133)
- `teren/routes.py`: import rozpoznaje plik `.csv`/`.txt`; strona
  projektu: pole pliku przyjmuje CSV, opis pod nim
- Testy: arkusz po polsku (cp1250, średnik, przecinek dziesiętny), CSV z
  przecinkiem i eksport Warsztatu, 7 błędów z numerem wiersza, import
  przez stronę (ponowny pomija), stałość uid GeoJSON; przeglądarka
  1300/390 px
- Plan: przy ETAPie 244 dopisany przegląd formularzy na iPhonie (Safari)
- Pomoc: „Import punktów z tabeli CSV”
- `DECISIONS.md`: D-228

## ETAP 221 — Ceny: mapa schematyczna w raporcie zestawienia plików RCN
Data: 2026-10-03
Status: zamknięty

- `ceny/rcn.py`: `mapa_plikow_svg` — dla każdego pliku otoczka wypukła
  rdzenia (95% transakcji najbliższych środka, `RDZEN_PLIKU`), kropki
  (najwyżej 1500 najnowszych z rdzenia), numer w środku (mediana
  długości i szerokości); schemat wyśrodkowany; `_rdzen`
- Podziałka i strzałka północy wydzielone z `mapa_svg` do
  `_podzialka_i_polnoc` (wspólne dla obu map; dodana długość 50 km)
- `ceny/trasy_rcn.py`: transakcje każdego pliku pobierane raz — do
  tabeli i do mapy; szablon `zestawienie.html`: sekcja „Gdzie są
  transakcje” z opisem
- Testy: rdzeń bez punktu odstającego (podziałka nie rozciąga się),
  plik bez położenia pominięty, liczba kropek, brak nazw w SVG; strona
  zestawienia z mapą; przeglądarka 1300/390 px i wydruk PDF
- Pomoc: akapit „Mapa zestawienia”
- `DECISIONS.md`: D-229

## ETAP 222 — Dostępność: lista, przeciąganie i ponowna edycja punktów szybkiego modelu
Data: 2026-10-03
Status: zamknięty

- Szybki model: lista punktów (`#lista-punktow-modelu`) — numer (pokaż
  na mapie), nazwa (do obszarów obsługi), ✕ usuń; znaczniki przeciągane
  (`draggable`, położenie po `dragend`); nazwy w dymkach przez
  textContent
- „Edytuj te punkty i policz ponownie” w „Obszarach obsługi”: zestaw
  (usługa, prędkość, krętość, „dodaj do istniejących”, punkty z nazwami)
  przez sessionStorage na stronę pliku bazowego; bez pliku bazowego — na
  bieżącym pliku z uwagą
- `dostepnosc/routes.py`: `opis_pliku` zwraca `punkty.baza_istnieje`
  (`_punkty_z_baza`; plik przykładowy też się liczy)
- Test: `baza_istnieje` (nowa siatka, plik bazowy, usunięty, przykład);
  przeglądarka 1300/390 px: wstawienie, nazwa, przeciągnięcie, usunięcie,
  policzenie, powrót do edycji na pliku bazowym
- Pomoc: „Poprawianie punktów usług w szybkim modelu”
- `DECISIONS.md`: D-230

## ETAP 223 — Dostępność: kilka rodzajów usług w jednym liczeniu szybkiego modelu
Data: 2026-10-03
Status: zamknięty

- `dostepnosc/model.py`: `grupy_uslug` (punkty według usługi, ta sama
  kolumna dla różnych zapisów, `MAKS_USLUG=8`); `punkty_z_csv` czyta
  kolumnę usługi (`NAGLOWKI_USLUGI`)
- `dostepnosc/routes.py`: `z_punktow` liczy kolumnę dla każdej grupy
  (łączenie z istniejącymi — każda kolumna musi być w pliku bazowym),
  nazwa domyślna `…_N_uslugi`; plik punktów: wierzch = pierwsza usługa
  (zgodność wstecz) + lista `grupy`; `grupa_kolumny` — raport bierze
  obszary obsługi drukowanej kolumny
- Strona: pole usługi przy każdym punkcie (podpowiedzi z pliku), kolor
  punktu według usługi, „Obszary obsługi” z nagłówkiem usługi; „Edytuj te
  punkty” przenosi usługi punktów; opis pod przyciskiem zwykłą czcionką
  (poprawka po ETAPie 222)
- Testy: grupy usług, dwie usługi → dwie kolumny + wskaźnik łączny, raport
  drugiej usługi, łączenie bez kolumny, plik punktów sprzed ETAPu 223,
  kolumna usługi w CSV; przeglądarka 1300/390 px (błąd przebudowy listy
  przy „change” znaleziony i poprawiony)
- Pomoc: „Kilka rodzajów usług naraz w szybkim modelu”
- `DECISIONS.md`: D-231

## ETAP 224 — Fiszki: prognoza gotowości na dzień egzaminu z harmonogramu Leitnera
Data: 2026-10-03
Status: zamknięty

- `fiszki/egzaminy.py`: `prognoza` — dla każdej fiszki zakresu rozkład
  (pudełko, termin) przesuwany dzień po dniu do dnia przed egzaminem;
  „umiem” → następne pudełko, „trudne” → to samo jutro, „nie umiem” →
  powrót tego dnia do „umiem” → pudełko 2 (`PUDELKO_PO_POWROCIE`);
  wynik: oczekiwane utrwalone, maksimum (same „umiem”), najwięcej
  powtórek jednego dnia; identyczne stany liczone raz (`Counter`)
- `udzialy_odpowiedzi` — udziały odpowiedzi z dziennika z ostatnich 60
  dni (`DNI_DZIENNIKA`), od 30 odpowiedzi (`MIN_ODPOWIEDZI`); mniej — tylko
  maksimum z uwagą
- `_stany_w_zakresie`; `lista` dodaje `prognoza` do nadchodzących
  egzaminów z fiszkami; karta egzaminu: rozwijana „Prognoza na dzień
  egzaminu” z założeniami
- Testy: maksimum z odstępów (6 przypadków), wartości przy udziałach
  (w tym spadek utrwalonej), okno 60 dni dziennika, strona z i bez
  prognozy przy skuteczności; przeglądarka 1300/390 px
- Pomoc: „Prognoza gotowości na dzień egzaminu”
- `DECISIONS.md`: D-232

## ETAP 225 — Przepisy: ustawy zmieniające ogłoszone po tekście jednolitym
Data: 2026-10-03
Status: zamknięty

- Plan: „akty powiązane z API Sejmu (wykonawcze, zmieniające)” zastąpione
  (D-198) — `api.sejm.gov.pl` odrzucone przez proxy środowiska, więc pól
  z powiązaniami aktów w odpowiedzi API nie dało się sprawdzić
- `dane/sejm.py`: `czy_nowelizacja` (w tytule „o zmianie ustaw…” i
  przedmiot tej ustawy, bez obwieszczeń); `nowsze_teksty_jednolite`
  zwraca też `nowelizacje` ogłoszone po akcie z biblioteki z polem
  `po_tekscie_jednolitym` (po najnowszym znalezionym tekście jednolitym)
  — z tej samej wyszukiwarki co w ETAPie 101, bez dodatkowych zapytań
- „Czy jest nowszy tekst?”: sekcja „Ustawy zmieniające ogłoszone po …”
  z liczbą tych po tekście jednolitym, „Pobierz” przy każdej, uwaga o
  granicach szukania po tytule
- Testy: `czy_nowelizacja` (5 tytułów), nowelizacje przed i po tekście
  jednolitym, rozszerzony test z ETAPu 101; przeglądarka 1300/390 px z
  podstawioną odpowiedzią API
- Pomoc: akapit „Czy jest nowszy tekst?” uzupełniony
- `DECISIONS.md`: D-233

## ETAP 226 — Wydajność dużych baz: pomiar, indeksy i krzywa zapominania w SQL
Data: 2026-10-03
Status: zamknięty

- Przegląd indeksów: Teren ma `UNIQUE (projekt_id, uid)` (import),
  Przepisy `jednostki_akt`, Ceny indeksy po pliku (ETAP 117) — rośnie
  bez ograniczeń dziennik powtórek Fiszek, więc pomiar na nim
- `narzedzia/pomiar_fiszek.py`: baza jak po roku nauki (40 PDF, 20 tys.
  fiszek, 300 tys. odpowiedzi, 3 egzaminy) i czasy stron
- Wynik przed → po: `/fiszki/` 2085 → 285 ms, `/fiszki/statystyki`
  1508 → 55 ms, strona główna 203 → 86 ms; kolejka powtórek bez zmian
  (ok. 80 ms)
- Przyczyny i zmiany: krzywa zapominania (pętla w Pythonie po całym
  dzienniku przy każdym wejściu) → jedno zapytanie z funkcją okna `LAG`
  + zapamiętanie do nowej odpowiedzi (dziennik tylko przybywa);
  „najtrudniejsze” → zliczenie w dzienniku przed złączeniem; kalendarz
  na stronie głównej → `egzaminy.lista(z_prognoza=False)` (prognoza z
  ETAPu 224 była liczona niepotrzebnie)
- Indeksy (`fiszki/baza.py`, `IF NOT EXISTS` — istniejące bazy dostają je
  przy starcie): `dziennik_powtorek (fiszka_id, data, wynik)`,
  `dziennik_powtorek (data, wynik)`, `tematy_fiszek (temat)`; indeksy
  sprawdzone pomiarem pojedynczo — sam indeks bez zmiany krzywej nic nie
  dawał (sortowanie 300 tys. wierszy)
- Testy: krzywa w SQL = dawna pętla (3000 losowych odpowiedzi),
  zapamiętanie i unieważnienie po nowej odpowiedzi
- `DECISIONS.md`: D-234

## ETAP 227 — Dostępność dla czytników ekranu: przegląd ARIA
Data: 2026-10-03
Status: zamknięty

- `narzedzia/przeglad_stron.py`: nowe kontrole — `<main>`, dokładnie
  jeden `h1`, przyciski i linki z samym symbolem bez nazwy, komunikaty
  bez `aria-live`/roli, wykresy SVG bez `role="img"` i opisu, pola
  opisane tylko placeholderem, elementy fokusowalne w `aria-hidden`;
  kolejność poziomów nagłówków — tylko jako informacja (zmienna `ILE` —
  ile uwag na stronę)
- Pierwszy przebieg: 47 stron z uwagami → po poprawkach 0 problemów na
  99 stronach (31 informacji o kolejności nagłówków)
- Komunikaty w szablonach (58): `role="alert"` dla błędów, `role="status"`
  dla pozostałych; komunikaty tworzone w JS — rola przy utworzeniu
  (Fiszki, MPZP — `blad()`, Przepisy); kontenery wyników z
  `aria-live="polite"` (propozycje fiszek, opis Gemini w Atlasie i raporcie
  gminy, sprawdzanie aktualności aktu)
- Pola z samym placeholderem: `aria-label` (szukanie fiszek, symbole,
  działka, Dziennik Ustaw, nowa koncepcja, wskaźnik GUS, temat importu,
  budynki w kalkulatorze, opcje pola w Terenie)
- `h1`: raporty Dostępności i Osiedla — tytuł jako `h1.tytul-raportu`
  (wygląd jak h2); strony druku Atlasu — `h1.tylko-czytnik`; nowe klasy w
  `static/style.css`
- Wykresy i mapy SVG w raportach: `role="img"` z opisem na kontenerze (9)
- Plan: porządkowanie poziomów nagłówków dopisane do ETAPu 249
- `DECISIONS.md`: D-235

## ETAP 228 — Testy: pokrycie najsłabszych plików (ULDK, granice, raport gminy)
Data: 2026-10-03
Status: zamknięty

- Pomiar pokrycia: najsłabsze były `atlas/trasy_raport.py` (85%),
  `dane/uldk.py` (85%), `atlas/granice.py` (88%) — niepokryte prawie
  wyłącznie ścieżki błędów (sieć, dziwne odpowiedzi, walidacja)
- `tests/test_uldk.py`: błąd sieci w wyszukiwaniu i po identyfikatorze,
  pusta/dziwna odpowiedź, kod błędu, zły identyfikator, zła geometria,
  WKT bez SRID, pomijanie niepełnych wierszy podpowiedzi
- `tests/test_atlas.py` (granice): parametry zapytań WFS (warstwa, filtr
  TERYT), błąd połączenia i HTTP 503, pusta odpowiedź gmin bez zapisu
  cache, zły XML, obiekt bez geometrii, wielobok bez obwodu, kolejność
  lon/lat
- `tests/test_atlas.py` (raport gminy): walidacja zestawu (limit 20,
  przesunięcie, usuwanie, nieznany wskaźnik), błąd BDL → 502 we wszystkich
  trasach raportu (strona, CSV, opis, podobne, dodanie wskaźnika, lista
  gmin), opis bez danych → 404
- Wynik: `dane/uldk.py` 100%, `atlas/granice.py` 100%,
  `atlas/trasy_raport.py` 97%; całość 95% → 96% (692 testy)
- `DECISIONS.md`: D-236
