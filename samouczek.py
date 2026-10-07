"""Samouczek z danymi przykładowymi — bez internetu (ETAP 247).

Przykłady tworzymy w modułach zwykłymi funkcjami ich baz (bez
skrótów do SQL), z nazwą zaczynającą się od PREFIKS, żeby dało się je
rozpoznać i usunąć jednym przyciskiem. Wszystkie liczby w przykładach to
dane wymyślone do nauki (okolica Poznania), nie pomiary.

- Teren: projekt „Inwentaryzacja zieleni” z punktami (dwie
  inwentaryzacje — rok po roku — do porównania i „zmiany w czasie”),
- Osiedle: koncepcja z obszarem, terenami, budynkami i ustaleniami planu,
- Praca: przykładowy grafik do wklejenia (tekst, nie baza),
- Dostępność ma własny plik przykładowy (ETAP 37).
"""

import math
import random

PREFIKS = "Przykład — "
NAZWA_TERENU = PREFIKS + "zieleń przy szkole 2025"
NAZWA_TERENU_2 = PREFIKS + "zieleń przy szkole 2026"
NAZWA_OSIEDLA = PREFIKS + "osiedle przy parku"

SRODEK = (52.4064, 16.9252)  # Poznań, Stary Rynek — tylko punkt odniesienia

# Przykładowy grafik w układzie „komórka po komórce” (jak PDF z Google Docs)
GRAFIK = """Październik 2026
poniedziałek wtorek środa czwartek piątek sobota niedziela
1.
Ola
15:30-20:00
2.
Ty
8:30-14:30
6.
Ty
15:30-20:00
9.
Ty
8:30-12:30
14.
Ty
15:30-20:00
21.
Ola
15:30-20:00
23.
Ty
16:00-20:00
30.
Ty
8:30-14:30
"""
IMIE_W_GRAFIKU = "Ty"


def _przesun(dx_m: float, dy_m: float) -> tuple[float, float]:
    """Punkt dx/dy metrów od SRODEK (lat, lng) — przybliżenie lokalne."""
    lat = SRODEK[0] + dy_m / 111_320
    lng = SRODEK[1] + dx_m / (111_320 * math.cos(math.radians(SRODEK[0])))
    return lat, lng


def _punkty_zieleni(rok: int, losowe: random.Random) -> list[dict]:
    stany = ["dobry", "średni", "zły", "do usunięcia"]
    gatunki = ["lipa drobnolistna", "klon zwyczajny", "dąb szypułkowy", "kasztanowiec", "brzoza brodawkowata"]
    punkty = []
    for i in range(12):
        lat, lng = _przesun(-120 + (i % 4) * 80, -60 + (i // 4) * 60)
        # rok później: część drzew się pogarsza — do porównania inwentaryzacji
        stan = stany[min(3, (i * 7) % 3 + (1 if rok == 2026 and i % 4 == 0 else 0))]
        punkty.append({
            "uid": f"przyklad{rok}{i:02d}", "lat": round(lat + losowe.uniform(-2, 2) / 111_320, 6), "lng": round(lng, 6),
            "dokladnosc_m": round(losowe.uniform(3, 8), 1), "czas": f"{rok}-05-{10 + i // 6:02d}T{9 + i % 6:02d}:{(i * 7) % 60:02d}",
            "wartosci": {"obiekt": "drzewo", "gatunek": gatunki[i % len(gatunki)], "obwód pnia [cm]": 60 + i * 9 + (4 if rok == 2026 else 0), "stan": stan},
            "uwagi": "", "zdjecie": None,
        })
    return punkty


def _prostokat(x0: float, y0: float, szer: float, wys: float, funkcja: str, **wlasciwosci) -> dict:
    narozniki = [(x0, y0), (x0 + szer, y0), (x0 + szer, y0 + wys), (x0, y0 + wys), (x0, y0)]
    pierscien = [[round(lng, 7), round(lat, 7)] for lat, lng in (_przesun(x, y) for x, y in narozniki)]
    return {"type": "Feature", "properties": {"funkcja": funkcja, **wlasciwosci}, "geometry": {"type": "Polygon", "coordinates": [pierscien]}}


def koncepcja_osiedla() -> tuple[dict, dict]:
    """(rysunek GeoJSON, ustawienia) przykładowej koncepcji — ok. 2 ha."""
    rysunek = {"type": "FeatureCollection", "features": [
        _prostokat(300, 300, 200, 100, "obszar"),
        _prostokat(300, 300, 120, 100, "MW", pbc_proc=30),
        _prostokat(420, 340, 80, 60, "ZP"),
        _prostokat(420, 300, 80, 40, "U"),
        _prostokat(300, 300, 200, 8, "KD"),
        _prostokat(315, 320, 40, 14, "budynek", kondygnacje=5, zielony_dach_proc=50),
        _prostokat(315, 355, 40, 14, "budynek", kondygnacje=5),
        _prostokat(370, 325, 14, 50, "budynek", kondygnacje=4),
        _prostokat(430, 310, 30, 20, "budynek", kondygnacje=2),
    ]}
    ustawienia = {"plan": {"max_zabudowa_proc": 35, "min_pbc_proc": 30, "max_intensywnosc": 1.2, "max_kondygnacje": 5}}
    return rysunek, ustawienia


def wczytaj() -> dict:
    """Tworzy brakujące przykłady (ponowne wywołanie niczego nie dubluje)."""
    from osiedle import baza as baza_osiedla
    from teren import baza as baza_terenu
    from teren.projekt import WZORY

    utworzone = []
    istniejace = {p["nazwa"] for p in baza_terenu.projekty()}
    for nazwa, rok in ((NAZWA_TERENU, 2025), (NAZWA_TERENU_2, 2026)):
        if nazwa not in istniejace:
            projekt_id = baza_terenu.utworz_projekt(nazwa, WZORY["zielen"]["pola"])
            baza_terenu.zapisz_punkty(projekt_id, _punkty_zieleni(rok, random.Random(rok)))
            utworzone.append(nazwa)
    if NAZWA_OSIEDLA not in {k["nazwa"] for k in baza_osiedla.lista()}:
        rysunek, ustawienia = koncepcja_osiedla()
        koncepcja_id = baza_osiedla.utworz(NAZWA_OSIEDLA)
        baza_osiedla.zapisz(koncepcja_id, geojson=rysunek, ustawienia=ustawienia)
        utworzone.append(NAZWA_OSIEDLA)
    return {"utworzone": utworzone, "linki": linki()}


def linki() -> dict:
    """Adresy przykładów, które już są (do kroków samouczka)."""
    from osiedle import baza as baza_osiedla
    from teren import baza as baza_terenu

    teren = {p["nazwa"]: p["id"] for p in baza_terenu.projekty()}
    osiedla = {k["nazwa"]: k["id"] for k in baza_osiedla.lista()}
    return {"teren": teren.get(NAZWA_TERENU), "teren_2": teren.get(NAZWA_TERENU_2), "osiedle": osiedla.get(NAZWA_OSIEDLA)}


def usun() -> int:
    """Przykłady do kosza modułów (jak zwykłe usunięcie) — zwraca ich liczbę."""
    from osiedle import baza as baza_osiedla
    from teren import baza as baza_terenu

    ile = 0
    for p in baza_terenu.projekty():
        if p["nazwa"].startswith(PREFIKS):
            baza_terenu.usun_projekt(p["id"])
            ile += 1
    for k in baza_osiedla.lista():
        if k["nazwa"].startswith(PREFIKS):
            baza_osiedla.usun(k["id"])
            ile += 1
    return ile
