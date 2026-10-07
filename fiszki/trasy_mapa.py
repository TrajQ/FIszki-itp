"""Trasy fiszek „gdzie to jest” i quizu z mapą (ETAP 248).

Rejestrują się na fiszki_bp (import na końcu fiszki/routes.py).
"""

import random

from flask import abort, jsonify, render_template, request

from . import miejsca
from .baza import get_db
from .routes import _pobierz_pdf_albo_404, _wstaw_fiszke, fiszki_bp

FRAGMENT_MAPY = "(fiszka z mapy)"  # fragment_tekstu jest wymagany; miejsce zamiast cytatu z PDF


@fiszki_bp.route("/mapa")
def mapa_fiszek():
    db = get_db()
    pliki = [dict(w) for w in db.execute("SELECT id, nazwa_oryginalna FROM pdfy ORDER BY id DESC")]
    return render_template("fiszki/mapa.html", pliki=pliki, fiszki=miejsca.lista(db), promienie=miejsca.PROMIENIE_M,
                           promien_domyslny=miejsca.PROMIEN_DOMYSLNY_M)


@fiszki_bp.route("/mapa/fiszki", methods=["POST"])
def zapisz_fiszke_z_miejscem():
    dane = request.get_json(silent=True) or {}
    pdf_id = dane.get("pdf_id")
    if not isinstance(pdf_id, int):
        return jsonify({"blad": "Wybierz plik, do którego trafi fiszka."}), 400
    _pobierz_pdf_albo_404(pdf_id)
    pytanie = " ".join(str(dane.get("pytanie") or "").split())[:500]
    odpowiedz = " ".join(str(dane.get("odpowiedz") or "").split())[:500]
    if not pytanie or not odpowiedz:
        return jsonify({"blad": "Wpisz pytanie i odpowiedź (nazwę miejsca)."}), 400
    try:
        lat, lng, promien = miejsca.sprawdz(dane.get("lat"), dane.get("lng"), dane.get("promien_m", miejsca.PROMIEN_DOMYSLNY_M))
    except miejsca.BladMiejsca as e:
        return jsonify({"blad": str(e)}), 400
    db = get_db()
    fiszka_id = _wstaw_fiszke(db, pdf_id, 1, FRAGMENT_MAPY, pytanie, odpowiedz, [])
    miejsca.zapisz(db, fiszka_id, lat, lng, promien)
    db.commit()
    return jsonify({"id": fiszka_id, "pytanie": pytanie, "odpowiedz": odpowiedz, "lat": lat, "lng": lng, "promien_m": promien}), 201


@fiszki_bp.route("/mapa/quiz")
def quiz_z_mapa():
    return render_template("fiszki/quiz_mapa.html", pdf_id=request.args.get("pdf", type=int))


@fiszki_bp.route("/mapa/quiz/pytania")
def pytania_quizu_z_mapa():
    """Pytania bez odpowiedzi (miejsce zna tylko serwer) w losowej kolejności."""
    lista = miejsca.lista(get_db(), request.args.get("pdf", type=int))
    random.shuffle(lista)
    return jsonify([{"id": f["id"], "pytanie": f["pytanie"]} for f in lista[: miejsca.MAKS_W_QUIZIE]])


@fiszki_bp.route("/mapa/quiz/<int:fiszka_id>", methods=["POST"])
def odpowiedz_quizu_z_mapa(fiszka_id):
    db = get_db()
    miejsce = miejsca.miejsce(db, fiszka_id)
    if miejsce is None:
        abort(404)
    dane = request.get_json(silent=True) or {}
    try:
        lat, lng, _ = miejsca.sprawdz(dane.get("lat"), dane.get("lng"), miejsce["promien_m"])
    except miejsca.BladMiejsca as e:
        return jsonify({"blad": str(e)}), 400
    fiszka = db.execute("SELECT odpowiedz FROM fiszki WHERE id = ?", (fiszka_id,)).fetchone()
    return jsonify({**miejsca.ocen(miejsce, lat, lng), "odpowiedz": fiszka["odpowiedz"]})
