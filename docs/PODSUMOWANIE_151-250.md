# Podsumowanie ETAPów 151–250 — koniec projektu

Sto ETAPów pracy samodzielnej (zgoda autora: D-081), plan w
`docs/PLAN_171-250.md`. Autor zdecydował, że ETAP 250 kończy projekt.
Szczegóły każdego ETAPu: `docs/PROGRESS.md`, decyzje D-159…D-258:
`DECISIONS.md`.

## Liczby

| | ETAP 150 | ETAP 250 |
|---|---|---|
| moduły | 8 | 9 (Praca i notatki od ETAPu 230) |
| testy automatyczne | 554 | 743 |
| pokrycie testami | 95% | 96% (najsłabszy plik 87%) |
| decyzje w DECISIONS.md | 158 | 258 |
| strony w przeglądzie przeglądarką | 75 × 2 szerokości | 111 × 2 szerokości: 0 problemów, 0 uwag o nagłówkach |
| wiersze Pythona aplikacji | ok. 16 500 | ok. 23 600 (+ 11 500 testów) |
| wiersze JavaScriptu | — | ok. 11 400 (bez Leaflet i pdf.js) |
| start aplikacji | ok. 0,42 s | ok. 0,7 s |

## Co doszło — według modułów

**Atlas**: gorące punkty Gi*, iloraz lokalizacji, ten sam wskaźnik w
kilku latach, kilka gmin na wykresie, gminy podobne, trend liniowy jako
kartogram, profil podobnych gmin w raporcie, stabilność rankingu,
powiaty zamiast gmin, odtwarzanie lat na mapie, mapa dwuzmiennowa 3 × 3
z wydrukiem, eksport ODS.

**MPZP**: zestawienie i arkusz „Moich działek”, karta terenu z
inwentaryzacją i cenami, hurtowe sprawdzenie listy działek, kalkulator
zabudowy dla kilku działek razem.

**Dostępność**: wyniki w narysowanych dzielnicach, kontury klas czasu,
dzielnice przed/po, grupy wieku, raport dzielnic, edycja punktów i kilka
usług w szybkim modelu, własne miejsca nowych placówek po kolei.

**Osiedle**: koszty ze stawek, stawka gruntu z RCN, budynki z
kondygnacjami i wskaźniki z budynków, linia zabudowy, cień od budynków,
etapy realizacji, chłonność terenu, GeoPackage dla QGIS, własne
normatywy programu, przekrój terenu z wysokością budynków, zielone
dachy w PBC.

**Przepisy**: druk notatek i artykułów, „Moje przepisy”, przeniesienie
notatek na nowszy tekst, notatki do Markdown, ustawy zmieniające po
tekście jednolitym, filtry wyszukiwarki (rodzaj aktu, rok).

**Teren**: porównanie dwóch inwentaryzacji i zmiana stanu w czasie
(2–6), pola wymagane, tabela krzyżowa z chi-kwadrat i wykresem, trasa
obchodu z GPX, punkty „do sprawdzenia”, opis i kierunek zdjęcia, import
CSV, GeoPackage ze stylami.

**Ceny**: wpływ cech (regresja), kilka plików RCN z mapą schematyczną,
indeks z rokiem bazowym, nietypowe transakcje, korekta na datę i
zapisane wyceny, premia rynku pierwotnego w latach, cena a odległość od
miejsca (gradient).

**Fiszki**: wycinek rysunku, luki w trybie pisania, zasłony (image
occlusion), krzywa zapominania, przeplatanie tematów, wyjaśnienia,
prognoza gotowości na egzamin, fiszki „gdzie to jest” i quiz z mapą.

**Praca i notatki** (nowy moduł, 230–233): godziny z grafiku (PDF albo
zdjęcie) z sumą i wypłatą, wyłączanie zmian, historia miesięcy; notatki
w Wordzie (DOCX budowany bez biblioteki) z pytaniami kontrolnymi i
eksportem do Fiszek.

