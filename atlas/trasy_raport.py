"""Raport gminy (ETAP 63): uwarunkowania jednej gminy w jednym miejscu.

Zestaw wskaźników raportu układa użytkownik z wyszukiwarki BDL (tabela
raport_wskazniki). Raport pobiera dla gminy szereg każdego wskaźnika i
wartości wszystkich gmin województwa w ostatnim roku — stąd miejsce w
województwie i mediana (atlas/raport.py). Każdy wskaźnik to osobne
zapytanie z przeglądarki: wolne API GUS nie blokuje całej strony, a błąd
jednego wskaźnika nie psuje reszty.

Funkcje z routes.py wołamy przez moduł (routes._wartosci_wskaznika),
żeby testy mogły je podmienić.
"""

from dataclasses import asdict

import os

from flask import Response, abort, jsonify, render_template, request

from dane import bdl, gemini
from dane.bdl import BladBDL

from . import baza, granice, mapa_svg, raport, routes, statystyki
from .baza import folder_modulu, z_cache
from .routes import atlas_bp


def _gminy(woj_bdl_id: str) -> list[dict]:
    return z_cache(f"gminy:{woj_bdl_id}", lambda: [asdict(j) for j in bdl.gminy_wojewodztwa(woj_bdl_id)])


def _gmina_albo_404(gmina_bdl_id: str) -> tuple[dict, dict]:
    """(gmina, województwo) albo 404; błąd BDL przechodzi dalej."""
    if len(gmina_bdl_id) != 12 or not gmina_bdl_id.isdigit():
        abort(404)
    woj_id = bdl.wojewodztwo_gminy(gmina_bdl_id)
    wojewodztwo = next((w for w in routes._wojewodztwa() if w["bdl_id"] == woj_id), None)
    gmina = next((g for g in _gminy(woj_id) if g["bdl_id"] == gmina_bdl_id), None)
    if wojewodztwo is None or gmina is None:
        abort(404)
    return gmina, wojewodztwo


def _szereg(zmienna_id: int, gmina_bdl_id: str) -> list[dict]:
    return z_cache(f"szereg:{zmienna_id}:{gmina_bdl_id}", lambda: bdl.szereg_gminy(zmienna_id, gmina_bdl_id))


def _podsumowanie(w: dict, gmina_bdl_id: str) -> dict | None:
    szereg = _szereg(w["zmienna_id"], gmina_bdl_id)
    if w["mianownik_id"]:
        szereg = statystyki.podziel_szeregi(szereg, _szereg(w["mianownik_id"], gmina_bdl_id), w["mnoznik"])
    if not szereg:
        return None
    gminy_w_roku = routes._wartosci_wskaznika(
        w["zmienna_id"], szereg[-1]["rok"], bdl.wojewodztwo_gminy(gmina_bdl_id), w["mianownik_id"], w["mnoznik"]
    )
    return raport.podsumuj(szereg, gminy_w_roku, gmina_bdl_id)


def _nazwa_wskaznika(w: dict) -> str:
    if not w["mianownik_id"]:
        return w["nazwa"]
    na = "" if w["mnoznik"] == 1 else f"{w['mnoznik']:,}".replace(",", " ") + " "
    return f"{w['nazwa']} na {na}({w['mianownik_nazwa']})"


def _wskaznik_dla_strony(w: dict) -> dict:
    return {**w, "nazwa_pelna": _nazwa_wskaznika(w)}


@atlas_bp.route("/raport-gminy")
def raport_gminy_wybor():
    return render_template("atlas/raport_wybor.html", wskazniki=[_wskaznik_dla_strony(w) for w in baza.wskazniki_raportu()])


@atlas_bp.route("/gminy/<woj_bdl_id>")
def gminy_wojewodztwa(woj_bdl_id):
    if len(woj_bdl_id) != 12 or not woj_bdl_id.isdigit():
        return jsonify({"blad": "Identyfikator województwa BDL ma 12 cyfr."}), 400
    try:
        return jsonify(_gminy(woj_bdl_id))
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502


# ---------- zestaw wskaźników ----------


@atlas_bp.route("/raport-wskazniki", methods=["POST"])
def dodaj_wskaznik_raportu():
    dane = request.get_json(silent=True) or {}
    if len(baza.wskazniki_raportu()) >= baza.MAKS_WSKAZNIKOW_RAPORTU:
        return jsonify({"blad": f"Raport może mieć najwyżej {baza.MAKS_WSKAZNIKOW_RAPORTU} wskaźników."}), 400
    try:
        zmienna_id = int(dane.get("zmienna"))
    except (TypeError, ValueError):
        return jsonify({"blad": "Wymagany parametr zmienna (liczba)."}), 400
    try:
        wzgledne = routes._parametry_wzgledne(dane, zmienna_id)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    try:
        zmienna = z_cache(f"zmienna:{zmienna_id}", lambda: asdict(bdl.pobierz_zmienna(zmienna_id)))
        mianownik = None
        if wzgledne["mianownik"] is not None:
            mid = wzgledne["mianownik"]
            mianownik = z_cache(f"zmienna:{mid}", lambda: asdict(bdl.pobierz_zmienna(mid)))
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    wskaznik_id = baza.dodaj_wskaznik_raportu(zmienna, mianownik, wzgledne["mnoznik"])
    return jsonify({"id": wskaznik_id, "wskazniki": [_wskaznik_dla_strony(w) for w in baza.wskazniki_raportu()]}), 201


