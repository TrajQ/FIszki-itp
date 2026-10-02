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

ETAP 106 — działki (tabela `transakcje_dzialki`, kolumny `dzi_cena_brutto`,
`dzi_pow_ewid`, `dzi_przezn_wmpzp`, `dzi_sposob_uzyt`, `nier_rodzaj`, z tych
samych projektów). Powierzchnię bierzemy z obrysu działki w pliku (PL-1992,
metry), nie z `dzi_pow_ewid`: projekty różnią się co do jej jednostki (ha
albo m², w części plików mieszane). Cena: cena działki, a bez niej cena
całej transakcji na sumę powierzchni jej działek (np. dwie sąsiednie
działki sprzedane razem). Dla działki zabudowanej cena obejmuje budynek —
dlatego filtr „nieruchomość”.
"""

import math
import re
import sqlite3
import statistics
import struct
from collections import Counter
from datetime import date

import h3
import shapely
from shapely import wkb
from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union
from shapely.validation import make_valid

from mpzp.uklady import w_polsce, wgs84_z_pl1992

TABELA = "transakcje_lokale"
TABELA_DZIALKI = "transakcje_dzialki"
KOLUMNY_CENY_DZIALKI = ("dzi_cena_brutto", "nier_cena_brutto", "tran_cena_brutto")
# działki: od małej działki pod garaż do dużego gospodarstwa; cena od gruntów
# rolnych (kilka zł/m²) do centrów dużych miast
POW_DZIALKI_M2 = (20, 2_000_000)
CENA_DZIALKI_M2 = (0.5, 30_000)
KOLUMNY_CENY = ("lok_cena_brutto", "nier_cena_brutto", "tran_cena_brutto")
POW_M2 = (10, 500)
CENA_M2 = (500, 100_000)
MAKS_PUNKTOW_MAPY = 4000


class BladPliku(ValueError):
    """Plik nie jest GeoPackage RCN albo brakuje w nim potrzebnych danych."""


def _poczatek_wkb(blob: bytes | None) -> int | None:
    """Położenie WKB w blobie GeoPackage (za nagłówkiem „GP” i kopertą)."""
    if not blob or blob[:2] != b"GP":
        return None
    flagi = blob[3]
    dlugosc_koperty = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get((flagi >> 1) & 0b111)
    if dlugosc_koperty is None or flagi & 0b10000:  # zła koperta albo pusta geometria
        return None
    return 8 + dlugosc_koperty


def _ksztalt(blob: bytes | None):
    """Geometria shapely z blobu GeoPackage albo None."""
    poczatek = _poczatek_wkb(blob)
    if poczatek is None:
        return None
    try:
        return wkb.loads(bytes(blob[poczatek:]))
    except Exception:
        return None


def _srodek_geometrii(blob: bytes | None) -> tuple[float, float] | None:
    """(x, y) środka geometrii z blobu GeoPackage (nagłówek „GP” + WKB)."""
    poczatek = _poczatek_wkb(blob)
    if poczatek is None:
        return None
    if poczatek > 8:  # koperta: środek bez czytania całego WKB
        kolejnosc = "<" if blob[3] & 1 else ">"
        minx, maxx, miny, maxy = struct.unpack(kolejnosc + "4d", blob[8:40])
        return (minx + maxx) / 2, (miny + maxy) / 2
    ksztalt = _ksztalt(blob)
    if ksztalt is None:
        return None
    punkt = ksztalt.representative_point()
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


def _wiersze_tabeli(db, tabele: set, tabela: str, wymagane: list[str], ceny: tuple[str, ...]) -> tuple[list[dict], str | None, int | None]:
    """Wiersze tabeli RCN, nazwa kolumny geometrii i jej układ; BladPliku, gdy
    brakuje wymaganych kolumn albo wszystkich kolumn ceny."""
    kolumny = [w[1] for w in db.execute(f"PRAGMA table_info({tabela})")]
    brakuje = [k for k in wymagane if k not in kolumny] + ([] if any(k in kolumny for k in ceny) else ["kolumna ceny"])
    if brakuje:
        raise BladPliku(f"W tabeli {tabela} brakuje: {', '.join(brakuje)}. Kolumny w pliku: {', '.join(kolumny)[:400]}.")
    geometria = srs = None
    if "gpkg_geometry_columns" in tabele:
        wiersz = db.execute("SELECT column_name, srs_id FROM gpkg_geometry_columns WHERE table_name = ?", (tabela,)).fetchone()
        if wiersz:
            geometria, srs = wiersz
    db.row_factory = sqlite3.Row
    wiersze = [dict(w) for w in db.execute(f"SELECT * FROM {tabela}")]
    db.row_factory = None
    return wiersze, geometria, srs


def czytaj_plik(sciezka: str) -> dict:
    """GeoPackage RCN → {"lokale", "odrzucone", "dzialki", "odrzucone_dzialki"}.

    Czyta tabelę lokali i tabelę działek — tę, która jest w pliku; błąd,
    gdy nie ma żadnej."""
    db = sqlite3.connect(f"file:{sciezka}?mode=ro", uri=True)
    try:
        tabele = {w[0] for w in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as e:
        db.close()  # connect() nie czyta pliku — błąd wychodzi dopiero przy pierwszym zapytaniu
        raise BladPliku("To nie jest plik GeoPackage (baza SQLite).") from e
    wynik = {"lokale": [], "odrzucone": {}, "dzialki": [], "odrzucone_dzialki": {}}
    try:
        if TABELA not in tabele and TABELA_DZIALKI not in tabele:
            raise BladPliku(f"W pliku nie ma tabeli „{TABELA}” ani „{TABELA_DZIALKI}” — to nie jest plik RCN. Tabele w pliku: {', '.join(sorted(t for t in tabele if not t.startswith(('gpkg_', 'rtree_', 'sqlite_'))))[:300]}.")
        if TABELA in tabele:
            wiersze, geometria, srs = _wiersze_tabeli(db, tabele, TABELA, ["lok_pow_uzyt", "dok_data"], KOLUMNY_CENY)
            wynik.update(_lokale(wiersze, geometria, srs))
        if TABELA_DZIALKI in tabele:
            wiersze, geometria, srs = _wiersze_tabeli(db, tabele, TABELA_DZIALKI, ["dok_data"], KOLUMNY_CENY_DZIALKI)
            if geometria is None:
                raise BladPliku(f"Tabela {TABELA_DZIALKI} nie ma geometrii (obrysów działek) — bez nich nie da się policzyć powierzchni.")
            wynik.update(_dzialki(wiersze, geometria, srs))
    finally:
        db.close()
    return wynik


def _na_wgs84(x: float, y: float, srs: int | None) -> tuple[float | None, float | None]:
    if srs == 4326:
        lng, lat = x, y
    else:  # PL-1992: w pliku x = wschód, y = północ
        lat, lng = wgs84_z_pl1992(y, x)
    return (lat, lng) if w_polsce(lat, lng) else (None, None)


# ETAP 112: piętro lokalu (`lok_nr_kond`) w przedziałach do filtra i tabeli
PIETRA = {"parter": (-5, 0), "1-3": (1, 3), "4-9": (4, 9), "10+": (10, 200)}
OPISY_PIETER = {"parter": "parter (i niżej)", "1-3": "1–3 piętro", "4-9": "4–9 piętro", "10+": "10 piętro i wyżej"}


def _kondygnacja(wartosc) -> int | None:
    """Numer kondygnacji lokalu: liczba albo „parter”; inne zapisy → brak danych."""
    tekst = str(wartosc or "").strip().lower()
    if "parter" in tekst:
        return 0
    dopasowanie = re.match(r"-?\d+", tekst)
    if not dopasowanie:
        return None
    numer = int(dopasowanie.group())
    return numer if -5 <= numer <= 200 else None


def przedzial_pietra(kondygnacja: int | None) -> str | None:
    if kondygnacja is None:
        return None
    return next(k for k, (od, do) in PIETRA.items() if od <= kondygnacja <= do)


def _lokale(wiersze: list[dict], geometria: str | None, srs: int | None) -> dict:
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
        srodek = _srodek_geometrii(w.get(geometria)) if geometria else None
        lat, lng = _na_wgs84(*srodek, srs) if srodek else (None, None)
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
            "kondygnacja": _kondygnacja(w.get("lok_nr_kond")),
            "lat": lat,
            "lng": lng,
        })
    return {"lokale": lokale, "odrzucone": {k: v for k, v in odrzucone.items() if v}}


def _czytelne(kod) -> str:
    """„budownictwoMieszkaniowe” → „budownictwo mieszkaniowe” (wartości słownikowe RCN)."""
    tekst = " ".join(str(kod or "").split())
    return re.sub(r"(?<=[a-ząćęłńóśźż])(?=[A-ZĄĆĘŁŃÓŚŹŻ])", " ", tekst).lower()


def _wspolne(wartosci: list[str]) -> str:
    rozne = {w for w in wartosci if w}
    return rozne.pop() if len(rozne) == 1 else ("różne" if rozne else "")


def _dzialki(wiersze: list[dict], geometria: str, srs: int | None) -> dict:
    """Wiersze tabeli działek → transakcje z ceną za m² gruntu.

    Działka z własną ceną to jeden rekord. Działki transakcji bez własnych
    cen łączymy w jeden rekord: cena transakcji / suma ich powierzchni.
    Liczniki odrzuconych liczą działki."""
    odrzucone = {"udział w działce": 0, "brak daty": 0, "brak obrysu działki": 0, "bez ceny działki": 0,
                 "nierealna powierzchnia": 0, "nierealna cena za m²": 0}
    transakcje: dict = {}
    for nr, w in enumerate(wiersze):
        dzialki_transakcji = transakcje.setdefault(w.get("tran_lokalny_id_iip") or f"bez identyfikatora {nr}", {})
        dzialki_transakcji.setdefault(w.get("dzi_id_dzialki") or nr, w)  # ta sama działka drugi raz — pomijamy
    wynik = []
    for dzialki_transakcji in transakcje.values():
        czesci = []
        for w in dzialki_transakcji.values():
            if w.get("nier_udzial") not in (None, "", "1/1", "1"):
                odrzucone["udział w działce"] += 1
                continue
            dzien = _data(w.get("dok_data"))
            if dzien is None:
                odrzucone["brak daty"] += 1
                continue
            ksztalt = _ksztalt(w.get(geometria)) if srs != 4326 else None  # pole w metrach tylko z układu płaskiego
            if ksztalt is None or ksztalt.area <= 0:
                odrzucone["brak obrysu działki"] += 1
                continue
            czesci.append((w, dzien, ksztalt))
        wlasne = [c for c in czesci if _liczba(c[0].get("dzi_cena_brutto"))]
        bez_ceny = [c for c in czesci if not _liczba(c[0].get("dzi_cena_brutto"))]
        rekordy = [([c], _liczba(c[0]["dzi_cena_brutto"])) for c in wlasne]
        if bez_ceny:
            cena = None
            if not wlasne:  # cena transakcji obejmuje wtedy dokładnie te działki
                pierwsza = bez_ceny[0][0]
                cena = (_liczba(pierwsza.get("nier_cena_brutto")) if len(bez_ceny) == 1 else None) or _liczba(pierwsza.get("tran_cena_brutto"))
            if cena:
                rekordy.append((bez_ceny, cena))
            else:
                odrzucone["bez ceny działki"] += len(bez_ceny)
        for czesc, cena in rekordy:
            pow_m2 = sum(k.area for _, _, k in czesc)
            if not POW_DZIALKI_M2[0] <= pow_m2 <= POW_DZIALKI_M2[1]:
                odrzucone["nierealna powierzchnia"] += len(czesc)
                continue
            if not CENA_DZIALKI_M2[0] <= cena / pow_m2 <= CENA_DZIALKI_M2[1]:
                odrzucone["nierealna cena za m²"] += len(czesc)
                continue
            w, dzien, _ = czesc[0]
            punkt = unary_union([k for _, _, k in czesc]).representative_point()
            lat, lng = _na_wgs84(punkt.x, punkt.y, srs)
            wynik.append({
                "data": dzien.isoformat(),
                "rok": dzien.year,
                "kwartal": (dzien.month - 1) // 3 + 1,
                "rynek": _rynek(w.get("tran_rodzaj_rynku")),
                "rodzaj": str(w.get("tran_rodzaj_trans") or ""),
                "pow_m2": round(pow_m2, 1),
                "cena": round(cena, 2),
                "cena_m2": round(cena / pow_m2, 2),
                "przeznaczenie": _wspolne([_czytelne(c[0].get("dzi_przezn_wmpzp")) for c in czesc]),
                "uzytek": _wspolne([_czytelne(c[0].get("dzi_sposob_uzyt")) for c in czesc]),
                "nieruchomosc": _czytelne(w.get("nier_rodzaj")),
                "dzialek": len(czesc),
                "lat": lat,
                "lng": lng,
            })
    return {"dzialki": wynik, "odrzucone_dzialki": {k: v for k, v in odrzucone.items() if v}}


# ---------- statystyki ----------


def _kwartyle(liczby: list[float]) -> tuple[float, float, float]:
    if len(liczby) < 2:
        return liczby[0], liczby[0], liczby[0]
    q1, q2, q3 = statistics.quantiles(liczby, n=4, method="inclusive")
    return q1, q2, q3


MAKS_GRUP = 10


def _grupy(lokale: list[dict]) -> list[dict]:
    """Tabela pod wykresami: lokale według liczby izb, działki (ETAP 106)
    według przeznaczenia w planie — najczęstsze, reszta jako „pozostałe”."""
    po_grupie: dict = {}
    if "izby" in lokale[0]:
        for l in lokale:
            po_grupie.setdefault("brak" if l["izby"] is None else ("4+" if l["izby"] >= 4 else str(l["izby"])), []).append(l)
        kolejnosc = sorted(po_grupie.items(), key=lambda p: (p[0] == "brak", p[0]))
    else:
        for l in lokale:
            po_grupie.setdefault(l["przeznaczenie"] or "brak danych", []).append(l)
        kolejnosc = sorted(po_grupie.items(), key=lambda p: -len(p[1]))
        if len(kolejnosc) > MAKS_GRUP:
            reszta = [l for _, v in kolejnosc[MAKS_GRUP - 1:] for l in v]
            kolejnosc = kolejnosc[:MAKS_GRUP - 1] + [("pozostałe", reszta)]
    return [
        {"nazwa": k, "liczba": len(v), "mediana_m2": statistics.median(x["cena_m2"] for x in v), "mediana_pow": statistics.median(x["pow_m2"] for x in v)}
        for k, v in kolejnosc
    ]


def _pietra(lokale: list[dict]) -> list[dict]:
    """Lokale według piętra (ETAP 112); „brak danych” na końcu."""
    po_pietrze: dict = {}
    for l in lokale:
        po_pietrze.setdefault(przedzial_pietra(l["kondygnacja"]), []).append(l)
    kolejnosc = [k for k in PIETRA if k in po_pietrze] + ([None] if None in po_pietrze else [])
    return [
        {"pietro": k, "nazwa": OPISY_PIETER.get(k, "brak danych"), "liczba": len(po_pietrze[k]),
         "mediana_m2": statistics.median(x["cena_m2"] for x in po_pietrze[k]),
         "mediana_pow": statistics.median(x["pow_m2"] for x in po_pietrze[k])}
        for k in kolejnosc
    ]


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
    grupy = _grupy(lokale)
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
        "grupy": grupy,
        "pietra": _pietra(lokale) if "kondygnacja" in lokale[0] else [],
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


# ---------- obszary do porównania i raport (ETAP 105) ----------

MAKS_OBSZAROW = 8
# kwintyle ceny za m² — te same kolory co na mapie (ceny/static/transakcje.js)
KOLORY_KLAS = ["#ffe8a3", "#ffc55c", "#ff9f0a", "#e2630b", "#a33a00"]
KOLORY_OBSZAROW = ["#0071e3", "#34c759", "#5e5ce6", "#ff375f", "#30b0c7", "#8e6e4e", "#bf5af2", "#1d1d1f"]


def sprawdz_obszar(geometria) -> dict:
    """GeoJSON wieloboku z mapy → poprawiona geometria (WGS84) albo BladPliku."""
    try:
        g = shape(geometria)
    except Exception as e:
        raise BladPliku("Obszar musi być wielobokiem GeoJSON.") from e
    if g.geom_type not in ("Polygon", "MultiPolygon"):
        raise BladPliku("Obszar musi być wielobokiem.")
    if not g.is_valid:
        g = make_valid(g)
    minx, miny, maxx, maxy = g.bounds
    if not (w_polsce(miny, minx) and w_polsce(maxy, maxx)) or g.area <= 0:
        raise BladPliku("Obszar musi leżeć w Polsce i mieć niezerowe pole.")
    return mapping(g)


def _w_ksztalcie(ksztalt, xs: list[float], ys: list[float]) -> list[bool]:
    """Czy punkty (xs, ys) leżą w kształcie — jedno wywołanie shapely dla
    wszystkich punktów (ETAP 117: przy 100 tys. transakcji ok. 50 razy
    szybciej niż osobny `Point` dla każdej)."""
    return shapely.contains_xy(ksztalt, xs, ys).tolist() if xs else []


def w_obszarze(lokale: list[dict], geometria: dict) -> list[dict]:
    z_polozeniem = [l for l in lokale if l["lat"] is not None]
    wewnatrz = _w_ksztalcie(shape(geometria), [l["lng"] for l in z_polozeniem], [l["lat"] for l in z_polozeniem])
    return [l for l, w in zip(z_polozeniem, wewnatrz) if w]


def _mediany_lat(lokale: list[dict]) -> dict[int, float]:
    po_roku: dict = {}
    for l in lokale:
        po_roku.setdefault(l["rok"], []).append(l["cena_m2"])
    return {r: statistics.median(v) for r, v in sorted(po_roku.items())}


MIN_W_RYNKU = 5  # ETAP 135: premia rynku pierwotnego tylko przy co najmniej tylu transakcjach w obu rynkach


def _rynki(zbior: list[dict]) -> dict:
    """Mediana za m² osobno na rynku pierwotnym i wtórnym oraz premia
    pierwotnego (%), gdy oba rynki mają co najmniej MIN_W_RYNKU transakcji."""
    rynki = {}
    for rynek in ("pierwotny", "wtórny"):
        ceny = [l["cena_m2"] for l in zbior if l["rynek"] == rynek]
        rynki[rynek] = {"liczba": len(ceny), "mediana_m2": statistics.median(ceny) if ceny else None}
    p, w = rynki["pierwotny"], rynki["wtórny"]
    premia = 100 * (p["mediana_m2"] / w["mediana_m2"] - 1) if min(p["liczba"], w["liczba"]) >= MIN_W_RYNKU else None
    return {"rynki": rynki, "premia_pierwotnego_proc": premia}


def porownanie(lokale: list[dict], obszary: list[dict]) -> dict:
    """Wiersz „cały plik” i po jednym dla każdego obszaru: liczba, mediana za m²
    z kwartylami, mediana powierzchni i ceny, różnica mediany wobec całości,
    mediany w latach."""
    def wiersz(nazwa, zbior, kolor=None, obszar_id=None):
        if not zbior:
            return {"id": obszar_id, "nazwa": nazwa, "kolor": kolor, "liczba": 0}
        ceny = sorted(l["cena_m2"] for l in zbior)
        q1, med, q3 = _kwartyle(ceny)
        return {
            "id": obszar_id, "nazwa": nazwa, "kolor": kolor, "liczba": len(zbior),
            "mediana_m2": med, "q1_m2": q1, "q3_m2": q3,
            "mediana_pow": statistics.median(l["pow_m2"] for l in zbior),
            "mediana_ceny": statistics.median(l["cena"] for l in zbior),
            "lata": _mediany_lat(zbior),
            "lata_liczba": {r: n for r, n in sorted(Counter(l["rok"] for l in zbior).items())},
            **_rynki(zbior),
        }

    calosc = wiersz("cały plik", lokale)
    wiersze = []
    for i, o in enumerate(obszary):
        w = wiersz(o["nazwa"], w_obszarze(lokale, o["geometria"]), KOLORY_OBSZAROW[i % len(KOLORY_OBSZAROW)], o["id"])
        if w["liczba"] and calosc["liczba"]:
            w["wobec_calosci_proc"] = 100 * (w["mediana_m2"] / calosc["mediana_m2"] - 1)
        wiersze.append(w)
    lata = sorted({r for w in [calosc, *wiersze] for r in w.get("lata", {})})
    return {"calosc": calosc, "obszary": wiersze, "lata": lata}


# ---------- zestawienie kilku plików RCN — różne powiaty obok siebie (ETAP 165) ----------

MAKS_PLIKOW_ZESTAWIENIA = 4


def zestawienie_plikow(zbiory: list[tuple[str, list[dict], list[dict]]]) -> dict:
    """[(nazwa pliku, transakcje po filtrach, obszary pliku)] → wiersz na plik
    (z różnicą mediany wobec pierwszego pliku) i pod nim jego obszary.
    Pliki się nie mieszają — każdy liczony osobno, jak w porównaniu obszarów.
    `pliki` + `lata` pasują do wykres_lat_svg (linia na plik)."""
    pliki = []
    for i, (nazwa, lokale, obszary) in enumerate(zbiory):
        por = porownanie(lokale, obszary)
        wiersz = {**por["calosc"], "nazwa": nazwa, "kolor": KOLORY_OBSZAROW[i % len(KOLORY_OBSZAROW)], "obszary": por["obszary"]}
        pierwszy = pliki[0] if pliki else wiersz
        if i and wiersz["liczba"] and pierwszy["liczba"]:
            wiersz["wobec_pierwszego_proc"] = 100 * (wiersz["mediana_m2"] / pierwszy["mediana_m2"] - 1)
        pliki.append(wiersz)
    lata = sorted({r for p in pliki for r in p.get("lata", {})})
    return {"pliki": pliki, "lata": lata}


def wykres_plikow_svg(zestawienie: dict) -> str:
    """Wykres median w latach — linia na plik (bez linii „cały plik”)."""
    return wykres_lat_svg({"obszary": zestawienie["pliki"], "calosc": {}, "lata": zestawienie["lata"]})


def mapa_svg(lokale: list[dict], obszary: list[dict], progi: list[float], kolory: list[str],
             szerokosc: int = 1000, wysokosc: int = 620) -> str:
    """Schematyczna mapa do raportu: punkty transakcji w klasach ceny i
    obrysy obszarów z numerami, podziałka i strzałka północy. Tylko liczby i
    kolory z kodu (nazwy obszarów są w legendzie raportu, nie w SVG)."""
    # te same punkty co na mapie strony: najwyżej MAKS_PUNKTOW_MAPY najnowszych (ETAP 117 —
    # wcześniej rysowało wszystkie, przy 100 tys. transakcji raport miał 9 MB)
    najnowsze = sorted((l for l in lokale if l["lat"] is not None), key=lambda l: l["data"], reverse=True)[:MAKS_PUNKTOW_MAPY]
    punkty = [(l["lng"], l["lat"], l["cena_m2"]) for l in najnowsze]
    ksztalty = [shape(o["geometria"]) for o in obszary]
    xs = [p[0] for p in punkty] + [b for k in ksztalty for b in (k.bounds[0], k.bounds[2])]
    ys = [p[1] for p in punkty] + [b for k in ksztalty for b in (k.bounds[1], k.bounds[3])]
    otwarcie = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>'
    if not xs:
        return otwarcie + f'<text x="{szerokosc / 2}" y="{wysokosc / 2}" text-anchor="middle" fill="#6e6e73">brak transakcji z położeniem</text></svg>'
    kx = math.cos(math.radians((min(ys) + max(ys)) / 2))  # metry na stopień długości / szerokości
    margines = 30
    skala = min((szerokosc - 2 * margines) / (((max(xs) - min(xs)) * kx) or 1e-9), (wysokosc - 2 * margines - 20) / ((max(ys) - min(ys)) or 1e-9))

    def px(lng, lat):
        return margines + (lng - min(xs)) * kx * skala, margines + (max(ys) - lat) * skala

    czesci = [otwarcie]
    for lng, lat, cena in sorted(punkty, key=lambda p: p[2]):
        i = 0
        while i < len(progi) and cena > progi[i]:
            i += 1
        x, y = px(lng, lat)
        czesci.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{kolory[i]}" stroke="#3a2a1a" stroke-width="0.3"/>')
    for nr, (k, o) in enumerate(zip(ksztalty, obszary), start=1):
        kolor = KOLORY_OBSZAROW[(nr - 1) % len(KOLORY_OBSZAROW)]
        for w in getattr(k, "geoms", [k]):
            d = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in (px(*p) for p in w.exterior.coords)) + " Z"
            czesci.append(f'<path d="{d}" fill="{kolor}" fill-opacity="0.06" stroke="{kolor}" stroke-width="2.5"/>')
        x, y = px(*k.representative_point().coords[0])
        czesci.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="#ffffff" stroke="{kolor}" stroke-width="2"/><text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" font-weight="700" fill="{kolor}">{nr}</text>')
    # podziałka: okrągła długość do ok. 1/4 szerokości
    m_na_px = 111_320 / skala
    dlugosc_m = max((k for k in (100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000) if k / m_na_px <= szerokosc / 4), default=100)
    dl = dlugosc_m / m_na_px
    y0 = wysokosc - 14
    czesci.append(
        f'<g stroke="#1d1d1f" stroke-width="2"><line x1="{margines}" y1="{y0}" x2="{margines + dl:.1f}" y2="{y0}"/>'
        f'<line x1="{margines}" y1="{y0 - 5}" x2="{margines}" y2="{y0 + 1}"/><line x1="{margines + dl:.1f}" y1="{y0 - 5}" x2="{margines + dl:.1f}" y2="{y0 + 1}"/></g>'
        f'<text x="{margines + dl + 6:.1f}" y="{y0 + 4}" fill="#1d1d1f">{dlugosc_m if dlugosc_m < 1000 else dlugosc_m // 1000} {"m" if dlugosc_m < 1000 else "km"}</text>'
    )
    x = szerokosc - margines
    czesci.append(f'<path d="M{x},{margines - 12} L{x + 6},{margines + 4} L{x},{margines} L{x - 6},{margines + 4} Z" fill="#1d1d1f"/><text x="{x}" y="{margines + 18}" text-anchor="middle" fill="#1d1d1f">N</text>')
    czesci.append("</svg>")
    return "".join(czesci)


# ---------- podobne transakcje — wycena porównawcza (ETAP 107) ----------

PROMIENIE_M = (250, 500, 1000, 2000, 5000)
TOLERANCJE = (0.1, 0.2, 0.3, 0.5)
MIN_PODOBNYCH = 5
MAKS_NA_LISCIE = 30


def odleglosc_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Odległość w metrach (równoodległościowe przybliżenie — w skali
    kilku km błąd poniżej promila)."""
    r = 6_371_000
    dx = math.radians(lng2 - lng1) * math.cos(math.radians((lat1 + lat2) / 2))
    dy = math.radians(lat2 - lat1)
    return r * math.hypot(dx, dy)


