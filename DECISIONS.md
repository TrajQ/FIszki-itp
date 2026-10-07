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

## D-077 — Aktualizacja z ZIP-a skryptem, z kopią zapasową i listą plików wersji
Data: 2026-09-29

**Decyzja:** `./aktualizuj.sh` (logika w `aktualizacja.py`, tylko
biblioteka standardowa Pythona) aktualizuje instalację z pobranego
ZIP-a: znajduje najnowszy `warsztat_etap*.zip` w Pobranych (albo
wskazany), sprawdza ZIP (katalog `warsztat/`, `app.py`, brak ścieżek
wychodzących poza katalog), przerywa, gdy aplikacja działa, robi kopię
zapasową w `~/warsztat_kopie/`, podmienia pliki programu, nigdy nie
dotyka `instance/`, `.env`, `.venv/`, usuwa pliki z poprzedniej wersji
nieobecne w nowej (lista w `.pliki_wersji`; przy pierwszym użyciu nic
nie usuwa) i instaluje zależności, zapisując sumę `requirements.txt` tak
jak `uruchom.sh`. Skrypt bash ma całą treść w funkcji — bash wczytuje ją
przed wykonaniem, więc podmiana skryptu w trakcie nie szkodzi.

**Uzasadnienie:** Autor aktualizuje po każdym ETAPie, ręczne
przenoszenie plików grozi nadpisaniem danych albo `.env`. Kopia przed
zmianą pozwala wrócić bez gita.

**Odrzucone alternatywy:**
- `git pull` jako jedyna droga — autor instaluje z ZIP-ów.
- rsync — nie zawsze zainstalowany, a lista plików wersji i tak jest
  potrzebna do usuwania starych plików.

## D-078 — Teren: poprawki punktów po imporcie
Data: 2026-09-29

**Decyzja:** Punkt po imporcie można poprawić w Warsztacie (PUT
`/teren/projekty/<id>/punkty/<pid>`, panel „Popraw punkt” z tabeli albo
dymka): wartości pól, uwagi, położenie (przeciąganie znacznika na mapie,
z podglądem przesunięcia w metrach). Przesunięty punkt ma
`polozenie_reczne = 1`, a dokładność GPS jest kasowana — raport i
eksporty pokazują „poprawione ręcznie”. Nowe kolumny (`polozenie_reczne`,
`data_poprawki`) dopisuje `init_db` przez ALTER TABLE, gdy ich brak —
stare bazy działają bez utraty danych. Ponowny import pliku z telefonu
nie nadpisuje poprawek (punkty o znanym uid są pomijane).

**Uzasadnienie:** GPS telefonu przy budynkach i pod koronami drzew myli
się o kilkanaście metrów, a literówki w terenie są normalne. Oznaczenie
ręcznego położenia zachowuje uczciwość danych w raporcie.

**Odrzucone alternatywy:**
- Przechowywanie historii wszystkich zmian — więcej kodu niż potrzeba;
  zostaje data ostatniej poprawki.

## D-079 — Raport gminy: mapa położenia z granic PRG
Data: 2026-09-29

**Decyzja:** Raport gminy ma w nagłówku mapę położenia
(`/atlas/raport-gminy/<id>/mapa.svg`, `mapa_svg.polozenie_gminy_svg`):
gminy województwa na szaro, wybrana gmina wyróżniona i narysowana na
wierzchu, podziałka, północ. Granice z tej samej pamięci podręcznej PRG
co kartogram, to samo odwzorowanie. Obrazek ładuje się niezależnie od
tabeli; przy błędzie PRG zostaje podpis z przyczyną.

**Uzasadnienie:** Wydruk raportu bez lokalizacji gminy był niepełny;
kod rysowania granic już był w module.

**Odrzucone alternatywy:**
- Mapa na podkładzie kafelkowym — zależna od sieci przy druku.

## D-080 — Fiszki na telefon: samodzielny plik HTML, wyniki wracają plikiem
Data: 2026-09-29

**Decyzja:** „Fiszki na telefon” (strona Fiszek) pobiera samodzielny plik
HTML z fiszkami z wybranego zakresu (wszystkie, temat, plik PDF), ich
stanem pudełek i zasadami Leitnera z `fiszki/powtorki.py` (jedno źródło
odstępów). Telefon planuje powtórki sam (także przez kilka dni), stan i
wyniki trzyma w IndexedDB; „nie umiem” wraca w tej samej sesji. Stan z
telefonu wygrywa nad stanem z pliku tylko, gdy powstał po pobraniu pliku.
Wyniki eksportuje do JSON (`warsztat-powtorki`, wersja 1, identyfikator
instalacji). Import (`fiszki/telefon.py`) stosuje wyniki w kolejności
czasu z datą z telefonu, pomija wyniki o znanym uid (tabela
`powtorki_z_telefonu`) i fiszki usunięte; gdy fiszkę powtórzono na
komputerze później — wynik z telefonu trafia tylko do dziennika
(statystyk). Identyfikator instalacji (tabela `ustawienia`) chroni przed
plikiem z innej instalacji.

**Uzasadnienie:** Ten sam obieg co w module Teren (D-071): Warsztat działa
tylko na 127.0.0.1. Nauka w drodze bez sieci, bez konta w usłudze.

**Odrzucone alternatywy:**
- Eksport do Anki (już jest, ETAP 54) — gubi stan pudełek Warsztatu i
  wyniki nie wracają.
- Pokazywanie na telefonie tylko fiszek „na dziś” — nauka przez kilka dni
  bez nowego pliku byłaby niemożliwa.

## D-081 — Zgoda autora: kolejne ETAPy wybierane samodzielnie
Data: 2026-09-29

**Decyzja:** Autor napisał: „rób i dodawaj kolejne rzeczy sam bez
pytania”. Od ETAPu 75 kolejne usprawnienia wybieram sam, bez pytania o
zgodę przed każdym (zmiana zasady 2 z CLAUDE.md na czas tej zgody).
Reszta zasad bez zmian: jeden ETAP na raz, testy zielone przed następnym,
dokumentacja, rekord w DECISIONS i ZIP po każdym, bez nowych zależności
bez uzasadnienia, bez zmiany stosu, 127.0.0.1, liczby tylko z danych.
Każdy ETAP ma być małym, sprawdzalnym usprawnieniem istniejących modułów,
a nie wymyślaniem nowych.

**Uzasadnienie:** Wyraźne polecenie autora; zapis tutaj, żeby kolejna
sesja wiedziała, skąd zmiana trybu pracy.

## D-082 — Osiedle: obszar opracowania z działek ewidencyjnych (ULDK)
Data: 2026-09-29

**Decyzja:** Panel „Co rysujesz” ma pole na identyfikatory działek; POST
`/osiedle/koncepcje/<id>/obszar-z-dzialek` pobiera granice z ULDK (klient
`dane/uldk.py`, wspólna warstwa danych, bez sięgania do modułu mpzp),
łączy je (`unary_union`) i zapisuje jako obszar opracowania — zastępuje
dotychczasowy, tereny zostają. Identyfikatory działek zapisane we
właściwościach obszaru (widać je w eksporcie GeoJSON). Do 50 działek;
duplikaty pomijane; pierwszy błąd (zły format, brak działki, awaria
ULDK) przerywa bez zmian w koncepcji.

**Uzasadnienie:** Koncepcja na prawdziwych granicach ewidencyjnych jest
dokładniejsza niż obrys rysowany na podkładzie; identyfikatory student
ma z modułu MPZP.

**Odrzucone alternatywy:**
- Klikanie działek na mapie osiedla — więcej zapytań ULDK i kodu mapy;
  lista identyfikatorów wystarcza na start.

## D-083 — Raport gminy: porównanie z drugą gminą i CSV
Data: 2026-09-29

**Decyzja:** Raport gminy przyjmuje `?porownaj=<id BDL>` — druga gmina z
dowolnego województwa; tabela dostaje jej wartość i miejsce we WŁASNYM
województwie (miejsca z różnych województw nie są porównywalne wprost,
dlatego nagłówek podaje województwo, gdy jest inne). Wybór gminy nad
raportem (województwo → gmina). `/atlas/raport-gminy/<id>.csv` — tabela
(obu gmin) w CSV z przecinkiem dziesiętnym i BOM dla polskiego Excela.
Dane z tych samych, zapamiętanych odpowiedzi BDL co raport na ekranie.

**Uzasadnienie:** Diagnoza uwarunkowań zwykle porównuje gminę z
sąsiednią albo podobną; CSV — do tabel w pracy.

**Odrzucone alternatywy:**
- Więcej niż dwie gminy naraz — tabela przestaje się mieścić na A4.

## D-084 — Przepisy: porównanie wersji aktu po oznaczeniach jednostek
Data: 2026-09-29

**Decyzja:** Strona `/przepisy/porownanie?stary=&nowy=` zestawia dwa
wgrane akty: jednostki łączone po oznaczeniu („Art. 15”), status dodana /
usunięta / zmieniona / bez zmian, w zmienionych różnice słowo po słowie
(`difflib.SequenceMatcher` z biblioteki standardowej; białe znaki nie są
zmianą). Usunięte jednostki stoją tam, gdzie były w starej wersji.
Domyślnie tylko zmiany.

**Uzasadnienie:** Nowelizacje (np. reforma planowania z 2023 r.) zmieniają
dziesiątki artykułów; porównanie tekstów jednolitych pokazuje, co
naprawdę się zmieniło, bez czytania całości.

**Odrzucone alternatywy:**
- Dopasowanie przenumerowanych artykułów po podobieństwie treści —
  zgadywanie; przenumerowanie pokazujemy uczciwie jako usunięcie i dodanie.

## D-085 — Dostępność: „Gdzie nowa placówka?” — maksymalne pokrycie, zachłannie
Data: 2026-09-29

**Decyzja:** Dla wskaźnika czasu dojścia do jednej usługi kod proponuje
1–5 miejsc nowej placówki (`dostepnosc/lokalizacja.py`): komórki z czasem
powyżej progu (suwak krzywej dostępności) ważone mieszkańcami (bez
ludności — liczbą komórek), kandydaci = komórki siatki z pliku, zasięg
nowej placówki z szybkiego modelu (linia prosta × krętość / prędkość,
parametry z panelu modelu), wybór zachłanny — każda kolejna placówka po
uwzględnieniu poprzednich. Wynik: miejsca na mapie (numerowane
znaczniki), liczba obejmowanych mieszkańców, udział w zasięgu przed i po.
Sąsiedztwo liczone przez `h3.grid_disk` z promieniem z progu, potem
sprawdzane odległością — 631 komórek w ok. 0,05 s.

**Uzasadnienie:** Klasyczne zadanie planistyczne (MCLP) na danych, które
moduł już ma; liczby liczy kod, a uproszczenia są jawnie opisane w panelu.

**Odrzucone alternatywy:**
- Dokładne rozwiązanie programowaniem całkowitoliczbowym — nowa
  zależność (solver) i wolniej; zachłanny wynik jest zrozumiały krok po
  kroku, a pierwsza propozycja jest optymalna.

## D-086 — Przegląd po ETAPach 67–78
Data: 2026-09-30

**Decyzja:** Przegląd kodu i stron po dwunastu ETAPach: pyflakes na całym
projekcie i `node --check` na wszystkich skryptach — czysto; przegląd
logiki nowych ścieżek danych (import wyników z telefonu, fiszki z
przepisów, poprawki punktów, obszar z działek, aktualizator, lokalizacja
placówek) — bez błędów. Test wszystkich 24 stron aplikacji w trzech
szerokościach okna (1300, 700, 390 px): brak błędów JS; na 390 px trzy
strony wychodziły poza okno (suwak lat kroniki, tabela symboli planu,
tabela punktów w raporcie z terenu) — poprawione (zawijanie, przewijanie
tabeli w poziomie; wydruk bez zmian).

**Uzasadnienie:** Co kilka ETAPów przegląd całości — poprzedni (D-072)
znalazł błąd utraty danych, którego testy jednostkowe nie łapały.

## D-087 — MPZP: karta działki zamiast osobnego raportu
Data: 2026-09-30

**Decyzja:** Raport działki (`/mpzp/raport`) rozbudowany do karty
działki: wymiary (szerokość × głębokość, obwód, zwartość — z istniejącej
`geometria.wymiary`), środek działki w WGS84, PL-1992 i PL-2000,
ortofotomapa obecna i najstarsza archiwalna z żółtym obrysem granicy
(`mpzp/karta.py`), linki do kroniki zmian i kalkulatora zabudowy.
Obrazy WMS pobiera przeglądarka: GetMap 1.3.0, CRS=EPSG:3857, BBOX w
metrach x,y — ten sam układ co mapy Leaflet w aplikacji; obrys liczony
tymi samymi wzorami Web Mercator, więc pasuje do obrazu. Najstarszy
rocznik dobiera skrypt strony z zapamiętanego opisu usługi archiwalnej
(D-070) — wolna usługa nie blokuje otwarcia karty.

**Uzasadnienie:** Wszystko, co moduł wie o działce, na jednej stronie do
wydruku; bez nowej strony obok istniejącego raportu.

**Odrzucone alternatywy:**
- Układ PL-1992 (EPSG:2180) w zapytaniu WMS — kolejność osi w WMS 1.3.0
  dla tego układu łatwo pomylić, a nie da się jej tu sprawdzić na żywo.

## D-088 — Osiedle: plan miejscowy i działki jako nakładki pod rysunkiem
Data: 2026-09-30

**Decyzja:** Mapa Osiedla ma w przełączniku warstw nakładki „Plan
miejscowy (GUGiK)” (przezroczystość 0,55) i „Działki ewidencyjne
(GUGiK)” — te same usługi WMS krajowych integracji co w MPZP, z nazwami
warstw z trasy `/mpzp/warstwy-krajowe` (Osiedle korzysta z niej jak z
usługi, bez importu kodu MPZP). Włączone nakładki zapamiętane w
przeglądarce. Rysunek koncepcji jest zawsze nad nimi.

**Uzasadnienie:** Koncepcję rysuje się w granicach i przeznaczeniach
planu — obraz planu pod rysunkiem uzupełnia wpisywanie ustaleń (D-064).

**Odrzucone alternatywy:**
- Automatyczne przepisanie wskaźników z planu do koncepcji — usługa
  podaje je jako tekst w różnych formatach; zgadywanie liczb z tekstu
  łamie zasadę „liczby z danych”.

## D-089 — Przepisy: fiszki z całego artykułu, sprawdzane cytatem i liczbami
Data: 2026-09-30

**Decyzja:** Przy każdej jednostce na stronie aktu „✦ Fiszki”: Gemini
(`dane/gemini.py: zaproponuj_fiszki_z_przepisu`, prompt dla przepisów —
treść normy, wskazanie jednostki redakcyjnej) proponuje do 4 fiszek z
dosłownym cytatem. Serwer odrzuca propozycje, których cytatu nie ma w
tekście jednostki albo których pytanie/odpowiedź zawiera liczbę spoza
jej tekstu i oznaczenia (`pytania.sprawdz_propozycje_fiszek`). Student
zaznacza i poprawia; zapis przez `fiszki/zewnetrzne.py` (D-074) z
kotwicą na stronie PDF-a, na której naprawdę jest cytat. Przy zapisie
cytaty sprawdzane ponownie; wszystkie przed zapisem pierwszej — nic „do
połowy”.

**Uzasadnienie:** Nauka przepisów artykuł po artykule; te same gwarancje
co przy fiszkach z cytatu odpowiedzi (D-068, D-074).

**Odrzucone alternatywy:**
- Prompt fiszek z podręcznika — pytania o „stronę”, bez wskazania
  artykułu i ustępu.

## D-090 — Teren: mapa offline w formularzu z jednym obrazem ortofotomapy
Data: 2026-09-30

**Decyzja:** Projekt terenowy ma opcjonalny obszar prac (ustawiany z
widoku mapy, 50 m – 3 km boku; kolumna `projekty.obszar`, dopisywana do
starych baz). Przy pobieraniu formularza Warsztat pobiera JEDEN obraz
aktualnej ortofotomapy GUGiK tego obszaru (WMS GetMap, EPSG:3857, do
1600 px, `dane/ortofoto.obraz_ortofotomapy`) i osadza go w pliku HTML.
Telefon rysuje na płótnie (Web Mercator — ten sam układ co obraz):
podkład, zapisane punkty z numerami, pozycję GPS z kołem dokładności,
podziałkę; ostrzega, gdy jesteś poza obszarem. Bez obszaru albo przy
błędzie usługi — mapa bez zdjęcia (punkty i pozycja). Przy okazji
naprawiono formularz: po zapisie punktu śledzenie GPS się kończy, a koniec
czasu przy już ustalonym położeniu nie jest błędem (wcześniej po ok. 30 s
pojawiał się mylący komunikat „Nie udało się ustalić położenia”).

**Uzasadnienie:** W terenie trzeba widzieć, gdzie się jest i co już
zinwentaryzowano. Ortofotomapa GUGiK jest udostępniana bezpłatnie
(otwarte dane); jeden obraz obszaru to zwykłe użycie usługi WMS.

**Odrzucone alternatywy:**
- Kafelki OSM do pracy offline — zasady korzystania z serwerów kafelków
  OSM zabraniają pobierania hurtowego.
- Wiele poziomów przybliżenia (piramida kafelków) — wiele zapytań i duży
  plik; jeden obraz 1600 px wystarcza na obszar do 3 km.

## D-091 — Atlas: wskaźnik złożony z zestawu wskaźników raportu
Data: 2026-09-30

**Decyzja:** Wskaźnik złożony (syntetyczny) liczony z wybranych wskaźników
zestawu raportu gminy (tabela `raport_wskazniki`, bez osobnej listy).
Każda składowa ma kierunek (stymulanta +1, destymulanta −1) i wagę > 0.
Metody: unitaryzacja zerowana (domyślna, wynik 0–1) albo standaryzacja
(odchylenie standardowe populacyjne — gminy województwa to cała
populacja). Wynik = średnia ważona składowych, tylko dla gmin z danymi
wszystkich składowych (pozostałe wypisane jako pominięte). Składowa stała
we wszystkich gminach to błąd z komunikatem, nie dzielenie przez zero.
Parametry w adresie (`s=id:kierunek:waga,…`), więc wynik, kartogram i CSV
dają się otworzyć tym samym linkiem. Kartogram: klasy kwantylowe, te same
kolory co mapa do druku.

**Uzasadnienie:** Klasyczne narzędzie diagnozy (np. poziom rozwoju
społeczno-gospodarczego gmin) z zajęć z analizy regionalnej. Wszystkie
liczby liczy Python z danych GUS — nie model językowy.

**Odrzucone alternatywy:**
- Metoda Hellwiga (wzorzec rozwoju) — trudniejsza do wyjaśnienia; może
  być kolejnym krokiem, gdy będzie potrzebna.
- Dobór wag automatycznie (np. z korelacji) — wagi to decyzja badacza,
  powinny być jawne.

## D-092 — Dostępność: zasięg z punktu jako okręgi szybkiego modelu
Data: 2026-09-30

**Decyzja:** „Izochrony” z klikniętego punktu liczymy szybkim modelem
(D-052: linia prosta × krętość / prędkość), więc są okręgami o promieniu
t × prędkość / krętość dla 5, 10 i 15 minut. W zasięgu są komórki siatki
pliku, których środek leży w okręgu (jak w szybkim modelu). Przy kolumnie
czasu dojścia podajemy też, ilu z mieszkańców w zasięgu ma dziś do usługi
dalej niż dany próg. Prędkość i krętość z pól szybkiego modelu.

**Uzasadnienie:** Uzupełnia „gdzie nowa placówka” (D-085) o sprawdzenie
miejsca wskazanego przez użytkownika („a gdyby tu?”), bez nowych danych
i zależności. Okrąg uczciwie pokazuje, czym jest model.

**Odrzucone alternatywy:**
- Izochrony po sieci ulic (OSRM, OSM) — wymagałyby pobierania sieci albo
  zewnętrznej usługi; moduł z zasady czyta gotowe wyniki analiz
  sieciowych, a szybki model ma być natychmiastowy.
- Progi ustawiane suwakiem — 5/10/15 min to standard „miasta
  15-minutowego”; suwak progu jest już w krzywej dostępności.

## D-093 — Kalendarz na stronie głównej z terminów modułów
Data: 2026-09-30

**Decyzja:** Fiszki i Teren mają po jednej funkcji `terminy()` (w swoich
`routes.py`), zwracającej nadchodzące terminy jako słowniki
{data, dni, rodzaj, nazwa, opis, url}. Strona główna je łączy, sortuje od
najbliższego i pokazuje 6 pierwszych; błąd jednego modułu nie blokuje
strony (tak samo jak podsumowania modułów na stronie głównej). Teren dostał kolumnę `projekty.termin`
(dopisywaną do starych baz). Minione terminy nie są pokazywane.

**Uzasadnienie:** Egzaminy i wyjścia w teren to dwa rodzaje terminów,
które student planuje równolegle; strona główna to pierwsze, co widzi.

**Odrzucone alternatywy:**
- Wspólna tabela terminów / moduł „kalendarz” — dwa źródła nie
  uzasadniają nowej abstrakcji (CLAUDE.md), każdy moduł zostaje właścicielem
  swoich danych.
- Eksport do kalendarza Google (ICS) — nie było prośby; można dodać później.

## D-094 — Pomoc jako jedna statyczna strona
Data: 2026-09-30

**Decyzja:** `/pomoc`: jeden szablon z przepisami „jak zrobić…” w
rozwijanych sekcjach (details) — na start i dla każdego modułu, z
linkami do stron. Opisy odwołują się do etykiet przycisków z kodu; test
sprawdza, że wszystkie linki ze strony pomocy działają.

**Uzasadnienie:** Autor wraca do projektu po przerwie — pomoc ma
przypomnieć, gdzie co jest, bez czytania README.

**Odrzucone alternatywy:**
- Podpowiedzi na każdej stronie modułu — opisy już tam są; brakowało
  jednego miejsca z przeglądem.
- Pomoc generowana przez Gemini — treść ma być stała i sprawdzona.

## D-095 — Portfolio: opis w repo, zrzuty tylko z prawdziwych danych
Data: 2026-09-30

**Decyzja:** Opis projektu do portfolio jest w `docs/PORTFOLIO.md` (po
polsku — pierwsi odbiorcy to polskie biura planistyczne i urzędy — ze
streszczeniem po angielsku). Zrzuty ekranu robi autor na prawdziwych
danych i zapisuje w `docs/portfolio/`; opis zawiera listę 10 zrzutów z
instrukcją. Sekcja „Jak powstał” mówi wprost o pracy z asystentem AI.

