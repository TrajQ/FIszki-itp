"""Szkic koncepcji jako SVG — do raportu i porównania wariantów (ETAP 60).

Wieloboki w metrach (lokalna skala jak w bilans.py), północ u góry,
podziałka liniowa. Kilka koncepcji rysujemy w jednej skali, żeby dało
się porównać ich wielkość na oko. W SVG są tylko liczby i kolory z kodu —
żadnego tekstu wpisanego przez użytkownika.
"""

from shapely.geometry import shape

from .bilans import BUDYNEK, FUNKCJE, KOLOR_BUDYNKU, OBSZAR, _w_metrach

MARGINES_PX = 24
KROKI_PODZIALKI_M = [5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000]


def _cechy(geojson: dict) -> list[tuple[str, object]]:
    cechy = []
    for cecha in geojson.get("features") or []:
        try:
            cechy.append(((cecha.get("properties") or {}).get("funkcja"), shape(cecha["geometry"])))
        except Exception:
            continue  # zapisany rysunek przeszedł walidację; to tylko ostrożność
    return cechy


def _szerokosc(cechy) -> float:
    """Szerokość geograficzna skali metrycznej rysunku (średnia środków)."""
    return sum(g.centroid.y for _, g in cechy) / len(cechy)


def _geometrie_w_metrach(geojson: dict) -> list[tuple[str, object]]:
    """[(funkcja, geometria w metrach)] — obszar opracowania na początku (pod spodem),
    budynki na końcu (nad terenami, ETAP 173)."""
    cechy = _cechy(geojson)
    if not cechy:
        return []
    szerokosc = _szerokosc(cechy)
    wynik = [(f, _w_metrach(g, szerokosc)) for f, g in cechy]
    return sorted(wynik, key=lambda p: 0 if p[0] == OBSZAR else 2 if p[0] == BUDYNEK else 1)


def zasieg_m(geojson: dict) -> tuple[float, float]:
    """(szerokość, wysokość) rysunku w metrach; (0, 0) dla pustego."""
    geometrie = _geometrie_w_metrach(geojson)
    if not geometrie:
        return 0.0, 0.0
    minx = min(g.bounds[0] for _, g in geometrie)
    miny = min(g.bounds[1] for _, g in geometrie)
    maxx = max(g.bounds[2] for _, g in geometrie)
    maxy = max(g.bounds[3] for _, g in geometrie)
    return maxx - minx, maxy - miny


def skala_dla(geojsony: list[dict], szerokosc_px: int, wysokosc_px: int) -> float | None:
    """Metry na piksel, przy których zmieści się największy z rysunków."""
    najwiekszy = [zasieg_m(g) for g in geojsony]
    szer = max((s for s, _ in najwiekszy), default=0)
    wys = max((w for _, w in najwiekszy), default=0)
    if not szer and not wys:
        return None
    return max(szer / (szerokosc_px - 2 * MARGINES_PX), wys / (wysokosc_px - 2 * MARGINES_PX - 30))


def _pierscien(wspolrzedne, przelicz) -> str:
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in (przelicz(p) for p in wspolrzedne)) + " Z"


def _sciezka(geometria, przelicz) -> str:
    if geometria.geom_type in ("MultiPolygon", "GeometryCollection"):
        # z kolekcji rysujemy tylko wieloboki (np. różnica figur bywa kolekcją z odcinkami)
        wieloboki = [w for g in geometria.geoms for w in (getattr(g, "geoms", None) or [g]) if w.geom_type == "Polygon"]
    else:
        wieloboki = [geometria]
    czesci = []
    for w in wieloboki:
        czesci.append(_pierscien(w.exterior.coords, przelicz))
        czesci.extend(_pierscien(d.coords, przelicz) for d in w.interiors)
    return " ".join(czesci)


