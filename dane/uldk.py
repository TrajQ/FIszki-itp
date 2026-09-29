"""Klient krajowej usługi ULDK (Usługa Lokalizacji Działek Katastralnych).

Usługa jest publiczna i bezkluczowa (uldk.gugik.gov.pl). Zwraca działkę
ewidencyjną pod wskazanym punktem — używana przez moduł mpzp do znalezienia
działki pod kliknięciem na mapie, zanim sprawdzimy jej przeznaczenie w WFS
gminy.
"""

import re
from dataclasses import dataclass

import requests
from shapely import wkt as shapely_wkt
from shapely.geometry.base import BaseGeometry

URL_ULDK = "https://uldk.gugik.gov.pl/service.php"


class BladULDK(Exception):
    """Błąd komunikacji z ULDK albo nieparsowalna odpowiedź."""


@dataclass
class Dzialka:
    id: str
    geometria: BaseGeometry
    teryt_gminy: str


def znajdz_dzialke(lat: float, lon: float) -> Dzialka | None:
    """Zwraca działkę pod punktem (lat, lon) albo None, gdy nic tam nie ma.

    Podnosi BladULDK przy błędzie sieci albo nieoczekiwanym formacie
    odpowiedzi usługi.
    """
    try:
        odpowiedz = requests.get(
            URL_ULDK,
            params={
                "request": "GetParcelByXY",
                "xy": f"{lon},{lat},4326",
                "result": "id,geom_wkt",
                "srid": "4326",
            },
            timeout=10,
        )
        odpowiedz.raise_for_status()
    except requests.RequestException as e:
        raise BladULDK(f"Błąd połączenia z ULDK: {e}") from e

    return _sparsuj_odpowiedz(odpowiedz.text)


# Identyfikator działki ewidencyjnej: TERYT jednostki ewidencyjnej
# (6 cyfr + „_” + cyfra rodzaju), obręb i numer, np. 306401_1.0051.AR_18.14
WZOR_ID_DZIALKI = re.compile(r"^\d{6}_\d\.\d{4}\.\S+$")


def znajdz_dzialke_po_id(dzialka_id: str) -> Dzialka | None:
    """Zwraca działkę o podanym identyfikatorze albo None, gdy jej nie ma.

    Podnosi ValueError dla identyfikatora w złym formacie i BladULDK przy
    błędzie sieci albo nieoczekiwanej odpowiedzi.
    """
    dzialka_id = dzialka_id.strip()
    if not WZOR_ID_DZIALKI.match(dzialka_id):
        raise ValueError(
            "Identyfikator działki ma postać np. 306401_1.0051.AR_18.14 "
            "(TERYT jednostki ewidencyjnej, obręb, numer)."
        )
    try:
        odpowiedz = requests.get(
            URL_ULDK,
            params={
                "request": "GetParcelById",
                "id": dzialka_id,
                "result": "id,geom_wkt",
                "srid": "4326",
            },
            timeout=10,
        )
        odpowiedz.raise_for_status()
    except requests.RequestException as e:
        raise BladULDK(f"Błąd połączenia z ULDK: {e}") from e

    return _sparsuj_odpowiedz(odpowiedz.text)


def _sparsuj_odpowiedz(tekst: str) -> Dzialka | None:
    linie = tekst.strip().splitlines()
    if not linie:
        raise BladULDK("Pusta odpowiedź ULDK.")

    kod = linie[0].strip()
    if kod.startswith("-1"):
        return None
    if kod != "0":
        raise BladULDK(f"ULDK zwrócił błąd: {tekst.strip()}")

    if len(linie) < 2 or "|" not in linie[1]:
        raise BladULDK(f"Nieoczekiwany format odpowiedzi ULDK: {tekst.strip()}")

    dzialka_id, geom_wkt = linie[1].split("|", 1)
    if "_" not in dzialka_id:
        raise BladULDK(f"Nieoczekiwany format identyfikatora działki: {dzialka_id}")
    teryt_gminy = dzialka_id.split("_", 1)[0]

    wkt_bez_srid = geom_wkt.split(";", 1)[-1]
    try:
        geometria = shapely_wkt.loads(wkt_bez_srid)
    except Exception as e:
        raise BladULDK(f"Nie udało się sparsować geometrii działki: {e}") from e

    return Dzialka(id=dzialka_id, geometria=geometria, teryt_gminy=teryt_gminy)