@atlas_bp.route("/raport-wskazniki/<int:wskaznik_id>", methods=["DELETE"])
def usun_wskaznik_raportu(wskaznik_id):
    if not baza.usun_wskaznik_raportu(wskaznik_id):
        abort(404)
    return jsonify({"wskazniki": [_wskaznik_dla_strony(w) for w in baza.wskazniki_raportu()]})


@atlas_bp.route("/raport-wskazniki/<int:wskaznik_id>/przesun", methods=["POST"])
def przesun_wskaznik_raportu(wskaznik_id):
    o = (request.get_json(silent=True) or {}).get("o")
    if o not in (-1, 1):
        return jsonify({"blad": "o: -1 (wyżej) albo 1 (niżej)."}), 400
    if not baza.przesun_wskaznik_raportu(wskaznik_id, o):
        abort(404)
    return jsonify({"wskazniki": [_wskaznik_dla_strony(w) for w in baza.wskazniki_raportu()]})


# ---------- raport ----------


@atlas_bp.route("/raport-gminy/<gmina_bdl_id>")
def raport_gminy(gmina_bdl_id):
    try:
        gmina, wojewodztwo = _gmina_albo_404(gmina_bdl_id)
    except BladBDL as e:
        return render_template("atlas/raport_gminy.html", blad=str(e), gmina=None, wojewodztwo=None, wskazniki=[]), 502
    return render_template(
        "atlas/raport_gminy.html",
        blad=None,
        gmina=gmina,
        wojewodztwo=wojewodztwo,
        wskazniki=[_wskaznik_dla_strony(w) for w in baza.wskazniki_raportu()],
        lat_wstecz=raport.LAT_WSTECZ,
    )


@atlas_bp.route("/raport-gminy/<gmina_bdl_id>/wskaznik/<int:wskaznik_id>")
def raport_gminy_wskaznik(gmina_bdl_id, wskaznik_id):
    w = next((w for w in baza.wskazniki_raportu() if w["id"] == wskaznik_id), None)
    if w is None or len(gmina_bdl_id) != 12 or not gmina_bdl_id.isdigit():
        abort(404)
    try:
        return jsonify({"podsumowanie": _podsumowanie(w, gmina_bdl_id)})
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502


@atlas_bp.route("/raport-gminy/<gmina_bdl_id>/opis", methods=["POST"])
def raport_gminy_opis(gmina_bdl_id):
    """Charakterystyka gminy przez Gemini z faktów policzonych tutaj —
    liczb nie przyjmujemy od przeglądarki."""
    try:
        gmina, wojewodztwo = _gmina_albo_404(gmina_bdl_id)
        pozycje = [
            {"nazwa": _nazwa_wskaznika(w), "jednostka": "" if w["mianownik_id"] else w["jednostka"], "podsumowanie": _podsumowanie(w, gmina_bdl_id)}
            for w in baza.wskazniki_raportu()
        ]
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    if not any(p["podsumowanie"] for p in pozycje):
        return jsonify({"blad": "Brak danych do opisania — dodaj wskaźniki do raportu."}), 404
    fakty = raport.fakty_raportu(gmina["nazwa"], wojewodztwo["nazwa"], pozycje)
    try:
        return jsonify({"opis": gemini.opisz_gmine(fakty), "fakty": fakty})
    except gemini.BladGemini as e:
        return jsonify({"blad": str(e), "fakty": fakty}), 502


@atlas_bp.route("/raport-gminy/<gmina_bdl_id>/mapa.svg")
def raport_gminy_mapa(gmina_bdl_id):
    """Mapa położenia gminy w województwie (ETAP 73) — granice z PRG,
    z tej samej pamięci podręcznej co kartogram."""
    try:
        gmina, wojewodztwo = _gmina_albo_404(gmina_bdl_id)
        kolekcja = granice.granice_gmin(wojewodztwo["teryt"], os.path.join(folder_modulu(), "granice"))
        svg = mapa_svg.polozenie_gminy_svg(kolekcja, gmina["teryt"])
    except (BladBDL, granice.BladGranic, ValueError) as e:
        return Response(str(e), status=502, mimetype="text/plain")
    return Response(svg, mimetype="image/svg+xml")
