"""Klient WFS 2.0 warstwy MPZP obsługiwanej gminy (zob. mpzp/gminy.py).

Warstwa jest pobierana w całości i indeksowana lokalnie
(shapely.STRtree) zamiast polegać na filtrowaniu przestrzennym po
stronie WFS — w rozpoznaniu do ETAPu 3 filtry BBOX/Intersects tej usługi
konsekwentnie zwracały 0 wyników mimo testowania punktami leżącymi
wewnątrz znanych wielokątów (zob. spec ETAPu 3), więc pobieramy raz i
sprawdzamy punkt-w-wielokącie sami.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import requests
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from .gminy import Gmina

NS_GML = "{http://www.opengis.net/gml/3.2}"
NS_WFS = "{http://www.opengis.net/wfs/2.0}"

ROZMIAR_STRONY = 10000


class BladWFS(Exception):
    """Błąd komunikacji z WFS gminy albo nieparsowalna odpowiedź."""


@dataclass
class Wydzielenie:
    geometria: BaseGeometry
    atrybuty: dict = field(default_factory=dict)


class _WarstwaGminy:
    def __init__(self, wydzielenia: list[Wydzielenie]):
        self.wydzielenia = wydzielenia
        self.drzewo = STRtree([w.geometria for w in wydzielenia])


_cache: dict[str, _WarstwaGminy] = {}


def znajdz_przeznaczenie(gmina: Gmina, punkt: Point) -> Wydzielenie | None:
    """Zwraca wydzielenie MPZP zawierające punkt, albo None.

    Pierwsze wywołanie dla danej gminy pobiera całą warstwę WFS (blokująco)
    i buduje indeks przestrzenny; kolejne wywołania korzystają z cache'a w
    pamięci procesu. Podnosi BladWFS przy błędzie sieci albo
    nieparsowalnej odpowiedzi.
    """
    warstwa = _cache.get(gmina.teryt_prefiks)
    if warstwa is None:
        warstwa = _pobierz_warstwe(gmina)
        _cache[gmina.teryt_prefiks] = warstwa

    for indeks in warstwa.drzewo.query(punkt):
        wydzielenie = warstwa.wydzielenia[indeks]
        if wydzielenie.geometria.covers(punkt):
            return wydzielenie
    return None


def odswiez(gmina: Gmina) -> None:
    """Wymusza ponowne pobranie całej warstwy WFS dla gminy."""
    _cache[gmina.teryt_prefiks] = _pobierz_warstwe(gmina)


def _pobierz_warstwe(gmina: Gmina) -> _WarstwaGminy:
    wszystkie: list[Wydzielenie] = []
    start_index = 0
    while True:
        tekst = _pobierz_strone(gmina, start_index)
        strona, dopasowania, zwrocone = _sparsuj_kolekcje(tekst, gmina.pole_geometrii)
        wszystkie.extend(strona)
        start_index += zwrocone
        if zwrocone == 0 or start_index >= dopasowania:
            break
    return _WarstwaGminy(wszystkie)


def _pobierz_strone(gmina: Gmina, start_index: int) -> str:
    try:
        odpowiedz = requests.get(
            gmina.wfs_url,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": gmina.type_name,
                "srsName": "EPSG:4326",
                "count": ROZMIAR_STRONY,
                "startIndex": start_index,
            },
            timeout=120,
        )
        odpowiedz.raise_for_status()
    except requests.RequestException as e:
        raise BladWFS(f"Błąd połączenia z WFS gminy {gmina.nazwa}: {e}") from e
    return odpowiedz.text


def _sparsuj_kolekcje(tekst: str, pole_geometrii: str):
    try:
        root = ET.fromstring(tekst)
    except ET.ParseError as e:
        raise BladWFS(f"Nie udało się sparsować odpowiedzi WFS: {e}") from e

    dopasowania = int(root.get("numberMatched", "0"))
    zwrocone = int(root.get("numberReturned", "0"))

    wydzielenia = []
    for member in root.findall(f"{NS_WFS}member"):
        for cecha in member:
            wydzielenie = _sparsuj_cechy(cecha, pole_geometrii)
            if wydzielenie is not None:
                wydzielenia.append(wydzielenie)
    return wydzielenia, dopasowania, zwrocone


def _sparsuj_cechy(cecha, pole_geometrii: str) -> Wydzielenie | None:
    atrybuty = {}
    geometria = None
    for dziecko in cecha:
        nazwa_pola = dziecko.tag.split("}", 1)[-1]
        if nazwa_pola == pole_geometrii:
            geometria = _sparsuj_geometrie(dziecko)
        else:
            atrybuty[nazwa_pola] = (dziecko.text or "").strip()

    if geometria is None:
        return None
    return Wydzielenie(geometria=geometria, atrybuty=atrybuty)


def _sparsuj_geometrie(element_geometrii) -> BaseGeometry:
    poligony = []
    for element_polygon in element_geometrii.iter(f"{NS_GML}Polygon"):
        posList_zewn = element_polygon.find(
            f"{NS_GML}exterior/{NS_GML}LinearRing/{NS_GML}posList"
        )
        if posList_zewn is None:
            continue
        pierscien_zewn = _poslist_na_punkty(posList_zewn.text)

        dziury = []
        for element_interior in element_polygon.findall(f"{NS_GML}interior"):
            posList_dziury = element_interior.find(f"{NS_GML}LinearRing/{NS_GML}posList")
            if posList_dziury is not None:
                dziury.append(_poslist_na_punkty(posList_dziury.text))

        poligony.append(Polygon(pierscien_zewn, dziury))

    if not poligony:
        raise BladWFS("Element geometrii nie zawiera żadnego wielokąta.")
    if len(poligony) == 1:
        return poligony[0]
    return MultiPolygon(poligony)


def _poslist_na_punkty(tekst: str) -> list[tuple[float, float]]:
    liczby = [float(x) for x in tekst.split()]
    pary_lat_lon = zip(liczby[0::2], liczby[1::2])
    return [(lon, lat) for lat, lon in pary_lat_lon]
