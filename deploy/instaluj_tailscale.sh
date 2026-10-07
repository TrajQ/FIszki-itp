#!/usr/bin/env bash
# Warsztat na serwerze z Tailscale — Oracle Linux 9 (ETAP 252).
# Uruchom w katalogu z rozpakowanym Warsztatem:
#     bash deploy/instaluj_tailscale.sh
# Warsztat (gunicorn) słucha tylko na 127.0.0.1:PORT, a HTTPS z
# certyfikatem *.ts.net daje Tailscale Serve na osobnym porcie
# (PORT_HTTPS) — tylko dla Twoich urządzeń w Tailscale. Zapory, portów
# w Oracle ani innych usług na serwerze skrypt nie zmienia.
set -euo pipefail

PORT="${WARSZTAT_PORT:-8002}"
PORT_HTTPS="${WARSZTAT_PORT_HTTPS:-8443}"
KATALOG="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
UZYTKOWNIK="$(whoami)"
cd "$KATALOG"

echo "== 1/6 Sprawdzenie serwera"
command -v tailscale >/dev/null || { echo "Brak Tailscale na serwerze."; exit 1; }
PYTHON=""
for p in python3.13 python3.12 python3.11 python3; do
    if command -v "$p" >/dev/null && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then PYTHON="$(command -v "$p")"; break; fi
done
[[ -n "$PYTHON" ]] || { echo "Brak Pythona 3.11+ (na Oracle Linux 9: sudo dnf install -y python3.12)."; exit 1; }
echo "Python: $PYTHON"
if sudo ss -tln | grep -q "127.0.0.1:$PORT \|0.0.0.0:$PORT \|\[::\]:$PORT "; then
    if ! systemctl is-active --quiet warsztat; then
        echo "Port $PORT jest zajęty przez inny program — uruchom z innym: WARSZTAT_PORT=8003 bash deploy/instaluj_tailscale.sh"; exit 1
    fi
fi
SERVE="$(sudo tailscale serve status 2>/dev/null || true)"
if echo "$SERVE" | grep -q ":$PORT_HTTPS" && ! echo "$SERVE" | grep -q "127.0.0.1:$PORT"; then
    echo "Port HTTPS $PORT_HTTPS w Tailscale jest już używany przez coś innego — podaj inny: WARSZTAT_PORT_HTTPS=10000 bash deploy/instaluj_tailscale.sh"; exit 1
fi
DOMENA="$(sudo tailscale status --json | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
[[ -n "$DOMENA" ]] || { echo "Nie odczytałem nazwy serwera w Tailscale (MagicDNS włączony?)."; exit 1; }
echo "Adres: https://$DOMENA:$PORT_HTTPS"

echo "== 2/6 Środowisko Pythona (.venv)"
if ! "$PYTHON" -m venv .venv; then
    # Oracle Linux: venv potrzebuje pakietu z pip dla tej wersji Pythona
    sudo dnf install -y -q "$(basename "$PYTHON")-pip"
    "$PYTHON" -m venv .venv
fi
.venv/bin/pip install -q --disable-pip-version-check --upgrade pip
.venv/bin/pip install -q --disable-pip-version-check -r requirements-serwer.txt

echo "== 3/6 Plik .env: adres i hasło"
[[ -f .env ]] || cp .env.example .env
if grep -q '^WARSZTAT_DOMENA=' .env; then sed -i "s|^WARSZTAT_DOMENA=.*|WARSZTAT_DOMENA=$DOMENA|" .env; else echo "WARSZTAT_DOMENA=$DOMENA" >> .env; fi
if ! grep -q '^WARSZTAT_HASLO_HASH=.' .env; then .venv/bin/python narzedzia/ustaw_haslo.py; fi
chmod 600 .env

echo "== 4/6 Usługa systemd warsztat (gunicorn na 127.0.0.1:$PORT)"
# Start przez /bin/bash — jak inne usługi na tym serwerze (SELinux pozwala uruchomić bash)
sudo tee /etc/systemd/system/warsztat.service >/dev/null <<UNIT
[Unit]
Description=Warsztat (Flask przez gunicorn, za Tailscale Serve)
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
User=$UZYTKOWNIK
WorkingDirectory=$KATALOG
ExecStart=/bin/bash -c 'cd $KATALOG && exec .venv/bin/gunicorn --workers 1 --threads 4 --timeout 180 --bind 127.0.0.1:$PORT wsgi:app'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now warsztat
sudo systemctl restart warsztat
sleep 3
if ! curl -s -o /dev/null -H "Host: $DOMENA" "http://127.0.0.1:$PORT/logowanie"; then
    echo "Warsztat nie odpowiada — dziennik: journalctl -u warsztat -n 50"; exit 1
fi

echo "== 5/6 Tailscale Serve: https://$DOMENA:$PORT_HTTPS → 127.0.0.1:$PORT (inne wpisy zostają)"
sudo tailscale serve --bg --https="$PORT_HTTPS" "http://127.0.0.1:$PORT"

echo "== 6/6 Kopia danych co 6 godzin (14 ostatnich w ~/warsztat_kopie)"
LINIA="0 */6 * * * cd $KATALOG && .venv/bin/python narzedzia/kopia_serwera.py >/dev/null 2>&1"
( crontab -l 2>/dev/null | grep -v 'narzedzia/kopia_serwera.py' ; echo "$LINIA" ) | crontab -

echo
echo "Gotowe. Na urządzeniu z Tailscale otwórz: https://$DOMENA:$PORT_HTTPS"
echo "Stan: sudo systemctl status warsztat   |   Dziennik: journalctl -u warsztat -n 50   |   sudo tailscale serve status"