def podobne(rekordy: list[dict], lat: float, lng: float, promien_m: float, pow_m2: float, tolerancja: float) -> dict:
    """Transakcje w promieniu od punktu o powierzchni pow_m2 ± tolerancja.

    Szacunek to mediana ceny za m² podobnych transakcji razy powierzchnia —
    orientacja z danych, nie operat szacunkowy (bez korekt na stan, piętro,
    datę)."""
    kandydaci = []
    for r in rekordy:
        if r["lat"] is None or abs(r["pow_m2"] - pow_m2) > tolerancja * pow_m2:
            continue
        odl = odleglosc_m(lat, lng, r["lat"], r["lng"])
        if odl <= promien_m:
            kandydaci.append({**r, "odleglosc_m": round(odl)})
    kandydaci.sort(key=lambda r: (r["odleglosc_m"], r["data"]))
    wynik = {"liczba": len(kandydaci), "wystarczy": len(kandydaci) >= MIN_PODOBNYCH, "min_podobnych": MIN_PODOBNYCH,
             "pow_m2": pow_m2, "promien_m": promien_m, "tolerancja": tolerancja}
    if not kandydaci:
        return {**wynik, "transakcje": []}
    q1, mediana, q3 = _kwartyle(sorted(r["cena_m2"] for r in kandydaci))
    return {
        **wynik,
        "mediana_m2": mediana,
        "q1_m2": q1,
        "q3_m2": q3,
        "szacunek": mediana * pow_m2,
        "szacunek_od": q1 * pow_m2,
        "szacunek_do": q3 * pow_m2,
        "od": min(r["data"] for r in kandydaci),
        "do": max(r["data"] for r in kandydaci),
        "transakcje": [
            {k: r.get(k) for k in ("data", "rynek", "pow_m2", "cena", "cena_m2", "izby", "kondygnacja", "przeznaczenie", "lat", "lng", "odleglosc_m")}
            for r in kandydaci[:MAKS_NA_LISCIE]
        ],
    }


