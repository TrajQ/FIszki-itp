"""Kalkulator skali mapy — przeliczenia rysunek ↔ teren.

Skala 1:M oznacza, że 1 jednostka na rysunku to M takich samych jednostek
w terenie. Powierzchnia skaluje się kwadratem: 1 cm² na rysunku to M² cm²
w terenie. Formaty arkuszy wg ISO 216 (w mm, orientacja dowolna).
"""

SKALE_STANDARDOWE = [500, 1000, 2000, 5000, 10000, 25000, 50000, 100000]

ARKUSZE_MM = {
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189),
}

JEDNOSTKI_DLUGOSCI_M = {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0}
JEDNOSTKI_POWIERZCHNI_M2 = {"cm2": 0.0001, "m2": 1.0, "ha": 10_000.0, "km2": 1_000_000.0}


class BladSkali(ValueError):
    pass


def _sprawdz_mianownik(mianownik: float) -> None:
    if mianownik <= 0:
        raise BladSkali("Mianownik skali musi być dodatni (np. 1000 dla 1:1000).")


def dlugosc_w_terenie(na_rysunku: float, jednostka: str, mianownik: float) -> float:
    """Długość w terenie w metrach."""
    _sprawdz_mianownik(mianownik)
    return na_rysunku * JEDNOSTKI_DLUGOSCI_M[jednostka] * mianownik


def dlugosc_na_rysunku(w_terenie: float, jednostka: str, mianownik: float) -> float:
    """Długość na rysunku w milimetrach."""
    _sprawdz_mianownik(mianownik)
    return w_terenie * JEDNOSTKI_DLUGOSCI_M[jednostka] / mianownik * 1000


def powierzchnia_w_terenie(na_rysunku_cm2: float, mianownik: float) -> float:
    """Powierzchnia w terenie w m² z powierzchni na rysunku w cm²."""
    _sprawdz_mianownik(mianownik)
    return na_rysunku_cm2 * 0.0001 * mianownik**2


def powierzchnia_na_rysunku(w_terenie: float, jednostka: str, mianownik: float) -> float:
    """Powierzchnia na rysunku w cm²."""
    _sprawdz_mianownik(mianownik)
    return w_terenie * JEDNOSTKI_POWIERZCHNI_M2[jednostka] / mianownik**2 / 0.0001


def dobierz_skale(szerokosc_m: float, wysokosc_m: float, arkusz: str, margines_mm: float = 20) -> dict:
    """Najdokładniejsza (najmniejszy mianownik) skala standardowa, w której
    teren szerokosc × wysokosc zmieści się na arkuszu z marginesem —
    w orientacji pionowej albo poziomej."""
    if szerokosc_m <= 0 or wysokosc_m <= 0:
        raise BladSkali("Wymiary terenu muszą być dodatnie.")
    if margines_mm < 0:
        raise BladSkali("Margines nie może być ujemny.")
    if arkusz not in ARKUSZE_MM:
        raise BladSkali(f"Nieznany arkusz: {arkusz}.")
    krotszy, dluzszy = ARKUSZE_MM[arkusz]
    uzyteczne = (krotszy - 2 * margines_mm, dluzszy - 2 * margines_mm)
    if min(uzyteczne) <= 0:
        raise BladSkali("Margines jest większy niż arkusz.")

    for mianownik in SKALE_STANDARDOWE:
        w_mm = szerokosc_m * 1000 / mianownik
        h_mm = wysokosc_m * 1000 / mianownik
        for orientacja, (pole_w, pole_h) in (("pionowa", uzyteczne), ("pozioma", uzyteczne[::-1])):
            if w_mm <= pole_w and h_mm <= pole_h:
                return {
                    "mianownik": mianownik,
                    "orientacja": orientacja,
                    "rysunek_mm": (w_mm, h_mm),
                    "wypelnienie_proc": 100 * (w_mm * h_mm) / (pole_w * pole_h),
                }
    return {"mianownik": None, "orientacja": None, "rysunek_mm": None, "wypelnienie_proc": None}
