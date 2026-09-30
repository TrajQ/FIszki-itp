"""Transakcje lokali z Rejestru Cen Nieruchomości (ETAP 104).

Plik: GeoPackage powiatu pobrany z geoportal.gov.pl (moduł „Rejestr Cen
Nieruchomości” → dane do pobrania). GeoPackage to baza SQLite, więc
czytamy go biblioteką standardową — bez GDAL i nowej zależności.

Nazwy tabeli i kolumn ustalone z kodu kilku otwartych projektów, które
czytają te pliki (tabela `transakcje_lokale`, kolumny `lok_cena_brutto`,
`nier_cena_brutto`, `tran_cena_brutto`, `lok_pow_uzyt`, `dok_data`,
`tran_rodzaj_rynku`, `tran_rodzaj_trans`, `lok_funkcja`, …). Kod nie
zakłada, że wszystkie są obecne: sprawdza, co jest w pliku, i jasno mówi,
czego brakuje.

Cena lokalu (jak w tych projektach): cena lokalu, a bez niej cena
nieruchomości, a bez niej cena transakcji — tę ostatnią tylko wtedy, gdy
w transakcji był jeden lokal (inaczej cena dotyczy kilku lokali naraz).
Odrzucamy lokale niemieszkalne, udziały inne niż całość i wartości
nierealne (powierzchnia poza 10–500 m², cena za m² poza 500–100 000 zł) —
z liczbą odrzuconych z każdego powodu.

Geometria: nagłówek GeoPackage + WKB, układ PL-1992 (EPSG:2180; x w pliku
= współrzędna wschodnia, jak w GIS). Do mapy bierzemy środek obiektu i
przeliczamy go na WGS84 (mpzp/uklady.py).
"""

import sqlite3
import statistics
import struct
from datetime import date

from shapely import wkb

from mpzp.uklady import w_polsce, wgs84_z_pl1992

TABELA = "transakcje_lokale"
KOLUMNY_CENY = ("lok_cena_brutto", "nier_cena_brutto", "tran_cena_brutto")
POW_M2 = (10, 500)
CENA_M2 = (500, 100_000)
MAKS_PUNKTOW_MAPY = 4000


class BladPliku(ValueError):
    """Plik nie jest GeoPackage RCN albo brakuje w nim potrzebnych danych."""


def _srodek_geometrii(blob: bytes | None) -> tuple[float, float] | None:
    """(x, y) środka geometrii z blobu GeoPackage (nagłówek „GP” + WKB)."""
    if not blob or blob[:2] != b"GP":
        return None
    flagi = blob[3]
    koperta = (flagi >> 1) & 0b111
    dlugosc_koperty = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get(koperta)
    if dlugosc_koperty is None or flagi & 0b10000:  # zła koperta albo pusta geometria
        return None
    if dlugosc_koperty:
        kolejnosc = "<" if flagi & 1 else ">"
        minx, maxx, miny, maxy = struct.unpack(kolejnosc + "4d", blob[8:40])
        return (minx + maxx) / 2, (miny + maxy) / 2
    try:
        punkt = wkb.loads(bytes(blob[8:])).representative_point()
    except Exception:
        return None
    return punkt.x, punkt.y


def _liczba(w) -> float | None:
    if w is None or w == "":
        return None
    try:
        return float(str(w).replace(",", "."))
    except ValueError:
        return None


def _rynek(tekst) -> str:
    t = str(tekst or "").lower()
    if "pierwot" in t or "primary" in t:
        return "pierwotny"
    if "wtórn" in t or "wtorn" in t or "secondary" in t:
        return "wtórny"
    return "nieznany"


def _data(tekst) -> date | None:
    try:
        return date.fromisoformat(str(tekst)[:10])
    except ValueError:
        return None