# ---------- mapa cen w heksagonach H3 (ETAP 108) ----------

ROZDZIELCZOSCI_H3 = (7, 8, 9)  # średnia krawędź wg h3: ok. 1,4 km / 530 m / 200 m
MINIMA_W_KOMORCE = (3, 5, 10)


def krawedz_h3_m(rozdzielczosc: int) -> int:
    """Średnia długość krawędzi heksagonu H3, zaokrąglona do 10 m."""
    return int(round(h3.average_hexagon_edge_length(rozdzielczosc, unit="m"), -1))


def heksagony(rekordy: list[dict], rozdzielczosc: int, minimum: int) -> dict:
    """Mediana ceny za m² w komórkach H3. Komórki z mniej niż `minimum`
    transakcjami są ukryte (jedna transakcja nie maluje całego heksagonu);
    progi kolorów — kwintyle median pokazanych komórek."""
    po_komorce: dict = {}
    for r in rekordy:
        if r["lat"] is not None:
            po_komorce.setdefault(h3.latlng_to_cell(r["lat"], r["lng"], rozdzielczosc), []).append(r["cena_m2"])
    komorki, ukryte, w_ukrytych = [], 0, 0
    for komorka, ceny in sorted(po_komorce.items()):
        if len(ceny) < minimum:
            ukryte += 1
            w_ukrytych += len(ceny)
            continue
        komorki.append({
            "h3": komorka,
            "granica": [[round(a, 6), round(b, 6)] for a, b in h3.cell_to_boundary(komorka)],
            "liczba": len(ceny),
            "mediana_m2": statistics.median(ceny),
        })
    mediany = [k["mediana_m2"] for k in komorki]
    return {
        "rozdzielczosc": rozdzielczosc,
        "krawedz_m": krawedz_h3_m(rozdzielczosc),
        "minimum": minimum,
        "komorki": komorki,
        "progi": statistics.quantiles(mediany, n=5, method="inclusive") if len(mediany) >= 5 else [],
        "ukryte": ukryte,
        "transakcji_w_ukrytych": w_ukrytych,
    }