**Uzasadnienie:** Portfolio ma pokazać umiejętności z gospodarki
przestrzennej. Zrzuty z testów mają zmyślone liczby (np. gmina z ponad
milionem mieszkańców) i byłyby mylące. Uczciwy opis roli AI jest
bezpieczniejszy niż pytanie bez przygotowanej odpowiedzi na rozmowie.

**Odrzucone alternatywy:**
- Zrzuty z danych testowych — mylące.
- Osobna strona internetowa portfolio — wymaga hostingu; na razie
  wystarczy plik w repo i PDF-y z raportów.

## D-096 — Przepisy: teksty aktów z API Sejmu (ELI)
Data: 2026-09-30

**Decyzja:** Wyszukiwanie aktów po słowach tytułu w Dzienniku Ustaw przez
oficjalne API Kancelarii Sejmu (`api.sejm.gov.pl/eli`: `/acts/search`,
`/acts/DU/{rok}/{poz}/text.pdf`) i pobranie urzędowego PDF-a do modułu
tą samą ścieżką co wgrany plik (podział na jednostki, FTS). Wyniki od
najnowszych; pozycje „… jednolitego tekstu …” oznaczone. Nazwa aktu =
tytuł z API + adres Dz.U. Bez filtrowania „tylko obowiązujące” — nie
potwierdziłem formatu parametru, pokazujemy za to status aktu.

**Uzasadnienie:** Aktualny tekst jednolity to podstawa pracy z
przepisami, a ręczne szukanie PDF-a w ISAP to kilka kroków. API jest
publiczne, bez klucza — zgodne z zasadą „wyłącznie API i usługi”.

**Odrzucone alternatywy:**
- Tekst HTML aktu (`text.html`) — dla nowszych aktów API daje tylko PDF,
  a moduł i kotwice w PDF-ie już działają na PDF-ach.
- Pobieranie ze strony ISAP — to byłoby scrapowanie strony, a jest API.
- Automatyczne szukanie najnowszego tekstu jednolitego (powiązania
  aktów) — format powiązań w API nie jest jednoznacznie opisany; wybór
  zostawiamy użytkownikowi.

## D-097 — MPZP: plany ogólne gmin z usługi GUGiK, wszystko z GetCapabilities
Data: 2026-09-30

**Decyzja:** Plany ogólne gmin z usługi WMS GUGiK
(`mapy.geoportal.gov.pl/wss/ext/PlanyOgolneGmin`). Nowy plik
`mpzp/uslugi.py` obsługuje „inne usługi GUGiK” w module MPZP: nazwy
warstw, obsługę EPSG:3857 i formaty GetFeatureInfo czyta z
GetCapabilities (pamięć na dobę), a atrybuty w punkcie odczytuje z GML
(parsery z `krajowe.py`), tekstu albo tabel HTML. Bez odpowiedzi usługi
nakładki po prostu nie ma. Sekcja w panelu działki ładuje się dopiero po
rozwinięciu.

**Uzasadnienie:** Plan ogólny to nowy dokument planistyczny gminy, który
wyznacza strefy dla przyszłych planów miejscowych. Adres usługi jest
podany przez GUGiK, ale nazw warstw i formatów nie znam z pewności —
dlatego nie są wpisane w kod (NIE ZGADUJ).

**Odrzucone alternatywy:**
- Rozszerzenie `krajowe.py` — to moduł jednej usługi (KIMPZP) z własnymi
  regułami (rozpoznawanie symbolu przeznaczenia); nowy plik korzysta z
  jego parserów zamiast go przebudowywać.
- Opis symboli stref (SW, SJ…) w aplikacji — pokazujemy atrybuty z
  usługi, bez własnej interpretacji.

## D-098 — MPZP: Rejestr Cen Nieruchomości przez WMS, bez własnych analiz cen
Data: 2026-09-30

**Decyzja:** Usługa RCN GUGiK (`mapy.geoportal.gov.pl/wss/service/rcn`)
obsługiwana tak samo jak plan ogólny (D-097): nakładka z warstwami z
GetCapabilities i atrybuty transakcji w punkcie działki, pokazane tak, jak
podała je usługa. Transakcje w okolicy — na mapie (warstwa), bez
zestawień.

**Uzasadnienie:** Od 2026 r. dane RCN są bezpłatne. Ceny transakcyjne są
potrzebne przy ocenie działki i w analizach rynku, a nakładka z
atrybutami nie wymaga znajomości schematu danych.

**Odrzucone alternatywy:**
- Zestawienie cen w promieniu (średnia cena za m²) przez WFS — wymaga
  schematu obiektów RCN, którego nie potwierdziłem; może być następnym
  krokiem po sprawdzeniu usługi na żywo.
- Pobieranie paczek GeoPackage/GeoParquet z RCN — duże pliki, a
  potrzebny jest podgląd dla jednej działki.

## D-099 — Atlas: metoda Hellwiga z wagami, odchylenie populacyjne
Data: 2026-09-30

**Decyzja:** Trzecia metoda wskaźnika złożonego: taksonomiczna miara
rozwoju Hellwiga. Standaryzacja z kierunkiem (destymulanty ze znakiem
minus), wzorzec = maksimum każdej składowej, odległość euklidesowa ważona
(wagi przeskalowane do sumy równej liczbie składowych, więc równe wagi
dają wersję klasyczną), d0 = średnia + 2 odchylenia standardowe
(populacyjne, jak w standaryzacji — D-091), m = 1 − d/d0.

**Uzasadnienie:** Hellwig to najczęściej uczona metoda porządkowania
liniowego w analizie regionalnej; była odrzuconą alternatywą w D-091
„na później”. Liczy kod, bez modelu językowego.

**Odrzucone alternatywy:**
- Wzorzec z maksimum wartości surowych bez standaryzacji — składowe
  w różnych jednostkach nie dałyby się porównać.
- Odchylenie z próby (n − 1) — gminy województwa to cała populacja.

## D-100 — Atlas: ekstrapolacja trendu liniowego, nie „prognoza ludności”
Data: 2026-09-30

**Decyzja:** Dla każdego wskaźnika raportu gminy kod liczy trend liniowy
(metoda najmniejszych kwadratów) z ostatnich 10 lat (min. 5 lat danych) i
wartość za 5 lat, z R². Wynik jest nazwany wprost: ekstrapolacja „jeśli
dotychczasowa zmiana się utrzyma”, zaokrąglona do 3 cyfr znaczących,
z dopiskiem „trend niestabilny” przy R² < 0,7. Nie trafia do faktów dla
modelu językowego.

**Uzasadnienie:** Proste przedłużenie trendu przydaje się w diagnozie
gminy, ale nie jest prognozą demograficzną. Prawdziwą prognozę ludności
dla powiatów publikuje GUS (metoda kohortowa: urodzenia, zgony,
migracje). Uczciwa nazwa i R² chronią przed nadinterpretacją.

**Odrzucone alternatywy:**
- Własna prognoza kohortowa — wymaga struktury wieku, płodności i
  umieralności; to materiał na osobny, duży etap.
- Trend wykładniczy — przy krótkich szeregach gminnych zawyża skrajne
  wartości; liniowy jest prostszy do wyjaśnienia.
- Przekazanie ekstrapolacji do opisu Gemini — model mógłby ją przedstawić
  jak pewną prognozę.

## D-101 — Teren: ankieta jako rodzaj projektu, nie osobny moduł
Data: 2026-09-30

**Decyzja:** Ankieta korzysta z całej ścieżki modułu teren (formularz HTML
offline → plik JSON → import → raport). Projekt ma rodzaj
„inwentaryzacja” albo „ankieta” (kolumna dopisywana do starych baz),
który zmienia tylko wygląd formularza i raportu. Doszedł typ pola „wiele”
(lista zaznaczonych opcji, zapisywana w kolejności opcji); w zestawieniu
procent liczony od wszystkich odpowiedzi, więc suma może przekroczyć 100%
— raport o tym mówi.

**Uzasadnienie:** Ankiety z użytkownikami przestrzeni to typowe zadanie
na zajęciach z planowania; formularz offline i import już działały.

**Odrzucone alternatywy:**
- Osobny moduł ankiet — powielałby formularz, import i raport.
- Formularze Google — wymagają internetu i konta, a dane trafiają poza
  komputer autora.
- Kolumny 0/1 dla każdej opcji wielokrotnego wyboru w bazie — lista w JSON
  wartości punktu pasuje do obecnego zapisu wartości.

## D-102 — Osiedle: cień jako najgorszy przypadek dla terenów, nie budynków
Data: 2026-09-30

**Decyzja:** Koncepcja ma tereny, nie budynki, więc liczymy najgorszy
przypadek: budynki przy krawędzi terenu, wysokość = kondygnacje × 3 m.
Położenie słońca ze wzorów astronomicznych (deklinacja 0° / ±23,44°,
kąt godzinny, czas słoneczny 9–15). Strefa cienia to suma Minkowskiego
terenu z wektorem cienia w każdej godzinie (bez samego terenu); pokazujemy
powierzchnię terenów MN, MW i ZP w strefie. Odległość od granicy obszaru
= najmniejsza odległość terenu zabudowy od brzegu obszaru. Przepisy (§ 12,
§ 13, § 60 warunków technicznych) tylko wskazujemy, bez podawania ich
wartości w kodzie.

**Uzasadnienie:** Na etapie koncepcji trzeba zobaczyć, czy wysoka
zabudowa od południa nie zasłania domów i zieleni, i czy tereny nie
dochodzą do granicy działek. Dokładna analiza nasłonecznienia wymaga
projektu budynków — tu jej nie udajemy.

**Odrzucone alternatywy:**
- Rysowanie pojedynczych budynków — duża zmiana modułu; tereny z
  parametrami to obecny poziom szczegółu koncepcji.
- Czas strefowy zamiast słonecznego — wymaga długości geograficznej i
  równania czasu; czas słoneczny jest prostszy i wystarcza do porównania.
- Wartości z warunków technicznych w kodzie (np. odległości) — łatwo o
  nieaktualny przepis; odsyłamy do paragrafów.

## D-103 — Fiszki: tagi Anki z tematów
Data: 2026-09-30

**Decyzja:** Plik dla Anki dostaje czwartą kolumnę z tematami fiszki jako
tagami i nagłówek `#tags column:4` (podręcznik Anki, import plików
tekstowych, Anki 2.1.54+). Spacje w nazwie tematu zamieniamy na „_”, bo w
Anki rozdzielają tagi. Eksport można zawęzić do jednego tematu, tak jak
druk.

**Uzasadnienie:** Eksport do Anki istniał od wczesnych etapów, ale gubił
podział na tematy, który w Warsztacie porządkuje naukę do egzaminów.

**Odrzucone alternatywy:**
- Paczka .apkg — wymaga zależności albo ręcznego budowania bazy SQLite
  Anki; plik tekstowy jest oficjalnie obsługiwany i czytelny.
- Nagłówek `#deck:` — talia musi już istnieć w Anki; lepiej, żeby
  użytkownik wybrał ją przy imporcie.

## D-104 — Wydajność: mierzyć, poprawiać tylko przy tym samym wyniku
Data: 2026-09-30

**Decyzja:** Po serii etapów mierzymy czasy na danych na granicy limitów
(20 tys. komórek H3, 3000 artykułów, 3000 punktów, 150 terenów).
Optymalizujemy tylko to, co wyraźnie odstaje („Gdzie nowa placówka”), i
tylko zmianami, które dają identyczny wynik — sprawdzonymi porównaniem ze
starą wersją na wielu zestawach danych.

**Uzasadnienie:** Aplikacja działa na laptopie jednej osoby; czasy rzędu
sekundy przy maksymalnych danych są akceptowalne, a poprawność wyniku
jest ważniejsza niż szybkość.

**Odrzucone alternatywy:**
- Odległość płaska zamiast po kuli — szybsza, ale zmieniałaby wynik na
  krawędzi zasięgu.
- Wektoryzacja w numpy — możliwa (numpy przychodzi z shapely), ale
  przepisałaby czytelny algorytm; do rozważenia, gdy pliki z wynikami
  będą regularnie tak duże.

## D-105 — Kopia automatyczna przy starcie, w tle, z rotacją
Data: 2026-09-30

**Decyzja:** Przy uruchomieniu (`python app.py`, czyli z ikony) Warsztat
w osobnym wątku sprawdza, czy od ostatniej kopii automatycznej minęło
`AUTO_KOPIA_DNI` dni (domyślnie 7, 0 = wyłączone), i jeśli tak — zapisuje
ten sam ZIP co przycisk na stronie głównej (`kopia.utworz_kopie`, bazy
przez `sqlite3.backup`) do `AUTO_KOPIA_FOLDER` (domyślnie
`~/warsztat_kopie`, obok kopii sprzed aktualizacji). Zostaje 5 najnowszych
kopii `warsztat_auto_*.zip`. Zapis przez plik tymczasowy, potem zmiana
nazwy.

**Uzasadnienie:** Kopia „od czasu do czasu” z przycisku łatwo wypada z
głowy, a dane (fiszki, zdjęcia z terenu, koncepcje) są tylko na jednym
komputerze.

**Odrzucone alternatywy:**
- Harmonogram systemowy (cron) — wymaga konfiguracji poza aplikacją.
- Kopia do chmury — wymagałaby konta i klucza; decyzja o miejscu kopii
  należy do autora (Pomoc podpowiada pendrive albo chmurę).
- Kopia przy każdym starcie — przy dużych PDF-ach i zdjęciach
  niepotrzebnie zapełniałaby dysk.

## D-106 — Pomoc aktualizowana razem z funkcjami, pilnowana testem
Data: 2026-09-30

**Decyzja:** Po serii ETAPów 88–97 Pomoc nie wspominała żadnej nowej
funkcji. Uzupełniamy ją i dodajemy test sprawdzający, że wymienia kluczowe
etykiety z interfejsu. Kolejne ETAPy z nową funkcją dopisują akapit w
Pomocy w tym samym ETAPie.

**Uzasadnienie:** Pomoc powstała po to, żeby autor po przerwie wiedział,
gdzie co jest (D-094); nieaktualna jest gorsza niż żadna.

**Odrzucone alternatywy:**
- Generowanie Pomocy z opisów w kodzie — więcej mechaniki niż treści;
  jedna strona HTML jest prostsza w utrzymaniu.

## D-107 — Teren: wykresy jako paski CSS w tabeli zestawienia
Data: 2026-09-30

**Decyzja:** Rozkład odpowiedzi pokazujemy paskiem w dodatkowej kolumnie
tabeli (szerokość = procent), kolorem skali dla pól „skala” (ten sam wzór
co kolory punktów, ETAP 70). Druk z zachowaniem kolorów
(`print-color-adjust: exact`).

**Uzasadnienie:** Wyniki ankiety czyta się z wykresu szybciej niż z
liczb, a tabela zostaje obok — liczby zawsze widać.

**Odrzucone alternatywy:**
- Osobne wykresy SVG — więcej kodu dla tego samego efektu przy
  wykresach słupkowych jednej zmiennej.
- Biblioteka wykresów — nowa zależność i CDN (sprzeczne z zasadami).

## D-108 — Osiedle: analiza cienia w raporcie domyślnie włączona
Data: 2026-09-30

**Decyzja:** Raport do druku pokazuje odległości i strefę cienia dla
równonocy, jeśli koncepcja ma tereny zabudowy; dzień można zmienić
(parametr `?cien=`), a analizę wyłączyć (`?cien=nie`). Numery terenów na
szkicu odpowiadają tabelom (kolejność zapisu rysunku, bez obszaru).
Szkic w porównaniu wariantów zostaje bez tych dodatków.

**Uzasadnienie:** Raport idzie do prowadzącego jako całość koncepcji —
cień i odległości od granicy są jej częścią. Równonoc to umowny dzień
porównawczy (zimą cienie są wielokrotnie dłuższe).

**Odrzucone alternatywy:**
- Osobny raport cienia — dwa wydruki tej samej koncepcji.
- Cień na szkicach porównania wariantów — przy małych szkicach numery i
  strefa zasłaniałyby rysunek.

## D-109 — Przepisy: aktualność tekstu po przedmiocie ustawy z nazwy aktu
Data: 2026-09-30

**Decyzja:** Aktualność sprawdzamy tylko dla aktów pobranych z Dziennika
Ustaw (ETAP 88): z nazwy aktu bierzemy adres (rok, pozycja) i przedmiot
ustawy, szukamy w API Sejmu po przedmiocie i zostawiamy obwieszczenia
„… jednolitego tekstu …” zawierające ten sam przedmiot, nowsze niż akt.
Wynik pokazujemy; pobranie nowszego tekstu jest decyzją użytkownika.

**Uzasadnienie:** Teksty jednolite ustaw planistycznych zmieniają się
często; praca na starym tekście to częsty błąd.

**Odrzucone alternatywy:**
- Powiązania aktów z API (np. „tekst jednolity dla aktu”) — ich format
  nie jest jednoznacznie opisany (D-096); tytuły są pewniejsze.
- Automatyczne sprawdzanie przy każdym otwarciu aktu — niepotrzebne
  zapytania do API; wystarczy przycisk.

## D-110 — Kalendarz: plik .ics zamiast integracji z Kalendarzem Google
Data: 2026-09-30

**Decyzja:** Terminy eksportujemy do pliku iCalendar (RFC 5545), który
użytkownik importuje sam. Wydarzenia całodniowe; UID liczony z rodzaju,
daty i nazwy, więc ponowny import aktualizuje te same wydarzenia. Plik
powstaje w bibliotece standardowej (bez nowej zależności).

**Uzasadnienie:** Terminy nauki i terenu chcemy mieć w telefonie, ale
Warsztat działa tylko lokalnie i nie powinien trzymać kont ani tokenów.

**Odrzucone alternatywy:**
- API Kalendarza Google — logowanie OAuth i klucze w aplikacji lokalnej;
  sprzeczne z zasadą prostoty i „zero sekretów”.
- Subskrypcja kalendarza (adres URL) — telefon nie połączy się z
  127.0.0.1.
- Biblioteka `icalendar` — nowa zależność dla kilkudziesięciu linii
  formatu tekstowego.

## D-111 — Ceny: osobny moduł, pierwszy etap na danych GUS dla powiatów
Data: 2026-09-30

**Decyzja:** Ósmy moduł „Ceny” (decyzja autora: osobny moduł, nie część
Atlasu). Pierwszy etap korzysta z GUS BDL na poziomie powiatu (miasta na
prawach powiatu to powiaty). Wskaźnik ceny wybiera użytkownik z
wyszukiwarki zmiennych BDL dla powiatów i jest zapamiętywany w bazie
modułu — bez numerów zmiennych w kodzie (jak zestaw raportu gminy,
D-069). Miasta na prawach powiatu rozpoznajemy po numerze powiatu TERYT
(≥ 61). Obliczenia w `ceny/analiza.py`, bez modelu językowego.

**Uzasadnienie:** Autor chce sprawdzać ceny w miastach. Dane GUS są
oficjalne, bezpłatne i dostępne przez API, którego klient już jest w
projekcie; transakcje z Rejestru Cen Nieruchomości to kolejny etap
(szczegóły w dzielnicach, mapa).

**Odrzucone alternatywy:**
- Rozszerzenie Atlasu — Atlas pracuje na gminach, a moduł cen dostanie
  dane punktowe RCN z mapą; autor wybrał osobny moduł.
- Ceny z portali ogłoszeniowych — to ceny ofertowe, a pobieranie ich
  byłoby scrapowaniem stron bez zgody.
- Dane NBP o cenach w 17 miastach — pliki arkuszy wymagałyby nowej
  zależności; GUS obejmuje wszystkie powiaty.

## D-112 — Ceny: RCN z pliku GeoPackage czytanego przez sqlite3
Data: 2026-09-30

**Decyzja:** Transakcje lokali czytamy z pliku GeoPackage powiatu,
pobranego przez użytkownika z Geoportalu, bezpośrednio przez `sqlite3` i
`shapely.wkb` (bez GDAL). Plik wskazuje się z katalogu Pobrane (tylko z
listy pokazanej przez Warsztat) albo wgrywa, jeśli jest mały. Cena lokalu
wg hierarchii cena lokalu → nieruchomości → transakcji (ostatnia tylko
przy jednym lokalu w transakcji); odrzucamy lokale niemieszkalne, udziały
i wartości nierealne, z licznikami powodów. Zaimportowane lokale trzymamy
w bazie modułu, więc filtry działają bez ponownego czytania pliku.

**Uzasadnienie:** RCN to ceny z aktów notarialnych dla pojedynczych
lokali — dokładniejsze w skali miasta niż mediana GUS dla powiatu. Pliki
są bezpłatne od 2026 r.; usługa WFS nie byłaby wygodna do pobrania całego
powiatu z ogranicznikami liczby obiektów.

**Odrzucone alternatywy:**
- GDAL/pyogrio/geopandas — ciężkie zależności dla odczytu jednej tabeli.
- Pobieranie przez WFS w aplikacji — schemat odpowiedzi niepotwierdzony
  (D-098), a limity obiektów na zapytanie wymagałyby stronicowania.
- Wgrywanie tylko przez przeglądarkę — pliki dużych miast przekraczają
  limit 50 MB; wskazanie z Pobranych jest bezpieczne (tylko pliki z
  listy).

## D-113 — Ceny: obszary porównania rysowane przez użytkownika, liczone na serwerze
Data: 2026-09-30

**Decyzja:** Dzielnice do porównania użytkownik rysuje sam na mapie
transakcji (Leaflet.draw, jak w module osiedle); obszary zapisujemy w
bazie modułu przy pliku RCN (`rcn_obszary`, najwyżej 8). Przynależność
transakcji do obszaru i wszystkie statystyki liczy serwer (shapely,
`prep` + `contains`), z tymi samymi filtrami co reszta strony. Raport do
druku to strona HTML z mapą schematyczną SVG generowaną w Pythonie (bez
podkładu kafelkowego), drukowana przez przeglądarkę.

**Uzasadnienie:** Granice dzielnic nie są dostępne jednolicie dla całej
Polski przez usługę, na którą mamy zgodę — a student często porównuje
własne obszary (osiedle, okolica stacji), nie urzędowe dzielnice. SVG
z Pythona drukuje się zawsze tak samo i nie zależy od sieci.

**Odrzucone alternatywy:**
- Granice dzielnic z PRG/WFS — tylko jednostki administracyjne (gminy),
  dzielnice miast nie są tam jednolicie; do dodania później, gdy będzie
  potwierdzona usługa.
