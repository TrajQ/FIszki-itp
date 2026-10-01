"""Diagnostyka: stan konfiguracji i usług zewnętrznych (ETAP 126).

Strona /diagnostyka pomaga, gdy coś przestaje działać: pokazuje, czy są
klucze (bez ich treści), gdzie leżą dane i ile zajmują, wersje bibliotek
i — na żądanie — czy odpowiadają usługi, z których korzysta Warsztat.

Sprawdzenie usługi to jedno zapytanie GET pod adres używany w kodzie
modułu, z krótkim limitem czasu. Każda odpowiedź HTTP (także 4xx) znaczy
„serwer osiąga się”; błąd połączenia albo przekroczony czas — „brak
połączenia”. Do Gemini nie wysyłamy klucza ani zapytania do modelu —
sprawdzamy tylko, czy serwer odpowiada (bez kosztów).
"""

import os
import platform
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata

import requests

from atlas.granice import URL_PRG
from dane.bdl import URL_BDL
from dane.ortofoto import URL_ORTO_OBECNA
from dane.sejm import URL_API as URL_SEJM
from dane.uldk import URL_ULDK
from mpzp.krajowe import URL_KIMPZP

LIMIT_CZASU_S = 6
URL_GEMINI = "https://generativelanguage.googleapis.com/"
BIBLIOTEKI = ["Flask", "requests", "shapely", "h3", "pypdf", "google-genai", "python-dotenv"]

USLUGI = [
    ("GUS — Bank Danych Lokalnych", "atlas, ceny", URL_BDL),
    ("GUGiK — ULDK (działki)", "mpzp, osiedle", URL_ULDK),
    ("GUGiK — krajowa integracja planów (KIMPZP)", "mpzp", URL_KIMPZP),
    ("GUGiK — granice administracyjne (PRG)", "atlas", URL_PRG),
    ("GUGiK — ortofotomapa", "mpzp, teren", URL_ORTO_OBECNA),
    ("Sejm — API Dziennika Ustaw (ELI)", "przepisy", URL_SEJM),
    ("Google — Gemini", "atlas, przepisy, fiszki", URL_GEMINI),
]


def sprawdz_usluge(adres: str) -> dict:
    """{"osiagalna", "status" (kod HTTP), "ms", "blad"} — bez wyjątków."""
    start = time.monotonic()
    try:
        with requests.get(adres, timeout=LIMIT_CZASU_S, stream=True, headers={"User-Agent": "Warsztat-diagnostyka"}) as odp:
            return {"osiagalna": True, "status": odp.status_code, "ms": round(1000 * (time.monotonic() - start)), "blad": None}
    except requests.Timeout:
        return {"osiagalna": False, "status": None, "ms": None, "blad": f"brak odpowiedzi w {LIMIT_CZASU_S} s"}
    except requests.RequestException as e:
        return {"osiagalna": False, "status": None, "ms": None, "blad": f"brak połączenia ({e.__class__.__name__})"}


def sprawdz_uslugi() -> list[dict]:
    """Wszystkie usługi równolegle (całość trwa najwyżej ok. LIMIT_CZASU_S)."""
    with ThreadPoolExecutor(max_workers=len(USLUGI)) as pula:
        wyniki = list(pula.map(lambda u: sprawdz_usluge(u[2]), USLUGI))
    return [{"nazwa": n, "moduly": m, "adres": a, **w} for (n, m, a), w in zip(USLUGI, wyniki)]


def _rozmiar(sciezka: str) -> int:
    if os.path.isfile(sciezka):
        return os.path.getsize(sciezka)
    return sum(os.path.getsize(os.path.join(k, p)) for k, _, pliki in os.walk(sciezka) for p in pliki)


def stan(konfiguracja, folder_instance: str) -> dict:
    """Konfiguracja i dane — bez treści kluczy."""
    moduly = []
    if os.path.isdir(folder_instance):
        for nazwa in sorted(os.listdir(folder_instance)):
            sciezka = os.path.join(folder_instance, nazwa)
            if os.path.isdir(sciezka):
                bazy = sorted(p for p in os.listdir(sciezka) if p.endswith(".db"))
                moduly.append({"nazwa": nazwa, "mb": round(_rozmiar(sciezka) / 1e6, 2), "bazy": bazy})
    dysk = shutil.disk_usage(folder_instance if os.path.isdir(folder_instance) else os.path.dirname(folder_instance))
    wersje = {}
    for b in BIBLIOTEKI:
        try:
            wersje[b] = metadata.version(b)
        except metadata.PackageNotFoundError:
            wersje[b] = None
    return {
        "python": platform.python_version(),
        "system": f"{platform.system()} {platform.release()}",
        "biblioteki": wersje,
        "klucz_gemini": bool(konfiguracja.get("GEMINI_API_KEY")),
        "model_gemini": konfiguracja.get("GEMINI_MODEL"),
        "klucz_gus": bool(konfiguracja.get("GUS_BDL_API_KEY")),
        "folder_danych": folder_instance,
        "moduly": moduly,
        "dane_mb": round(sum(m["mb"] for m in moduly), 2),
        "wolne_gb": round(dysk.free / 1e9, 1),
        "auto_kopia_dni": konfiguracja.get("AUTO_KOPIA_DNI"),
        "auto_kopia_folder": konfiguracja.get("AUTO_KOPIA_FOLDER"),
    }
