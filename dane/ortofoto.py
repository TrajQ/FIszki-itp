"""Ortofotomapy archiwalne: jakie lata udostępnia usługa WMS (ETAP 64).

Lat nie wpisujemy w kod — czytamy je z odpowiedzi GetCapabilities usługi
(adres w Config.ORTO_ARCHIWALNA_WMS). Obsługujemy dwa sposoby, w jakie
usługi WMS podają zdjęcia z różnych lat:

1. wymiar czasu warstwy (<Dimension name="time"> w WMS 1.3.0, <Extent
   name="time"> w 1.1.1): lista dat albo przedziały „od/do/okres”;
   wtedy obraz z danego roku pobiera się parametrem TIME,
2. osobna warstwa na rok (rok w nazwie albo tytule warstwy).

Obrazy pobiera już przeglądarka (Leaflet, jak podkład ortofotomapy
w innych modułach); serwer tylko czyta opis usługi.
"""

import re
import time
import xml.etree.ElementTree as ET

import requests

from config import Config
from dane.siec import opis_bledu_sieci

WAZNOSC_S = 24 * 3600  # opis usługi zmienia się rzadko
_ROK = re.compile(r"(?<!\d)(19[3-9]\d|20[0-9]\d)(?!\d)")
_pamiec: dict[str, tuple[float, dict]] = {}


class BladOrtofoto(Exception):
    """Usługa nie odpowiada albo jej opisu nie da się odczytać."""


def _bez_przestrzeni(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _dziecko(el, nazwa):
    return next((c for c in el if _bez_przestrzeni(c.tag) == nazwa), None)


def _lata_z_wymiaru(tekst: str) -> list[dict]:
    """„2010-05-01,2012-06-01” albo „2004-01-01/2023-12-31/P1Y” → [{rok, time, przedzial}]."""
    lata = {}
    for czesc in (c.strip() for c in tekst.split(",")):
        if not czesc:
            continue
        if "/" in czesc:
            poczatek, koniec = czesc.split("/")[:2]
            od, do = _ROK.search(poczatek), _ROK.search(koniec)
            if od and do:
                for rok in range(int(od.group()), int(do.group()) + 1):
                    # Przedział nie mówi, czy w danym roku są zdjęcia — pytamy o cały rok.
                    lata.setdefault(rok, {"rok": rok, "time": f"{rok}-01-01/{rok}-12-31", "przedzial": True})
            continue
        rok = _ROK.search(czesc)
        if rok:
            # Kilka dat w jednym roku: bierzemy najpóźniejszą (zwykle pełniejszy nalot).
            r = int(rok.group())
            if r not in lata or lata[r]["przedzial"] or czesc > lata[r]["time"]:
                lata[r] = {"rok": r, "time": czesc, "przedzial": False}
    return list(lata.values())


def odczytaj_capabilities(xml: bytes) -> dict:
    """Opis usługi → {"wersja", "lata": [{rok, warstwa, time|None, przedzial}]} rosnąco po roku."""
    try:
        korzen = ET.fromstring(xml)
    except ET.ParseError as e:
        raise BladOrtofoto(f"Usługa zwróciła niepoprawny opis (XML): {e}.") from None
    if _bez_przestrzeni(korzen.tag) not in ("WMS_Capabilities", "WMT_MS_Capabilities"):
        raise BladOrtofoto("To nie jest opis usługi WMS (GetCapabilities).")
    wersja = korzen.get("version") or "1.3.0"

    z_wymiaru, z_warstw = {}, {}
    for warstwa in korzen.iter():
        if _bez_przestrzeni(warstwa.tag) != "Layer":
            continue
        nazwa_el = _dziecko(warstwa, "Name")
        if nazwa_el is None or not (nazwa_el.text or "").strip():
            continue
        nazwa = nazwa_el.text.strip()
        tytul = (_dziecko(warstwa, "Title").text or "") if _dziecko(warstwa, "Title") is not None else ""
        wymiar = next(
            (c for c in warstwa if _bez_przestrzeni(c.tag) in ("Dimension", "Extent") and (c.get("name") or "").lower() == "time" and (c.text or "").strip()),
            None,
        )
        if wymiar is not None:
            for r in _lata_z_wymiaru(wymiar.text):
                z_wymiaru.setdefault(r["rok"], {**r, "warstwa": nazwa})
            continue
        rok = _ROK.search(nazwa) or _ROK.search(tytul)
        if rok:
            z_warstw.setdefault(int(rok.group()), {"rok": int(rok.group()), "warstwa": nazwa, "time": None, "przedzial": False})

    lata = z_wymiaru or z_warstw  # usługa z wymiarem czasu ma pierwszeństwo
    return {"wersja": wersja, "lata": sorted(lata.values(), key=lambda r: r["rok"])}


def lata_archiwalne() -> dict:
    """{"url", "wersja", "lata"} dla usługi z konfiguracji (pamięć na 24 h)."""
    url = Config.ORTO_ARCHIWALNA_WMS
    zapamietane = _pamiec.get(url)
    if zapamietane and time.time() - zapamietane[0] < WAZNOSC_S:
        return zapamietane[1]
    try:
        odpowiedz = requests.get(url, params={"SERVICE": "WMS", "REQUEST": "GetCapabilities"}, timeout=30)
        odpowiedz.raise_for_status()
    except requests.RequestException as e:
        raise BladOrtofoto(f"Usługa ortofotomap archiwalnych: {opis_bledu_sieci(e)}.") from e
    wynik = {"url": url, **odczytaj_capabilities(odpowiedz.content)}
    if wynik["lata"]:
        _pamiec[url] = (time.time(), wynik)
    return wynik
