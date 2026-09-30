"""Inne usługi WMS GUGiK w module MPZP: plany ogólne gmin (ETAP 89) i
Rejestr Cen Nieruchomości (ETAP 90).

Każda usługa daje dwie rzeczy, tak jak krajowa integracja planów
(krajowe.py):
1. obraz na mapie — warstwa WMS ładowana wprost przez Leaflet,
2. informacje w punkcie — zapytanie GetFeatureInfo (atrybuty obiektów).

Niczego nie wpisujemy na sztywno poza adresem usługi: nazwy warstw,
układy współrzędnych i formaty odpowiedzi GetFeatureInfo czytamy z
GetCapabilities (raz na dobę). Gdy usługa nie odpowiada, warstwy po
prostu nie ma — bez zgadywania nazw.

Atrybuty pokazujemy tak, jak podała je usługa. Interpretacja (np. co
oznacza symbol strefy) należy do dokumentu źródłowego.
"""

import re
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import requests

from dane.siec import opis_bledu_sieci

from . import krajowe

USLUGI = {
    "plany_ogolne": {
        "url": "https://mapy.geoportal.gov.pl/wss/ext/PlanyOgolneGmin",
        "nazwa": "Plan ogólny gminy",
    },
    # ETAP 90: ceny transakcyjne — dane RCN są bezpłatne od lutego 2026 r.
    "ceny": {
        "url": "https://mapy.geoportal.gov.pl/wss/service/rcn",
        "nazwa": "Rejestr Cen Nieruchomości",
    },
}

WAZNOSC_S = 24 * 3600
NS = krajowe.NS_WMS
# Formaty odpowiedzi GetFeatureInfo, które umiemy czytać — w kolejności chęci.
FORMATY = ("application/vnd.ogc.gml", "application/vnd.ogc.gml/3.1.1", "text/xml", "text/plain", "text/html")

_cache: dict[str, dict] = {}


class BladUslugi(Exception):
    """Usługa nie odpowiada albo odpowiedź jest nieczytelna."""


def _pobierz(url: str, parametry: dict, nazwa: str) -> str:
    try:
        odpowiedz = requests.get(url, params=parametry, timeout=30)
        odpowiedz.raise_for_status()
    except requests.RequestException as e:
        raise BladUslugi(f"{nazwa}: {opis_bledu_sieci(e)}.") from e
    return odpowiedz.text


def _opis_z_capabilities(tekst: str, nazwa: str) -> dict:
    try:
        warstwy = krajowe.sparsuj_capabilities(tekst)
        uklady = krajowe.uklady_wspolrzednych(tekst)
        glowna = krajowe.warstwa_glowna(tekst)
        root = ET.fromstring(tekst)
    except (krajowe.BladKIMPZP, ET.ParseError) as e:
        raise BladUslugi(f"{nazwa}: nieczytelna odpowiedź usługi.") from e
    if not warstwy:
        raise BladUslugi(f"{nazwa}: usługa nie podała żadnej warstwy.")
    formaty = [
        (f.text or "").strip()
        for f in root.findall(f"{NS}Capability/{NS}Request/{NS}GetFeatureInfo/{NS}Format")
    ]
    return {
        "warstwy": [w["nazwa"] for w in warstwy],
        "zapytywalne": [w["nazwa"] for w in warstwy if w["zapytywalna"]],
        "glowna": glowna,
        "mercator": not uklady or "EPSG:3857" in uklady,
        "formaty": [f for f in FORMATY if f in formaty],
    }


def opis(klucz: str) -> dict:
    """Opis usługi z GetCapabilities (z pamięci na dobę)."""
    usluga = USLUGI[klucz]
    zapisany = _cache.get(klucz)
    if zapisany and time.time() - zapisany["czas"] < WAZNOSC_S:
        return zapisany["opis"]
    tekst = _pobierz(usluga["url"], {"service": "WMS", "request": "GetCapabilities", "version": "1.3.0"}, usluga["nazwa"])
    wynik = _opis_z_capabilities(tekst, usluga["nazwa"])
    _cache[klucz] = {"czas": time.time(), "opis": wynik}
    return wynik


def warstwa_mapy(klucz: str) -> dict | None:
    """{"url", "warstwy", "mercator"} dla Leafleta albo None, gdy usługa nie odpowiada."""
    try:
        o = opis(klucz)
    except BladUslugi:
        return None
    return {
        "url": USLUGI[klucz]["url"],
        "warstwy": ",".join(krajowe._ogranicz(o["warstwy"], o["glowna"])),
        "mercator": o["mercator"],
    }