def czytaj_plik(sciezka: str) -> dict:
    """GeoPackage RCN → {"lokale": [...], "odrzucone": {powód: liczba}, "kolumny": [...]}."""
    try:
        db = sqlite3.connect(f"file:{sciezka}?mode=ro", uri=True)
        tabele = {w[0] for w in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as e:
        raise BladPliku("To nie jest plik GeoPackage (baza SQLite).") from e
    try:
        if TABELA not in tabele:
            raise BladPliku(f"W pliku nie ma tabeli „{TABELA}” — to nie jest plik RCN z lokalami. Tabele w pliku: {', '.join(sorted(t for t in tabele if not t.startswith(('gpkg_', 'rtree_', 'sqlite_'))))[:300]}.")
        kolumny = [w[1] for w in db.execute(f"PRAGMA table_info({TABELA})")]
        ceny = [k for k in KOLUMNY_CENY if k in kolumny]
        brakuje = [k for k in ("lok_pow_uzyt", "dok_data") if k not in kolumny] + ([] if ceny else ["kolumna ceny"])
        if brakuje:
            raise BladPliku(f"W tabeli {TABELA} brakuje: {', '.join(brakuje)}. Kolumny w pliku: {', '.join(kolumny)[:400]}.")
        geometria = next(
            (w[0] for w in db.execute("SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?", (TABELA,))), None
        ) if "gpkg_geometry_columns" in tabele else None
        srs = next((w[0] for w in db.execute("SELECT srs_id FROM gpkg_geometry_columns WHERE table_name = ?", (TABELA,))), None) if geometria else None
        db.row_factory = sqlite3.Row
        wiersze = [dict(w) for w in db.execute(f"SELECT * FROM {TABELA}")]
    finally:
        db.close()
    return _lokale(wiersze, geometria, srs, kolumny)


def _lokale(wiersze: list[dict], geometria: str | None, srs: int | None, kolumny: list[str]) -> dict:
    lokali_w_transakcji: dict = {}
    for w in wiersze:
        lokali_w_transakcji[w.get("tran_lokalny_id_iip")] = lokali_w_transakcji.get(w.get("tran_lokalny_id_iip"), 0) + 1
    odrzucone = {"niemieszkalne": 0, "udział w lokalu": 0, "bez ceny lokalu": 0, "brak daty": 0, "nierealna powierzchnia": 0, "nierealna cena za m²": 0}
    lokale, widziane = [], set()
    for w in wiersze:
        if "lok_funkcja" in w and w["lok_funkcja"] and "mieszk" not in str(w["lok_funkcja"]).lower():
            odrzucone["niemieszkalne"] += 1
            continue
        if w.get("nier_udzial") not in (None, "", "1/1", "1"):
            odrzucone["udział w lokalu"] += 1
            continue
        cena = _liczba(w.get("lok_cena_brutto")) or _liczba(w.get("nier_cena_brutto"))
        if cena is None and lokali_w_transakcji.get(w.get("tran_lokalny_id_iip")) == 1:
            cena = _liczba(w.get("tran_cena_brutto"))
        if not cena:
            odrzucone["bez ceny lokalu"] += 1
            continue
        dzien = _data(w.get("dok_data"))
        if dzien is None:
            odrzucone["brak daty"] += 1
            continue
        pow_m2 = _liczba(w.get("lok_pow_uzyt"))
        if pow_m2 is None or not POW_M2[0] <= pow_m2 <= POW_M2[1]:
            odrzucone["nierealna powierzchnia"] += 1
            continue
        cena_m2 = cena / pow_m2
        if not CENA_M2[0] <= cena_m2 <= CENA_M2[1]:
            odrzucone["nierealna cena za m²"] += 1
            continue
        klucz = (w.get("tran_lokalny_id_iip"), w.get("lok_id_lokalu"))
        if klucz[0] is not None and klucz in widziane:
            continue  # ten sam lokal w tej samej transakcji drugi raz
        widziane.add(klucz)
        lat = lng = None
        srodek = _srodek_geometrii(w.get(geometria)) if geometria else None
        if srodek is not None:
            if srs == 4326:
                lng, lat = srodek
            else:  # PL-1992: w pliku x = wschód, y = północ
                lat, lng = wgs84_z_pl1992(srodek[1], srodek[0])
            if not w_polsce(lat, lng):
                lat = lng = None
        lokale.append({
            "data": dzien.isoformat(),
            "rok": dzien.year,
            "kwartal": (dzien.month - 1) // 3 + 1,
            "rynek": _rynek(w.get("tran_rodzaj_rynku")),
            "rodzaj": str(w.get("tran_rodzaj_trans") or ""),
            "pow_m2": round(pow_m2, 2),
            "cena": round(cena, 2),
            "cena_m2": round(cena_m2, 2),
            "izby": int(_liczba(w.get("lok_liczba_izb")) or 0) or None,
            "lat": lat,
            "lng": lng,
        })
    return {"lokale": lokale, "odrzucone": {k: v for k, v in odrzucone.items() if v}, "kolumny": kolumny}


# ---------- statystyki ----------


def _kwartyle(liczby: list[float]) -> tuple[float, float, float]:
    if len(liczby) < 2:
        return liczby[0], liczby[0], liczby[0]
    q1, q2, q3 = statistics.quantiles(liczby, n=4, method="inclusive")
    return q1, q2, q3


def statystyki(lokale: list[dict]) -> dict | None:
    if not lokale:
        return None
    ceny_m2 = sorted(l["cena_m2"] for l in lokale)
    q1, mediana, q3 = _kwartyle(ceny_m2)
    po_kwartale: dict = {}
    for l in lokale:
        po_kwartale.setdefault((l["rok"], l["kwartal"]), []).append(l["cena_m2"])
    trend = [
        {"rok": r, "kwartal": k, "liczba": len(v), "mediana_m2": statistics.median(v)}
        for (r, k), v in sorted(po_kwartale.items())
    ]
    po_izbach: dict = {}
    for l in lokale:
        klucz = "brak" if l["izby"] is None else ("4+" if l["izby"] >= 4 else str(l["izby"]))
        po_izbach.setdefault(klucz, []).append(l)
    izby = [
        {"izby": k, "liczba": len(v), "mediana_m2": statistics.median(x["cena_m2"] for x in v), "mediana_pow": statistics.median(x["pow_m2"] for x in v)}
        for k, v in sorted(po_izbach.items(), key=lambda p: (p[0] == "brak", p[0]))
    ]
    # histogram cen za m² od 2. do 98. percentyla (skrajne wartości nie rozciągają osi)
    lo = ceny_m2[int(0.02 * (len(ceny_m2) - 1))]
    hi = ceny_m2[int(0.98 * (len(ceny_m2) - 1))]
    przedzialy = 12
    szer = (hi - lo) / przedzialy or 1
    histogram = [{"od": lo + i * szer, "do": lo + (i + 1) * szer, "liczba": 0} for i in range(przedzialy)]
    for c in ceny_m2:
        if lo <= c <= hi:
            histogram[min(przedzialy - 1, int((c - lo) / szer))]["liczba"] += 1
    return {
        "liczba": len(lokale),
        "mediana_m2": mediana,
        "q1_m2": q1,
        "q3_m2": q3,
        "mediana_ceny": statistics.median(l["cena"] for l in lokale),
        "mediana_pow": statistics.median(l["pow_m2"] for l in lokale),
        "od": min(l["data"] for l in lokale),
        "do": max(l["data"] for l in lokale),
        "trend": trend,
        "izby": izby,
        "histogram": histogram,
    }


def punkty_mapy(lokale: list[dict]) -> dict:
    """Punkty z położeniem, najwyżej MAKS_PUNKTOW_MAPY (najnowsze), z progami
    kwintyli ceny za m² do kolorów."""
    z_polozeniem = sorted((l for l in lokale if l["lat"] is not None), key=lambda l: l["data"], reverse=True)
    wybrane = z_polozeniem[:MAKS_PUNKTOW_MAPY]
    ceny = [l["cena_m2"] for l in wybrane]
    progi = statistics.quantiles(ceny, n=5, method="inclusive") if len(ceny) >= 5 else []
    return {
        "punkty": [[round(l["lat"], 6), round(l["lng"], 6), round(l["cena_m2"]), l["data"], round(l["pow_m2"], 1)] for l in wybrane],
        "progi": progi,
        "wszystkich_z_polozeniem": len(z_polozeniem),
    }
