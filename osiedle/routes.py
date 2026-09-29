"""Moduł osiedle: koncepcje osiedla rysowane na mapie i ich bilans terenu."""

import json

from flask import Blueprint, Response, abort, jsonify, render_template, request
from shapely.geometry import mapping
from shapely.ops import unary_union
from werkzeug.utils import secure_filename

from dane import uldk

from . import baza
from .bilans import FUNKCJE, OBSZAR, BladKoncepcji, bilans
from .program import ZALOZENIA
from .wskazniki import DOMYSLNE

osiedle_bp = Blueprint(
    "osiedle",
    __name__,
    template_folder="templates",
    static_folder="static",
)

MAKS_DLUGOSC_NAZWY = 80
MAKS_DZIALEK = 50

# Na poziomie modułu, żeby testy mogły podmienić usługę ULDK.
znajdz_dzialke_po_id = uldk.znajdz_dzialke_po_id


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
    return render_template(
        "osiedle/index.html", funkcje=FUNKCJE, obszar=OBSZAR, domyslne=DOMYSLNE,
        zalozenia=ZALOZENIA,
    )


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
    return jsonify({**k, "bilans": bilans(k["geojson"], k["ustawienia"])})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>", methods=["PUT"])
def zapisz_koncepcje(koncepcja_id):
    """Zapis nazwy, rysunku albo ustawień; zwraca świeży bilans."""
    obecna = _koncepcja_albo_404(koncepcja_id)
    dane = request.get_json(silent=True) or {}
    try:
        nazwa = _nazwa(dane["nazwa"]) if "nazwa" in dane else None
        geojson = dane.get("geojson")
        ustawienia = dane.get("ustawienia")
        if ustawienia is not None and not isinstance(ustawienia, dict):
            raise BladKoncepcji("Ustawienia muszą być obiektem.")
        # ETAP 67: projekt z modułu teren pokazywany jako warstwa punktów
        teren = (ustawienia or {}).get("teren_projekt")
        if teren is not None and (isinstance(teren, bool) or not isinstance(teren, int)):
            raise BladKoncepcji("Projekt terenowy: oczekiwano numeru projektu.")
        # walidacja przed zapisem: nowy rysunek i nowe ustawienia razem
        wynik = bilans(
            geojson if geojson is not None else obecna["geojson"],
            ustawienia if ustawienia is not None else obecna["ustawienia"],
        )
    except BladKoncepcji as e:
        return jsonify({"blad": str(e)}), 400
    baza.zapisz(koncepcja_id, nazwa, geojson, ustawienia)
    return jsonify({**baza.pobierz(koncepcja_id), "bilans": wynik})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>/obszar-z-dzialek", methods=["POST"])
def obszar_z_dzialek(koncepcja_id):
    """Obszar opracowania = suma granic działek ewidencyjnych z ULDK
    (ETAP 75). Zastępuje dotychczasowy obszar; tereny zostają."""
    k = _koncepcja_albo_404(koncepcja_id)
    surowe = (request.get_json(silent=True) or {}).get("dzialki")
    if not isinstance(surowe, list) or not surowe:
        return jsonify({"blad": "Podaj co najmniej jeden identyfikator działki."}), 400
    identyfikatory = list(dict.fromkeys(" ".join(str(d).split()) for d in surowe if str(d).strip()))
    if len(identyfikatory) > MAKS_DZIALEK:
        return jsonify({"blad": f"Najwyżej {MAKS_DZIALEK} działek naraz."}), 400
    geometrie = []
    for dzialka_id in identyfikatory:
        try:
            dzialka = znajdz_dzialke_po_id(dzialka_id)
        except ValueError as e:
            return jsonify({"blad": f"{dzialka_id}: {e}"}), 400
        except uldk.BladULDK as e:
            return jsonify({"blad": str(e)}), 502
        if dzialka is None:
            return jsonify({"blad": f"ULDK nie zna działki {dzialka_id}."}), 404
        geometrie.append(dzialka.geometria)
    obszar = unary_union(geometrie)
    cechy = [c for c in k["geojson"]["features"] if (c.get("properties") or {}).get("funkcja") != OBSZAR]
    cechy.insert(0, {"type": "Feature", "properties": {"funkcja": OBSZAR, "dzialki": identyfikatory}, "geometry": mapping(obszar)})
    geojson = {"type": "FeatureCollection", "features": cechy}
    try:
        wynik = bilans(geojson, k["ustawienia"])
    except BladKoncepcji as e:
        return jsonify({"blad": str(e)}), 400
    baza.zapisz(koncepcja_id, geojson=geojson)
    return jsonify({**baza.pobierz(koncepcja_id), "bilans": wynik})


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


# Raport, szkic i porównanie — w osobnym pliku, rejestruje się na osiedle_bp.
# Import na końcu, bo tamten plik importuje osiedle_bp z tego modułu.
from . import trasy_druk  # noqa: E402, F401
