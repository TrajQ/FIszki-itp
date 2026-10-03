# Warsztat — narzędzia do gospodarki przestrzennej

*Projekt studencki (gospodarka przestrzenna, I rok). Lokalna aplikacja
webowa: 8 modułów, dane publiczne GUS i GUGiK, praca w terenie bez
internetu. English summary at the end.*

## W jednym zdaniu

Warsztat łączy w jednym miejscu to, co student i młody planista robi na
co dzień: diagnozę gminy z danych GUS, sprawdzanie planów miejscowych i
działek, analizy dostępności pieszej, szkic koncepcji osiedla z
bilansem terenu, pracę z przepisami, inwentaryzację w terenie i naukę
do egzaminów.

## Moduły i co pokazują

| Moduł | Co robi | Umiejętności, które pokazuje |
|---|---|---|
| **Atlas** | Wskaźniki GUS BDL dla gmin województwa: kartogram, ranking, zmiany w czasie, korelacja, miary zróżnicowania, autokorelacja przestrzenna (I Morana, LISA), wskaźnik złożony (unitaryzacja, standaryzacja), typologia gmin (k-średnich z sylwetką), raport gminy, mapa do druku z legendą, podziałką i źródłem | statystyka regionalna, kartografia tematyczna, metody klasyfikacji (kwantyle, Jenks, GVF), analiza skupień |
| **MPZP** | Działka → przeznaczenie w planie miejscowym w całej Polsce, karta działki, kronika zmian na ortofotomapach archiwalnych, kalkulator zabudowy, eksport DXF do CAD | usługi ULDK, WMS/WFS, krajowa integracja planów miejscowych, układy PL-2000/PL-1992 |
| **Dostępność** | Czas dojścia na siatce H3, miasto 15-minutowe, mieszkańcy w zasięgu, porównanie scenariuszy, gdzie postawić nową placówkę (problem maksymalnego pokrycia), zasięg z wybranego punktu | analiza dostępności, siatki heksagonalne, modele lokalizacyjne |
| **Osiedle** | Koncepcja rysowana na mapie: bilans terenu, wskaźniki zabudowy, zgodność z ustaleniami planu, program osiedla (mieszkańcy, parkingi, przedszkola, szkoły), porównanie wariantów, raport do druku, obszar z pliku QGIS, rysunek do CAD (DXF) | wskaźniki urbanistyczne, programowanie osiedla, wymiana danych GIS/CAD |
| **Przepisy** | Ustawy z PDF podzielone na artykuły, wyszukiwarka, pytania do modelu językowego z cytatami sprawdzanymi w tekście, porównanie wersji aktu po nowelizacji, słowniczek definicji, odesłania jako odnośniki, notatki | praca z prawem planistycznym, kontrola wiarygodności AI |
| **Teren** | Formularz na telefon działający bez internetu (GPS, zdjęcia, mapa offline z ortofotomapą), import (także GeoJSON z QGIS), poprawki punktów, raport z heksagonami H3 i eksport do QGIS | inwentaryzacja urbanistyczna, zbieranie danych w terenie |
| **Ceny** | Ceny mieszkań w miastach i powiatach z GUS (szeregi, zmiany, ranking, dostępność cenowa — m² za przeciętne wynagrodzenie); pojedyncze transakcje mieszkań i działek z Rejestru Cen Nieruchomości: mapa, trend, porównanie narysowanych dzielnic, mapa cen i zmian cen w heksagonach H3, wycena porównawcza z kartą do druku, premia rynku pierwotnego, raport porównania miast, ceny w okolicy działki i osiedla, eksport do QGIS | rynek nieruchomości, analiza przestrzenna cen, podejście porównawcze, statystyka publiczna |
| **Fiszki** | Fiszki z PDF-ów z kotwicą w źródle, fiszki z luką, powtórki metodą pudełek, egzaminy z postępem, nauka na telefonie offline | — (narzędzie do nauki) |

## Zasady, które wyróżniają projekt

- **Liczby zawsze z danych, nie z AI.** Model językowy (Gemini) tylko
  opisuje i proponuje tekst. Każda liczba w jego opisie jest sprawdzana
  z danymi GUS, a każdy cytat z przepisu — z tekstem ustawy. Odpowiedź
  bez prawdziwego cytatu nie jest pokazywana.
- **Wyłącznie oficjalne źródła.** API GUS BDL, usługi GUGiK (ULDK, PRG,
  ortofotomapy, krajowa integracja planów miejscowych), WFS miasta. Bez
  pobierania danych ze stron, które na to nie pozwalają.
- **Dane zostają u użytkownika.** Aplikacja działa na 127.0.0.1; do
  terenu i nauki jest samodzielny plik HTML na telefon, bez internetu.
- **Uczciwe przybliżenia.** Szybki model dostępności (linia prosta ×
  krętość) jest wprost opisany jako przybliżenie do porównania
  wariantów, nie jako analiza sieciowa.
- **Eksport do narzędzi branżowych.** GeoJSON do QGIS (także import),
  DXF do programów CAD, CSV, mapy SVG/PDF gotowe do pracy zaliczeniowej;
  każdy wydruk ze źródłem danych i datą.

## Jak powstał

