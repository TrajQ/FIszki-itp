# ETAP 3 — moduł mpzp: działka → przeznaczenie — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zaimplementować realny moduł mpzp — klik na mapie Leaflet znajduje
działkę ewidencyjną (ULDK) i sprawdza jej przeznaczenie w planie
miejscowym gminy Poznań (WFS), zamiast obecnego placeholdera.

**Architecture:** Dwa nowe klienty usług zewnętrznych (`dane/uldk.py` dla
ULDK, `mpzp/wfs.py` dla WFS Poznania) plus mały rejestr gmin
(`mpzp/gminy.py`). WFS Poznania jest pobierany w całości raz i indeksowany
lokalnie przez `shapely.STRtree`, bo filtrowanie przestrzenne po stronie
WFS okazało się zawodne (zob. spec). `mpzp/routes.py` spina to w dwa
endpointy JSON, `mpzp/mpzp.js` (IIFE, wzorem reszty frontendu) obsługuje
mapę Leaflet wektorowaną lokalnie. Brak bazy danych modułu.

**Tech Stack:** Flask (istniejący), `requests` (nowa zależność — klient
HTTP do ULDK i WFS), `shapely` (nowa zależność — parsowanie geometrii i
point-in-polygon), Leaflet 1.9.4 (wektorowany lokalnie, jak `pdf.js` w
module fiszki), pytest (istniejący, wzorzec mockowania z `test_fiszki.py`).

**Spec:** `docs/superpowers/specs/2026-09-25-mpzp-etap3-design.md`

## Global Constraints

- Tylko jedna gmina obsługiwana: Poznań (TERYT-prefiks działki `306401`).
  Żadnej innej gminy, żadnego mechanizmu rejestracji dynamicznej.
- Wybór działki wyłącznie przez klik na mapie Leaflet — bez formularza
  numeru działki.
- Wynik to surowe atrybuty z WFS (np. `symb_t`) — bez słownika symboli,
  bez tłumaczenia przez Gemini. Moduł mpzp nie importuje `dane/gemini.py`.
- Brak własnej bazy danych modułu, brak historii zapytań.
- Nowe zależności w `requirements.txt`: `requests==2.34.2`,
  `shapely==2.1.2` — obie z wpisem w `DECISIONS.md` (D-005).
- Leaflet wektorowany lokalnie do `mpzp/static/leaflet/` — bez CDN, bez
  `node_modules` — z wpisem w `DECISIONS.md` (D-006).
- Brak nowych zmiennych w `.env`/`.env.example` — ULDK i WFS Poznania są
  publiczne, bez klucza/autoryzacji.
- Odświeżanie warstwy WFS wyłącznie ręczne (`POST /mpzp/odswiez`),
  blokujące, bez TTL/harmonogramu.
- Zero realnych wywołań sieciowych w testach — ULDK i WFS zawsze
  mockowane (`monkeypatch`), wzorem `test_fiszki.py`.
- Błędy zewnętrznych usług (ULDK, WFS) nigdy nie kończą się gołym 500 —
  zawsze czytelny JSON `{"blad": "..."}"` z kodem `502` (błąd
  komunikacji) albo `404`/`200` z komunikatem (brak wyniku, nieobsłużona
  gmina).
- Host aplikacji pozostaje `127.0.0.1` — bez zmian w `app.py`.
- Nazwy techniczne po angielsku, nazwy domenowe i komentarze po polsku
  (jak w reszcie projektu).

## Review Focus

- Klik dokładnie na granicy dwóch wydzieleń MPZP (punkt leżący na krawędzi
  wielokąta, nie w jego wnętrzu) — `shapely.Polygon.contains()` zwraca
  `False` dla punktów na brzegu, więc użytkownik klikający idealnie na
  widocznej na mapie linii dostałby fałszywe "brak planu". Rozwiązanie:
  `covers()` zamiast `contains()`. Test w Task 3.
- Wydzielenie MPZP z dziurą w środku (np. skwer z wysepką zabudowy) albo
  złożone z kilku rozłącznych części tej samej cechy (`gml:surfaceMember`
  w liczbie mnogiej) — naiwne parsowanie tylko zewnętrznego pierścienia
  pierwszego wielokąta dałoby błędny wynik point-in-polygon. Test w
  Task 3.
- Klik poza granicami Polski / w miejscu bez działki ewidencyjnej (ULDK
  zwraca `-1 brak wyników`) — endpoint musi zwrócić czytelny `404` z
  JSON, nie 500. Test w Task 4.
- Działka leży w gminie innej niż Poznań — endpoint musi mimo to zwrócić
  geometrię działki (do narysowania na mapie), tylko z komunikatem o
  nieobsłużonej gminie, bez próby odpytania WFS Poznania. Test w Task 4.
- Zerwane połączenie z ULDK albo WFS w trakcie pobierania całej warstwy
  (~22 MB) — musi zwrócić czytelny `502`, nie zawiesić serwera i nie
  zostawić częściowo wypełnionego cache'a, który potem cicho zwraca złe
  wyniki. Testy w Task 3 i Task 4.

---

## Task 1: `dane/uldk.py` — klient ULDK

**Files:**
- Create: `dane/uldk.py`
- Test: `tests/test_uldk.py`
- Modify: `requirements.txt` (dodaj `requests==2.34.2`, `shapely==2.1.2`)
- Modify: `DECISIONS.md` (dodaj D-005)

**Interfaces:**
- Produces: `dane.uldk.Dzialka` (dataclass: `id: str`, `geometria:
  shapely.geometry.base.BaseGeometry`, `teryt_gminy: str`),
  `dane.uldk.BladULDK(Exception)`,
  `dane.uldk.znajdz_dzialke(lat: float, lon: float) -> Dzialka | None`.

- [ ] **Step 1: Dodaj zależności i wpis w DECISIONS.md**

W `requirements.txt` dodaj na końcu:

```
requests==2.34.2
shapely==2.1.2
```

Na końcu `DECISIONS.md` dodaj:

```markdown

## D-005 — Zależności: requests i shapely
Data: 2026-09-25

**Decyzja:** Moduł mpzp korzysta z `requests==2.34.2` (klient HTTP do
ULDK i WFS gminy) oraz `shapely==2.1.2` (parsowanie geometrii WKT/GML,
point-in-polygon, indeks przestrzenny `STRtree`).

**Uzasadnienie:** `requests` jest czytelniejszy niż `urllib` z biblioteki
standardowej przy obsłudze zapytań GET z parametrami i statusami błędów.
`shapely` eliminuje ręczne parsowanie geometrii regexem i implementację
point-in-polygon od zera — sprawdzona biblioteka do geometrii
obliczeniowej, używana też przez GeoPandas i inne narzędzia GIS.

**Odrzucone alternatywy:**
- `urllib` z biblioteki standardowej — odrzucone, więcej kodu
  obsługującego błędy sieci/HTTP bez realnej korzyści.
- Ręczne parsowanie WKT/GML i własna implementacja point-in-polygon —
  odrzucone jako wynajdywanie koła na nowo przy dostępnej, dojrzałej
  bibliotece.
```

Zainstaluj zależności w wirtualnym środowisku:

```bash
.venv/bin/pip install requests==2.34.2 shapely==2.1.2
```

- [ ] **Step 2: Napisz nieprzechodzący test**

Utwórz `tests/test_uldk.py`:

