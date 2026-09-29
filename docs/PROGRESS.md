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