- Liczenie w przeglądarce — dwa miejsca z tą samą statystyką (raport i
  strona) rozjechałyby się.
- Zrzut mapy Leaflet do PDF — kafelki OSM w druku zależą od sieci i
  licencji wydruku; schemat SVG wystarcza do porównania.

## D-114 — Ceny działek: powierzchnia z obrysu, działki sprzedane razem jako jedna transakcja
Data: 2026-09-30

**Decyzja:** Transakcje działek czytamy z tabeli `transakcje_dzialki` tego
samego pliku GeoPackage i trzymamy w osobnej tabeli `rcn_dzialki`, na tej
samej stronie co mieszkania (przełącznik, wspólne obszary i raport).
Powierzchnia działki = pole jej obrysu w pliku (PL-1992, metry). Cena:
`dzi_cena_brutto`; gdy działki transakcji nie mają własnych cen — cena
nieruchomości (jedna działka) albo transakcji, podzielona przez łączną
powierzchnię tych działek. Gdy część działek transakcji ma własną cenę,
a część nie, tych bez ceny nie liczymy.

**Uzasadnienie:** Dwa otwarte projekty czytające te pliki różnią się co do
jednostki `dzi_pow_ewid` (jeden zakłada hektary, drugi wykrył pliki
mieszane) — geometria w metrach nie wymaga zgadywania. Dzielenie ceny
transakcji wielu działek przez powierzchnię jednej zawyżałoby cenę m².

**Odrzucone alternatywy:**
- `dzi_pow_ewid` w hektarach albo m² z heurystyką — zgadywanie jednostki.
- Osobna strona dla działek — powieliłaby mapę, wykresy, obszary i raport.
- Stały filtr „tylko niezabudowane” — wartości słownika `nier_rodzaj` nie
  są potwierdzone na prawdziwym pliku; filtr z listy wartości w pliku.

## D-115 — Wycena porównawcza: mediana podobnych transakcji, bez korekt
Data: 2026-09-30

**Decyzja:** „Podobne transakcje” to transakcje z zaimportowanego pliku RCN
w wybranym promieniu od klikniętego miejsca, o powierzchni w zadanej
tolerancji, przy filtrach strony. Wynik: liczba, mediana ceny za m² z
kwartylami i cena orientacyjna = mediana × powierzchnia. Bez korekt na
cechy (stan, piętro, data) i bez modelu — opisane wprost na stronie jako
orientacja z danych, nie operat szacunkowy. Poniżej 5 transakcji
ostrzeżenie. Odległość liczona przybliżeniem równoodległościowym.

**Uzasadnienie:** Liczby mają pochodzić z danych, a korekty w podejściu
porównawczym wymagają wiedzy rzeczoznawcy i cech, których RCN często nie
ma. Mediana z przedziałem uczciwie pokazuje rozrzut cen.

**Odrzucone alternatywy:**
- Regresja (hedoniczna) ceny — liczby z modelu, trudne do sprawdzenia i
  wytłumaczenia na pierwszym roku; może później jako osobny ETAP.
- Korekta o trend cen w czasie — przy kilkunastu transakcjach niestabilna.
- Wzór haversine — w promieniu do 5 km różnica pomijalna, prostszy kod.

## D-116 — Ceny: kartogram w heksagonach H3 liczony na serwerze, z minimum transakcji
Data: 2026-09-30

**Decyzja:** Widok „heksagony” liczy serwer: transakcje z położeniem
przypisujemy do komórek H3 (`h3.latlng_to_cell`, rozdzielczość 7/8/9),
w komórce mediana ceny za m²; komórki z mniej niż 3/5/10 transakcjami
(wybór użytkownika, domyślnie 5) nie są pokazywane, a legenda podaje ich
liczbę. Kolory — kwintyle median komórek, te same barwy co punkty.
Opis wielkości heksagonu z `h3.average_hexagon_edge_length`.

**Uzasadnienie:** Heksagony pokazują przestrzenny wzór cen czytelniej niż
tysiące nakładających się punktów, a stała siatka pozwala porównywać
miejsca. Minimum transakcji chroni przed kolorowaniem obszaru jedną
nietypową transakcją. H3 jest już w projekcie (moduł dostępność, D-015).

**Odrzucone alternatywy:**
- Mapa ciepła (gęstość) — pokazuje, gdzie jest dużo transakcji, a nie
  jakie są ceny; wymagałaby też wtyczki Leaflet.
- Siatka kwadratów w PL-1992 — własny kod siatki, gdy H3 już jest.
- Średnia zamiast mediany — wrażliwa na pojedyncze skrajne ceny.

## D-117 — Ceny w okolicy: MPZP i osiedle pytają moduł ceny przez jedną trasę
Data: 2026-09-30

**Decyzja:** MPZP i osiedle nie czytają bazy modułu ceny — wysyłają
geometrię (działka albo obszar opracowania) i promień do POST
`/ceny/okolica`, a moduł ceny wybiera zaimportowany plik RCN z największą
liczbą transakcji w zasięgu i zwraca podsumowanie mieszkań i działek.
Każdy z dwóch modułów ma własny, krótki kod tabeli (bez wspólnego
komponentu JS). Odległość od kształtu liczona w lokalnym układzie
metrycznym (przybliżenie równoodległościowe).

**Uzasadnienie:** Moduły zostają niezależne (osobne bazy, D-004), a
statystyka jest w jednym miejscu. Wybór jednego pliku zamiast łączenia
chroni przed podwójnym liczeniem, gdy ktoś zaimportował ten sam powiat
dwa razy. Wspólny komponent JS dla dwóch modułów to abstrakcja, której
CLAUDE.md każe unikać.

**Odrzucone alternatywy:**
- Łączenie transakcji ze wszystkich plików — duplikaty przy ponownym
  imporcie tego samego pliku.
- Import `ceny.baza` w mpzp i osiedlu — zależność między bazami modułów.
- Usługa WMS RCN (ETAP 90) zamiast pliku — daje atrybuty w punkcie, nie
  statystykę okolicy.

## D-118 — Trend w obszarach: mediany roczne, niepewne lata oznaczone, bez wygładzania
Data: 2026-10-01

**Decyzja:** Trend obszaru to mediany ceny za m² w kolejnych latach (te
same, co w tabeli raportu), bez wygładzania i bez linii trendu. Rok, w
którym obszar ma mniej niż 5 transakcji (`MIN_W_ROKU`), ma pusty punkt.
Wykres na stronie (JS) i w raporcie (SVG z Pythona) rysują te same dane z
serwera; próg przychodzi z serwera.

**Uzasadnienie:** Mała dzielnica ma czasem kilka transakcji w roku — ich
mediana skacze. Pokazanie tego wprost jest uczciwsze niż wygładzanie,
które ukryłoby niepewność.

**Odrzucone alternatywy:**
- Kwartały zamiast lat — w małych obszarach najczęściej 0–3 transakcje.
- Średnia krocząca — wygląda pewniej, niż wynika z danych.
- Ukrywanie lat z małą liczbą transakcji — przerwy w linii mylą bardziej.

## D-119 — Zmiana cen: różnica median w heksagonach, stałe klasy, minimum w obu okresach
Data: 2026-10-01

**Decyzja:** Zmiana w heksagonie = mediana ceny za m² w okresie B /
mediana w okresie A − 1. Pokazujemy tylko komórki z minimum transakcji w
obu okresach. Klasy kolorów są stałe i symetryczne wokół zera (−10, −2,
+2, +10, +20%), a nie kwantylowe. Opis na mapie mówi wprost, że to nie
indeks cen (zmienia się też to, co sprzedano).

**Uzasadnienie:** Przy klasach kwantylowych „najciemniejszy” mógłby
oznaczać +3% albo +40% zależnie od miasta; przy stałych klasach student
może porównać mapy dwóch miast albo dwóch okresów. Indeks cen (np.
hedoniczny) wymagałby modelu i cech, których RCN często nie ma.

**Odrzucone alternatywy:**
- Klasy kwantylowe — nieporównywalne między mapami.
- Indeks powtórnych sprzedaży — w RCN trudno pewnie połączyć ten sam
  lokal w dwóch transakcjach.
- Uwzględnianie komórek z transakcjami tylko w jednym okresie — brak
  podstawy do zmiany.

## D-120 — Piętro lokalu: przedziały, „parter” rozpoznawany, inne zapisy jako brak danych
Data: 2026-10-01

**Decyzja:** `lok_nr_kond` czytamy jako liczbę całkowitą (także ujemną —
kondygnacje podziemne — do −5) albo słowo „parter” (= 0); inne zapisy
(np. „poddasze”) to brak danych, widoczny w tabeli jako osobny wiersz.
Do filtra i tabeli przedziały: parter i niżej, 1–3, 4–9, 10 i wyżej.

**Uzasadnienie:** Format wartości w prawdziwych plikach nie jest
potwierdzony — lepiej pokazać „brak danych” niż zgadywać piętro z tekstu.
Przedziały odpowiadają typowej zabudowie: niska, średnia, wysoka.

**Odrzucone alternatywy:**
- Pojedyncze piętra w tabeli — kilkanaście wierszy z małą liczbą transakcji.
- Liczby rzymskie i opisy słowne — brak potwierdzenia, że występują.

## D-121 — Karta wyceny: ta sama wycena co na stronie, schemat bez podkładu
Data: 2026-10-01

**Decyzja:** Karta wyceny powstaje z tych samych parametrów URL i tej
samej funkcji co wynik na stronie (`rcn.podobne`), więc liczby na
wydruku i na ekranie są identyczne. Schemat to SVG z Pythona bez
podkładu mapowego (jak raport, D-113), z numerami transakcji zgodnymi z
tabelą. Karta mówi wprost, że to nie operat szacunkowy, i opisuje metodę.

**Uzasadnienie:** Student może dołączyć kartę do pracy z wyceny albo
analizy rynku; musi być jasne, skąd liczby i czego nie uwzględniają.

**Odrzucone alternatywy:**
- Zrzut mapy Leaflet — zależny od sieci i kafelków OSM.
- Zapisywanie wycen w bazie — nikt o to nie prosił; adres karty wystarcza,
  żeby wrócić do tej samej wyceny.

## D-122 — Eksport do QGIS jako GeoJSON w WGS84, bez nowej zależności
Data: 2026-10-01

**Decyzja:** Transakcje, heksagony i obszary eksportujemy jako GeoJSON
(RFC 7946: WGS84, kolejność lon, lat) budowany zwykłym `json` — z
filtrami strony i tymi samymi atrybutami co CSV. Pierścienie heksagonów
zamknięte (pierwszy punkt = ostatni).

**Uzasadnienie:** QGIS czyta GeoJSON bez konfiguracji; student może
zrobić własny kartogram, połączyć ceny z innymi warstwami (np. MPZP) i
wydrukować mapę w układzie PL-1992 — przeliczenie zrobi QGIS.

**Odrzucone alternatywy:**
- GeoPackage / Shapefile — wymagałyby GDAL/Fiony (ciężka zależność).
- Eksport w PL-1992 — RFC 7946 przewiduje tylko WGS84; QGIS przelicza
  „w locie”.

## D-123 — Ceny w raportach: stały promień 500 m, sekcja tylko z danymi
Data: 2026-10-01

**Decyzja:** Na karcie działki i w raporcie koncepcji ceny w okolicy
liczymy w stałym promieniu 500 m (bez wyboru na wydruku). Sekcja pojawia
się tylko, gdy moduł ceny ma zaimportowany plik z transakcjami w
zasięgu; źródło podaje nazwę pliku i datę importu.

**Uzasadnienie:** Wydruk ma być powtarzalny — ten sam promień w każdym
raporcie ułatwia porównanie działek i wariantów. Pusta sekcja „brak
danych” w każdym wydruku byłaby szumem dla osób, które nie używają RCN.
Inny promień jest na stronie MPZP i w panelu osiedla (ETAP 109).

**Odrzucone alternatywy:**
- Wybór promienia w raporcie — parametr w adresie, który łatwo zgubić.
- Liczenie cen po stronie serwera raportu (import modułu ceny w mpzp i
  osiedlu) — zależność między bazami modułów (D-117).

## D-124 — Dostępność cenowa: dwa wskaźniki GUS wybierane przez użytkownika, prosty iloraz
Data: 2026-10-01

**Decyzja:** Dostępność cenowa = przeciętne miesięczne wynagrodzenie
brutto / cena 1 m² (m² za wynagrodzenie) i 50 × cena 1 m² / wynagrodzenie
(wynagrodzeń na mieszkanie 50 m²), tylko w latach, w których GUS ma oba
wskaźniki dla tego samego powiatu. Wskaźnik wynagrodzenia użytkownik
wybiera z wyszukiwarki GUS (jak wskaźnik ceny), bez numeru zmiennej w
kodzie (D-069).

**Uzasadnienie:** Iloraz jest przejrzysty i znany z raportów o
mieszkalnictwie; student może sam go sprawdzić. Numeru zmiennej BDL nie
mogę tu zweryfikować (API zablokowane) — wybór z wyszukiwarki usuwa
zgadywanie.

**Odrzucone alternatywy:**
- Wskaźnik z ratą kredytu — wymagałby stóp procentowych i założeń o
  kredycie (dane spoza GUS, liczby z założeń).
- Wynagrodzenie netto — GUS publikuje dla powiatów brutto; przeliczenie
  wymagałoby założeń podatkowych.

## D-125 — Wydajność RCN: mierzyć na dużym pliku, wektorowe sprawdzanie punktów
Data: 2026-10-01

**Decyzja:** Wydajność modułu ceny mierzymy na syntetycznym pliku
wielkości dużego miasta (100 tys. lokali, 20 tys. działek). Sprawdzanie,
czy transakcje leżą w obszarze, robimy jednym wywołaniem
`shapely.contains_xy` na listach współrzędnych. Mapa raportu rysuje te
same punkty co mapa strony (najwyżej 4000 najnowszych). Bez cache wyników
— dane zmieniają się tylko przy imporcie, a czasy są do przyjęcia.

**Uzasadnienie:** Testy na kilkunastu transakcjach nie pokazały, że
raport rysuje wszystkie punkty — wyszło dopiero przy 100 tys. (180 s).
Pomiar przed optymalizacją pokazał, co naprawdę jest wolne.

**Odrzucone alternatywy:**
- Cache odpowiedzi — złożoność (unieważnianie przy filtrach i obszarach)
  przy czasach ok. 1 s.
- SpatiaLite / indeks przestrzenny — nowa zależność; prostokąt w SQL i
  wektorowe `contains_xy` wystarczają.
- Jawny import numpy — `contains_xy` przyjmuje zwykłe listy.

## D-126 — Przegląd stron z tablicy tras, Playwright jako narzędzie autora
Data: 2026-10-01

**Decyzja:** Listę stron do przeglądu bierzemy z `app.url_map` (każda
trasa GET bez parametrów zwracająca HTML) plus kilka stron z parametrami
na danych testowych — nowa strona trafia do przeglądu sama. Skrypt jest w
repo (`narzedzia/`), ale Playwright nie jest zależnością aplikacji (nie
ma go w `requirements.txt`) — to narzędzie autora, opisane w nagłówku.

**Uzasadnienie:** Ręczna lista stron z ETAPu 96 nie miała stron dodanych
później (np. całego modułu ceny). Kod HTTP, błędy JS i przewijanie
poziome to najczęstsze błędy wychwycone w poprzednich ETAPach.

**Odrzucone alternatywy:**
- Playwright w `requirements.txt` — duża zależność (przeglądarka)
  niepotrzebna do działania aplikacji.
- Testy przeglądarkowe w pytest — wolne (ok. 2 min) przy każdym
  uruchomieniu testów.

## D-127 — Liczby w portfolio liczone z repozytorium przy każdej aktualizacji
Data: 2026-10-01

**Decyzja:** Liczby w portfolio (wiersze kodu, testy, decyzje, etapy)
podajemy z policzenia w repozytorium w chwili aktualizacji, z etapem w
nagłówku („stan: ETAP 119”); wiersze testów osobno od kodu aplikacji;
biblioteki zewnętrzne (Leaflet, pdf.js) nie są liczone.

**Uzasadnienie:** Portfolio czyta rekruter — liczby muszą dać się
sprawdzić i nie mogą być „na oko”.

**Odrzucone alternatywy:**
- Liczenie z testami razem — zawyża „kod aplikacji”.
- Brak liczb — trudniej pokazać skalę projektu.

## D-128 — Słowniczek: definicje rozpoznawane po formułach ustawowych, bez odmiany
Data: 2026-10-01

**Decyzja:** Definicje wyciągamy wyrażeniami regularnymi z typowych
formuł techniki prawodawczej: zdanie wprowadzające („Ilekroć w ustawie
jest mowa o:”, „Użyte w ustawie określenia oznaczają:”) i punkty „N)
pojęcie – definicja”; skróty z „zwany dalej „…””. Pojęcie zostaje w
formie z tekstu, definicja to dokładny tekst (podgląd 500 znaków) z
odnośnikiem do artykułu.

**Uzasadnienie:** Zasady techniki prawodawczej narzucają te formuły,
więc proste reguły wystarczą dla większości ustaw. Odmiana pojęć do
mianownika wymagałaby słownika fleksyjnego (nowa zależność), a błędna
odmiana zmieniłaby treść przepisu.

**Odrzucone alternatywy:**
- Model językowy do wyciągania definicji — liczby i treść mają
  pochodzić z tekstu; reguły są sprawdzalne.
- Słownik fleksyjny (np. Morfeusz) — ciężka zależność dla wygody.

## D-129 — Odesłania: tylko w obrębie aktu, inne akty po nazwie zostają tekstem
Data: 2026-10-01

**Decyzja:** Linkujemy odesłania „art. N …” i „§ N …” do jednostek tego
samego aktu. Odesłanie, po którym stoi nazwa innego aktu (ustawa z dnia
/ o / – Prawo …, rozporządzenie organu, kodeks, konstytucja, dyrektywa),
zostaje zwykłym tekstem. Samo „ustawy” bez dalszej nazwy traktujemy jak
odesłanie do tego aktu.

**Uzasadnienie:** Błędny link (do artykułu o tym samym numerze w złej
ustawie) jest gorszy niż brak linku — student mógłby przeczytać nie ten
przepis.

**Odrzucone alternatywy:**
- Linkowanie do innych aktów w bazie — wymagałoby pewnego rozpoznania
  aktu po nazwie; na razie bez.
- Linki także do ustępów („ust. 2”) — jednostką w bazie jest artykuł.

## D-130 — DXF R12 pisany ręcznie w `dane/dxf.py`, domyślnie PL-2000
Data: 2026-10-01

**Decyzja:** DXF zapisujemy sami w najprostszej wersji formatu (R12,
tekst: pary „kod grupy / wartość”) — warstwy, zamknięte polilinie,
teksty. Moduł jest w `dane/` obok innych warstw dostępu do formatów i
usług (bdl, uldk), bo używa go osiedle i (ETAP 123) MPZP: to zapis
formatu pliku, nie wspólna abstrakcja modułów, której CLAUDE.md zabrania.
Domyślny układ PL-2000 (jedna strefa wg środka rysunku), opcjonalnie
PL-1992; X = wschód, Y = północ.

**Uzasadnienie:** Studenci i projektanci pracują w CAD na mapie
zasadniczej w PL-2000; R12 otworzy każdy program. Pola w PL-2000 są
zgodne z rzeczywistymi do 0,005%, w PL-1992 mniejsze o ok. 0,1%.

**Odrzucone alternatywy:**
- Biblioteka ezdxf jako zależność — duża (numpy, fonttools) dla kilku
  typów obiektów; użyta tylko do sprawdzenia plików w testach ręcznych.
- Nowsze wersje DXF (2000+) — więcej obowiązkowych tabel, a nic nie
  zyskujemy dla prostych wieloboków.
- Polskie znaki w opisach — R12 nie ma jednolitego kodowania (strona
  kodowa zależy od programu).

## D-131 — DXF działki z tych samych obiektów co GeoJSON
Data: 2026-10-01

**Decyzja:** Eksport DXF działki korzysta z tej samej funkcji co eksport
GeoJSON (`_cechy_eksportu`): działka z ULDK, części w przeznaczeniach z
WFS gminy albo przeznaczenie z KIMPZP. Zapis DXF przez `dane/dxf.py`
(D-130); nazwa warstwy części to PRZEZN_ + symbol z planu.

**Uzasadnienie:** Oba eksporty zawsze pokazują to samo i tak samo
reagują na błędy usług. Warstwa na przeznaczenie pozwala w CAD włączać i
wyłączać przeznaczenia jak w QGIS.

**Odrzucone alternatywy:**
- Osobne zapytania do usług dla DXF — rozjechałyby się z GeoJSON.
- Kreskowanie (HATCH) przeznaczeń — R12 go nie ma; kolor warstwy wystarcza.

## D-132 — Typologia gmin: k-średnich bez losowania, opisy typów z profilu
Data: 2026-10-01

**Decyzja:** Typologię liczymy metodą k-średnich na wskaźnikach
standaryzowanych, z deterministycznym startem (gmina najbliższa średniej,
potem kolejno najdalsza od wybranych). Typy numerujemy od
najliczniejszego. Opis typu powstaje regułą z profilu (|z| ≥ 0,5 →
„wysoki/niski: wskaźnik”). Jakość — średnia sylwetka. Własna
implementacja (ok. 60 wierszy), bez scikit-learn.

**Uzasadnienie:** Student musi móc powtórzyć wynik — losowy start
k-średnich daje różne typy przy każdym kliknięciu. Opis z reguły jest
sprawdzalny i nie pochodzi od modelu językowego. Dla ~200 gmin czysty
Python jest wystarczająco szybki.

**Odrzucone alternatywy:**
- scikit-learn — duża zależność dla jednego algorytmu.
- Wielokrotny losowy start i wybór najlepszego — wynik też zależny od
  ziarna; trudniej wytłumaczyć.
- Grupowanie hierarchiczne (Ward) — dobre, ale wymaga dendrogramu do
  wyboru liczby typów; k-średnich z sylwetką prostsze na I roku.

## D-133 — Liczba typów: sylwetka jako podpowiedź, wybór zostaje przy użytkowniku
Data: 2026-10-01

**Decyzja:** Dla k = 2…8 liczymy średnią sylwetkę tych samych danych i
pokazujemy tabelę z zaznaczeniem najwyższej wartości; k nie zmienia się
samo — użytkownik klika wiersz. Przy remisie wskazujemy mniejsze k.

**Uzasadnienie:** Sylwetka często wskazuje 2 typy (najprostszy podział),
a w analizie regionalnej typy muszą też mieć sens merytoryczny — to
decyzja planisty, nie algorytmu.