# ---------- ceny w okolicy działki / obszaru (ETAP 109, dla MPZP i osiedla) ----------

PROMIENIE_OKOLICY_M = (250, 500, 1000, 2000)
NIEZABUDOWANA = "gruntowa niezabudowana"  # wartość nier_rodzaj po _czytelne (ETAP 164)


def ksztalt_okolicy(geometria) -> object:
    """GeoJSON punktu albo wieloboku (WGS84) z MPZP / osiedla → shapely; BladPliku, gdy zły."""
    if isinstance(geometria, dict) and geometria.get("type") == "Point":
        try:
            punkt = shape(geometria)
        except Exception as e:
            raise BladPliku("Niepoprawny punkt.") from e
        if not w_polsce(punkt.y, punkt.x):
            raise BladPliku("Punkt musi leżeć w Polsce.")
        return punkt
    return shape(sprawdz_obszar(geometria))


def prostokat_okolicy(ksztalt, promien_m: float) -> tuple[float, float, float, float]:
    """(lat_min, lat_max, lng_min, lng_max) obejmujący kształt z zapasem promienia — do zapytania SQL."""
    minx, miny, maxx, maxy = ksztalt.bounds
    dlat = promien_m / 111_195 * 1.01
    dlng = dlat / math.cos(math.radians((miny + maxy) / 2))
    return miny - dlat, maxy + dlat, minx - dlng, maxx + dlng


