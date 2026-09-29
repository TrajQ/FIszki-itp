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
- Dodano `DECISIONS.md` D-007.
- Dodano testy edycji i eksportu.