**Odrzucone alternatywy:**
- Automatyczny wybór k — ukrywa decyzję metodyczną.
- Metoda „łokcia” (suma kwadratów) — wymaga odczytu załamania z wykresu,
  mniej jednoznaczna niż sylwetka.

## D-134 — Diagnostyka: sprawdzanie usług na żądanie, bez kluczy
Data: 2026-10-01

**Decyzja:** Strona diagnostyki pokazuje konfigurację i dane od razu, a
usługi zewnętrzne sprawdza dopiero po kliknięciu: jedno GET na adres ze
stałej modułu, limit 6 s, równolegle. Każda odpowiedź HTTP oznacza
„serwer osiągalny” (sprawdzamy połączenie, nie poprawność danych). Klucze
tylko jako „ustawiony / brak”; do Gemini nie wysyłamy klucza.

**Uzasadnienie:** Najczęstsze „nie działa” to brak internetu, awaria
usługi albo brak klucza — strona rozróżnia te przypadki w kilka sekund.
Adresy ze stałych modułów: diagnostyka sprawdza dokładnie to, czego
używa kod. Strona nadaje się do wysłania przy zgłaszaniu problemu.

**Odrzucone alternatywy:**
- Automatyczne sprawdzanie przy otwarciu — zbędny ruch i oczekiwanie.
- Próbne zapytanie do Gemini z kluczem — koszt i limit zapytań.

## D-135 — Dziennik błędów: plik rotowany w instance/logi, bez kopii zapasowej
Data: 2026-10-01

**Decyzja:** Logger aplikacji zapisuje WARNING i wyżej do
`instance/logi/warsztat.log` (1 MB × 4 pliki najwyżej). Podgląd w
Diagnostyce czyta pliki od najstarszego i pokazuje 30 najnowszych wpisów.
Dziennik pomijamy w kopii zapasowej.

**Uzasadnienie:** Aplikację uruchamia się ikoną; okno terminala z
komunikatami znika po zamknięciu — bez pliku nie da się później
powiedzieć, co się stało. Rotacja chroni dysk.

**Odrzucone alternatywy:**
- Zapis INFO i niżej — szum (każde zapytanie), szybka rotacja.
- Dziennik w bazie SQLite — błąd bazy uniemożliwiłby zapis błędu.
- Dziennik w kopii zapasowej — to nie dane użytkownika, a może zawierać
  ścieżki z komputera.

## D-136 — Wyszukiwarka globalna: funkcja w każdym module, zbieranie w app.py
Data: 2026-10-02

**Decyzja:** Każdy moduł przeszukuje swoje dane własną funkcją
`wyszukaj(fraza)` (ten sam wzorzec co `podsumowanie()` dla strony
głównej) i zwraca proste wyniki z adresem; `app.py` je zbiera i grupuje.
Przepisy używają istniejącej wyszukiwarki pełnotekstowej, reszta —
zawierania frazy bez wielkości liter. Bez wspólnego indeksu.

**Uzasadnienie:** Moduły zostają niezależne (osobne bazy), a nowy moduł
dokłada jedną funkcję. Przy danych jednej osoby (setki rekordów) prosty
przegląd jest natychmiastowy.

**Odrzucone alternatywy:**
- Wspólny indeks FTS dla wszystkich modułów — synchronizacja przy każdej
  zmianie w każdym module.
- Wyszukiwanie gmin w BDL — wymaga sieci; Atlas ma własny wybór gminy.

## D-137 — Przywracanie kopii: sprawdzenie przed zmianą, poprzednie dane przenoszone
Data: 2026-10-02

**Decyzja:** Przywracanie najpierw rozpakowuje i sprawdza kopię w folderze
tymczasowym (struktura, ścieżki, rozmiar, integralność baz), potem robi
kopię bieżących danych, przenosi je do `instance_stary_<data>` i dopiero
wstawia dane z kopii. Źródło: wgrany ZIP (limit 50 MB) albo plik z
folderu kopii wybrany z listy. Wymagane potwierdzenie.

**Uzasadnienie:** Przywracanie jest jedyną operacją, która zastępuje
wszystkie dane naraz — każdy błąd (zły plik, uszkodzona baza, przerwanie)
musi zostawić obecne dane nietknięte albo zachowane w dwóch miejscach.
Ręczne przywracanie z instrukcji było dla studenta zbyt ryzykowne.

**Odrzucone alternatywy:**
- Usuwanie poprzednich danych po przywróceniu — nieodwracalne.
- Restart aplikacji po przywróceniu — połączenia z bazami otwierane są na
  zapytanie, więc nie jest potrzebny.
- Dowolna ścieżka pliku do przywrócenia — tylko pliki z listy (jak RCN).

## D-138 — Dostępność sprawdzana automatycznie w przeglądzie stron
Data: 2026-10-02

**Decyzja:** Podstawowe reguły dostępności (lang, alt, etykiety pól,
nazwy przycisków i linków, unikalne id) sprawdza skrypt przeglądu stron
na każdej stronie; dodany link „Przejdź do treści” i ramka fokusu
`:focus-visible`. Etykiety dodajemy przez `aria-label` tam, gdzie
widoczny tekst obok pola wystarcza wzrokowo, ale nie jest powiązany z
polem.

**Uzasadnienie:** Ręczne sprawdzanie łatwo pominąć przy nowej stronie;
reguły w skrypcie działają dla każdej strony z tablicy tras. Obsługa
klawiaturą i czytnikiem ekranu to wymaganie dostępności cyfrowej.

**Odrzucone alternatywy:**
- axe-core — zewnętrzny skrypt wstrzykiwany do stron (CDN niedostępny w
  aplikacji offline); podstawowe reguły wystarczą.
- Ramka fokusu także przy kliknięciu myszą — rozprasza; `:focus-visible`
  pokazuje ją tylko z klawiatury.

## D-139 — Osobny token na tło pod białym tekstem; kontrast w testach
Data: 2026-10-02

**Decyzja:** Kolor akcentu ma dwie role: tekst/link (`--akcent`) i tło
pod białym tekstem (`--akcent-wypelnienie`). W ciemnym motywie link
zostaje jasnoniebieski (dobry kontrast na ciemnym tle), a przyciski mają
ciemniejszy niebieski. Kontrast par tekst/tło z tokenów sprawdza test
(próg WCAG AA 4,5:1).

**Uzasadnienie:** Jeden kolor nie spełni obu ról w ciemnym motywie —
jasny niebieski jest czytelny jako tekst na czarnym, ale biały napis na
nim ma kontrast 3:1. Test liczy kontrast z tego samego pliku CSS, z
którego korzysta aplikacja.

**Odrzucone alternatywy:**
- Ciemny tekst na przyciskach w ciemnym motywie — niespójne z jasnym.
- Ręczny audyt bez testu — kolejna zmiana koloru mogłaby wrócić do 3:1.

## D-140 — Teren: heksagony z automatyczną wielkością, wartość najczęstsza
Data: 2026-10-02

**Decyzja:** Wielkość heksagonów w raporcie terenu dobieramy z danych:
najdrobniejsza z trzech siatek (krawędź ok. 30 / 75 / 200 m), w której na
komórkę przypadają średnio co najmniej 2 punkty. Dla pola wyboru
pokazujemy wartość najczęstszą w komórce z udziałem. Sekcja od 10 punktów.

**Uzasadnienie:** Inwentaryzacja obejmuje od placu po dzielnicę — stała
wielkość komórki dałaby jedną komórkę albo same pojedyncze punkty. Wartość
najczęstsza z udziałem jest zrozumiała bez statystyki.

**Odrzucone alternatywy:**
- Wybór wielkości przez użytkownika — raport ma działać bez ustawień.
- Mapa ciepła (gęstość jądrowa) — wymaga parametru wygładzania i trudniej
  ją opisać w raporcie.

## D-141 — Import GeoJSON do terenu: dopasowanie po nazwie, reszta w uwagach
Data: 2026-10-02

**Decyzja:** Atrybuty GeoJSON przypisujemy do pól projektu po nazwie
(bez wielkości liter), z łagodnym przeliczeniem typów, a następnie
sprawdzamy tak samo jak dane z telefonu. Atrybuty bez pola nie giną —
trafiają do uwag z nazwą, a użytkownik dostaje ich listę. Identyfikator
punktu wynika z treści (położenie + atrybuty), więc ponowny import nie
dubluje punktów.

**Uzasadnienie:** Punkty z innych źródeł (QGIS, dane miejskie) rzadko
mają dokładnie nasze nazwy i typy; utrata atrybutu bez informacji byłaby
gorsza niż zapis w uwagach.

**Odrzucone alternatywy:**
- Kreator mapowania atrybutów na pola — więcej kroków dla rzadkiej
  operacji; zmiana nazwy atrybutu w QGIS jest prosta.
- Przeliczanie z PL-1992/PL-2000 — GeoJSON (RFC 7946) jest w WGS84;
  QGIS zapisuje go tak domyślnie.

## D-142 — Projekt podobny: kopiujemy definicję, nie dane
Data: 2026-10-02

**Decyzja:** „Utwórz podobny” kopiuje to, co opisuje formularz (pola,
rodzaj, obszar mapy), a nie wyniki (punkty, zdjęcia) ani termin. Nowy
projekt ma własny klucz, więc plik z telefonu z jednego projektu nie da
się zaimportować do drugiego.

**Uzasadnienie:** Powtarzalne inwentaryzacje (ten sam formularz w innym
kwartale, kolejny rok) wymagały dotąd ręcznego przepisywania pól.

**Odrzucone alternatywy:**
- Kopiowanie z punktami — mieszałoby pomiary z różnych terminów.
- Osobna biblioteka „szablonów” — wzorce wbudowane już są; projekt jako
  wzór wystarcza bez nowego miejsca w interfejsie.

## D-143 — Premia rynku pierwotnego tylko przy 5 transakcjach na rynek
Data: 2026-10-02

**Decyzja:** W porównaniu obszarów mediana za m² liczy się osobno dla
rynku pierwotnego i wtórnego; różnicę procentową („premia pierwotnego”)
pokazujemy tylko, gdy oba rynki mają w obszarze co najmniej 5 transakcji.
Liczby obok median zawsze widać.

**Uzasadnienie:** Różnica między rynkami to jedno z pierwszych pytań przy
analizie cen dzielnicy, a dotąd wymagała dwukrotnego przełączania filtra
i liczenia w pamięci. Próg 5 jest ten sam co w medianach rocznych (D-118).

**Odrzucone alternatywy:**
- Premia bez progu — przy 1–2 transakcjach deweloperskich wynik byłby
  przypadkowy, a wyglądałby jak wskaźnik.
- Osobny przełącznik „porównaj rynki” — tabela pojawia się sama, gdy
  w danych są oba rynki.

## D-144 — Nowsza wersja pliku RCN pod tym samym id
Data: 2026-10-02

**Decyzja:** Import może zastąpić transakcje istniejącego pliku zamiast
tworzyć nowy. Wiersz `rcn_pliki` zostaje (nowa nazwa, data importu,
liczby), transakcje są usuwane i wstawiane od nowa, obszary (`rcn_obszary`)
są nietknięte. Wybór robi użytkownik; domyślnie „nowy plik”.

**Uzasadnienie:** RCN aktualizuje się co kwartał. Bez tej opcji nowy plik
oznaczał ponowne rysowanie wszystkich dzielnic, a stary plik zostawał w bazie
(kilkaset MB przy dużym mieście po kilku kwartałach).

**Odrzucone alternatywy:**
- Automatyczne zastępienie pliku o tej samej nazwie — pliki z geoportalu
  mają różne nazwy, a zgadywanie „to ten sam powiat” byłoby kruche.
- Dokładanie tylko nowych transakcji — RCN poprawia też stare rekordy;
  pełna podmiana jest prostsza i zgodna ze źródłem.
- Kopiowanie obszarów do nowego pliku — zmieniałoby adresy (numer pliku)
  zapisane np. w zakładkach.

## D-145 — Raport miast z serwera, wykres wspólny z raportem transakcji
Data: 2026-10-02

**Decyzja:** Raport porównania miast renderuje serwer (Jinja + SVG z
`rcn.wykres_lat_svg`), z tych samych szeregów BDL i funkcji
`analiza.podsumuj` / `analiza.dostepnosc` co strona modułu. Kolory miast
są skopiowane z `ceny.js` (stała `KOLORY_MIAST`).

**Uzasadnienie:** Wydruk ma wyglądać tak samo bez JavaScriptu i w PDF;
wykres liniowy w latach już istniał dla obszarów RCN, więc zamiast drugiej
funkcji rysującej przekazujemy mu szeregi GUS (jedna wartość na rok =
wszystkie punkty pełne).

**Odrzucone alternatywy:**
- Druk strony modułu (window.print) — formularze, ranking i wybór
  województwa na wydruku, wykres zależny od JS.
- Osobna funkcja wykresu dla GUS — duplikat ~40 linii.

## D-146 — Obszar z GeoJSON: układ z „crs” albo z zakresu liczb, bez pyproj
Data: 2026-10-02

**Decyzja:** Plik z granicą opracowania przyjmujemy w WGS84, PL-1992
i PL-2000. Układ bierzemy z pola `crs` (QGIS je zapisuje dla układów innych
niż 4326), a gdy go nie ma — z zakresu współrzędnych, które dla tych trzech
układów na obszarze Polski są rozłączne. Przeliczenie: własne szeregi
Krügera z `mpzp/uklady.py` (dołożona odwrotność PL-2000).

**Uzasadnienie:** Granica opracowania zwykle powstaje w QGIS na mapie
zasadniczej w PL-2000 albo na ortofotomapie w PL-1992; wymaganie
przeliczenia do WGS84 przed importem byłoby zbędnym krokiem.

**Odrzucone alternatywy:**
- pyproj — ciężka zależność (biblioteka PROJ) dla trzech układów, które
  i tak już liczymy.
- Tylko WGS84 — najczęstszy błąd studenta to plik w układzie projektu QGIS.

## D-147 — Luki rozpisane na zwykłe fiszki, bez nowego typu w bazie
Data: 2026-10-02

**Decyzja:** Fiszka z luką nie jest osobnym typem. Tekst z `[[lukami]]`
serwer zamienia na N zwykłych fiszek (pytanie z „[…]”, odpowiedź = ukryte
słowa), każda z kotwicą w tym samym fragmencie PDF-a. Luki wybiera
użytkownik, nie Gemini.

**Uzasadnienie:** Definicje i wyliczenia z wykładów najlepiej uczyć się
z luką, a cała reszta (pudełka Leitnera, plik na telefon, quiz, druk,
eksport do Anki) działa na parach pytanie–odpowiedź. Nowy typ wymagałby
zmian w siedmiu miejscach, w tym w samodzielnym pliku na telefon.

**Odrzucone alternatywy:**
- Kolumna `rodzaj` i renderowanie luk przy powtórce — edycja jednej
  fiszki zmieniałaby wszystkie z tego tekstu, a telefon wymagałby nowej
  wersji formatu.
- Luki proponowane przez Gemini — wybór, co jest ważne, to część nauki;
  propozycje pytań z modelu już są.

## D-148 — Notatka przypięta do jednostki wgranego aktu
Data: 2026-10-02

**Decyzja:** Notatka jest kluczowana numerem jednostki (`jednostka_id`)
z kopią `akt_id`. Nowszy tekst jednolity to w Warsztacie nowy akt, więc
notatki go nie „przechodzą” — zostają przy starej wersji.

**Uzasadnienie:** Jednostki aktu nie są nigdy dzielone ponownie w miejscu,
więc numer jednostki jest stały. Przenoszenie po oznaczeniu („Art. 15”)
między wersjami byłoby mylące, gdy nowelizacja zmieniła treść artykułu —
notatka opisywałaby inny tekst.

**Odrzucone alternatywy:**
- Klucz (akt, oznaczenie) — w rozporządzeniach z załącznikami oznaczenia
  potrafią się powtarzać.
- Notatki jako fiszki — fiszka to pytanie i odpowiedź do powtórek,
  notatka to komentarz do czytania; inne użycie.

## D-149 — „Ostatnio używane” z danych modułów, bez dziennika odwiedzin
Data: 2026-10-02

**Decyzja:** Sekcja „Wróć do pracy” powstaje z dat, które moduły już
zapisują (zmiana koncepcji, import punktów, nowa fiszka, powtórka,
notatka, import pliku RCN, sprawdzenie działki). Każdy moduł podaje swoje
pozycje funkcją `ostatnie`, strona główna je łączy.

**Uzasadnienie:** Praca nad projektem semestralnym wraca do tych samych
kilku rzeczy; dotąd trzeba było wejść w moduł i wybrać z listy.

**Odrzucone alternatywy:**
- Dziennik odwiedzanych stron — samo otwarcie to nie praca; zapis przy
  każdym wejściu oznaczałby nową tabelę i zapisy przy odczycie.
- Atlas i Dostępność w sekcji — nie przechowują dat zmian (cache GUS i
  pliki wyników); dodawanie ich tylko dla tej sekcji to zbędna zmiana schematu.

## D-150 — Jedna stopka wydruków jako makro Jinja
Data: 2026-10-02

**Decyzja:** Strony do druku kończą się wspólnym makrem
`stopka_wydruku` z `templates/_wydruk.html`. Stopka stoi na końcu
dokumentu, nie na każdej kartce. Test pilnuje, żeby nowa strona z
przyciskiem „Drukuj” jej nie pominęła.

**Uzasadnienie:** Dopiski o źródle i dacie były w każdym raporcie inne
(albo ich nie było); wydruk do pracy semestralnej musi mówić, skąd są dane
i z którego dnia. To dziesięć stron w ośmiu modułach — wspólny element ma
tu sens (zasada „bez abstrakcji dla dwóch modułów” nie dotyczy).

**Odrzucone alternatywy:**
- Stopka na każdej stronie (`position: fixed` albo `@page` z polami
  marginesu) — `fixed` nachodzi na treść, pola marginesu nie działają w
  Firefoksie, domyślnej przeglądarce Linux Mint.

## D-151 — Biblioteka Gemini ładowana przy pierwszym zapytaniu
Data: 2026-10-02

**Decyzja:** `google.genai` importujemy wewnątrz `dane/gemini._generuj`,
a nie na początku modułu. Wszystkie wywołania modelu idą przez tę funkcję.
Test pilnuje, żeby start aplikacji biblioteki nie ładował.

**Uzasadnienie:** Import trwał ok. 0,4 s, połowę czasu od kliknięcia ikony
do gotowego serwera, a większość uruchomień w ogóle nie pyta modelu.
Przy okazji sześć skopiowanych bloków (klient, zapytanie, zamiana błędu)
zeszło do jednego miejsca.

**Odrzucone alternatywy:**
- Dłuższe przechowywanie statycznych plików w pamięci przeglądarki
  (`SEND_FILE_MAX_AGE_DEFAULT`) — lokalnie zysk znikomy, a po aktualizacji
  stary CSS/JS zostawałby w przeglądarce.

## D-152 — Pokrycie mierzone doraźnie, bez progu w testach
Data: 2026-10-02

**Decyzja:** `coverage` uruchamiamy z osobnego środowiska przy przeglądach
(instrukcja w README), nie dodajemy go do `requirements.txt` ani nie
ustawiamy progu, poniżej którego testy „nie przechodzą”.

**Uzasadnienie:** Liczba procent sama nie mówi, czy testy sprawdzają to, co
ważne — przegląd luk pokazał np. nieprzetestowany parser odpowiedzi modelu,
a to on decyduje, co trafia do fiszki. Próg kusiłby testami „dla procentu”.

**Odrzucone alternatywy:**
- pytest-cov w zależnościach — kolejny pakiet w instalacji użytkownika
  tylko dla narzędzia deweloperskiego.

## D-153 — Architektura opisana w jednym pliku, ze stanem faktycznym
Data: 2026-10-02

**Decyzja:** `docs/ARCHITEKTURA.md` opisuje aplikację tak, jak jest w
kodzie (sprawdzone importami i grepem), z odnośnikami do decyzji.
Rozbieżność z opisem stosu w CLAUDE.md jest nazwana wprost: geometria
leży w SQLite jako GeoJSON i liczy ją shapely, SpatiaLite nie wszedł do
projektu.

**Uzasadnienie:** Po 140 ETAPach wiedza o układzie była rozsiana po
PROGRESS (2500 linii) i 150 decyzjach. Ktoś wracający po trzech miesiącach
potrzebuje mapy na jedną stronę.

**Odrzucone alternatywy:**
- Diagramy generowane narzędziem — kolejna zależność; obraz ASCII
  wystarcza i da się go poprawić w edytorze.
- Zmiana wpisu o SpatiaLite w CLAUDE.md — to sekcja „Stack — nie zmieniaj
  bez pytania”; zostaje do decyzji autora.

## D-154 — Pierwsze kroki znikają same, bez przycisku „ukryj”
Data: 2026-10-02

**Decyzja:** Karta „Pierwsze kroki” pokazuje się, dopóki instalacja jest
pusta, i znika po pierwszym zapisie w dowolnym module. Stan kluczy liczy
serwer (czy są ustawione, bez treści — jak w diagnostyce).

**Uzasadnienie:** Nowy użytkownik widział osiem kart bez wskazówki, że
część funkcji wymaga klucza w `.env`, a część działa od razu na przykładach.

**Odrzucone alternatywy:**
- Przycisk „ukryj” zapamiętany w przeglądarce — kolejny stan do
  pilnowania; karta i tak przestaje być potrzebna po pierwszej pracy.
- Kreator krok po kroku — za dużo jak na dwie zmienne w `.env`.

## D-155 — Ostrzeżenia o zasobach jako błędy testów; tekst do dymków jako węzeł
Data: 2026-10-02

**Decyzja:** `pytest.ini` zamienia `ResourceWarning` na błąd. Do dymków
Leaflet (`bindTooltip`, `bindPopup`) tekst spoza kodu trafia wyłącznie jako
element z `textContent`.

**Uzasadnienie:** Ostrzeżenie o niezamkniętym pliku pojawiało się co
kilka przebiegów przy przypadkowym teście i przez kilkadziesiąt ETAPów
było odkładane. Jako błąd wskazuje winny test od razu. Leaflet traktuje
napis w dymku jako HTML, więc nazwa z wgranego pliku mogła wykonać skrypt
na stronie aplikacji, która ma dostęp do wszystkich danych użytkownika.

**Odrzucone alternatywy:**
- Escapowanie napisów przed `bindTooltip` — łatwo zapomnieć o nowym
  miejscu; węzeł DOM jest bezpieczny z definicji.

