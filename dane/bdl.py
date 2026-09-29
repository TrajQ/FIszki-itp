"""Klient API Banku Danych Lokalnych GUS (BDL), wersja v1.

Dokumentacja: https://api.stat.gov.pl/Home/BdlApi
Klucz (nagłówek X-ClientId) jest opcjonalny — bez niego API działa, ale
z niższymi limitami zapytań. Klucz czytamy z GUS_BDL_API_KEY w .env.

Poziomy jednostek w BDL: 0 Polska, 1 makroregion, 2 województwo,
3 region, 4 podregion, 5 powiat, 6 gmina.

Identyfikator jednostki BDL ma 12 znaków i zawiera w sobie kod TERYT,
np. Kraków „011212161011”:
    01  makroregion
    12  województwo (TERYT)
    121 region + podregion
    61  powiat (TERYT)
    01  gmina (TERYT)
    1   rodzaj gminy (1 miejska, 2 wiejska, 3 miejsko-wiejska)
Stąd 7-znakowy TERYT gminy = woj + powiat + gmina + rodzaj = „1261011”.
"""

from dataclasses import dataclass

import requests

from config import Config
from dane.siec import opis_bledu_sieci

URL_BDL = "https://bdl.stat.gov.pl/api/v1"
ROZMIAR_STRONY = 100
POZIOM_WOJEWODZTWO = 2
POZIOM_GMINA = 6
RODZAJE_GMIN = {"1", "2", "3"}  # 4 i 5 to części gmin miejsko-wiejskich


class BladBDL(Exception):
    """Błąd komunikacji z API BDL albo nieoczekiwany format odpowiedzi."""


@dataclass
class Zmienna:
    id: int
    nazwa: str
    jednostka: str


@dataclass
class Jednostka:
    bdl_id: str
    nazwa: str
    teryt: str


@dataclass
class Wartosc:
    bdl_id: str
    teryt: str
    nazwa: str
    wartosc: float


def teryt_z_id_bdl(bdl_id: str) -> str:
    """Wyciąga kod TERYT z 12-znakowego identyfikatora BDL.

    Dla gminy zwraca 7 znaków (woj+pow+gm+rodzaj), dla województwa 2.
    """
    if len(bdl_id) != 12 or not bdl_id.isdigit():
        raise BladBDL(f"Nieoczekiwany identyfikator jednostki BDL: {bdl_id}")
    woj = bdl_id[2:4]
    if bdl_id[4:] == "00000000":
        return woj
    return woj + bdl_id[7:9] + bdl_id[9:11] + bdl_id[11]


def szukaj_zmiennych(fraza: str) -> list[Zmienna]:
    """Zmienne BDL, których nazwa zawiera frazę, dostępne na poziomie gmin."""
    dane = _pobierz(
        "/variables/search", {"name": fraza, "level": POZIOM_GMINA, "page-size": 50}
    )
    return [_zmienna_z_json(z) for z in dane.get("results", [])]


def pobierz_zmienna(zmienna_id: int) -> Zmienna:
    return _zmienna_z_json(_pobierz(f"/variables/{zmienna_id}", {}))


def wojewodztwa() -> list[Jednostka]:
    dane = _pobierz("/units", {"level": POZIOM_WOJEWODZTWO, "page-size": ROZMIAR_STRONY})
    return sorted(
        (
            Jednostka(bdl_id=j["id"], nazwa=j["name"].lower(), teryt=teryt_z_id_bdl(j["id"]))
            for j in dane.get("results", [])
        ),
        key=lambda j: j.teryt,
    )


def wartosci_dla_gmin(zmienna_id: int, rok: int, wojewodztwo_bdl_id: str) -> list[Wartosc]:
    """Wartości zmiennej w danym roku dla wszystkich gmin województwa.

    Gminy bez wartości (brak danych) są pomijane.
    """
    wyniki = []
    strona = 0
    while True:
        dane = _pobierz(
            f"/data/by-variable/{zmienna_id}",
            {
                "unit-level": POZIOM_GMINA,
                "unit-parent-id": wojewodztwo_bdl_id,
                "year": rok,
                "page-size": ROZMIAR_STRONY,
                "page": strona,
            },
        )
        for jednostka in dane.get("results", []):
            if jednostka["id"][-1] not in RODZAJE_GMIN:
                continue
            wartosc = _wartosc_z_roku(jednostka.get("values", []), rok)
            if wartosc is None:
                continue
            wyniki.append(
                Wartosc(
                    bdl_id=jednostka["id"],
                    teryt=teryt_z_id_bdl(jednostka["id"]),
                    nazwa=jednostka["name"],
                    wartosc=wartosc,
                )
            )

        wszystkich = dane.get("totalRecords", 0)
        strona += 1
        if strona * ROZMIAR_STRONY >= wszystkich or not dane.get("results"):
            break
    return wyniki


