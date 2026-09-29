# Decyzje projektowe

Format: D-0XX, data, decyzja, uzasadnienie, odrzucone alternatywy.

## D-001 — Struktura szkieletu aplikacji
Data: 2026-09-24

**Decyzja:** Każdy z czterech modułów (atlas, mpzp, fiszki, dostepnosc) to
osobny pakiet Pythona z własnym blueprintem Flask, własnym `templates/` i
`static/` (zagnieżdżonym pod nazwą modułu, np. `atlas/templates/atlas/`, żeby
uniknąć kolizji nazw szablonów między modułami i aplikacją główną). Brak
wspólnej bazy danych, wspólnego stanu ani wspólnej logiki między modułami.
Host aplikacji zakodowany na sztywno jako `127.0.0.1` w `app.py` — nie do
zmiany przez zmienną środowiskową.

**Uzasadnienie:** Moduły są funkcjonalnie niezależne (różne dane, różne
źródła, różni odbiorcy). Osobne pakiety ułatwiają pracę nad jednym modułem
bez ryzyka zepsucia pozostałych i odpowiadają zasadzie z CLAUDE.md o
unikaniu uniwersalnych abstrakcji dla dwóch modułów. Sztywny host 127.0.0.1
eliminuje ryzyko przypadkowego wystawienia aplikacji na sieć.

**Odrzucone alternatywy:**
- Wspólna baza SQLite dla wszystkich modułów — odrzucona, bo moduły nie
  współdzielą danych, a wspólna baza wymuszałaby migracje dotykające
  wszystkich modułów naraz.
- Flask-SQLAlchemy jako ORM — odłożone; żaden moduł jeszcze nie ma schematu,
  decyzja o ORM vs. surowy `sqlite3` zapadnie przy pierwszym module, który
  faktycznie zapisuje dane.

## D-002 — Zależność: google-genai (SDK do Gemini API)
Data: 2026-09-24

**Decyzja:** Warstwa `dane/gemini.py` korzysta z oficjalnego pakietu
`google-genai` (import `from google import genai`), przypiętego w
`requirements.txt` na wersji `2.25.0`.

**Uzasadnienie:** Moduł fiszki potrzebuje wywołać Gemini, żeby na
podstawie zaznaczonego fragmentu PDF-a zaproponować pytanie/odpowiedź.
`google-genai` to oficjalny SDK Google do tego API — sprawdzony przez
Context7 (`/googleapis/python-genai`), z prostym wzorcem
`genai.Client(api_key=...).models.generate_content(...)` i dedykowanym
wyjątkiem `google.genai.errors.APIError` do obsługi błędów sieci/API.

**Odrzucone alternatywy:**
- Ręczne wywołania REST przez `requests` — więcej kodu do utrzymania
  (autoryzacja, format żądania) bez żadnej korzyści, skoro oficjalny SDK
  istnieje i jest aktualnie utrzymywany.

## D-003 — Zależność: pdf.js wektorowany lokalnie
Data: 2026-09-24

**Decyzja:** Widok PDF-a w module fiszki korzysta z `pdf.js`
(pakiet `pdfjs-dist`, wersja `6.3.289`), wektorowanego lokalnie do
`fiszki/static/pdfjs/` (`pdf.min.mjs`, `pdf.worker.min.mjs`,
`text_layer.css`) — bez CDN, bez `node_modules`/kroku budowania. Wersja
przypięta w `VERSION.txt` w tym samym folderze.

**Uzasadnienie:** Renderowanie PDF-a w przeglądarce i natywne zaznaczanie
tekstu myszką (potrzebne do kotwicy fiszki) wymaga silnika PDF po stronie
klienta — nie ma sensownej alternatywy bez JS-owej biblioteki. `pdf.js` to
biblioteka referencyjna (ten sam silnik co w Firefoksie), a jej rdzeń
(`build/pdf.mjs`) eksportuje samodzielną klasę `TextLayer`, więc nie trzeba
dociągać pełnego `web/pdf_viewer.mjs`/`.css` (kompletnego "viewera" ze
swoim UI, którego nie używamy). Zgodne z podejściem do Leafleta z ETAPu 1:
biblioteka trzymana lokalnie w repo, wersja jawnie przypięta.

**Odrzucone alternatywy:**
- CDN (np. cdnjs) — odrzucone zgodnie z zasadą CLAUDE.md o Leaflet: brak
  CDN, żeby aplikacja działała offline i nie zależała od zewnętrznego
  hosta.
- Pełny bundle `web/pdf_viewer.mjs` + `pdf_viewer.css` (gotowy "viewer" z
  paskiem narzędzi, wyszukiwaniem itd.) — odrzucone jako zbędny ciężar;
  potrzebujemy tylko renderowania strony na canvasie i warstwy tekstowej
  do zaznaczania, co daje sam rdzeń biblioteki.

## D-004 — Baza modułu fiszki: surowy sqlite3, bez ORM
Data: 2026-09-24

**Decyzja:** Moduł fiszki zapisuje dane przez surowy `sqlite3` z biblioteki
standardowej (`fiszki/baza.py`), bez ORM. Baza: `instance/fiszki/fiszki.db`
(dwie tabele: `pdfy`, `fiszki`). Pliki PDF trzymane osobno na dysku, w
`instance/fiszki/pliki/`.

**Uzasadnienie:** Rozstrzyga odłożoną kwestię z D-001. Schemat jest mały
(dwie tabele, proste relacje), projekt jednoosobowy — ORM (np.
Flask-SQLAlchemy) dodałby zależność i warstwę abstrakcji bez realnej
korzyści przy tak małym zakresie zapytań.

**Odrzucone alternatywy:**
- Flask-SQLAlchemy — odrzucone jako niepotrzebny ciężar przy dwóch
  tabelach; do rozważenia dopiero, gdyby kolejny moduł potrzebował
  bardziej złożonych relacji/migracji.

## D-005 — Zależności: requests i shapely
Data: 2026-09-25

**Decyzja:** Moduł mpzp korzysta z `requests==2.34.2` (klient HTTP do
ULDK i WFS gminy) oraz `shapely==2.1.2` (parsowanie geometrii WKT/GML,
point-in-polygon, indeks przestrzenny `STRtree`).

**Uzasadnienie:** `requests` jest czytelniejszy niż `urllib` z biblioteki
standardowej przy obsłudze zapytań GET z parametrami i statusami błędów.
`shapely` eliminuje ręczne parsowanie geometrii regexem i implementację
point-in-polygon od zera — sprawdzona biblioteka do geometrii
obliczeniowej, używana też przez GeoPandas i inne narzędzia GIS.

**Odrzucone alternatywy:**
- `urllib` z biblioteki standardowej — odrzucone, więcej kodu
  obsługującego błędy sieci/HTTP bez realnej korzyści.
- Ręczne parsowanie WKT/GML i własna implementacja point-in-polygon —
  odrzucone jako wynajdywanie koła na nowo przy dostępnej, dojrzałej
  bibliotece.

## D-006 — Leaflet wektorowany lokalnie
Data: 2026-09-25

**Decyzja:** Mapa w module mpzp korzysta z Leaflet 1.9.4, wektorowanego
lokalnie do `mpzp/static/leaflet/` (`leaflet.js`, `leaflet.css`, obrazy
markerów/warstw) — bez CDN, bez `node_modules`/kroku budowania. Wersja
przypięta w `VERSION.txt` w tym samym folderze.

**Uzasadnienie:** Zgodne z zasadą CLAUDE.md (żadnego CDN dla Leafleta) i
z podejściem do `pdf.js` z ETAPu 2 (D-003) — biblioteka trzymana lokalnie
w repo, aplikacja działa offline dla warstwy UI niezależnie od
zewnętrznego hosta biblioteki. (Kafelki mapy bazowej nadal wymagają
połączenia z internetem — to dane, nie kod, więc reguła anty-CDN ich nie
dotyczy, podobnie jak zapytania do WFS/ULDK.)

**Odrzucone alternatywy:**
- CDN (np. unpkg, cdnjs) — odrzucone zgodnie z zasadą CLAUDE.md.

## D-007 — Eksport do Anki jako plik tekstowy (TSV), bez genanki
Data: 2026-09-29

**Decyzja:** Fiszki eksportowane są do Anki jako plik tekstowy
rozdzielany tabulatorami (`eksport.txt`) z nagłówkami `#separator:tab` i
`#html:true`, importowany w Anki przez Plik → Importuj. Kolumny:
pytanie, odpowiedź, źródło (nazwa PDF-a i strona). Pola escapowane jako
HTML, nowe linie jako `<br>`, tabulatory w treści zamieniane na spacje.
Obok osobny eksport CSV (UTF-8 z BOM) do arkusza kalkulacyjnego.

**Uzasadnienie:** Anki natywnie importuje pliki tekstowe — zero nowych
zależności, format czytelny i łatwy do sprawdzenia w edytorze. Kolumna
źródła zachowuje kotwicę w PDF-ie także po stronie Anki.

**Odrzucone alternatywy:**
- `.apkg` przez bibliotekę `genanki` — odrzucone, nowa zależność dla
  wygody jednego kliknięcia przy imporcie.
- Jeden wspólny CSV dla arkusza i Anki — odrzucone, Anki i arkusze
  inaczej traktują nowe linie i HTML w polach.

## D-008 — Polyfill `Map.getOrInsertComputed` dla pdf.js 6.x
Data: 2026-09-29

**Status:** zastąpiona przez D-009 (polyfill usunięty).

**Decyzja:** Zostajemy przy pdf.js 6.3.289 i dokładamy własny polyfill
(`fiszki/static/polyfill_map.mjs`) dla `Map`/`WeakMap.prototype.getOrInsert`
i `getOrInsertComputed`. Polyfill jest importowany jako pierwszy w
`fiszki.js` i w `fiszki/static/pdf_worker.mjs` — nowym punkcie wejścia
workera, który po polyfillu importuje oryginalny `pdf.worker.min.mjs`.
Metody są dodawane tylko wtedy, gdy przeglądarka ich nie ma.

**Uzasadnienie:** Bez tych metod przeglądarka na Linux Mint nie rysowała
strony PDF ani warstwy tekstu. Polyfill to ~25 linii, nie zmienia
wektorowanych plików pdf.js (aktualizacja biblioteki dalej polega na
podmianie plików), a gdy przeglądarki dogonią standard — staje się
martwym kodem do usunięcia bez skutków ubocznych.

**Odrzucone alternatywy:**
- Powrót do pdf.js 5.x — odrzucone, wymaga ponownego wektorowania i
  sprawdzania zmian API `TextLayer`, więcej ryzyka niż polyfill.
- Łatanie `pdf.min.mjs` / `pdf.worker.min.mjs` — odrzucone, zmiany w
  zminifikowanym kodzie zewnętrznym ginęłyby przy każdej aktualizacji.

## D-009 — pdf.js w wersji legacy zamiast ręcznego polyfilla
Data: 2026-09-29

**Decyzja:** Pliki `fiszki/static/pdfjs/pdf.min.mjs` i
`pdf.worker.min.mjs` pochodzą z `legacy/build/` paczki pdfjs-dist 6.3.289
(ta sama wersja i to samo API co wcześniej, inny wariant buildu). Ręczny
polyfill z D-008 (`polyfill_map.mjs`, `pdf_worker.mjs`) usunięty.
Dodatkowo `fiszki.js` pokazuje błąd wczytania PDF-a na stronie
(`#blad-pdf`) zamiast milczeć.

**Uzasadnienie:** Po D-008 PDF nadal nie wyświetlał się na Linux Mint.
Nowoczesny build pdf.js 6.3 używa wielu świeżych API przeglądarki
(`Promise.try`, `Uint8Array.fromBase64`, `Math.sumPrecise`,
`Float16Array`, `URL.parse`, `Map.getOrInsertComputed`…) — łatanie ich po
kolei to zabawa w kotka i myszkę. Build legacy jest oficjalnie
przygotowany przez projekt pdf.js dla starszych przeglądarek i zawiera
polyfille (core-js). Sprawdzone w Chromium z usuniętymi w/w API: strona
się rysuje, warstwa tekstu i „pokaż w źródle” działają. Minimalne
wymaganie: przeglądarka z `Promise.withResolvers` (Firefox 121+, Chrome
119+, czyli od początku 2024 r.).

**Odrzucone alternatywy:**
- Dalsze ręczne polyfille (D-008) — odrzucone, nie wiadomo, ile ich
  jeszcze brakuje; każdy to kod do utrzymania.
- Powrót do pdf.js 5.x — odrzucone, legacy 6.3 rozwiązuje problem bez
  zmiany API w `fiszki.js`.

## D-010 — Skrypt startowy i ikona na pulpit
Data: 2026-09-29

