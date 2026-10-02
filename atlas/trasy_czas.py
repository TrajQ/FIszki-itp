"""Kilka gmin na jednym wykresie w czasie (ETAP 171).

Strona z wyborem do MAKS_GMIN gmin województwa i wykresem szeregów
czasowych wskaźnika (także względnego) z GUS BDL, tabelą wartości w
latach i CSV. Szeregi z tego samego cache co profil gminy.
"""

import csv
import io

from flask import Response, abort, render_template, request
from markupsafe import Markup

from dane import bdl
from dane.bdl import BladBDL

from . import statystyki
from .baza import z_cache
from .routes import _opis_zmiennej, _parametry_zapytania, _wartosci_wskaznika, _wojewodztwa, atlas_bp
from .wykres_svg import KOLORY_SERII, wykres_gmin_svg

MAKS_GMIN = len(KOLORY_SERII)


def _szereg(zmienna_id: int, gmina_bdl_id: str, mianownik: int | None, mnoznik: int) -> list[dict]:
    def surowy(zid):
        return z_cache(f"szereg:{zid}:{gmina_bdl_id}", lambda: bdl.szereg_gminy(zid, gmina_bdl_id))

    szereg = surowy(zmienna_id)
    if mianownik is not None:
        szereg = statystyki.podziel_szeregi(szereg, surowy(mianownik), mnoznik)
    return szereg


@atlas_bp.route("/gminy-w-czasie")
def gminy_w_czasie():
    try:
        p = _parametry_zapytania(request.args)
    except ValueError:
        abort(400)
    wojewodztwo = next((w for w in _wojewodztwa() if w["bdl_id"] == p["woj_bdl_id"]), None)
    if wojewodztwo is None:
        abort(404)
    try:
        zmienna = _opis_zmiennej(p["zmienna_id"], p["mianownik"], p["mnoznik"])
        gminy = sorted(_wartosci_wskaznika(p["zmienna_id"], p["rok"], p["woj_bdl_id"], p["mianownik"], p["mnoznik"]), key=lambda g: g["nazwa"])
    except BladBDL as e:
        return render_template("atlas/gminy_w_czasie.html", blad=str(e), parametry=request.args, gminy=[], wybrane=[], serie=[], lata=[],
                               zmienna=None, wojewodztwo=wojewodztwo, maks=MAKS_GMIN, wykres=None), 502
    po_id = {g["bdl_id"]: g for g in gminy}
    wybrane = list(dict.fromkeys(i for i in request.args.get("gminy", "").split(",") if i in po_id))[:MAKS_GMIN]
    serie, blad = [], None
    try:
        for i, gid in enumerate(wybrane):
            szereg = _szereg(p["zmienna_id"], gid, p["mianownik"], p["mnoznik"])
            serie.append({"gmina": po_id[gid], "szereg": szereg, "kolor": KOLORY_SERII[i], "zmiana": statystyki.zmiana_w_szeregu(szereg),
                          "po_roku": {s["rok"]: s["wartosc"] for s in szereg}})
    except BladBDL as e:
        blad = str(e)
    lata = sorted({s["rok"] for se in serie for s in se["szereg"]})
    if request.args.get("format") == "csv" and serie:
        return _csv(zmienna, serie, lata)
    parametry = {k: v for k, v in request.args.items() if k not in ("gminy", "format")}
    return render_template("atlas/gminy_w_czasie.html", blad=blad, parametry=parametry, gminy=gminy, wybrane=wybrane, serie=serie, lata=lata,
                           zmienna=zmienna, wojewodztwo=wojewodztwo, maks=MAKS_GMIN,
                           wykres=Markup(wykres_gmin_svg(serie)) if serie else None)  # tylko liczby i kolory z kodu


def _csv(zmienna: dict, serie: list[dict], lata: list[int]) -> Response:
    """Jak eksport.csv Atlasu: przecinek, liczby bez formatowania, UTF-8 z BOM."""
    bufor = io.StringIO()
    zapis = csv.writer(bufor)
    zapis.writerow(["teryt", "gmina", *(f"wartosc_{r}" for r in lata)])
    for s in serie:
        zapis.writerow([s["gmina"]["teryt"], s["gmina"]["nazwa"], *(s["po_roku"].get(r, "") for r in lata)])
    return Response(bufor.getvalue().encode("utf-8-sig"), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=atlas_gminy_w_czasie_{zmienna['id']}.csv"})
