"""Kartogram do druku jako SVG — do pracy zaliczeniowej albo raportu.

Elementy mapy tematycznej, których wymaga się na zajęciach z kartografii:
tytuł, legenda (z liczebnością klas), podziałka liniowa, strzałka
północy, źródło danych i metoda klasyfikacji. SVG jest wektorowy, więc
da się go dalej edytować (Inkscape, Illustrator) albo wydrukować do PDF.

Odwzorowanie: proste walcowe równoodległościowe ze skalą długości
cos(φ₀) dla środka województwa. W skali jednego województwa zniekształcenia
są rzędu ułamka procenta — do kartogramu wystarczy, a nie potrzebujemy
biblioteki do odwzorowań. Podziałka liczona dla środkowej szerokości.
"""

import math
from html import escape

SZEROKOSC, WYSOKOSC = 1123, 794  # A4 poziomo w px (96 dpi)
MARGINES = 40
POLE_MAPY = (MARGINES, 110, 760, WYSOKOSC - 70)  # x0, y0, x1, y1
KOLUMNA_LEGENDY = 800
KM_NA_STOPIEN = 111.32
KOLOR_BRAK = "#c7c7cc"
LADNE_DLUGOSCI_KM = (1, 2, 5, 10, 20, 25, 50, 100, 200)


def _pierscienie(geometria: dict) -> list[list]:
    if geometria["type"] == "Polygon":
        return geometria["coordinates"]
    if geometria["type"] == "MultiPolygon":
        return [p for wielokat in geometria["coordinates"] for p in wielokat]
    return []


def _zasieg(cechy: list[dict]) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for cecha in cechy:
        for pierscien in _pierscienie(cecha["geometry"]):
            for x, y in pierscien:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def kartogram_svg(
    granice: dict,
    kolory: dict[str, str],
    tytul: str,
    podtytul: str,
    legenda: list[tuple[str, str, int | None]],
    tytul_legendy: str,
    przypisy: list[str],
) -> str:
    """SVG z kartogramem. kolory: {teryt: kolor}; legenda: [(kolor, opis, liczba gmin)]."""
    cechy = [c for c in granice["features"] if _pierscienie(c["geometry"])]
    if not cechy:
        raise ValueError("Brak granic gmin do narysowania.")
    min_lon, min_lat, max_lon, max_lat = _zasieg(cechy)
    wsp_dlugosci = math.cos(math.radians((min_lat + max_lat) / 2))

    x0, y0, x1, y1 = POLE_MAPY
    szer_stopni = (max_lon - min_lon) * wsp_dlugosci
    wys_stopni = max_lat - min_lat
    skala = min((x1 - x0) / szer_stopni, (y1 - y0) / wys_stopni)  # px na „stopień szerokości”
    przesun_x = x0 + ((x1 - x0) - szer_stopni * skala) / 2
    przesun_y = y0 + ((y1 - y0) - wys_stopni * skala) / 2

    def punkt(lon: float, lat: float) -> str:
        return f"{przesun_x + (lon - min_lon) * wsp_dlugosci * skala:.1f},{przesun_y + (max_lat - lat) * skala:.1f}"

    czesci = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SZEROKOSC}" height="{WYSOKOSC}" '
        f'viewBox="0 0 {SZEROKOSC} {WYSOKOSC}" font-family="Helvetica, Arial, sans-serif">',
        f'<rect width="{SZEROKOSC}" height="{WYSOKOSC}" fill="#ffffff"/>',
        f'<text x="{MARGINES}" y="52" font-size="24" font-weight="700" fill="#1d1d1f">{escape(tytul)}</text>',
        f'<text x="{MARGINES}" y="80" font-size="15" fill="#6e6e73">{escape(podtytul)}</text>',
        '<g stroke="#ffffff" stroke-width="0.6" stroke-linejoin="round">',
    ]
    for cecha in cechy:
        teryt = cecha["properties"].get("teryt", "")
        sciezka = " ".join(
            "M" + " L".join(punkt(lon, lat) for lon, lat in pierscien) + " Z"
            for pierscien in _pierscienie(cecha["geometry"])
        )
        nazwa = escape(cecha["properties"].get("nazwa") or teryt)
        czesci.append(
            f'<path d="{sciezka}" fill="{kolory.get(teryt, KOLOR_BRAK)}" fill-rule="evenodd"><title>{nazwa}</title></path>'
        )
    czesci.append("</g>")

    czesci += _legenda(legenda, tytul_legendy)
    czesci += _podzialka(skala)
    czesci += _polnoc()
    for i, przypis in enumerate(przypisy):
        czesci.append(
            f'<text x="{MARGINES}" y="{WYSOKOSC - 44 + i * 16}" font-size="11" fill="#6e6e73">{escape(przypis)}</text>'
        )
    czesci.append("</svg>")
    return "\n".join(czesci)


