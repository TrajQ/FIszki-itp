# Changelog

## ETAP 1 — 2026-09-24
- Dodano szkielet aplikacji Flask z czterema niezależnymi blueprintami
  (atlas, mpzp, fiszki, dostepnosc) jako placeholderami.
- Dodano stronę startową z listą modułów.
- Dodano konfigurację przez `.env`, `requirements.txt`, `.gitignore`.
- Dodano testy smoke (pytest).
- Dodano `DECISIONS.md` (D-001) i `docs/PROGRESS.md`.

## ETAP 2 — 2026-09-24
- Dodano moduł fiszki: upload PDF, widok PDF-a z zaznaczaniem tekstu
  (pdf.js wektorowany lokalnie), tworzenie fiszek hybrydowo (Gemini
  proponuje szkic na podstawie zaznaczonego fragmentu, użytkownik
  poprawia przed zapisem), kotwica w źródle (strona + podświetlony
  fragment), usuwanie fiszek.
- Dodano warstwę `dane/gemini.py` (pierwsze użycie Gemini w projekcie).
- Dodano bazę sqlite3 modułu fiszki (`pdfy`, `fiszki`).
- Dodano zależność `google-genai` (`requirements.txt`).
- Dodano `DECISIONS.md` D-002, D-003, D-004.
- Dodano testy modułu fiszki (Gemini mockowany, bez realnych wywołań API).

## ETAP 3 — 2026-09-25
- Dodano moduł mpzp: klik na mapie Leaflet znajduje działkę ewidencyjną
  (ULDK) i sprawdza jej przeznaczenie w planie miejscowym gminy Poznań
  (WFS).
- Dodano warstwę `dane/uldk.py` (klient krajowej usługi ULDK).
- Dodano `mpzp/gminy.py` (rejestr gmin, na start tylko Poznań) i
  `mpzp/wfs.py` (klient WFS z lokalnym indeksem przestrzennym
  `shapely.STRtree`).
- Dodano endpointy `GET /mpzp/sprawdz` i `POST /mpzp/odswiez`.
- Dodano zależności `requests` i `shapely` (`requirements.txt`).
- Dodano Leaflet 1.9.4 wektorowany lokalnie (`mpzp/static/leaflet/`).
- Dodano `DECISIONS.md` D-005, D-006.
- Dodano testy modułu mpzp (ULDK i WFS mockowane, bez realnych wywołań
  sieciowych).

## ETAP 4 — 2026-09-29
- Dodano edycję pytania i odpowiedzi fiszki (`PUT /fiszki/<pdf_id>/fiszki/<id>`,
  przycisk „edytuj” w liście fiszek).
- Dodano eksport fiszek z PDF-a do CSV (`/fiszki/<pdf_id>/eksport.csv`).
- Dodano eksport fiszek do Anki jako TSV (`/fiszki/<pdf_id>/eksport.txt`).
- Naprawiono wczytywanie PDF-a: wywołanie `getDocument` dostosowane do
  pdf.js 6.x.
- Usunięto przypadkowy gitlink `FIszki-itp` (zagnieżdżone repozytorium).
- Naprawiono pusty podgląd PDF-a: pdf.js 6.3.289 w wersji legacy
  (z polyfillami dla starszych przeglądarek); błąd wczytania PDF-a
  wyświetlany na stronie.
- Dodano `uruchom.sh`, `zainstaluj_ikone.sh` i `docs/URUCHOMIENIE.md`.
- Dodano `DECISIONS.md` D-007, D-008 (zastąpiona), D-009, D-010.
- Dodano testy edycji i eksportu.

## ETAP 5 — 2026-09-29
- Dodano wspólny szablon `templates/base.html` z paskiem nawigacji.
- Przepisano `static/style.css` (styl Apple, grid/flexbox, tryb ciemny).
- Odświeżono wygląd strony głównej, fiszek i mpzp.
- `/mpzp/sprawdz` zwraca dodatkowo `wydzielenie.przeznaczenie`.
- Lista PDF-ów w fiszkach pokazuje liczbę fiszek.
- Dodano `DECISIONS.md` D-011.

