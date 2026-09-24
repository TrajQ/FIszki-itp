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
