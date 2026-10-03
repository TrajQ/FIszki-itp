"""Zapis GeoPackage (.gpkg) bez zależności (ETAP 213).

GeoPackage (standard OGC) to baza SQLite z umówionymi tabelami — Python
ma sqlite3, więc plik da się zapisać tak jak DXF (D-130) i ODS (D-196),
bez GDAL-a. QGIS otwiera go przeciągnięciem; style zapisane w tabeli
`layer_styles` (rozszerzenie używane przez QGIS) wczytuje jako domyślne.

Zawartość pliku:
- gpkg_spatial_ref_sys — układy (wymagane: -1, 0, 4326) i układ warstw,
- gpkg_contents, gpkg_geometry_columns — opis warstw,
- tabela na warstwę: fid, geom (nagłówek „GP” + WKB), atrybuty,
- layer_styles — styl QML każdej warstwy (opcjonalnie).

Geometria w blobie: nagłówek GeoPackage (wersja 0, little endian,
obwiednia XY) i WKB 2D.
"""

import colorsys
import os
import re
import sqlite3
import struct
import tempfile
from datetime import datetime, timezone
from xml.sax.saxutils import quoteattr

import shapely

# Układy, których używamy: EPSG → (nazwa, definicja WKT)
UKLADY = {
    4326: ("WGS 84", 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],'
                     'UNIT["degree",0.0174532925199433],AUTHORITY["EPSG","4326"]]'),
    2180: ("ETRF2000-PL / CS92", 'PROJCS["ETRF2000-PL / CS92",GEOGCS["ETRF2000-PL",DATUM["ETRF2000_Poland",'
                                 'SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
                                 'PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",19],'
                                 'PARAMETER["scale_factor",0.9993],PARAMETER["false_easting",500000],PARAMETER["false_northing",-5300000],'
                                 'UNIT["metre",1],AUTHORITY["EPSG","2180"]]'),
}
TYPY_GEOMETRII = ("POINT", "LINESTRING", "POLYGON", "MULTIPOINT", "MULTILINESTRING", "MULTIPOLYGON", "GEOMETRY")
TYPY_KOLUMN = ("TEXT", "INTEGER", "REAL")


def _id(nazwa: str) -> str:
    """Nazwa tabeli albo kolumny w cudzysłowie SQL (nazwy pól Terenu wpisuje użytkownik)."""
    return '"' + str(nazwa).replace('"', '""') + '"'


def blob_geometrii(geometria, srs_id: int) -> bytes:
    """Geometria shapely → blob GeoPackage (nagłówek z obwiednią + WKB little endian)."""
    minx, miny, maxx, maxy = geometria.bounds
    naglowek = b"GP" + bytes([0, 0b0000_0011]) + struct.pack("<i", srs_id) + struct.pack("<4d", minx, maxx, miny, maxy)
    return naglowek + shapely.to_wkb(geometria, byte_order=1, output_dimension=2)