def okolica(rekordy: list[dict], ksztalt, promien_m: float) -> dict | None:
    """Transakcje w odległości do promien_m od kształtu (wewnątrz: 0 m).

    Odległość w lokalnym układzie metrycznym wokół kształtu (przybliżenie
    równoodległościowe, jak w `odleglosc_m`)."""
    srodek = ksztalt.centroid
    kx = math.cos(math.radians(srodek.y)) * 111_195
    ky = 111_195
    lokalny = shapely_transform(lambda x, y, z=None: ((x - srodek.x) * kx, (y - srodek.y) * ky), ksztalt)
    z_polozeniem = [r for r in rekordy if r["lat"] is not None]
    xs = [(r["lng"] - srodek.x) * kx for r in z_polozeniem]
    ys = [(r["lat"] - srodek.y) * ky for r in z_polozeniem]
    w_buforze = _w_ksztalcie(lokalny.buffer(promien_m), xs, ys)
    wewnatrz = _w_ksztalcie(lokalny, xs, ys)
    w_zasiegu = [r for r, w in zip(z_polozeniem, w_buforze) if w]
    w_srodku = sum(wewnatrz)
    if not w_zasiegu:
        return None
    q1, mediana, q3 = _kwartyle(sorted(r["cena_m2"] for r in w_zasiegu))
    return {
        "liczba": len(w_zasiegu),
        "w_srodku": w_srodku,
        "mediana_m2": mediana,
        "q1_m2": q1,
        "q3_m2": q3,
        "mediana_pow": statistics.median(r["pow_m2"] for r in w_zasiegu),
        "od": min(r["data"] for r in w_zasiegu),
        "do": max(r["data"] for r in w_zasiegu),
        "lata": _mediany_lat(w_zasiegu),
    }


