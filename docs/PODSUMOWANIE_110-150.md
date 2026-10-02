# Podsumowanie ETAPów 110–150

Czterdzieści ETAPów pracy samodzielnej (zgoda autora: D-081). Ten plik
zbiera, co się zmieniło, co znalazły przeglądy i co dalej. Szczegóły
każdego ETAPu: `docs/PROGRESS.md`, decyzje D-118…D-158: `DECISIONS.md`.

## Liczby

| | ETAP 109 | ETAP 150 |
|---|---|---|
| testy automatyczne | 494 | 554 |
| pokrycie testami | (nie mierzone) | 95% (najsłabszy plik 85%) |
| decyzje w DECISIONS.md | 117 | 158 |
| strony w przeglądzie przeglądarką | — (narzędzie od ETAPu 118) | 75 (z danymi) × 2 szerokości, 0 problemów |
| start aplikacji | ok. 0,87 s | ok. 0,42 s |
| wiersze Pythona aplikacji | ok. 14 800 | ok. 16 500 |

## Co doszło — według modułów

**Ceny** (110–117, 135–137): trend cen w narysowanych dzielnicach, zmiana
cen w heksagonach między okresami, piętro lokalu, karta wyceny do druku,
GeoJSON do QGIS, ceny w okolicy na karcie działki i w raporcie osiedla,
dostępność cenowa (m² za wynagrodzenie), premia rynku pierwotnego, nowsza
wersja pliku RCN bez utraty obszarów, raport porównania miast GUS.
Wydajność: raport dużego pliku 180 s → 1,7 s.

**Przepisy** (120, 121, 140): słowniczek definicji ustawowych i skrótów,
odesłania „art. 15 ust. 2” jako odnośniki, własne notatki przy artykułach.

**Osiedle i MPZP** (122, 123, 138): rysunek koncepcji i działki do DXF
(CAD, PL-2000 / PL-1992), obszar opracowania z pliku GeoJSON z QGIS.

**Atlas** (124, 125): typologia gmin metodą k-średnich z sylwetką do
wyboru liczby typów.

**Teren** (132–134): rozmieszczenie punktów w heksagonach H3 w raporcie,
import punktów z GeoJSON, nowy projekt na wzór istniejącego.

**Fiszki** (139): fiszki z luką — zwykłe fiszki, więc działają na telefonie
i w quizie bez zmian.

**Całość** (126–131, 141–146): diagnostyka, dziennik błędów, wyszukiwarka
globalna, przywracanie kopii, dostępność (etykiety, klawiatura) i kontrast
WCAG w obu motywach, „Wróć do pracy”, „Pierwsze kroki”, wspólna stopka
wydruków, szybszy start, `docs/ARCHITEKTURA.md`.

## Co znalazły przeglądy i testy (błędy poprawione)

- Raport dużego pliku RCN rysował wszystkie punkty (3 minuty) — ETAP 117.
- Odesłania: „§” nie był rozpoznawany, „ustawy” brane za inny akt — 121.
- DXF: filtr tekstu usuwał nawiasy z opisów — 122.
- Kopia: dwa przywrócenia w tej samej sekundzie nadpisywały katalog — 129.
- Mapa typologii obcinała przypisy i legendę — 124.
- Wyszukiwarka cen: 1 znak dawał „nic nie znaleziono” zamiast prośby
  o 2 znaki — 128.
- Dymki map wstawiały nazwy z plików i od użytkownika jako HTML (możliwe
  wykonanie skryptu z wgranego pliku) — 147.
- Niezamknięty plik w teście (niestabilne „1 warning” od wielu ETAPów),
  połączenia SQLite niezamykane w dwóch miejscach — 147; ostrzeżenia
  o zasobach są teraz błędem testu.
- Wyszukiwarka przepisów nie znajdowała „plan” w „planu” — 148.
- Odmiana: „1 kart.”, „Tylko 3 podobnych” — 148, 107.
- Pomyłki w moich własnych założeniach wyłapane testami: polska kolejność
  alfabetyczna („ładzie” przed „łąką”), długości krawędzi H3 wpisane
  z pamięci (teraz liczy je biblioteka).

## Otwarte sprawy dla autora

- **SpatiaLite** jest w opisie stosu w CLAUDE.md, ale nigdy nie wszedł do
  kodu (geometria to GeoJSON w SQLite + shapely). Do decyzji: zostawić
  wpis czy go poprawić (D-153).
- **Zrzuty do portfolio** trzeba zrobić na prawdziwych danych — lista
  14 plików w `docs/PORTFOLIO.md`.
- **Akapit „Jak powstał”** w portfolio czeka na własne słowa autora.
- Usługi GUS i GUGiK były w środowisku pracy niedostępne; wszystko
  testowano na podmienionych odpowiedziach o sprawdzonym formacie.
  Pierwsze uruchomienie na prawdziwych danych warto zacząć od
  `/diagnostyka` → „Sprawdź usługi”.

## Plan ETAPów 151–200

Kolejne dwadzieścia ETAPów konkretnie; 171–200 to kierunki — do
doprecyzowania po przeglądzie w ETAPie 170, z tym, co wyjdzie w użyciu.

| ETAP | Co | Dlaczego |
|---|---|---|
| 151 | Przełącznik motywu (jasny / ciemny / jak system) | dziś tylko według systemu; na rzutniku na zajęciach potrzebny jasny |
| 152 | Atlas: gorące punkty Getisa-Orda Gi* | uzupełnia LISA; standard w analizie przestrzennej |
| 153 | Atlas: iloraz lokalizacji (LQ) | specjalizacja gmin względem województwa — klasyka geografii ekonomicznej |
| 154 | Fiszki: fiszka z wycinkiem rysunku z PDF | mapy, schematy i przekroje z wykładów nie dają się zapisać tekstem |
| 155 | Osiedle: szacunek kosztów z jawnymi stawkami | porównanie wariantów także kosztem; stawki wpisuje użytkownik |
| 156 | Ceny: wpływ cech na cenę m² (regresja) | ile „kosztuje” piętro, metraż, rynek — liczone z pliku RCN, z miarą dopasowania |
| 157 | Teren: porównanie dwóch inwentaryzacji | „projekt na wzór” (134) daje powtórzenie — brakuje zestawienia zmian |
| 158 | Przepisy: druk notatek i wybranych artykułów | przygotowanie do kolokwium na papierze |
| 159 | „Co nowego” po aktualizacji | użytkownik nie czyta CHANGELOG-u |
| 160 | Przegląd kodu, stron i testów | jak 147–148 |
| 161 | Atlas: mapy jednego wskaźnika w kilku latach obok siebie | zmiana przestrzenna czytelniej niż jedna mapa zmiany |
| 162 | MPZP: zestawienie „Moich działek” do druku | kilka działek inwestycji na jednej kartce |
| 163 | Dostępność: wyniki w narysowanych dzielnicach | jak obszary w Cenach — średni czas i mieszkańcy w zasięgu na dzielnicę |
| 164 | Osiedle: miejsca postojowe wg własnych wskaźników uchwały | gminy mają różne uchwały parkingowe |
| 165 | Ceny: dwa pliki RCN (dwa powiaty) w jednym porównaniu | miasto i powiat obwarzankowy |
| 166 | Teren: pola wymagane i zakresy liczb w formularzu telefonu | jakość danych zbieranych w terenie |
| 167 | Skróty klawiszowe (powtórka, mapy) i ich lista w Pomocy | szybsza praca, dostępność |
| 168 | Kopia automatyczna: sprawdzenie spójności i przypomnienie o kopii poza dyskiem | kopia, której nie da się przywrócić, nie jest kopią |
| 169 | Dokumentacja po 151–168 | |
| 170 | Przegląd i plan 171–200 | |
| 171–180 | kierunki: eksport wyników Atlasu i Dostępności do arkusza z formatowaniem; warstwy budynków w koncepcji osiedla; fiszki z luką w trybie wpisywania | |
| 181–190 | kierunki: raport „analiza terenu” łączący MPZP, ceny, dostępność i inwentaryzację dla jednego obszaru; porównanie gmin w czasie | |
| 191–200 | przegląd końcowy, wydajność, dokumentacja, podsumowanie 150–200 | |
