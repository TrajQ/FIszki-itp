"""Współrzędne punktu w polskich układach PL-1992 i PL-2000.

Mapa (Leaflet, ULDK) podaje szerokość i długość geograficzną (WGS84),
a w pracy z mapami zasadniczymi, QGIS-em czy operatami geodezyjnymi
potrzebne są współrzędne płaskie:

- PL-1992 (EPSG:2180) — jedna strefa na cały kraj, południk 19°E,
  skala 0,9993; układ map urzędowych małych i średnich skal,
- PL-2000 (EPSG:2176–2179) — cztery strefy co 3° (15, 18, 21, 24°E),
  skala 0,999923; układ mapy zasadniczej i ewidencji gruntów.

Oba to odwzorowanie Gaussa-Krügera elipsoidy GRS80. Liczymy je wzorami
Krügera w postaci szeregów (Karney 2011, do 6. rzędu) — dokładność
rzędu milimetrów, bez dodatkowej biblioteki (pyproj byłby za ciężki dla
jednej funkcji). Różnicę WGS84 ↔ ETRF2000 (kilkadziesiąt cm) pomijamy —
przy sprawdzaniu działki w aplikacji nie ma znaczenia.

Uwaga na osie: w polskiej geodezji X to współrzędna północna, a Y —
wschodnia (odwrotnie niż w matematyce i w QGIS, gdzie x = wschód).
"""

import math

# Elipsoida GRS80
A = 6378137.0
F = 1 / 298.257222101

_N = F / (2 - F)
_A_PROSTOKATNE = A / (1 + _N) * (1 + _N**2 / 4 + _N**4 / 64 + _N**6 / 256)
_ALFA = (
    _N / 2 - 2 * _N**2 / 3 + 5 * _N**3 / 16 + 41 * _N**4 / 180 - 127 * _N**5 / 288 + 7891 * _N**6 / 37800,
    13 * _N**2 / 48 - 3 * _N**3 / 5 + 557 * _N**4 / 1440 + 281 * _N**5 / 630 - 1983433 * _N**6 / 1935360,
    61 * _N**3 / 240 - 103 * _N**4 / 140 + 15061 * _N**5 / 26880 + 167603 * _N**6 / 181440,
    49561 * _N**4 / 161280 - 179 * _N**5 / 168 + 6601661 * _N**6 / 7257600,
    34729 * _N**5 / 80640 - 3418889 * _N**6 / 1995840,
    212378941 * _N**6 / 319334400,
)
_E = math.sqrt(F * (2 - F))


def gauss_kruger(lat: float, lon: float, poludnik: float, skala: float) -> tuple[float, float]:
    """(północ, wschód) w metrach od równika i południka osiowego, przed
    przesunięciem (false easting/northing) układu."""
    fi = math.radians(lat)
    dl = math.radians(lon - poludnik)
    # szerokość konforemna
    t = math.sinh(math.atanh(math.sin(fi)) - _E * math.atanh(_E * math.sin(fi)))
    ksi_p = math.atan2(t, math.cos(dl))
    eta_p = math.atanh(math.sin(dl) / math.sqrt(1 + t * t))
    ksi, eta = ksi_p, eta_p
    for j, alfa in enumerate(_ALFA, start=1):
        ksi += alfa * math.sin(2 * j * ksi_p) * math.cosh(2 * j * eta_p)
        eta += alfa * math.cos(2 * j * ksi_p) * math.sinh(2 * j * eta_p)
    return skala * _A_PROSTOKATNE * ksi, skala * _A_PROSTOKATNE * eta


def pl1992(lat: float, lon: float) -> dict:
    polnoc, wschod = gauss_kruger(lat, lon, 19.0, 0.9993)
    return {"uklad": "PL-1992", "epsg": 2180, "x": polnoc - 5_300_000, "y": wschod + 500_000}


def strefa_pl2000(lon: float) -> int:
    """Numer strefy PL-2000 (5–8) = południk osiowy / 3."""
    return min(8, max(5, round(lon / 3)))


