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