## D-156 — Słowa 4-literowe w wyszukiwarce przepisów po początku
Data: 2026-10-02

**Decyzja:** W wyszukiwarce aktów słowo 4-literowe jest szukane jako
początek wyrazu („plan” → plan, planu, planie, planowanie). Słowa 2–3
literowe nadal dokładnie.

**Uzasadnienie:** „plan” to jedno z najczęstszych zapytań w gospodarce
przestrzennej, a w tekście ustawy prawie zawsze jest odmienione — zapytanie
nie dawało wyników. Przy 2–3 literach (skróty „mn”, „ust”) prefiks
zalewałby wyniki.

**Odrzucone alternatywy:**
- Polski stemmer — zależność spoza biblioteki standardowej dla jednej
  wyszukiwarki; prosta reguła długości słowa wystarcza.

## D-157 — Liczby w portfolio liczone z repozytorium przy każdej aktualizacji
Data: 2026-10-02

**Decyzja:** Sekcja „Liczby” w PORTFOLIO podaje stan na konkretny ETAP i
jest liczona poleceniami (wiersze z `git ls-files`, liczba testów z
pytest, decyzji z `DECISIONS.md`, stron z przeglądu), nie przepisywana.

**Uzasadnienie:** README mówił o „siedmiu” narzędziach przez kilkadziesiąt
ETAPów po dodaniu ósmego modułu. Opis do portfolio jest czytany przez
obce osoby — liczby muszą się zgadzać z kodem.

**Odrzucone alternatywy:**
- Liczby generowane automatycznie w dokumencie — kolejny skrypt do
  utrzymania przy aktualizacji raz na kilkadziesiąt ETAPów.

## D-158 — Plan kolejnych ETAPów: dwadzieścia konkretnie, reszta kierunkami
Data: 2026-10-02

**Decyzja:** Plan na ETAPy 151–200 rozpisuje konkretnie tylko 151–170
(co i dlaczego), a 171–200 jako kierunki. Szczegóły dalszej części powstaną
po przeglądzie w ETAPie 170.

**Uzasadnienie:** Plan ETAPów 121–150 zmieniał się w trakcie (np. przegląd
stron wyłapał błędy wyszukiwarki, przegląd kodu — dymki map). Rozpisanie 50
pozycji z góry dawałoby listę, która po drodze przestaje odpowiadać
temu, co wychodzi w użyciu.

**Odrzucone alternatywy:**
- Pełna lista 50 ETAPów — sztywna i w połowie nieaktualna przed realizacją.

## D-159 — Motyw ręczny w przeglądarce, nie w bazie
Data: 2026-10-02

**Decyzja:** Wybór motywu trzyma localStorage przeglądarki i ustawia go
krótki skrypt w `<head>` (atrybut `data-motyw`). Tokeny trybu ciemnego są
w dwóch blokach CSS (systemowy i ręczny); test pilnuje, że są identyczne.

**Uzasadnienie:** To ustawienie wyglądu jednej przeglądarki, nie dane
użytkownika — nie powinno trafiać do kopii zapasowej ani wymagać zapytania
do serwera. Skrypt w `<head>` zapobiega mignięciu jasnej strony.

**Odrzucone alternatywy:**
- Ustawienie po stronie serwera (ciasteczko / baza) — zapis przy każdej
  zmianie i obsługa w każdym module dla czysto wizualnej rzeczy.
- Zmienne CSS bez duplikacji przez `light-dark()` — nowsza funkcja CSS,
  starsze przeglądarki na Linux Mint by jej nie obsłużyły.

## D-160 — Gi* z istotnością z rozkładu normalnego, sprawdzony z PySAL
Data: 2026-10-02

**Decyzja:** Gi* liczy się wzorem analitycznym (z-score, p z rozkładu
normalnego, progi 90/95/99% jak w ArcGIS Hot Spot Analysis), bez
permutacji. Poprawność sprawdzona porównaniem z PySAL (esda) w osobnym
środowisku — PySAL nie jest zależnością projektu.

**Uzasadnienie:** Gi* jest standardem w analizie „gorących punktów” i
uzupełnia LISA (skupiska wartości zamiast podobieństwa do sąsiadów). Wzór
analityczny to jedna pętla, bez kosztu 999 permutacji na gminę.

**Odrzucone alternatywy:**
- esda/libpysal jako zależność — numpy, scipy i pandas dla jednego wzoru.
- Permutacyjna istotność jak w LISA — dla Gi* praktyka (ArcGIS, QGIS)
  opiera się na z-score; wynik byłby nieporównywalny z tymi narzędziami.

## D-161 — LQ z sum województwa i ze stałymi klasami
Data: 2026-10-02

**Decyzja:** Udział województwa w ilorazie lokalizacji liczymy z sum
(Σx/ΣX gmin z danymi), nie jako średnią wskaźników gmin. Klasy LQ są
stałe (0,5 / 0,8 / 1,2 / 2), wspólne dla wszystkich map.

**Uzasadnienie:** Średnia wskaźników dawałaby małym gminom tę samą wagę co
miastom i zawyżała lub zaniżała punkt odniesienia; definicja podręcznikowa
używa sum. Stałe klasy pozwalają porównać mapy różnych branż i lat.

**Odrzucone alternatywy:**
- Klasy z kwantyli jak na mapie wartości — „1 = jak w województwie”
  straciłoby znaczenie.

## D-162 — Wycinek rysunku robi przeglądarka, serwer tylko sprawdza PNG
Data: 2026-10-02

**Decyzja:** Wycinek powstaje w przeglądarce z płótna, na którym pdf.js
narysował stronę; serwer przyjmuje gotowy PNG (data URL), sprawdza
sygnaturę i rozmiar i zapisuje plik. Obraz należy do pytania. W pliku na
telefon jest osadzony jako data URL; eksport CSV/Anki zostaje tekstowy.

**Uzasadnienie:** Strona jest już wyrenderowana na płótnie — wycięcie to
jedno `drawImage`. Renderowanie PDF po stronie serwera wymagałoby nowej
zależności (np. PyMuPDF / poppler).

**Odrzucone alternatywy:**
- Kolumna `obraz` w tabeli `fiszki` — moduł dokłada nowe tabele zamiast
  kolumn (bez migracji), jak tematy.
- Obrazy w eksporcie Anki — wymaga paczki .apkg z mediami, osobny format.

## D-163 — Koszty koncepcji tylko ze stawek wpisanych przez użytkownika
Data: 2026-10-02

**Decyzja:** Szacunek kosztów nie ma stawek domyślnych. Pozycje bez
wpisanej stawki są pomijane; bez żadnej stawki sekcji nie ma w raporcie.

**Uzasadnienie:** W odróżnieniu od założeń programu (osoby na mieszkanie
zmieniają się powoli) ceny budowy zmieniają się z kwartału na kwartał i
między regionami. Stawka wpisana w kod wyglądałaby jak dana, a byłaby
zgadywaniem — sprzeczne z zasadą „liczby z danych”.

**Odrzucone alternatywy:**
- Stawki z publikacji (np. wskaźniki cenowe) wpisane w kod — dezaktualizują
  się bez śladu w interfejsie.
- Stawka gruntu z mediany cen RCN w okolicy — dobry pomysł na później,
  ale wymaga rozróżnienia przeznaczenia działek; na razie wpis ręczny.

## D-164 — Regresja cen bez numpy, z jawnym opisem ograniczeń
Data: 2026-10-02

**Decyzja:** Metoda najmniejszych kwadratów jest napisana w module
(odwrócenie macierzy 3×3–5×5 metodą Gaussa-Jordana); poprawność sprawdzona
z numpy w osobnym środowisku. Istotność z progu |t| ≥ 1,96 (duże próby,
min. 30 transakcji), bez rozkładu t. Interfejs mówi wprost: związek w
danych, nie wycena i nie przyczyna; R² pokazuje, ile cechy wyjaśniają.

**Uzasadnienie:** Pytanie „ile kosztuje piętro / rynek pierwotny” wraca
przy każdej analizie cen; mediany w grupach mieszają cechy (nowe mieszkania
są też mniejsze i w innych miejscach). Model z kilkoma zmiennymi rozdziela
te związki. numpy dla pięciu kolumn to zbędna zależność.

**Odrzucone alternatywy:**
- Lokalizacja w modelu (współrzędne, dzielnice) — wymaga przemyślenia
  (efekty przestrzenne); do rozważenia później.
- Logarytm ceny — trudniejszy do odczytania dla czytelnika raportu.

## D-165 — Te same miejsca: wzajemnie najbliższe punkty w promieniu 15 m
Data: 2026-10-02

**Decyzja:** Punkty dwóch inwentaryzacji łączymy w pary, gdy są dla siebie
nawzajem najbliższe i leżą najwyżej 15 m od siebie. Zmiany „lepiej /
gorzej” liczymy tylko dla pól na skali, z kolejności opcji.

**Uzasadnienie:** Punkty z telefonu nie mają wspólnego identyfikatora
obiektu, a GPS ma ±5–10 m. Warunek wzajemności nie łączy jednego punktu
z dwoma; próg 15 m pokrywa błąd GPS, a nie łączy sąsiednich drzew w
typowym szpalerze (rozstaw 8–10 m bywa — dlatego raport prosi o sprawdzenie
przy gęstych pomiarach).

**Odrzucone alternatywy:**
- Identyfikator obiektu wpisywany w terenie — dodatkowa praca i błędy
  przepisywania; może później jako pole opcjonalne.
- Optymalne przypisanie (algorytm węgierski) — przy tych skalach wynik
  prawie ten sam, kod dużo trudniejszy.

## D-166 — Wybór artykułów do druku w adresie strony
Data: 2026-10-02

**Decyzja:** Lista jednostek do druku jest w parametrach adresu (`?j=`),
nie w bazie; zaznaczenia na stronie aktu nie są zapamiętywane.

**Uzasadnienie:** Wybór do wydruku jest jednorazowy (przed kolokwium);
adres da się zapisać w zakładkach, a stan w bazie trzeba by sprzątać.
Notatki, które są trwałe, mają własny tryb `?notatki=1`.

**Odrzucone alternatywy:**
- Zapamiętane „zakładki” artykułów — notatki pełnią już tę rolę.

## D-167 — „Co nowego” z CHANGELOG-u, bez osobnej listy
Data: 2026-10-02

**Decyzja:** Strona „Co nowego” czyta `docs/CHANGELOG.md`, który i tak jest
uzupełniany po każdym ETAPie. Ostatnio obejrzany ETAP to jedna liczba w
pliku w `instance/`.

**Uzasadnienie:** Użytkownik nie czyta plików w repozytorium, a po
aktualizacji o kilka ETAPów nie wie, co doszło. Jedno źródło zmian — brak
ryzyka, że dwie listy się rozjadą.

**Odrzucone alternatywy:**
- Osobna, krótsza lista „dla użytkownika” — kolejny plik do utrzymania.

## D-168 — Przegląd stron na koncepcjach z treścią
Data: 2026-10-02

**Decyzja:** Dane w narzędziu przeglądu stron obejmują nie tylko „puste”
obiekty (projekt, koncepcja), ale też takie z treścią, która wyświetla
tabele i sekcje warunkowe (tereny, koszty, notatki, wycinki, drugi
projekt do porównania).

**Uzasadnienie:** Błąd z ETAPu 100 (tabela cienia poszerzała raport na
telefonie) przetrwał 60 ETAPów, bo przegląd oglądał koncepcję bez terenów —
sekcji nie było na stronie.

**Odrzucone alternatywy:**
- Osobny zestaw danych przeglądu w pliku — dane zasiewa ten sam skrypt,
  czytelnie obok listy stron.

## D-169 — Małe mapy we wspólnych klasach ze wszystkich lat
Data: 2026-10-02

**Decyzja:** Progi klas dla arkusza „mapy w latach” liczymy z wartości
gmin ze wszystkich wybranych lat razem, wybraną metodą klasyfikacji.

**Uzasadnienie:** Osobne klasy dla każdego roku (np. kwantyle) dawałyby
zawsze ten sam rozkład kolorów i ukrywały wzrost lub spadek — porównanie
map byłoby mylące. Wspólne klasy pokazują zmianę wprost.

**Odrzucone alternatywy:**
- Mapa zmiany między dwoma latami — już jest (widok „Zmiana”); małe mapy
  pokazują przebieg w kilku punktach czasu.

## D-170 — Zestawienie działek z danych zapisanych, bez pobierania na nowo
Data: 2026-10-02

**Decyzja:** Zestawienie „Moich działek” korzysta wyłącznie z tego, co
zapisano razem z działką (przeznaczenie, powierzchnia, punkt), i mówi to
w przypisie. Pełne, aktualne dane daje porównanie działek (pobiera na
nowo) i karta działki.

**Uzasadnienie:** Zestawienie ma działać od razu i bez sieci (np. przed
spotkaniem), także dla kilkudziesięciu działek, które w porównaniu
oznaczałyby kilkadziesiąt zapytań do ULDK i WFS.

**Odrzucone alternatywy:**
- Obrysy działek na schemacie — wymagałyby pobrania geometrii z ULDK.

## D-171 — Dzielnice w Dostępności bez zapisu na serwerze
Data: 2026-10-02

**Decyzja:** Obszary narysowane w module Dostępność nie trafiają do bazy:
przeglądarka trzyma je w localStorage (osobno dla pliku wyników) i
przysyła do bezstanowej trasy, która liczy statystyki. Komórka należy do
obszaru, gdy jej środek jest w wieloboku.

**Uzasadnienie:** Moduł nie ma bazy (czyta pliki wyników CSV, D-015) —
dokładanie jej dla listy wieloboków to nowy plik w kopii zapasowej i
migracje. Obszary łatwo narysować ponownie; wynik zależy tylko od pliku
i wieloboku. Środek komórki zamiast części wspólnej — komórki H3 są małe,
a podział mieszkańców proporcjonalnie do pola byłby fałszywą dokładnością.

**Odrzucone alternatywy:**
- Tabela obszarów jak w Cenach (`rcn_obszary`) — Ceny mają bazę modułu;
  tu byłaby jedyną tabelą.

## D-172 — Stawka gruntu z RCN tylko jako podpowiedź
Data: 2026-10-02

**Decyzja:** Osiedle może pokazać medianę ceny m² działek niezabudowanych
w promieniu 1 km od obszaru (zaimportowany plik RCN), ale wpisuje ją do
stawki gruntu dopiero po kliknięciu. Pozostałe stawki dalej wpisuje
użytkownik (D-163).

**Uzasadnienie:** Dla gruntu jest lokalne źródło liczb (akty notarialne z
RCN), dla kosztów budowy — nie. Działki zabudowane odpadają, bo ich cena
zawiera budynek. Wpis na kliknięcie: przeznaczenie i stan działek w
okolicy bywają różne, a mała próba daje niepewną medianę — użytkownik
widzi liczbę transakcji i lata, zanim zdecyduje.

**Odrzucone alternatywy:**
- Automatyczne wypełnianie pola przy rysowaniu — ukryta liczba w
  kosztorysie, której źródła nie widać.
- Filtr po przeznaczeniu w MPZP działki — w RCN często puste.

## D-173 — Zestawienie plików RCN bez łączenia transakcji
Data: 2026-10-02

**Decyzja:** Pliki różnych powiatów zestawiamy obok siebie (wiersz i
linia na plik), każdy liczony osobno tymi samymi funkcjami co porównanie
obszarów. Transakcji z różnych plików nie łączymy w jeden zbiór, a
obszary zostają przypisane do swojego pliku.

**Uzasadnienie:** Powiaty prowadzą rejestr z różną kompletnością i
w różnym czasie publikują dane — wspólna mediana mieszałaby te różnice.
Zestawienie odpowiada na pytanie „o ile drożej w mieście niż w powiecie
ościennym” bez nowego modelu danych (jak w cenach w okolicy, D-117, gdzie pliki też się nie mieszają). Do 4 plików
— tyle czytelnie mieści tabela i wykres.

**Odrzucone alternatywy:**
- Obszar rysowany ponad granicą plików — wymagałby łączenia transakcji
  i podwójnych wierszy przy nakładających się plikach.

## D-174 — Reguły pól Teren pilnuje telefon, import tylko oznacza braki
Data: 2026-10-02

**Decyzja:** „Wymagane” i zakres liczby sprawdza formularz na telefonie
przed zapisem punktu. Import pliku (z telefonu albo GeoJSON) przyjmuje
punkty niezgodne z regułami, a strona projektu oznacza je ⚠ z opisem.

**Uzasadnienie:** Błąd najtaniej poprawić w terenie, przy obiekcie.
Punkt już zebrany jest cenniejszy niż reguła — reguły zmienia się po
pobraniu formularza, a dane z QGIS nie znały ich wcale; odrzucenie całego
pliku (import „cały plik albo nic”, D-071) kazałoby wracać w teren. Klucze
`wymagane` / `min` / `max` są w definicji pola tylko, gdy ustawione — bez
migracji zapisanych projektów.

**Odrzucone alternatywy:**
- Odrzucanie punktów z brakami przy imporcie — utrata danych z terenu.
- Domyślne zakresy dla wzorów (np. kondygnacje 1–30) — Warsztat nie
  zgaduje reguł za użytkownika.

## D-175 — Skróty klawiszowe: jeden plik wspólny, skróty stron w szablonach
Data: 2026-10-02

**Decyzja:** Skróty wspólne (`?`, `/`, `m`) obsługuje jeden plik
`static/skroty.js` ładowany w `base.html`. Lista w oknie składa się z
wierszy wspólnych i bloku `skroty`, który wypełnia szablon strony.
Skróty działające już w modułach (powtórka, quiz, pomiar w MPZP) zostają
w ich plikach JS — okno tylko je opisuje.

**Uzasadnienie:** Lista skrótów jest tam, gdzie jest strona — kto zmienia
szablon, widzi też jej skróty. Pojedyncze litery bez modyfikatorów, bo
Ctrl/Alt to skróty przeglądarki i systemu (Linux Mint). Skróty nie
działają w polach tekstowych, żeby „m” czy „/” dało się wpisać.

**Odrzucone alternatywy:**
- Rejestr skrótów w JS z opisami generowanymi do okna — wspólna
  abstrakcja dla trzech miejsc; szablon wystarcza.
- Skróty nawigacji „g a” (do Atlasu) itp. — menu jest zawsze widoczne,
  a dwuklawiszowe sekwencje trudno zapamiętać.

## D-176 — Kopia: sprawdzana od razu, „poza dyskiem” z deklaracji użytkownika
Data: 2026-10-02

**Decyzja:** Każda kopia automatyczna przechodzi to samo sprawdzenie co
kopia przed przywróceniem (plus sumy CRC z `testzip`), zanim dostanie
docelową nazwę. O kopii poza komputerem Warsztat wie tylko z kliknięcia
„Skopiowałem kopię poza ten komputer” i przypomina po 30 dniach; osobno
ostrzega, gdy folder kopii jest na tym samym systemie plików co dane.

**Uzasadnienie:** Kopia, z której nie da się przywrócić danych, daje
fałszywe poczucie bezpieczeństwa — lepiej wiedzieć o tym od razu. Aplikacja
działa lokalnie i nie powinna sama wysyłać danych do chmury ani szukać
pendrive'ów; data z deklaracji wystarcza do przypomnienia. Porównanie
`st_dev` nie wymaga uprawnień i działa na Linux Mint.

**Odrzucone alternatywy:**
- Automatyczna kopia do chmury (np. Google Drive) — dane wychodzą z
  komputera, a klucze i zgody to nowa zależność.
- Sprawdzanie wszystkich kopii przy każdym starcie — przy dużych kopiach
  wydłużyłoby start bez potrzeby.

## D-177 — Dokumentacja zbiorczo co ~20 ETAPów, Pomoc na bieżąco
Data: 2026-10-02

**Decyzja:** Wpis w Pomocy powstaje w tym samym ETAPie co funkcja
(użytkownik widzi go od razu), a README, ARCHITEKTURA i PORTFOLIO są
uzupełniane zbiorczo w ETAPie dokumentacyjnym po każdej serii (tu
151–168), razem z przeglądem stron.

**Uzasadnienie:** README i ARCHITEKTURA opisują całość — dopisywane po
jednym zdaniu w każdym ETAPie rozjeżdżały się stylem i powtarzały. Jeden
przegląd po serii pozwala sprawdzić je z kodem (nowe pliki, haki,
powiązania) i odświeżyć liczby w PORTFOLIO naraz.

**Odrzucone alternatywy:**
- Generowanie tabeli plików z kodu — opis „co robi plik” i tak pisze
  człowiek; skrypt dla jednej tabeli to zbędna abstrakcja.

## D-178 — Plan 171–250 w czterech seriach z przeglądem co 20 ETAPów
Data: 2026-10-02

**Decyzja:** ETAPy 171–250 idą czterema seriami po 20; ostatni ETAP
serii to przegląd (testy, pokrycie, pyflakes, przegląd stron) i
dokumentacja zbiorcza. Plan jest kierunkiem: ETAP można zastąpić, gdy
przegląd kodu pokaże, że funkcja już jest albo inna potrzeba jest
ważniejsza — z uzasadnieniem w rekordzie decyzji.

**Uzasadnienie:** Seria 151–170 pokazała, że przegląd po ~20 ETAPach
łapie rzeczy, których nie widać w pojedynczym ETAPie (przepełnienia
szerokich tabel, powielony CSS, wolne parowanie punktów). Plan rozkłada
pracę równo na moduły i kończy się porządkami (podział dużych plików,
samouczek), żeby projekt dało się dalej czytać po trzech miesiącach.

**Odrzucone alternatywy:**
- Plan tylko do 200 i nowy plan potem — mniej spójne serie, dwa razy
  ta sama praca przeglądowa.

## D-179 — Wykres gmin w czasie rysowany na serwerze
Data: 2026-10-02

**Decyzja:** Wykres kilku gmin w latach to SVG z Pythona
(`atlas/wykres_svg.py`) na osobnej stronie, a nie rozbudowa wykresu
profilu w JS (`wykres_gminy.js`, jedna seria). Wybór gmin jest w adresie
strony (`gminy=…`), więc wynik da się zapisać jako zakładkę i wydrukować.

**Uzasadnienie:** Strona ma służyć do porównań w pracach zaliczeniowych —
druk i CSV są ważniejsze niż interakcja. Jak mapy do druku: SVG tylko z
liczb i kolorów, nazwy gmin w HTML. Wykres cen (`ceny/rcn.wykres_lat_svg`)
jest podobny, ale to dwa moduły z innymi danymi — bez wspólnej funkcji
(CLAUDE.md: bez abstrakcji dla dwóch modułów).