**Decyzja:** `uruchom.sh` startuje `app.py` z `.venv`, czeka aż serwer
odpowie i otwiera przeglądarkę (`xdg-open`); zamknięcie okna terminala
zatrzymuje serwer. `zainstaluj_ikone.sh` generuje `warsztat.desktop` na
pulpicie i w `~/.local/share/applications` ze ścieżką bezwzględną do
projektu i oznacza go jako zaufany dla Nemo. Instrukcja w
`docs/URUCHOMIENIE.md`.

**Uzasadnienie:** CLAUDE.md zakłada uruchamianie ikoną z pulpitu, a
takiego mechanizmu nie było. Terminal widoczny (`Terminal=true`), bo to
w nim widać błędy serwera i łatwo aplikację zamknąć. Plik `.desktop`
generowany, a nie trzymany w repo, bo wymaga ścieżki bezwzględnej,
różnej na każdym komputerze.

**Odrzucone alternatywy:**
- Usługa systemd użytkownika (serwer w tle stale) — odrzucone, zbędna
  złożoność i serwer działający, gdy nikt go nie używa.
- Gotowy `.desktop` w repo ze stałą ścieżką — odrzucone, psuje się po
  przeniesieniu katalogu.

## D-011 — Wspólny szablon bazowy i system stylów
Data: 2026-09-29

**Decyzja:** Wszystkie strony dziedziczą po `templates/base.html`
(nawigacja + bloki Jinja). `static/style.css` zawiera tylko elementy
wspólne: tokeny kolorów jako zmienne CSS (jasny i ciemny motyw przez
`prefers-color-scheme`), typografię, karty, przyciski, formularze,
tabele i komunikaty. Układ każdego modułu zostaje w jego własnym pliku
CSS (grid dla układów stron, flexbox dla rzędów i stosów elementów).
Czcionka systemowa (`-apple-system`, `Inter`, `Ubuntu`, ...), bez
pobierania fontów z sieci.

**Uzasadnienie:** Autor poprosił o wygląd w stylu Apple z użyciem grid
i flexboxa. Nawigacja i podstawowe elementy powtarzały się w każdym
szablonie — jeden szkielet to mniej kopiowania. To powłoka aplikacji,
a nie abstrakcja logiki modułów, więc nie łamie zasady niezależności
modułów. Tokeny kolorów pozwalają mieć tryb ciemny bez dublowania reguł.

**Odrzucone alternatywy:**
- Framework CSS (Bootstrap, Tailwind) — odrzucone: zależność, a
  Tailwind wymaga kroku budowania (zakazane w CLAUDE.md).
- Fonty SF Pro / Inter pobierane z sieci — odrzucone: licencja SF Pro
  i zasada „bez CDN”; stos czcionek systemowych wygląda natywnie.

## D-012 — Powtórki w systemie Leitnera, osobna tabela stanu
Data: 2026-09-29

**Decyzja:** Powtórki według systemu Leitnera: 5 pudełek, stałe odstępy
1/2/4/8/16 dni, „nie umiem” cofa do pudełka 1 z terminem na dziś. Stan
w osobnej tabeli `powtorki` (klucz = `fiszka_id`, `ON DELETE CASCADE`),
a nie w nowych kolumnach tabeli `fiszki`. Logika w czystych funkcjach
(`fiszki/powtorki.py`), SQL w `routes.py`.

**Uzasadnienie:** Leitner da się wytłumaczyć w dwóch zdaniach i
sprawdzić ręcznie w bazie, a to projekt uczący się. Osobna tabela
tworzy się przez `CREATE TABLE IF NOT EXISTS` w istniejącej bazie —
bez skryptu migracji; brak wiersza oznacza fiszkę nową.

**Odrzucone alternatywy:**
- SM-2 (algorytm Anki/SuperMemo) — odrzucone: współczynnik łatwości i
  cztery oceny to więcej logiki i trudniejsze testy; eksport do Anki
  (D-007) jest dla tych, którzy chcą SM-2.
- Kolumny `pudelko`/`nastepna_powtorka` w `fiszki` — odrzucone:
  wymagałyby `ALTER TABLE` w istniejących bazach.

## D-013 — Atlas: BDL API, granice z PRG, strażnik liczb w opisie
Data: 2026-09-29

**Decyzja:** Dane z API BDL v1 (`dane/bdl.py`), jednostka analizy:
gminy jednego województwa. Kod TERYT gminy wyciągany z identyfikatora
BDL, co pozwala połączyć dane z granicami z PRG (WFS GUGiK). Odpowiedzi
BDL w cache SQLite na 30 dni, granice w cache GeoJSON bez terminu.
Statystyki i progi klas (kwantyle, 5 klas) liczone w Pythonie. Gemini
dostaje listę gotowych faktów, a opis jest odrzucany, jeśli zawiera
liczbę, której nie ma w faktach.

**Uzasadnienie:** CLAUDE.md: tylko API i WFS, bez scrapowania; model
nie generuje liczb. Samo polecenie w prompcie tego nie gwarantuje,
dlatego jest twarda kontrola po stronie kodu. Fakty liczone na
serwerze, nie przyjmowane z przeglądarki. Klasy kwantylowe dają
czytelny kartogram także przy skośnych rozkładach (np. ludność, gdzie
jedno miasto dominuje). Województwo jako zakres: ok. 100–300 gmin, więc
rozsądny rozmiar granic i czytelna mapa.

**Odrzucone alternatywy:**
- Cała Polska naraz (2477 gmin) — odrzucone na start: duże granice,
  wolny pierwszy wczyt, nieczytelny ranking.
- Granice gmin jako plik w repo — odrzucone: kilkadziesiąt MB danych,
  które się zmieniają; PRG to źródło referencyjne.
- Klasy równych przedziałów — odrzucone: przy danych skośnych prawie
  wszystkie gminy w jednej klasie.

## D-014 — Leaflet we wspólnym `static/leaflet/`
Data: 2026-09-29

**Decyzja:** Leaflet 1.9.4 przeniesiony z `mpzp/static/leaflet/` do
`static/leaflet/` (dalej lokalnie, bez CDN — D-006 w mocy).

**Uzasadnienie:** Z mapy korzystają teraz trzy moduły (mpzp, atlas,
dostępność). Biblioteka zewnętrzna w jednym miejscu to jedna kopia do
aktualizacji; to nie jest współdzielona logika modułów.

**Odrzucone alternatywy:**
- Kopia Leafleta w każdym module — odrzucone: trzy kopie tej samej
  wersji do pilnowania.
- Odwołania atlasu do `mpzp.static` — odrzucone: ukryta zależność
  między niezależnymi modułami.

## D-015 — Dostępność: CSV na siatce H3, biblioteka `h3`
Data: 2026-09-29

**Decyzja:** Moduł czyta gotowe wyniki jako CSV: kolumna `h3` + kolumny
liczbowe. Nazwa kolumny decyduje o interpretacji: `*_min` / `czas*` to
minuty (stałe klasy 5/10/15/20/30, udziały w zasięgu 5/10/15 min),
reszta — klasy kwantylowe. Geometrię heksagonów liczy biblioteka `h3`
(`h3==4.5.0`, oficjalne wiązanie Pythona do biblioteki Ubera). Pliki
użytkownika w `instance/dostepnosc/wyniki/`, bez bazy danych. Dołączony
plik przykładowy jest syntetyczny i tak opisany w nazwie i interfejsie.

**Uzasadnienie:** CLAUDE.md: moduł „czyta gotowe wyniki” — więc liczy
tylko statystyki opisowe, a nie samą dostępność. CSV z indeksem H3
eksportuje każde narzędzie (QGIS, pandas, r5py, h3-py), jest mały (bez
geometrii) i czytelny. Samodzielne liczenie wierzchołków heksagonu to
nietrywialna geometria na dwudziestościanie — biblioteka referencyjna
jest pewniejsza. Stałe progi minut odpowiadają koncepcji miasta
15-minutowego i są porównywalne między plikami. Bez bazy, bo pliki są
źródłem prawdy, a jedyny stan to ich lista.

**Odrzucone alternatywy:**
- GeoJSON z gotowymi wielokątami — odrzucone: pliki kilkanaście razy
  większe, a indeks H3 i tak niesie geometrię.
- `h3-js` w przeglądarce — odrzucone: to też zależność, a liczenie po
  stronie serwera pozwala testować wyniki w pytest.
- SpatiaLite — odrzucone: brak operacji przestrzennych, które by go
  wymagały.

## D-016 — MPZP: słownik symboli w kodzie, historia w SQLite
Data: 2026-09-29

**Decyzja:** Słownik oznaczeń przeznaczenia jako `dict` w
`mpzp/symbole.py` (podstawa: rozporządzenie z 26.08.2003, Dz.U. nr 164
poz. 1587), wyświetlany z przypisem „opis orientacyjny, rozstrzyga
uchwała”, zawsze obok surowych atrybutów z WFS. Historia sprawdzonych
działek w osobnej bazie modułu (`mpzp.db`), 20 ostatnich wpisów.
Wyszukiwanie tylko po pełnym identyfikatorze działki (ULDK
`GetParcelById`).

**Uzasadnienie:** Symbole typu „KDL” są nieczytelne dla początkującego;
słownik z rozporządzenia pokrywa większość planów. Nie da się jednak
zagwarantować, że gmina nie użyła własnych oznaczeń — stąd przypis i
nieukrywanie oryginalnych atrybutów. Opis ze słownika, a nie z Gemini:
to stała wiedza, a nie tekst do generowania. Pełny identyfikator jest
jednoznaczny; wyszukiwanie po samym numerze wymagałoby wyboru obrębu.

**Odrzucone alternatywy:**
- Opis symbolu przez Gemini — odrzucone: model mógłby „dopowiedzieć”
  treść uchwały, której nie zna.
- Wyszukiwanie po nazwie obrębu i numerze (ULDK `GetParcelByIdOrNr`) —
  odłożone: niejednoznaczne wyniki wymagają osobnego interfejsu wyboru.
- Historia w `localStorage` przeglądarki — odrzucone: znika po
  wyczyszczeniu przeglądarki i nie da się jej testować w pytest.

## D-017 — Atlas: zmiana procentowa ze stałymi klasami
Data: 2026-09-29

**Decyzja:** Porównanie lat pokazuje zmianę procentową
`(teraz − wtedy) / |wtedy| × 100`, liczoną w Pythonie, tylko dla gmin z
danymi w obu latach. Kartogram zmiany ma stałe, symetryczne klasy
(≤ −10%, −10…−2%, −2…+2%, +2…+10%, > +10%) i skalę rozbieżną
pomarańcz–szary–niebieski. Gmina z wartością bazową 0 ma zmianę
bezwzględną, ale nie procentową.

**Uzasadnienie:** Stałe progi pozwalają porównywać mapy różnych
wskaźników i województw („czy tu jest gorzej niż tam”), a przedział
±2% wyróżnia gminy praktycznie bez zmian. Pomarańcz/niebieski zamiast
czerwień/zieleń — czytelne także dla osób z zaburzeniami widzenia barw
i bez wartościowania („spadek” nie zawsze znaczy „źle”, np. bezrobocie).
Porównanie tylko gmin obecnych w obu latach, bo zmiany granic gmin
(np. nowe gminy) dawałyby fałszywe wyniki.

**Odrzucone alternatywy:**
- Kwantyle zmiany — odrzucone: przy prawie samych wzrostach połowa gmin
  „ze wzrostem” wyglądałaby jak spadek.
- Średnioroczne tempo zmian (CAGR) — odrzucone na start: trudniejsze do
  wyjaśnienia; można dodać później.

## D-018 — Wyszukiwanie fiszek w Pythonie zamiast SQL/FTS
Data: 2026-09-29

**Decyzja:** Wyszukiwarka pobiera fiszki z bazy i filtruje je w Pythonie
(`str.casefold()`), a nie przez `LIKE` ani indeks pełnotekstowy FTS5.

**Uzasadnienie:** `LOWER()`/`LIKE` w SQLite rozróżnia wielkość liter
poza ASCII, więc „ład” nie znalazłoby „ŁAD”. Osobista kolekcja to setki
albo kilka tysięcy fiszek — filtrowanie w Pythonie trwa milisekundy, a
kod jest prosty i łatwy do przetestowania.

**Odrzucone alternatywy:**
- FTS5 z tokenizerem `unicode61` — odrzucone na teraz: osobna tabela
  wirtualna i jej synchronizacja przy każdej zmianie fiszki; warto
  wrócić, gdyby kolekcja urosła do dziesiątek tysięcy.
- Własna funkcja SQL (`create_function`) do porównań — odrzucone:
  więcej kodu dla tego samego efektu.

## D-019 — Ochrona przed CSRF przez sprawdzanie Origin, bez tokenów
Data: 2026-09-29

**Decyzja:** Zamiast tokenów CSRF w formularzach aplikacja odrzuca
zapytania zmieniające stan, których `Origin` (albo `Referer`) wskazuje
inne źródło niż ona sama, oraz każde zapytanie z nagłówkiem `Host`
innym niż `127.0.0.1`/`localhost`. Całość w jednym pliku `ochrona.py`,
podpiętym w `app.py` dla wszystkich modułów.

**Uzasadnienie:** Współczesne przeglądarki zawsze wysyłają `Origin` przy
POST z innej strony, więc sprawdzenie nagłówka zamyka ten atak bez
zmian w każdym formularzu i każdym `fetch`. To zabezpieczenie powłoki
aplikacji (jak `base.html`), a nie wspólna logika modułów. Kontrola
`Host` to standardowa obrona serwerów lokalnych przed DNS rebinding.

**Odrzucone alternatywy:**
- Tokeny CSRF (np. Flask-WTF) — odrzucone: nowa zależność, sesje i
  zmiany w kilkunastu miejscach frontendu dla tego samego efektu.
- Content-Security-Policy — odłożone: szablony używają wbudowanych
  `<script>` ze stałymi URL-i i `onsubmit`, więc CSP wymagałaby
  `unsafe-inline` albo przepisania tych miejsc.

## D-020 — Wskaźnik łączny jako maksimum czasów
Data: 2026-09-29

**Decyzja:** Łączna dostępność komórki to maksimum czasów dojścia do
wszystkich usług z pliku (kolumny `*_min` / `czas*`). Komórka z brakiem
danych dla którejkolwiek usługi nie dostaje wartości łącznej. Obok
liczymy, która usługa najczęściej wyznacza to maksimum.

**Uzasadnienie:** Idea miasta 15-minutowego to „wszystkie podstawowe
usługi w zasięgu” — dopiero najdalsza z nich mówi, czy komórka spełnia
warunek. „Najsłabsze ogniwo” podpowiada, której usługi brakuje
najbardziej — to wniosek planistyczny liczony z danych, a nie
interpretacja modelu. Uzupełnianie braków (np. zerem albo średnią)
fałszowałoby wynik.

**Odrzucone alternatywy:**
- Średnia czasów — odrzucone: bliski przystanek „nadrabiałby” brak
  przychodni, co przeczy idei wskaźnika.
- Wagi usług ustawiane przez użytkownika — odłożone: wymagają
  uzasadnienia wag, a wynik przestaje być porównywalny.

## D-021 — Podsumowania na stronie głównej: funkcje w modułach
Data: 2026-09-29

**Decyzja:** Każdy moduł udostępnia zwykłą funkcję zwracającą swoje
liczby dla strony głównej; `app.py` woła je po kolei i łapie wyjątki,
żeby błąd jednego modułu nie wyłączył całej strony.

**Uzasadnienie:** Moduły zostają niezależne — strona główna nie zagląda
do cudzych baz ani tabel, tylko pyta każdy moduł. Brak wspólnej klasy
czy rejestru wtyczek (zasada: bez uniwersalnych abstrakcji), bo cztery
wywołania czyta się łatwiej niż mechanizm.

**Odrzucone alternatywy:**
- Zapytania SQL do baz modułów bezpośrednio w `app.py` — odrzucone:
  powłoka znałaby schematy baz wszystkich modułów.
- Podsumowania ładowane przez JS z osobnych endpointów — odrzucone:
  cztery dodatkowe zapytania i migotanie strony dla kilku liczb.

## D-022 — Pustych odpowiedzi API nie zapamiętujemy w cache
Data: 2026-09-29

**Decyzja:** `atlas/baza.py:z_cache` nie zapisuje pustego wyniku (pusta
lista / brak danych) — takie zapytanie trafi do BDL ponownie.

**Uzasadnienie:** Pusty wynik najczęściej znaczy „GUS jeszcze nie
opublikował danych za ten rok”, a nie „tych danych nigdy nie będzie”.
Zapamiętanie go na 30 dni ukrywałoby nowe dane. Koszt: kilka
dodatkowych zapytań o lata bez danych.

**Odrzucone alternatywy:**
- Krótszy czas ważności dla pustych wyników (np. 1 dzień) — odrzucone:
  dodatkowa kolumna i logika dla bardzo małego zysku.

## D-023 — Podpowiedzi działek: ULDK GetParcelByIdOrNr + historia
Data: 2026-09-29

**Decyzja:** Pole wyszukiwania działki podpowiada w trakcie pisania:
wpisy z lokalnej historii (od razu) i wyniki ULDK `GetParcelByIdOrNr`
dla frazy „obręb numer”. Podpowiedzi nie zawierają geometrii — pobieramy
ją dopiero dla wybranej działki (istniejące `GetParcelById`).

**Uzasadnienie:** Pełnego identyfikatora działki nikt nie pamięta, a
obręb i numer są na wypisie z rejestru i w geoportalu. ULDK to usługa
publiczna GUGiK (CLAUDE.md: tylko API/WFS). Bez geometrii w podpowiedziach
odpowiedź jest mała i szybka, a jedno dodatkowe zapytanie po wyborze
jest niezauważalne. Opóźnienie 400 ms i minimum 3 znaki ograniczają
liczbę zapytań do ULDK.

**Odrzucone alternatywy:**
- Własna baza działek do wyszukiwania lokalnego — odrzucone: miliony
  rekordów i ich aktualizacja; ULDK robi to po stronie GUGiK.
- Zapytanie przy każdym znaku — odrzucone: obciąża usługę publiczną.

## D-024 — Praca trafia na `main`
Data: 2026-09-29

**Decyzja:** `main` jest gałęzią, z której autor uruchamia aplikację;
zamknięte ETAPy są na nią przenoszone (fast-forward), a nie tylko na
gałąź roboczą.

**Uzasadnienie:** Autor aktualizuje projekt przez `git pull` na `main`
i przez to przez wiele ETAPów uruchamiał wersję z ETAPu 3 („nic nie
działa”, stary wygląd). Jedna gałąź do uruchamiania usuwa tę pułapkę.

**Odrzucone alternatywy:**
- Instrukcja „przełącz się na gałąź roboczą” — odrzucone: łatwo o tym
  zapomnieć, a nazwa gałęzi jest nieczytelna.

## D-025 — Fiszki ze strony: cytat obowiązkowy i sprawdzany w kodzie
Data: 2026-09-29

**Decyzja:** Gemini proponuje fiszki z całej strony tylko razem z
dosłownym cytatem. Kod sprawdza, czy cytat występuje w tekście strony
(porównanie bez białych znaków); propozycje bez kotwicy nie są
pokazywane. Użytkownik zatwierdza każdą propozycję przed zapisem.
Historia powtórek w osobnym dzienniku (bez kasowania przy usunięciu
fiszki), statystyki liczone SQL-em z dziennika.

**Uzasadnienie:** Kotwica w źródle to istota modułu — fiszka, której
nie da się pokazać w PDF-ie, może zawierać treść wymyśloną przez model.
Ten sam mechanizm (strażnik po stronie kodu) co przy liczbach w atlasie.
Porównanie bez białych znaków, bo pdf.js i zaznaczenie myszką różnią
się nowymi liniami i odstępami.

**Odrzucone alternatywy:**
- Automatyczny zapis wszystkich propozycji — odrzucone: student ma
  przeczytać i ocenić fiszkę, to część nauki.
- Dopasowanie przybliżone (fuzzy) cytatu — odrzucone: pozwalałoby
  przepuścić parafrazę, której nie ma w źródle.

## D-026 — Wykresy jako własne SVG, bez biblioteki
Data: 2026-09-29

**Decyzja:** Wykres liniowy profilu gminy jest rysowany ręcznie w SVG
(`atlas/static/wykres_gminy.js`, ok. 130 linii), style z tokenów CSS.

**Uzasadnienie:** Jedna seria, kilkanaście punktów, linia odniesienia i
dymek — to za mało, żeby dokładać bibliotekę (Chart.js, D3) wektorowaną
lokalnie. Własne SVG automatycznie dziedziczy jasny/ciemny motyw i jest
czytelne dla kogoś, kto uczy się, jak działa wykres.

**Odrzucone alternatywy:**
- Chart.js / D3 lokalnie — odrzucone: nowa zależność frontendowa dla
  jednego prostego wykresu.
- Porównanie z medianą województwa w każdym roku — odrzucone: wymaga
  pobrania danych wszystkich gmin dla każdego roku (dziesiątki zapytań do
  BDL); linia mediany badanego roku daje punkt odniesienia bez tego kosztu.

## D-027 — Powierzchnia z lokalnej skali zamiast biblioteki odwzorowań
Data: 2026-09-29

**Decyzja:** Powierzchnię działki i jej części liczymy z geometrii WGS84
przeskalowanej lokalną skalą metrów na stopień (wzory elipsoidy WGS84 dla
szerokości środka działki). Raport jest stroną HTML ze stylami druku —
PDF powstaje przez „Drukuj → Zapisz jako PDF” przeglądarki.

**Uzasadnienie:** Dla obiektów wielkości działki błąd jest poniżej 0,1% —
mniej niż różnice między geometrią a powierzchnią ewidencyjną, o czym
raport uprzedza. Unikamy zależności (pyproj ciągnie bibliotekę PROJ).
Raport w HTML korzysta z tych samych stylów co aplikacja, a przeglądarka
i tak ma dobry eksport do PDF.

**Odrzucone alternatywy:**
- pyproj + EPSG:2180 — odrzucone: ciężka zależność dla dokładności,
  której w tym zastosowaniu nie potrzeba.
- Generowanie PDF po stronie serwera (np. WeasyPrint, ReportLab) —
  odrzucone: nowa zależność i drugi, osobny szablon wyglądu.

## D-028 — Porównanie scenariuszy na wspólnych komórkach, ludność jako waga
Data: 2026-09-29

**Decyzja:** Porównanie dwóch plików wyników bierze tylko komórki H3
obecne w obu plikach z wartością w obu i wymaga tej samej rozdzielczości.
Zmiana = czas „po” − czas „przed”; stałe klasy ±1 i ±5 min (poniżej
1 minuty traktujemy jako brak zmiany). Kolumna ludności nie jest
wskaźnikiem do mapy, tylko wagą do udziałów i do liczby mieszkańców,
którzy zyskali lub stracili dostęp w 15 minut.

**Uzasadnienie:** Ocena wpływu inwestycji (szkoła, przystanek) to typowe
zadanie planisty: „ilu mieszkańców zyska dostęp”. Udział powierzchni
potrafi mylić — pusta łąka i blokowisko liczą się tak samo — dlatego z
kolumną ludności główną liczbą jest odsetek mieszkańców. Próg ±1 min
odcina szum obliczeń sieciowych.

**Odrzucone alternatywy:**
- Porównanie po współrzędnych zamiast po indeksie H3 — odrzucone: te
  same indeksy gwarantują porównanie „komórka w komórkę”.
- Uzupełnianie brakujących komórek zerem — odrzucone: fałszowałoby
  zmianę dostępności.

## D-029 — Naprawa geometrii przy wczytywaniu danych WFS
Data: 2026-09-29

**Decyzja:** Każda geometria wydzielenia z WFS, która nie jest poprawna
(np. przecina sama siebie), jest naprawiana `shapely.make_valid` od razu
przy parsowaniu; operacje przecięcia są dodatkowo chronione — błąd GEOS
pomija jedno wydzielenie zamiast całego zapytania.

**Uzasadnienie:** Dane planów miejscowych przygotowują różne biura i
narzędzia; niepoprawne wielokąty to norma, nie wyjątek. Naprawa w jednym
miejscu (przy wczytaniu) chroni wszystkie późniejsze operacje:
punkt-w-wielokącie, podział działki, szkic w raporcie.

**Odrzucone alternatywy:**
- `buffer(0)` — odrzucone: potrafi zgubić części wielokątów typu
  „kokarda”; `make_valid` zachowuje obie części.

## D-030 — Kalkulator zabudowy w module mpzp, liczony na serwerze
Data: 2026-09-29

**Decyzja:** Kalkulator wskaźników zabudowy jest częścią modułu mpzp
(`mpzp/zabudowa.py`), a nie osobnym, piątym modułem. Liczy serwer, a
przeglądarka tylko wysyła pola i pokazuje wynik.

**Uzasadnienie:** Wskaźniki zabudowy to ustalenia planu miejscowego —
naturalne przedłużenie „działka → przeznaczenie”, a do kalkulatora
przechodzi się z panelu działki z gotową powierzchnią. Obliczenia w
Pythonie są testowane w pytest (definicje z ustawy łatwo sprawdzić
przykładami), a CLAUDE.md przewiduje cztery moduły.

