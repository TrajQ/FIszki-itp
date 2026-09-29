"""Raport dostępności do druku: mapa SVG i dane do strony raportu (ETAP 48).

Mapa ma elementy wymagane na mapie tematycznej: tytuł, legendę z
liczbą komórek w klasach, podziałkę, strzałkę północy i źródło.
Świadomie osobna implementacja niż atlas/mapa_svg.py — moduły są
niezależne (CLAUDE.md: bez wspólnych abstrakcji dla dwóch modułów),
a tu rysujemy heksagony H3 i punkty usług, nie gminy.

Odwzorowanie: walcowe równoodległościowe ze skalą cos φ₀ — w skali
miasta zniekształcenie jest pomijalne.
"""

import math
from html import escape

SZEROKOSC, WYSOKOSC = 1123, 794  # A4 poziomo, px przy 96 dpi
MARGINES = 40
POLE_MAPY = (MARGINES, 110, 760, WYSOKOSC - 70)
KOLUMNA_LEGENDY = 800
KM_NA_STOPIEN = 111.32
LADNE_DLUGOSCI_M = (100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000)
MAKS_KOMOREK_NA_MAPIE = 30_000

# Te same palety co dostepnosc.js — wydruk ma wyglądać jak ekran.
KOLORY_MINUT = ["#30d158", "#a3d94f", "#ffd60a", "#ff9f0a", "#ff6b3d", "#d70015"]
KOLORY_INNE = ["#d6e8ff", "#9ecbff", "#5aa7ff", "#1f7ae0", "#0b4fa8", "#062f66"]


def kolory_klas(analiza: dict) -> list[str]:
    """Jak kolory() w dostepnosc.js: przy mniejszej liczbie klas — z całej skali."""
    if analiza["minuty"]:
        return KOLORY_MINUT
    liczba = len(analiza["progi"]) + 1
    if liczba == 1:
        return [KOLORY_INNE[3]]
    return [KOLORY_INNE[round(i * (len(KOLORY_INNE) - 1) / (liczba - 1))] for i in range(liczba)]


def _format(liczba: float) -> str:
    tekst = f"{liczba:.1f}".rstrip("0").rstrip(".")
    return tekst.replace(".", ",")


def legenda(analiza: dict) -> list[tuple[str, str, int]]:
    """[(kolor, opis przedziału, liczba komórek)] w kolejności klas."""
    progi = analiza["progi"]
    kolory = kolory_klas(analiza)
    jednostka = " min" if analiza["minuty"] else ""
    ile = [0] * (len(progi) + 1)
    for cecha in analiza["geojson"]["features"]:
        ile[cecha["properties"]["klasa"]] += 1
    wiersze = []
    for i in range(len(progi) + 1):
        if not progi:
            opis = f"{_format(analiza['statystyki']['min'])}{jednostka}"
        elif i == 0:
            opis = f"≤ {_format(progi[0])}{jednostka}"
        elif i == len(progi):
            opis = f"> {_format(progi[-1])}{jednostka}"
        else:
            opis = f"{_format(progi[i - 1])} – {_format(progi[i])}{jednostka}"
        wiersze.append((kolory[i], opis, ile[i]))
    return wiersze


def dlugosc_podzialki_m(m_na_px: float, maks_px: float = 180) -> int:
    pasujace = [d for d in LADNE_DLUGOSCI_M if d / m_na_px <= maks_px]
    return pasujace[-1] if pasujace else LADNE_DLUGOSCI_M[0]


