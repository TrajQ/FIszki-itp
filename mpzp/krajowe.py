"""Krajowa integracja miejscowych planów (KIMPZP) — usługa WMS GUGiK.

Poznań ma własny WFS z geometrią wydzieleń (mpzp/wfs.py), ale reszta
Polski nie. Gminy przekazują za to swoje plany do krajowej integracji
GUGiK, która łączy je w jedną usługę WMS dla całego kraju. Z niej
bierzemy dwie rzeczy:

1. obraz planów na mapie (warstwa WMS ładowana wprost przez Leaflet),
2. informację o planie w punkcie — zapytanie GetFeatureInfo.

Ograniczenia, o których trzeba pamiętać:
- GetFeatureInfo zwraca atrybuty, ale nie geometrię wydzielenia — nie
  policzymy więc podziału działki na przeznaczenia (to umie tylko WFS).
- Każda gmina opisuje plany trochę inaczej (nazwy pól, format). Dlatego
  pokazujemy wszystkie atrybuty, a symbol przeznaczenia tylko
  rozpoznajemy po nazwie pola — to podpowiedź, nie pewnik.
- Nie wszystkie gminy przekazały plany (albo przekazały tylko skany
  rysunku bez atrybutów).

Nazwy warstw czytamy z GetCapabilities usługi, zamiast wpisywać je na
sztywno; lista zapasowa jest tylko na wypadek braku odpowiedzi.
"""

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import requests

from dane.siec import opis_bledu_sieci

URL_KIMPZP = (
    "https://integracja.gugik.gov.pl/cgi-bin/"
    "KrajowaIntegracjaMiejscowychPlanowZagospodarowaniaPrzestrzennego"
)
# Działki ewidencyjne z krajowej integracji ewidencji (KIEG) — tylko obraz na mapie.
URL_KIEG = "https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow"
WARSTWY_KIEG = "dzialki,numery_dzialek"

# Używane tylko, gdy GetCapabilities nie odpowie.
WARSTWY_ZAPASOWE = ["raster", "wektor-str", "wektor-lzb", "wektor-pow", "wektor-lin", "wektor-pkt", "granice"]
WAZNOSC_LISTY_WARSTW_S = 24 * 3600
# Powyżej tylu warstw pytamy o warstwę główną (grupę) zamiast wymieniać
# wszystkie — inaczej adres zapytania robi się za długi.
MAKS_WARSTW_W_ZAPYTANIU = 30

# Okno zapytania GetFeatureInfo: ok. 70 × 110 m wokół punktu, 101 × 101 px,
# punkt dokładnie w środku (piksel 50, 50).
POL_OKNA_STOPNIE = 0.0005
ROZMIAR_OKNA_PX = 101

NS_WMS = "{http://www.opengis.net/wms}"
NS_GML_PREFIKSY = ("{http://www.opengis.net/gml",)

# Pola, w których gminy zwykle trzymają symbol przeznaczenia — w kolejności
# pewności. Porównujemy bez wielkości liter i bez polskich znaków.
POLA_SYMBOLU = ("symbol", "oznaczenie", "przeznaczenie", "symb", "przezn", "funkcja")
POLA_TYTULU = ("tytul", "nazwa", "nazwa_planu", "tytul_planu")
MAKS_DLUGOSC_SYMBOLU = 40


class BladKIMPZP(Exception):
    """Błąd komunikacji z krajową integracją planów albo zła odpowiedź."""


@dataclass
class ObiektPlanu:
    warstwa: str
    atrybuty: dict = field(default_factory=dict)


_warstwy_cache: dict = {"czas": 0.0, "warstwy": None, "uklady": None, "glowna": None}


# ---------- lista warstw ----------


def warstwy() -> list[dict]:
    """Warstwy KIMPZP: [{"nazwa", "tytul", "zapytywalna"}]. Z cache (doba)."""
    if _warstwy_cache["warstwy"] is not None and time.time() - _warstwy_cache["czas"] < WAZNOSC_LISTY_WARSTW_S:
        return _warstwy_cache["warstwy"]
    tekst = _pobierz(URL_KIMPZP, {"service": "WMS", "request": "GetCapabilities", "version": "1.3.0"})
    lista = sparsuj_capabilities(tekst)
    if not lista:
        raise BladKIMPZP("Usługa KIMPZP nie podała żadnej warstwy.")
    _warstwy_cache.update(
        czas=time.time(), warstwy=lista, uklady=uklady_wspolrzednych(tekst), glowna=warstwa_glowna(tekst)
    )
    return lista


def warstwa_glowna(tekst: str) -> dict | None:
    """Nazwana warstwa najwyższego poziomu (grupa wszystkich) albo None."""
    capability = _xml(tekst).find(f"{NS_WMS}Capability")
    glowna = capability.find(f"{NS_WMS}Layer") if capability is not None else None
    if glowna is None or not (glowna.findtext(f"{NS_WMS}Name") or "").strip():
        return None
    return {"nazwa": glowna.findtext(f"{NS_WMS}Name").strip(), "zapytywalna": glowna.get("queryable") == "1"}