**Odrzucone alternatywy:**
- Obliczenia tylko w JS — odrzucone: brak testów pytest dla logiki,
  która ma być wiarygodna na zaliczeniu.
- Uwzględnianie kondygnacji o różnej powierzchni — odłożone: komplikuje
  formularz; opisane jako uproszczenie na stronie.

## D-031 — Eksport do QGIS jako GeoJSON (WGS84)
Data: 2026-09-29

**Decyzja:** Każda mapa ma eksport GeoJSON (RFC 7946, EPSG:4326) z
geometrią i wszystkimi policzonymi wartościami jako atrybutami.

**Uzasadnienie:** QGIS to podstawowe narzędzie na zajęciach z GIS;
GeoJSON otwiera się przeciągnięciem pliku, bez konfiguracji, i nie
wymaga żadnej zależności po stronie aplikacji. Wartości liczone w
aplikacji (udziały, zmiany, klasy) trafiają do tabeli atrybutów, więc
student może na nich dalej pracować.

**Odrzucone alternatywy:**
- GeoPackage / Shapefile — odrzucone: wymagają GDAL/Fiona (ciężkie
  zależności), a Shapefile ucina nazwy pól do 10 znaków.
- Eksport w EPSG:2180 — odrzucone: RFC 7946 wymaga WGS84, a QGIS sam
  przelicza do układu projektu.

## D-032 — Korelacja: statystyki z biblioteki standardowej, opis z progów
Data: 2026-09-29

**Decyzja:** r Pearsona i regresja liniowa z modułu `statistics`
(Python 3.10+), rho Spearmana jako Pearson na rangach z uśrednianiem
remisów, opis siły związku według stałych progów — bez modelu językowego
i bez numpy/scipy. Nie liczymy istotności (p-value).

**Uzasadnienie:** Wszystkie liczby pochodzą z kodu (zasada projektu), a
biblioteka standardowa wystarcza dla setek gmin. Opis z progów jest
powtarzalny i zgodny z podręcznikiem. P-value wymagałoby rozkładu t
(scipy) i łatwo je nadinterpretować przy danych, które są całą
populacją gmin województwa, a nie próbą.

**Odrzucone alternatywy:**
- numpy/scipy — odrzucone: ciężkie zależności dla trzech wzorów.
- Opis wyniku przez Gemini — odrzucone: stałe progi dają ten sam opis
  za każdym razem i nie ryzykują wymyślonych liczb.

## D-033 — Dystraktory quizu z własnych fiszek, nie z modelu
Data: 2026-09-29

**Decyzja:** Błędne odpowiedzi w quizie ABCD to odpowiedzi innych
fiszek użytkownika — najpierw z tego samego PDF-a. Quiz nie zapisuje
wyników do systemu Leitnera (to osobny tryb sprawdzania się).

**Uzasadnienie:** Model mógłby wygenerować „błędną” odpowiedź, która w
rzeczywistości jest poprawna albo wprowadza w błąd — w nauce do
kolokwium to gorsze niż brak quizu. Odpowiedzi z tego samego materiału
są wiarygodne i tematycznie bliskie, więc quiz nie jest trywialny.
Oddzielenie od Leitnera chroni harmonogram powtórek przed przypadkowym
„zgadnięciem” poprawnej odpowiedzi.

**Odrzucone alternatywy:**
- Dystraktory z Gemini — odrzucone (patrz wyżej).
- Wynik quizu jako ocena w powtórkach — odrzucone: rozpoznanie
  odpowiedzi spośród czterech jest łatwiejsze niż jej przypomnienie.

## D-034 — Każde asynchroniczne zapytanie w UI ma numer
Data: 2026-09-29

**Decyzja:** Każdy widok, który wysyła zapytania w tle (kalkulator,
korelacja, podpowiedzi, mapy), numeruje je i wyświetla tylko odpowiedź
na najnowsze; zmiana danych wejściowych (także wyczyszczenie pola)
unieważnia trwające zapytania.

**Uzasadnienie:** Przeglądy kodu kilkukrotnie znalazły ten sam rodzaj
błędu — wolniejsza, starsza odpowiedź nadpisywała nowszą. Jedna zasada
stosowana wszędzie jest łatwiejsza do sprawdzenia niż osobne łatki.

**Odrzucone alternatywy:**
- `AbortController` do przerywania zapytań — odrzucone na teraz: więcej
  kodu, a numer zapytania wystarcza, bo serwer jest lokalny i szybki.

## D-035 — Odchylenie populacyjne i skala oceny współczynnika zmienności
Data: 2026-09-29

**Decyzja:** Odchylenie standardowe liczone populacyjnie (`pstdev`), bo
gminy województwa to cała populacja, a nie próba. Ocena współczynnika
zmienności według stałej skali 25 / 45 / 100%. Histogram ma 10
przedziałów równej szerokości (nie kwantylowych jak kartogram).

**Uzasadnienie:** Tak liczy się i ocenia zróżnicowanie w statystyce
społeczno-ekonomicznej na zajęciach — wyniki zgadzają się z ręcznymi
obliczeniami studenta. Histogram o równej szerokości pokazuje kształt
rozkładu (skośność), którego klasy kwantylowe celowo nie pokazują.

**Odrzucone alternatywy:**
- Odchylenie z próby (`stdev`) — odrzucone: to nie jest próba.
- Indeks Theila — odłożone: Gini jest powszechniej znany na studiach.

## D-036 — Wskaźnik względny wybierany przez użytkownika, nie z listy
Data: 2026-09-29

**Decyzja:** Mianownik wskaźnika względnego to dowolna zmienna BDL
wyszukana przez użytkownika (plus mnożnik), a nie stała lista typu
„na 1000 mieszkańców” z zaszytym identyfikatorem zmiennej.

**Uzasadnienie:** Identyfikatorów zmiennych BDL nie dało się sprawdzić
na żywo, a zaszycie złego numeru dawałoby błędne wyniki bez ostrzeżenia.
Wybór z wyszukiwarki jest jawny (nazwa mianownika trafia do nazwy i
jednostki wskaźnika) i pozwala liczyć też „na km²”, „na 100 podmiotów”
itd. Dzielenie odbywa się po TERYT i po roku, więc działa w każdym
widoku atlasu.

**Odrzucone alternatywy:**
- Gotowy przycisk „na 1000 mieszkańców” — odłożone do czasu
  potwierdzenia identyfikatora zmiennej ludności w działającym BDL.

## D-037 — Dobór skali tylko spośród skal standardowych
Data: 2026-09-29

**Decyzja:** Kalkulator proponuje wyłącznie skale standardowe (1:500,
1:1000, 1:2000, 1:5000, 1:10 000, 1:25 000, 1:50 000, 1:100 000) — tę
najdokładniejszą, w której teren mieści się na arkuszu z marginesem.

**Uzasadnienie:** Rysunki planistyczne i mapy zasadnicze wykonuje się w
skalach standardowych; skala „1:1734” byłaby matematycznie optymalna,
ale nieprzydatna na zajęciach i w urzędzie.

**Odrzucone alternatywy:**
- Dowolna skala dopasowana do arkusza — odrzucone (patrz wyżej).

## D-038 — Karty drukowane jako składane, nie dwustronne
Data: 2026-09-29

**Decyzja:** Pytanie i odpowiedź drukujemy obok siebie na jednej
stronie; kartę składa się na pół wzdłuż linii przerywanej.

**Uzasadnienie:** Druk dwustronny wymaga lustrzanego ułożenia kart i
drukarki, która idealnie trafia w pozycję — w praktyce karty się
rozjeżdżają. Karta składana działa na każdej drukarce i z każdą
kolejnością stron.

**Odrzucone alternatywy:**
- Strony „przody” i „tyły” do druku dwustronnego — odrzucone (patrz
  wyżej).

## D-039 — Kopia zapasowa: pobieranie tak, przywracanie ręcznie
Data: 2026-09-29

**Decyzja:** Aplikacja tworzy ZIP z `instance/`, ale nie ma przycisku
„przywróć” — przywraca się ręcznie, rozpakowując ZIP (instrukcja w
środku i w `docs/URUCHOMIENIE.md`).

**Uzasadnienie:** Automatyczne przywracanie nadpisuje wszystkie dane
użytkownika; pomyłka (stara kopia, zły plik) byłaby nieodwracalna.
Ręczne przywracanie z zachowaniem starego folderu jest bezpieczne, a
robi się je rzadko. Bazy kopiowane przez `backup()`, bo zwykłe
skopiowanie pliku w trakcie zapisu może dać uszkodzoną bazę.

**Odrzucone alternatywy:**
- Przycisk „przywróć z ZIP” — odrzucone (patrz wyżej).
- Kopia z cache granic — odrzucone: duże pliki, które i tak pobiorą
  się ponownie.

## D-040 — Pola liczbowe: tylko liczby skończone
Data: 2026-09-29

**Decyzja:** Wszystkie liczby z formularzy kalkulatorów przechodzą przez
`_liczba_skonczona` (przecinek dziesiętny, spacje, odrzucenie `nan`,
`inf` i przepełnienia).

**Uzasadnienie:** `float()` w Pythonie przyjmuje „nan” i „inf”, a JSON
nie ma takich wartości — przeglądarka nie odczytałaby odpowiedzi.
Jedna funkcja zamiast osobnych warunków w każdym polu.

## D-041 — Atlas bez kafelków OSM; podkłady w mpzp i dostępności
Data: 2026-09-29

**Decyzja:** Mapa atlasu nie ładuje kafelków OpenStreetMap. Tło jest
białe (kolor karty), a pod kartogramem leżą szare województwa z PRG
(`ms:A01_Granice_wojewodztw`, uproszczone do ~1 km, cache
`instance/atlas/granice/wojewodztwa.geojson`) z nazwami sąsiadów.
W mpzp i dostępności kafelki OSM zostają, ale z opcją Leafleta
`referrerPolicy: "strict-origin-when-cross-origin"`, a obok nich
przełącznik podkładów: OSM / ortofotomapa GUGiK (WMS) / bez podkładu.

**Uzasadnienie:** Użytkownik widział wokół województwa kafelki
„Access blocked”. OSM odrzuca kafelki pobierane bez nagłówka Referer,
a nasz globalny `Referrer-Policy: same-origin` (ochrona.py) go
wycina. Kartogram gmin nie potrzebuje ulic — szare województwa dają
kontekst („gdzie jestem”) bez zależności od zewnętrznych kafelków.
Polityka ustawiona tylko na warstwie kafelków: poza nią zostaje
`same-origin`, a OSM dostaje wyłącznie adres `http://127.0.0.1:port`.

**Odrzucone alternatywy:**
- Zmiana globalnego `Referrer-Policy` — odrzucone: szersza zmiana niż
  potrzeba.
- Inny dostawca kafelków — odrzucone: wymaga klucza albo zgody.

**Niezweryfikowane:** z kontenera, w którym powstał kod, sieć do OSM,
geoportal.gov.pl i PRG jest zablokowana — działanie sprawdzone tylko na
danych testowych. Jeśli PRG nie odpowie, mapa atlasu jest po prostu
biała.

## D-042 — MPZP dla całej Polski przez krajową integrację planów (KIMPZP)
Data: 2026-09-29

**Decyzja:** Gminy bez własnego WFS w `mpzp/gminy.py` (czyli wszystkie
poza Poznaniem) obsługujemy przez usługę WMS krajowej integracji
miejscowych planów GUGiK (`mpzp/krajowe.py`): GetFeatureInfo w punkcie
działki daje atrybuty planu, a symbol przeznaczenia rozpoznajemy po
nazwie pola (symbol / oznaczenie / przeznaczenie …). Na mapie dochodzą
nakładki WMS: plany (KIMPZP) i działki (KIEG). Nazwy warstw i
obsługiwane układy współrzędnych czytamy z GetCapabilities; lista
zapasowa tylko na wypadek braku odpowiedzi. Poznań zostaje na WFS
(geometria wydzieleń → podział działki na przeznaczenia).

**Uzasadnienie:** Użytkownik chce sprawdzać działki w każdej gminie.
Dopisywanie WFS gmina po gminie nie skaluje się (2477 gmin, różne
schematy), a krajowa integracja to oficjalna usługa (nie scraping —
zgodne z CLAUDE.md). Atrybuty różnią się między gminami, dlatego
pokazujemy wszystkie, a rozpoznany symbol opisujemy jako podpowiedź.

**Ograniczenia:**
- Bez geometrii wydzieleń — podział działki na przeznaczenia (m², %)
  i szkic z kolorami są tylko dla gmin z WFS.
- Część gmin nie przekazała planów albo przekazała same skany rysunku
  (wtedy GetFeatureInfo nic nie zwraca).

