"""Strona „O danych”: skąd Warsztat bierze dane i na czym jest zbudowany (ETAP 244).

Lista usług to te, z którymi kod naprawdę się łączy (adresy w dane/,
mpzp/, atlas/, config.py). Nie piszemy tu nazw licencji danych
publicznych, których nie sprawdziliśmy w źródle (D-218) — przy każdej
usłudze jest link do strony dostawcy z zasadami. Licencje bibliotek
Pythona czytamy z metadanych zainstalowanych pakietów, więc zgadzają
się z tym, co jest na komputerze.
"""

import importlib.metadata

# (usługa, dostawca, co pobieramy, moduły, strona z opisem i zasadami, czy bez klucza)
ZRODLA = [
    {"nazwa": "Bank Danych Lokalnych (API BDL)", "dostawca": "Główny Urząd Statystyczny",
     "co": "wskaźniki gmin i powiatów (ludność, mieszkania, ceny mieszkań…)", "moduly": "Atlas, Ceny (GUS)",
     "url": "https://api.stat.gov.pl/Home/BdlApi", "uwagi": "bez klucza z limitem zapytań; klucz GUS (zmienna GUS_BDL_API_KEY) podnosi limit"},
    {"nazwa": "Państwowy Rejestr Granic (WFS)", "dostawca": "Główny Urząd Geodezji i Kartografii",
     "co": "granice gmin i województw", "moduly": "Atlas", "url": "https://www.geoportal.gov.pl", "uwagi": ""},
    {"nazwa": "Usługa Lokalizacji Działek Katastralnych (ULDK)", "dostawca": "GUGiK",
     "co": "granice i identyfikatory działek ewidencyjnych", "moduly": "MPZP, Osiedle", "url": "https://uldk.gugik.gov.pl", "uwagi": ""},
    {"nazwa": "Krajowa integracja miejscowych planów i ewidencji gruntów", "dostawca": "GUGiK",
     "co": "plany miejscowe i działki w gminach bez własnego WFS", "moduly": "MPZP", "url": "https://integracja.gugik.gov.pl", "uwagi": ""},
    {"nazwa": "Plany ogólne gmin i Rejestr Cen Nieruchomości (WMS)", "dostawca": "GUGiK (geoportal.gov.pl)",
     "co": "nakładki na mapę MPZP i Osiedla", "moduly": "MPZP, Osiedle", "url": "https://www.geoportal.gov.pl", "uwagi": ""},
    {"nazwa": "Ortofotomapa (WMS, także archiwalna)", "dostawca": "GUGiK",
     "co": "podkład zdjęć lotniczych, kronika zmian", "moduly": "MPZP, Osiedle, Teren, Dostępność", "url": "https://www.geoportal.gov.pl", "uwagi": ""},
    {"nazwa": "Rejestr Cen Nieruchomości (pliki GeoPackage)", "dostawca": "GUGiK / starostwa",
     "co": "transakcje mieszkań i działek — plik pobierasz sam z geoportalu", "moduly": "Ceny", "url": "https://www.geoportal.gov.pl/mapy/rejestr-cen-nieruchomosci/", "uwagi": "Warsztat czyta plik z dysku, nie pobiera go"},
    {"nazwa": "Plany miejscowe Poznania (WFS)", "dostawca": "Miejska Pracownia Urbanistyczna w Poznaniu",
     "co": "wydzielenia planistyczne z przeznaczeniem", "moduly": "MPZP", "url": "https://gis.mpu.pl", "uwagi": "przykład gminy z własną usługą"},
    {"nazwa": "API Sejmu (ELI)", "dostawca": "Kancelaria Sejmu",
     "co": "wyszukiwanie aktów i teksty PDF z Dziennika Ustaw", "moduly": "Przepisy", "url": "https://api.sejm.gov.pl/", "uwagi": "bez klucza"},
    {"nazwa": "OpenStreetMap (kafelki mapy)", "dostawca": "Fundacja OpenStreetMap i współtwórcy",
     "co": "podkład mapy", "moduly": "wszystkie mapy", "url": "https://www.openstreetmap.org/copyright",
     "uwagi": "dane © współtwórcy OpenStreetMap, licencja ODbL; kafelki wg zasad korzystania z serwerów OSM"},
    {"nazwa": "Gemini (API)", "dostawca": "Google",
     "co": "opisy wskaźników, pytania do przepisów, fiszki, przepisanie grafiku i notatki — tekst, nie liczby", "moduly": "Atlas, Przepisy, Fiszki, Praca",
     "url": "https://ai.google.dev", "uwagi": "tylko z kluczem GEMINI_API_KEY; wysyłany jest tekst albo plik, o który pytasz"},
]

# Biblioteki dołączone do Warsztatu w katalogu static/ (licencje z plików LICENSE obok)
BIBLIOTEKI_JS = [
    {"nazwa": "Leaflet", "wersja": "1.9.4", "licencja": "BSD-2-Clause", "plik": "static/leaflet/LICENSE"},
    {"nazwa": "Leaflet.draw", "wersja": "1.0.4", "licencja": "MIT", "plik": "static/leaflet-draw/LICENSE"},
]

PAKIETY = ("flask", "python-dotenv", "requests", "shapely", "h3", "pypdf", "google-genai", "pytest")


def _licencja(meta) -> str:
    """Krótka nazwa licencji z metadanych pakietu (pole albo klasyfikator)."""
    wyrazenie = meta.get("License-Expression")
    if wyrazenie:
        return wyrazenie
    tekst = (meta.get("License") or "").strip()
    if tekst and "\n" not in tekst and len(tekst) <= 40:
        return tekst
    for klasyfikator in meta.get_all("Classifier") or []:
        if klasyfikator.startswith("License :: OSI Approved :: "):
            return klasyfikator.rsplit(" :: ", 1)[1]
    return "zob. pakiet"


def biblioteki_pythona() -> list[dict]:
    wynik = []
    for nazwa in PAKIETY:
        try:
            meta = importlib.metadata.metadata(nazwa)
        except importlib.metadata.PackageNotFoundError:
            wynik.append({"nazwa": nazwa, "wersja": "nie zainstalowano", "licencja": "—"})
            continue
        wynik.append({"nazwa": meta.get("Name") or nazwa, "wersja": meta.get("Version"), "licencja": _licencja(meta)})
    return wynik