```python
import dane.uldk as uldk


class _FejkowaOdpowiedz:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_znajduje_dzialke(monkeypatch):
    tekst = (
        "0\n"
        "306401_1.0051.AR_18.14|SRID=4326;POLYGON((16.93 52.40,16.94 52.40,"
        "16.94 52.41,16.93 52.41,16.93 52.40))"
    )
    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: _FejkowaOdpowiedz(tekst))

    dzialka = uldk.znajdz_dzialke(52.405, 16.935)

    assert dzialka is not None
    assert dzialka.id == "306401_1.0051.AR_18.14"
    assert dzialka.teryt_gminy == "306401"
    minx, miny, maxx, maxy = dzialka.geometria.bounds
    assert minx == 16.93 and maxx == 16.94
    assert miny == 52.40 and maxy == 52.41


def test_brak_dzialki_pod_punktem(monkeypatch):
    tekst = (
        "-1 brak wyników\n"
        "błędny format odpowiedzi XML, usługa zwróciła odpowiedź"
        "Zbiorcza baza danych obsłużyła zapytanie. "
    )
    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: _FejkowaOdpowiedz(tekst))

    assert uldk.znajdz_dzialke(54.6, 14.0) is None


def test_blad_polaczenia_podnosi_blad_uldk(monkeypatch):
    def podnies_wyjatek(*a, **k):
        raise uldk.requests.RequestException("connection refused")

    monkeypatch.setattr(uldk.requests, "get", podnies_wyjatek)

    try:
        uldk.znajdz_dzialke(52.4, 16.9)
        assert False, "oczekiwano BladULDK"
    except uldk.BladULDK:
        pass


def test_niepoprawna_odpowiedz_podnosi_blad_uldk(monkeypatch):
    monkeypatch.setattr(uldk.requests, "get", lambda *a, **k: _FejkowaOdpowiedz("0\nto nie jest poprawny wiersz"))

    try:
        uldk.znajdz_dzialke(52.4, 16.9)
        assert False, "oczekiwano BladULDK"
    except uldk.BladULDK:
        pass
```

- [ ] **Step 3: Uruchom test i sprawdź, że pada**

Run: `.venv/bin/pytest tests/test_uldk.py -v`
Expected: FAIL z `ModuleNotFoundError: No module named 'dane.uldk'` albo
podobnym (plik jeszcze nie istnieje).

- [ ] **Step 4: Napisz implementację**

Utwórz `dane/uldk.py`:

```python
"""Klient krajowej usługi ULDK (Usługa Lokalizacji Działek Katastralnych).

Usługa jest publiczna i bezkluczowa (uldk.gugik.gov.pl). Zwraca działkę
ewidencyjną pod wskazanym punktem — używana przez moduł mpzp do znalezienia
działki pod kliknięciem na mapie, zanim sprawdzimy jej przeznaczenie w WFS
gminy.
"""

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
```

- [ ] **Step 5: Uruchom testy i sprawdź, że przechodzą**

Run: `.venv/bin/pytest tests/test_uldk.py -v`
Expected: 4 passed

- [ ] **Step 6: Uruchom całą suitę testów**

Run: `.venv/bin/pytest -q`
Expected: wszystkie testy zielone (11 dotychczasowych + 4 nowe = 15
passed)

- [ ] **Step 7: Commit**

```bash
git add dane/uldk.py tests/test_uldk.py requirements.txt DECISIONS.md
git commit -m "ETAP 3: dodaj klienta ULDK (dane/uldk.py) i zależności requests/shapely"
```

---

## Task 2: `mpzp/gminy.py` — rejestr gmin

**Files:**
- Create: `mpzp/gminy.py`
- Test: `tests/test_gminy.py`

**Interfaces:**
- Produces: `mpzp.gminy.Gmina` (frozen dataclass: `nazwa: str`,
  `teryt_prefiks: str`, `wfs_url: str`, `type_name: str`,
  `pole_przeznaczenia: str`, `pole_geometrii: str`),
  `mpzp.gminy.GMINY: dict[str, Gmina]`,
  `mpzp.gminy.GMINA_PILOTAZOWA: Gmina`,
  `mpzp.gminy.znajdz_gmine(teryt_prefiks: str) -> Gmina | None`.

- [ ] **Step 1: Napisz nieprzechodzący test**

Utwórz `tests/test_gminy.py`:

```python
from mpzp.gminy import GMINA_PILOTAZOWA, znajdz_gmine


def test_znajduje_poznan():
    gmina = znajdz_gmine("306401")
    assert gmina is not None
    assert gmina.nazwa == "Poznań"
    assert gmina.pole_przeznaczenia == "symb_t"
    assert gmina.pole_geometrii == "shape"


def test_nieobslugiwana_gmina_zwraca_none():
    assert znajdz_gmine("999999") is None


def test_gmina_pilotazowa_to_poznan():
    assert GMINA_PILOTAZOWA.teryt_prefiks == "306401"
```

- [ ] **Step 2: Uruchom test i sprawdź, że pada**

Run: `.venv/bin/pytest tests/test_gminy.py -v`
Expected: FAIL z `ModuleNotFoundError: No module named 'mpzp.gminy'`

- [ ] **Step 3: Napisz implementację**

Utwórz `mpzp/gminy.py`:

```python
"""Rejestr gmin obsługiwanych przez moduł mpzp.

Świadomie tylko `dict` w kodzie — jedna gmina pilotażowa (Poznań), bez
mechanizmu wtyczek/dynamicznej rejestracji (zob. spec ETAPu 3, sekcja
"Poza zakresem").
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Gmina:
    nazwa: str
    teryt_prefiks: str
    wfs_url: str
    type_name: str
    pole_przeznaczenia: str
    pole_geometrii: str


GMINY: dict[str, Gmina] = {
    "306401": Gmina(
        nazwa="Poznań",
        teryt_prefiks="306401",
        wfs_url=(
            "https://gis.mpu.pl/server/services/Hosted/"
            "ZbiorDanychPrzestrzennychMPZP/MapServer/WFSServer"
        ),
        type_name="ZbiorDanychPrzestrzennychMPZP:app.WydzieleniePlanistyczne.MPZP",
        pole_przeznaczenia="symb_t",
        pole_geometrii="shape",
    ),
}

GMINA_PILOTAZOWA = GMINY["306401"]


def znajdz_gmine(teryt_prefiks: str) -> Gmina | None:
    return GMINY.get(teryt_prefiks)
```

- [ ] **Step 4: Uruchom testy i sprawdź, że przechodzą**

Run: `.venv/bin/pytest tests/test_gminy.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add mpzp/gminy.py tests/test_gminy.py
git commit -m "ETAP 3: dodaj rejestr gmin mpzp/gminy.py (Poznań jako pilotaż)"
```

---

## Task 3: `mpzp/wfs.py` — klient WFS, parsowanie GML, indeks STRtree

**Files:**
- Create: `mpzp/wfs.py`
- Test: `tests/test_wfs.py`

**Interfaces:**
- Consumes: `mpzp.gminy.Gmina` (Task 2).
- Produces: `mpzp.wfs.Wydzielenie` (dataclass: `geometria:
  shapely.geometry.base.BaseGeometry`, `atrybuty: dict[str, str]`),
  `mpzp.wfs.BladWFS(Exception)`,
  `mpzp.wfs.znajdz_przeznaczenie(gmina: Gmina, punkt: shapely.geometry.Point) -> Wydzielenie | None`,
  `mpzp.wfs.odswiez(gmina: Gmina) -> None`.

