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

## Gdy coś nie działa

- Ikona pyta, czy uruchomić / nic nie robi → prawy klik na ikonie →
  „Zezwól na uruchamianie” (albo ponownie `./zainstaluj_ikone.sh`).
- Po przeniesieniu katalogu projektu uruchom `./zainstaluj_ikone.sh`
  jeszcze raz — ikona zawiera ścieżkę bezwzględną.
- PDF się nie wyświetla → nad podglądem pojawia się czerwony komunikat z
  przyczyną; komunikaty serwera są w oknie terminala.
- Testy: `.venv/bin/pip install pytest && .venv/bin/python -m pytest -q`.
