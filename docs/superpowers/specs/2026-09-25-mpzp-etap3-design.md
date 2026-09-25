# ETAP 3 — moduł mpzp: działka → przeznaczenie (projekt)

Data: 2026-09-25
Status: zaakceptowany przez użytkownika (brainstorming), gotowy do writing-plans

## Cel

Realna implementacja modułu mpzp: użytkownik klika punkt na mapie, aplikacja
znajduje działkę ewidencyjną pod tym punktem (ULDK) i sprawdza jej
przeznaczenie w miejscowym planie zagospodarowania przestrzennego (WFS
gminy). Obecnie moduł to placeholder (`mpzp/routes.py` ma tylko pusty
widok `index`).

## Zakres ETAPu 3 (ustalony w brainstormingu)

- Jedna gmina pilotażowa: **Poznań**. Rozpoznanie potwierdziło działający
  WFS 2.0 (`https://gis.mpu.pl/server/services/Hosted/ZbiorDanychPrzestrzennychMPZP/MapServer/WFSServer`),
  warstwę `ZbiorDanychPrzestrzennychMPZP:app.WydzieleniePlanistyczne.MPZP`
  z realnymi danymi (9727 obiektów), atrybutem przeznaczenia `symb_t`
  (np. `ZP`, `MN`) i geometrią dostępną we WGS84 przez `srsName=EPSG:4326`.
- Wybór działki: **klik na mapie Leaflet** (nie formularz z numerem działki).
- Wynik: **surowe atrybuty z WFS**, bez słownika symboli i bez Gemini —
  ten moduł nie korzysta z warstwy `dane/gemini.py`.
- **Bez własnej bazy danych** — brak historii sprawdzonych działek. Czysto
  żywe narzędzie "klik → wynik".
- Poza zakresem (świadomie odłożone, analogicznie do ETAPu 2): obsługa
  wielu gmin / rejestr rozszerzalny, słownik symboli MPZP, tłumaczenie
  przeznaczenia przez Gemini, historia zapytań, numer działki jako
  alternatywne wejście.

## Rozpoznanie techniczne (wykonane w trakcie brainstormingu)

- **ULDK** (`uldk.gugik.gov.pl`) — usługa krajowa, bez klucza API.
  `GetParcelByXY` ze `srid=4326` zwraca ID działki i geometrię WKT
  bezpośrednio we WGS84 — zero potrzeby transformacji współrzędnych po
  naszej stronie dla geometrii działki.
- **WFS Poznania** — zwraca geometrię w natywnym EPSG:2177, ale honoruje
  `srsName=EPSG:4326` w `GetFeature` i reprojektuje wynik na WGS84
  (potwierdzone: `posList` wraca jako stopnie, nie metry). Dzięki temu
  **nie potrzebujemy `pyproj`** ani ręcznej transformacji układów.
- **Filtrowanie przestrzenne po stronie WFS zawodne**: próby `BBOX` (różne
  układy współrzędnych i kolejności osi) oraz `fes:Intersects` przez POST
  z punktem konsekwentnie zwracały 0 wyników, mimo testowania punktami
  leżącymi wewnątrz znanych poligonów z tej samej warstwy. Przyczyna nie
  została ustalona (możliwe: niestabilna kolejność stronicowania w
  ArcGIS FeatureServer, ograniczenie usługi) — **decyzja: nie polegać na
  spatial filter WFS**, tylko pobrać całą warstwę i indeksować lokalnie.
- **Rozmiar danych**: próbka 200 obiektów (już we WGS84) waży ~460 KB
  (~2,3 KB/obiekt). Dla całej warstwy (~9727 obiektów) to ok. **22 MB**
  surowego GML pobieranego jednorazowo z sieci; w pamięci procesu (same
  geometrie shapely + atrybuty, bez narzutu XML) rząd kilku MB.

## Architektura

Nowe/zmienione komponenty:

- **`dane/uldk.py`** (nowy) — klient ULDK w warstwie współdzielonej `dane/`
  (obok `gemini.py`), bo ULDK jest usługą krajową i potencjalnie przydatną
  innym modułom w przyszłości.
  - `znajdz_dzialke(lat: float, lon: float) -> Dzialka | None`
  - `Dzialka`: id działki, geometria (WKT/shapely), TERYT
  - błędy jako `BladULDK` (analogicznie do `BladGemini`)

- **`mpzp/gminy.py`** (nowy) — rejestr obsługiwanych gmin: słownik z jedną
  pozycją dla Poznania (prefiks TERYT, adres WFS, `typeName` warstwy,
  nazwa atrybutu przeznaczenia). Świadomie tylko `dict` w kodzie modułu,
  bez mechanizmu pluginów/rejestracji dynamicznej — jedna gmina na start,
  zgodnie z zasadą "nie twórz uniwersalnych abstrakcji dla dwóch modułów"
  zastosowaną tu do samej liczby gmin.

- **`mpzp/wfs.py`** (nowy) — klient WFS specyficzny dla mpzp:
  - pobranie całej warstwy dla danej gminy (stronicowane `GetFeature`,
    `count`/`startIndex`, `srsName=EPSG:4326`)
  - budowa `shapely.STRtree` nad geometriami
  - `znajdz_przeznaczenie(punkt) -> Wydzielenie | None` (kandydaci przez
    STRtree, dokładny test `polygon.contains(point)`)
  - cache warstwy trzymany jako moduł-level singleton w pamięci procesu;
    odświeżany przy pierwszym użyciu i ręcznie (`odswiez()`)
  - błędy jako `BladWFS`

- **`mpzp/routes.py`** (rozbudowa):
  - `GET /mpzp/` — widok mapy (bez zmian w koncepcji, tylko realny
    frontend zamiast pustego placeholdera)
  - `GET /mpzp/sprawdz?lat=..&lon=..` — JSON: geometria działki +
    przeznaczenie albo czytelny komunikat błędu
  - `POST /mpzp/odswiez` — wymuszenie ponownego pobrania warstwy WFS

- **`mpzp/static/mpzp.js`** (nowy) + **`mpzp/templates/mpzp/index.html`**
  (rozbudowa) — mapa Leaflet (wzorzec z pozostałych modułów, biblioteka
  lokalnie), obsługa kliknięcia, rysowanie geometrii działki i wydzielenia,
  panel wyniku, przycisk odświeżenia danych gminy.

Brak zmian w `app.py` poza tym, co już jest (blueprint już zarejestrowany).
Brak nowej bazy danych/tabel.

## Przepływ danych

1. Pierwsze wejście na `/mpzp/` (albo start aplikacji — szczegół do
   ustalenia w planie) uruchamia pobranie całej warstwy WFS dla Poznania
   i budowę indeksu `STRtree`. UI pokazuje stan "wczytywanie danych
   gminy...".
2. Klik na mapie → frontend wysyła `lat, lon` do `GET /mpzp/sprawdz`.
3. Backend: `dane/uldk.py::znajdz_dzialke(lat, lon)`.
   - brak działki pod punktem → `{"blad": "Brak działki w tym miejscu."}`
   - `BladULDK` (sieć/timeout) → czytelny JSON błędu, nie 500
4. Sprawdzenie TERYT działki względem skonfigurowanej gminy pilotażowej.
   - inna gmina → `{"blad": "Ta gmina nie jest jeszcze obsługiwana
     (pilotaż: Poznań)."}`, ale geometria działki i tak wraca do
     wyświetlenia na mapie
5. Jeśli gmina pasuje: `mpzp/wfs.py::znajdz_przeznaczenie(...)` na
   geometrii/punkcie działki.
   - brak trafienia (działka poza wszystkimi wydzieleniami) →
     `{"blad": "Brak planu miejscowego dla tej działki."}`
6. Sukces: geometria działki + surowe atrybuty wydzielenia (`symb_t`,
   `kod_mpzp`, `nr_ter`, itd. — bez interpretacji/tłumaczenia).

## Odświeżanie danych

Ręczne, przyciskiem w UI (`POST /mpzp/odswiez`) — blokujące na czas
pobierania, z komunikatem w UI. Bez automatycznego TTL/harmonogramu:
dane MPZP nie zmieniają się często, a moduł jest jednoosobowy/uczący.

## Testowanie

- Testy z mockowanym ULDK i WFS (wzorzec z modułu fiszki/Gemini) — zero
  realnych wywołań sieciowych w pytest.
- Do mocków: próbki XML (GetCapabilities, DescribeFeatureType, GetFeature)
  pobrane podczas rozpoznania — jako fixtures.
- Pokrycie: parsowanie odpowiedzi ULDK, parsowanie GML z WFS,
  point-in-polygon przez STRtree, wszystkie ścieżki błędów endpointu
  `/mpzp/sprawdz` (brak działki, inna gmina, brak planu, sukces, błąd
  sieci ULDK/WFS).

## Zależności i konfiguracja

- Nowe zależności w `requirements.txt`: `requests`, `shapely` — obie z
  wpisem uzasadniającym w `DECISIONS.md` (klient HTTP czytelniejszy niż
  `urllib`; `shapely` do parsowania geometrii WFS/ULDK i point-in-polygon
  zamiast ręcznego parsowania GML/WKT regexem).
- `.env.example` — brak nowych zmiennych; ULDK i WFS Poznania są
  publiczne, bez autoryzacji.

## Poza zakresem ETAPu 3 (odłożone świadomie)

- Obsługa więcej niż jednej gminy / rejestr rozszerzalny.
- Słownik symboli MPZP (tłumaczenie `ZP`, `MN` itd. na opis).
- Wykorzystanie Gemini w module mpzp.
- Historia sprawdzonych działek / własna baza modułu.
- Wybór działki po numerze ewidencyjnym (tylko klik na mapie).
- Naprawa/wyjaśnienie, dlaczego spatial filter WFS (`BBOX`/`Intersects`)
  zwraca 0 wyników — obeszliśmy to pobraniem całej warstwy.
