# Bez internetu i na iPhonie (ETAP 245)

Przegląd z kodu (adresy usług w `dane/`, `mpzp/`, `atlas/`, `config.py`)
i z przeglądarki Chromium. Safari (WebKit) **nie było dostępne** w
środowisku, w którym powstawał Warsztat — część o iPhonie to przegląd
kodu i lista testów do zrobienia na prawdziwym telefonie, nie wynik
testu.

## Co działa bez internetu (komputer)

Warsztat działa na tym samym komputerze (127.0.0.1), więc strony, bazy i
obliczenia nie potrzebują sieci. Internet jest potrzebny tylko do usług
z listy na stronie „O danych”.

| Moduł | Działa bez internetu | Potrzebuje internetu |
|---|---|---|
| Atlas | wskaźniki i granice pobrane wcześniej (cache BDL 30 dni, granice w plikach), kartogramy, raporty z tych danych | nowe wskaźniki, lata i województwa (API BDL), opisy Gemini |
| MPZP | kalkulatory zabudowy i skali, słownik symboli, zapisane działki (lista) | działka z ULDK, plany (WFS, krajowa integracja), ortofotomapa, kafelki mapy |
| Fiszki | wszystko poza Gemini: PDF, fiszki, powtórki, quiz, egzaminy, druk, plik na telefon | propozycje fiszek z Gemini |
| Dostępność | wszystkie analizy (pliki CSV z siatką H3, szybki model) | tylko podkład mapy |
| Osiedle | rysunek, bilans, wskaźniki, program, koszty, cień, przekrój, raport, eksporty | obszar z działek (ULDK), podkład i nakładki mapy |
| Przepisy | wgrane akty: wyszukiwarka, filtry, notatki, „Moje przepisy”, porównanie wersji | pytania do Gemini, wyszukiwanie aktów w API Sejmu |
| Teren | projekty, import, raporty, porównania, zmiana w czasie, formularz na telefon | podkład mapy na stronie projektu |
| Ceny | pliki RCN (czytane z dysku), wszystkie analizy transakcji | ceny GUS (API BDL), podkład mapy |
| Praca | godziny z PDF z tekstem, historia, Word z wklejonego tekstu… | …ale same notatki układa Gemini; zdjęcie grafiku przepisuje Gemini |

Bez sieci mapy pokazują puste tło — warstwy z Warsztatu (punkty,
tereny, heksagony) są nadal rysowane.

## Formularze na telefon (Teren i Fiszki)

Oba pliki HTML są samodzielne (bez internetu): dane zapisują w
IndexedDB przeglądarki telefonu, wyniki wracają do Warsztatu jako plik
JSON (pobranie albo „Udostępnij”).

### Android

Sprawdzone wcześniej (ETAPy 66, 74, 83): plik otwarty w Chrome albo
Firefoksie.

### iPhone (Safari) — przegląd kodu

| Funkcja w formularzu | Co robi kod | Ryzyko na iPhonie |
|---|---|---|
| zapis danych | IndexedDB, `navigator.storage.persist()` gdy jest | Safari może usuwać dane zapisane przez strony nieotwierane przez kilka dni (zasada WebKit dla stron internetowych; czy dotyczy pliku — do testu) → formularz na iPhonie pokazuje ostrzeżenie „eksportuj po każdym użyciu” |
| GPS | `watchPosition` z wysoką dokładnością | przeglądarki dają położenie tylko „bezpiecznym” stronom; Chromium traktuje plik jako bezpieczny, Safari — do testu. Przy odmowie formularz mówi, żeby wpisać współrzędne ręcznie |
| zdjęcie | `<input type="file" accept="image/*" capture>`, zmniejszenie na `<canvas>` do JPEG | format zdjęcia z aparatu (HEIC/JPEG) — do testu, czy obraz się wczytuje |
| eksport | link `download` do pliku z `Blob` | do testu, gdzie Safari zapisuje plik (Pobrane w aplikacji Pliki) |
| udostępnianie | `navigator.share({files})`, przycisk tylko gdy `canShare` | przycisk pojawia się sam, jeśli Safari to umie |
| komunikaty | rada „otwórz w Chrome” | na iOS każda przeglądarka używa silnika Safari — formularz na iPhonie radzi Safari i odsyła do Pomocy |

### Jak otworzyć plik na iPhonie

Najpewniejsze do sprawdzenia: wyślij plik HTML na telefon (AirDrop,
poczta, dysk), zapisz w aplikacji Pliki i otwórz go w Safari. Podgląd
pliku w samej aplikacji Pliki to nie Safari — może nie uruchomić
skryptów (do testu). Jeśli na iPhonie formularz nie działa z pliku,
zostaje wersja na serwerze z HTTPS (plan dalszy: Oracle Cloud, ETAP 250).

### Lista testów na iPhonie (do odhaczenia)

Formularz terenowy (projekt ze wzoru „Inwentaryzacja zieleni”):

- [ ] plik otwiera się w Safari i pokazuje pola formularza
- [ ] widać ostrzeżenie „iPhone: eksportuj wyniki po każdym użyciu”
- [ ] „📍” pyta o zgodę i podaje położenie z dokładnością; po odmowie — komunikat o ręcznym wpisaniu
- [ ] zdjęcie z aparatu i z galerii pokazuje podgląd
- [ ] zapisany punkt jest na liście po zamknięciu i ponownym otwarciu pliku
- [ ] „Eksportuj plik” zapisuje JSON (gdzie?); „Udostępnij” wysyła do poczty / AirDrop
- [ ] JSON importuje się w Warsztacie (Teren → projekt → Import)
- [ ] dane zostają po 1, 3 i 8 dniach bez otwierania pliku (zapisz wynik)

Fiszki na telefon:

- [ ] plik otwiera się w Safari, liczby „do powtórki dziś” się zgadzają
- [ ] fiszka z rysunkiem i z zasłoną wyświetla się poprawnie
- [ ] powtórka zapisuje wyniki; po ponownym otwarciu liczby się zgadzają
- [ ] eksport wyników i import w Warsztacie (Fiszki → Import wyników z telefonu)

Wynik testów dopisz w `docs/PROGRESS.md` przy ETAPie, w którym je zrobisz.