**Odrzucone alternatywy:**
- Rejestr WFS wielu gmin w `gminy.py` — odrzucone: ręczna praca na
  każdą gminę, a i tak pokryłby ułamek kraju.
- Pobieranie planów APP (GML) gmin — odrzucone na teraz: pliki różnej
  wielkości i jakości, brak wspólnego punktu dostępu.

**Niezweryfikowane:** z kontenera, w którym powstał kod,
integracja.gugik.gov.pl jest zablokowana. Format odpowiedzi
(GML MapServera, zapasowo text/plain) sprawdzony tylko na przykładach
w testach. Jeśli po uruchomieniu u siebie panel pokaże błąd albo puste
atrybuty — to pierwsze miejsce do poprawki.

## D-043 — Współrzędne PL-1992/PL-2000 własnymi wzorami; pomiar liczony na serwerze
Data: 2026-09-29

**Decyzja:** Współrzędne klikniętego punktu w PL-1992 (EPSG:2180) i
PL-2000 (EPSG:2176–2179, strefa wg południka) liczy `mpzp/uklady.py`
— odwzorowanie Gaussa-Krügera szeregami Krügera (Karney 2011), bez
nowej zależności. Pomiar odległości i powierzchni na mapie MPZP liczy
serwer (`POST /mpzp/pomiar`) tymi samymi wzorami co powierzchnię
działki (`mpzp/geometria.py`).

**Uzasadnienie:** pyproj (z bazą PROJ) to kilkadziesiąt MB dla jednej
funkcji. Wzory mają ~40 linii i zgadzają się z pyproj co do milimetra
na 5 punktach w całej Polsce (test `tests/test_uklady.py`; wartości
wzorcowe policzone pyproj jednorazowo, poza projektem). Pomiar na
serwerze: jedna implementacja przeliczania stopni na metry w module,
testowana w pytest, zamiast drugiej w JS.

**Odrzucone alternatywy:**
- pyproj jako zależność — odrzucone (rozmiar, patrz wyżej).
- Pomiar w JS (Leaflet nie liczy powierzchni) — odrzucone: druga
  kopia wzorów, bez testów.

**Pominięte świadomie:** różnica WGS84 ↔ ETRF2000 (rzędu dziesiątek cm)
— bez znaczenia przy sprawdzaniu działki; do prac geodezyjnych służą
dane z operatu.

## D-044 — Krzywa dostępności liczona co minutę na serwerze
Data: 2026-09-29

**Decyzja:** Dla kolumn czasu serwer zwraca krzywą dostępności: udział
komórek (i mieszkańców, jeśli jest kolumna ludności) w zasięgu t minut
dla t = 0…60 (albo do pełnego pokrycia). Suwak progu w przeglądarce
tylko odczytuje punkt krzywej. „Luki” to 10 komórek powyżej 15 min,
sortowanych po liczbie mieszkańców (bez ludności — po czasie).

**Uzasadnienie:** Liczby tylko z serwera (jak w całym projekcie), a
suwak działa natychmiast, bez zapytania na każdą zmianę. 61 punktów to
znikomy dodatek do odpowiedzi. Pełne minuty wystarczą — dane wejściowe
i tak mają dokładność modelu ruchu pieszego.

**Odrzucone alternatywy:**
- Zapytanie do serwera przy każdym ruchu suwaka — odrzucone: zbędny ruch.
- Liczenie udziałów w JS — odrzucone: liczby miałyby dwa źródła.

## D-045 — Ocena „trudne”, tryb przed egzaminem bez zapisu, porównanie słów bez oceny
Data: 2026-09-29

**Decyzja:**
- Trzecia ocena w powtórce: „trudne” — fiszka zostaje w swoim pudełku
  i wraca jutro. W skuteczności („zapamiętane w 30 dni”) liczy się jak
  „umiem”; w „najtrudniejszych” liczą się tylko „nie umiem”.
- Tryb „przed egzaminem”: wszystkie fiszki (pliku albo wszystkie) w
  losowej kolejności; oceny nie są wysyłane na serwer, więc harmonogram
  Leitnera zostaje nietknięty.
- Tryb wpisywania odpowiedzi: podświetlamy w poprawnej odpowiedzi słowa
  o wspólnym początku (5 liter) z wpisaną, ale nie wystawiamy oceny —
  student ocenia się sam.

**Uzasadnienie:** Dwie oceny zmuszały do wyboru między „spadnij na
początek” a „awansuj”, choć często odpowiedź była wymęczona. Masowa
powtórka przed kolokwium psułaby odstępy, gdyby zapisywała oceny.
Automatyczna ocena wpisanej odpowiedzi byłaby zawodna (synonimy, szyk)
albo wymagałaby modelu językowego — porównanie słów jest przejrzyste,
a 5-literowy rdzeń wystarcza na polską odmianę w typowych definicjach.

**Odrzucone alternatywy:**
- Algorytm SM-2 (Anki) — odrzucone na teraz: prostszy Leitner jest
  czytelny dla studenta i działa; „trudne” daje większość korzyści.
- Ocena wpisanej odpowiedzi przez Gemini — odrzucone: koszt, opóźnienie,
  a werdykt modelu łatwo wziąć za pewnik.

## D-046 — Cztery metody klasyfikacji kartogramu i GVF
Data: 2026-09-29

**Decyzja:** Kartogram atlasu ma do wyboru metodę podziału na klasy —
kwantyle (dotychczasowa, domyślna), naturalne przerwy Jenksa, równe
przedziały, odchylenie standardowe — i liczbę klas 3–7. Serwer zwraca
progi, liczebność klas i GVF (goodness of variance fit). Jenks liczony
dokładnie (programowanie dynamiczne Fishera, O(k·n²)), bez biblioteki.

**Uzasadnienie:** Dobór metody klasyfikacji to podstawa kartografii
tematycznej — ta sama zmienna na mapie z kwantylami i z równymi
przedziałami wygląda zupełnie inaczej, a student powinien to widzieć i
umieć uzasadnić wybór. GVF daje liczbową ocenę podziału. Dla gmin
jednego województwa (≤ ~320) dokładny Jenks trwa ułamek sekundy, więc
biblioteka (jenkspy, mapclassify) byłaby zbędną zależnością.

**Odrzucone alternatywy:**
- mapclassify — odrzucone: ciągnie numpy/scipy dla czterech funkcji.
- Przybliżony Jenks (iteracyjny) — odrzucone: dokładny jest wystarczająco
  szybki i daje powtarzalny wynik.

## D-047 — I Morana i LISA własną implementacją, sprawdzoną z PySAL
Data: 2026-09-29

**Decyzja:** `atlas/autokorelacja.py` liczy globalne I Morana i lokalne
LISA (Anselin 1995): sąsiedztwo queen z granic PRG (styk z tolerancją
~0,001°, bo granice gmin upraszczane są osobno i między sąsiadami bywają
szczeliny), wagi standaryzowane wierszami, istotność z 999 permutacji
(dla LISA warunkowych), stałe ziarno losowania. Gminy bez sąsiadów z
danymi („wyspy”) są pomijane i zliczane. Obliczenie na żądanie
(przycisk), wynik jako trzeci tryb mapy „Klastry LISA”.

**Uzasadnienie:** Autokorelacja przestrzenna to standard analiz
regionalnych na 2. roku gospodarki przestrzennej (GeoDa, PySAL).
PySAL (libpysal + esda) ciągnie numpy, scipy, pandas i geopandas —
za dużo dla jednej funkcji. Własna implementacja ma ~150 linii; globalne
I zgadza się z esda.Moran co do 1e-15, lokalne Ii — z esda.Moran_Local
(ta sama wariancja z dzielnikiem n − 1). Wartość wzorcowa w teście
policzona PySAL jednorazowo, poza projektem. Ok. 2 s dla 320 gmin.

**Odrzucone alternatywy:**
- PySAL jako zależność — odrzucone (rozmiar, patrz wyżej).
- Istotność z rozkładu normalnego (bez permutacji) — odrzucone: dla
  wskaźników gmin (skośne rozkłady) permutacje są pewniejsze i to
  standard w GeoDa.
- Liczenie przy każdym „Pokaż” — odrzucone: 1–2 s na każde zapytanie.

## D-048 — Mapa do druku jako SVG generowany na serwerze
Data: 2026-09-29

**Decyzja:** `atlas/mapa_svg.py` składa kartogram A4 (poziomo) jako SVG:
tytuł, podtytuł, legenda z liczebnością klas, podziałka liniowa,
strzałka północy, źródło i metoda klasyfikacji (albo I Morana dla mapy
LISA). Strona `/atlas/druk` pokazuje podgląd z przyciskami „Drukuj /
zapisz PDF” i „Pobierz SVG”. Odwzorowanie: walcowe równoodległościowe ze
skalą cos φ₀. Palety kolorów powielone z atlas.js (mapa na papierze =
mapa na ekranie). Analiza autokorelacji sortuje gminy po TERYT, żeby
permutacje — a więc klastry — były takie same na ekranie i na wydruku.

**Uzasadnienie:** Student potrzebuje mapy do pracy zaliczeniowej z
obowiązkowymi elementami mapy tematycznej. Zrzut ekranu Leafleta ich nie
ma i jest rastrowy. SVG jest wektorowy, edytowalny w Inkscape i drukuje
się ostro. Dla jednego województwa zniekształcenie prostego odwzorowania
jest pomijalne, więc bez biblioteki kartograficznej.

**Odrzucone alternatywy:**
- matplotlib/geopandas do renderowania — odrzucone: ciężkie zależności.
- Eksport PNG z przeglądarki (canvas) — odrzucone: raster, bez legendy
  i podziałki w pliku.

## D-049 — Wymiary działki i obszar analizowany WZ liczone z geometrii ULDK
Data: 2026-09-29

**Decyzja:** Odpowiedź o działce zawiera `wymiary`: boki (po uproszczeniu
granicy o 20 cm), obwód, szerokość i głębokość (najmniejszy prostokąt
opisany) i zwartość Polsby-Popper. Obszar analizowany do decyzji WZ to
bufor wokół działki na odległość max(3 × szerokość frontu, 50 m)
(§ 3 ust. 2 rozporządzenia MI z 26.08.2003, Dz.U. nr 164 poz. 1588).
Front wskazuje student (bok od strony drogi) — domyślnie szerokość
działki. Serwer liczy bufor z geometrii przesłanej z mapy
(`POST /mpzp/obszar-analizowany`), bez ponownego pytania ULDK.

**Uzasadnienie:** Analiza urbanistyczna do WZ i sprawdzanie minimalnej
szerokości frontu to typowe zadania na zajęciach z planowania. Front
działki zależy od dostępu do drogi, którego nie ma w danych ULDK —
dlatego wybór zostaje przy użytkowniku, a nie jest zgadywany.
Uproszczenie o 20 cm usuwa punkty granicy leżące prawie na prostej.

**Niepewne:** nowelizacja ustawy o planowaniu z 2023 r. zmieniła zasady
WZ; panel prosi o sprawdzenie aktualnych przepisów, a reguła 3 × front /
min. 50 m jest opisana ze źródłem.

**Odrzucone alternatywy:**
- Automatyczne wykrywanie frontu (bok najbliżej drogi) — odrzucone: brak
  danych o drogach w używanych usługach, byłoby zgadywaniem.

## D-050 — „Moje działki”: osobna tabela z notatką, poza historią
Data: 2026-09-29

**Decyzja:** Tabela `zapisane` w bazie mpzp: działki zapisane gwiazdką,
z notatką (do 2000 znaków), położeniem, powierzchnią i przeznaczeniem z
chwili zapisu. Bez limitu i niezależna od historii (ta trzyma ostatnie
20 sprawdzeń). Notatka zapisuje się po wyjściu z pola; lista trafia do
CSV (średnik, BOM) i do raportu działki. Identyfikator przechodzi przez
ten sam wzorzec co wyszukiwanie ULDK.

**Uzasadnienie:** Na zajęciach pracuje się na kilku konkretnych
działkach przez cały semestr. Historia sama je wypiera, a notatka
(„wariant B”, „działka sąsiada”) jest częścią pracy. Osobna tabela
zamiast kolumny w `historia`, bo cykl życia jest inny.

**Odrzucone alternatywy:**
- Flaga „ulubiona” w tabeli historii — odrzucone: wpis znikałby po 20
  kolejnych sprawdzeniach albo historia przestałaby mieć limit.

## D-051 — Słownik symboli: rozporządzenie osobno, oznaczenia zwyczajowe osobno
Data: 2026-09-29

