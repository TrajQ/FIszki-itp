# Architektura Warsztatu

Dokument dla kogoś, kto otwiera kod po przerwie: jak aplikacja jest
poskładana, gdzie czego szukać i jakich zasad pilnuje kod. Szczegóły
decyzji — `DECISIONS.md` (numery D-0XX w nawiasach), historia — `docs/PROGRESS.md`.

## W jednym obrazku

```
ikona na pulpicie
   └─ uruchom.sh ── .venv, zależności (suma requirements.txt), .env z .env.example
        └─ app.py ── create_app(): Flask na 127.0.0.1:PORT
             ├─ ochrona.py      before/after_request: Host, Origin, nagłówki
             ├─ dziennik.py     błędy → instance/logi/warsztat.log
             ├─ 8 blueprintów   /atlas /mpzp /fiszki /dostepnosc /osiedle /przepisy /teren /ceny
             │    każdy: routes.py (+ trasy_*.py), baza.py, logika, templates/, static/
             ├─ dane/           klienci usług zewnętrznych i formaty plików
             └─ strony wspólne  /, /szukaj, /pomoc, /diagnostyka, /kopia-zapasowa, /kalendarz.ics

instance/                       DANE UŻYTKOWNIKA (poza repozytorium)
   ├─ atlas/atlas.db  mpzp/mpzp.db  fiszki/fiszki.db + pliki/  osiedle/osiedle.db
   ├─ przepisy/przepisy.db + pliki/  teren/teren.db + zdjęcia  ceny/ceny.db
   ├─ dostepnosc/wyniki/        wgrane CSV z wynikami
   └─ logi/                     dziennik (nie trafia do kopii)
```

## Start i konfiguracja

- `uruchom.sh` sprawdza `.venv`, doinstalowuje zależności, gdy zmieniła
  się suma `requirements.txt`, tworzy `.env` z `.env.example`, startuje
  `app.py` i otwiera przeglądarkę. Zamknięcie terminala zatrzymuje serwer.
- `config.py` czyta `.env` (python-dotenv): `PORT`, `GEMINI_API_KEY`,
  `GEMINI_MODEL`, `GUS_BDL_API_KEY`, `AUTO_KOPIA_DNI`, `AUTO_KOPIA_FOLDER`,
  `SECRET_KEY`. Kluczy nie ma w kodzie; `/diagnostyka` pokazuje tylko,
  czy są ustawione.
- `create_app(instance_path=None)` — fabryka aplikacji. Testy podają
  katalog tymczasowy, więc każdy test ma czyste bazy.
- Serwer słucha wyłącznie na `127.0.0.1`. `ochrona.py` dodatkowo odrzuca
  obcy nagłówek Host (DNS rebinding), zapytania zmieniające stan z obcym
  Origin/Referer (CSRF) i ustawia `X-Frame-Options`.
- Start trwa ok. 0,4 s; biblioteka Gemini ładuje się dopiero przy
  pierwszym zapytaniu do modelu (D-151).

## Moduł = blueprint

Każdy z ośmiu modułów ma ten sam układ:

| Plik | Rola |
|---|---|
| `__init__.py` | eksport blueprintu |
| `routes.py` | blueprint, strona modułu, API JSON; większe moduły dzielą trasy na `trasy_*.py` |
| `baza.py` | surowy `sqlite3` (D-004): `SCHEMAT`, `get_db`, `init_db`, funkcje zapytań; jedna baza na moduł |
| pliki logiki | czyste funkcje bez Flaska (np. `osiedle/bilans.py`, `ceny/rcn.py`, `atlas/statystyki.py`) — to je testujemy najdokładniej |
| `templates/<moduł>/` | Jinja, dziedziczą z `templates/base.html` |
| `static/` | jeden plik CSS modułu i skrypty JS (IIFE, bez buildu) |

Kolumny dodane po czasie: `CREATE TABLE IF NOT EXISTS` nie dodaje kolumn,
więc Teren i Ceny mają w `baza.py` małe migracje „dodaj kolumnę, jeśli jej
nie ma” (`ALTER TABLE`); pozostałe moduły dokładają raczej nowe tabele.

Geometria leży w SQLite jako tekst GeoJSON (WGS84) i jest liczona
biblioteką shapely; SpatiaLite nie jest używany — przy tej skali danych
nie był potrzebny.

### Haki, które moduł udostępnia stronom wspólnym

Moduł podaje dane, strona wspólna tylko je zbiera. Błąd w jednym module
jest łapany i logowany, reszta strony działa.

| Funkcja w `routes.py` | Kto zbiera | Po co |
|---|---|---|
| `podsumowanie()` | `/` | meta na karcie modułu |
| `terminy()` | `/`, `/kalendarz.ics` | egzaminy (Fiszki), wyjścia w teren (Teren) |
| `wyszukaj(fraza)` | `/szukaj` (D-136) | wyniki wyszukiwarki globalnej |
| `ostatnie(limit)` | `/` — „Wróć do pracy” (D-149) | ostatnio używane rzeczy |