Odpowiedź WFS ma strukturę (przykład rzeczywisty, pobrany podczas
rozpoznania):

```xml
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    numberMatched="9727" numberReturned="1">
  <wfs:member>
    <ZbiorDanychPrzestrzennychMPZP:app.WydzieleniePlanistyczne.MPZP>
      <ZbiorDanychPrzestrzennychMPZP:symb_t>ZP</ZbiorDanychPrzestrzennychMPZP:symb_t>
      <ZbiorDanychPrzestrzennychMPZP:shape>
        <gml:MultiSurface srsName="urn:ogc:def:crs:EPSG::4326">
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>52.386 16.952 52.386 16.952 ...</gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:MultiSurface>
      </ZbiorDanychPrzestrzennychMPZP:shape>
    </ZbiorDanychPrzestrzennychMPZP:app.WydzieleniePlanistyczne.MPZP>
  </wfs:member>
</wfs:FeatureCollection>
```

Ważne: `gml:posList` dla EPSG:4326 zwraca współrzędne w kolejności
**lat lon** (potwierdzone na żywym serwerze), więc trzeba je zamienić na
`(lon, lat)` — odwrotnie niż WKT z ULDK, które już jest w kolejności
`(lon, lat)`.

- [ ] **Step 1: Przygotuj fixture'y XML**

Utwórz katalog `tests/fixtures/` i plik
`tests/fixtures/wfs_dwa_wydzielenia.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    xmlns:app="https://gis.mpu.pl/app"
    numberMatched="2" numberReturned="2">
  <wfs:member>
    <app:MPZP gml:id="app.MPZP.1">
      <app:symb_t>MN</app:symb_t>
      <app:shape>
        <gml:MultiSurface gml:id="app.MPZP.1.pl" srsName="urn:ogc:def:crs:EPSG::4326">
          <gml:surfaceMember>
            <gml:Polygon gml:id="app.MPZP.1.pl.0">
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>52.400 16.900 52.400 16.910 52.410 16.910 52.410 16.900 52.400 16.900</gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:MultiSurface>
      </app:shape>
    </app:MPZP>
  </wfs:member>
  <wfs:member>
    <app:MPZP gml:id="app.MPZP.2">
      <app:symb_t>ZP</app:symb_t>
      <app:shape>
        <gml:MultiSurface gml:id="app.MPZP.2.pl" srsName="urn:ogc:def:crs:EPSG::4326">
          <gml:surfaceMember>
            <gml:Polygon gml:id="app.MPZP.2.pl.0">
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>52.400 16.920 52.400 16.930 52.410 16.930 52.410 16.920 52.400 16.920</gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:MultiSurface>
      </app:shape>
    </app:MPZP>
  </wfs:member>
</wfs:FeatureCollection>
```

Utwórz `tests/fixtures/wfs_dziura.xml` (wydzielenie z otworem w środku —
np. skwer z wysepką zabudowy, którą trzeba wykluczyć z point-in-polygon):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    xmlns:app="https://gis.mpu.pl/app"
    numberMatched="1" numberReturned="1">
  <wfs:member>
    <app:MPZP gml:id="app.MPZP.3">
      <app:symb_t>ZP</app:symb_t>
      <app:shape>
        <gml:MultiSurface gml:id="app.MPZP.3.pl" srsName="urn:ogc:def:crs:EPSG::4326">
          <gml:surfaceMember>
            <gml:Polygon gml:id="app.MPZP.3.pl.0">
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>52.500 16.900 52.500 16.920 52.520 16.920 52.520 16.900 52.500 16.900</gml:posList>
                </gml:LinearRing>
              </gml:exterior>
              <gml:interior>
                <gml:LinearRing>
                  <gml:posList>52.505 16.905 52.505 16.915 52.515 16.915 52.515 16.905 52.505 16.905</gml:posList>
                </gml:LinearRing>
              </gml:interior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:MultiSurface>
      </app:shape>
    </app:MPZP>
  </wfs:member>
</wfs:FeatureCollection>
```

Utwórz `tests/fixtures/wfs_multisurface.xml` (jedna cecha złożona z dwóch
rozłącznych wielokątów — realny przypadek, gdy działka/wydzielenie jest
przecięte np. drogą):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    xmlns:app="https://gis.mpu.pl/app"
    numberMatched="1" numberReturned="1">
  <wfs:member>
    <app:MPZP gml:id="app.MPZP.4">
      <app:symb_t>MN</app:symb_t>
      <app:shape>
        <gml:MultiSurface gml:id="app.MPZP.4.pl" srsName="urn:ogc:def:crs:EPSG::4326">
          <gml:surfaceMember>
            <gml:Polygon gml:id="app.MPZP.4.pl.0">
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>52.600 16.900 52.600 16.905 52.605 16.905 52.605 16.900 52.600 16.900</gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
          <gml:surfaceMember>
            <gml:Polygon gml:id="app.MPZP.4.pl.1">
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>52.600 16.950 52.600 16.955 52.605 16.955 52.605 16.950 52.600 16.950</gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:MultiSurface>
      </app:shape>
    </app:MPZP>
  </wfs:member>
</wfs:FeatureCollection>
```

Utwórz `tests/fixtures/wfs_pusta.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    numberMatched="0" numberReturned="0">
</wfs:FeatureCollection>
```

- [ ] **Step 2: Napisz nieprzechodzące testy**

Utwórz `tests/test_wfs.py`:

