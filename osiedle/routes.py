"""Moduł osiedle: koncepcje osiedla rysowane na mapie i ich bilans terenu."""

import json

from flask import Blueprint, Response, abort, jsonify, render_template, request
from werkzeug.utils import secure_filename

from . import baza
from .bilans import FUNKCJE, OBSZAR, BladKoncepcji, bilans

osiedle_bp = Blueprint(
    "osiedle",
    __name__,
    template_folder="templates",
    static_folder="static",
)

MAKS_DLUGOSC_NAZWY = 80


def _koncepcja_albo_404(koncepcja_id: int) -> dict:
    koncepcja = baza.pobierz(koncepcja_id)
    if koncepcja is None:
        abort(404)
    return koncepcja


def _nazwa(tekst) -> str:
    nazwa = " ".join(str(tekst or "").split())
    if not nazwa:
        raise BladKoncepcji("Podaj nazwę koncepcji, np. „Osiedle Jeżyce — wariant A”.")
    if len(nazwa) > MAKS_DLUGOSC_NAZWY:
        raise BladKoncepcji(f"Nazwa może mieć najwyżej {MAKS_DLUGOSC_NAZWY} znaków.")
    return nazwa


def podsumowanie() -> dict:
    """Liczba koncepcji — na kartę modułu na stronie głównej."""
    koncepcje = baza.lista()
    return {"liczba": len(koncepcje), "ostatnia": koncepcje[0]["nazwa"] if koncepcje else None}


@osiedle_bp.route("/")
def index():
    return render_template("osiedle/index.html", funkcje=FUNKCJE, obszar=OBSZAR)


@osiedle_bp.route("/koncepcje")
def lista_koncepcji():
    return jsonify(baza.lista())


@osiedle_bp.route("/koncepcje", methods=["POST"])
def nowa_koncepcja():
    dane = request.get_json(silent=True) or {}
    try:
        koncepcja_id = baza.utworz(_nazwa(dane.get("nazwa")))
    except BladKoncepcji as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify(baza.pobierz(koncepcja_id)), 201


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>")
def koncepcja(koncepcja_id):
    k = _koncepcja_albo_404(koncepcja_id)
    return jsonify({**k, "bilans": bilans(k["geojson"])})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>", methods=["PUT"])
def zapisz_koncepcje(koncepcja_id):
    """Zapis nazwy, rysunku albo ustawień; zwraca świeży bilans."""
    _koncepcja_albo_404(koncepcja_id)
    dane = request.get_json(silent=True) or {}
    try:
        nazwa = _nazwa(dane["nazwa"]) if "nazwa" in dane else None
        geojson = dane.get("geojson")
        wynik = bilans(geojson) if geojson is not None else None  # walidacja przed zapisem
        ustawienia = dane.get("ustawienia")
        if ustawienia is not None and not isinstance(ustawienia, dict):
            raise BladKoncepcji("Ustawienia muszą być obiektem.")
    except BladKoncepcji as e:
        return jsonify({"blad": str(e)}), 400
    baza.zapisz(koncepcja_id, nazwa, geojson, ustawienia)
    k = baza.pobierz(koncepcja_id)
    return jsonify({**k, "bilans": wynik or bilans(k["geojson"])})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>", methods=["DELETE"])
def usun_koncepcje(koncepcja_id):
    _koncepcja_albo_404(koncepcja_id)
    baza.usun(koncepcja_id)
    return jsonify({"ok": True})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>.geojson")
def eksport_geojson(koncepcja_id):
    """Rysunek koncepcji do QGIS (funkcja jako atrybut)."""
    k = _koncepcja_albo_404(koncepcja_id)
    for cecha in k["geojson"]["features"]:
        funkcja = (cecha.get("properties") or {}).get("funkcja")
        if funkcja in FUNKCJE:
            cecha["properties"]["nazwa_funkcji"] = FUNKCJE[funkcja]["nazwa"]
    nazwa = secure_filename(f"koncepcja_{k['id']}_{k['nazwa']}.geojson") or "koncepcja.geojson"
    return Response(
        json.dumps(k["geojson"], ensure_ascii=False),
        mimetype="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )
