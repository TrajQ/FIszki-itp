# Warsztat — kontekst projektu

## Czym to jest
Lokalna aplikacja desktopowa (Flask + vanilla JS) łącząca cztery niezależne
moduły narzędziowe. Uruchamiana ikoną z pulpitu na Linux Mint, dostępna
wyłącznie na 127.0.0.1. Ma dostęp do internetu (API GUS, WFS gmin, ULDK, Gemini).

Autor: jedna osoba, student gospodarki przestrzennej, pierwszy rok.
To jest projekt uczący i użytkowy jednocześnie. Kod ma być czytelny dla
kogoś, kto wróci do niego za trzy miesiące.

## Moduły
- atlas       — wskaźniki GUS BDL dla gmin, kartogramy, generowanie opisów
- mpzp        — czytnik planów miejscowych, działka → przeznaczenie
- fiszki      — generator fiszek z PDF z kotwicą w źródle
- dostepnosc  — analiza dostępności pieszej, siatka H3 (czyta gotowe wyniki)

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
ETAP: 55 (dostępność: punkty usług z CSV — zamknięty)
Ostatni ZIP: releases/warsztat_etap55_20260929.zip
Testy: 344 passed / 0 failed