```python
from pathlib import Path

import pytest
from shapely.geometry import Point

import mpzp.wfs as wfs
from mpzp.gminy import GMINA_PILOTAZOWA

FIXTURES = Path(__file__).parent / "fixtures"


class _FejkowaOdpowiedz:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


@pytest.fixture(autouse=True)
def wyczysc_cache():
    wfs._cache.clear()
    yield
    wfs._cache.clear()


def _mockuj_jedna_strone(monkeypatch, tekst_xml):
    monkeypatch.setattr(wfs.requests, "get", lambda *a, **k: _FejkowaOdpowiedz(tekst_xml))


def test_znajduje_wydzielenie_w_pierwszym_kwadracie(monkeypatch):
    tekst = (FIXTURES / "wfs_dwa_wydzielenia.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.905, 52.405))

    assert wynik is not None
    assert wynik.atrybuty["symb_t"] == "MN"


def test_znajduje_wydzielenie_w_drugim_kwadracie(monkeypatch):
    tekst = (FIXTURES / "wfs_dwa_wydzielenia.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.925, 52.405))

    assert wynik is not None
    assert wynik.atrybuty["symb_t"] == "ZP"


def test_punkt_miedzy_wydzieleniami_zwraca_none(monkeypatch):
    tekst = (FIXTURES / "wfs_dwa_wydzielenia.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.915, 52.405))

    assert wynik is None


def test_punkt_dokladnie_na_granicy_jest_pokryty(monkeypatch):
    tekst = (FIXTURES / "wfs_dwa_wydzielenia.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    # (16.910, 52.405) leży dokładnie na prawej krawędzi pierwszego kwadratu.
    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.910, 52.405))

    assert wynik is not None
    assert wynik.atrybuty["symb_t"] == "MN"


def test_dziura_w_wydzieleniu_jest_wykluczona(monkeypatch):
    tekst = (FIXTURES / "wfs_dziura.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    w_obwarzanku = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.902, 52.502))
    w_dziurze = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.910, 52.510))

    assert w_obwarzanku is not None
    assert w_dziurze is None


def test_multisurface_obie_czesci_naleza_do_tej_samej_cechy(monkeypatch):
    tekst = (FIXTURES / "wfs_multisurface.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    czesc_a = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.902, 52.602))
    czesc_b = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.952, 52.602))

    assert czesc_a is not None and czesc_a.atrybuty["symb_t"] == "MN"
    assert czesc_b is not None and czesc_b.atrybuty["symb_t"] == "MN"


def test_pusta_warstwa_zwraca_none(monkeypatch):
    tekst = (FIXTURES / "wfs_pusta.xml").read_text(encoding="utf-8")
    _mockuj_jedna_strone(monkeypatch, tekst)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.905, 52.405))

    assert wynik is None


def test_blad_polaczenia_podnosi_blad_wfs(monkeypatch):
    def podnies_wyjatek(*a, **k):
        raise wfs.requests.RequestException("connection refused")

    monkeypatch.setattr(wfs.requests, "get", podnies_wyjatek)

    try:
        wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.905, 52.405))
        assert False, "oczekiwano BladWFS"
    except wfs.BladWFS:
        pass


def test_niepoprawny_xml_podnosi_blad_wfs(monkeypatch):
    _mockuj_jedna_strone(monkeypatch, "to nie jest xml")

    try:
        wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.905, 52.405))
        assert False, "oczekiwano BladWFS"
    except wfs.BladWFS:
        pass


def test_stronicowanie_pobiera_wszystkie_strony(monkeypatch):
    strona_1 = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
        'xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:app="https://gis.mpu.pl/app" '
        'numberMatched="2" numberReturned="1">'
        '<wfs:member><app:MPZP><app:symb_t>MN</app:symb_t><app:shape>'
        '<gml:MultiSurface srsName="urn:ogc:def:crs:EPSG::4326"><gml:surfaceMember>'
        '<gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>'
        "52.400 16.900 52.400 16.910 52.410 16.910 52.410 16.900 52.400 16.900"
        "</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"
        "</gml:surfaceMember></gml:MultiSurface></app:shape></app:MPZP></wfs:member>"
        "</wfs:FeatureCollection>"
    )
    strona_2 = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
        'xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:app="https://gis.mpu.pl/app" '
        'numberMatched="2" numberReturned="1">'
        '<wfs:member><app:MPZP><app:symb_t>ZP</app:symb_t><app:shape>'
        '<gml:MultiSurface srsName="urn:ogc:def:crs:EPSG::4326"><gml:surfaceMember>'
        '<gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>'
        "52.400 16.920 52.400 16.930 52.410 16.930 52.410 16.920 52.400 16.920"
        "</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"
        "</gml:surfaceMember></gml:MultiSurface></app:shape></app:MPZP></wfs:member>"
        "</wfs:FeatureCollection>"
    )

    wolania = []

    def fejkowe_get(url, params, timeout):
        wolania.append(params["startIndex"])
        tekst = strona_1 if params["startIndex"] == 0 else strona_2
        return _FejkowaOdpowiedz(tekst)

    monkeypatch.setattr(wfs.requests, "get", fejkowe_get)

    wynik = wfs.znajdz_przeznaczenie(GMINA_PILOTAZOWA, Point(16.925, 52.405))

    assert wynik is not None
    assert wynik.atrybuty["symb_t"] == "ZP"
    assert wolania == [0, 1]
```

- [ ] **Step 3: Uruchom testy i sprawdź, że padają**

Run: `.venv/bin/pytest tests/test_wfs.py -v`
Expected: FAIL z `ModuleNotFoundError: No module named 'mpzp.wfs'`

- [ ] **Step 4: Napisz implementację**

Utwórz `mpzp/wfs.py`:

```python
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
```

- [ ] **Step 5: Uruchom testy i sprawdź, że przechodzą**

Run: `.venv/bin/pytest tests/test_wfs.py -v`
Expected: 10 passed

- [ ] **Step 6: Uruchom całą suitę testów**

Run: `.venv/bin/pytest -q`
Expected: wszystkie testy zielone (15 + 3 + 10 = 28 passed)

- [ ] **Step 7: Commit**

```bash
git add mpzp/wfs.py tests/test_wfs.py tests/fixtures/
git commit -m "ETAP 3: dodaj klienta WFS (mpzp/wfs.py) z indeksem STRtree"
```

---

## Task 4: `mpzp/routes.py` — endpointy `/sprawdz` i `/odswiez`

**Files:**
- Modify: `mpzp/routes.py`
- Test: `tests/test_mpzp.py`

**Interfaces:**
- Consumes: `dane.uldk.znajdz_dzialke`, `dane.uldk.BladULDK`,
  `dane.uldk.Dzialka` (Task 1); `mpzp.gminy.znajdz_gmine`,
  `mpzp.gminy.GMINA_PILOTAZOWA` (Task 2); `mpzp.wfs.znajdz_przeznaczenie`,
  `mpzp.wfs.odswiez`, `mpzp.wfs.BladWFS`, `mpzp.wfs.Wydzielenie` (Task 3).
- Produces: `GET /mpzp/sprawdz?lat=..&lon=..` → JSON, `POST /mpzp/odswiez`
  → JSON.

- [ ] **Step 1: Napisz nieprzechodzące testy**

Utwórz `tests/test_mpzp.py`:

```python
import pytest
from shapely.geometry import Point, Polygon

from app import create_app
import mpzp.routes as mpzp_routes
from dane.uldk import BladULDK, Dzialka
from mpzp.wfs import BladWFS, Wydzielenie


@pytest.fixture
def app(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


def _dzialka_poznan():
    return Dzialka(
        id="306401_1.0051.AR_18.14",
        geometria=Polygon([(16.93, 52.40), (16.94, 52.40), (16.94, 52.41), (16.93, 52.41)]),
        teryt_gminy="306401",
    )


def test_sprawdz_bez_wspolrzednych(client):
    odpowiedz = client.get("/mpzp/sprawdz")
    assert odpowiedz.status_code == 400
    assert "blad" in odpowiedz.get_json()


def test_sprawdz_niepoprawne_wspolrzedne(client):
    odpowiedz = client.get("/mpzp/sprawdz?lat=abc&lon=16.9")
    assert odpowiedz.status_code == 400


def test_sprawdz_brak_dzialki(client, monkeypatch):
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: None)

    odpowiedz = client.get("/mpzp/sprawdz?lat=54.6&lon=14.0")

    assert odpowiedz.status_code == 404
    assert odpowiedz.get_json()["blad"] == "Brak działki w tym miejscu."


def test_sprawdz_blad_uldk(client, monkeypatch):
    def podnies(lat, lon):
        raise BladULDK("Błąd połączenia z ULDK: timeout")

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", podnies)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.4&lon=16.9")

    assert odpowiedz.status_code == 502
    assert "blad" in odpowiedz.get_json()


def test_sprawdz_inna_gmina(client, monkeypatch):
    dzialka = Dzialka(
        id="999999_1.0001.AR_1.1",
        geometria=Polygon([(21.0, 52.2), (21.01, 52.2), (21.01, 52.21), (21.0, 52.21)]),
        teryt_gminy="999999",
    )
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: dzialka)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.2&lon=21.0")
    dane = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert dane["dzialka"]["id"] == "999999_1.0001.AR_1.1"
    assert dane["blad"] == "Ta gmina nie jest jeszcze obsługiwana (pilotaż: Poznań)."
    assert "wydzielenie" not in dane


def test_sprawdz_brak_planu(client, monkeypatch):
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_poznan())
    monkeypatch.setattr(mpzp_routes, "znajdz_przeznaczenie", lambda gmina, punkt: None)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.405&lon=16.935")
    dane = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert dane["blad"] == "Brak planu miejscowego dla tej działki."
    assert "wydzielenie" not in dane


def test_sprawdz_sukces(client, monkeypatch):
    wydzielenie = Wydzielenie(
        geometria=Polygon([(16.93, 52.40), (16.94, 52.40), (16.94, 52.41), (16.93, 52.41)]),
        atrybuty={"symb_t": "ZP", "kod_mpzp": "306401 9R1"},
    )
    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_poznan())
    monkeypatch.setattr(mpzp_routes, "znajdz_przeznaczenie", lambda gmina, punkt: wydzielenie)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.405&lon=16.935")
    dane = odpowiedz.get_json()

    assert odpowiedz.status_code == 200
    assert "blad" not in dane
    assert dane["wydzielenie"]["atrybuty"]["symb_t"] == "ZP"
    assert dane["dzialka"]["geometria"]["type"] == "Polygon"


def test_sprawdz_blad_wfs(client, monkeypatch):
    def podnies(gmina, punkt):
        raise BladWFS("Błąd połączenia z WFS gminy Poznań: timeout")

    monkeypatch.setattr(mpzp_routes, "znajdz_dzialke", lambda lat, lon: _dzialka_poznan())
    monkeypatch.setattr(mpzp_routes, "znajdz_przeznaczenie", podnies)

    odpowiedz = client.get("/mpzp/sprawdz?lat=52.405&lon=16.935")
    dane = odpowiedz.get_json()

    assert odpowiedz.status_code == 502
    assert "dzialka" in dane
    assert "blad" in dane


def test_odswiez_sukces(client, monkeypatch):
    wolania = []
    monkeypatch.setattr(mpzp_routes, "odswiez_warstwe", lambda gmina: wolania.append(gmina))

    odpowiedz = client.post("/mpzp/odswiez")

    assert odpowiedz.status_code == 200
    assert odpowiedz.get_json() == {"ok": True}
    assert len(wolania) == 1


def test_odswiez_blad(client, monkeypatch):
    def podnies(gmina):
        raise BladWFS("Błąd połączenia z WFS gminy Poznań: timeout")

    monkeypatch.setattr(mpzp_routes, "odswiez_warstwe", podnies)

    odpowiedz = client.post("/mpzp/odswiez")

    assert odpowiedz.status_code == 502
    assert "blad" in odpowiedz.get_json()
```

- [ ] **Step 2: Uruchom testy i sprawdź, że padają**

Run: `.venv/bin/pytest tests/test_mpzp.py -v`
Expected: FAIL — `AttributeError` (routes.py nie eksportuje jeszcze
`znajdz_dzialke`/`znajdz_przeznaczenie`/`odswiez_warstwe`) albo 404
(endpointy jeszcze nie istnieją).

- [ ] **Step 3: Napisz implementację**

Zastąp całą zawartość `mpzp/routes.py`:

```python
from flask import Blueprint, jsonify, render_template, request
from shapely.geometry import Point, mapping

from dane.uldk import BladULDK, znajdz_dzialke
from mpzp.gminy import GMINA_PILOTAZOWA, znajdz_gmine
from mpzp.wfs import BladWFS, odswiez as odswiez_warstwe, znajdz_przeznaczenie

mpzp_bp = Blueprint(
    "mpzp",
    __name__,
    template_folder="templates",
    static_folder="static",
)


@mpzp_bp.route("/")
def index():
    return render_template("mpzp/index.html")


@mpzp_bp.route("/sprawdz")
def sprawdz():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return jsonify({"blad": "Brak poprawnych współrzędnych lat/lon."}), 400

    try:
        dzialka = znajdz_dzialke(lat, lon)
    except BladULDK as e:
        return jsonify({"blad": str(e)}), 502

    if dzialka is None:
        return jsonify({"blad": "Brak działki w tym miejscu."}), 404

    wynik = {"dzialka": {"id": dzialka.id, "geometria": mapping(dzialka.geometria)}}

    gmina = znajdz_gmine(dzialka.teryt_gminy)
    if gmina is None:
        wynik["blad"] = "Ta gmina nie jest jeszcze obsługiwana (pilotaż: Poznań)."
        return jsonify(wynik)

    try:
        wydzielenie = znajdz_przeznaczenie(gmina, Point(lon, lat))
    except BladWFS as e:
        wynik["blad"] = str(e)
        return jsonify(wynik), 502

    if wydzielenie is None:
        wynik["blad"] = "Brak planu miejscowego dla tej działki."
        return jsonify(wynik)

    wynik["wydzielenie"] = {
        "geometria": mapping(wydzielenie.geometria),
        "atrybuty": wydzielenie.atrybuty,
    }
    return jsonify(wynik)


@mpzp_bp.route("/odswiez", methods=["POST"])
def odswiez():
    try:
        odswiez_warstwe(GMINA_PILOTAZOWA)
    except BladWFS as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify({"ok": True})
```

- [ ] **Step 4: Uruchom testy i sprawdź, że przechodzą**

Run: `.venv/bin/pytest tests/test_mpzp.py -v`
Expected: 10 passed

- [ ] **Step 5: Uruchom całą suitę testów**

Run: `.venv/bin/pytest -q`
Expected: wszystkie testy zielone (28 + 10 = 38 passed)

- [ ] **Step 6: Commit**

```bash
git add mpzp/routes.py tests/test_mpzp.py
git commit -m "ETAP 3: dodaj endpointy /mpzp/sprawdz i /mpzp/odswiez"
```

---

## Task 5: Leaflet wektorowany lokalnie

**Files:**
- Create: `mpzp/static/leaflet/leaflet.js`
- Create: `mpzp/static/leaflet/leaflet.css`
- Create: `mpzp/static/leaflet/images/layers-2x.png`
- Create: `mpzp/static/leaflet/images/layers.png`
- Create: `mpzp/static/leaflet/images/marker-icon-2x.png`
- Create: `mpzp/static/leaflet/images/marker-icon.png`
- Create: `mpzp/static/leaflet/images/marker-shadow.png`
- Create: `mpzp/static/leaflet/LICENSE`
- Create: `mpzp/static/leaflet/VERSION.txt`
- Modify: `DECISIONS.md` (dodaj D-006)
- Test: brak (zasoby statyczne — zweryfikowane wizualnie w Task 6)

- [ ] **Step 1: Pobierz i wypakuj paczkę Leaflet 1.9.4**

```bash
cd /tmp
curl -sL "https://registry.npmjs.org/leaflet/-/leaflet-1.9.4.tgz" -o leaflet.tgz
rm -rf leaflet_pkg && mkdir leaflet_pkg
tar -xzf leaflet.tgz -C leaflet_pkg
cd /home/trajq/warsztat
mkdir -p mpzp/static/leaflet/images
cp /tmp/leaflet_pkg/package/dist/leaflet.js mpzp/static/leaflet/leaflet.js
cp /tmp/leaflet_pkg/package/dist/leaflet.css mpzp/static/leaflet/leaflet.css
cp /tmp/leaflet_pkg/package/dist/images/layers-2x.png mpzp/static/leaflet/images/
cp /tmp/leaflet_pkg/package/dist/images/layers.png mpzp/static/leaflet/images/
cp /tmp/leaflet_pkg/package/dist/images/marker-icon-2x.png mpzp/static/leaflet/images/
cp /tmp/leaflet_pkg/package/dist/images/marker-icon.png mpzp/static/leaflet/images/
cp /tmp/leaflet_pkg/package/dist/images/marker-shadow.png mpzp/static/leaflet/images/
cp /tmp/leaflet_pkg/package/LICENSE mpzp/static/leaflet/LICENSE
```