def _ogranicz(nazwy: list[str], glowna: dict | None, tylko_zapytywalna: bool = False) -> list[str]:
    if len(nazwy) <= MAKS_WARSTW_W_ZAPYTANIU or glowna is None:
        return nazwy[:MAKS_WARSTW_W_ZAPYTANIU] if glowna is None else nazwy
    if tylko_zapytywalna and not glowna["zapytywalna"]:
        return nazwy[:MAKS_WARSTW_W_ZAPYTANIU]
    return [glowna["nazwa"]]


def sparsuj_capabilities(tekst: str) -> list[dict]:
    """Warstwy-liście (bez grup) z dokumentu GetCapabilities WMS 1.3.0."""
    root = _xml(tekst)
    wynik = []
    for warstwa in root.iter(f"{NS_WMS}Layer"):
        if warstwa.find(f"{NS_WMS}Layer") is not None:
            continue  # grupa warstw — interesują nas liście
        nazwa = warstwa.findtext(f"{NS_WMS}Name")
        if not nazwa:
            continue
        wynik.append(
            {
                "nazwa": nazwa.strip(),
                "tytul": (warstwa.findtext(f"{NS_WMS}Title") or nazwa).strip(),
                "zapytywalna": warstwa.get("queryable") == "1",
            }
        )
    return wynik


def uklady_wspolrzednych(tekst: str) -> set[str]:
    """Kody CRS z GetCapabilities (np. „EPSG:3857”) — zbiorczo dla usługi."""
    return {(e.text or "").strip().upper() for e in _xml(tekst).iter(f"{NS_WMS}CRS")}


def nazwy_warstw() -> tuple[list[str], bool]:
    """(nazwy warstw, czy z GetCapabilities). Przy błędzie — lista zapasowa."""
    try:
        return _ogranicz([w["nazwa"] for w in warstwy()], _warstwy_cache["glowna"]), True
    except BladKIMPZP:
        return list(WARSTWY_ZAPASOWE), False


def czy_mercator() -> bool:
    """Czy usługa rysuje w EPSG:3857 (układ mapy Leafleta).

    Jeśli nie — mapa poprosi o obrazki w EPSG:4326 (w skali działki
    różnica kształtu jest niewidoczna). Bez odpowiedzi zakładamy, że tak.
    """
    uklady = _warstwy_cache.get("uklady")
    return not uklady or "EPSG:3857" in uklady


# ---------- plan w punkcie ----------


def plan_w_punkcie(lat: float, lon: float) -> list[ObiektPlanu]:
    """Obiekty planów (atrybuty) w punkcie; pusta lista = brak planu w KIMPZP."""
    try:
        zapytywalne = _ogranicz(
            [w["nazwa"] for w in warstwy() if w["zapytywalna"]], _warstwy_cache["glowna"], tylko_zapytywalna=True
        )
    except BladKIMPZP:
        zapytywalne = list(WARSTWY_ZAPASOWE)
    if not zapytywalne:
        return []

    parametry = {
        "service": "WMS",
        "version": "1.1.1",  # w 1.1.1 EPSG:4326 to zawsze kolejność lon, lat
        "request": "GetFeatureInfo",
        "srs": "EPSG:4326",
        "bbox": ",".join(
            str(round(v, 7))
            for v in (lon - POL_OKNA_STOPNIE, lat - POL_OKNA_STOPNIE, lon + POL_OKNA_STOPNIE, lat + POL_OKNA_STOPNIE)
        ),
        "width": ROZMIAR_OKNA_PX,
        "height": ROZMIAR_OKNA_PX,
        "x": ROZMIAR_OKNA_PX // 2,
        "y": ROZMIAR_OKNA_PX // 2,
        "layers": ",".join(zapytywalne),
        "query_layers": ",".join(zapytywalne),
        "styles": "",
        "format": "image/png",
        "feature_count": 20,
    }
    # Najpierw GML (łatwy do czytania), a gdy usługa go nie obsługuje — tekst.
    tekst = _pobierz(URL_KIMPZP, {**parametry, "info_format": "application/vnd.ogc.gml"})
    try:
        return sparsuj_gml(tekst)
    except BladKIMPZP:
        tekst = _pobierz(URL_KIMPZP, {**parametry, "info_format": "text/plain"})
        return sparsuj_tekst(tekst)