## ETAP 6 — 2026-09-29
- Dodano powtórki fiszek w systemie Leitnera (5 pudełek): sesja z
  kartą, skróty klawiszowe, pasek postępu, link do źródła.
- Dodano tabelę `powtorki` i endpointy `/fiszki/powtorka*`.
- Lista plików pokazuje liczbę fiszek do powtórki i rozkład pudełek.
- Dodano `DECISIONS.md` D-012 i testy powtórek.

## ETAP 7 — 2026-09-29
- Dodano moduł atlas: wskaźniki GUS BDL dla gmin województwa,
  kartogram (granice PRG), kafelki statystyk, ranking gmin, opis przez
  Gemini ze sprawdzaniem liczb.
- Dodano warstwę `dane/bdl.py` i `opisz_wskaznik` w `dane/gemini.py`.
- Dodano `atlas/baza.py` (cache BDL), `atlas/granice.py`,
  `atlas/statystyki.py`.
- Przeniesiono Leaflet do `static/leaflet/`.
- Dodano `GUS_BDL_API_KEY` do `config.py`.
- Dodano `DECISIONS.md` D-013, D-014 i testy atlasu.

## ETAP 8 — 2026-09-29
- Dodano moduł dostępność: wgrywanie gotowych wyników (CSV na siatce
  H3), mapa heksagonów, klasy czasu dojścia, udziały i powierzchnie w
  zasięgu 5/10/15 min.
- Dodano syntetyczny plik przykładowy i skrypt, który go generuje.
- Dodano zależność `h3` (`requirements.txt`).
- Poprawiono kolor przycisków zoomu mapy w trybie ciemnym.
- `uruchom.sh` doinstalowuje zależności po aktualizacji; dodano
  `README.md`.
- Dodano `DECISIONS.md` D-015 i testy modułu.

## ETAP 9 — 2026-09-29
- MPZP: opis symbolu przeznaczenia ze słownika (orientacyjny).
- MPZP: wyszukiwanie działki po identyfikatorze (`/mpzp/dzialka`).
- MPZP: historia ostatnio sprawdzonych działek (`/mpzp/historia`,
  baza `instance/mpzp/mpzp.db`).
- Dodano `DECISIONS.md` D-016 i testy.

## ETAP 10 — 2026-09-29
- Atlas: porównanie z rokiem bazowym (zmiana %, kartogram rozbieżny,
  ranking zmian, fakty zmiany w opisie).
- Atlas: eksport tabeli gmin do CSV (`/atlas/eksport.csv`).
- Poprawiono przybliżenie kartogramu przy pierwszym wczytaniu.
- Dodano `DECISIONS.md` D-017 i testy.

## ETAP 11 — 2026-09-29
- Fiszki: wyszukiwarka we wszystkich plikach (`/fiszki/szukaj`).
- Fiszki: eksport wszystkich fiszek do CSV i Anki.
- Fiszki: usuwanie PDF-a razem z fiszkami i powtórkami.
- Dodano `DECISIONS.md` D-018 i testy.

## ETAP 12 — 2026-09-29
- Dodano ochronę przed zapytaniami z obcych stron (sprawdzanie `Host`
  oraz `Origin`/`Referer` dla metod zmieniających stan) — `ochrona.py`.
- Dodano nagłówki bezpieczeństwa (`X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy`).
- Dodano `DECISIONS.md` D-019 i testy.

## ETAP 13 — 2026-09-29
- Dostępność: wskaźnik łączny (czas do wszystkich usług naraz) i
  „najsłabsze ogniwo” (`/dostepnosc/plik/<nazwa>/laczny`).
- Dodano `DECISIONS.md` D-020 i testy.