def pl2000(lat: float, lon: float) -> dict:
    strefa = strefa_pl2000(lon)
    polnoc, wschod = gauss_kruger(lat, lon, 3.0 * strefa, 0.999923)
    return {
        "uklad": f"PL-2000 strefa {strefa}",
        "epsg": 2171 + strefa,  # 5 → 2176 … 8 → 2179
        "x": polnoc,
        "y": strefa * 1_000_000 + 500_000 + wschod,
    }


def w_polsce(lat: float, lon: float) -> bool:
    """Z grubsza obszar Polski z zapasem — poza nim układy PL nie mają sensu."""
    return 48.5 <= lat <= 55.5 and 13.5 <= lon <= 24.5


# ---------- przeliczenie odwrotne: PL-1992 → WGS84 (ETAP 104) ----------

_BETA = (
    _N / 2 - 2 * _N**2 / 3 + 37 * _N**3 / 96 - _N**4 / 360 - 81 * _N**5 / 512 + 96199 * _N**6 / 604800,
    _N**2 / 48 + _N**3 / 15 - 437 * _N**4 / 1440 + 46 * _N**5 / 105 - 1118711 * _N**6 / 3870720,
    17 * _N**3 / 480 - 37 * _N**4 / 840 - 209 * _N**5 / 4480 + 5569 * _N**6 / 90720,
    4397 * _N**4 / 161280 - 11 * _N**5 / 504 - 830251 * _N**6 / 7257600,
    4583 * _N**5 / 161280 - 108847 * _N**6 / 3991680,
    20648693 * _N**6 / 638668800,
)


def odwrotne_gauss_kruger(polnoc: float, wschod: float, poludnik: float, skala: float) -> tuple[float, float]:
    """(szerokość, długość) w stopniach — odwrotność gauss_kruger (szeregi
    Krügera, Karney 2011; szerokość z konforemnej metodą Newtona)."""
    ksi = polnoc / (skala * _A_PROSTOKATNE)
    eta = wschod / (skala * _A_PROSTOKATNE)
    ksi_p, eta_p = ksi, eta
    for j, beta in enumerate(_BETA, start=1):
        ksi_p -= beta * math.sin(2 * j * ksi) * math.cosh(2 * j * eta)
        eta_p -= beta * math.cos(2 * j * ksi) * math.sinh(2 * j * eta)
    tau_p = math.sin(ksi_p) / math.hypot(math.sinh(eta_p), math.cos(ksi_p))  # tangens szerokości konforemnej
    dl = math.atan2(math.sinh(eta_p), math.cos(ksi_p))
    tau = tau_p
    for _ in range(5):
        sigma = math.sinh(_E * math.atanh(_E * tau / math.sqrt(1 + tau * tau)))
        tau_i = tau * math.sqrt(1 + sigma * sigma) - sigma * math.sqrt(1 + tau * tau)
        tau += (tau_p - tau_i) / math.sqrt(1 + tau_i * tau_i) * (1 + (1 - _E**2) * tau * tau) / ((1 - _E**2) * math.sqrt(1 + tau * tau))
    return math.degrees(math.atan(tau)), poludnik + math.degrees(dl)


def wgs84_z_pl1992(x: float, y: float) -> tuple[float, float]:
    """PL-1992 (x — północ, y — wschód, jak w geodezji) → (szerokość, długość)."""
    return odwrotne_gauss_kruger(x + 5_300_000, y - 500_000, 19.0, 0.9993)


def wgs84_z_pl2000(x: float, y: float) -> tuple[float, float]:
    """PL-2000 (x — północ, y — wschód z numerem strefy na początku, np.
    7 4xx xxx) → (szerokość, długość). ETAP 138."""
    strefa = int(y // 1_000_000)
    if strefa not in (5, 6, 7, 8):
        raise ValueError("Współrzędna wschodnia nie zaczyna się od numeru strefy PL-2000 (5–8).")
    return odwrotne_gauss_kruger(x, y - strefa * 1_000_000 - 500_000, 3.0 * strefa, 0.999923)