**Wspólne**: przełącznik motywu, „Co nowego”, skróty klawiszowe, kopia
zapasowa ze sprawdzaniem i kopią poza komputerem, przypięte rzeczy,
kosz we wszystkich modułach, arkusze ODS bez zależności, strona „O
danych”, instrukcja „Bez internetu i na iPhonie”, samouczek z danymi
przykładowymi, porządki (podział `ceny/rcn.py` i `osiedle.js`).

## Co znalazły przeglądy (ETAPy 160, 170, 190, 200, 210, 226–229, 234, 249)

- Wydajność dużych baz Fiszek: strona główna modułu 2085 ms → 285 ms
  (indeksy, krzywa zapominania w SQL, ETAP 226).
- Dostępność dla czytników ekranu: role komunikatów, etykiety pól,
  obrazy SVG z opisem (227), kolejność nagłówków na wszystkich stronach
  (249) — wygląd bez zmian.
- Bezpieczeństwo: CSP, limity wielkości plików, czytelny błąd 413 (229).
- Testy najsłabszych plików (ULDK, granice, raport gminy) — 228.

## Czego nie dało się sprawdzić w środowisku, w którym powstawał projekt

- **Gemini na prawdziwym kluczu** (opisy, pytania, fiszki, notatki,
  przepisanie grafiku) — testy na podstawionych odpowiedziach; liczby i
  cytaty i tak sprawdza kod.
- **Wygląd pliku Word w Wordzie / LibreOffice** — plik sprawdzony
  biblioteką python-docx (struktura), nie obejrzany w edytorze.
- **iPhone (Safari)** — lista testów w `docs/BEZ_INTERNETU_I_IPHONE.md`.
- **Usługi GUS, GUGiK i Sejmu** były zablokowane — działanie na żywych
  danych sprawdzone wcześniej przez autora; testy na nagranych
  odpowiedziach.

## Plan dalszy (poza projektem)

### 1. Warsztat w chmurze (Oracle Cloud) — do rozmowy z autorem

Cel: Warsztat dostępny z telefonu (także iPhone) i z innych komputerów.
To zmienia założenie projektu „tylko 127.0.0.1”, więc wymaga decyzji:

| Sprawa | Co trzeba zrobić |
|---|---|
| dostęp | logowanie (co najmniej jedno konto z hasłem), bo aplikacja przestaje być prywatna; ochrona przed zgadywaniem haseł |
| HTTPS | domena albo adres z certyfikatem (np. Let's Encrypt) i serwer pośredniczący (nginx/Caddy) przed Flaskiem; Flask na produkcyjnym serwerze WSGI (np. gunicorn) zamiast serwera deweloperskiego |
| dane | bazy SQLite i pliki na dysku serwera; automatyczna kopia poza serwerem |
| klucze | `.env` na serwerze, poza repozytorium (jak teraz) |
| telefon | formularze Terenu i Fiszki mogłyby działać jako strona z serwera (PWA) — wtedy GPS i zapis danych na iPhonie bez problemów z plikiem otwieranym z dysku |
| koszty i limity | Oracle oferuje darmowy próg „Always Free” — aktualne warunki (rodzaj maszyny, limity, wymagania karty) trzeba sprawdzić na stronie Oracle przed decyzją |

Proponowana kolejność: (1) decyzja o logowaniu i zakresie (sam autor
czy więcej osób), (2) przygotowanie aplikacji (logowanie, konfiguracja
adresu, gunicorn), (3) serwer i HTTPS, (4) kopie, (5) formularze jako PWA.

### 2. Mniejsze rzeczy

- Testy na iPhonie z listy i poprawki, jeśli coś nie zadziała.
- Podział `dostepnosc.js`, `atlas.js` i `mpzp.js` (ponad 1000 wierszy).
- Zrzuty ekranu do portfolio na prawdziwych danych (`docs/PORTFOLIO.md`).