# ---------- trend cen w obszarach (ETAP 110) ----------

MIN_W_ROKU = 5  # rok z mniejszą liczbą transakcji: punkt pusty (mediana niepewna)


def _ladna_os(lo: float, hi: float, podzialek: int = 5) -> tuple[float, float, float]:
    """Zakres osi zaokrąglony do „ładnego” kroku 1/2/2,5/5 × 10^n."""
    rozpietosc = (hi - lo) or abs(hi) or 1
    potega = 10 ** math.floor(math.log10(rozpietosc / podzialek))
    krok = next(k * potega for k in (1, 2, 2.5, 5, 10) if rozpietosc / (k * potega) <= podzialek)
    return math.floor(lo / krok) * krok, math.ceil(hi / krok) * krok, krok


def wykres_lat_svg(por: dict, szerokosc: int = 900, wysokosc: int = 300) -> str:
    """Wykres liniowy median ceny za m² w latach: obszary w ich kolorach,
    cały plik linią przerywaną. Rok z mniej niż MIN_W_ROKU transakcjami —
    pusty punkt. Tylko liczby i kolory z kodu (nazwy są w legendzie raportu)."""
    lata = por["lata"]
    serie = [(o["kolor"], o.get("lata", {}), o.get("lata_liczba", {}), str(nr), False) for nr, o in enumerate(por["obszary"], start=1)]
    serie.append(("#6e6e73", por["calosc"].get("lata", {}), por["calosc"].get("lata_liczba", {}), "", True))
    wartosci = [v for _, med, _, _, _ in serie for v in med.values()]
    otwarcie = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="#ffffff"/>'
    if len(lata) < 2 or not wartosci:
        return otwarcie + f'<text x="{szerokosc / 2}" y="{wysokosc / 2}" text-anchor="middle" fill="#6e6e73">za mało lat do wykresu</text></svg>'
    lo, hi, krok = _ladna_os(min(wartosci), max(wartosci))
    m = {"l": 70, "p": 40, "g": 14, "d": 30}

    def x(rok):
        return m["l"] + (lata.index(rok)) * (szerokosc - m["l"] - m["p"]) / (len(lata) - 1)

    def y(v):
        return wysokosc - m["d"] - (v - lo) / ((hi - lo) or 1) * (wysokosc - m["g"] - m["d"])

    czesci = [otwarcie]
    v = lo
    while v <= hi + krok / 2:
        etykieta = f"{v:,.0f}".replace(",", " ")
        czesci.append(f'<line x1="{m["l"]}" x2="{szerokosc - m["p"]}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#e8e8ed"/>'
                      f'<text x="{m["l"] - 8}" y="{y(v) + 4:.1f}" text-anchor="end" fill="#6e6e73">{etykieta}</text>')
        v += krok
    co_ile = math.ceil(len(lata) / 12)  # najwyżej ~12 podpisów lat; ostatni rok zawsze podpisany
    for i, rok in enumerate(lata):
        if (len(lata) - 1 - i) % co_ile == 0:
            czesci.append(f'<text x="{x(rok):.1f}" y="{wysokosc - 10}" text-anchor="middle" fill="#6e6e73">{rok}</text>')
    for kolor, mediany, liczby, numer, przerywana in serie:
        punkty = [(x(r), y(mediany[r]), liczby.get(r, 0)) for r in lata if r in mediany]
        if not punkty:
            continue
        kreska = ' stroke-dasharray="6 4"' if przerywana else ""
        czesci.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b, _ in punkty)}" fill="none" stroke="{kolor}" stroke-width="2.5"{kreska}/>')
        for a, b, n in punkty:
            wypelnienie = kolor if n >= MIN_W_ROKU else "#ffffff"
            czesci.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="4" fill="{wypelnienie}" stroke="{kolor}" stroke-width="2"/>')
        if numer:
            a, b, _ = punkty[-1]
            czesci.append(f'<text x="{a + 8:.1f}" y="{b + 4:.1f}" font-weight="700" fill="{kolor}">{numer}</text>')
    czesci.append("</svg>")
    return "".join(czesci)


