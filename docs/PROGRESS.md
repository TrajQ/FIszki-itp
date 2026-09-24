# Postęp prac

## ETAP 1 — Szkielet aplikacji
Data: 2026-09-24
Status: zamknięty

Zrobione:
- Aplikacja Flask (app factory w `app.py`), bindowana na 127.0.0.1
- 4 blueprinty-placeholdery: atlas, mpzp, fiszki, dostepnosc
- Strona startowa z linkami do modułów
- Konfiguracja przez `.env` / `.env.example`
- Testy smoke (pytest)
- `DECISIONS.md` z D-001

Testy: 5 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap1_20260924.zip

## ETAP 2 — Moduł fiszki (upload PDF, tworzenie fiszek z kotwicą)
Data: 2026-09-24
Status: zamknięty

Zrobione:
- Baza sqlite3 modułu (`fiszki/baza.py`): tabele `pdfy` i `fiszki`,
  `instance/fiszki/fiszki.db`, pliki PDF w `instance/fiszki/pliki/`
- Warstwa Gemini (`dane/gemini.py`): `zaproponuj_fiszke(fragment_tekstu)`,
  pracuje wyłącznie na dostarczonym fragmencie, błędy jako `BladGemini`
- Endpointy `fiszki/routes.py`: lista PDF-ów + upload (walidacja
  rozszerzenia i nagłówka `%PDF-`), widok PDF-a, serwowanie pliku, JSON
  listy fiszek, szkic fiszki przez Gemini, zapis fiszki, usuwanie fiszki
- Widok PDF-a (`pdf.html` + `fiszki.js`): renderowanie stron przez
  wektorowany lokalnie `pdf.js` (warstwa tekstowa do zaznaczania myszką),
  przycisk "Zaproponuj fiszkę", panel tworzenia/edycji fiszki, lista fiszek
  z "pokaż w źródle" (podświetlenie fragmentu na właściwej stronie) i "usuń"
- Testy (mockowany Gemini, bez realnych wywołań API): upload poprawnego i
  niepoprawnego PDF-a, szkic fiszki (sukces i błąd Gemini → czytelny JSON,
  nie 500), zapis i usuwanie fiszki
- `DECISIONS.md`: D-002 (google-genai), D-003 (pdf.js lokalnie),
  D-004 (surowy sqlite3, bez ORM)

Poza zakresem (świadomie odłożone): system powtórek (spaced repetition),
edycja treści fiszki po zapisaniu, eksport (Anki/CSV).

Testy: 11 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap2_20260924.zip

Następny krok: wybór kolejnego modułu do realnej implementacji.
