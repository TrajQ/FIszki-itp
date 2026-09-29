import os
from dataclasses import asdict

from flask import Blueprint, jsonify, render_template, request

from dane import bdl
from dane.bdl import BladBDL
from dane.gemini import BladGemini, opisz_wskaznik

from . import granice, statystyki
from .baza import folder_modulu, z_cache

atlas_bp = Blueprint(
    "atlas",
    __name__,
    template_folder="templates",
    static_folder="static",
)

MIN_DLUGOSC_FRAZY = 3


@atlas_bp.route("/")
def index():
    return render_template("atlas/index.html")


@atlas_bp.route("/zmienne")
def zmienne():
    fraza = (request.args.get("q") or "").strip()
    if len(fraza) < MIN_DLUGOSC_FRAZY:
        return jsonify({"blad": f"Wpisz co najmniej {MIN_DLUGOSC_FRAZY} znaki."}), 400
    try:
        wyniki = z_cache(
            f"zmienne:{fraza.lower()}",
            lambda: [asdict(z) for z in bdl.szukaj_zmiennych(fraza)],
        )
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify(wyniki)


@atlas_bp.route("/wojewodztwa")
def wojewodztwa():
    try:
        return jsonify(_wojewodztwa())
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502


@atlas_bp.route("/dane")
def dane():
    try:
        parametry = _parametry_zapytania(request.args)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    try:
        return jsonify(_policz_dane(**parametry))
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404


@atlas_bp.route("/granice/<teryt_woj>")
def granice_wojewodztwa(teryt_woj):
    if len(teryt_woj) != 2 or not teryt_woj.isdigit():
        return jsonify({"blad": "Kod TERYT województwa to dwie cyfry."}), 400
    try:
        kolekcja = granice.granice_gmin(teryt_woj, os.path.join(folder_modulu(), "granice"))
    except granice.BladGranic as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify(kolekcja)


@atlas_bp.route("/opis", methods=["POST"])
def opis():
    """Opis przez Gemini. Liczby liczymy tu, na serwerze, z danych BDL —
    nie przyjmujemy ich od przeglądarki."""
    try:
        parametry = _parametry_zapytania(request.get_json(silent=True) or {})
        wynik = _policz_dane(**parametry)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404

    if wynik["statystyki"]["liczba_gmin"] == 0:
        return jsonify({"blad": "Brak danych do opisania."}), 404

    fakty = statystyki.fakty_do_opisu(
        wynik["zmienna"], wynik["rok"], wynik["wojewodztwo"]["nazwa"], wynik["statystyki"]
    )
    try:
        tekst = opisz_wskaznik(fakty)
    except BladGemini as e:
        return jsonify({"blad": str(e), "fakty": fakty}), 502
    return jsonify({"opis": tekst, "fakty": fakty})


def _parametry_zapytania(zrodlo) -> dict:
    try:
        zmienna_id = int(zrodlo.get("zmienna"))
        rok = int(zrodlo.get("rok"))
    except (TypeError, ValueError):
        raise ValueError("Wymagane parametry: zmienna (liczba) i rok (liczba).")
    woj = str(zrodlo.get("woj") or "")
    if len(woj) != 12 or not woj.isdigit():
        raise ValueError("Parametr woj musi być 12-cyfrowym identyfikatorem BDL województwa.")
    if not 1995 <= rok <= 2100:
        raise ValueError("Niepoprawny rok.")
    return {"zmienna_id": zmienna_id, "rok": rok, "woj_bdl_id": woj}


def _wojewodztwa() -> list[dict]:
    return z_cache("wojewodztwa", lambda: [asdict(j) for j in bdl.wojewodztwa()])


def _policz_dane(zmienna_id: int, rok: int, woj_bdl_id: str) -> dict:
    wojewodztwo = next((w for w in _wojewodztwa() if w["bdl_id"] == woj_bdl_id), None)
    if wojewodztwo is None:
        raise LookupError("Nie znaleziono takiego województwa w BDL.")

    zmienna = z_cache(f"zmienna:{zmienna_id}", lambda: asdict(bdl.pobierz_zmienna(zmienna_id)))
    gminy = z_cache(
        f"dane:{zmienna_id}:{rok}:{woj_bdl_id}",
        lambda: [asdict(w) for w in bdl.wartosci_dla_gmin(zmienna_id, rok, woj_bdl_id)],
    )
    gminy = sorted(gminy, key=lambda g: g["wartosc"], reverse=True)

    return {
        "zmienna": zmienna,
        "rok": rok,
        "wojewodztwo": wojewodztwo,
        "gminy": gminy,
        "statystyki": statystyki.statystyki(gminy),
        "progi_klas": statystyki.progi_klas([g["wartosc"] for g in gminy]),
    }