def sparsuj_gml(tekst: str) -> list[ObiektPlanu]:
    """Odpowiedź GetFeatureInfo w GML (MapServer: <warstwa_layer><warstwa_feature>)."""
    root = _xml(tekst)
    wynik = []
    for element in root.iter():
        nazwa = _lokalna(element.tag)
        if nazwa.endswith("_feature"):
            wynik.append(ObiektPlanu(warstwa=nazwa[: -len("_feature")], atrybuty=_atrybuty(element)))
        elif nazwa in ("featureMember", "member"):
            for cecha in element:
                wynik.append(ObiektPlanu(warstwa=_lokalna(cecha.tag), atrybuty=_atrybuty(cecha)))
    return [o for o in wynik if o.atrybuty]


WZOR_WARSTWY = re.compile(r"^Layer '([^']*)'")
WZOR_ATRYBUTU = re.compile(r"^\s+([^=]+?)\s*=\s*'(.*)'\s*$")
WZOR_OBIEKTU = re.compile(r"^\s*Feature\s")


def sparsuj_tekst(tekst: str) -> list[ObiektPlanu]:
    """Odpowiedź GetFeatureInfo w formacie text/plain MapServera."""
    if "ServiceException" in tekst or "msWMS" in tekst:
        # raport błędu (XML albo tekst MapServera) to nie „brak planu”
        raise BladKIMPZP(f"KIMPZP zwróciła błąd: {' '.join(tekst.split())[:300]}")
    wynik: list[ObiektPlanu] = []
    warstwa = ""
    for linia in tekst.splitlines():
        if m := WZOR_WARSTWY.match(linia):
            warstwa = m.group(1)
        elif WZOR_OBIEKTU.match(linia):
            wynik.append(ObiektPlanu(warstwa=warstwa))
        elif (m := WZOR_ATRYBUTU.match(linia)) and wynik:
            if m.group(2).strip():
                wynik[-1].atrybuty[m.group(1).strip()] = m.group(2).strip()
    return [o for o in wynik if o.atrybuty]


# ---------- rozpoznanie symbolu i linków ----------


def _bez_ogonkow(tekst: str) -> str:
    return tekst.lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))


def rozpoznaj_przeznaczenie(obiekty: list[ObiektPlanu]) -> str | None:
    """Symbol przeznaczenia z atrybutów — z pola o typowej nazwie.

    Szukamy najpierw pola o najpewniejszej nazwie („symbol”) we wszystkich
    obiektach, potem kolejnych. Długie teksty pomijamy — to opisy, nie symbole.
    """
    for wzor in POLA_SYMBOLU:
        for obiekt in obiekty:
            for klucz, wartosc in obiekt.atrybuty.items():
                if wzor in _bez_ogonkow(klucz) and 0 < len(str(wartosc).strip()) <= MAKS_DLUGOSC_SYMBOLU:
                    return str(wartosc).strip()
    return None


def tytul_planu(obiekty: list[ObiektPlanu]) -> str | None:
    for wzor in POLA_TYTULU:
        for obiekt in obiekty:
            for klucz, wartosc in obiekt.atrybuty.items():
                if _bez_ogonkow(klucz) == wzor and str(wartosc).strip():
                    return str(wartosc).strip()
    return None


def linki(obiekty: list[ObiektPlanu]) -> list[str]:
    """Adresy http(s) z atrybutów (np. tekst uchwały, rysunek) — bez powtórzeń."""
    wynik = []
    for obiekt in obiekty:
        for wartosc in obiekt.atrybuty.values():
            tekst = str(wartosc).strip()
            if re.match(r"^https?://\S+$", tekst) and tekst not in wynik:
                wynik.append(tekst)
    return wynik


# ---------- pomocnicze ----------


def _lokalna(tag) -> str:
    return tag.split("}", 1)[-1] if isinstance(tag, str) else ""


def _atrybuty(cecha) -> dict:
    """Liście elementu (pola z tekstem), bez geometrii i elementów GML."""
    atrybuty = {}
    for pole in cecha.iter():
        if pole is cecha or len(pole) or not isinstance(pole.tag, str):
            continue
        if pole.tag.startswith(NS_GML_PREFIKSY) or _lokalna(pole.tag) in ("boundedBy", "msGeometry"):
            continue
        tekst = (pole.text or "").strip()
        if tekst:
            atrybuty[_lokalna(pole.tag)] = tekst
    return atrybuty


def _xml(tekst: str):
    try:
        root = ET.fromstring(tekst)
    except ET.ParseError as e:
        raise BladKIMPZP(f"Niepoprawna odpowiedź usługi KIMPZP: {e}") from e
    if _lokalna(root.tag) in ("ServiceExceptionReport", "ExceptionReport"):
        raise BladKIMPZP(f"KIMPZP zwróciła błąd: {' '.join(root.itertext()).strip()[:300]}")
    return root


def _pobierz(url: str, parametry: dict) -> str:
    try:
        odpowiedz = requests.get(url, params=parametry, timeout=30)
        odpowiedz.raise_for_status()
    except requests.RequestException as e:
        raise BladKIMPZP(f"Błąd połączenia z krajową integracją planów (GUGiK): {opis_bledu_sieci(e)}.") from e
    return odpowiedz.text
