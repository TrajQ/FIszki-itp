# Decyzje projektowe

Format: D-0XX, data, decyzja, uzasadnienie, odrzucone alternatywy.

## D-001 — Struktura szkieletu aplikacji
Data: 2026-09-24

**Decyzja:** Każdy z czterech modułów (atlas, mpzp, fiszki, dostepnosc) to
osobny pakiet Pythona z własnym blueprintem Flask, własnym `templates/` i
`static/` (zagnieżdżonym pod nazwą modułu, np. `atlas/templates/atlas/`, żeby
uniknąć kolizji nazw szablonów między modułami i aplikacją główną). Brak
wspólnej bazy danych, wspólnego stanu ani wspólnej logiki między modułami.
Host aplikacji zakodowany na sztywno jako `127.0.0.1` w `app.py` — nie do
zmiany przez zmienną środowiskową.

**Uzasadnienie:** Moduły są funkcjonalnie niezależne (różne dane, różne
źródła, różni odbiorcy). Osobne pakiety ułatwiają pracę nad jednym modułem
bez ryzyka zepsucia pozostałych i odpowiadają zasadzie z CLAUDE.md o
unikaniu uniwersalnych abstrakcji dla dwóch modułów. Sztywny host 127.0.0.1
eliminuje ryzyko przypadkowego wystawienia aplikacji na sieć.

**Odrzucone alternatywy:**
- Wspólna baza SQLite dla wszystkich modułów — odrzucona, bo moduły nie
  współdzielą danych, a wspólna baza wymuszałaby migracje dotykające
  wszystkich modułów naraz.
- Flask-SQLAlchemy jako ORM — odłożone; żaden moduł jeszcze nie ma schematu,
  decyzja o ORM vs. surowy `sqlite3` zapadnie przy pierwszym module, który
  faktycznie zapisuje dane.
