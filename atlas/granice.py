"""Granice gmin z Państwowego Rejestru Granic (PRG) — usługa WFS GUGiK.

Potrzebne do kartogramu. Pobieramy gminy jednego województwa (filtr po
początku kodu TERYT), upraszczamy geometrię (~50 m — do mapy w skali
województwa wystarczy, a plik jest wielokrotnie mniejszy) i zapisujemy
jako GeoJSON w instance/atlas/granice/, żeby kolejne otwarcia nie
pobierały tego samego.

Druga warstwa — granice wszystkich województw — to tło mapy: wokół
wybranego województwa widać sąsiednie zamiast kafelków OSM (ETAP 34).
Upraszczamy ją mocniej (~1 km), bo służy tylko za tło w skali kraju.

Świadomie osobny parser GML niż w mpzp/wfs.py — moduły są niezależne
(CLAUDE.md: bez wspólnych abstrakcji dla dwóch modułów).
"""

import json
import os
import xml.etree.ElementTree as ET

import requests
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union

from dane.siec import opis_bledu_sieci

URL_PRG = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
WARSTWA_GMIN = "ms:A03_Granice_gmin"
WARSTWA_WOJEWODZTW = "ms:A01_Granice_wojewodztw"
POLE_TERYT = "JPT_KOD_JE"
POLE_NAZWA = "JPT_NAZWA_"
TOLERANCJA_UPRASZCZANIA = 0.0005  # stopnie, ok. 35–55 m w Polsce
TOLERANCJA_WOJEWODZTW = 0.01  # ok. 0,7–1,1 km — tło w skali kraju

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


# ETAP 215: powiaty z połączonych gmin — gmina 3064011 należy do powiatu 3064
DOMKNIECIE_SZCZELIN = 0.0002  # stopnie, ok. 15–20 m: szczeliny po osobnym uproszczeniu sąsiednich gmin
MIN_POLE_DZIURY = 1e-6  # stopnie² (ok. 0,007 km²) — mniejsze otwory to resztki szczelin, nie enklawy


def _bez_drobnych_dziur(geometria):
    czesci = list(geometria.geoms) if geometria.geom_type == "MultiPolygon" else [geometria]
    oczyszczone = [Polygon(p.exterior, [r for r in p.interiors if Polygon(r).area > MIN_POLE_DZIURY]) for p in czesci]
    return oczyszczone[0] if len(oczyszczone) == 1 else MultiPolygon(oczyszczone)


def granice_powiatow(teryt_wojewodztwa: str, folder_cache: str) -> dict:
    """GeoJSON powiatów województwa jako połączenie gmin (TERYT gminy zaczyna
    się od TERYT powiatu). Bez osobnej warstwy PRG — z tych samych granic
    gmin co kartogram gmin, więc granice obu poziomów się pokrywają."""
    sciezka = os.path.join(folder_cache, f"powiaty_{teryt_wojewodztwa}.geojson")
    if os.path.exists(sciezka):
        with open(sciezka, encoding="utf-8") as plik:
            return json.load(plik)
    po_powiecie: dict[str, list] = {}
    nazwy_gmin: dict[str, list[str]] = {}
    for cecha in granice_gmin(teryt_wojewodztwa, folder_cache)["features"]:
        teryt = cecha["properties"]["teryt"][:4]
        po_powiecie.setdefault(teryt, []).append(shape(cecha["geometry"]))
        nazwy_gmin.setdefault(teryt, []).append(cecha["properties"]["nazwa"])
    cechy = []
    for teryt in sorted(po_powiecie):
        g = unary_union([x.buffer(DOMKNIECIE_SZCZELIN) for x in po_powiecie[teryt]]).buffer(-DOMKNIECIE_SZCZELIN)
        nazwa = nazwy_gmin[teryt][0] if len(nazwy_gmin[teryt]) == 1 else ""  # miasto na prawach powiatu = jedna gmina
        cechy.append({"type": "Feature", "properties": {"teryt": teryt, "nazwa": nazwa},
                      "geometry": mapping(_bez_drobnych_dziur(g).simplify(TOLERANCJA_UPRASZCZANIA / 2, preserve_topology=True))})
    kolekcja = {"type": "FeatureCollection", "features": cechy}
    with open(sciezka, "w", encoding="utf-8") as plik:
        json.dump(kolekcja, plik)
    return kolekcja


def granice_wojewodztw(folder_cache: str) -> dict:
    """GeoJSON wszystkich 16 województw (tło mapy atlasu); z cache, jeśli jest."""
    sciezka = os.path.join(folder_cache, "wojewodztwa.geojson")
    if os.path.exists(sciezka):
        with open(sciezka, encoding="utf-8") as plik:
            return json.load(plik)

    kolekcja = _sparsuj_gml(_pobierz_gml_wojewodztw(), "", TOLERANCJA_WOJEWODZTW)
    if not kolekcja["features"]:
        raise BladGranic("PRG nie zwrócił granic województw.")

    os.makedirs(folder_cache, exist_ok=True)
    with open(sciezka, "w", encoding="utf-8") as plik:
        json.dump(kolekcja, plik)
    return kolekcja


def _pobierz_gml_wojewodztw() -> str:
    return _zapytaj_prg(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": WARSTWA_WOJEWODZTW,
            "srsName": "EPSG:4326",
        }
    )


def _pobierz_gml(teryt_wojewodztwa: str) -> str:
    filtr = (
        '<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0">'
        '<fes:PropertyIsLike wildCard="*" singleChar="?" escapeChar="!">'
        f"<fes:ValueReference>{POLE_TERYT}</fes:ValueReference>"
        f"<fes:Literal>{teryt_wojewodztwa}*</fes:Literal>"
        "</fes:PropertyIsLike></fes:Filter>"
    )
    return _zapytaj_prg(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": WARSTWA_GMIN,
            "srsName": "EPSG:4326",
            "filter": filtr,
        }
    )


def _zapytaj_prg(parametry: dict) -> str:
    try:
        odpowiedz = requests.get(URL_PRG, params=parametry, timeout=180)
        odpowiedz.raise_for_status()
    except requests.RequestException as e:
        raise BladGranic(f"Błąd połączenia z PRG (geoportal.gov.pl): {opis_bledu_sieci(e)}.") from e
    return odpowiedz.text


def _sparsuj_gml(tekst: str, teryt_wojewodztwa: str, tolerancja: float = TOLERANCJA_UPRASZCZANIA) -> dict:
    """GML z PRG → GeoJSON. Pusty `teryt_wojewodztwa` = bez filtra (wszystko)."""
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
            tolerancja, preserve_topology=True
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