def geopackage(warstwy: list[dict], srs_id: int) -> bytes:
    """warstwy: [{"nazwa", "typ" (TYPY_GEOMETRII), "kolumny": [(nazwa, TEXT|INTEGER|REAL)],
    "obiekty": [(geometria shapely, {kolumna: wartość})], "opis"?, "styl_qml"?}] → bajty pliku."""
    if srs_id not in UKLADY:
        raise ValueError(f"Nieobsługiwany układ EPSG:{srs_id}.")
    teraz = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    with tempfile.TemporaryDirectory() as katalog:
        sciezka = os.path.join(katalog, "plik.gpkg")
        db = sqlite3.connect(sciezka)
        try:
            db.execute("PRAGMA application_id = 1196444487")  # „GPKG”
            db.execute("PRAGMA user_version = 10400")  # GeoPackage 1.4
            db.executescript("""
                CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT NOT NULL, srs_id INTEGER PRIMARY KEY, organization TEXT NOT NULL,
                    organization_coordsys_id INTEGER NOT NULL, definition TEXT NOT NULL, description TEXT);
                CREATE TABLE gpkg_contents (table_name TEXT NOT NULL PRIMARY KEY, data_type TEXT NOT NULL, identifier TEXT UNIQUE,
                    description TEXT DEFAULT '', last_change DATETIME NOT NULL, min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE,
                    srs_id INTEGER REFERENCES gpkg_spatial_ref_sys(srs_id));
                CREATE TABLE gpkg_geometry_columns (table_name TEXT NOT NULL, column_name TEXT NOT NULL, geometry_type_name TEXT NOT NULL,
                    srs_id INTEGER NOT NULL, z TINYINT NOT NULL, m TINYINT NOT NULL, PRIMARY KEY (table_name, column_name));
            """)
            db.executemany("INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?, ?)", [
                ("Undefined cartesian SRS", -1, "NONE", -1, "undefined", None),
                ("Undefined geographic SRS", 0, "NONE", 0, "undefined", None),
                *[(nazwa, epsg, "EPSG", epsg, wkt, None) for epsg, (nazwa, wkt) in UKLADY.items()],
            ])
            style = []
            for w in warstwy:
                if w["typ"] not in TYPY_GEOMETRII or any(t not in TYPY_KOLUMN for _, t in w["kolumny"]):
                    raise ValueError(f"Warstwa {w['nazwa']}: nieznany typ geometrii albo kolumny.")
                kolumny = "".join(f", {_id(k)} {t}" for k, t in w["kolumny"])
                db.execute(f"CREATE TABLE {_id(w['nazwa'])} (fid INTEGER PRIMARY KEY AUTOINCREMENT, geom {w['typ']}{kolumny})")
                nazwy = [k for k, _ in w["kolumny"]]
                lista_kolumn = ", ".join(["geom", *(_id(k) for k in nazwy)])
                znaki = ", ".join("?" * (len(nazwy) + 1))
                for geometria, atrybuty in w["obiekty"]:
                    db.execute(f"INSERT INTO {_id(w['nazwa'])} ({lista_kolumn}) VALUES ({znaki})",
                               [blob_geometrii(geometria, srs_id), *[atrybuty.get(k) for k in nazwy]])
                obwiednia = shapely.total_bounds([g for g, _ in w["obiekty"]]) if w["obiekty"] else [None] * 4
                db.execute("INSERT INTO gpkg_contents VALUES (?, 'features', ?, ?, ?, ?, ?, ?, ?, ?)",
                           (w["nazwa"], w["nazwa"], w.get("opis", ""), teraz, *[None if v is None else float(v) for v in obwiednia], srs_id))
                db.execute("INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', ?, ?, 0, 0)", (w["nazwa"], w["typ"], srs_id))
                if w.get("styl_qml"):
                    style.append((w["nazwa"], w["styl_qml"]))
            if style:
                db.execute("""CREATE TABLE layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT(256),
                    f_table_schema TEXT(256), f_table_name TEXT(256), f_geometry_column TEXT(256), styleName TEXT(30), styleQML TEXT,
                    styleSLD TEXT, useAsDefault BOOLEAN, description TEXT, owner TEXT(30), ui TEXT(30), update_time DATETIME)""")
                db.executemany("INSERT INTO layer_styles (f_table_catalog, f_table_schema, f_table_name, f_geometry_column, styleName, "
                               "styleQML, styleSLD, useAsDefault, description, owner, update_time) VALUES ('', '', ?, 'geom', ?, ?, '', 1, "
                               "'Warsztat', '', ?)", [(t, t, qml, teraz) for t, qml in style])
                db.execute("INSERT INTO gpkg_contents (table_name, data_type, identifier, last_change) VALUES "
                           "('layer_styles', 'attributes', 'layer_styles', ?)", (teraz,))
            db.commit()
        finally:
            db.close()
        with open(sciezka, "rb") as plik:
            return plik.read()


# ---------- style QGIS (QML) do tabeli layer_styles ----------
# Małe klocki XML-a stylu: symbol (wypełnienie, linia, punkt) i renderer
# (jeden symbol, kategorie po wartości, przedziały liczby). Tekst wartości
# i etykiet przechodzi przez quoteattr.

_HSL = re.compile(r"hsl\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*\)")


