"""Fiszki „gdzie to jest” — odpowiedź to miejsce na mapie (ETAP 248).

Fiszka z miejscem jest zwykłą fiszką (pytanie, odpowiedź tekstem —
działa w powtórce, na telefonie i w druku), a do tego ma punkt i
promień w tabeli miejsca_fiszek. Quiz z mapą: klikasz, gdzie to jest;
serwer liczy odległość od punktu i ocenia trafienie (w promieniu) —
odległości i oceny liczy kod, nie model językowy.
"""

import math

PROMIENIE_M = (50, 100, 300, 1000, 5000)
PROMIEN_DOMYSLNY_M = 300
R_ZIEMI_M = 6_371_008.8
MAKS_W_QUIZIE = 20


class BladMiejsca(ValueError):
    """Złe położenie albo promień."""


def sprawdz(lat, lng, promien_m) -> tuple[float, float, int]:
    try:
        lat, lng, promien_m = float(lat), float(lng), int(promien_m)
    except (TypeError, ValueError):
        raise BladMiejsca("Wskaż miejsce na mapie.") from None
    if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
        raise BladMiejsca("Współrzędne miejsca poza zakresem.")
    if promien_m not in PROMIENIE_M:
        raise BladMiejsca("Niepoprawny promień trafienia.")
    return lat, lng, promien_m


def odleglosc_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Odległość po kuli (haversine)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lng2 - lng1)
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * R_ZIEMI_M * math.asin(math.sqrt(h))


def ocen(miejsce: dict, lat: float, lng: float) -> dict:
    """Odległość kliknięcia od miejsca i ocena: trafione (w promieniu),
    blisko (do trzech promieni) albo pudło."""
    odl = odleglosc_m(miejsce["lat"], miejsce["lng"], lat, lng)
    ocena = "trafione" if odl <= miejsce["promien_m"] else "blisko" if odl <= 3 * miejsce["promien_m"] else "pudło"
    return {"odleglosc_m": round(odl), "ocena": ocena, "lat": miejsce["lat"], "lng": miejsce["lng"], "promien_m": miejsce["promien_m"]}


def zapisz(db, fiszka_id: int, lat: float, lng: float, promien_m: int):
    db.execute("INSERT OR REPLACE INTO miejsca_fiszek (fiszka_id, lat, lng, promien_m) VALUES (?, ?, ?, ?)",
               (fiszka_id, lat, lng, promien_m))


def lista(db, pdf_id: int | None = None) -> list[dict]:
    """Fiszki z miejscem (najnowsze pierwsze), opcjonalnie z jednego pliku."""
    warunek = "WHERE f.pdf_id = ?" if pdf_id else ""
    wiersze = db.execute(
        f"""SELECT f.id, f.pdf_id, f.pytanie, f.odpowiedz, m.lat, m.lng, m.promien_m, p.nazwa_oryginalna AS plik
            FROM miejsca_fiszek m JOIN fiszki f ON f.id = m.fiszka_id JOIN pdfy p ON p.id = f.pdf_id
            {warunek} ORDER BY f.id DESC""",
        (pdf_id,) if pdf_id else (),
    ).fetchall()
    return [dict(w) for w in wiersze]


def miejsce(db, fiszka_id: int) -> dict | None:
    w = db.execute("SELECT lat, lng, promien_m FROM miejsca_fiszek WHERE fiszka_id = ?", (fiszka_id,)).fetchone()
    return dict(w) if w else None