**Odrzucone alternatywy:**
- Kilka serii w `wykres_gminy.js` — profil gminy zrobiłby się
  przeładowany, a druk wymagałby osobnej ścieżki.
- Mediana województwa jako linia odniesienia — wymaga pobrania wartości
  wszystkich gmin w każdym roku (kilkanaście zapytań do BDL).

## D-180 — Luka w trybie pisania: porównanie całego wpisu, ocena dalej ręczna
Data: 2026-10-02

**Decyzja:** Fiszka z luką w trybie pisania porównuje cały wpis z
odpowiedzią (po uproszczeniu: małe litery, bez interpunkcji) i nazywa
wynik: dokładnie, bez polskich znaków, literówka, inaczej. Ocenę Leitnera
nadal wybiera użytkownik.

**Uzasadnienie:** Odpowiedź w luce to krótki termin („aktem prawa
miejscowego”), więc porównanie słów z ETAPu 39 (wspólne rdzenie) jest
za luźne, a dokładne dopasowanie — za surowe dla literówek i klawiatury
bez polskich znaków. Automatyczna ocena pomijałaby przypadki, gdy wpis
jest poprawnym synonimem; zostaje zasada „oceń się sam” z ETAPu 39
(harmonogram Leitnera, D-012, zależy tylko od ocen użytkownika).

**Odrzucone alternatywy:**
- Kilka luk naraz w jednej karcie — każda luka to osobna fiszka (D-147),
  pole jest jedno.
- Ocena automatyczna „umiem”, gdy wpis się zgadza — mniej kontroli,
  a błąd porównania psułby harmonogram.

## D-181 — Budynek jako osobny obiekt rysunku, nie funkcja terenu
Data: 2026-10-02

**Decyzja:** Budynek to obiekt rysunku z `funkcja: "budynek"`, czytany
osobno (`wczytaj_budynki`) i pomijany przez `wczytaj_tereny`. Bilans
terenu, program, cień i koszty liczą się dalej z terenów; budynki mają
własne zestawienie i kontrole.

**Uzasadnienie:** Budynek stoi na terenie MW/MN/U — gdyby był funkcją
terenu, bilans liczyłby jego pole podwójnie albo „wycinał” je z terenu
zabudowy, a kontrola nakładania się zgłaszałaby każdy budynek. Osobny
obiekt w tym samym GeoJSON nie wymaga zmiany bazy ani formatu zapisu,
a starsze koncepcje (bez budynków) liczą się jak dotąd. Wskaźniki z
budynków obok wskaźników z parametrów terenów — w następnym ETAPie.

**Odrzucone alternatywy:**
- Osobna tabela budynków w bazie — drugi zapis do zsynchronizowania z
  rysunkiem.
- Budynek jako „podteren” z hierarchią — komplikuje rysowanie w
  Leaflet.draw bez zysku na tym etapie.

## D-182 — Wskaźniki z budynków obok, nie zamiast wskaźników z terenów
Data: 2026-10-02

**Decyzja:** Gdy koncepcja ma budynki, wskaźniki z obrysów (rzut ×
kondygnacje) są pokazywane w osobnej kolumnie obok wskaźników z
parametrów terenów, a zgodność z planem jest sprawdzana dla obu.
Program osiedla i koszty liczą się dalej z terenów.

**Uzasadnienie:** Koncepcja zwykle zaczyna się od terenów z procentami
(szybki szkic), a budynki dochodzą tylko w części terenów — zastąpienie
jednych drugimi dawałoby skok wskaźników przy pierwszym narysowanym
budynku. Dwie kolumny pokazują, czy rysunek budynków dogonił założenia
terenów. PBC zostaje z terenów: obrys budynku nie mówi nic o zieleni.

**Odrzucone alternatywy:**
- Automatyczne przełączenie na budynki, gdy jest ich „dość” — próg
  arbitralny, wynik niejasny dla czytającego raport.
- Program (mieszkania) z powierzchni całkowitej budynków — w kolejnych
  ETAPach, gdy budynki dostaną funkcję.

## D-183 — Linia zabudowy: kontrola przecięcia, bez zgadywania strony
Data: 2026-10-02

**Decyzja:** Nieprzekraczalna linia zabudowy to łamana w rysunku
koncepcji. Warsztat zgłasza budynki, których obrys ją przecina, i podaje
odległość każdego budynku od linii; nie ocenia, po której stronie linii
budynek ma stać.

**Uzasadnienie:** Strona „dozwolona” zależy od rysunku planu (zwykle od
strony drogi), a linia narysowana w Warsztacie nie niesie tej informacji.
Zgadywanie (np. „strona z terenem KD”) dawałoby fałszywe ostrzeżenia przy
liniach wzdłuż zieleni czy granic działek. Przecięcie i odległość są
jednoznaczne, a położenie po złej stronie widać na rysunku.

**Odrzucone alternatywy:**
- Linia jako wielobok „pas zakazu zabudowy” — wymaga rysowania drugiej
  krawędzi; plan podaje linię, nie pas.
- Wskazanie strony strzałką przy linii — dodatkowy element interfejsu
  dla rzadkiego przypadku; do rozważenia, jeśli będzie potrzebne.

## D-184 — Punkty z Terenu na karcie działki przez trasę Terenu
Data: 2026-10-03

**Decyzja:** Karta działki pobiera punkty inwentaryzacji z POST
`/teren/okolica` (stały promień 100 m), tak jak ceny z `/ceny/okolica`
(D-117, D-123). Sekcja pojawia się tylko, gdy są punkty w zasięgu.

**Uzasadnienie:** Moduły zostają niezależne (osobne bazy), a karta łączy
to, co student ma o działce: przeznaczenie w planie, ceny w okolicy i
własne obserwacje z terenu. 100 m wystarcza na działkę i sąsiedztwo,
a dokładność GPS telefonu (kilka metrów) nie uzasadnia mniejszych
promieni na wydruku.

**Odrzucone alternatywy:**
- Wspólna funkcja „okolica” dla Cen i Terenu — dwa moduły z innymi
  danymi i zasadami (CLAUDE.md: bez abstrakcji dla dwóch modułów).
- Wybór projektu na karcie — karta ma być powtarzalna; projekt widać
  w kolumnie.

## D-185 — Gminy podobne liczone na danych typologii
Data: 2026-10-03

**Decyzja:** Podobieństwo gmin to odległość euklidesowa w przestrzeni
standaryzowanych wskaźników — tych samych, które wybrano do typologii
(`_dane` z ETAPu 124). Funkcja jest w `atlas/typologia.py`, a lista na
stronie typologii.

**Uzasadnienie:** Standaryzacja z typologii już wyrównuje jednostki
wskaźników; podobne gminy i typy opisują wtedy ten sam obraz. Wskaźnik
największej różnicy tłumaczy wynik słowami bez modelu językowego.

**Odrzucone alternatywy:**
- Podobieństwo w raporcie gminy z jego zestawem wskaźników — w kolejnym
  ETAPie planu (193) korzysta z tej funkcji.
- Odległość Mahalanobisa (uwzględnia korelacje wskaźników) — trudniejsza
  do wyjaśnienia na pierwszym roku; euklidesowa w z jest standardem.

## D-186 — Trend w gminach: ta sama metoda co prognoza, zmiana w % średniej
Data: 2026-10-03

**Decyzja:** Kartogram trendu używa `raport.prognoza_trendu` (najmniejsze
kwadraty, najwyżej 10 lat wstecz od końca okresu, min. 5 punktów, R² ≥ 0,7
— stabilny). Kolor to nachylenie w % średniej wartości gminy w okresie,
w stałych klasach ±0,5% i ±3% rocznie.

**Uzasadnienie:** Ta sama gmina ma wtedy ten sam trend na mapie i w
raporcie gminy. Nachylenie bezwzględne faworyzowałoby duże gminy (Kraków
„rośnie” najszybciej każdym wskaźnikiem liczonym w osobach); procent
średniej porównuje tempo. Stałe klasy pozwalają zestawiać mapy różnych
wskaźników i okresów.

**Odrzucone alternatywy:**
- Klasy z danych (kwantyle) — dzielą gminy po równo nawet wtedy, gdy
  wszystkie są „stabilne”, co sugeruje różnice, których nie ma.
- Ukrycie trendów niestabilnych na mapie — gubi informację; przypis i
  gwiazdka w tabeli wystarczą.

## D-187 — Test chi-kwadrat własną implementacją, tylko pytania jednokrotne
Data: 2026-10-03

**Decyzja:** Tabela krzyżowa obejmuje pytania jednokrotnego wyboru i
tak/nie. Wartość p liczy własna funkcja (`_p_chi2`, regularyzowana
funkcja gamma wg Numerical Recipes), sprawdzona testem z wartościami z
tablic chi-kwadrat; przy licznościach oczekiwanych < 5 raport ostrzega.

**Uzasadnienie:** Test chi-kwadrat zakłada, że każda osoba trafia do
jednej komórki — przy pytaniu wielokrotnego wyboru to nieprawda. Jedna
funkcja specjalna nie uzasadnia scipy jako zależności (D-047: własne
implementacje sprawdzone z referencją). Słowne opisy wyniku z progów
pomagają czytać tabelę bez znajomości statystyki, a zastrzeżenie „związek
to nie przyczyna” jest w Pomocy.

**Odrzucone alternatywy:**
- Dokładny test Fishera przy małych licznościach — przydatny głównie dla
  tabel 2×2; ostrzeżenie wystarcza na tym etapie.
- Pytania wielokrotne jako osobne kolumny tak/nie — do rozważenia przy
  wykresach ankiety (ETAP 180).

## D-188 — Wykres tabeli krzyżowej: słupki 100%, numery zamiast nazw w SVG
Data: 2026-10-03

**Decyzja:** Zależność dwóch pytań pokazujemy skumulowanymi słupkami 100%
(rozkład kolumn w każdym wierszu). SVG zawiera tylko numery wierszy,
procenty i kolory; nazwy odpowiedzi są w legendzie i liście HTML.

**Uzasadnienie:** Słupki 100% porównują grupy różnej liczności (ten sam
punkt odniesienia), czego nie dają liczby bezwzględne. Zasada „SVG tylko
z liczb i kolorów z kodu” chroni wydruk przed wstrzyknięciem
tekstu z formularza do SVG wstawianego przez `Markup` (jak mapa do
druku, D-048).

**Odrzucone alternatywy:**
- Słupki grupowane (obok siebie) — przy 4×4 odpowiedziach 16 słupków,
  trudno porównać udziały.
- Wykres w JS na stronie — raport jest stroną do druku, SVG z serwera
  drukuje się tak samo jak mapa.

## D-189 — Indeks cen liczony na serwerze, rok bazowy wspólny dla porównania
Data: 2026-10-03

**Decyzja:** Indeks to proste przeliczenie szeregu na rok bazowy = 100,
liczone w `ceny/analiza.py` (trasa z parametrem `bazowy`). Na stronie do
wyboru są tylko lata, w których dane mają wszystkie wybrane miasta; w
zestawieniu plików RCN rok bazowy to pierwszy wspólny rok median.

**Uzasadnienie:** Wykres cen w zł pokazuje poziom, ale „który rynek
drożeje szybciej” widać dopiero od wspólnego punktu startu. Liczby
liczy serwer jak wszystkie zmiany w module (D-111); wspólny rok bazowy
gwarantuje, że linie startują z tego samego miejsca.

**Odrzucone alternatywy:**
- Rok bazowy osobno dla każdego miasta (jego pierwszy rok) — linie
  startowałyby w różnych latach i porównanie by się rozjechało.
- Skala logarytmiczna cen — trudniejsza do czytania dla odbiorcy raportu.

## D-190 — Nietypowe transakcje: Tukey na logarytmie ilorazu do mediany roku
Data: 2026-10-03

**Decyzja:** Transakcja jest nietypowa, gdy logarytm ilorazu jej ceny za
m² do mediany roku leży poza Q1 − 1,5·IQR … Q3 + 1,5·IQR (z całego
filtrowanego zbioru). Warsztat tylko pokazuje listę; statystyki i mapy
liczą się dalej ze wszystkich transakcji (import odsiewa wyłącznie ceny
nierealne, D-112).

**Uzasadnienie:** Mediana roku usuwa wpływ wzrostu cen w czasie (inaczej
wszystkie stare transakcje byłyby „tanie”). Logarytm sprawia, że
dwukrotnie drożej i dwukrotnie taniej są tak samo daleko — rozkład cen
jest prawoskośny. Reguła Tukeya nie zakłada rozkładu normalnego i jest
znana ze statystyki opisowej. Decyzję, czy transakcję pominąć, zostawiamy
użytkownikowi — nietypowa nie znaczy błędna.

**Odrzucone alternatywy:**
- Automatyczne wykluczanie odstających ze statystyk — ukryta zmiana
  wyników; mediana i tak jest na nie odporna.
- Odchylenie od mediany w promieniu (lokalnie) — dokładniejsze, ale
  zależne od gęstości transakcji; do rozważenia w wycenie.

## D-191 — Izochrony z siatki H3: suma komórek, progi skumulowane
Data: 2026-10-03

**Decyzja:** Zasięg „do N minut” to suma heksagonów z czasem ≤ N
(`h3.cells_to_geo`), po jednym obiekcie na próg, od największego.
Progi jak klasy mapy (5/10/15/20/30 min).

**Uzasadnienie:** Moduł czyta gotowe wyniki na siatce H3 (D-034) —
kontur z komórek jest wierny danym, bez interpolacji, której wynik zależy
od metody. Zasięgi skumulowane (a nie pierścienie 5–10, 10–15) odpowiadają
pytaniu „co jest w zasięgu 15 minut” i nakładają się w QGIS bez dziur.

**Odrzucone alternatywy:**
- Wygładzanie konturów (bufor, alfa-kształt) — ładniej, ale pokazuje
  obszary, których dane nie obejmują.
- Pierścienie przedziałów — dostępne z heksagonów w zwykłym eksporcie
  (pole `klasa`).

## D-192 — Dzielnice w porównaniu: każdy scenariusz liczony osobno
Data: 2026-10-03

**Decyzja:** W porównaniu scenariuszy statystyki dzielnicy liczymy
osobno w pliku „przed” i „po” (komórki ze środkiem w wieloboku), a
zmiana to różnica tych statystyk. Nie łączymy komórek obu plików w pary.

**Uzasadnienie:** Pliki scenariuszy mogą mieć różny zasięg siatki;
statystyka dzielnicy z każdego pliku osobno odpowiada temu, co pokazuje
pojedynczy plik (ETAP 163), więc liczby się zgadzają. Średnia ważona
mieszkańcami z każdego scenariusza osobno uwzględnia też ewentualną zmianę
ludności (np. scenariusz z nowym osiedlem).

**Odrzucone alternatywy:**
- Średnia ze zmian w komórkach wspólnych (jak mapa porównania) — inne
  liczby niż w tabeli pojedynczego pliku, trudne do wyjaśnienia.

## D-193 — Zasłony obrazu: osobne fiszki, nakładka CSS zamiast przerabiania obrazu
Data: 2026-10-03

**Decyzja:** Każdy zasłonięty fragment to zwykła fiszka z tym samym
plikiem obrazu i jednym prostokątem w tabeli `zaslony_fiszek`
(współrzędne względne). Zasłonę rysuje nakładka CSS na obrazie; plik
obrazu się nie zmienia.

**Uzasadnienie:** Jak przy lukach (D-147) — powtórki Leitnera, tematy,
quiz i statystyki działają bez zmian, bo to zwykłe fiszki. Nakładka nie
wymaga biblioteki do obróbki obrazów (Pillow), pozwala odsłonić to samo
miejsce obrysem i współdzielić jeden plik między fiszkami (`usun_osierocone`
usuwa plik dopiero, gdy nie używa go żadna fiszka). Współrzędne względne
działają przy każdej szerokości ekranu i na wydruku.

**Odrzucone alternatywy:**
- Kopia obrazu z wypaloną zasłoną dla każdej fiszki — więcej plików,
  zależność od Pillow, brak obrysu po odsłonięciu.
- Kilka zasłon na jednej fiszce („zasłoń wszystkie, odsłoń jedną”) —
  wariant znany z Anki; do rozważenia, gdy pojedyncze zasłony się sprawdzą.

## D-194 — Krzywa zapominania z dziennika, bez dopasowania modelu
Data: 2026-10-03

**Decyzja:** Krzywa to udział zapamiętanych powtórek w przedziałach
odstępu od poprzedniej powtórki tej samej fiszki, liczony wprost z
`dziennik_powtorek`. Nie dopasowujemy wykładniczej krzywej Ebbinghausa
i nie zmieniamy na tej podstawie harmonogramu Leitnera.

**Uzasadnienie:** Surowe udziały są zrozumiałe bez statystyki i pokazują
studentowi jego pamięć; dopasowanie modelu przy kilkudziesięciu
powtórkach dawałoby pozornie dokładne parametry. Harmonogram zostaje
prosty i przewidywalny (D-012) — krzywa jest informacją, nie sterowaniem.
Powtórki tego samego dnia (po „nie umiem”) pomijamy, bo mierzą pamięć
krótkotrwałą.

**Odrzucone alternatywy:**
- Algorytm SM-2/FSRS dopasowujący odstępy do krzywej — zmiana systemu
  powtórek, poza zakresem ETAPu.

## D-195 — Moje przepisy: płaski zbiór jednostek, kolejność z aktów
Data: 2026-10-03

**Decyzja:** „Moje przepisy” to płaski zbiór jednostek (tabela
`moje_przepisy`), wyświetlany po aktach w kolejności tekstu każdego aktu.
Bez folderów, własnej kolejności i nazw zbiorów.

**Uzasadnienie:** Potrzeba to ściąga z artykułów potrzebnych na zajęcia —
kolejność ustawy jest naturalna i nie wymaga przeciągania. Jeden zbiór
wystarczy na początek; foldery to dodatkowy interfejs bez pewności, że
będą używane. Druk korzysta z tych samych stylów co druk aktu (ETAP 158).

**Odrzucone alternatywy:**
- Wiele nazwanych zbiorów (np. per przedmiot) — do rozważenia po
  użyciu; tabela łatwo dostanie kolumnę zbioru.
- Zakładki w przeglądarce (localStorage) — znikałyby przy kopii
  zapasowej i na innym komputerze.

## D-196 — ODS pisany ręcznie zamiast XLSX z biblioteką
Data: 2026-10-03

**Decyzja:** Arkusz zapisujemy w formacie OpenDocument (.ods) własnym
kodem w `dane/arkusz.py` (zipfile + XML), jak DXF (D-130). Bez
openpyxl/odfpy.

**Uzasadnienie:** ODS to otwarty standard, otwiera go LibreOffice (Linux
Mint) i Excel. Minimalny plik to trzy części ZIP, a potrzebne są tylko
komórki tekstowe i liczbowe, nagłówek i szerokości — nowa zależność dla
jednego formatu nie jest uzasadniona (CLAUDE.md). Liczby jako liczby
rozwiązują znany problem CSV: przecinek dziesiętny i kodowanie w Excelu.

**Odrzucone alternatywy:**
- XLSX przez openpyxl — popularniejszy format, ale zależność z
  zależnościami; Excel czyta ODS.
- Formatowanie liczb (miejsca po przecinku, separatory) w stylach ODS —
  zostawione arkuszowi; dane pozostają dokładne.

## D-197 — Jedna lista wierszy dla CSV i ODS w każdym module
Data: 2026-10-03

**Decyzja:** Każdy eksport ma jedną funkcję budującą wiersze tabeli
(`_wiersze_eksportu`, `_tabela_porownania`, `_wiersze_punktow`,
`arkusze_koncepcji`), a CSV i ODS różnią się tylko zapisem. Osiedle,
które nie miało CSV, dostało od razu arkusz z zakładkami.

**Uzasadnienie:** Ten sam eksport w dwóch formatach nie może się
rozjechać — wspólna lista wierszy to gwarantuje. Funkcje są w modułach
(nie jedna wspólna „eksportująca”), bo tabele są różne (CLAUDE.md: bez
uniwersalnych abstrakcji); wspólny jest tylko format w `dane/arkusz.py`.

**Odrzucone alternatywy:**
- Zastąpienie CSV przez ODS — CSV czytają QGIS, R i Python bez
  dodatkowych bibliotek; zostaje.

## D-198 — Pozycja planu zrobiona wcześniej zostaje zastąpiona, nie przesunięta
Data: 2026-10-03

**Decyzja:** Gdy ETAP planu okazuje się już zrobiony w ramach innego
ETAPu (tu 217 w 176), w planie zostaje przekreślony z odnośnikiem, a w
jego miejsce wchodzi pokrewna, mała funkcja tego samego modułu. Numeracja
ETAPów się nie przesuwa.

**Uzasadnienie:** Stała numeracja pozwala odnosić się do ETAPów w
DECISIONS i PROGRESS bez przeliczania; przekreślenie zostawia ślad,
dlaczego plan się zmienił (D-178).

**Odrzucone alternatywy:**
- Przenumerowanie dalszych ETAPów — psuje odnośniki w dokumentacji.

## D-199 — Lista działek: do 30 naraz, po kolei, bez historii
Data: 2026-10-03

**Decyzja:** Hurtowe sprawdzenie obejmuje najwyżej 30 działek w jednym
zapytaniu, a działki są sprawdzane kolejno (bez równoległych zapytań).
Wyniki nie trafiają do historii sprawdzonych działek.

**Uzasadnienie:** ULDK, WFS gmin i KIMPZP to bezpłatne usługi publiczne —
masowe, równoległe pobieranie byłoby nadużyciem (CLAUDE.md: tylko API i
WFS, z umiarem). 30 działek wystarcza na typową listę z ogłoszenia
przetargu czy ćwiczenia. Historia służy do powrotu do oglądanych działek;
lista z arkusza by ją zalała.

**Odrzucone alternatywy:**
- Wczytywanie pliku CSV — wklejenie kolumny z arkusza robi to samo bez
  obsługi formatów; plik można dodać, jeśli będzie potrzebny.
- Udziały przeznaczeń dla każdej działki — kolejne zapytanie WFS na
  działkę; zostaje na karcie działki.

## D-200 — Arkusz listy działek liczony ponownie na serwerze
Data: 2026-10-03

**Decyzja:** „Arkusz ODS” wysyła tę samą listę wpisów, a serwer sprawdza
działki jeszcze raz i zapisuje wynik. Nie przyjmujemy wyników z
przeglądarki (np. ukrytego pola z tabelą).