def mapa_svg(analiza: dict, tytul: str, podtytul: str, przypisy: list[str], punkty: list[dict] | None = None) -> str:
    cechy = analiza["geojson"]["features"]
    if not cechy:
        raise ValueError("Brak komórek z wartością do narysowania.")
    if len(cechy) > MAKS_KOMOREK_NA_MAPIE:
        raise ValueError(f"Za dużo komórek na mapę do druku (limit {MAKS_KOMOREK_NA_MAPIE}).")

    pierscienie = [c["geometry"]["coordinates"][0] for c in cechy]
    lons = [x for p in pierscienie for x, _ in p]
    lats = [y for p in pierscienie for _, y in p]
    min_lon, max_lon, min_lat, max_lat = min(lons), max(lons), min(lats), max(lats)
    wsp = math.cos(math.radians((min_lat + max_lat) / 2))
    x0, y0, x1, y1 = POLE_MAPY
    szer = (max_lon - min_lon) * wsp
    wys = max_lat - min_lat
    skala = min((x1 - x0) / szer, (y1 - y0) / wys)  # px na stopień szerokości
    dx = x0 + ((x1 - x0) - szer * skala) / 2
    dy = y0 + ((y1 - y0) - wys * skala) / 2

    def punkt(lon: float, lat: float) -> tuple[float, float]:
        return dx + (lon - min_lon) * wsp * skala, dy + (max_lat - lat) * skala

    kolory = kolory_klas(analiza)
    czesci = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SZEROKOSC}" height="{WYSOKOSC}" '
        f'viewBox="0 0 {SZEROKOSC} {WYSOKOSC}" font-family="Helvetica, Arial, sans-serif">',
        f'<rect width="{SZEROKOSC}" height="{WYSOKOSC}" fill="#ffffff"/>',
        f'<text x="{MARGINES}" y="52" font-size="24" font-weight="700" fill="#1d1d1f">{escape(tytul)}</text>',
        f'<text x="{MARGINES}" y="80" font-size="15" fill="#6e6e73">{escape(podtytul)}</text>',
        '<g stroke-width="0.4" stroke-linejoin="round">',
    ]
    for cecha, pierscien in zip(cechy, pierscienie):
        kolor = kolory[cecha["properties"]["klasa"]]
        wsp_px = " ".join(f"{x:.1f},{y:.1f}" for x, y in (punkt(lon, lat) for lon, lat in pierscien[:-1]))
        czesci.append(f'<polygon points="{wsp_px}" fill="{kolor}" stroke="{kolor}"/>')
    czesci.append("</g>")

    for p in punkty or []:
        x, y = punkt(p["lon"], p["lat"])
        czesci.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="10" fill="#5e5ce6" stroke="#ffffff" stroke-width="2"/>')
        czesci.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="11" font-weight="700" fill="#ffffff" text-anchor="middle">{p["nr"]}</text>'
        )

    # legenda
    lx, ly = KOLUMNA_LEGENDY, 140
    tytul_legendy = "Czas dojścia" if analiza["minuty"] else analiza["kolumna"]
    czesci.append(f'<text x="{lx}" y="{ly}" font-size="14" font-weight="700" fill="#1d1d1f">{escape(tytul_legendy)}</text>')
    czesci.append(f'<text x="{SZEROKOSC - MARGINES}" y="{ly}" font-size="11" fill="#6e6e73" text-anchor="end">komórki</text>')
    for i, (kolor, opis, ile) in enumerate(legenda(analiza)):
        wy = ly + 22 + i * 28
        czesci.append(f'<rect x="{lx}" y="{wy}" width="28" height="18" rx="3" fill="{kolor}"/>')
        czesci.append(f'<text x="{lx + 38}" y="{wy + 14}" font-size="13" fill="#1d1d1f">{escape(opis)}</text>')
        czesci.append(f'<text x="{SZEROKOSC - MARGINES}" y="{wy + 14}" font-size="12" fill="#6e6e73" text-anchor="end">{ile}</text>')
    if punkty:
        wy = ly + 22 + (len(legenda(analiza)) + 0.5) * 28
        czesci.append(f'<circle cx="{lx + 14}" cy="{wy + 9}" r="9" fill="#5e5ce6"/>')
        czesci.append(f'<text x="{lx + 38}" y="{wy + 14}" font-size="13" fill="#1d1d1f">punkt usługi (numer)</text>')

    # podziałka i północ
    m_na_px = KM_NA_STOPIEN * 1000 / skala
    metry = dlugosc_podzialki_m(m_na_px)
    dlugosc_px = metry / m_na_px
    px, py = KOLUMNA_LEGENDY, WYSOKOSC - 120
    podpis = f"{metry / 1000:g} km".replace(".", ",") if metry >= 1000 else f"{metry} m"
    czesci += [
        f'<rect x="{px}" y="{py}" width="{dlugosc_px / 2:.1f}" height="6" fill="#1d1d1f"/>',
        f'<rect x="{px + dlugosc_px / 2:.1f}" y="{py}" width="{dlugosc_px / 2:.1f}" height="6" fill="#ffffff" stroke="#1d1d1f"/>',
        f'<text x="{px}" y="{py + 22}" font-size="11" fill="#1d1d1f">0</text>',
        f'<text x="{px + dlugosc_px:.1f}" y="{py + 22}" font-size="11" fill="#1d1d1f" text-anchor="middle">{podpis}</text>',
    ]
    nx, ny = SZEROKOSC - MARGINES - 16, WYSOKOSC - 150
    czesci += [
        f'<polygon points="{nx},{ny - 30} {nx - 10},{ny} {nx},{ny - 7} {nx + 10},{ny}" fill="#1d1d1f"/>',
        f'<text x="{nx}" y="{ny + 18}" font-size="14" font-weight="700" fill="#1d1d1f" text-anchor="middle">N</text>',
    ]
    for i, przypis in enumerate(przypisy):
        czesci.append(f'<text x="{MARGINES}" y="{WYSOKOSC - 44 + i * 16}" font-size="11" fill="#6e6e73">{escape(przypis)}</text>')
    czesci.append("</svg>")
    return "\n".join(czesci)