Projekt powstał w dialogu z asystentem AI do programowania (Claude Code)
w 150 małych etapach. Moja rola: pomysły i wymagania z perspektywy
gospodarki przestrzennej, zasady projektu (np. „liczby tylko z
danych”), akceptacja planów etapów, testowanie na prawdziwych danych i
decyzje o kierunku. Od etapu 75 asystent za moją zgodą sam proponował i
realizował kolejne etapy (decyzja D-081), a ja je sprawdzałem.
*(Uzupełnij ten akapit własnymi słowami — to pytanie padnie na
rozmowie.)*
Każda decyzja projektowa ma uzasadnienie i odrzucone alternatywy w
[DECISIONS.md](../DECISIONS.md), a przebieg prac jest w
[PROGRESS.md](PROGRESS.md).

## Liczby (stan: ETAP 200)

- 8 modułów, 200 etapów, 208 zapisanych decyzji projektowych
- ok. 19 500 wierszy Pythona aplikacji (+ 9 500 wierszy testów, pokrycie
  ok. 95%), 9 700 JavaScriptu, 621 testów automatycznych; przegląd 92 stron
  (z danymi) w przeglądarce jednym skryptem (`narzedzia/przeglad_stron.py`),
  kontrast kolorów wg WCAG pilnowany testem
- architektura opisana w [ARCHITEKTURA.md](ARCHITEKTURA.md)
- technologie: Python, Flask, SQLite, vanilla JavaScript, Leaflet,
  shapely, H3, pypdf, Gemini API; bez frameworków frontendowych i buildu

## Zrzuty ekranu do portfolio

Zrzuty trzeba zrobić na prawdziwych danych (w środowisku, w którym
powstawał ten opis, usługi GUS i GUGiK były niedostępne, a dane testowe
są zmyślone — nie nadają się do pokazywania). Zapisz je w
`docs/portfolio/` pod nazwami z tabeli.

| Plik | Co pokazać | Jak |
|---|---|---|
| `01_atlas_kartogram.png` | kartogram jednego wskaźnika | Atlas → np. „mieszkania oddane … na 1000 ludności”, swoje województwo, ostatni rok |
| `02_atlas_raport_gminy.png` | raport Twojej gminy z porównaniem | Raport gminy → gmina + „porównaj z gminą…” sąsiednią |
| `03_atlas_wskaznik_zlozony.png` | ranking i kartogram | Wskaźnik złożony → 3–4 składowe, w tym destymulanta |
| `04_mpzp_karta_dzialki.png` | karta działki z ortofotomapami | MPZP → działka w planie miejscowym → „Karta działki ↗” |
| `05_mpzp_kronika.png` | zmiany na zdjęciach z kilku lat | Kronika zmian dla działki, na której coś zbudowano |
| `06_dostepnosc.png` | mapa czasu dojścia i zasięg z punktu | plik przykładowy albo własny wynik z QGIS, „Zasięg z punktu” |
| `07_osiedle.png` | koncepcja z bilansem i wskaźnikami | Osiedle → obszar z działek, 4–5 terenów, ustalenia planu |
| `08_przepisy.png` | odpowiedź z cytatami | ustawa o planowaniu i zagospodarowaniu przestrzennym, pytanie o plan ogólny |
| `09_teren_telefon.jpg` | formularz na telefonie z mapą offline | zrzut z telefonu w terenie |
| `10_teren_raport.png` | raport inwentaryzacji | kilka punktów ze zdjęciami → Raport do druku |
| `11_ceny_transakcje.png` | mapa cen w heksagonach i porównanie dzielnic | Ceny → Transakcje (RCN) → plik GeoPackage swojego miasta, 2–3 narysowane dzielnice, widok „heksagony” |
| `12_ceny_wycena.png` | karta wyceny porównawczej | kliknij miejsce na mapie, powierzchnia → „Karta wyceny do druku” |
| `13_atlas_typologia.png` | typy gmin na kartogramie i ich profile | Atlas → Typologia → 3–4 wskaźniki z zestawu raportu, „Porównaj liczbę typów” |
| `14_przepisy_slowniczek.png` | słowniczek i odesłania w tekście ustawy | ustawa o planowaniu → „Słowniczek” i klik w „art. 15 ust. 2” |

Dobrze też dołączyć 2–3 gotowe wydruki PDF (raport gminy, karta działki,
raport inwentaryzacji, raport cen transakcyjnych) — pokazują efekt, a nie tylko interfejs.

## English summary

**Warsztat** ("Workshop") is a local web application built during my
first year of Spatial Planning studies. It brings together eight tools
used in planning practice: municipal indicators from Statistics Poland
(choropleths, composite indices, spatial autocorrelation, k-means typology), local zoning
plan and cadastral parcel lookup with archival orthophotos, walking
accessibility on an H3 grid with a maximal covering location model,
housing estate concept design with land-use balance and zoning
compliance, housing and land prices from the national transaction price
register (district comparison, H3 price and price-change maps,
comparative valuation sheet, export to QGIS), legal acts with LLM answers whose quotes are verified
against the source text (plus a glossary of statutory definitions and cross-references as links), an offline smartphone field survey form, and
spaced-repetition flashcards. Numbers always come from data; the
language model only describes. Built with Python/Flask, SQLite, vanilla
JavaScript and Leaflet, GeoJSON and DXF exchange with QGIS and CAD, 554 automated tests (95% coverage), developed iteratively with
an AI coding assistant, with every design decision documented.
