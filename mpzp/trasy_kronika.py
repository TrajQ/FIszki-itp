"""Kronika zmian (ETAP 64): ortofotomapy z różnych lat w miejscu działki.

Strona dostaje działkę (identyfikator → granica z ULDK) albo punkt;
lata zdjęć podaje usługa WMS (dane/ortofoto.py). Działkę szukamy przez
moduł routes (routes.znajdz_dzialke_po_id), żeby testy mogły ją podmienić.
"""

from flask import jsonify, render_template, request
from shapely.geometry import mapping

from dane import ortofoto
from dane.uldk import BladULDK

from . import routes
from .routes import mpzp_bp


@mpzp_bp.route("/kronika")
def kronika():
    dzialka, blad = None, None
    dzialka_id = (request.args.get("id") or "").strip()
    if dzialka_id:
        try:
            znaleziona = routes.znajdz_dzialke_po_id(dzialka_id)
            if znaleziona is None:
                blad = f"ULDK nie zna działki {dzialka_id}."
            else:
                dzialka = {"id": znaleziona.id, "geometria": mapping(znaleziona.geometria)}
        except ValueError as e:
            blad = str(e)
        except BladULDK as e:
            blad = str(e)
    punkt = None
    try:
        lat, lng = float(request.args["lat"]), float(request.args["lng"])
        if 49 <= lat <= 55 and 14 <= lng <= 24.5:  # Polska
            punkt = [lat, lng]
    except (KeyError, ValueError):
        pass
    return render_template("mpzp/kronika.html", dzialka=dzialka, punkt=punkt, blad=blad)


@mpzp_bp.route("/kronika/lata")
def kronika_lata():
    try:
        wynik = ortofoto.lata_archiwalne()
    except ortofoto.BladOrtofoto as e:
        return jsonify({"blad": str(e)}), 502
    if not wynik["lata"]:
        return jsonify({"blad": "Usługa odpowiedziała, ale nie podała lat zdjęć (brak wymiaru czasu i warstw z rokiem w nazwie). "
                                "Sprawdź adres ORTO_ARCHIWALNA_WMS w pliku .env.", "url": wynik["url"]}), 502
    return jsonify(wynik)