def _legenda(legenda: list[tuple], tytul_legendy: str) -> list[str]:
    x, y = KOLUMNA_LEGENDY, 140
    wynik = [f'<text x="{x}" y="{y}" font-size="14" font-weight="700" fill="#1d1d1f">{escape(tytul_legendy)}</text>']
    for i, (kolor, opis, liczba) in enumerate(legenda):
        wiersz_y = y + 22 + i * 28
        wynik.append(f'<rect x="{x}" y="{wiersz_y}" width="28" height="18" rx="3" fill="{kolor}" stroke="#d2d2d7" stroke-width="0.5"/>')
        wynik.append(f'<text x="{x + 38}" y="{wiersz_y + 14}" font-size="13" fill="#1d1d1f">{escape(opis)}</text>')
        if liczba is not None:
            wynik.append(
                f'<text x="{SZEROKOSC - MARGINES}" y="{wiersz_y + 14}" font-size="12" fill="#6e6e73" text-anchor="end">{liczba}</text>'
            )
    if any(liczba is not None for _, _, liczba in legenda):
        wynik.append(
            f'<text x="{SZEROKOSC - MARGINES}" y="{y}" font-size="11" fill="#6e6e73" text-anchor="end">liczba gmin</text>'
        )
    return wynik


def dlugosc_podzialki_km(km_na_px: float, maks_px: float = 180) -> float:
    """Największa „ładna” długość podziałki mieszcząca się w maks_px."""
    pasujace = [d for d in LADNE_DLUGOSCI_KM if d / km_na_px <= maks_px]
    return pasujace[-1] if pasujace else LADNE_DLUGOSCI_KM[0]


def _podzialka(skala: float) -> list[str]:
    km_na_px = KM_NA_STOPIEN / skala
    km = dlugosc_podzialki_km(km_na_px)
    dlugosc_px = km / km_na_px
    x, y = KOLUMNA_LEGENDY, WYSOKOSC - 120
    polowa = dlugosc_px / 2
    return [
        f'<rect x="{x}" y="{y}" width="{polowa:.1f}" height="6" fill="#1d1d1f"/>',
        f'<rect x="{x + polowa:.1f}" y="{y}" width="{polowa:.1f}" height="6" fill="#ffffff" stroke="#1d1d1f" stroke-width="1"/>',
        f'<text x="{x}" y="{y + 22}" font-size="11" fill="#1d1d1f">0</text>',
        f'<text x="{x + dlugosc_px:.1f}" y="{y + 22}" font-size="11" fill="#1d1d1f" text-anchor="middle">{km:g} km</text>',
    ]


def _polnoc() -> list[str]:
    x, y = SZEROKOSC - MARGINES - 16, WYSOKOSC - 150
    return [
        f'<polygon points="{x},{y - 30} {x - 10},{y} {x},{y - 7} {x + 10},{y}" fill="#1d1d1f"/>',
        f'<text x="{x}" y="{y + 18}" font-size="14" font-weight="700" fill="#1d1d1f" text-anchor="middle">N</text>',
    ]
