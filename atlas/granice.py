"""Granice gmin z Państwowego Rejestru Granic (PRG) — usługa WFS GUGiK.

Potrzebne do kartogramu. Pobieramy gminy jednego województwa (filtr po
początku kodu TERYT), upraszczamy geometrię (~50 m — do mapy w skali
województwa wystarczy, a plik jest wielokrotnie mniejszy) i zapisujemy
jako GeoJSON w instance/atlas/granice/, żeby kolejne otwarcia nie
pobierały tego samego.

Świadomie osobny parser GML niż w mpzp/wfs.py — moduły są niezależne
(CLAUDE.md: bez wspólnych abstrakcji dla dwóch modułów).
"""

import json
import os
import xml.etree.ElementTree as ET

import requests
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.ops import unary_union

URL_PRG = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
WARSTWA_GMIN = "ms:A03_Granice_gmin"
POLE_TERYT = "JPT_KOD_JE"
POLE_NAZWA = "JPT_NAZWA_"
TOLERANCJA_UPRASZCZANIA = 0.0005  # stopnie, ok. 35–55 m w Polsce

NS_GML = "{http://www.opengis.net/gml/3.2}"
NS_WFS = "{http://www.opengis.net/wfs/2.0}"


class BladGranic(Exception):
    """Błąd pobierania albo parsowania granic gmin z PRG."""


def granice_gmin(teryt_wojewodztwa: str, folder_cache: str) -> dict:
    """GeoJSON (FeatureCollection) gmin województwa; z cache, jeśli jest."""
    sciezka = os.path.join(folder_cache, f"gminy_{teryt_wojewodztwa}.geojson")
    if os.path.exists(sciezka):
        with open(sciezka, encoding="utf-8") as plik:
            return json.load(plik)

    kolekcja = _sparsuj_gml(_pobierz_gml(teryt_wojewodztwa), teryt_wojewodztwa)
    if not kolekcja["features"]:
        raise BladGranic(f"PRG nie zwrócił żadnej gminy dla województwa {teryt_wojewodztwa}.")

    os.makedirs(folder_cache, exist_ok=True)
    with open(sciezka, "w", encoding="utf-8") as plik:
        json.dump(kolekcja, plik)
    return kolekcja


def _pobierz_gml(teryt_wojewodztwa: str) -> str:
    filtr = (
        '<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0">'
        '<fes:PropertyIsLike wildCard="*" singleChar="?" escapeChar="!">'
        f"<fes:ValueReference>{POLE_TERYT}</fes:ValueReference>"
        f"<fes:Literal>{teryt_wojewodztwa}*</fes:Literal>"
        "</fes:PropertyIsLike></fes:Filter>"
    )
    try:
        odpowiedz = requests.get(
            URL_PRG,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": WARSTWA_GMIN,
                "srsName": "EPSG:4326",
                "filter": filtr,
            },
            timeout=180,
        )
        odpowiedz.raise_for_status()
    except requests.RequestException as e:
        raise BladGranic(f"Błąd połączenia z PRG (geoportal.gov.pl): {e}") from e
    return odpowiedz.text


def _sparsuj_gml(tekst: str, teryt_wojewodztwa: str) -> dict:
    try:
        root = ET.fromstring(tekst)
    except ET.ParseError as e:
        raise BladGranic(f"Nie udało się sparsować odpowiedzi PRG: {e}") from e

    if root.tag.endswith("ExceptionReport"):
        raise BladGranic(f"PRG zwrócił błąd: {' '.join(root.itertext()).strip()[:300]}")

    # Jedna gmina bywa w kilku rekordach — łączymy geometrie po TERYT.
    geometrie: dict[str, list] = {}
    nazwy: dict[str, str] = {}
    for member in root.iter(f"{NS_WFS}member"):
        for cecha in member:
            teryt, nazwa, geometria = _sparsuj_ceche(cecha)
            if not teryt or geometria is None or not teryt.startswith(teryt_wojewodztwa):
                continue
            geometrie.setdefault(teryt, []).append(geometria)
            nazwy[teryt] = nazwa

    cechy = []
    for teryt in sorted(geometrie):
        geometria = unary_union(geometrie[teryt]).simplify(
            TOLERANCJA_UPRASZCZANIA, preserve_topology=True
        )
        cechy.append(
            {
                "type": "Feature",
                "properties": {"teryt": teryt, "nazwa": nazwy[teryt]},
                "geometry": mapping(geometria),
            }
        )
    return {"type": "FeatureCollection", "features": cechy}


def _sparsuj_ceche(cecha):
    teryt = nazwa = None
    poligony = []
    for dziecko in cecha:
        pole = dziecko.tag.split("}", 1)[-1]
        if pole == POLE_TERYT:
            teryt = (dziecko.text or "").strip()
        elif pole == POLE_NAZWA:
            nazwa = (dziecko.text or "").strip()
        else:
            poligony.extend(_poligony(dziecko))

    if not poligony:
        return teryt, nazwa, None
    geometria = poligony[0] if len(poligony) == 1 else MultiPolygon(poligony)
    return teryt, nazwa, geometria


def _poligony(element) -> list[Polygon]:
    wynik = []
    for polygon in element.iter(f"{NS_GML}Polygon"):
        zewn = polygon.find(f"{NS_GML}exterior/{NS_GML}LinearRing/{NS_GML}posList")
        if zewn is None:
            continue
        dziury = [
            _punkty(p.text)
            for p in polygon.findall(f"{NS_GML}interior/{NS_GML}LinearRing/{NS_GML}posList")
        ]
        wynik.append(Polygon(_punkty(zewn.text), dziury))
    return wynik


def _punkty(tekst: str) -> list[tuple[float, float]]:
    """posList → [(lon, lat), ...].

    WFS 2.0 z EPSG:4326 podaje zwykle kolejność lat, lon — ale nie każdy
    serwer się tego trzyma. W Polsce szerokość (49–55°) i długość (14–24,2°)
    się nie nakładają, więc kolejność rozpoznajemy po pierwszej liczbie.
    """
    liczby = [float(x) for x in tekst.split()]
    pary = list(zip(liczby[0::2], liczby[1::2]))
    if pary and pary[0][0] > 45:  # pierwsza liczba to szerokość
        return [(lon, lat) for lat, lon in pary]
    return pary
