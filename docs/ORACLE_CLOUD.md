# Warsztat w chmurze: Oracle Cloud + HTTPS (ETAP 251)

Warsztat na własnym serwerze, dostępny z telefonu (także iPhone) i z
każdego komputera pod adresem `https://twoja-nazwa.duckdns.org`, po
zalogowaniu jednym hasłem. Lokalna wersja na PC działa dalej bez zmian.

Jak to jest zbudowane:

```
przeglądarka ──HTTPS──▶ Caddy (porty 80/443, certyfikat Let's Encrypt)
                          └──▶ gunicorn + Warsztat (tylko 127.0.0.1:8000)
```

Warsztat dalej słucha tylko na 127.0.0.1 — z internetu widać wyłącznie
Caddy. Każda strona wymaga zalogowania (hasło znasz tylko Ty; na
serwerze jest jego skrót). Po 5 złych hasłach z jednego adresu
logowanie z niego czeka 15 minut.

Nazwy przycisków w panelach Oracle i DuckDNS mogą się nieco różnić od
opisanych — szukaj podobnych. Warunki darmowego progu sprawdź na
stronie Oracle przed założeniem konta.

---

## Krok 1. Konto i maszyna w Oracle Cloud (ok. 20 min, raz)

1. Załóż konto na oracle.com/cloud („Free Tier”). Oracle prosi o kartę
   do weryfikacji.
2. W panelu: **Compute → Instances → Create instance**.
   - Nazwa: `warsztat`.
   - **Image**: kliknij **Change image** → Canonical **Ubuntu 24.04**
     (nie Oracle Linux — domyślny obraz; skrypt instalacji jest dla
     Ubuntu, a Warsztat wymaga Pythona 3.11+, którego nie ma Ubuntu 22.04).
     Na Ubuntu użytkownik to `ubuntu`, na Oracle Linux — `opc`.
   - **Shape**: wybierz kształt oznaczony jako „Always Free-eligible”
     (np. Ampere A1 z 1 OCPU i 6 GB pamięci — wystarczy z zapasem).
   - **Networking**: zostaw domyślną sieć, zaznacz przypisanie
     publicznego adresu IPv4.
   - **Add SSH keys → Generate a key pair for me → Save private key**
     — zapisz plik klucza (np. `~/Pobrane/ssh-key.key`). Bez niego nie
     wejdziesz na serwer.
3. **Create**. Po chwili zapisz **Public IP address** maszyny (np.
   `141.145.x.x`).
4. Otwórz porty 80 i 443 w sieci Oracle: na stronie maszyny kliknij
   podsieć (**Subnet**) → **Security Lists** → domyślna lista →
   **Add Ingress Rules**, dwa razy:
   - Source CIDR `0.0.0.0/0`, IP Protocol `TCP`, Destination Port `80`
   - Source CIDR `0.0.0.0/0`, IP Protocol `TCP`, Destination Port `443`

## Krok 2. Darmowa domena w DuckDNS (5 min, raz)

HTTPS potrzebuje nazwy domeny. DuckDNS daje darmową subdomenę.

1. Wejdź na duckdns.org i zaloguj się (np. kontem Google albo GitHub).
2. Wpisz nazwę, np. `warsztat-patryk`, kliknij **add domain**.
3. W polu **current ip** wpisz Public IP maszyny z kroku 1 i kliknij
   **update ip**.

Twój adres to `warsztat-patryk.duckdns.org` (z Twoją nazwą).

## Krok 3. Wgranie Warsztatu na serwer (z PC, terminal)

```bash
chmod 600 ~/Pobrane/ssh-key.key
scp -i ~/Pobrane/ssh-key.key ~/Pobrane/warsztat_etap251_*.zip ubuntu@IP_MASZYNY:~
ssh -i ~/Pobrane/ssh-key.key ubuntu@IP_MASZYNY
```

(`IP_MASZYNY` zamień na adres z kroku 1. Przy pierwszym połączeniu
odpowiedz `yes`.)

## Krok 4. Instalacja (na serwerze, po `ssh`)

```bash
cd ~
unzip -o ~/warsztat_etap251_*.zip      # ZIP ma w środku folder warsztat/ — powstaje ~/warsztat
cd ~/warsztat
bash deploy/instaluj_serwer.sh warsztat-patryk.duckdns.org
```

Skrypt instaluje pakiety i Caddy, przygotowuje Pythona, **pyta dwa
razy o hasło do Warsztatu** (co najmniej 12 znaków), uruchamia usługę,
otwiera porty w zaporze serwera i ustawia kopię danych co 6 godzin.
Trwa kilka minut.

Klucz Gemini (opcjonalnie):

```bash
nano ~/warsztat/.env        # GEMINI_API_KEY=… , zapisz: Ctrl+O, Enter, Ctrl+X
sudo systemctl restart warsztat
```

## Krok 5. Gotowe

Otwórz `https://warsztat-patryk.duckdns.org` na komputerze albo
telefonie i zaloguj się. Na iPhonie: Safari → Udostępnij → „Do ekranu
początkowego” — Warsztat będzie jak aplikacja.

**Formularz Terenu i Fiszki na telefon** możesz otworzyć wprost z
serwera (strona projektu → „Pobierz formularz na telefon” → otwórz w
przeglądarce). Strona z HTTPS dostaje GPS bez problemów z plikiem
otwieranym z dysku. Dane zapisują się w telefonie — eksportuj je po
każdym wyjściu w teren, jak dotąd.

---

## Na co dzień

| Co | Jak |
|---|---|
| zmiana hasła | `cd ~/warsztat && .venv/bin/python narzedzia/ustaw_haslo.py && sudo systemctl restart warsztat` |
| aktualizacja do nowego ZIP-a | z PC: `scp -i … nowy.zip ubuntu@IP:~`, na serwerze: `cd ~/warsztat && bash deploy/aktualizuj_serwer.sh ~/nowy.zip` |
| czy działa | `sudo systemctl status warsztat caddy` |
| co się stało (błędy) | `journalctl -u warsztat -u caddy -n 50` oraz `~/warsztat/instance/logi/warsztat.log` |
| kopie na serwerze | `~/warsztat_kopie/` (co 6 h, 14 ostatnich) |
| kopia poza serwerem | w przeglądarce: strona główna → „Pobierz kopię zapasową (ZIP)” — rób co jakiś czas |
| wylogowanie | „Wyloguj” w menu (sesja trwa 30 dni) |

## Gdy coś nie działa

- **Strona się nie otwiera / przekroczony czas**: sprawdź reguły 80 i
  443 w Security List (krok 1.4) i czy IP w DuckDNS jest aktualne.
- **Błąd certyfikatu zaraz po instalacji**: Caddy pobiera certyfikat do
  minuty; `journalctl -u caddy -n 50` pokaże przyczynę (najczęściej
  domena nie wskazuje jeszcze na IP maszyny albo zamknięty port 80).
- **„Nieznany nagłówek Host”**: domena w `.env` (`WARSZTAT_DOMENA`) różni
  się od adresu w przeglądarce — popraw i `sudo systemctl restart warsztat`.
- **Usługa nie startuje**: `journalctl -u warsztat -n 50` — w trybie
  serwerowym Warsztat nie wystartuje bez hasła i losowego `SECRET_KEY`
  (oba ustawia `narzedzia/ustaw_haslo.py`).
