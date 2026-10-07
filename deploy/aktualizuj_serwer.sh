#!/usr/bin/env bash
# Aktualizacja Warsztatu na serwerze (ETAP 251):
#     bash deploy/aktualizuj_serwer.sh ~/warsztat_etapNNN.zip
# Kopia (kod, instance/, .env) w ~/warsztat_kopie, podmiana plików
# programu (aktualizuj.sh — dane i .env zostają), zależności, restart.
set -euo pipefail
ZIP="${1:?Podaj plik ZIP z nową wersją}"
KATALOG="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
cd "$KATALOG"
sudo systemctl stop warsztat
bash ./aktualizuj.sh "$ZIP"
.venv/bin/pip install -q --disable-pip-version-check -r requirements-serwer.txt
sudo systemctl start warsztat
echo "Zaktualizowano i uruchomiono ponownie."