def kolor_qml(kolor: str, alfa: int = 255) -> str:
    """„#rrggbb” albo „hsl(h, s%, l%)” → „r,g,b,a” jak w QML; pusty — przezroczysty."""
    if not kolor:
        return "0,0,0,0"
    m = _HSL.fullmatch(kolor.strip())
    if m:
        r, g, b = colorsys.hls_to_rgb(float(m.group(1)) / 360, float(m.group(3)) / 100, float(m.group(2)) / 100)
        return f"{round(r * 255)},{round(g * 255)},{round(b * 255)},{alfa}"
    k = kolor.lstrip("#")
    return f"{int(k[0:2], 16)},{int(k[2:4], 16)},{int(k[4:6], 16)},{alfa}"


def _opcje(**wartosci) -> str:
    return '<Option type="Map">' + "".join(f'<Option type="QString" name="{k}" value={quoteattr(str(v))}/>' for k, v in wartosci.items()) + "</Option>"


def symbol_wypelnienia(kolor: str, alfa: int = 170, obrys: str = "#232323", szerokosc_obrysu: float = 0.26) -> tuple[str, str]:
    warstwa = ('<layer class="SimpleFill" enabled="1" locked="0" pass="0">'
               + _opcje(color=kolor_qml(kolor, alfa), style="solid" if kolor else "no", outline_color=kolor_qml(obrys),
                        outline_width=szerokosc_obrysu, outline_width_unit="MM") + "</layer>")
    return "fill", warstwa


def symbol_linii(kolor: str, szerokosc: float = 0.6, styl: str = "solid") -> tuple[str, str]:
    warstwa = ('<layer class="SimpleLine" enabled="1" locked="0" pass="0">'
               + _opcje(line_color=kolor_qml(kolor), line_width=szerokosc, line_width_unit="MM", line_style=styl) + "</layer>")
    return "line", warstwa


def symbol_punktu(kolor: str, rozmiar: float = 2.6) -> tuple[str, str]:
    warstwa = ('<layer class="SimpleMarker" enabled="1" locked="0" pass="0">'
               + _opcje(name="circle", color=kolor_qml(kolor), outline_color="255,255,255,255", outline_width=0.3,
                        outline_width_unit="MM", size=rozmiar, size_unit="MM") + "</layer>")
    return "marker", warstwa


def _symbole(symbole: list[tuple[str, str]]) -> str:
    return "<symbols>" + "".join(f'<symbol type="{typ}" name="{i}" alpha="1" clip_to_extent="1" force_rhr="0">{warstwa}</symbol>'
                                 for i, (typ, warstwa) in enumerate(symbole)) + "</symbols>"


def _qml(renderer: str) -> str:
    return f"<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'><qgis version=\"3.28.0\" styleCategories=\"Symbology\">{renderer}</qgis>"


def styl_pojedynczy(symbol: tuple[str, str]) -> str:
    return _qml(f'<renderer-v2 type="singleSymbol" symbollevels="0" enableorderby="0" forceraster="0">{_symbole([symbol])}</renderer-v2>')


def styl_kategorie(kolumna: str, kategorie: list[tuple[str, str, tuple[str, str]]]) -> str:
    """kategorie: [(wartość, etykieta, symbol)] — kolor wg wartości kolumny."""
    wpisy = "".join(f'<category render="true" symbol="{i}" value={quoteattr(str(w))} label={quoteattr(e)}/>'
                    for i, (w, e, _) in enumerate(kategorie))
    return _qml(f'<renderer-v2 type="categorizedSymbol" attr={quoteattr(kolumna)} symbollevels="0" enableorderby="0" forceraster="0">'
                f"<categories>{wpisy}</categories>{_symbole([s for _, _, s in kategorie])}</renderer-v2>")


def styl_przedzialy(kolumna: str, przedzialy: list[tuple[float, float, str, tuple[str, str]]]) -> str:
    """przedzialy: [(od, do, etykieta, symbol)] — kolor wg przedziału liczby."""
    wpisy = "".join(f'<range render="true" symbol="{i}" lower="{od:.6f}" upper="{do:.6f}" label={quoteattr(e)}/>'
                    for i, (od, do, e, _) in enumerate(przedzialy))
    return _qml(f'<renderer-v2 type="graduatedSymbol" attr={quoteattr(kolumna)} graduatedMethod="GraduatedColor" symbollevels="0" '
                f'enableorderby="0" forceraster="0"><ranges>{wpisy}</ranges>{_symbole([s for *_, s in przedzialy])}</renderer-v2>')