# ---------- zmiana cen w heksagonach między dwoma okresami (ETAP 111) ----------

# stałe, symetryczne klasy zmiany mediany [%] — ta sama skala na każdej mapie
PROGI_ZMIANY = [-10, -2, 2, 10, 20]
KOLORY_ZMIANY = ["#2b6cb0", "#90cdf4", "#d2d2d7", "#ffc55c", "#ff9f0a", "#a33a00"]


def zmiana_heksagonow(rekordy: list[dict], rozdzielczosc: int, minimum: int,
                      okres_a: tuple[int, int], okres_b: tuple[int, int]) -> dict:
    """Zmiana mediany ceny za m² w komórkach H3 z okresu A do okresu B (lata
    włącznie). Pokazane tylko komórki z co najmniej `minimum` transakcjami
    w OBU okresach. Zmiana mediany to też zmiana tego, co sprzedano (inne
    mieszkania w każdym okresie) — nie indeks cen."""
    po_komorce: dict = {}
    for r in rekordy:
        if r["lat"] is None:
            continue
        okres = "a" if okres_a[0] <= r["rok"] <= okres_a[1] else "b" if okres_b[0] <= r["rok"] <= okres_b[1] else None
        if okres:
            komorka = po_komorce.setdefault(h3.latlng_to_cell(r["lat"], r["lng"], rozdzielczosc), {"a": [], "b": []})
            komorka[okres].append(r["cena_m2"])
    komorki, pominiete = [], 0
    for komorka, ceny in sorted(po_komorce.items()):
        if len(ceny["a"]) < minimum or len(ceny["b"]) < minimum:
            pominiete += 1
            continue
        mediana_a, mediana_b = statistics.median(ceny["a"]), statistics.median(ceny["b"])
        komorki.append({
            "h3": komorka,
            "granica": [[round(a, 6), round(b, 6)] for a, b in h3.cell_to_boundary(komorka)],
            "liczba_a": len(ceny["a"]), "liczba_b": len(ceny["b"]),
            "mediana_a": mediana_a, "mediana_b": mediana_b,
            "zmiana_proc": 100 * (mediana_b / mediana_a - 1),
        })
    zmiany = [k["zmiana_proc"] for k in komorki]
    return {
        "rozdzielczosc": rozdzielczosc,
        "krawedz_m": krawedz_h3_m(rozdzielczosc),
        "minimum": minimum,
        "okres_a": list(okres_a),
        "okres_b": list(okres_b),
        "komorki": komorki,
        "pominiete": pominiete,
        "mediana_zmian": statistics.median(zmiany) if zmiany else None,
        "progi": PROGI_ZMIANY,
        "kolory": KOLORY_ZMIANY,
    }


# ---------- karta wyceny porównawczej do druku (ETAP 113) ----------


def mapa_wyceny_svg(wynik: dict, lat: float, lng: float, szerokosc: int = 640, wysokosc: int = 640) -> str:
    """Schemat: okrąg promienia, wskazane miejsce i podobne transakcje z
    numerami jak w tabeli karty (od najbliższej), podziałka, strzałka północy."""
    promien = wynik["promien_m"]
    margines = 36
    skala = (min(szerokosc, wysokosc) / 2 - margines) / promien  # piksele na metr
    kx = math.cos(math.radians(lat)) * 111_195

    def px(la, ln):
        return szerokosc / 2 + (ln - lng) * kx * skala, wysokosc / 2 - (la - lat) * 111_195 * skala

    czesci = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" font-family="sans-serif" font-size="11"><rect width="100%" height="100%" fill="#ffffff"/>',
              f'<circle cx="{szerokosc / 2}" cy="{wysokosc / 2}" r="{promien * skala:.1f}" fill="#0071e3" fill-opacity="0.04" stroke="#0071e3" stroke-width="1.5" stroke-dasharray="6 5"/>']
    for nr, t in reversed(list(enumerate(wynik["transakcje"], start=1))):  # najbliższe rysowane na wierzchu
        x, y = px(t["lat"], t["lng"])
        czesci.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#ff9f0a" stroke="#a33a00" stroke-width="1"/>'
                      f'<text x="{x:.1f}" y="{y + 3.5:.1f}" text-anchor="middle" font-weight="700" fill="#1d1d1f">{nr}</text>')
    srodek_x, srodek_y = szerokosc / 2, wysokosc / 2
    czesci.append(f'<path d="M{srodek_x},{srodek_y} l-7,-18 a7,7 0 1,1 14,0 z" fill="#0071e3" stroke="#ffffff" stroke-width="1.5"/>')
    _, _, krok = _ladna_os(0, promien / 2, 1)
    dlugosc = krok * skala
    opis = f"{krok / 1000:g} km".replace(".", ",") if krok >= 1000 else f"{krok:g} m"
    czesci.append(f'<path d="M{margines},{wysokosc - 18} v6 h{dlugosc:.1f} v-6" fill="none" stroke="#1d1d1f" stroke-width="1.5"/>'
                  f'<text x="{margines + dlugosc + 6:.1f}" y="{wysokosc - 12}" fill="#1d1d1f">{opis}</text>')
    x = szerokosc - margines + 10
    czesci.append(f'<path d="M{x},{margines - 22} L{x + 6},{margines - 6} L{x},{margines - 10} L{x - 6},{margines - 6} Z" fill="#1d1d1f"/><text x="{x}" y="{margines + 6}" text-anchor="middle" fill="#1d1d1f">N</text>')
    czesci.append("</svg>")
    return "".join(czesci)


# ---------- co wpływa na cenę m² — regresja liniowa (ETAP 156) ----------

