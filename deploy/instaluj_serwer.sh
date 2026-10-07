#!/usr/bin/env bash
# Instalacja Warsztatu na serwerze Ubuntu (Oracle Cloud) — ETAP 251.
# Uruchom w katalogu z rozpakowanym Warsztatem:
#     bash deploy/instaluj_serwer.sh twoja-nazwa.duckdns.org
# Skrypt: pakiety, środowisko Pythona, .env (domena + hasło), usługa
# systemd z gunicorn, Caddy z HTTPS, porty 80/443 w zaporze, kopia z crona.
set -euo pipefail

DOMENA="${1:-}"
if [[ -z "$DOMENA" ]]; then
    echo "Podaj domenę, np.: bash deploy/instaluj_serwer.sh warsztat-patryk.duckdns.org"
    exit 1
fi
KATALOG="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
UZYTKOWNIK="$(whoami)"
cd "$KATALOG"

echo "== 1/7 Pakiety systemu"
sudo apt-get update -q
sudo apt-get install -y -q python3-venv python3-pip unzip curl debian-keyring debian-archive-keyring apt-transport-https gnupg

echo "== 2/7 Caddy (serwer HTTPS) z oficjalnego repozytorium"
if ! command -v caddy >/dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    sudo apt-get update -q
    sudo apt-get install -y -q caddy
fi

echo "== 3/7 Środowisko Pythona"
python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements-serwer.txt

echo "== 4/7 Plik .env: domena, hasło, klucz sesji"
[[ -f .env ]] || cp .env.example .env
if grep -q '^WARSZTAT_DOMENA=' .env; then
    sed -i "s|^WARSZTAT_DOMENA=.*|WARSZTAT_DOMENA=$DOMENA|" .env
else
    echo "WARSZTAT_DOMENA=$DOMENA" >> .env
fi
if ! grep -q '^WARSZTAT_HASLO_HASH=.' .env; then
    .venv/bin/python narzedzia/ustaw_haslo.py
fi
chmod 600 .env

echo "== 5/7 Usługa systemd (gunicorn na 127.0.0.1:8000)"
sed -e "s|UZYTKOWNIK|$UZYTKOWNIK|" -e "s|KATALOG|$KATALOG|g" deploy/warsztat.service | sudo tee /etc/systemd/system/warsztat.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now warsztat
sudo systemctl restart warsztat

echo "== 6/7 Caddy i zapora (porty 80 i 443)"
sed "s|{\$WARSZTAT_DOMENA}|$DOMENA|" deploy/Caddyfile | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy || sudo systemctl restart caddy
# Obrazy Ubuntu w Oracle Cloud mają własne reguły iptables — otwieramy 80 i 443
for PORT in 80 443; do
    if ! sudo iptables -C INPUT -p tcp --dport "$PORT" -m state --state NEW -j ACCEPT 2>/dev/null; then
        sudo iptables -I INPUT 5 -p tcp --dport "$PORT" -m state --state NEW -j ACCEPT
    fi
done
if command -v netfilter-persistent >/dev/null; then
    sudo netfilter-persistent save
fi

echo "== 7/7 Kopia danych co 6 godzin (zostaje 14 kopii w ~/warsztat_kopie)"
LINIA="0 */6 * * * cd $KATALOG && .venv/bin/python narzedzia/kopia_serwera.py >/dev/null 2>&1"
( crontab -l 2>/dev/null | grep -v 'narzedzia/kopia_serwera.py' ; echo "$LINIA" ) | crontab -

echo
echo "Gotowe. Otwórz https://$DOMENA (pierwszy certyfikat Caddy pobiera do minuty)."
echo "Stan: sudo systemctl status warsztat caddy   |   Dziennik: journalctl -u warsztat -u caddy -n 50"