**Uzasadnienie:** Liczby i symbole w pliku mają pochodzić z usług, nie z
treści formularza (CLAUDE.md: liczby z danych). Lista ma najwyżej 30
działek, więc ponowne zapytania są do przyjęcia; zapamiętywanie wyników na
serwerze wymagałoby nowej tabeli i sprzątania.

**Odrzucone alternatywy:**
- Pamięć podręczna wyników listy — oszczędza zapytania, ale dokłada stan
  bez wyraźnej potrzeby.

## D-201 — Podobne gminy w raporcie z zestawu raportu, w jednym roku
Data: 2026-10-03

**Decyzja:** W raporcie gminy podobieństwo liczy się z tego samego
zestawu wskaźników co tabela raportu, w jednym roku — najnowszym, w
którym badana gmina ma wszystkie wskaźniki.

**Uzasadnienie:** Czytelnik raportu widzi te same wskaźniki w tabeli i w
podobieństwie, więc wynik da się wyjaśnić. Jeden rok dla wszystkich
wskaźników jest warunkiem standaryzacji (porównujemy gminy w tym samym
czasie); najnowszy wspólny rok to kompromis między aktualnością a
kompletnością.

**Odrzucone alternatywy:**
- Każdy wskaźnik z jego ostatniego roku — mieszałoby lata w jednym
  profilu gminy.

## D-202 — Stabilność rankingu: miejsca wśród gmin wspólnych, rho skrajnych lat
Data: 2026-10-03

**Decyzja:** Wskaźnik złożony liczy się osobno dla każdego roku (własna
normalizacja w roku), a miejsca porównujemy tylko wśród gmin z danymi we
wszystkich latach. Zgodność to rho Spearmana między pierwszym a ostatnim
rokiem.

**Uzasadnienie:** Ranking odpowiada pytaniu „która gmina jest wyżej w
danym roku” — normalizacja w roku zachowuje sens wskaźnika złożonego
(ETAP 84). Gminy, którym brakuje danych w części lat, zmieniałyby liczbę
miejsc i fałszowały awanse. Rho na rangach to standardowa miara zgodności
dwóch rankingów, znana z korelacji w Atlasie (ETAP 25).

**Odrzucone alternatywy:**
- Normalizacja na danych ze wszystkich lat naraz — pokazuje zmianę
  poziomu, nie pozycji; to inny wskaźnik (do rozważenia jako dynamika).

## D-203 — Cień od budynków, gdy są narysowane; tereny jako zapas
Data: 2026-10-03

**Decyzja:** Analiza „Odległości i cień” bierze budynki jako źródło cienia,
gdy koncepcja ma choć jeden budynek; w przeciwnym razie zostaje
najgorszy przypadek od całych terenów zabudowy. Nie mieszamy obu źródeł.

**Uzasadnienie:** Obrys budynku z kondygnacjami jest bliższy rzeczywistości
niż teren zakładający budynek przy samej krawędzi. Mieszanie (część
terenów z budynkami, część bez) dawałoby strefę trudną do odczytania;
reguła „są budynki — liczą się budynki” jest prosta do wyjaśnienia w
opisie nad tabelą.

**Odrzucone alternatywy:**
- Obie strefy naraz na mapie — dwie nakładające się strefy cienia są
  nieczytelne na małym ekranie.
- Przełącznik źródła w interfejsie — dodatkowa decyzja dla użytkownika
  bez wyraźnej korzyści; tereny bez budynków nadal działają.

## D-204 — Etapy realizacji liczone osobno, grunt poza etapami
Data: 2026-10-03

**Decyzja:** Etap jest właściwością terenu (liczba 1–10). Każdy etap
liczymy tymi samymi funkcjami co całą koncepcję (`program`, `koszty`),
tylko na jego terenach. Miejsca postojowe muszą się zmieścić w tym samym
etapie; koszt gruntu nie jest dzielony.

**Uzasadnienie:** Ponowne użycie `program.py` i `koszty.py` daje liczby
spójne z całością bez drugiej implementacji. Osobny bilans parkingów
odpowiada pytaniu, które etapowanie stawia: czy oddany etap działa sam,
zanim powstanie następny. Grunt kupuje się zwykle naraz, a podział
proporcjonalny do powierzchni byłby założeniem, którego autor nie wpisał.

**Odrzucone alternatywy:**
- Etap jako osobny wielobok na mapie (teren należy do etapu, w którym
  leży) — kolejny rodzaj obiektu do rysowania, a tereny na granicy
  etapów wymagałyby cięcia.
- Parking narastająco (KS z wcześniejszych etapów obsługuje późniejsze) —
  ukrywa braki w pierwszym etapie, który jest najważniejszy.
- Grunt proporcjonalnie do powierzchni etapu — liczba wynikająca z
  założenia kodu, nie z danych autora.

## D-205 — Chłonność z ustaleń już wpisanych w koncepcji
Data: 2026-10-03

**Decyzja:** Chłonność liczymy wyłącznie z ustaleń planu, które autor
wpisał do zgodności (max intensywność; max wskaźnik zabudowy razem z max
kondygnacjami), od tej samej podstawy co wskaźniki. Gdy ograniczeń jest
kilka, decyduje najmniejsza wartość; zapas w mieszkaniach przeliczamy
przez średnie mieszkanie MW z założeń programu.

**Uzasadnienie:** Jedno źródło ustaleń (pola „Plan”) — bez drugiego
formularza i bez rozbieżności między zgodnością a chłonnością. Najmniejsza
wartość to faktyczne ograniczenie. Mieszkania MW dają górny szacunek
(najmniejszy metraż), opisany wprost jako szacunek.

**Odrzucone alternatywy:**
- Chłonność z ustaleń pobranych z MPZP dla działek pod obszarem — plany
  różnie zapisują wskaźniki (tekst uchwały), a moduł MPZP nie zwraca ich
  liczbowo dla każdego planu.
- Mieszkania wg proporcji MN/MW z koncepcji — zapas nie ma jeszcze
  funkcji; przyjęcie proporcji byłoby założeniem kodu.

## D-206 — Trasa obchodu: heurystyka w linii prostej, GPX bez zależności
Data: 2026-10-03

**Decyzja:** Kolejność punktów liczymy w Pythonie heurystyką „najbliższy
sąsiad + 2-opt” na odległościach po kuli; trasę zapisujemy jako GPX 1.1
składany ręcznie (jak DXF i ODS). Punkty trasy = punkty widoczne na mapie
po filtrze legendy.

**Uzasadnienie:** Dla kilkudziesięciu punktów 2-opt daje trasę bliską
optimum w ułamku sekundy, bez bibliotek. GPX czytają aplikacje
nawigacyjne na telefonie, także offline — formularz na telefon (ETAP 65)
nie musi dostawać własnej nawigacji. Filtr legendy jest już znanym
sposobem wyboru punktów.

**Odrzucone alternatywy:**
- Trasa po sieci ulic (OSRM, GraphHopper) — zewnętrzna usługa routingu
  albo duży graf lokalnie; długość w linii prostej jest opisana jako
  dolne oszacowanie.
- Dokładne rozwiązanie komiwojażera (np. OR-Tools) — nowa, ciężka
  zależność dla zysku rzędu kilku procent długości.
- Biblioteka gpxpy — kilkanaście wierszy XML nie uzasadnia zależności.

## D-207 — Punkty do sprawdzenia wpisane w plik formularza; ✓ w localStorage
Data: 2026-10-03

**Decyzja:** Punkty do ponownej wizyty trafiają do samodzielnego pliku
formularza jako JSON (położenie, numer trasy, krótki opis), wybrane przez
trasę obchodu. Oznaczenie „sprawdzony” trzyma telefon w localStorage;
nie jest eksportowane.

**Uzasadnienie:** Telefon nie łączy się z Warsztatem (D-071), więc dane
muszą być w pliku — tak jak podkład mapy. Trasa daje sensowną kolejność
i wybór punktów filtrem legendy. ✓ to pomoc w terenie, nie wynik
inwentaryzacji: wynikiem jest nowy punkt, porównywalny z poprzednim
(porównanie projektów, ETAP 157).

**Odrzucone alternatywy:**
- Nowy magazyn w IndexedDB na stan sprawdzenia — zmiana wersji bazy
  formularzy już używanych na telefonach dla danych pomocniczych.
- Powiązanie nowego punktu ze starym (identyfikator w pliku eksportu) —
  zmiana formatu pliku i importu; porównanie projektów paruje punkty po
  odległości bez tego.
- Pełne dane starych punktów w formularzu (zdjęcia) — plik urósłby o
  megabajty; opis i położenie wystarczą do odnalezienia miejsca.

## D-208 — Plan 201–250 bez zmian po półmetku
Data: 2026-10-03

**Decyzja:** Po przeglądzie w ETAPie 200 plan 201–250 zostaje bez zmian;
kolejne ETAPy idą w zapisanej kolejności, a pozycje wymagające nowych
usług (API Sejmu: nowszy tekst jednolity, akty powiązane) najpierw
sprawdzają, co API rzeczywiście zwraca.

**Uzasadnienie:** Żadna pozycja nie okazała się zrobiona wcześniej ani
zbędna; przegląd nie wykazał długu, który trzeba spłacić przed dalszymi
funkcjami (pokrycie 95%, brak ostrzeżeń, strony bez problemów).
Zasada „nie zgaduj” dotyczy też usług — pola odpowiedzi API sprawdzamy
w dokumentacji i na żywym zapytaniu przed napisaniem kodu.

**Odrzucone alternatywy:**
- Przesunięcie podziału `osiedle.js` (ETAP 245) na teraz — plik ma ok.
  1 000 wierszy, ale jest uporządkowany sekcjami; podział zaplanowano po
  funkcjach Osiedla z serii 231–240, żeby dzielić raz.

## D-209 — Korekta na datę z median roku w całym pliku, jako drugi wynik
Data: 2026-10-03

**Decyzja:** Wycena porównawcza pokazuje obok wyniku bez korekt drugi
wynik: ceny za m² podobnych transakcji przeliczone na ostatni rok pliku
współczynnikiem mediana(rok bazowy) / mediana(rok transakcji). Mediany
liczymy z całego pliku przy tych samych filtrach; rok z mniej niż 10
transakcjami nie dostaje współczynnika, a jego transakcje są pomijane w
wyniku po korekcie (z informacją ile).

**Uzasadnienie:** Korekta na czas to podstawowa poprawka w podejściu
porównawczym — transakcja sprzed czterech lat bez niej zaniża wycenę przy
rosnącym rynku. Mediana z całego pliku (powiatu) jest stabilniejsza niż z
kilku transakcji w promieniu. Wynik bez korekty zostaje, bo korekta
zależy od założenia (rynek okolicy zmienia się jak rynek powiatu), które
użytkownik powinien widzieć i móc pominąć.

**Odrzucone alternatywy:**
- Indeks z GUS BDL (ceny 1 m² w powiecie) — tylko lokale, z opóźnieniem
  publikacji i w innym podziale; dla działek brak.
- Trend liniowy z regresji (ETAP 156) — zakłada stałe tempo, a ceny
  rosną i spadają skokowo; mediana roku tego nie zakłada.
- Korekta zawsze włączona, bez wyniku surowego — ukrywa założenie.

## D-210 — Wycena zapisana jako parametry plus wynik z dnia zapisu
Data: 2026-10-03

**Decyzja:** Zapisujemy parametry wyceny (zapytanie URL z listy znanych
pól) i kilka liczb wyniku z dnia zapisu. Karta liczy wycenę od nowa i
pokazuje zapisany wynik obok.

**Uzasadnienie:** Parametry pozwalają odtworzyć wycenę na nowszych
danych (ponowny import pliku zachowuje jego id, jak przy obszarach), a
zapisany wynik pokazuje, ile się zmieniło. Lista dozwolonych pól sprawia,
że do bazy nie trafiają przypadkowe parametry z adresu.

**Odrzucone alternatywy:**
- Zapis pełnej listy transakcji wyniku — kopia danych pliku, która
  rozjeżdża się z nim po imporcie.
- Zapis w pamięci przeglądarki — znika przy czyszczeniu danych i nie
  trafia do kopii zapasowej.

## D-211 — Premia w latach z tej samej funkcji co premia w obszarach
Data: 2026-10-03

**Decyzja:** Premię rynku pierwotnego w każdym roku liczymy funkcją
`_rynki` z ETAPu 135 (mediany osobno, próg 5 transakcji na rynku), bez
nowej metody. Rok bez progu pokazuje „za mało danych”.

**Uzasadnienie:** Ta sama definicja w obszarach i w latach — liczby da
się porównać, a opis ograniczeń (różnica median, nie ten sam lokal) jest
jeden. Próg chroni przed premią z dwóch transakcji.

**Odrzucone alternatywy:**
- Premia z regresji (ETAP 156) w każdym roku — model z kilkoma cechami
  na rok wymaga dużo więcej transakcji, a wynik trudniej wyjaśnić.
- Premia w kwartałach — za mało transakcji pierwotnych w kwartale w
  typowym powiecie.

## D-212 — Grupy mieszkańców rozpoznawane po prefiksie nazwy kolumny
Data: 2026-10-03

**Decyzja:** Kolumny zaczynające się od `ludnosc_`, `mieszkancy_` albo
`wiek_` są wagami (liczbą osób w grupie), jak kolumna `ludnosc` z ETAPu
21 — nie trafiają na listę wskaźników. Dla każdej grupy liczymy udział w
zasięgu progów i medianę czasu ważoną liczbą osób.

**Uzasadnienie:** Format pliku zostaje prostym CSV bez osobnego pliku
opisu; prefiks jest czytelny w QGIS i w arkuszu. Mediana ważona mówi,
w jakim czasie dociera połowa seniorów albo dzieci — porównywalne między
grupami bez zakładania progu.

**Odrzucone alternatywy:**
- Wybór kolumn grup w interfejsie po wgraniu — dodatkowy krok przy
  każdym pliku i stan do zapamiętania.
- Grupy z GUS (BDL) dla obszaru — dane gminne, nie na siatce H3; podział
  na komórki byłby założeniem.

## D-213 — Raport dzielnic: obszary z przeglądarki, mapa bez nazw
Data: 2026-10-03

**Decyzja:** Raport dzielnic jest stroną, której skrypt czyta obszary z
localStorage (jak karta Dzielnice, D-171) i prosi serwer POST-em o tabelę
i mapę SVG. Na mapie są tylko kontury i numery; nazwy obszarów — w
tabeli HTML.

**Uzasadnienie:** Obszary nie są zapisywane na serwerze (ETAP 163), więc
zwykły link GET by ich nie przeniósł. SVG z serwera tylko z liczb i
kolorów (D-048) — nazwa wpisana przez użytkownika nie trafia do pliku
SVG; mapa jako obraz z Bloba nie wstawia znaczników do strony.

**Odrzucone alternatywy:**
- Zapis obszarów w bazie modułu — zmiana modelu danych z ETAPu 163 dla
  jednego raportu; obszary są własnością przeglądarki i pliku.
- Obszary w adresie strony — geometria kilku wieloboków przekracza
  rozsądną długość URL.

## D-214 — Przeplatanie: zachłanne, w ramach kolejki dnia, na serwerze
Data: 2026-10-03

**Decyzja:** Przeplatanie zmienia tylko kolejność fiszek, które i tak są
do powtórki — nie dokłada nowych ani nie zmienia harmonogramu. Układa je
serwer zachłannie: następna fiszka z innej grupy niż poprzednia, z grupy,
w której zostało najwięcej; w grupie zostaje kolejność od niższych
pudełek.

**Uzasadnienie:** Przeplatanie (interleaving) pomaga rozróżniać podobne
pojęcia z różnych działów; zachowanie kolejności pudełek w grupie nie
psuje zasady „najpierw słabiej znane”. Wybór grupy z największą resztą
nie zostawia jednego tematu blokiem na końcu. Funkcja w Pythonie jest
testowana jak reszta systemu Leitnera.

**Odrzucone alternatywy:**
- Losowe tasowanie — może dać kilka kart tego samego tematu z rzędu i
  gubi kolejność pudełek.
- Przeplatanie w JavaScripcie — druga implementacja do utrzymania (także
  w formularzu na telefon), bez testów pytest.

## D-215 — Wyjaśnienie z Gemini tylko z fragmentu źródła, zapisane przy fiszce
Data: 2026-10-03

**Decyzja:** Model dostaje pytanie, odpowiedź i fragment PDF-a, z którego
powstała fiszka (kotwica w źródle), i ma wyjaśnić odpowiedź tylko na ich
podstawie. Wynik z liczbą spoza tych tekstów jest odrzucany
(`sprawdz_liczby`, jak w Atlasie). Wyjaśnienie zapisujemy przy fiszce —
generowane raz, nie przy każdej powtórce; użytkownik może je zastąpić
własnym.

**Uzasadnienie:** Zasada „model tłumaczy, nie dodaje faktów” — fragment
źródła jest jedyną wiedzą, jaką dostaje. Zapis oszczędza zapytania i
pozwala poprawić tekst. Własne wyjaśnienie (skojarzenie) działa bez
klucza API.

**Odrzucone alternatywy:**
- Wyjaśnienie z wiedzy ogólnej modelu — nie da się sprawdzić w źródle.
- Generowanie przy każdym odsłonięciu — koszt, opóźnienie i za każdym
  razem inny tekst.

## D-216 — Notatki na nowy tekst: dopasowanie po oznaczeniu, raport zamiast zgadywania
Data: 2026-10-03

**Decyzja:** Notatki i „Moje przepisy” przenosimy na jednostkę nowego
aktu o tym samym oznaczeniu („Art. 15”, „§ 4”). Gdy oznaczenia nie ma
albo występuje kilka razy, nie przenosimy, tylko wypisujemy je w
raporcie; zmieniony tekst artykułu też jest w raporcie. Istniejącej
notatki nie nadpisujemy — stara jest dopisywana pod nią.

**Uzasadnienie:** Numeracja artykułów w tekście jednolitym jest stała
(uchylone zostają jako „uchylony”, nowe dostają litery), więc oznaczenie
jest pewnym kluczem. Dopasowanie po podobieństwie treści mogłoby
przypiąć notatkę do innego przepisu bez wiedzy użytkownika. Nic nie
ginie: stary akt zostaje bez zmian.

**Odrzucone alternatywy:**
- Dopasowanie po podobieństwie tekstu — ryzyko cichej pomyłki przy
  przepisach o podobnej treści.
- Automatyczne przeniesienie przy pobraniu — użytkownik może chcieć
  zachować notatki osobno; karta z wybranym źródłem to jeden klik.

## D-217 — Notatki jako Markdown, nie TXT ani DOCX
Data: 2026-10-03

**Decyzja:** Eksport notatek to plik Markdown: czytelny jako zwykły tekst,
a w edytorach Markdown (np. Obsidian, Typora) — jako dokument z
nagłówkami i cytatami. Pisany ręcznie, bez
biblioteki.

**Uzasadnienie:** Plan mówi „plik tekstowy” — Markdown nim jest, a
struktura (nagłówek artykułu, cytat przepisu, notatka) zostaje widoczna.
Student może dalej pracować na notatkach w swoim narzędziu; wydruk z
notatkami jest od ETAPu 158.

**Odrzucone alternatywy:**
- Czysty TXT — gubi rozróżnienie tekstu przepisu i notatki.
- DOCX — nowa zależność (python-docx) albo ręczne składanie ZIP-a z XML
  dla formatu, który i tak jest edytowany w innym programie.

## D-218 — W dokumentacji tylko sprawdzone twierdzenia o programach zewnętrznych
Data: 2026-10-03

**Decyzja:** Opisy w Pomocy i DECISIONS nie obiecują, jak zachowa się
program spoza Warsztatu (np. czy Word otworzy plik .md), jeśli nie jest
to sprawdzone. Piszemy o formacie i narzędziach, które go na pewno
czytają (Notatnik, edytory Markdown).

**Uzasadnienie:** Zasada „nie zgaduj” dotyczy też dokumentacji —
błędna obietnica w Pomocy kosztuje użytkownika czas tak samo jak błąd w
kodzie. Przegląd ETAPu 210 znalazł takie zdanie w ETAPie 209.

**Odrzucone alternatywy:**
- Zostawić ogólnik „otworzysz w Wordzie” — nie da się go potwierdzić
  dla każdej wersji programu.

## D-219 — Przypięte jako lista adresów w instance/, nie w bazach modułów
Data: 2026-10-03

**Decyzja:** Przypięte rzeczy to lista adresów stron aplikacji z tytułem
i nazwą modułu, w pliku JSON w `instance/` (jak `widziana_wersja.txt`
z ETAPu 159). Przypina się je z „Wróć do pracy”; moduły nic o nich nie
wiedzą.

**Uzasadnienie:** Przypięcie dotyczy strony głównej, nie danych modułu —
osobna tabela w ośmiu bazach byłaby wspólną abstrakcją wbrew CLAUDE.md.
Adres strony działa dla każdego modułu bez zmian w nim; plik w
`instance/` trafia do kopii zapasowej. Tylko adresy zaczynające się od
„/” — przypięcie nie może prowadzić poza aplikację.

**Odrzucone alternatywy:**
- localStorage przeglądarki — nie trafia do kopii i znika przy
  czyszczeniu danych przeglądarki.
- Przycisk „przypnij” na każdej stronie modułu — zmiany w ośmiu
  modułach; „Wróć do pracy” ma już wszystko, co trzeba przypiąć.
- Gdy przypięty obiekt zostanie usunięty, link prowadzi do strony
  błędu — akceptowalne, ✕ usuwa go z listy.

## D-220 — Kosz: migawka w Fiszkach, znacznik usunięcia w Osiedlu i Terenie
Data: 2026-10-03

**Decyzja:** Każdy moduł ma własny kosz (bez wspólnej abstrakcji).
Osiedle i Teren dostają kolumnę `usunieto` na głównym obiekcie — kilka
zapytań filtruje usunięte, a przywrócenie czyści datę; pliki zostają do
usunięcia na dobre. Fiszki zapisują migawkę: wiersze wszystkich tabel
powiązanych z PDF-em albo fiszką jako JSON i pliki w folderze kosza, po
czym usuwają jak dotąd; przywrócenie wstawia te same wiersze.

**Uzasadnienie:** W Fiszkach z fiszkami pracuje ponad dwadzieścia
zapytań (powtórki, quiz, statystyki, egzaminy, telefon, wyszukiwarka) —
znacznik usunięcia trzeba by dopisać w każdym, a jeden pominięty pokazałby
usunięte fiszki w powtórce. Migawka nie zmienia żadnego z nich. Test
pilnuje, żeby nowa tabela z `fiszka_id` albo `pdf_id` trafiła na listę.
W Osiedlu i Terenie zapytań jest kilka, więc znacznik jest prostszy i
zachowuje pliki bez przenoszenia.

