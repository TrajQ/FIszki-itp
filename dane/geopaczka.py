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

import os
import sqlite3
import struct
import tempfile
from datetime import datetime, timezone

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
                kolumny = "".join(f', "{k}" {t}' for k, t in w["kolumny"])
                db.execute(f'CREATE TABLE "{w["nazwa"]}" (fid INTEGER PRIMARY KEY AUTOINCREMENT, geom {w["typ"]}{kolumny})')
                nazwy = [k for k, _ in w["kolumny"]]
                lista_kolumn = ", ".join(["geom", *(f'"{k}"' for k in nazwy)])
                znaki = ", ".join("?" * (len(nazwy) + 1))
                for geometria, atrybuty in w["obiekty"]:
                    db.execute(f'INSERT INTO "{w["nazwa"]}" ({lista_kolumn}) VALUES ({znaki})',
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
