"""Transakcje z Rejestru Cen Nieruchomości: import pliku, statystyki, mapa (ETAP 104).

Plik GeoPackage powiatu bywa duży (setki MB w dużych miastach), a
Warsztat działa na tym samym komputerze — dlatego zamiast wgrywać go przez
przeglądarkę, można wskazać plik z katalogu Pobrane. Wgrywanie zostaje dla
mniejszych plików (limit wgrywania aplikacji). Wskazać można tylko plik
.gpkg z listy, którą pokazuje sam Warsztat (nie dowolną ścieżkę).
"""

import csv
import glob
import io
import os
import tempfile

from flask import Response, abort, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from . import baza, rcn
from .routes import ceny_bp

RYNKI = ("pierwotny", "wtórny", "nieznany")


def katalogi_pobranych() -> list[str]:
    dom = os.path.expanduser("~")
    return [os.path.join(dom, "Pobrane"), os.path.join(dom, "Downloads")]


def pliki_gpkg() -> list[dict]:
    """Pliki .gpkg w katalogach pobranych, od najnowszego."""
    pliki = [p for k in katalogi_pobranych() for p in glob.glob(os.path.join(k, "*.gpkg"))]
    return [
        {"sciezka": p, "nazwa": os.path.basename(p), "mb": round(os.path.getsize(p) / 1e6, 1)}
        for p in sorted(pliki, key=os.path.getmtime, reverse=True)
    ]


def _importuj(sciezka: str, nazwa: str):
    try:
        wynik = rcn.czytaj_plik(sciezka)
    except rcn.BladPliku as e:
        return redirect(url_for("ceny.transakcje", blad=str(e)))
    if not wynik["lokale"]:
        return redirect(url_for("ceny.transakcje", blad="W pliku nie ma transakcji lokali mieszkalnych, które dałoby się policzyć."))
    plik_id = baza.zapisz_plik_rcn(nazwa, wynik["lokale"], wynik["odrzucone"])
    return redirect(url_for("ceny.transakcje", plik=plik_id))


@ceny_bp.route("/transakcje")
def transakcje():
    return render_template(
        "ceny/transakcje.html",
        pliki=baza.pliki_rcn(),
        do_importu=pliki_gpkg(),
        katalogi=katalogi_pobranych(),
        wybrany=request.args.get("plik", type=int),
        blad=request.args.get("blad"),
        rynki=RYNKI,
    )


@ceny_bp.route("/transakcje/import", methods=["POST"])
def importuj_transakcje():
    sciezka = request.form.get("sciezka")
    if sciezka:
        # tylko plik z listy pokazanej przez Warsztat — żadnych dowolnych ścieżek
        if sciezka not in {p["sciezka"] for p in pliki_gpkg()}:
            abort(400)
        return _importuj(sciezka, os.path.basename(sciezka))
    plik = request.files.get("plik")
    if plik is None or not plik.filename.lower().endswith(".gpkg"):
        return redirect(url_for("ceny.transakcje", blad="Wybierz plik .gpkg z Rejestru Cen Nieruchomości."))
    with tempfile.TemporaryDirectory() as katalog:
        tymczasowy = os.path.join(katalog, "rcn.gpkg")
        plik.save(tymczasowy)
        return _importuj(tymczasowy, secure_filename(plik.filename) or "rcn.gpkg")


def _filtry() -> dict:
    rynek = request.args.get("rynek") or None
    izby = request.args.get("izby") or None
    if rynek not in (None, *RYNKI) or izby not in (None, "1", "2", "3", "4+"):
        raise ValueError("Niepoprawny filtr.")
    return {
        "rynek": rynek,
        "od_roku": request.args.get("od", type=int),
        "do_roku": request.args.get("do", type=int),
        "izby": izby,
        "rodzaj": request.args.get("rodzaj") or None,
    }


@ceny_bp.route("/transakcje/<int:plik_id>/dane")
def dane_transakcji(plik_id):
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        filtry = _filtry()
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    lokale = baza.lokale_rcn(plik_id, **filtry)
    wszystkie = baza.lokale_rcn(plik_id)
    return jsonify({
        "plik": plik,
        "lata": sorted({l["rok"] for l in wszystkie}),
        "rodzaje": baza.rodzaje_transakcji(plik_id),
        "statystyki": rcn.statystyki(lokale),
        "mapa": rcn.punkty_mapy(lokale),
    })


@ceny_bp.route("/transakcje/<int:plik_id>.csv")
def csv_transakcji(plik_id):
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        lokale = baza.lokale_rcn(plik_id, **_filtry())
    except ValueError:
        abort(400)
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";")
    pola = ["data", "rynek", "rodzaj", "pow_m2", "cena", "cena_m2", "izby", "lat", "lng"]
    zapis.writerow(pola)
    for l in sorted(lokale, key=lambda l: l["data"]):
        zapis.writerow([l[p] if l[p] is not None else "" for p in pola])
    zapis.writerow([])
    zapis.writerow([f"Źródło: Rejestr Cen Nieruchomości (GUGiK), plik {plik['nazwa']}. Opracowanie: Warsztat."])
    return Response(
        "﻿" + bufor.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=rcn_lokale_{plik_id}.csv"},
    )


@ceny_bp.route("/transakcje/<int:plik_id>/usun", methods=["POST"])
def usun_transakcje(plik_id):
    if not baza.usun_plik_rcn(plik_id):
        abort(404)
    return redirect(url_for("ceny.transakcje"))
