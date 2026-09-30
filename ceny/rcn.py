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
from datetime import date

from shapely import wkb
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union
from shapely.prepared import prep
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
    try:
        db = sqlite3.connect(f"file:{sciezka}?mode=ro", uri=True)
        tabele = {w[0] for w in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as e:
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


def w_obszarze(lokale: list[dict], geometria: dict) -> list[dict]:
    obszar = prep(shape(geometria))
    return [l for l in lokale if l["lat"] is not None and obszar.contains(Point(l["lng"], l["lat"]))]


def _mediany_lat(lokale: list[dict]) -> dict[int, float]:
    po_roku: dict = {}
    for l in lokale:
        po_roku.setdefault(l["rok"], []).append(l["cena_m2"])
    return {r: statistics.median(v) for r, v in sorted(po_roku.items())}


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


def mapa_svg(lokale: list[dict], obszary: list[dict], progi: list[float], kolory: list[str],
             szerokosc: int = 1000, wysokosc: int = 620) -> str:
    """Schematyczna mapa do raportu: punkty transakcji w klasach ceny i
    obrysy obszarów z numerami, podziałka i strzałka północy. Tylko liczby i
    kolory z kodu (nazwy obszarów są w legendzie raportu, nie w SVG)."""
    punkty = [(l["lng"], l["lat"], l["cena_m2"]) for l in lokale if l["lat"] is not None]
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
            {k: r.get(k) for k in ("data", "rynek", "pow_m2", "cena", "cena_m2", "izby", "przeznaczenie", "lat", "lng", "odleglosc_m")}
            for r in kandydaci[:MAKS_NA_LISCIE]
        ],
    }
