import csv
import io
import json
import os
from dataclasses import asdict

from flask import Blueprint, Response, jsonify, render_template, request

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


@atlas_bp.route("/gmina/<gmina_bdl_id>")
def profil_gminy(gmina_bdl_id):
    """Szereg czasowy wskaźnika dla jednej gminy (wykres w profilu gminy)."""
    try:
        zmienna_id = int(request.args.get("zmienna", ""))
    except ValueError:
        return jsonify({"blad": "Wymagany parametr zmienna (liczba)."}), 400
    if len(gmina_bdl_id) != 12 or not gmina_bdl_id.isdigit():
        return jsonify({"blad": "Identyfikator gminy BDL ma 12 cyfr."}), 400

    try:
        szereg = z_cache(
            f"szereg:{zmienna_id}:{gmina_bdl_id}",
            lambda: bdl.szereg_gminy(zmienna_id, gmina_bdl_id),
        )
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify({"szereg": szereg, "zmiana": statystyki.zmiana_w_szeregu(szereg)})


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
    if "porownanie" in wynik:
        fakty += statystyki.fakty_zmiany(
            wynik["porownanie"]["rok_bazowy"], wynik["rok"], wynik["porownanie"]["statystyki"]
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

    rok_bazowy = zrodlo.get("rok_bazowy")
    if rok_bazowy in (None, ""):
        rok_bazowy = None
    else:
        try:
            rok_bazowy = int(rok_bazowy)
        except (TypeError, ValueError):
            raise ValueError("rok_bazowy musi być liczbą.")
        if rok_bazowy >= rok:
            raise ValueError("Rok bazowy musi być wcześniejszy niż rok badany.")
    return {"zmienna_id": zmienna_id, "rok": rok, "woj_bdl_id": woj, "rok_bazowy": rok_bazowy}


def _wojewodztwa() -> list[dict]:
    return z_cache("wojewodztwa", lambda: [asdict(j) for j in bdl.wojewodztwa()])


def _wartosci(zmienna_id: int, rok: int, woj_bdl_id: str) -> list[dict]:
    return z_cache(
        f"dane:{zmienna_id}:{rok}:{woj_bdl_id}",
        lambda: [asdict(w) for w in bdl.wartosci_dla_gmin(zmienna_id, rok, woj_bdl_id)],
    )


def _policz_dane(zmienna_id: int, rok: int, woj_bdl_id: str, rok_bazowy: int | None = None) -> dict:
    wojewodztwo = next((w for w in _wojewodztwa() if w["bdl_id"] == woj_bdl_id), None)
    if wojewodztwo is None:
        raise LookupError("Nie znaleziono takiego województwa w BDL.")

    zmienna = z_cache(f"zmienna:{zmienna_id}", lambda: asdict(bdl.pobierz_zmienna(zmienna_id)))
    gminy = sorted(_wartosci(zmienna_id, rok, woj_bdl_id), key=lambda g: g["wartosc"], reverse=True)

    wynik = {
        "zmienna": zmienna,
        "rok": rok,
        "wojewodztwo": wojewodztwo,
        "gminy": gminy,
        "statystyki": statystyki.statystyki(gminy),
        "progi_klas": statystyki.progi_klas([g["wartosc"] for g in gminy]),
    }
    if rok_bazowy is not None:
        porownanie = statystyki.porownaj(gminy, _wartosci(zmienna_id, rok_bazowy, woj_bdl_id))
        wynik["porownanie"] = {
            "rok_bazowy": rok_bazowy,
            "gminy": porownanie,
            "statystyki": statystyki.statystyki_zmiany(porownanie),
            "progi_zmiany_proc": statystyki.PROGI_ZMIANY_PROC,
        }
    return wynik


@atlas_bp.route("/eksport.geojson")
def eksport_geojson():
    """Kartogram do QGIS: granice gmin + wartości (i zmiana, jeśli porównanie)."""
    try:
        parametry = _parametry_zapytania(request.args)
        wynik = _policz_dane(**parametry)
        kolekcja = granice.granice_gmin(
            wynik["wojewodztwo"]["teryt"], os.path.join(folder_modulu(), "granice")
        )
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except (BladBDL, granice.BladGranic) as e:
        return jsonify({"blad": str(e)}), 502
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404

    wartosci = {g["teryt"]: g for g in wynik["gminy"]}
    zmiany = {g["teryt"]: g for g in wynik.get("porownanie", {}).get("gminy", [])}
    cechy = []
    for cecha in kolekcja["features"]:
        teryt = cecha["properties"]["teryt"]
        wlasciwosci = {
            "teryt": teryt,
            "gmina": cecha["properties"]["nazwa"],
            "wartosc": wartosci.get(teryt, {}).get("wartosc"),
            "rok": wynik["rok"],
            "wskaznik": wynik["zmienna"]["nazwa"],
            "jednostka": wynik["zmienna"]["jednostka"],
        }
        if "porownanie" in wynik:
            z = zmiany.get(teryt, {})
            wlasciwosci.update(
                rok_bazowy=wynik["porownanie"]["rok_bazowy"],
                wartosc_bazowa=z.get("wartosc_bazowa"),
                zmiana=z.get("zmiana"),
                zmiana_proc=z.get("zmiana_proc"),
            )
        cechy.append({"type": "Feature", "properties": wlasciwosci, "geometry": cecha["geometry"]})

    nazwa = f"atlas_{parametry['zmienna_id']}_{wynik['wojewodztwo']['teryt']}_{wynik['rok']}.geojson"
    return _plik_geojson({"type": "FeatureCollection", "features": cechy}, nazwa)


def _plik_geojson(kolekcja: dict, nazwa: str) -> Response:
    return Response(
        json.dumps(kolekcja, ensure_ascii=False),
        mimetype="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )


@atlas_bp.route("/eksport.csv")
def eksport_csv():
    """Tabela gmin do arkusza (UTF-8 z BOM — polskie znaki w LibreOffice/Excelu)."""
    try:
        parametry = _parametry_zapytania(request.args)
        wynik = _policz_dane(**parametry)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404

    bufor = io.StringIO()
    zapis = csv.writer(bufor)
    rok = wynik["rok"]
    if "porownanie" in wynik:
        rb = wynik["porownanie"]["rok_bazowy"]
        zapis.writerow(["teryt", "gmina", f"wartosc_{rb}", f"wartosc_{rok}", "zmiana", "zmiana_proc"])
        for g in wynik["porownanie"]["gminy"]:
            proc = "" if g["zmiana_proc"] is None else round(g["zmiana_proc"], 2)
            zapis.writerow([g["teryt"], g["nazwa"], g["wartosc_bazowa"], g["wartosc"], g["zmiana"], proc])
    else:
        zapis.writerow(["teryt", "gmina", f"wartosc_{rok}"])
        for g in wynik["gminy"]:
            zapis.writerow([g["teryt"], g["nazwa"], g["wartosc"]])

    nazwa = f"atlas_{parametry['zmienna_id']}_{wynik['wojewodztwo']['teryt']}_{rok}.csv"
    return Response(
        bufor.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )
