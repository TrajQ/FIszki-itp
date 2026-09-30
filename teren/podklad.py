"""Podkład mapy w formularzu na telefon (ETAP 83).

Obszar prac projektu [południe, zachód, północ, wschód] w stopniach →
prostokąt w Web Mercator (EPSG:3857) → jeden obraz ortofotomapy GUGiK
(dane/ortofoto.py), osadzony w pliku HTML jako data URL. Telefon rysuje
go na płótnie w tym samym układzie, więc punkty GPS trafiają we właściwe
miejsca. Obszar ograniczony, żeby obraz miał sensowną szczegółowość i
rozmiar pliku.
"""

import base64
import math

from dane import ortofoto

MAKS_BOK_M = 3000  # dłuższy bok obszaru prac
MIN_BOK_M = 50
MAKS_PX = 1600
_R = 6378137.0


class BladObszaru(ValueError):
    """Niepoprawny obszar prac."""


def web_mercator(lat: float, lon: float) -> tuple[float, float]:
    return _R * math.radians(lon), _R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def sprawdz_obszar(obszar) -> list[float]:
    """[południe, zachód, północ, wschód] — liczby, kolejność, wielkość."""
    if not isinstance(obszar, list) or len(obszar) != 4:
        raise BladObszaru("Obszar to [południe, zachód, północ, wschód].")
    try:
        s, w, n, e = (float(v) for v in obszar)
    except (TypeError, ValueError):
        raise BladObszaru("Obszar: współrzędne muszą być liczbami.") from None
    if not (-85 <= s < n <= 85 and -180 <= w < e <= 180):
        raise BladObszaru("Obszar: złe współrzędne (południe < północ, zachód < wschód).")
    szer_m = (e - w) * 111_320 * math.cos(math.radians((s + n) / 2))
    wys_m = (n - s) * 110_574
    if max(szer_m, wys_m) > MAKS_BOK_M:
        raise BladObszaru(f"Obszar prac może mieć najwyżej {MAKS_BOK_M / 1000:g} km boku — przybliż mapę.")
    if min(szer_m, wys_m) < MIN_BOK_M:
        raise BladObszaru(f"Obszar prac musi mieć co najmniej {MIN_BOK_M} m boku.")
    return [round(v, 7) for v in (s, w, n, e)]


def podklad(obszar: list[float]) -> dict:
    """{"obraz": data URL albo None, "bbox_3857", "szerokosc", "wysokosc", "blad"}."""
    s, w, n, e = obszar
    x1, y1 = web_mercator(s, w)
    x2, y2 = web_mercator(n, e)
    proporcja = (x2 - x1) / (y2 - y1)
    szer, wys = (MAKS_PX, round(MAKS_PX / proporcja)) if proporcja >= 1 else (round(MAKS_PX * proporcja), MAKS_PX)
    wynik = {"bbox_3857": [x1, y1, x2, y2], "szerokosc": szer, "wysokosc": wys, "obraz": None, "blad": None}
    try:
        jpeg = ortofoto.obraz_ortofotomapy((x1, y1, x2, y2), szer, wys)
        wynik["obraz"] = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
    except ortofoto.BladOrtofoto as e:
        wynik["blad"] = str(e)
    return wynik
