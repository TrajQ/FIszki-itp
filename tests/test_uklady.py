"""mpzp/uklady.py — wartości referencyjne policzone biblioteką pyproj."""

import pytest

from mpzp import uklady

# (szerokość, długość) → (EPSG:2180 wschód, północ), (EPSG PL-2000, wschód, północ)
PUNKTY = [
    ((52.2319, 21.0067), (636999.958, 486991.385), (2178, 7500457.726, 5788701.217)),  # Warszawa
    ((52.4064, 16.9252), (358907.512, 506522.741), (2177, 6426861.897, 5808660.489)),  # Poznań
    ((54.35, 18.65), (477257.412, 720712.953), (2177, 6542262.361, 6024604.807)),  # Gdańsk
    ((49.3, 22.5), (754357.875, 165060.622), (2179, 8390913.267, 5463653.461)),  # Bieszczady, granica stref
    ((50.06, 19.94), (567262.453, 244060.615), (2178, 7424103.725, 5547631.97)),  # Kraków
]


@pytest.mark.parametrize("punkt, pl92, pl2000", PUNKTY)
def test_zgodnosc_z_pyproj_do_centymetra(punkt, pl92, pl2000):
    a = uklady.pl1992(*punkt)
    assert (a["y"], a["x"]) == pytest.approx(pl92, abs=0.01)
    b = uklady.pl2000(*punkt)
    assert b["epsg"] == pl2000[0]
    assert (b["y"], b["x"]) == pytest.approx(pl2000[1:], abs=0.01)


def test_strefy_pl2000():
    assert [uklady.strefa_pl2000(lon) for lon in (14.2, 16.4, 16.6, 19.4, 19.6, 22.4, 23.9)] == [5, 5, 6, 6, 7, 7, 8]


def test_poza_polska():
    assert uklady.w_polsce(52, 19) and not uklady.w_polsce(40, 19) and not uklady.w_polsce(52, 30)


# ---------- ETAP 104: przeliczenie odwrotne PL-1992 → WGS84 ----------


@pytest.mark.parametrize("lat, lon", [(52.4064, 16.9252), (50.0614, 19.9366), (54.35, 18.65), (49.3, 22.7), (53.9, 14.25)])
def test_pl1992_tam_i_z_powrotem(lat, lon):
    p = uklady.pl1992(lat, lon)
    lat2, lon2 = uklady.wgs84_z_pl1992(p["x"], p["y"])
    assert lat2 == pytest.approx(lat, abs=1e-8) and lon2 == pytest.approx(lon, abs=1e-8)  # ok. 1 mm
