#!/usr/bin/env bash
# Uruchamia Warsztat: serwer Flask na 127.0.0.1 + przeglądarka.
# Zamknięcie okna terminala (albo Ctrl+C) zatrzymuje serwer.

set -euo pipefail

# Katalog projektu = katalog, w którym leży ten skrypt (działa też z ikony).
cd "$(dirname "$(readlink -f "$0")")"

if [[ ! -x .venv/bin/python ]]; then
    echo "Brak środowiska .venv. Utwórz je raz:"
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    read -rp "Enter zamyka okno…"
    exit 1
fi

if [[ ! -f .env ]]; then
    echo "Brak pliku .env — tworzę go z .env.example (uzupełnij GEMINI_API_KEY)."
    cp .env.example .env
fi

# Ten sam port co w config.py: z .env, domyślnie 5000.
PORT=$(grep -E '^PORT=' .env | cut -d= -f2 | tr -d '[:space:]')
PORT=${PORT:-5000}
ADRES="http://127.0.0.1:${PORT}/"

.venv/bin/python app.py &
SERWER=$!
trap 'kill "$SERWER" 2>/dev/null' EXIT

# Czekamy, aż serwer zacznie odpowiadać (maks. ~10 s), potem przeglądarka.
for _ in $(seq 1 20); do
    if .venv/bin/python -c "import urllib.request; urllib.request.urlopen('$ADRES')" 2>/dev/null; then
        xdg-open "$ADRES" >/dev/null 2>&1 &
        break
    fi
    sleep 0.5
done

echo "Warsztat działa pod adresem $ADRES — zamknij to okno, żeby go zatrzymać."
wait "$SERWER"