- [ ] **Step 2: Sprawdź, że pliki są na miejscu i mają sensowny rozmiar**

Run: `ls -la mpzp/static/leaflet/ mpzp/static/leaflet/images/`
Expected: `leaflet.js` (~140 KB), `leaflet.css` (~15 KB), `LICENSE` i 5
plików `.png` w `images/`, wszystkie niezerowej wielkości.

- [ ] **Step 3: Utwórz `VERSION.txt`**

Utwórz `mpzp/static/leaflet/VERSION.txt`:

```
Leaflet 1.9.4
Źródło: https://registry.npmjs.org/leaflet/-/leaflet-1.9.4.tgz
Pliki: leaflet.js, leaflet.css, images/ (layers-2x.png, layers.png,
marker-icon-2x.png, marker-icon.png, marker-shadow.png) — build dist,
bez node_modules/kroku budowania.
Wektorowane lokalnie zgodnie z zasadą CLAUDE.md: bez CDN.
Licencja: BSD-2-Clause (LICENSE w tym folderze)
```

- [ ] **Step 4: Dodaj wpis w DECISIONS.md**

Na końcu `DECISIONS.md` dodaj:

```markdown

## D-006 — Leaflet wektorowany lokalnie
Data: 2026-09-25

**Decyzja:** Mapa w module mpzp korzysta z Leaflet 1.9.4, wektorowanego
lokalnie do `mpzp/static/leaflet/` (`leaflet.js`, `leaflet.css`, obrazy
markerów/warstw) — bez CDN, bez `node_modules`/kroku budowania. Wersja
przypięta w `VERSION.txt` w tym samym folderze.

**Uzasadnienie:** Zgodne z zasadą CLAUDE.md (żadnego CDN dla Leafleta) i
z podejściem do `pdf.js` z ETAPu 2 (D-003) — biblioteka trzymana lokalnie
w repo, aplikacja działa offline dla warstwy UI niezależnie od
zewnętrznego hosta biblioteki. (Kafelki mapy bazowej nadal wymagają
połączenia z internetem — to dane, nie kod, więc reguła anty-CDN ich nie
dotyczy, podobnie jak zapytania do WFS/ULDK.)

**Odrzucone alternatywy:**
- CDN (np. unpkg, cdnjs) — odrzucone zgodnie z zasadą CLAUDE.md.
```

- [ ] **Step 5: Uruchom całą suitę testów (upewnij się, że nic nie zepsuto)**

Run: `.venv/bin/pytest -q`
Expected: 38 passed

- [ ] **Step 6: Commit**

```bash
git add mpzp/static/leaflet/ DECISIONS.md
git commit -m "ETAP 3: wektoryzuj Leaflet 1.9.4 lokalnie (mpzp/static/leaflet/)"
```

---

## Task 6: Frontend — mapa, klik, panel wyniku, przycisk odświeżenia

**Files:**
- Modify: `mpzp/templates/mpzp/index.html`
- Modify: `mpzp/static/mpzp.css`
- Create: `mpzp/static/mpzp.js`
- Test: brak testów pytest (frontend czysto wizualny) — weryfikacja
  ręczna w przeglądarce w Step 4, zgodnie z zasadą CLAUDE.md o testowaniu
  zmian UI.

**Interfaces:**
- Consumes: `GET /mpzp/sprawdz?lat=..&lon=..`, `POST /mpzp/odswiez`
  (Task 4). Odpowiedź `dane.dzialka.geometria` i
  `dane.wydzielenie.geometria` to obiekty GeoJSON (z `shapely.geometry.mapping`)
  — bezpośrednio konsumowalne przez `L.geoJSON()`.

- [ ] **Step 1: Zastąp `mpzp/templates/mpzp/index.html`**

```html
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>MPZP — Warsztat</title>
    <link rel="stylesheet" href="{{ url_for('mpzp.static', filename='leaflet/leaflet.css') }}">
    <link rel="stylesheet" href="{{ url_for('mpzp.static', filename='mpzp.css') }}">
</head>
<body>
    <p><a href="{{ url_for('index') }}">← strona główna</a></p>
    <h1>MPZP — działka i przeznaczenie</h1>
    <p>Kliknij punkt na mapie, żeby sprawdzić działkę i jej przeznaczenie
    w planie miejscowym (obsługiwana gmina pilotażowa: Poznań).</p>

    <div id="pasek-narzedzi">
        <button id="przycisk-odswiez" type="button">Odśwież dane gminy</button>
    </div>

    <div id="uklad">
        <div id="mapa"></div>
        <div id="panel-wyniku">
            <p>Kliknij punkt na mapie.</p>
        </div>
    </div>

    <script>
        const URL_SPRAWDZ = "{{ url_for('mpzp.sprawdz') }}";
        const URL_ODSWIEZ = "{{ url_for('mpzp.odswiez') }}";
    </script>
    <script src="{{ url_for('mpzp.static', filename='leaflet/leaflet.js') }}"></script>
    <script src="{{ url_for('mpzp.static', filename='mpzp.js') }}"></script>
</body>
</html>
```

- [ ] **Step 2: Zastąp `mpzp/static/mpzp.css`**

```css
#uklad {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
}

#mapa {
    width: 70%;
    height: 600px;
    border: 1px solid #ccc;
}

#panel-wyniku {
    width: 30%;
    min-height: 600px;
    border: 1px solid #ccc;
    padding: 0.75rem;
    box-sizing: border-box;
    font-size: 0.9rem;
}

#panel-wyniku table {
    width: 100%;
    border-collapse: collapse;
}

#panel-wyniku th, #panel-wyniku td {
    text-align: left;
    padding: 0.25rem 0.4rem;
    border-bottom: 1px solid #eee;
    word-break: break-word;
}

#panel-wyniku .blad {
    color: #b00020;
}

#pasek-narzedzi {
    margin: 0.5rem 0;
}
```

- [ ] **Step 3: Utwórz `mpzp/static/mpzp.js`**