def szkic_svg(
    geojson: dict,
    szerokosc_px: int = 640,
    wysokosc_px: int = 480,
    metry_na_px: float | None = None,
    strefa_cienia: dict | None = None,
    numery: bool = False,
) -> str:
    """Szkic jednej koncepcji; metry_na_px — wspólna skala przy porównaniu.
    ETAP 100: strefa_cienia (GeoJSON w stopniach, z osiedle/cien.py) i
    numery terenów (jak w tabeli cienia: kolejne tereny bez obszaru)."""
    geometrie = _geometrie_w_metrach(geojson)
    otwarcie = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc_px} {wysokosc_px}" '
        f'width="{szerokosc_px}" height="{wysokosc_px}" font-family="sans-serif" font-size="12">'
        f'<rect width="100%" height="100%" fill="#ffffff"/>'
    )
    if not geometrie:
        return otwarcie + f'<text x="{szerokosc_px / 2}" y="{wysokosc_px / 2}" text-anchor="middle" fill="#6e6e73">pusty rysunek</text></svg>'

    skala = metry_na_px or skala_dla([geojson], szerokosc_px, wysokosc_px)
    minx = min(g.bounds[0] for _, g in geometrie)
    miny = min(g.bounds[1] for _, g in geometrie)
    maxx = max(g.bounds[2] for _, g in geometrie)
    maxy = max(g.bounds[3] for _, g in geometrie)
    # środek rysunku na środku pola (nad podziałką), oś y w dół
    srodek_x, srodek_y = (minx + maxx) / 2, (miny + maxy) / 2
    pole_srodek_y = (wysokosc_px - 30) / 2

    def przelicz(p):
        return szerokosc_px / 2 + (p[0] - srodek_x) / skala, pole_srodek_y - (p[1] - srodek_y) / skala

    czesci = [otwarcie]
    cechy = _cechy(geojson)
    szerokosc = _szerokosc(cechy)
    for funkcja, g in geometrie:
        d = _sciezka(g, przelicz)
        if funkcja == OBSZAR:
            czesci.append(f'<path d="{d}" fill="none" stroke="#1d1d1f" stroke-width="2" stroke-dasharray="8 5"/>')
        elif funkcja == BUDYNEK:
            czesci.append(f'<path d="{d}" fill="{KOLOR_BUDYNKU}" fill-opacity="0.85" stroke="#ffffff" stroke-width="1" fill-rule="evenodd"/>')
        else:
            kolor = FUNKCJE.get(funkcja, {}).get("kolor", "#8e8e93")
            czesci.append(f'<path d="{d}" fill="{kolor}" fill-opacity="0.75" stroke="{kolor}" stroke-width="1" fill-rule="evenodd"/>')

    if strefa_cienia is not None:
        d = _sciezka(_w_metrach(shape(strefa_cienia), szerokosc), przelicz)
        czesci.append(f'<path d="{d}" fill="#1d1d1f" fill-opacity="0.22" stroke="#48484a" stroke-width="1" stroke-dasharray="4 3" fill-rule="nonzero"/>')
    if numery:
        tereny = [g for f, g in cechy if f not in (OBSZAR, BUDYNEK)]  # kolejność z zapisu — jak w tabeli cienia
        for nr, g in enumerate(tereny, start=1):
            x, y = przelicz(_w_metrach(g, szerokosc).representative_point().coords[0])
            czesci.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="#ffffff" stroke="#1d1d1f" stroke-width="1"/>'
                f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" font-size="11" fill="#1d1d1f">{nr}</text>'
            )

    # podziałka: najdłuższy „okrągły” odcinek do ok. 1/4 szerokości
    dlugosc_m = max((k for k in KROKI_PODZIALKI_M if k / skala <= szerokosc_px / 4), default=KROKI_PODZIALKI_M[0])
    dlugosc_px = dlugosc_m / skala
    y = wysokosc_px - 16
    czesci.append(
        f'<g stroke="#1d1d1f" stroke-width="2"><line x1="{MARGINES_PX}" y1="{y}" x2="{MARGINES_PX + dlugosc_px:.1f}" y2="{y}"/>'
        f'<line x1="{MARGINES_PX}" y1="{y - 5}" x2="{MARGINES_PX}" y2="{y + 1}"/>'
        f'<line x1="{MARGINES_PX + dlugosc_px:.1f}" y1="{y - 5}" x2="{MARGINES_PX + dlugosc_px:.1f}" y2="{y + 1}"/></g>'
        f'<text x="{MARGINES_PX + dlugosc_px + 6:.1f}" y="{y + 4}" fill="#1d1d1f">{dlugosc_m} m</text>'
    )
    # strzałka północy
    x = szerokosc_px - MARGINES_PX
    czesci.append(
        f'<path d="M{x},{MARGINES_PX - 10} L{x + 6},{MARGINES_PX + 6} L{x},{MARGINES_PX + 2} L{x - 6},{MARGINES_PX + 6} Z" fill="#1d1d1f"/>'
        f'<text x="{x}" y="{MARGINES_PX + 20}" text-anchor="middle" fill="#1d1d1f">N</text>'
    )
    czesci.append("</svg>")
    return "".join(czesci)
