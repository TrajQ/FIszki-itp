#!/usr/bin/env bash
# Tworzy ikonę Warsztatu na pulpicie i w menu aplikacji (Linux Mint / Cinnamon).
# Uruchom raz, z katalogu projektu: ./zainstaluj_ikone.sh
# Plik .desktop wymaga ścieżki bezwzględnej, dlatego jest generowany tutaj,
# a nie trzymany w repo.

set -euo pipefail

KATALOG="$(dirname "$(readlink -f "$0")")"
PULPIT="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Pulpit")"
MENU="$HOME/.local/share/applications"

chmod +x "$KATALOG/uruchom.sh"
mkdir -p "$MENU" "$PULPIT"

TRESC="[Desktop Entry]
Type=Application
Name=Warsztat
Comment=Warsztat gospodarki przestrzennej — lokalnie na 127.0.0.1
Exec=\"$KATALOG/uruchom.sh\"
Path=$KATALOG
Icon=applications-science
Terminal=true
Categories=Education;Science;
"

for PLIK in "$MENU/warsztat.desktop" "$PULPIT/warsztat.desktop"; do
    printf '%s' "$TRESC" > "$PLIK"
    chmod +x "$PLIK"
    # Nemo (menedżer plików Minta) uruchamia ikonę z pulpitu bez pytania
    # dopiero, gdy jest oznaczona jako zaufana.
    gio set "$PLIK" metadata::trusted true 2>/dev/null || true
done

echo "Gotowe: ikona „Warsztat” na pulpicie ($PULPIT) i w menu."
