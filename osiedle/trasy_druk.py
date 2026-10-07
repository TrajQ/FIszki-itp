"""Raport koncepcji do druku, szkic SVG i porównanie wariantów (ETAP 60)."""

from flask import Response, abort, jsonify, render_template, request
from markupsafe import Markup
from werkzeug.utils import secure_filename

from . import baza, cien, przekroj
from .dxf_koncepcji import UKLADY, koncepcja_dxf
from .bilans import FUNKCJE, OBSZAR, BladKoncepcji, bilans
from .program import ZALOZENIA
from .routes import _koncepcja_albo_404, osiedle_bp
from .rysunek_svg import skala_dla, szkic_svg
from .wskazniki import USTALENIA, BladParametru

MAKS_WARIANTOW = 4


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>/raport")
def raport(koncepcja_id):
    k = _koncepcja_albo_404(koncepcja_id)
    # ETAP 100: odległości i strefa cienia (?cien=rownonoc|zima|lato|nie; domyślnie równonoc)
    dzien = request.args.get("cien", "rownonoc")
    analiza_cienia = cien.analiza(k["geojson"], dzien) if dzien in cien.DNI else None
    if analiza_cienia is not None and not analiza_cienia["tereny"]:
        analiza_cienia = None  # bez terenów zabudowy nie ma czego pokazać
    return render_template(
        "osiedle/raport.html",
        k=k,
        b=bilans(k["geojson"], k["ustawienia"]),
        szkic=Markup(szkic_svg(  # tylko liczby i kolory z kodu
            k["geojson"], 1000, 620,
            strefa_cienia=analiza_cienia["strefa"] if analiza_cienia else None,
            numery=analiza_cienia is not None,
        )),
        cien=analiza_cienia,
        przekroj=_przekroj_do_raportu(k),
        dzien_cienia=dzien,
        dni_cienia=cien.DNI,
        funkcje=FUNKCJE,
        ustalenia=USTALENIA,
        zalozenia=ZALOZENIA,
        # ETAP 115: ceny w okolicy obszaru opracowania (moduł ceny); bez obszaru — sekcji nie ma
        geometria_okolicy=next((f["geometry"] for f in k["geojson"].get("features", []) if f["properties"].get("funkcja") == OBSZAR), None),
    )


def _przekroj_do_raportu(k: dict) -> dict | None:
    """ETAP 238: przekrój w raporcie, gdy są budynki (?przekroj_kat=&przekroj_przes=
    — te same wartości co na stronie koncepcji); bez budynków — None."""
    try:
        kat = float(request.args.get("przekroj_kat", 90))
        przes = float(request.args.get("przekroj_przes", 0))
        p = przekroj.przekroj(k["geojson"], kat, przes, k["ustawienia"])
    except (ValueError, BladKoncepcji, BladParametru):
        return None
    if not p["budynki"]:
        return None
    return {"dane": p, "svg": Markup(przekroj.przekroj_svg(p))}  # tylko liczby i kolory z kodu


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>.svg")
def szkic(koncepcja_id):
    k = _koncepcja_albo_404(koncepcja_id)
    nazwa = secure_filename(f"koncepcja_{k['id']}_{k['nazwa']}.svg") or "koncepcja.svg"
    return Response(
        szkic_svg(k["geojson"], 1000, 620),
        mimetype="image/svg+xml",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>.dxf")
def dxf_koncepcji(koncepcja_id):
    """ETAP 122: koncepcja do programu CAD (?uklad=pl2000 domyślnie albo pl1992)."""
    k = _koncepcja_albo_404(koncepcja_id)
    uklad = request.args.get("uklad", "pl2000")
    if uklad not in UKLADY:
        abort(400)
    tekst, opis_ukladu = koncepcja_dxf(k["geojson"], uklad)
    nazwa = secure_filename(f"koncepcja_{k['id']}_{k['nazwa']}_{uklad}.dxf") or "koncepcja.dxf"
    return Response(tekst, mimetype="application/dxf",
                    headers={"Content-Disposition": f"attachment; filename={nazwa}", "X-Uklad-Wspolrzednych": opis_ukladu})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>.gpkg")
def gpkg_koncepcji(koncepcja_id):
    """ETAP 213: koncepcja jako GeoPackage dla QGIS — warstwy w PL-1992 ze stylami."""
    from .gpkg_koncepcji import koncepcja_gpkg

    k = _koncepcja_albo_404(koncepcja_id)
    nazwa = secure_filename(f"koncepcja_{k['id']}_{k['nazwa']}.gpkg") or "koncepcja.gpkg"
    return Response(koncepcja_gpkg(k["geojson"], k["nazwa"]), mimetype="application/geopackage+sqlite3",
                    headers={"Content-Disposition": f"attachment; filename={nazwa}"})


@osiedle_bp.route("/porownanie")
def porownanie():
    """Warianty obok siebie: bilans, wskaźniki, program, szkice w jednej skali."""
    wszystkie = baza.lista()
    wybrane = []
    for tekst in request.args.getlist("id")[:MAKS_WARIANTOW]:
        if tekst.isdigit() and (k := baza.pobierz(int(tekst))) is not None:
            wybrane.append(k)
    warianty = []
    if len(wybrane) >= 2:
        skala = skala_dla([k["geojson"] for k in wybrane], 360, 260)
        for k in wybrane:
            warianty.append(
                {
                    "k": k,
                    "b": bilans(k["geojson"], k["ustawienia"]),
                    "szkic": Markup(szkic_svg(k["geojson"], 360, 260, skala)),
                }
            )
    # funkcje obecne w którymkolwiek wariancie, w kolejności z FUNKCJE
    obecne = {f["funkcja"] for w in warianty for f in w["b"]["funkcje"]}
    return render_template(
        "osiedle/porownanie.html",
        wszystkie=wszystkie,
        wybrane_id=[k["id"] for k in wybrane],
        warianty=warianty,
        funkcje=[(kod, f) for kod, f in FUNKCJE.items() if kod in obecne],
        maks=MAKS_WARIANTOW,
    )


# ---------- ETAP 238: przekrój terenu z wysokością budynków ----------


def _parametry_przekroju() -> tuple[float, float]:
    try:
        kat = float(request.args.get("kat", 90))
        przesuniecie = float(request.args.get("przesuniecie", 0))
    except ValueError:
        abort(400)
    return kat, przesuniecie


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>/przekroj")
def przekroj_koncepcji(koncepcja_id):
    """Liczby przekroju (budynki, tereny, odstępy) i linia A–A′ do mapy."""
    k = _koncepcja_albo_404(koncepcja_id)
    try:
        return jsonify(przekroj.przekroj(k["geojson"], *_parametry_przekroju(), k["ustawienia"]))
    except (przekroj.BladPrzekroju, BladKoncepcji, BladParametru) as e:
        return jsonify({"blad": str(e)}), 400


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>/przekroj.svg")
def przekroj_svg(koncepcja_id):
    k = _koncepcja_albo_404(koncepcja_id)
    try:
        p = przekroj.przekroj(k["geojson"], *_parametry_przekroju(), k["ustawienia"])
    except (przekroj.BladPrzekroju, BladKoncepcji, BladParametru) as e:
        return jsonify({"blad": str(e)}), 400
    naglowki = {}
    if request.args.get("pobierz"):
        nazwa = secure_filename(f"przekroj_{k['id']}_{k['nazwa']}.svg") or "przekroj.svg"
        naglowki["Content-Disposition"] = f"attachment; filename={nazwa}"
    return Response(przekroj.przekroj_svg(p), mimetype="image/svg+xml", headers=naglowki)
