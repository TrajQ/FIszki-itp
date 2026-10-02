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
