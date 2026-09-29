# Uruchomienie na Linux Mint

## Raz, przy pierwszej instalacji

```bash
sudo apt install python3-venv git
python3 --version            # wymagany Python 3.11+ (Mint 22 ma 3.12)

git clone https://github.com/TrajQ/FIszki-itp.git ~/warsztat
cd ~/warsztat
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
nano .env                    # GEMINI_API_KEY, losowy SECRET_KEY

./zainstaluj_ikone.sh        # ikona „Warsztat” na pulpicie i w menu
```

## Na co dzień

Dwuklik w ikonę „Warsztat” na pulpicie. Otworzy się okno terminala
(serwer) i przeglądarka z aplikacją. Zamknięcie okna terminala zatrzymuje
aplikację.

Bez ikony: `cd ~/warsztat && ./uruchom.sh`.

## Aktualizacja

Zamknij Warsztat (okno terminala), pobierz nowy ZIP do katalogu Pobrane
i uruchom w katalogu projektu:

```bash
./aktualizuj.sh                        # najnowszy warsztat_etap*.zip z Pobranych
./aktualizuj.sh ~/Pobrane/plik.zip     # albo wskazany ZIP
```

Skrypt najpierw robi kopię zapasową (kod, `instance/`, `.env`) w
`~/warsztat_kopie/`, potem podmienia pliki programu, usuwa pliki, których
nie ma w nowej wersji, i doinstalowuje zależności. Dane (`instance/`),
klucze (`.env`) i środowisko (`.venv/`) zostają bez zmian. W
przeglądarce odśwież stronę przez Ctrl+Shift+R.

Powrót do poprzedniej wersji: rozpakuj kopię z `~/warsztat_kopie/`
(zawiera katalog `warsztat/` z kodem i danymi sprzed aktualizacji).

Z gita: `git pull` — `uruchom.sh` sam doinstaluje zależności.

## Klucze w `.env`

- `GEMINI_API_KEY` — szkice fiszek i opisy w atlasie (bez klucza reszta
  działa).
- `GUS_BDL_API_KEY` — opcjonalny; bez niego API GUS działa z niższym
  limitem zapytań. Klucz: https://api.stat.gov.pl/Home/BdlApi

## Gdy coś nie działa

- Ikona pyta, czy uruchomić / nic nie robi → prawy klik na ikonie →
  „Zezwól na uruchamianie” (albo ponownie `./zainstaluj_ikone.sh`).
- Po przeniesieniu katalogu projektu uruchom `./zainstaluj_ikone.sh`
  jeszcze raz — ikona zawiera ścieżkę bezwzględną.
- PDF się nie wyświetla → nad podglądem pojawia się czerwony komunikat z
  przyczyną; komunikaty serwera są w oknie terminala.
- Testy: `.venv/bin/pip install pytest && .venv/bin/python -m pytest -q`.

## Kopia zapasowa

Strona główna → „Pobierz kopię zapasową (ZIP)”. W ZIP-ie jest folder
`instance/` (fiszki, powtórki, historia działek, PDF-y, pliki wyników) i
plik `PRZYWRACANIE.txt`. Przywracanie: zamknij aplikację, zmień nazwę
obecnego `instance/` na `instance_stary/`, rozpakuj ZIP w katalogu
projektu, uruchom aplikację.