### Powiązania między modułami

Moduły nie sięgają nawzajem do swoich baz. Wyjątki są nieliczne i jawne:

- `mpzp/uklady.py` (odwzorowania PL-1992 / PL-2000) importują Osiedle
  i Ceny — to matematyka, nie dane.
- Przepisy zapisują fiszki przez `fiszki/zewnetrzne.py` (jedno wejście
  do modułu Fiszki, D-074).
- Ceny w okolicy w MPZP i Osiedlu: przeglądarka pyta `POST /ceny/okolica`
  (D-117) — przez trasę, nie przez import.
- Osiedle pokazuje punkty projektu z Terenu, pytając trasy Terenu (D-073).

## Warstwa `dane/`

| Plik | Co robi |
|---|---|
| `bdl.py` | API GUS BDL: zmienne, wartości dla gmin/powiatów, szeregi |
| `uldk.py` | ULDK (GUGiK): działka po punkcie albo identyfikatorze |
| `ortofoto.py` | lata ortofotomap archiwalnych z GetCapabilities WMS |
| `sejm.py` | API Sejmu (ELI): akty i teksty jednolite |
| `gemini.py` | jedyne miejsce, które rozmawia z modelem (`_generuj`) |
| `siec.py` | czytelne komunikaty błędów sieci |
| `dxf.py` | zapis DXF R12 (CAD) — format, nie usługa (D-130) |

Usługi WFS planów miejscowych i KIMPZP są w `mpzp/wfs.py` i
`mpzp/krajowe.py`. Wyłącznie API i WFS — bez scrapowania stron.
Odpowiedzi usług, które rzadko się zmieniają, moduły trzymają w swojej
bazie jako cache (np. `cache_bdl`).

## Zasady, których pilnuje kod

- **Model językowy nie podaje liczb.** Liczby liczy kod z danych; model
  dostaje fakty i opisuje. Każda liczba w opisie musi wystąpić w faktach,
  inaczej opis jest odrzucany (`dane/gemini.sprawdz_liczby`).
- **Cytaty są sprawdzane w źródle.** Fiszki ze strony PDF i odpowiedzi z
  przepisów zostają tylko wtedy, gdy cytat naprawdę jest w tekście
  (`fiszki/strona.py`, `przepisy/pytania.py`).
- **Kotwica w źródle.** Fiszka pamięta stronę i fragment PDF-a; odpowiedź
  z przepisów — jednostkę i stronę.
- **SVG i liczby z serwera w wydrukach.** Mapy i wykresy do druku rysuje
  Python (`*_svg`), wstawiane przez `Markup` tylko z liczb i kolorów z kodu;
  tekst użytkownika zawsze przechodzi przez escapowanie Jinja.
- **Dane użytkownika są nietykalne przy aktualizacji** (`aktualizacja.py`
  nie rusza `instance/`, `.env`, `.venv/`) i trafiają do kopii zapasowej
  (`kopia.py`, kopia spójna przez `sqlite3.backup`).

## Frontend

- Vanilla JS w IIFE, po jednym pliku na stronę lub funkcję; adresy tras
  przekazuje szablon w stałych (`const URL_… = "{{ url_for(…) }}"`).
- `static/style.css` — wspólne komponenty i tokeny kolorów (`--akcent`,
  `--tekst-drugi`…) z wersją ciemną (`prefers-color-scheme`); kontrast
  liczony wg WCAG i pilnowany testem (D-139). CSS modułów używa tokenów.
- Leaflet i Leaflet.draw lokalnie w `static/`; pdf.js lokalnie w Fiszkach.
- Strony do druku: `@media print`, przycisk „Drukuj / zapisz PDF”, wspólna
  stopka `templates/_wydruk.html` (D-150).
- Dostępność: link „Przejdź do treści”, `main#tresc`, `:focus-visible`,
  etykiety pól (D-138).

## Testy i narzędzia

- `pytest` — testy w `tests/`, jeden lub kilka plików na moduł. Usługi
  zewnętrzne są zawsze podmienione (`monkeypatch`), testy nie potrzebują
  internetu ani klucza Gemini.
- `narzedzia/przeglad_stron.py` — otwiera wszystkie strony w Chromium
  (390 px ciemny, 1300 px jasny): kody HTTP, błędy JS, poziome przewijanie,
  podstawowa dostępność.
- Pokrycie mierzone doraźnie (`coverage`, instrukcja w README, D-152).

## Gdzie zacząć czytać

1. `app.py` — fabryka, strony wspólne, rejestr blueprintów.
2. Jeden mały moduł od trasy do bazy, np. `osiedle/routes.py` →
   `osiedle/bilans.py` → `osiedle/baza.py` → `osiedle/static/osiedle.js`.
3. `dane/gemini.py` — jak model jest trzymany w ryzach.
4. `ochrona.py` — dlaczego lokalna aplikacja też potrzebuje ochrony.