**Decyzja:** Do słownika z rozporządzenia z 2003 r. dochodzi osobny
`SLOWNIK_ZWYCZAJOWY` (np. MU, ML, UC, UO, UZ, ZN, ZI, KS) — oznaczenia
spoza rozporządzenia, ale częste w planach. `opisz_symbol` zwraca flagę
`zwyczajowe`, a interfejs pokazuje ją jako etykietę z wyjaśnieniem.
Słownik nigdy nie nadpisuje oznaczeń z rozporządzenia (test). Strona
`/mpzp/symbole`: rozszyfrowanie symbolu i tabela z filtrem.

**Uzasadnienie:** Student czyta plany różnych gmin i trafia na symbole
spoza rozporządzenia; „brak w słowniku” nic mu nie mówi. Ale znaczenie
takich symboli różni się między gminami — mieszanie ich z oznaczeniami
z rozporządzenia sugerowałoby pewność, której nie ma.

**Odrzucone alternatywy:**
- Jeden wspólny słownik — odrzucone: znika informacja o źródle opisu.
- Symbole z rozporządzenia z 2021 r. o danych przestrzennych aktów
  planowania — odrzucone na teraz: bez weryfikacji pełnej listy w
  źródle nie dopisujemy (zasada „nie zgaduj”).

## D-052 — Szybki model dostępności w aplikacji: linia prosta × krętość
Data: 2026-09-29

**Decyzja:** `dostepnosc/model.py` liczy czas dojścia z punktów usług
wstawionych na mapie: odległość po kuli (haversine) ze środka komórki H3
do najbliższego punktu × krętość (domyślnie 1,3) ÷ prędkość (domyślnie
4,8 km/h). Siatka: komórki bieżącego pliku (z jego wskaźnikami i
ludnością) albo nowa siatka H3 (rozdzielczość 9) dla widocznego obszaru
mapy, do 20 000 komórek. Wynik to zwykły plik CSV w folderze wyników —
działają na nim wszystkie dotychczasowe analizy — plus plik
`<nazwa>.punkty.json` z punktami, parametrami i obszarami obsługi
(komórki najbliżej danego punktu, mieszkańcy na placówkę). Istniejących
plików nie nadpisujemy (`_2`, `_3`…).

**Uzasadnienie:** Moduł z założenia czytał wyniki z zewnątrz (QGIS,
r5py), ale student 2. roku zwykle nie ma do tego warsztatu, a na
zajęciach często chodzi o szybkie porównanie wariantów lokalizacji
usługi. Te same założenia mają pliki przykładowe, więc wyniki są
spójne. Obszary obsługi (ludność na placówkę) to podstawowy wskaźnik
przy planowaniu sieci szkół czy przedszkoli.

**Ograniczenia (wprost w interfejsie):** model nie zna sieci ulic ani
barier (rzeki, tory) — to nie zastępuje analizy sieciowej.

**Odrzucone alternatywy:**
- Analiza sieciowa na OSM (Overpass + graf ulic) — odrzucone na teraz:
  nowe zależności (np. networkx/osmnx), duże pobrania, a z kontenera, w
  którym powstaje kod, OSM jest niedostępny do sprawdzenia.
- Liczenie w przeglądarce — odrzucone: liczby tylko z serwera.

## D-053 — Raport dostępności do druku: własny SVG w module
Data: 2026-09-29

**Decyzja:** `dostepnosc/druk.py` rysuje mapę A4 (heksagony H3, punkty
usług, legenda z liczbą komórek, podziałka w m/km, strzałka północy,
źródło danych), a `/dostepnosc/raport` składa stronę do druku: mapa,
mediana/min/maks, udział powierzchni i mieszkańców w zasięgu 5–30 min,
najsłabsze ogniwo, obszary obsługi, luki. Przypis mówi, skąd są liczby
(przykład syntetyczny / szybki model z parametrami / wgrany plik).

**Uzasadnienie:** Wynik analizy dostępności trafia do pracy
zaliczeniowej — potrzebna jest mapa z obowiązkowymi elementami i tabela,
a nie zrzut ekranu. Implementacja osobna od atlas/mapa_svg.py, bo
CLAUDE.md zabrania wspólnych abstrakcji dla dwóch modułów; wspólna
jest tylko idea (te same elementy mapy i format A4).

**Odrzucone alternatywy:**
- Wspólny moduł „mapa do druku” dla atlasu i dostępności — odrzucone
  (zasada projektu, patrz wyżej).

## D-054 — Szybki model: „dodaj do istniejących usług”
Data: 2026-09-29

**Decyzja:** Opcja `polacz` w `/dostepnosc/z-punktow`: gdy plik bazowy
ma już wskaźnik tej usługi (np. `czas_szkola_min`), nowy czas w komórce
to minimum ze starego i czasu do nowych punktów. Obszary obsługi nowych
punktów obejmują wtedy tylko komórki, którym nowy punkt skrócił dojście
(„mieszkańcy, którzy zyskali”). Bez takiej kolumny — czytelny błąd 400
zamiast cichego liczenia od zera. Pole usługi podpowiada usługi z pliku.

**Uzasadnienie:** Typowe pytanie planistyczne to „co da nowa szkoła
obok istniejących?”. Bez połączenia nowy plik miałby czas tylko do
nowych punktów i porównanie scenariuszy pokazywałoby bzdury. Połączony
wynik nigdy nie jest gorszy od stanu wyjściowego (test).

## D-055 — Tematy fiszek: osobna tabela wiele-do-wielu
Data: 2026-09-29

**Decyzja:** Tabela `tematy_fiszek (fiszka_id, temat)` z kaskadowym
usuwaniem. Tematy wpisuje się po przecinku (przy edycji fiszki albo
jako „temat nowych fiszek” na stronie PDF-a — zapamiętany w
przeglądarce osobno dla pliku). Porównanie bez wielkości liter; zapisuje
się pierwsza użyta pisownia. Filtr `temat` działa w kolejce powtórki
(także „przed egzaminem”), quizie i kartach do druku. Strona fiszek ma
listę tematów z liczbą fiszek i fiszek do powtórki dziś.

**Uzasadnienie:** Przed kolokwium powtarza się materiał z konkretnych
wykładów, a nie wszystko naraz; jeden PDF często obejmuje kilka tematów,
a jeden temat — kilka PDF-ów, stąd relacja wiele-do-wielu zamiast
kolumny. Osobna tabela nie wymaga migracji starych baz.

**Odrzucone alternatywy:**
- Kolumna `temat` w `fiszki` — odrzucone: jeden temat na fiszkę i
  ALTER TABLE na istniejących bazach.

## D-056 — Egzaminy: postęp z pudełek Leitnera, plan jako proste dzielenie
Data: 2026-09-29

**Decyzja:** Tabela `egzaminy (nazwa, data, temat | pdf_id | wszystko)`.
Postęp: fiszka „utrwalona” = pudełko ≥ 3 (co najmniej dwa „umiem” z
rzędu od ostatniego „nie umiem”). Plan: nieutrwalone ÷ dni do egzaminu
(dziś liczy się jako dzień nauki), zaokrąglone w górę — opisane jako
podpowiedź. Pasek „utrwalone %” także przy każdym pliku. W powtórce
przełącznik „odwróć” (przód = odpowiedź); ocena trafia do tej samej
fiszki i tego samego harmonogramu.

**Uzasadnienie:** Student uczy się pod konkretne terminy; liczba dni i
procent utrwalenia motywują i mówią, czy trzeba przyspieszyć. Pudełko 3
to rozsądny, zrozumiały próg (pudełko 5 = „opanowane” pojawia się
dopiero po tygodniach, więc byłoby zbyt surowe przed kolokwium).
Odwrócona karta ćwiczy przypominanie pojęcia z definicji — osobny
harmonogram dla kierunku podwoiłby liczbę powtórek.

**Odrzucone alternatywy:**
- Planowanie terminów powtórek pod datę egzaminu (zmiana odstępów
  Leitnera) — odrzucone: komplikuje czytelny system pudełek; tryb
  „przed egzaminem” już pozwala przejrzeć wszystko.
- Osobne pudełka dla kierunku odwróconego — odrzucone (patrz wyżej).

## D-057 — „Na tle kraju”: wartości województw z BDL, nie z gmin
Data: 2026-09-29

**Decyzja:** Pod kartogramem atlas pokazuje ranking 16 województw dla
tego samego wskaźnika i roku (`bdl.wartosci_dla_wojewodztw`, poziom 2
BDL, cache jak dla gmin), z wyróżnionym województwem z mapy, jego
miejscem i medianą województw. Wskaźnik względny dzielony tak samo jak
dla gmin. Sekcja ładuje się sama po każdym „Pokaż” (zdarzenie
`atlas:dane`, osobny plik `wojewodztwa.js`, jak korelacja).

**Uzasadnienie:** Student często pyta „czy to dużo?” — odpowiedzią jest
porównanie z innymi regionami. Bierzemy wartości policzone przez GUS dla
województw zamiast sumować gminy w aplikacji, bo dla wielu wskaźników
(średnie, udziały, stopy) suma albo średnia gmin byłaby błędna.

**Odrzucone alternatywy:**
- Agregacja z gmin — odrzucone (patrz wyżej).
- Osobny kartogram województw — odrzucone na teraz: ranking z paskami
  jest czytelniejszy przy 16 jednostkach.

## D-058 — Porównanie działek: dane pobierane na nowo, szkice w jednej skali
Data: 2026-09-29

**Decyzja:** `/mpzp/porownanie` pokazuje 2–4 działki z „Moich działek”
obok siebie: szkic (wspólna skala z największej działki + podziałka),
powierzchnię, szerokość × głębokość, obwód, zwartość, przeznaczenie
(podział z WFS albo plan krajowy), odległość obszaru analizowanego WZ
(max(3 × szerokość, 50 m) — przy założeniu, że front to krótszy bok)
i notatkę. Geometrię i plan pobieramy na nowo z ULDK/planów; błąd jednej
działki pokazujemy w jej kolumnie, reszta działa.

**Uzasadnienie:** Na zajęciach wybiera się lokalizację spośród kilku
wariantów — porównanie „na oko” na mapie przy różnych przybliżeniach
myli, a wspólna skala szkiców od razu pokazuje różnicę wielkości i
kształtu. W „Moich działkach” nie trzymamy geometrii (mogłaby się
zdezaktualizować po podziale działki), więc pobieramy ją przy
porównaniu.

**Odrzucone alternatywy:**
- Zapisywanie geometrii w „Moich działkach” — odrzucone (patrz wyżej).

## D-059 — Import fiszek: do istniejącego PDF-a, strona 0 = bez kotwicy
Data: 2026-09-29

**Decyzja:** `fiszki/importer.py` czyta eksport Anki (nagłówki `#…`,
HTML → tekst), Quizlet (tabulator), CSV/TSV z nagłówkiem `pytanie`/
`odpowiedz` (własny eksport — wtedy wraca strona i fragment) albo bez
nagłówka (2 kolumny). Import trafia do wybranego PDF-a, opcjonalnie z
tematem; powtórzone pary pytanie–odpowiedź w tym PDF-ie są pomijane,
błędne wiersze wypisane. Fiszka bez kotwicy ma stronę 0 i pusty
fragment — interfejs nie pokazuje wtedy „w źródle” ani numeru strony.
Limity: 1 MB, 2000 fiszek, 5000 znaków w polu.

**Uzasadnienie:** Studenci mają fiszki z wcześniejszych semestrów w
Anki albo Quizlecie; przepisywanie ich ręcznie zniechęca. Import do
PDF-a zamiast osobnych „talii” nie zmienia modelu danych (każda fiszka
należy do pliku) i działa ze wszystkim, co już jest: powtórki, tematy,
egzaminy, quiz.

**Odrzucone alternatywy:**
- Talie bez PDF-a — odrzucone: zmiana schematu i wszystkich widoków,
  które zakładają plik źródłowy.
- Import pakietów .apkg Anki — odrzucone: to archiwum z bazą SQLite i
  mediami; eksport tekstowy Anki wystarcza.

## D-060 — Punkty usług z CSV: tylko WGS84, przegląd na mapie przed liczeniem
Data: 2026-09-29

**Decyzja:** `POST /dostepnosc/punkty-z-pliku` czyta CSV z punktami
(nagłówki lat/lon, szerokosc/dlugosc, X/Y z QGIS, opcjonalnie nazwa;
bez nagłówka dwie pierwsze kolumny, kolejność rozpoznana po zakresie
współrzędnych Polski; przecinek dziesiętny przy średniku). Serwer tylko
sprawdza i zwraca punkty — przeglądarka stawia z nich znaczniki, które
można usunąć albo uzupełnić kliknięciem, i dopiero „Policz” liczy
model. Nazwy trafiają do obszarów obsługi (tabela, raport).
Współrzędne muszą być w stopniach (EPSG:4326); PL-1992 odrzucamy z
podpowiedzią, jak wyeksportować dane z QGIS.

