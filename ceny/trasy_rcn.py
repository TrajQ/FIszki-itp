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
from datetime import date

from flask import Response, abort, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup
from werkzeug.utils import secure_filename

from mpzp.uklady import w_polsce

from . import baza, rcn
from .routes import ceny_bp

RYNKI = ("pierwotny", "wtórny", "nieznany")
CO = ("lokale", "dzialki")  # ETAP 106: mieszkania albo działki z tego samego pliku


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
    if not wynik["lokale"] and not wynik["dzialki"]:
        return redirect(url_for("ceny.transakcje", blad="W pliku nie ma transakcji lokali mieszkalnych ani działek, które dałoby się policzyć."))
    plik_id = baza.zapisz_plik_rcn(nazwa, wynik["lokale"], wynik["odrzucone"], wynik["dzialki"], wynik["odrzucone_dzialki"])
    return redirect(url_for("ceny.transakcje", plik=plik_id, co="lokale" if wynik["lokale"] else "dzialki"))


@ceny_bp.route("/transakcje")
def transakcje():
    return render_template(
        "ceny/transakcje.html",
        pliki=baza.pliki_rcn(),
        do_importu=pliki_gpkg(),
        katalogi=katalogi_pobranych(),
        wybrany=request.args.get("plik", type=int),
        co=request.args.get("co") if request.args.get("co") in CO else "lokale",
        blad=request.args.get("blad"),
        rynki=RYNKI,
        maks_obszarow=rcn.MAKS_OBSZAROW,
        promienie=rcn.PROMIENIE_M,
        tolerancje=rcn.TOLERANCJE,
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


def _co() -> str:
    co = request.args.get("co") or "lokale"
    if co not in CO:
        raise ValueError("Niepoprawny rodzaj nieruchomości.")
    return co


def _filtry(co: str) -> dict:
    rynek = request.args.get("rynek") or None
    if rynek not in (None, *RYNKI):
        raise ValueError("Niepoprawny filtr.")
    filtry = {
        "rynek": rynek,
        "od_roku": request.args.get("od", type=int),
        "do_roku": request.args.get("do", type=int),
        "rodzaj": request.args.get("rodzaj") or None,
    }
    if co == "dzialki":
        filtry["przeznaczenie"] = request.args.get("przeznaczenie") or None
        filtry["nieruchomosc"] = request.args.get("nieruchomosc") or None
    else:
        filtry["izby"] = request.args.get("izby") or None
        if filtry["izby"] not in (None, "1", "2", "3", "4+"):
            raise ValueError("Niepoprawny filtr.")
    return filtry


def _rekordy(plik_id: int, co: str, filtry: dict | None = None) -> list[dict]:
    return (baza.dzialki_rcn if co == "dzialki" else baza.lokale_rcn)(plik_id, **(filtry or {}))


@ceny_bp.route("/transakcje/<int:plik_id>/dane")
def dane_transakcji(plik_id):
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        co = _co()
        filtry = _filtry(co)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    lokale = _rekordy(plik_id, co, filtry)
    wszystkie = _rekordy(plik_id, co)
    obszary = baza.obszary_rcn(plik_id)
    tabela = "rcn_dzialki" if co == "dzialki" else "rcn_lokale"
    return jsonify({
        "plik": plik,
        "co": co,
        "lata": sorted({l["rok"] for l in wszystkie}),
        "listy": {pole: baza.wartosci_pola(plik_id, pole, tabela)
                  for pole in (("rodzaj", "przeznaczenie", "nieruchomosc") if co == "dzialki" else ("rodzaj",))},
        "statystyki": rcn.statystyki(lokale),
        "mapa": rcn.punkty_mapy(lokale),
        "obszary": obszary,
        "porownanie": rcn.porownanie(lokale, obszary),
    })


# ---------- obszary do porównania (ETAP 105) ----------


def _nazwa_obszaru(tekst) -> str:
    nazwa = " ".join(str(tekst or "").split())[:60]
    if not nazwa:
        raise rcn.BladPliku("Podaj nazwę obszaru.")
    return nazwa


@ceny_bp.route("/transakcje/<int:plik_id>/obszary", methods=["POST"])
def dodaj_obszar(plik_id):
    if baza.plik_rcn(plik_id) is None:
        abort(404)
    dane = request.get_json(silent=True) or {}
    try:
        if len(baza.obszary_rcn(plik_id)) >= rcn.MAKS_OBSZAROW:
            raise rcn.BladPliku(f"Najwyżej {rcn.MAKS_OBSZAROW} obszarów — usuń któryś.")
        obszar_id = baza.dodaj_obszar_rcn(plik_id, _nazwa_obszaru(dane.get("nazwa")), rcn.sprawdz_obszar(dane.get("geometria")))
    except rcn.BladPliku as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify({"id": obszar_id}), 201


@ceny_bp.route("/transakcje/obszary/<int:obszar_id>", methods=["PUT"])
def zmien_obszar(obszar_id):
    try:
        nazwa = _nazwa_obszaru((request.get_json(silent=True) or {}).get("nazwa"))
    except rcn.BladPliku as e:
        return jsonify({"blad": str(e)}), 400
    if not baza.zmien_nazwe_obszaru(obszar_id, nazwa):
        abort(404)
    return jsonify({"ok": True})


@ceny_bp.route("/transakcje/obszary/<int:obszar_id>", methods=["DELETE"])
def usun_obszar(obszar_id):
    if not baza.usun_obszar_rcn(obszar_id):
        abort(404)
    return jsonify({"ok": True})


# ---------- raport do druku (ETAP 105) ----------


@ceny_bp.route("/transakcje/<int:plik_id>/raport")
def raport_transakcji(plik_id):
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        co = _co()
        filtry = _filtry(co)
    except ValueError:
        abort(400)
    lokale = _rekordy(plik_id, co, filtry)
    obszary = baza.obszary_rcn(plik_id)
    mapa = rcn.punkty_mapy(lokale)
    return render_template(
        "ceny/raport.html",
        plik=plik,
        co=co,
        filtry=filtry,
        statystyki=rcn.statystyki(lokale),
        porownanie=rcn.porownanie(lokale, obszary),
        mapa=Markup(rcn.mapa_svg(lokale, obszary, mapa["progi"], rcn.KOLORY_KLAS)),  # tylko liczby i kolory z kodu
        progi=mapa["progi"],
        kolory=rcn.KOLORY_KLAS,
        dzis=date.today().isoformat(),
    )


# ---------- podobne transakcje (ETAP 107) ----------


@ceny_bp.route("/transakcje/<int:plik_id>/podobne")
def podobne_transakcje(plik_id):
    """Filtry strony (rynek, lata, izby, przeznaczenie…) + miejsce i powierzchnia."""
    if baza.plik_rcn(plik_id) is None:
        abort(404)
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    pow_m2 = request.args.get("pow", type=float)
    promien = request.args.get("promien", type=int)
    tolerancja = request.args.get("tolerancja", type=float)
    try:
        co = _co()
        filtry = _filtry(co)
        if lat is None or lng is None or not w_polsce(lat, lng):
            raise ValueError("Wskaż miejsce na mapie (kliknij).")
        if pow_m2 is None or not 1 <= pow_m2 <= 2_000_000:
            raise ValueError("Podaj powierzchnię w m².")
        if promien not in rcn.PROMIENIE_M or tolerancja not in rcn.TOLERANCJE:
            raise ValueError("Niepoprawny promień albo tolerancja.")
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify(rcn.podobne(_rekordy(plik_id, co, filtry), lat, lng, promien, pow_m2, tolerancja))


@ceny_bp.route("/transakcje/<int:plik_id>.csv")
def csv_transakcji(plik_id):
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        co = _co()
        lokale = _rekordy(plik_id, co, _filtry(co))
    except ValueError:
        abort(400)
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";")
    pola = ["data", "rynek", "rodzaj", "pow_m2", "cena", "cena_m2"]
    pola += ["przeznaczenie", "uzytek", "nieruchomosc", "dzialek"] if co == "dzialki" else ["izby"]
    pola += ["lat", "lng"]
    zapis.writerow(pola)
    for l in sorted(lokale, key=lambda l: l["data"]):
        zapis.writerow([l[p] if l[p] is not None else "" for p in pola])
    zapis.writerow([])
    zapis.writerow([f"Źródło: Rejestr Cen Nieruchomości (GUGiK), plik {plik['nazwa']}. Opracowanie: Warsztat."])
    return Response(
        "﻿" + bufor.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=rcn_{co}_{plik_id}.csv"},
    )


@ceny_bp.route("/transakcje/<int:plik_id>/usun", methods=["POST"])
def usun_transakcje(plik_id):
    if not baza.usun_plik_rcn(plik_id):
        abort(404)
    return redirect(url_for("ceny.transakcje"))
