# Warsztat — kontekst projektu

## Czym to jest
Lokalna aplikacja desktopowa (Flask + vanilla JS) łącząca siedem niezależnych
modułów narzędziowych. Uruchamiana ikoną z pulpitu na Linux Mint, dostępna
wyłącznie na 127.0.0.1. Ma dostęp do internetu (API GUS, WFS gmin, ULDK, Gemini).

Autor: jedna osoba, student gospodarki przestrzennej, pierwszy rok.
To jest projekt uczący i użytkowy jednocześnie. Kod ma być czytelny dla
kogoś, kto wróci do niego za trzy miesiące.

## Moduły
- atlas       — wskaźniki GUS BDL dla gmin, kartogramy, generowanie opisów,
                raport gminy
- mpzp        — czytnik planów miejscowych, działka → przeznaczenie,
                kronika zmian (ortofotomapy archiwalne)
- fiszki      — generator fiszek z PDF z kotwicą w źródle, powtórki także
                na telefonie bez internetu
- dostepnosc  — analiza dostępności pieszej, siatka H3 (czyta gotowe wyniki)
- osiedle     — koncepcja osiedla rysowana na mapie: bilans terenu,
                wskaźniki zabudowy, zgodność z planem, program osiedla,
                raport do druku i porównanie wariantów
- przepisy    — akty prawne z PDF: artykuły, wyszukiwarka, pytania do
                Gemini z cytatami sprawdzanymi w tekście i kotwicą w PDF
- teren       — inwentaryzacja w terenie: samodzielny formularz HTML na
                telefon (bez internetu), import pliku, mapa punktów, raport

Plan rozszerzeń D-062 zrealizowany (ETAPy 57–65).

## Stack — nie zmieniaj bez pytania
- Python 3.11+, Flask, blueprinty
- SQLite, osobny plik bazy na moduł; SpatiaLite tam, gdzie geometria
- Frontend: vanilla JS w modułach IIFE, po jednym pliku CSS na moduł
- Brak Reacta, brak Vue, brak buildu, brak node_modules
- Leaflet dla map, ładowany lokalnie, nie z CDN
- Gemini przez warstwę dane/gemini.py
- pytest do testów

## Zasady pracy — bezwzględne
1. NIE ZGADUJ. Przed zmianą czegokolwiek przeczytaj istniejący kod.
   Jeśli czegoś nie ma w repo, powiedz to zamiast zakładać.
2. Bez implementacji bez zgody. Najpierw audyt i plan, potem pytanie,
   dopiero po akceptacji kod.
3. Jeden ETAP na raz. Nie wybiegaj do przodu, nie dodawaj funkcji,
   o które nikt nie prosił.
4. Zero sekretów w kodzie. Klucze przez zmienne środowiskowe,
   .env w .gitignore, .env.example w repo.
5. Po każdym ETAPie: wpisy w docs/PROGRESS.md, docs/CHANGELOG.md,
   DECISIONS.md (rekord D-0XX) oraz ZIP całego projektu.
6. Nowy ETAP nie startuje przy czerwonych testach.
7. Język kodu: angielski dla nazw technicznych, polski dla nazw domenowych
   i komentarzy. Tak jak w PromoBudżecie.

## Czego nie robić
- Nie bindować na 0.0.0.0
- Nie tworzyć uniwersalnych abstrakcji dla dwóch modułów
- Nie scrapować stron, z którymi nie ma zgody — wyłącznie API i usługi WFS
- Nie pozwalać, by model językowy generował liczby: on tłumaczy i opisuje,
  liczby przychodzą z danych
- Nie dodawać zależności bez uzasadnienia i wpisu w DECISIONS.md

## Stan bieżący
ETAP: 84 (atlas: wskaźnik złożony — zamknięty)
Ostatni ZIP: releases/warsztat_etap84_20260930.zip
Testy: 443 passed / 0 failed
Tryb pracy: autor zgodził się, by kolejne ETAPy wybierać samodzielnie (D-081).