**Uzasadnienie:** Listy szkół czy przychodni student ma zwykle w
arkuszu albo w QGIS — klikanie kilkudziesięciu punktów jest żmudne i
niedokładne. Przegląd na mapie przed liczeniem pozwala wyłapać błędne
współrzędne. Przeliczania z PL-1992 nie dodajemy, bo wymagałoby
odwrotnego odwzorowania w module dostępności (kod z mpzp/uklady.py nie
może być współdzielony — zasada niezależnych modułów).

**Odrzucone alternatywy:**
- Geokodowanie adresów — odrzucone: wymaga zewnętrznej usługi i zgody
  na jej użycie; współrzędne z QGIS są pewniejsze.

## D-061 — Porządki: trasy w plikach tematycznych na wspólnym blueprincie
Data: 2026-09-29

**Decyzja:** Największe pliki tras (mpzp 730, fiszki 640, atlas 614
linii) podzielone na `routes.py` (blueprint + trasy główne + wspólne
pomocnicze) i pliki `trasy_*.py` z grupami tras, które importują
blueprint z `routes.py` i rejestrują na nim swoje trasy (import
podmodułów na końcu `routes.py`). Nazwy tras (endpointy) bez zmian.
W `routes.py` zostają funkcje, które testy podmieniają (np. zapytania do
ULDK i planów), żeby podmiana dalej działała. Usunięte nieużywane
importy (pyflakes czysty, poza zamierzonym importem podmodułów).
Mapa kodu w README.

**Uzasadnienie:** Pliki po kilkaset linii z kilkoma niezwiązanymi
funkcjami są trudne do czytania po przerwie — a to projekt, do którego
autor wraca po miesiącach (CLAUDE.md). Wspólny blueprint zamiast
nowych blueprintów: adresy URL i `url_for` w szablonach bez zmian.

**Odrzucone alternatywy:**
- Osobne blueprinty dla podgrup — odrzucone: zmiana nazw endpointów w
  szablonach i JS, ryzyko pomyłek bez korzyści dla użytkownika.

## D-062 — Nowe moduły i rozszerzenia Warsztatu
Data: 2026-09-29

**Decyzja (za zgodą autora):** Warsztat rośnie z czterech do siedmiu
modułów: `osiedle` (bilans terenu koncepcji), `przepisy` (asystent do
PDF-ów z przepisami, zawsze z cytatem), `teren` (inwentaryzacja w
terenie). Dwa pomysły to rozszerzenia istniejących modułów: „Raport
gminy” w atlasie i „Kronika zmian” (ortofotomapy archiwalne) w mpzp.
Kolejność: osiedle → przepisy → raport gminy → kronika → teren.

**Uzasadnienie:** Wspólne uruchamianie, wygląd, kopia zapasowa i
możliwość korzystania z danych innych modułów. Zasady z CLAUDE.md
zostają: niezależne moduły, tylko 127.0.0.1 — dlatego „teren” nie
wystawia serwera w sieci, tylko przyjmuje dane zebrane na telefonie.

**Odrzucone alternatywy:**
- Osobne aplikacje — odrzucone: podwójne uruchamianie i kopie danych.

## D-063 — Moduł osiedle: Leaflet.draw lokalnie, rysunek jako jeden GeoJSON
Data: 2026-09-29

**Decyzja:** Nowa zależność frontendu: Leaflet.draw 1.0.4 (MIT), pliki
`dist/` skopiowane bez zmian do `static/leaflet-draw/` (bez CDN, jak
Leaflet). Wybór autora zamiast własnego rysowania. `showArea` wyłączone
(pole liczy serwer; w 1.0.4 z nowym Leafletem ta opcja rzuca błąd).
Koncepcja w bazie `instance/osiedle/osiedle.db`: nazwa + cały rysunek
jako GeoJSON w jednej kolumnie + ustawienia (JSON). Po każdej zmianie
rysunek zapisuje się w całości, a bilans liczy się od nowa na serwerze
(`osiedle/bilans.py`): m² i % funkcji od obszaru opracowania (bez
niego — od sumy), nakładanie się terenów, tereny poza obszarem, część
obszaru bez funkcji. Przeliczenie stopni na metry — własna kopia w
module (niezależność modułów).

**Uzasadnienie:** Rysowanie i edycja wierzchołków to dużo kodu, który
Leaflet.draw ma dopracowany (edycja, usuwanie, cofanie punktu). Rysunek
w jednej kolumnie: kilkadziesiąt wieloboków, zapis w całości jest
prosty i odporny na rozjazd między mapą a bazą.

**Odrzucone alternatywy:**
- Tabela terenów z wierszem na wielobok — odrzucone na teraz: więcej
  kodu synchronizacji bez korzyści przy tej skali.
- SpatiaLite — odrzucone: bilans liczy shapely, baza tylko przechowuje.

## D-064 — Osiedle: wskaźniki zabudowy z parametrów terenów
Data: 2026-09-29

**Decyzja:** Każdy teren ma parametry we właściwościach obiektu
GeoJSON: `zabudowa_proc` i `kondygnacje` (tylko MN, MW, U) oraz
`pbc_proc` (wszystkie funkcje). Brak parametru = wartość typowa z tabeli
`DOMYSLNE` w `osiedle/wskazniki.py`, pokazywana w panelu jako
podpowiedź (MN 30%/2 kond./PBC 50%, MW 30%/5/30%, U 40%/2/20%, ZP PBC
90%, KD i KS 0%, WS 100% — woda powierzchniowa liczy się do terenu
biologicznie czynnego wg rozporządzenia o warunkach technicznych).
Wskaźniki (powierzchnia zabudowy i całkowita, wskaźnik zabudowy,
intensywność, PBC, najwyższa zabudowa) liczy serwer dla całego obszaru
opracowania, a bez niego — dla sumy terenów. Ustalenia planu (max
zabudowa, min/max intensywność, min PBC, max kondygnacje) są w
`ustawienia.plan` koncepcji; zgodność liczy serwer. Rysunek i ustalenia
zapisują się jednym żądaniem, więc żadna zmiana nie ginie w opóźnieniu
drugiej.

**Uzasadnienie:** Parametry na terenie zamiast rysowania budynków —
na etapie koncepcji planista myśli udziałami i kondygnacjami. Wartości
typowe widoczne w polu, żeby nie było ukrytych założeń. Definicje
wskaźników jak w module MPZP; kod osobny (niezależność modułów).

**Odrzucone alternatywy:**
- Rysowanie obrysów budynków — odrzucone na teraz: dużo pracy na
  mapie, a koncepcja urbanistyczna tego nie wymaga.
- Zgodność liczona osobno dla każdego terenu — odrzucone na teraz:
  parametry terenu to wprost udziały, więc porównanie widać od razu.

## D-065 — Osiedle: program z jawnych założeń
Data: 2026-09-29

**Decyzja:** `osiedle/program.py` szacuje z powierzchni całkowitej
terenów MN, MW i U: mieszkania (udział powierzchni mieszkań / średni
metraż, osobno MN i MW), mieszkańców, gęstość na hektar obszaru,
potrzebne miejsca postojowe i miejsca mieszczące się na terenach KS,
dzieci w wieku przedszkolnym i szkolnym z liczbą oddziałów oraz zieleń
urządzoną na mieszkańca. Wszystkie założenia (11 liczb) są w tabeli
`ZALOZENIA` z zakresem dopuszczalnym, widoczne w panelu jako
podpowiedzi i zmieniane per koncepcja (`ustawienia.program`). Liczby
całkowite w dół z tolerancją 0,01 na błąd przeliczenia powierzchni.

**Uzasadnienie:** Wartości domyślne to typowe założenia do szkicu, nie
normy ani dane GUS — dlatego są jawne i opisane w panelu jako „zmień
pod swoją gminę”. Model językowy nie bierze udziału (liczby z kodu).

**Odrzucone alternatywy:**
- Wskaźniki demograficzne pobierane z GUS BDL dla gminy — odrzucone
  na teraz: wymaga wyboru gminy w koncepcji; można dodać później.

## D-066 — Osiedle: raport, szkic SVG i porównanie wariantów
Data: 2026-09-29

**Decyzja:** Warianty to po prostu osobne koncepcje. Strona
`/osiedle/porownanie?id=…` (2–4 koncepcje) stawia je obok siebie:
szkice w jednej skali, bilans, wskaźniki, zgodność z planem („2 z 3”)
i program. Raport koncepcji (`/osiedle/koncepcje/<id>/raport`) drukuje
się do PDF z przeglądarki: szkic z legendą, podziałką i strzałką
północy, bilans, wskaźniki, zgodność, program i przyjęte założenia (z
wartością typową, gdy zmieniona). Szkic rysuje `osiedle/rysunek_svg.py`
po stronie serwera. W SVG są tylko liczby i kolory z kodu, więc
wstawiamy go do strony bez ucieczki. Trasy są w `osiedle/trasy_druk.py`.

**Uzasadnienie:** Wariant jako koncepcja nie wymaga nowego modelu
danych, a porównanie w jednej skali pokazuje różnice od razu.

**Odrzucone alternatywy:**
- Warianty wewnątrz jednej koncepcji — odrzucone: więcej kodu, ta sama
  wartość.
- Generowanie PDF na serwerze — odrzucone: druk z przeglądarki
  wystarcza (jak w innych raportach), bez nowej zależności.

## D-067 — Moduł przepisy: pypdf na serwerze, FTS5, jednostka = artykuł
Data: 2026-09-29

**Decyzja:** Nowy moduł `przepisy` (baza `instance/przepisy/przepisy.db`,
PDF-y w `instance/przepisy/pliki/`). Nowa zależność: **pypdf 6.19.0**
(czysty Python, licencja BSD) — wyciąga tekst z PDF-a na serwerze.
Tekst dzielimy na jednostki: artykuły („Art. 15.”) i paragrafy („§ 4.”)
zaczynające się na początku wiersza; wycinamy nagłówki stron ISAP i
Dziennika Ustaw, sklejamy przeniesienia wyrazów. Wyszukiwarka: SQLite
FTS5 (wbudowane w sqlite3, bez nowej zależności) z tokenizerem
`unicode61 remove_diacritics 2`; do indeksu i zapytań idzie tekst z
„ł” zamienionym na „l” (tokenizer tego nie robi), odmianę zastępuje
szukanie po początku słowa. Podgląd z podświetleniem liczy Python na
oryginalnym tekście. „art. 15” / „§ 4” szuka po oznaczeniu. Kotwica w
źródle: numer strony PDF-a i link `#page=N` (przeglądarka otwiera PDF
na tej stronie).

**Uzasadnienie:** Pytania do przepisów (ETAP 62) wymagają tekstu całego
aktu na serwerze, żeby wybrać właściwe artykuły i sprawdzić cytaty.
pdf.js w przeglądarce (jak w fiszkach) musiałby przesyłać cały tekst i
wiązałby moduł z plikami innego modułu. Artykuł to naturalna jednostka
cytowania przepisów.

**Odrzucone alternatywy:**
- pdfminer.six / PyMuPDF — cięższe (PyMuPDF: licencja AGPL); pypdf
  wystarcza dla tekstowych PDF-ów z ISAP.
- Polski stemmer (np. Morfologik) — duża zależność; szukanie po
  początku słowa daje wystarczające wyniki.
- Pobieranie aktów z API ISAP — odrzucone na teraz: użytkownik wgrywa
  PDF, który i tak ma pod ręką; do rozważenia później.

## D-068 — Przepisy: odpowiedź modelu tylko z cytatami sprawdzonymi w tekście
Data: 2026-09-29

**Decyzja:** Pytanie zadane zdaniem → kod wybiera do 8 jednostek (FTS5,
słowa połączone OR, bez słów pytających z listy `SLOWA_POMIJANE`, bez
tytułu aktu) → Gemini (`dane/gemini.py: odpowiedz_z_przepisow`) dostaje
tylko je, ponumerowane, i ma zwrócić JSON: odpowiedź + dosłowne cytaty
ze wskazaniem fragmentu. `przepisy/pytania.py` sprawdza: cytat musi być
w tekście wskazanej jednostki (porównanie bez białych znaków, z
ujednoliconymi cudzysłowami i myślnikami, bez wielkości liter);
fałszywe cytaty są odrzucane i liczone; odpowiedź bez żadnego
prawdziwego cytatu nie jest pokazywana (chyba że model sam stwierdził
brak odpowiedzi); liczba w odpowiedzi, której nie ma w jednostkach ani
w pytaniu, odrzuca całą odpowiedź. Kotwica: artykuł w stronie aktu i
strona PDF (początek jednostki). Historia pytań w tabeli `pytania` (z
kopią cytatów).