def w_punkcie(klucz: str, lat: float, lon: float) -> list[dict]:
    """Obiekty usługi w punkcie: [{"warstwa", "atrybuty"}]. Pusta lista — nic tu nie ma."""
    usluga = USLUGI[klucz]
    o = opis(klucz)
    warstwy = krajowe._ogranicz(o["zapytywalne"], o["glowna"], tylko_zapytywalna=True)
    if not warstwy:
        raise BladUslugi(f"{usluga['nazwa']}: usługa nie pozwala pytać o obiekty w punkcie.")
    if not o["formaty"]:
        raise BladUslugi(f"{usluga['nazwa']}: usługa nie podaje informacji w formacie, który umiemy odczytać.")
    pol = krajowe.POL_OKNA_STOPNIE
    parametry = {
        "service": "WMS",
        "version": "1.1.1",  # w 1.1.1 EPSG:4326 to zawsze kolejność lon, lat
        "request": "GetFeatureInfo",
        "srs": "EPSG:4326",
        "bbox": ",".join(str(round(v, 7)) for v in (lon - pol, lat - pol, lon + pol, lat + pol)),
        "width": krajowe.ROZMIAR_OKNA_PX,
        "height": krajowe.ROZMIAR_OKNA_PX,
        "x": krajowe.ROZMIAR_OKNA_PX // 2,
        "y": krajowe.ROZMIAR_OKNA_PX // 2,
        "layers": ",".join(warstwy),
        "query_layers": ",".join(warstwy),
        "styles": "",
        "format": "image/png",
        "feature_count": 20,
        "info_format": o["formaty"][0],
    }
    tekst = _pobierz(usluga["url"], parametry, usluga["nazwa"])
    return sparsuj(tekst, o["formaty"][0], usluga["nazwa"])


def sparsuj(tekst: str, format_: str, nazwa: str = "usługa") -> list[dict]:
    try:
        if format_ == "text/html":
            obiekty = sparsuj_html(tekst)
        elif format_ == "text/plain":
            obiekty = [{"warstwa": o.warstwa, "atrybuty": o.atrybuty} for o in krajowe.sparsuj_tekst(tekst)]
        else:
            obiekty = [{"warstwa": o.warstwa, "atrybuty": o.atrybuty} for o in krajowe.sparsuj_gml(tekst)]
    except krajowe.BladKIMPZP as e:
        raise BladUslugi(f"{nazwa}: nieczytelna odpowiedź usługi.") from e
    return obiekty


class _Tabele(HTMLParser):
    """Tabele HTML → wiersze komórek (tekst, czy nagłówek <th>), osobno dla każdej tabeli."""

    def __init__(self):
        super().__init__()
        self.tabele, self._wiersz, self._komorka, self._th = [], None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tabele.append([])
        elif tag == "tr" and self.tabele:
            self._wiersz = []
        elif tag in ("td", "th") and self._wiersz is not None:
            self._komorka, self._th = [], tag == "th"

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._komorka is not None:
            self._wiersz.append((" ".join("".join(self._komorka).split()), self._th))
            self._komorka = None
        elif tag == "tr" and self._wiersz is not None:
            if any(tekst for tekst, _ in self._wiersz):
                self.tabele[-1].append(self._wiersz)
            self._wiersz = None

    def handle_data(self, data):
        if self._komorka is not None:
            self._komorka.append(data)


def sparsuj_html(tekst: str) -> list[dict]:
    """Odpowiedź GetFeatureInfo w HTML. Dwa typowe układy tabel:
    nagłówek z nazwami pól (pierwszy wiersz z samych <th>) i wiersze
    obiektów albo wiersze „nazwa | wartość”."""
    parser = _Tabele()
    parser.feed(tekst)
    wynik = []
    for tabela in parser.tabele:
        if not tabela:
            continue
        z_naglowkiem = len(tabela) > 1 and all(th for _, th in tabela[0]) and not all(w[0][1] for w in tabela[1:])
        tabela = [[t for t, _ in w] for w in tabela]
        if not z_naglowkiem and all(len(w) == 2 for w in tabela):
            atrybuty = {k: v for k, v in tabela if k and v}
            if atrybuty:
                wynik.append({"warstwa": "", "atrybuty": atrybuty})
            continue
        naglowek, *wiersze = tabela
        for w in wiersze:
            atrybuty = {k: v for k, v in zip(naglowek, w) if k and v}
            if atrybuty:
                wynik.append({"warstwa": "", "atrybuty": atrybuty})
    return wynik


def linki(obiekty: list[dict]) -> list[str]:
    """Adresy http(s) z atrybutów (np. uchwała planu ogólnego)."""
    wynik = []
    for o in obiekty:
        for wartosc in o["atrybuty"].values():
            tekst = str(wartosc).strip()
            if re.match(r"^https?://\S+$", tekst) and tekst not in wynik:
                wynik.append(tekst)
    return wynik