MIN_TRANSAKCJI_REGRESJI = 30
UCIECIE_PROC = 1  # tyle % najniższych i najwyższych cen m² pomijamy (pomyłki w rejestrze, transakcje nierynkowe)
T_ISTOTNOSCI = 1.96  # |t| ≥ 1,96 ≈ istotne na poziomie 5% (duża próba)

# klucz → (opis efektu, jednostka efektu); kolejność = kolumny modelu
ZMIENNE_REGRESJI = {
    "czas": ("z każdym rokiem", "zł/m² na rok"),
    "pow_10m2": ("każde 10 m² powierzchni więcej", "zł/m²"),
    "kondygnacja": ("każde piętro wyżej", "zł/m²"),
    "pierwotny": ("rynek pierwotny zamiast wtórnego", "zł/m²"),
}


def _odwroc(m: list[list[float]]) -> list[list[float]]:
    """Odwrotność małej macierzy (Gauss-Jordan z wyborem elementu głównego)."""
    n = len(m)
    a = [wiersz[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, wiersz in enumerate(m)]
    for kol in range(n):
        glowny = max(range(kol, n), key=lambda w: abs(a[w][kol]))
        if abs(a[glowny][kol]) < 1e-12:
            raise ValueError("Zmienne są współliniowe — nie da się rozdzielić ich wpływu.")
        a[kol], a[glowny] = a[glowny], a[kol]
        dzielnik = a[kol][kol]
        a[kol] = [x / dzielnik for x in a[kol]]
        for w in range(n):
            if w != kol and a[w][kol]:
                mnoznik = a[w][kol]
                a[w] = [x - mnoznik * y for x, y in zip(a[w], a[kol])]
    return [wiersz[n:] for wiersz in a]


def najmniejsze_kwadraty(x: list[list[float]], y: list[float]) -> dict:
    """OLS: współczynniki, błędy standardowe, R². x — wiersze bez wyrazu wolnego."""
    wiersze = [[1.0, *w] for w in x]
    k, n = len(wiersze[0]), len(wiersze)
    xtx = [[sum(w[i] * w[j] for w in wiersze) for j in range(k)] for i in range(k)]
    xty = [sum(w[i] * yi for w, yi in zip(wiersze, y)) for i in range(k)]
    odwrotna = _odwroc(xtx)
    b = [sum(odwrotna[i][j] * xty[j] for j in range(k)) for i in range(k)]
    reszty = [yi - sum(bi * wi for bi, wi in zip(b, w)) for w, yi in zip(wiersze, y)]
    rss = sum(r * r for r in reszty)
    srednia = statistics.fmean(y)
    tss = sum((yi - srednia) ** 2 for yi in y)
    sigma2 = rss / (n - k)
    bledy = [math.sqrt(sigma2 * odwrotna[i][i]) for i in range(k)]
    return {"b": b, "se": bledy, "r2": 1 - rss / tss if tss else None, "rmse": math.sqrt(rss / n), "n": n}


def regresja_cen(lokale: list[dict]) -> dict:
    """Jak cechy transakcji wiążą się z ceną m² „przy pozostałych równych”:
    czas, powierzchnia, piętro, rynek pierwotny. Zmienne bez zróżnicowania
    w danych (np. sam rynek wtórny) są pomijane. Piętro — tylko gdy znane
    w co najmniej 80% transakcji (pozostałe wtedy pomijamy). Wynik to
    związek w danych, nie wycena i nie przyczyna."""
    rekordy = [l for l in lokale if l.get("cena_m2") and l.get("pow_m2")]
    if len(rekordy) < MIN_TRANSAKCJI_REGRESJI:
        raise ValueError(f"Za mało transakcji (potrzeba co najmniej {MIN_TRANSAKCJI_REGRESJI}).")
    ceny = sorted(l["cena_m2"] for l in rekordy)
    ile = len(ceny) * UCIECIE_PROC // 100
    dolna, gorna = ceny[ile], ceny[-ile - 1]
    pominiete_skrajne = sum(1 for l in rekordy if not dolna <= l["cena_m2"] <= gorna)
    rekordy = [l for l in rekordy if dolna <= l["cena_m2"] <= gorna]

    zmienne = ["czas", "pow_10m2"]
    ze_pietrem = [l for l in rekordy if l.get("kondygnacja") is not None]
    if len(ze_pietrem) >= 0.8 * len(rekordy) and len({l["kondygnacja"] for l in ze_pietrem}) > 1:
        zmienne.append("kondygnacja")
        rekordy = ze_pietrem
    rynki = {l["rynek"] for l in rekordy}
    if {"pierwotny", "wtórny"} <= rynki:
        zmienne.append("pierwotny")
        rekordy = [l for l in rekordy if l["rynek"] in ("pierwotny", "wtórny")]
    if len(rekordy) < MIN_TRANSAKCJI_REGRESJI:
        raise ValueError(f"Za mało transakcji z kompletem cech (potrzeba co najmniej {MIN_TRANSAKCJI_REGRESJI}).")

    poczatek = min(date.fromisoformat(l["data"]) for l in rekordy)
    def wartosc(l, z):
        if z == "czas":
            return (date.fromisoformat(l["data"]) - poczatek).days / 365.25
        if z == "pow_10m2":
            return l["pow_m2"] / 10
        if z == "kondygnacja":
            return float(l["kondygnacja"])
        return 1.0 if l["rynek"] == "pierwotny" else 0.0
    zmienne = [z for z in zmienne if len({wartosc(l, z) for l in rekordy}) > 1]
    try:
        model = najmniejsze_kwadraty([[wartosc(l, z) for z in zmienne] for l in rekordy], [l["cena_m2"] for l in rekordy])
    except ValueError as e:
        raise ValueError(str(e)) from None
    efekty = []
    for i, z in enumerate(zmienne, start=1):
        b, se = model["b"][i], model["se"][i]
        t = b / se if se else None
        efekty.append({"zmienna": z, "opis": ZMIENNE_REGRESJI[z][0], "jednostka": ZMIENNE_REGRESJI[z][1],
                       "efekt": b, "blad": se, "t": t, "istotny": t is not None and abs(t) >= T_ISTOTNOSCI})
    return {"efekty": efekty, "r2": model["r2"], "rmse": model["rmse"], "n": model["n"],
            "pominiete_skrajne": pominiete_skrajne, "od": poczatek.isoformat(), "wyraz_wolny": model["b"][0]}