**Uzasadnienie:** Przy przepisach zmyślony cytat jest gorszy niż brak
odpowiedzi. Weryfikacja w kodzie realizuje zasadę CLAUDE.md: model
tłumaczy i opisuje, treść i liczby pochodzą ze źródła.

**Odrzucone alternatywy:**
- Wysyłanie modelowi całego aktu — długie ustawy przekraczają rozsądny
  rozmiar zapytania, a cytaty trudniej sprawdzić.
- Wyszukiwanie semantyczne (embeddingi) — nowa zależność i koszt;
  FTS5 z odmianą po początku słowa wystarcza na start.

## D-069 — Atlas: Raport gminy z zestawu wskaźników ułożonego przez użytkownika
Data: 2026-09-29

**Decyzja:** „Raport gminy” (`/atlas/raport-gminy`) pokazuje dla jednej
gminy każdy wskaźnik z zestawu raportu: ostatni rok z danymi, wartość,
zmianę od najstarszego roku z ostatnich 10 lat, miejsce w województwie
w tym samym roku (1 = najwyższa, remisy dzielą miejsce), medianę
województwa i mały wykres trendu, z opcjonalną charakterystyką Gemini
(ze sprawdzaniem liczb, jak w opisie wskaźnika). Zestaw wskaźników
(tabela `raport_wskazniki` w bazie atlasu, wspólny dla wszystkich gmin)
użytkownik układa z wyszukiwarki BDL. Przeliczenie „na 1000
mieszkańców” — mianownik wybierany spośród wskaźników zestawu. Lista
gmin województwa: nowe zapytanie BDL `/units?parent-id=…&level=6`
(`bdl.gminy_wojewodztwa`), województwo gminy z identyfikatora BDL.
Każdy wskaźnik to osobne zapytanie z przeglądarki (po 3 naraz). Zmiana
w tabeli bez kolorów „dobrze/źle”, tylko ▲/▼.

**Uzasadnienie:** Identyfikatorów zmiennych BDL nie wpisujemy w kod z
pamięci — nie da się ich tu sprawdzić, a pomyłka dałaby raport z
cudzymi danymi (ta sama zasada co przy szybkim wyborze, ETAP 40).
Użytkownik widzi dokładną nazwę GUS przy dodawaniu. Osobne zapytania
na wskaźnik: wolne API GUS nie blokuje strony, a błąd jednego wskaźnika
nie psuje reszty.

**Odrzucone alternatywy:**
- Gotowy zestaw wskaźników z identyfikatorami w kodzie — odrzucone
  (zgadywanie identyfikatorów).
- Jedno zapytanie liczące cały raport — długie czekanie bez postępu.

## D-070 — MPZP: Kronika zmian z latami odczytanymi z opisu usługi WMS
Data: 2026-09-29

**Decyzja:** Strona `/mpzp/kronika` (z panelu działki albo nagłówka
MPZP) pokazuje ortofotomapy archiwalne w miejscu działki: suwak lat z
odtwarzaniem albo dwa lata obok siebie na zsynchronizowanych mapach, z
granicą działki z ULDK. Adres usługi WMS jest w konfiguracji
(`ORTO_ARCHIWALNA_WMS`, domyślnie usługa archiwalna GUGiK
„StandardResolutionTime”). Lat nie ma w kodzie: serwer
(`dane/ortofoto.py`) czyta GetCapabilities (pamięć 24 h) i obsługuje
dwa zapisy — wymiar czasu warstwy (lista dat → parametr TIME; przedział
→ zapytanie o cały rok z ostrzeżeniem w interfejsie) albo osobną
warstwę na rok (rok w nazwie/tytule). Kafelki pobiera przeglądarka
(Leaflet WMS), jak podkład ortofotomapy w innych modułach.

**Uzasadnienie:** Z tego środowiska nie da się sprawdzić, jakie lata i w
jakiej postaci podaje usługa GUGiK — wpisanie ich z pamięci byłoby
zgadywaniem. Opis usługi jest źródłem prawdy; gdy GUGiK zmieni adres,
wystarczy wpis w `.env`.

**Odrzucone alternatywy:**
- Lista lat w kodzie — zgadywanie i starzenie się listy.
- Pobieranie kafelków przez serwer Warsztatu — niepotrzebne pośrednictwo;
  pozostałe mapy też biorą kafelki wprost z usług.

## D-071 — Moduł teren: samodzielny formularz HTML na telefon i import pliku
Data: 2026-09-29

**Decyzja:** Nowy moduł `teren` (baza `instance/teren/teren.db`, zdjęcia
w `instance/teren/zdjecia/`). Projekt inwentaryzacji ma pola formularza
(lista wyboru, tekst, liczba, tak/nie; trzy wzory: zieleń, stan
zabudowy, przestrzeń publiczna) i losowy klucz. Warsztat generuje
**jeden samodzielny plik HTML** (cały CSS i JS w środku, bez zasobów z
sieci), który użytkownik przenosi na telefon i otwiera w przeglądarce.
Formularz działa bez internetu: położenie z GPS (śledzenie do ±10 m albo
30 s, najlepszy odczyt; współrzędne ręczne jako zapas), pola, zdjęcie
zmniejszane na telefonie do 1600 px (JPEG 0,8), uwagi; punkty w
IndexedDB telefonu (osobna baza na projekt). Eksport: plik JSON
(`format: warsztat-teren`, wersja 1, klucz projektu, punkty z uid).
Import w Warsztacie sprawdza każde pole (typy, opcje z listy, zakresy
współrzędnych, zdjęcie tylko JPEG do 4 MB) — cały plik albo nic; punkty
o znanym uid są pomijane, więc ponowny import nie dubluje. Mapa punktów
(kolor wg pola wyboru, legenda z ukrywaniem), tabela, eksport GeoJSON i
CSV.

**Uzasadnienie:** Warsztat nasłuchuje tylko na 127.0.0.1 (CLAUDE.md:
nie bindować na 0.0.0.0), więc telefon nie może wysyłać danych do
aplikacji. Plik HTML + plik JSON to najprostszy obieg bez serwera, bez
konta i bez internetu w terenie. Klucz projektu chroni przed
zaimportowaniem pliku do złego projektu.

**Odrzucone alternatywy:**
- Udostępnienie Warsztatu w sieci lokalnej — sprzeczne z zasadą
  127.0.0.1.
- Gotowe aplikacje (QField, Mergin) — dobre, ale wymagają osobnej
  konfiguracji projektu QGIS; do rozważenia jako uzupełnienie.
- Podkład mapy w formularzu na telefonie — kafelki wymagają internetu;
  współrzędne i dokładność wystarczą, mapa jest w Warsztacie.

## D-072 — Zapis koncepcji osiedla: treść brana w chwili wywołania
Data: 2026-09-29

**Decyzja:** Zapis rysunku osiedla (z opóźnieniem 300 ms) bierze
identyfikator koncepcji, rysunek i ustawienia w chwili wysłania, a nie
po odpowiedzi serwera; przed przełączeniem koncepcji zaległy zapis
wysyła się od razu (`dokonczZapis`), a przy wyjściu ze strony — przez
`fetch` z `keepalive`. Menu aplikacji w wąskim oknie przewija się
w poziomie zamiast poszerzać stronę. Usunięcie aktu prawnego usuwa
pytania z historii, które cytowały ten akt.

**Uzasadnienie:** Przegląd kodu po ETAPach 57–65 znalazł błąd utraty
danych: przełączenie koncepcji w ciągu 300 ms od zmiany rysunku
zapisywało do poprzedniej koncepcji pusty rysunek (odtworzone w
przeglądarce przed poprawką, sprawdzone po niej). Siedem pozycji menu
nie mieści się w oknie o szerokości połowy ekranu.

**Odrzucone alternatywy:**
- Zapis bez opóźnienia po każdej zmianie — więcej zapytań przy
  przesuwaniu wierzchołków, a problem kolejności i tak zostaje.

## D-073 — Osiedle: punkty z modułu Teren jako warstwa podglądu
Data: 2026-09-29

**Decyzja:** Koncepcja osiedla może pokazywać punkty jednego projektu
inwentaryzacji (wybór w panelu „Koncepcja”, zapisany w
`ustawienia.teren_projekt`). Osiedle pobiera je przez istniejące trasy
modułu Teren (`/teren/projekty.json` — nowa lista, `/teren/projekty/<id>/punkty`).
Warstwa jest tylko do podglądu: poza rysunkiem, nie wchodzi do bilansu
ani do eksportu. Pusta koncepcja przybliża mapę do punktów. Usunięty
projekt terenowy — wybór po cichu wraca do „nie pokazuj”.

**Uzasadnienie:** Inwentaryzacja to podstawa koncepcji (np. drzewa do
zachowania). Moduły zostają niezależne: Osiedle używa publicznych tras
Terenu jak zewnętrznej usługi, bez wspólnego kodu.

**Odrzucone alternatywy:**
- Kopiowanie punktów do koncepcji — dwie wersje tych samych danych.

## D-074 — Fiszka z cytatu przepisu: jedno wejście do fiszek z zewnątrz
Data: 2026-09-29

**Decyzja:** Przy każdym sprawdzonym cytacie odpowiedzi w Przepisach
jest „+ Fiszka” (pytanie i odpowiedź do poprawienia, temat „przepisy”).
Przepisy wołają jedną funkcję modułu fiszek:
`fiszki/zewnetrzne.py: dodaj_fiszke(...)` — to jedyne wejście do
fiszek z innego modułu. Fiszka dostaje prawdziwą kotwicę: PDF aktu
kopiowany do plików fiszek raz (rozpoznanie po SHA-256, tabela
`pdf_skroty`), strona — ta z zakresu stron artykułu, na której tekst
naprawdę zawiera cytat (pypdf), fragment — sam cytat. Przy okazji
naprawiono podgląd PDF w fiszkach: strona szersza niż kolumna miała
niewidoczny lewy brzeg (środkowanie flexboksem), teraz `margin: auto`.

**Uzasadnienie:** Zasada fiszek to kotwica w źródle — fiszka z przepisu
bez PDF-a byłaby słabsza niż fiszki z podręczników. Jedna, nazwana
funkcja zamiast sięgania do bazy fiszek z przepisów: zależność jest w
jednym miejscu i w jedną stronę (przepisy → fiszki).

**Odrzucone alternatywy:**
- Fiszka bez kotwicy (strona 0, jak import CSV) — traci „Pokaż w źródle”.
- Współdzielenie pliku PDF między modułami — usunięcie aktu w
  przepisach psułoby fiszki.

## D-075 — Raport z terenu: mapa schematyczna bez podkładu
Data: 2026-09-29

**Decyzja:** Raport projektu terenowego (`/teren/projekty/<id>/raport`,
druk/PDF z przeglądarki): mapa SVG generowana na serwerze
(`teren/raport.py`) — punkty w metrach lokalnej skali, numery w
kolejności pomiaru, kolor wg wybranego pola wyboru (domyślnie
pierwszego), podziałka, północ; zestawienie pól (liczebności i % dla
list wyboru i tak/nie, min–max, średnia, mediana dla liczb, liczba
wypełnionych dla tekstu); tabela punktów ze współrzędnymi i
dokładnością GPS; dokumentacja fotograficzna z tymi samymi numerami.

**Uzasadnienie:** Raport do zaliczenia ćwiczeń terenowych ma się dać
wydrukować zawsze — bez internetu i kafelków z cudzych serwerów. Wspólny
numer punktu łączy mapę, tabelę i zdjęcia.

**Odrzucone alternatywy:**
- Mapa z podkładem (OSM/ortofotomapa) — zależna od sieci i licencji
  kafelków przy druku; dokładny podkład daje eksport GeoJSON do QGIS.

## D-076 — Teren: pole-skala z kolorami od zielonego do czerwonego
Data: 2026-09-29

**Decyzja:** Pole „lista wyboru” może być oznaczone jako skala
(`"skala": true`): opcje są wtedy uporządkowane od najlepszej do
najgorszej i mapa projektu oraz raport kolorują je od zielonego do
czerwonego (odcień HSL 130° → 0°, ten sam wzór w `teren/raport.py` i
`teren.js`). Zaznaczenie w edytorze pól; we wzorach projektów pola
„stan” i „stan techniczny” są skalą od razu. Pola bez skali — dotychczasowa
paleta.

**Uzasadnienie:** Kolory z palety po kolei dawały np. „zły” na zielono.
Znaczenia opcji nie odgadujemy ze słów („zły”, „ruina”) — o kolejności
decyduje użytkownik, który zna swoje kategorie.

**Odrzucone alternatywy:**
- Rozpoznawanie słów „dobry/zły” w opcjach — zgadywanie, zawodne dla
  własnych kategorii.
