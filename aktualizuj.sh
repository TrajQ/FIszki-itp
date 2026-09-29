#!/usr/bin/env bash
# Aktualizacja Warsztatu z pobranego ZIP-a (ETAP 71).
#   ./aktualizuj.sh                       — najnowszy warsztat_etap*.zip z Pobranych
#   ./aktualizuj.sh ~/Pobrane/plik.zip    — wskazany ZIP
# Dane (instance/), klucze (.env) i środowisko (.venv/) zostają bez zmian;
# przed podmianą powstaje kopia zapasowa w ~/warsztat_kopie/.
#
# Całość jest w funkcji: bash wczytuje ją w całości przed wykonaniem, więc
# podmiana tego pliku przez aktualizację w trakcie nie psuje działania.

glowna() {
    set -euo pipefail
    cd "$(dirname "$(readlink -f "$0")")"
    python3 aktualizacja.py "$@"
}

glowna "$@"
exit $?