**Odrzucone alternatywy:**
- Jedna tabela kosza dla wszystkich modułów — wspólna abstrakcja wbrew
  CLAUDE.md; bazy modułów są osobne.
- Kosz bez limitu czasu — dane usunięte celowo powinny kiedyś zniknąć;
  30 dni wystarcza na zauważenie pomyłki, a kopia zapasowa sięga dalej.

## D-221 — GeoPackage ze stylami zamiast pliku projektu .qgs
Data: 2026-10-03

**Decyzja:** Zamiast projektu QGIS (.qgs) zapisujemy jeden plik
GeoPackage: warstwy w PL-1992 i style QML w tabeli `layer_styles`
(oznaczone jako domyślne). Plik składamy przez sqlite3, bez GDAL-a.

**Uzasadnienie:** Projekt .qgs odwołuje się do osobnych plików danych
ścieżkami i ma rozbudowany, wersjonowany format — ręcznie pisany łatwo
psuje się po cichu, a w tym środowisku nie ma QGIS-a, żeby go sprawdzić.
GeoPackage to standard OGC: jeden plik z danymi i stylem, czytany przez
QGIS, ArcGIS i GDAL; jego poprawność sprawdziliśmy GDAL-em. Style w
`layer_styles` to mechanizm QGIS-a; gdyby się nie wczytały, warstwy i
atrybuty i tak są w pliku (Pomoc mówi, jak wybrać styl z bazy).

**Odrzucone alternatywy:**
- Plik .qgs z GeoJSON-em w ZIP-ie — dwa pliki i ścieżki względne; bez
  QGIS-a nie da się sprawdzić, czy projekt się otwiera.
- GDAL/fiona jako zależność — duża biblioteka binarna dla zapisu, który
  sqlite3 robi w kilkudziesięciu wierszach (jak DXF i ODS).

## D-222 — Klocki stylów QML w dane/geopaczka.py
Data: 2026-10-03

**Decyzja:** Funkcje budujące styl QML (symbol, kategorie, przedziały)
są w `dane/geopaczka.py` obok zapisu GeoPackage; każdy moduł sam wybiera
kolumny, kolory i klasy (Osiedle — funkcje terenu, Teren — pole wyboru,
Ceny — kwintyle ceny).

**Uzasadnienie:** Trzy moduły piszą ten sam format stylu — to kod
formatu, jak `dane/arkusz.py` dla ODS, a nie wspólna abstrakcja
modułów. Decyzje „co i jakim kolorem” zostają w modułach, z tymi samymi
źródłami kolorów co ich mapy (FUNKCJE, kolory_pola, KOLORY_KLAS).

**Odrzucone alternatywy:**
- Osobny XML stylu w każdym module — trzy kopie tych samych znaczników
  QML, łatwo o rozjazd przy poprawce.
- Szablony Jinja dla QML — styl to dane, nie strona; f-stringi z
  `quoteattr` są krótsze i testowane jako poprawny XML.

## D-223 — Granice powiatów z połączenia gmin, nie z osobnej warstwy PRG
Data: 2026-10-03

**Decyzja:** Granice powiatów liczymy, łącząc gminy z tej samej warstwy
PRG, z której Atlas bierze kartogram gmin (A03); powiat = gminy o
wspólnych czterech pierwszych cyfrach TERYT.

**Uzasadnienie:** Nazwy warstwy powiatów i jej pól w usłudze PRG nie dało
się sprawdzić (usługa niedostępna w środowisku pracy), a zasada „nie
zgaduj” wyklucza wpisanie jej z pamięci. Połączenie gmin daje granice
zgodne z kartogramem gmin co do metra i nie wymaga drugiego pobrania.
Szczeliny po osobnym uproszczeniu sąsiednich gmin domykamy buforem
±0,0002° (ok. 15–20 m) — poniżej rozdzielczości mapy województwa.

**Odrzucone alternatywy:**
- Warstwa powiatów z PRG — niesprawdzona nazwa; do rozważenia, gdy
  będzie można potwierdzić usługę.
- Osobny moduł / strona dla powiatów — ten sam interfejs Atlasu działa,
  gdy dane mają ten sam kształt (lista jednostek z TERYT i wartością).

## D-224 — Powiaty w tym samym interfejsie Atlasu, funkcje gminne ukryte
Data: 2026-10-03

**Decyzja:** Tryb powiatów korzysta z tych samych tras i widoków co
gminy (parametr `poziom`, dane w tym samym kształcie). Funkcje z natury
gminne — profil i raport gminy, „Gminy w czasie”, trend w gminach —
w trybie powiatów są ukryte, a nie przerabiane.

**Uzasadnienie:** Analizy (klasy, LQ, Moran, korelacja, druk) działają
na liście jednostek z TERYT i wartością, bez względu na ich rodzaj —
jeden parametr daje cały Atlas dla powiatów. Raport gminy i porównanie
gmin w czasie mają treść i źródła dla gmin; ich wersje powiatowe to
osobne funkcje, nie przełącznik. Wartości powiatów bierzemy z GUS dla
powiatów (nie sumujemy gmin), bo wskaźniki względne i średnie nie są
sumowalne.

**Odrzucone alternatywy:**
- Osobna strona „Atlas powiatów” — powielenie interfejsu i tras.
- Wartości powiatów jako suma gmin — błędne dla wskaźników względnych.

## D-225 — Moje działki w ODS z tych samych danych co zestawienie do druku
Data: 2026-10-03

**Decyzja:** Arkusz „Moje działki” powstaje z tej samej funkcji co
zestawienie do druku (`zestawienie.wiersze` — numery, opis symbolu,
PL-2000) i ma te same dwie części: listę i podsumowanie według
przeznaczenia. Liczby (powierzchnia, współrzędne) zapisujemy jako liczby.

**Uzasadnienie:** Ten sam numer działki na wydruku i w arkuszu ułatwia
pracę z jednym i drugim; arkusz z liczbami pozwala od razu sumować i
filtrować bez zamiany przecinków jak w CSV.

**Odrzucone alternatywy:**
- Rozszerzenie CSV o kolumny PL-2000 — CSV i tak zostaje dla prostych
  zastosowań; dwie zakładki wymagają formatu arkusza.

## D-226 — Zestaw założeń kopiowany do koncepcji, nie łączony
Data: 2026-10-03

**Decyzja:** Zastosowanie zestawu wpisuje jego wartości do założeń
koncepcji (jak ręczne wpisanie). Koncepcja nie pamięta, z którego zestawu
pochodzą; zmiana albo usunięcie zestawu nie zmienia zapisanych koncepcji.

**Uzasadnienie:** Koncepcja ma dawać ten sam wynik po roku — także gdy
zestaw (np. normatywy gminy) zostanie poprawiony dla nowych prac. Kopia
jest jawna: wartości widać w polach i w raporcie („Przyjęte założenia”).

**Odrzucone alternatywy:**
- Odwołanie do zestawu (koncepcja zmienia się razem z nim) — wyniki
  starych wariantów zmieniałyby się po cichu.
- Zestawy w pliku poza bazą — trudniej o walidację i kopię zapasową;
  baza modułu jest w kopii.

## D-227 — Kierunek zdjęcia wybierany ręcznie z ośmiu stron świata
Data: 2026-10-03

**Decyzja:** Kierunek patrzenia aparatu użytkownik wybiera z listy ośmiu
stron świata (zapis w stopniach: 0, 45 … 315). Formularz nie odczytuje
kompasu telefonu ani metadanych EXIF zdjęcia.

**Uzasadnienie:** Formularz jest plikiem HTML otwieranym bez serwera;
dostęp do czujnika orientacji różni się między przeglądarkami (na części
wymaga osobnego pozwolenia) i nie da się go tu sprawdzić na prawdziwych
telefonach. Zdjęcie jest zmniejszane na płótnie, więc EXIF i tak znika.
Dokładność ośmiu kierunków wystarcza do opisu dokumentacji fotograficznej
(„widok na NE”); wartość jest jawna i poprawialna w Warsztacie.

**Odrzucone alternatywy:**
- Odczyt kompasu (DeviceOrientation) — niesprawdzalne tutaj, zależne od
  przeglądarki i kalibracji; może wrócić po testach na telefonach.
- Dowolne stopnie wpisywane ręcznie — fałszywa precyzja przy ocenie „na
  oko”, wolniejsze w terenie.

## D-228 — CSV tylko ze współrzędnymi w stopniach, kolumny po nazwie
Data: 2026-10-03

**Decyzja:** Import CSV przyjmuje współrzędne WGS84 w stopniach z kolumn o
ustalonych nazwach (lat/lng, szerokosc/dlugosc i kilka wariantów).
Separator wybierany jako najczęstszy z ; , tab w nagłówku. Nieczytelny
UTF-8 → Windows-1250. Bez okna przypisywania kolumn.

**Uzasadnienie:** Arkusz to najprostsza droga od notatek do mapy; reguły
nazw są te same co w GeoJSON (ETAP 133), więc jedno miejsce w Pomocy
opisuje oba importy. Układy PL-1992/PL-2000 w CSV mają kolumny x/y o
odwróconym znaczeniu i łatwo o pomyłkę — takie dane łatwiej przeliczyć w
QGIS do EPSG:4326 i wczytać jako GeoJSON. Współrzędne spoza zakresu stopni dają jasny błąd z numerem
wiersza zamiast punktów w złym miejscu.

**Odrzucone alternatywy:**
- Okno przypisywania kolumn do pól — dodatkowy ekran dla rzadkiego
  przypadku; zmiana nazwy kolumny w arkuszu jest prostsza.
- `csv.Sniffer` — zgaduje także inne znaki i myli się na krótkich
  plikach; trzy dozwolone separatory wystarczą.

## D-229 — Zasięg pliku z 95% transakcji najbliższych środka
Data: 2026-10-03

**Decyzja:** Na mapie zestawienia zasięg pliku to otoczka wypukła 95%
transakcji najbliższych środka (mediana długości i szerokości), a numer
stoi w tym środku. Pozostałe 5% nie jest rysowane i nie wpływa na kadr.

**Uzasadnienie:** W plikach RCN zdarzają się transakcje z błędnym
położeniem; jedna taka kropka setki kilometrów dalej zmniejszyłaby
schemat do kilku pikseli. Mediana położenia nie przesuwa się od
pojedynczych błędów. Mapa ma pokazać, jak pliki leżą względem siebie —
liczby (mediany, liczby transakcji) są w tabeli i liczą wszystkie
transakcje, więc pominięcie na schemacie niczego nie zmienia w wynikach.

**Odrzucone alternatywy:**
- Granice powiatów z PRG — usługa niedostępna z tego środowiska (D-223),
  a plik RCN nie mówi wprost, jaki obszar obejmuje.
- Prostokąt wszystkich transakcji — rozciągany przez błędne położenia.
- Podkład OSM w raporcie — kafle z sieci w wydruku; schemat wystarcza.

## D-230 — Ponowne liczenie zawsze na pliku bazowym, wynik jako nowy plik
Data: 2026-10-03

**Decyzja:** „Edytuj te punkty” przenosi punkty na stronę pliku bazowego
(tego, na którym policzono je pierwszy raz) i liczy od nowa jak przy
pierwszym razie; wynik to nowy plik, poprzedni zostaje.

**Uzasadnienie:** Przy „dodaj do istniejących” plik wynikowy ma już czasy
połączone ze starymi usługami — ponowne łączenie na nim zostawiłoby
przesunięty punkt w danych także w starym miejscu. Plik bazowy
ma czyste czasy istniejących usług, ludność i wskaźniki. Nowy plik zamiast
nadpisania: warianty „przed/po przesunięciu” porównuje się tym samym
„Porównaj” co scenariusze z ETAPu 21.

**Odrzucone alternatywy:**
- Nadpisanie pliku wynikowego — traci się wariant do porównania.
- Przenoszenie przez parametr w adresie — do 100 punktów z nazwami to
  długi adres; sessionStorage trzyma zestaw tylko na jedno przejście.

## D-231 — Jedno liczenie, kolumna na usługę; plik punktów zgodny wstecz
Data: 2026-10-03

**Decyzja:** Punkty szybkiego modelu mogą mieć różne usługi; jedno
liczenie zapisuje jeden plik z kolumną czasu dla każdej usługi. W pliku
punktów pola na wierzchu opisują pierwszą usługę (jak przed ETAPem 223),
a lista `grupy` — wszystkie.

**Uzasadnienie:** „Miasto 15-minutowe” wymaga kilku usług w jednym pliku
— wcześniej trzeba było liczyć je po kolei, każdą na wyniku poprzedniej.
Wierzch bez zmian: stare pliki punktów i kod, który czyta tylko
`kolumna`/`obszary`, działają dalej; nowy kod szuka grupy po kolumnie.

**Odrzucone alternatywy:**
- Osobny plik na usługę — wskaźnik łączny potrzebuje wszystkich kolumn w
  jednym pliku.
- Nowy format pliku punktów bez pól na wierzchu — wymagałby konwersji
  zapisanych plików.

## D-232 — Prognoza egzaminu: rachunek prawdopodobieństwa, nie losowanie
Data: 2026-10-03

**Decyzja:** Prognozę liczymy dokładnie: dla każdej fiszki rozkład
prawdopodobieństwa stanu (pudełko, termin powtórki) przesuwany dzień po
dniu, z udziałami odpowiedzi z dziennika. Druga liczba — same „umiem” —
to twarda górna granica z odstępów Leitnera.

**Uzasadnienie:** Wynik jest powtarzalny (ta sama baza → ta sama liczba)
i sprawdzalny w testach ręcznym rachunkiem. Losowanie (Monte Carlo)
dawałoby przy każdym odświeżeniu inną liczbę. Stanów jest mało (pudełka
1–5 × dni do egzaminu), a identyczne fiszki liczymy raz. Udziały z
dziennika zamiast założonej skuteczności — liczby z danych, nie z
przyjęcia; przy mniej niż 30 odpowiedziach pokazujemy tylko granicę.

**Odrzucone alternatywy:**
- Monte Carlo — wynik zmienny między odświeżeniami.
- Skuteczność osobno dla każdego pudełka — przy kilkudziesięciu
  odpowiedziach w pudełku udziały byłyby losowe.
- Stała skuteczność (np. 80%) bez danych — liczba niepochodząca z danych.

## D-233 — Nowelizacje z wyszukiwarki po tytule zamiast pól powiązań API
Data: 2026-10-03

**Decyzja:** Ustawy zmieniające znajdujemy tą samą wyszukiwarką po tytule
co teksty jednolite (ETAP 101): tytuł zawiera „o zmianie ustaw…” i
przedmiot ustawy. Aktów wykonawczych nie pokazujemy.

**Uzasadnienie:** Plan zakładał pola powiązań aktów z odpowiedzi API
Sejmu, ale API jest niedostępne z tego środowiska (proxy odrzuca
połączenie), a zasada „nie zgaduj” wyklucza wpisanie nazw pól z pamięci.
Wyszukiwarka jest już używana i przetestowana. Tytuły ustaw zmieniających
w Dzienniku Ustaw wymieniają zmienianą ustawę, więc to wystarcza dla
typowych nowelizacji; ograniczenie („o zmianie niektórych ustaw”) jest
opisane na stronie i w Pomocy.

**Odrzucone alternatywy:**
- Pola powiązań z odpowiedzi API wpisane z pamięci — niesprawdzalne tu;
  do zrobienia, gdy będzie można obejrzeć prawdziwą odpowiedź.
- Szukanie rozporządzeń po słowach z tytułu ustawy — tytuły rozporządzeń
  zwykle jej nie wymieniają, wynik byłby przypadkowy.

## D-234 — Najpierw pomiar i profil, potem indeksy
Data: 2026-10-03

**Decyzja:** Wydajność poprawiamy według profilu na powtarzalnej dużej
bazie (`narzedzia/pomiar_fiszek.py`), nie według przeczucia. Indeks
zostaje tylko, gdy pomiar pokazuje zysk; obliczenia po całej tabeli
przenosimy do SQL i zapamiętujemy, gdy dane się nie zmieniły.

**Uzasadnienie:** Pierwsza próba (pięć indeksów „na oko”) spowolniła
stronę Fiszek — planista wybrał indeks dat dla zakresu obejmującego
prawie całą tabelę. Profil pokazał, że czas zabiera krzywa zapominania
liczona w Pythonie, a nie brak indeksu. Zapamiętanie krzywej jest
bezpieczne, bo dziennik tylko przybywa (`kosz.TABELE_ZOSTAJA`, nic go nie
usuwa ani nie zmienia) — klucz: plik bazy, ostatnie id, liczba wpisów.

**Odrzucone alternatywy:**
- Tabela z gotową krzywą aktualizowana przy każdej odpowiedzi — druga
  kopia danych do pilnowania (także przy synchronizacji z telefonu).
- Indeksy na wszystkich kolumnach z WHERE — część nie pomaga albo
  szkodzi, a każdy spowalnia zapis odpowiedzi.

## D-235 — Komunikaty: alert dla błędów, status dla reszty; nagłówki później
Data: 2026-10-03

**Decyzja:** Błędy dostają `role="alert"` (czytnik przerywa i ogłasza),
pozostałe komunikaty `role="status"` (ogłasza po skończeniu zdania).
Opis wykresu SVG jest na kontenerze (`role="img"` + `aria-label`), bo SVG
wstawia serwer bez tekstów (D-048). Kolejność poziomów nagłówków na razie
tylko raportujemy.

**Uzasadnienie:** Rola na elemencie obecnym od załadowania strony
(ukrytym) sprawia, że późniejsza zmiana treści jest ogłaszana — dodana
dopiero razem z treścią bywa pomijana. Opis na kontenerze nie zmienia
SVG z serwera (tylko liczby i kolory). WCAG nie wymaga kolejnych poziomów
nagłówków; zmiana h3 → h2 na 31 stronach dotyka 34 reguł CSS z h3 i
nagłówków tworzonych w JS — to osobna praca (ETAP 249), nie przy okazji.

**Odrzucone alternatywy:**
- Jeden skrypt (MutationObserver) dopisujący role wszystkim
  komunikatom — rola dodana po wstawieniu treści nie jest pewnie
  ogłaszana.
- `role="alert"` dla wszystkich komunikatów — informacje przerywałyby
  czytanie strony.

## D-236 — Testy ścieżek błędów usług zewnętrznych na podstawionych odpowiedziach
Data: 2026-10-03

**Decyzja:** Ścieżki błędów usług zewnętrznych (ULDK, PRG, BDL) testujemy
na podstawionych `requests.get` i odpowiedziach tekstowych — bez sieci.
Sprawdzamy to, co widzi użytkownik: kod HTTP trasy (502 przy usłudze,
400/404 przy danych) i czytelny komunikat.

**Uzasadnienie:** Usługi bywają niedostępne (także w tym środowisku) — to
właśnie te ścieżki działają wtedy u użytkownika, a testy ich nie
dotykały. Podstawione odpowiedzi są powtarzalne i szybkie (cały zestaw
ULDK w 0,3 s).

**Odrzucone alternatywy:**
- Nagrane prawdziwe odpowiedzi usług — z tego środowiska nie da się ich
  nagrać (proxy), a formaty błędów i tak trzeba by dopisać ręcznie.
- Cel pokrycia 100% w całym projekcie — część gałęzi (np. zabezpieczenia
  przed wyścigiem przy zapisie) testowałaby się sztucznie.

## D-237 — CSP bez script-src; SECRET_KEY bez znaczenia, dopóki brak sesji
Data: 2026-10-07

**Decyzja:** Nagłówek CSP ogranicza połączenia JS i formularze do samej
aplikacji, wyłącza wtyczki, `<base>` i osadzanie w ramkach. Nie
ograniczamy `script-src` ani `img-src`.

**Uzasadnienie:** Szablony mają bloki `<script>` i atrybuty `onclick`, więc
`script-src` wymagałby `'unsafe-inline'` (bez wartości) albo przepisania
wszystkich szablonów. `connect-src 'self'` daje realną ochronę: nawet
wstrzyknięty skrypt nie wyśle danych fetch-em do obcej domeny. Kafle map i
ortofotomapy to obrazki z usług zewnętrznych — `img-src` zostaje wolne.
`SECRET_KEY` podpisuje tylko sesje Flaska, których aplikacja nie używa;
gdyby kiedyś doszły — klucz trzeba będzie generować przy pierwszym starcie.

**Odrzucone alternatywy:**
- Pełne CSP z `script-src 'self'` — przeniesienie skryptów z ~40
  szablonów do plików; duża zmiana przy niewielkim zysku dla aplikacji
  dostępnej tylko pod 127.0.0.1.
- Podniesienie limitu 50 MB — kopie przywraca się z listy w folderze bez
  wgrywania, a pliki RCN — z folderu Pobrane.

## D-238 — Moduł Praca: Gemini przepisuje zdjęcie, liczby liczy kod
Data: 2026-10-07

**Decyzja:** Nowy, dziewiąty moduł `praca` (prośba autora). Grafik z
PDF-u czyta pypdf; zdjęcie albo skan przepisuje Gemini na tekst, który
użytkownik widzi i może poprawić. Godziny, sumę i kwotę liczy wyłącznie
`praca/grafik.py` (kwota w `Decimal` z minut, nie z zaokrąglonych godzin).

**Uzasadnienie:** Zasada projektu: model nie generuje liczb. Przepisanie
obrazu to odczyt danych, nie ich tworzenie, ale może się pomylić — dlatego
tekst jest jawny i edytowalny przed liczeniem, a nieczytelna cyfra ma
być oznaczona „?” (wtedy kod nie rozpozna godziny i zmiana nie zostanie
policzona po cichu z błędną wartością). PDF z Google Docs ma warstwę
tekstu, więc najczęstszy przypadek działa bez modelu i bez klucza.
Parser obsługuje dwa układy tekstu z tabeli, bo kolejność komórek zależy
od programu tworzącego PDF — sprawdzony na wydruku tabeli z Chromium;
prawdziwego PDF-u z Google Docs nie było do sprawdzenia.

**Odrzucone alternatywy:**
- OCR (Tesseract) — nowa zależność systemowa i słabsze wyniki na zrzutach
  z ciemnym motywem; Gemini już jest w projekcie.
- Gemini od razu liczy godziny — liczby od modelu, wbrew zasadom.
- Osobna baza modułu na historię miesięcy — nikt o nią nie prosił.
