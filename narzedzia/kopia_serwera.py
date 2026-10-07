"""Codzienna kopia danych na serwerze (ETAP 251) — uruchamia ją cron.

Ta sama kopia co automatyczna przy starcie (kopia.kopia_automatyczna,
sprawdzana po zapisie), ale co 1 dzień; zostaje ZOSTAW najnowszych.
Kopia jest na dysku serwera — kopię poza serwerem pobierasz w
przeglądarce: strona główna → „Pobierz kopię zapasową (ZIP)”.
"""

import os
import sys

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KATALOG)
os.chdir(KATALOG)

ZOSTAW = 14


def main():
    from config import Config
    from kopia import kopia_automatyczna

    sciezka = kopia_automatyczna(os.path.join(KATALOG, "instance"), Config.AUTO_KOPIA_FOLDER, co_ile_dni=1, zostaw=ZOSTAW)
    print(sciezka or "Kopia z ostatniej doby już jest.")


if __name__ == "__main__":
    main()