def wartosci_dla_wojewodztw(zmienna_id: int, rok: int) -> list[Wartosc]:
    """Wartości zmiennej w danym roku dla wszystkich 16 województw (ETAP 52)."""
    dane = _pobierz(
        f"/data/by-variable/{zmienna_id}",
        {"unit-level": POZIOM_WOJEWODZTWO, "year": rok, "page-size": ROZMIAR_STRONY},
    )
    wyniki = []
    for jednostka in dane.get("results", []):
        wartosc = _wartosc_z_roku(jednostka.get("values", []), rok)
        if wartosc is None:
            continue
        wyniki.append(
            Wartosc(
                bdl_id=jednostka["id"],
                teryt=teryt_z_id_bdl(jednostka["id"]),
                nazwa=jednostka["name"].lower(),
                wartosc=wartosc,
            )
        )
    return wyniki


def szereg_gminy(zmienna_id: int, gmina_bdl_id: str) -> list[dict]:
    """Wartości zmiennej dla jednej gminy we wszystkich dostępnych latach:
    [{"rok": 2010, "wartosc": 123.0}, ...] rosnąco po roku (braki pominięte)."""
    teryt_z_id_bdl(gmina_bdl_id)  # walidacja formatu identyfikatora
    dane = _pobierz(f"/data/by-unit/{gmina_bdl_id}", {"var-id": zmienna_id})
    szereg = []
    for zmienna in dane.get("results", []):
        if str(zmienna.get("id")) != str(zmienna_id):
            continue
        for w in zmienna.get("values", []):
            if w.get("val") is None:
                continue
            try:
                szereg.append({"rok": int(w["year"]), "wartosc": float(w["val"])})
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(szereg, key=lambda x: x["rok"])


def _wartosc_z_roku(wartosci: list[dict], rok: int) -> float | None:
    for w in wartosci:
        if str(w.get("year")) == str(rok) and w.get("val") is not None:
            return float(w["val"])
    return None


def _zmienna_z_json(z: dict) -> Zmienna:
    # Nazwa zmiennej w BDL jest rozbita na poziomy n1..n5 (od ogólnego do
    # szczegółowego); łączymy te, które są wypełnione.
    czesci = [z.get(f"n{i}") for i in range(1, 6)]
    nazwa = " — ".join(c for c in czesci if c)
    return Zmienna(id=int(z["id"]), nazwa=nazwa, jednostka=z.get("measureUnitName") or "")


def _pobierz(sciezka: str, parametry: dict) -> dict:
    naglowki = {"Accept": "application/json"}
    if Config.GUS_BDL_API_KEY:
        naglowki["X-ClientId"] = Config.GUS_BDL_API_KEY
    try:
        odpowiedz = requests.get(
            URL_BDL + sciezka,
            params={**parametry, "format": "json", "lang": "pl"},
            headers=naglowki,
            timeout=30,
        )
        if odpowiedz.status_code == 429:
            raise BladBDL("Przekroczono limit zapytań BDL — spróbuj za chwilę (albo dodaj GUS_BDL_API_KEY).")
        if odpowiedz.status_code == 404:
            raise BladBDL("BDL: nie znaleziono (sprawdź identyfikator zmiennej lub jednostki).")
        odpowiedz.raise_for_status()
        return odpowiedz.json()
    except requests.RequestException as e:
        raise BladBDL(f"Błąd połączenia z API BDL (GUS): {opis_bledu_sieci(e)}.") from e
    except ValueError as e:
        raise BladBDL(f"API BDL zwróciło niepoprawny JSON: {e}") from e
