"""Fiszki na telefon bez internetu (ETAP 74): eksport pliku HTML i import
wyników powtórek. Logika w fiszki/telefon.py."""

import json
import time

from flask import Response, jsonify, render_template, request

from . import powtorki, telefon
from .baza import get_db
from .routes import _temat_z_zapytania, fiszki_bp


@fiszki_bp.route("/telefon.html")
def fiszki_na_telefon():
    db = get_db()
    temat = _temat_z_zapytania()
    pdf_id = request.args.get("pdf_id", type=int)
    fiszki = telefon.fiszki_do_eksportu(db, powtorki.dzisiaj(), temat, pdf_id)
    if not fiszki:
        return Response("Brak fiszek w wybranym zakresie.", status=404, mimetype="text/plain")
    zakres = temat or (fiszki[0]["zrodlo"] if pdf_id is not None else "wszystkie fiszki")
    html = render_template(
        "fiszki/telefon.html",
        fiszki=fiszki,
        zakres=zakres,
        zasady=telefon.zasady(),
        instalacja=telefon.identyfikator_instalacji(db),
        format_pliku=telefon.FORMAT,
        wygenerowano_ms=int(time.time() * 1000),
    )
    return Response(html, mimetype="text/html", headers={"Content-Disposition": "attachment; filename=fiszki_na_telefon.html"})


@fiszki_bp.route("/telefon/import", methods=["POST"])
def import_z_telefonu():
    plik = request.files.get("plik")
    if plik is None or not plik.filename:
        return jsonify({"blad": "Nie wybrano pliku."}), 400
    try:
        dane = json.loads(plik.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"blad": "To nie jest plik JSON z powtórek na telefonie."}), 400
    db = get_db()
    try:
        wyniki = telefon.odczytaj_wyniki(dane, telefon.identyfikator_instalacji(db), powtorki.dzisiaj())
    except telefon.BladPliku as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify(telefon.zastosuj(db, wyniki))