```javascript
(function () {
    "use strict";

    const mapa = L.map("mapa").setView([52.4064, 16.9252], 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 19,
    }).addTo(mapa);

    const panelWyniku = document.getElementById("panel-wyniku");
    const przyciskOdswiez = document.getElementById("przycisk-odswiez");

    let warstwaDzialki = null;
    let warstwaWydzielenia = null;

    function wyczyscWarstwy() {
        if (warstwaDzialki) {
            mapa.removeLayer(warstwaDzialki);
            warstwaDzialki = null;
        }
        if (warstwaWydzielenia) {
            mapa.removeLayer(warstwaWydzielenia);
            warstwaWydzielenia = null;
        }
    }

    function pokazBlad(tresc) {
        panelWyniku.innerHTML = "<p class=\"blad\"></p>";
        panelWyniku.querySelector(".blad").textContent = tresc;
    }

    function pokazAtrybuty(atrybuty) {
        panelWyniku.innerHTML = "";
        const tabela = document.createElement("table");
        for (const [klucz, wartosc] of Object.entries(atrybuty)) {
            const wiersz = document.createElement("tr");
            const naglowek = document.createElement("th");
            naglowek.textContent = klucz;
            const komorka = document.createElement("td");
            komorka.textContent = wartosc;
            wiersz.appendChild(naglowek);
            wiersz.appendChild(komorka);
            tabela.appendChild(wiersz);
        }
        panelWyniku.appendChild(tabela);
    }

    mapa.on("click", function (zdarzenie) {
        const lat = zdarzenie.latlng.lat;
        const lon = zdarzenie.latlng.lng;

        wyczyscWarstwy();
        panelWyniku.innerHTML = "<p>Sprawdzam...</p>";

        fetch(`${URL_SPRAWDZ}?lat=${lat}&lon=${lon}`)
            .then((odpowiedz) => odpowiedz.json())
            .then((dane) => {
                if (dane.dzialka) {
                    warstwaDzialki = L.geoJSON(dane.dzialka.geometria, {
                        style: { color: "#3388ff", weight: 2, fillOpacity: 0.1 },
                    }).addTo(mapa);
                }

                if (dane.wydzielenie) {
                    warstwaWydzielenia = L.geoJSON(dane.wydzielenie.geometria, {
                        style: { color: "#2ecc71", weight: 2, fillOpacity: 0.3 },
                    }).addTo(mapa);
                    pokazAtrybuty(dane.wydzielenie.atrybuty);
                } else if (dane.blad) {
                    pokazBlad(dane.blad);
                }
            })
            .catch(() => pokazBlad("Błąd połączenia z serwerem."));
    });

    przyciskOdswiez.addEventListener("click", function () {
        przyciskOdswiez.disabled = true;
        przyciskOdswiez.textContent = "Odświeżanie danych gminy...";

        fetch(URL_ODSWIEZ, { method: "POST" })
            .then((odpowiedz) => odpowiedz.json())
            .then((dane) => {
                if (dane.blad) {
                    pokazBlad(dane.blad);
                }
            })
            .catch(() => pokazBlad("Błąd połączenia z serwerem."))
            .finally(() => {
                przyciskOdswiez.disabled = false;
                przyciskOdswiez.textContent = "Odśwież dane gminy";
            });
    });
})();
```

- [ ] **Step 4: Ręczna weryfikacja w przeglądarce**

Uruchom serwer deweloperski:

```bash
.venv/bin/python app.py
```

W przeglądarce otwórz `http://127.0.0.1:<PORT>/mpzp/` (port z `.env`/
`config.py`) i sprawdź:

1. Mapa się ładuje, wyśrodkowana na Poznaniu.
2. Klik w centrum Poznania (np. w okolicy Placu Wolności) → po chwili na
   mapie pojawia się niebieski obrys działki i zielony obrys wydzielenia,
   a w panelu po prawej tabela z atrybutami (`symb_t` i inne).
3. Klik w miejscu bez działki (np. na rzece/jeziorze) → panel pokazuje
   "Brak działki w tym miejscu.", bez błędu w konsoli przeglądarki.
4. Klik w innym mieście (np. w Warszawie, ok. 52.23, 21.01) → na mapie
   pojawia się obrys działki, a panel pokazuje komunikat o nieobsłużonej
   gminie.
5. Przycisk "Odśwież dane gminy" → tekst przycisku zmienia się na
   "Odświeżanie danych gminy...", przycisk jest zablokowany, po kilku
   sekundach wraca do stanu początkowego.
6. Konsola przeglądarki (F12) nie pokazuje błędów JS podczas całego
   powyższego scenariusza.

Jeśli którykolwiek krok zawiedzie, popraw kod przed przejściem dalej —
nie oznaczaj tego kroku jako zrobiony bez realnej weryfikacji w
przeglądarce.

- [ ] **Step 5: Uruchom całą suitę testów**

Run: `.venv/bin/pytest -q`
Expected: 38 passed (frontend nie dodaje testów pytest, ale upewnij się,
że nic nie zepsuto)

- [ ] **Step 6: Commit**

```bash
git add mpzp/templates/mpzp/index.html mpzp/static/mpzp.css mpzp/static/mpzp.js
git commit -m "ETAP 3: dodaj frontend mpzp — mapa Leaflet, klik, panel wyniku"
```

---

## Task 7: Zamknięcie ETAPu 3 — dokumentacja i release

**Files:**
- Modify: `docs/PROGRESS.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `CLAUDE.md` (sekcja "Stan bieżący")
- Create: `releases/warsztat_etap3_20260925.zip` (niewersjonowany,
  `releases/` jest w `.gitignore`)

- [ ] **Step 1: Uruchom pełną suitę testów i upewnij się, że wszystko jest zielone**

Run: `.venv/bin/pytest -q`
Expected: 38 passed, 0 failed

- [ ] **Step 2: Dodaj wpis w `docs/PROGRESS.md`**

Na końcu pliku dodaj (i usuń/zaktualizuj poprzedni "Następny krok" pod
ETAPem 2, żeby nie wprowadzał w błąd):

```markdown

## ETAP 3 — Moduł mpzp (działka → przeznaczenie, gmina pilotażowa Poznań)
Data: 2026-09-25
Status: zamknięty

Zrobione:
- Klient ULDK (`dane/uldk.py`): `znajdz_dzialke(lat, lon)`, parsuje
  odpowiedź tekstową ULDK (sukces/brak wyników/błąd), zwraca geometrię
  jako obiekt shapely, błędy jako `BladULDK`
- Rejestr gmin (`mpzp/gminy.py`): jedna pozycja — Poznań (WFS
  `gis.mpu.pl`, warstwa `WydzieleniePlanistyczne.MPZP`, atrybut
  przeznaczenia `symb_t`)
- Klient WFS (`mpzp/wfs.py`): pobiera całą warstwę gminy raz (WFS
  Poznania nie honoruje filtrów przestrzennych — zwracały 0 wyników w
  rozpoznaniu), parsuje GML (obsługa dziur i wielokątów złożonych z kilku
  części), indeksuje `shapely.STRtree`, point-in-polygon przez `covers()`
  (żeby kliknięcie dokładnie na granicy też trafiało), błędy jako
  `BladWFS`
- Endpointy `mpzp/routes.py`: `GET /mpzp/sprawdz?lat=..&lon=..` (działka +
  przeznaczenie albo czytelny komunikat błędu), `POST /mpzp/odswiez`
  (wymuszenie ponownego pobrania warstwy WFS)
- Frontend (`mpzp.js` + `index.html` + `mpzp.css`): mapa Leaflet
  wektorowana lokalnie, klik na mapie, rysowanie działki i wydzielenia,
  panel wyniku z surowymi atrybutami WFS, przycisk odświeżenia danych
  gminy
- Testy (mockowane ULDK i WFS, zero realnych wywołań sieciowych):
  parsowanie odpowiedzi ULDK (sukces/brak/błąd), parsowanie GML z WFS
  (proste wydzielenia, dziura w wydzieleniu, wielokąt złożony z kilku
  części, stronicowanie, pusta warstwa, błędy sieci/XML), wszystkie
  ścieżki endpointu `/mpzp/sprawdz` (brak współrzędnych, brak działki,
  inna gmina, brak planu, sukces, błędy ULDK/WFS jako 502) i
  `/mpzp/odswiez`
- `DECISIONS.md`: D-005 (`requests`, `shapely`), D-006 (Leaflet lokalnie)

Poza zakresem (świadomie odłożone): obsługa więcej niż jednej gminy,
słownik symboli MPZP (tłumaczenie `ZP`/`MN`/itd.), użycie Gemini w mpzp,
historia sprawdzonych działek, wybór działki po numerze ewidencyjnym,
naprawa filtra przestrzennego WFS (obejście: pobranie całej warstwy).

Testy: 38 passed / 0 failed
Ostatni ZIP: releases/warsztat_etap3_20260925.zip

Następny krok: wybór kolejnego modułu do realnej implementacji (atlas
albo dostepnosc).
```

- [ ] **Step 3: Dodaj wpis w `docs/CHANGELOG.md`**

Na końcu pliku dodaj:

```markdown

## ETAP 3 — 2026-09-25
- Dodano moduł mpzp: klik na mapie Leaflet znajduje działkę ewidencyjną
  (ULDK) i sprawdza jej przeznaczenie w planie miejscowym gminy Poznań
  (WFS).
- Dodano warstwę `dane/uldk.py` (klient krajowej usługi ULDK).
- Dodano `mpzp/gminy.py` (rejestr gmin, na start tylko Poznań) i
  `mpzp/wfs.py` (klient WFS z lokalnym indeksem przestrzennym
  `shapely.STRtree`).
- Dodano endpointy `GET /mpzp/sprawdz` i `POST /mpzp/odswiez`.
- Dodano zależności `requests` i `shapely` (`requirements.txt`).
- Dodano Leaflet 1.9.4 wektorowany lokalnie (`mpzp/static/leaflet/`).
- Dodano `DECISIONS.md` D-005, D-006.
- Dodano testy modułu mpzp (ULDK i WFS mockowane, bez realnych wywołań
  sieciowych).
```

- [ ] **Step 4: Zaktualizuj sekcję "Stan bieżący" w `CLAUDE.md`**

Zamień istniejącą sekcję `## Stan bieżący` na końcu pliku na:

```markdown
## Stan bieżący
ETAP: 3 (moduł mpzp — zamknięty)
Ostatni ZIP: releases/warsztat_etap3_20260925.zip
Testy: 38 passed / 0 failed
```

- [ ] **Step 5: Zbuduj release ZIP**

```bash
mkdir -p releases
zip -r releases/warsztat_etap3_20260925.zip $(git ls-files) -x '.git/*'
```

Run: `unzip -l releases/warsztat_etap3_20260925.zip | tail -5`
Expected: archiwum istnieje, zawiera pliki `mpzp/wfs.py`,
`mpzp/static/leaflet/leaflet.js` i pozostałe świeżo dodane pliki.

- [ ] **Step 6: Commit**

```bash
git add docs/PROGRESS.md docs/CHANGELOG.md CLAUDE.md
git commit -m "ETAP 3: zamknięcie — dokumentacja, testy zielone (38 passed)"
```

(Release ZIP w `releases/` jest gitignorowany — nie trzeba/nie da się go
commitować, zgodnie z `.gitignore` i praktyką ETAPu 1/2.)

---

## Self-Review

**Pokrycie specyfikacji:**
- Gmina pilotażowa Poznań, WFS `gis.mpu.pl`, `symb_t` → Task 2, 3, 4. ✓
- Wybór działki przez klik na mapie (nie formularz) → Task 6. ✓
- Wynik jako surowe atrybuty WFS, bez słownika/Gemini → Task 3
  (`Wydzielenie.atrybuty` to surowy `dict`), Task 4 (przekazywane wprost
  do JSON), moduł mpzp nigdzie nie importuje `dane/gemini.py`. ✓
- Brak własnej bazy danych → żaden task nie tworzy schematu/bazy dla
  mpzp. ✓
- `dane/uldk.py`, `mpzp/gminy.py`, `mpzp/wfs.py`, rozbudowa
  `mpzp/routes.py` i frontendu → Task 1, 2, 3, 4, 6. ✓
- Nowe zależności `requests`, `shapely` + wpis w DECISIONS.md → Task 1
  (D-005). ✓
- Strategia WFS: pobranie całej warstwy, lokalny `STRtree`,
  point-in-polygon lokalnie → Task 3. ✓
- Przepływ danych z sekcji spec (błąd ULDK, brak działki, inna gmina,
  brak planu, sukces) → Task 4, dokładnie te ścieżki jako osobne testy. ✓
- Odświeżanie ręczne, blokujące, bez TTL → Task 3 (`odswiez()` bez
  harmonogramu), Task 4 (`POST /mpzp/odswiez`), Task 6 (przycisk). ✓
- Testowanie z mockowanym ULDK/WFS, fixtures XML → Task 1, 3, 4. ✓
- `.env.example` bez zmian → żaden task go nie modyfikuje. ✓
- Poza zakresem (wielu gmin, słownik symboli, Gemini, historia, numer
  działki, naprawa filtra WFS) → żaden task tego nie implementuje;
  jawnie wypisane w Task 7 jako świadomie odłożone. ✓

**Skan placeholderów:** brak "TBD"/"TODO"/"do ustalenia" w krokach
zadaniowych — decyzja "kiedy pobrać warstwę" ze spec (odłożona tam do
planu) została rozstrzygnięta w Task 3/4 jako leniwe pobranie przy
pierwszym wywołaniu `znajdz_przeznaczenie()`, nie przy starcie aplikacji
(prostsze, bez zmian w `app.py`, zgodne z "jeden ETAP na raz").

**Spójność typów:** `Dzialka` (Task 1: `id`, `geometria`, `teryt_gminy`)
używane identycznie w Task 4. `Gmina` (Task 2: `nazwa`, `teryt_prefiks`,
`wfs_url`, `type_name`, `pole_przeznaczenia`, `pole_geometrii`) — pola
zgodne w Task 3 (`_pobierz_strone`, `_sparsuj_kolekcje` używają
`gmina.wfs_url`, `gmina.type_name`, `gmina.pole_geometrii`) i w Task 4
(`GMINA_PILOTAZOWA` przekazywane do `znajdz_przeznaczenie`/
`odswiez_warstwe`). `Wydzielenie` (Task 3: `geometria`, `atrybuty`)
identyczne w Task 4 testach i w prawdziwym imporcie. Nazwa funkcji w
routes.py to `odswiez_warstwe` (alias importu `odswiez as
odswiez_warstwe`) konsekwentnie w Task 4 kodzie i testach
(`monkeypatch.setattr(mpzp_routes, "odswiez_warstwe", ...)`).

**Review Focus — pokrycie testami:**
- Klik na granicy wydzielenia (`covers()` vs `contains()`) →
  `test_punkt_dokladnie_na_granicy_jest_pokryty` w Task 3. ✓
- Dziura/wielokąt wieloczęściowy → `test_dziura_w_wydzieleniu_jest_wykluczona`,
  `test_multisurface_obie_czesci_naleza_do_tej_samej_cechy` w Task 3. ✓
- Klik poza Polską/bez działki → `test_sprawdz_brak_dzialki` (404) w
  Task 4. ✓
- Działka w innej gminie → `test_sprawdz_inna_gmina` w Task 4. ✓
- Zerwane połączenie ULDK/WFS → `test_blad_polaczenia_podnosi_blad_uldk`
  (Task 1), `test_blad_polaczenia_podnosi_blad_wfs` (Task 3),
  `test_sprawdz_blad_uldk`, `test_sprawdz_blad_wfs`,
  `test_odswiez_blad` (Task 4). ✓
