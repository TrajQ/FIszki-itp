"""„Moje działki” (ETAP 44): lista zapisanych działek z notatkami i CSV.

Trasy rejestrują się na wspólnym blueprincie `mpzp_bp` (import w
mpzp/routes.py na końcu pliku).
"""

import csv
import io

from flask import Response, jsonify, request

from dane.uldk import WZOR_ID_DZIALKI

from .baza import usun_zapisana, zapisane, zapisz_dzialke
from .liczby import liczba_skonczona
from .routes import mpzp_bp


# ---------- Moje działki (ETAP 44) ----------

MAKS_DLUGOSC_NOTATKI = 2000


@mpzp_bp.route("/zapisane")
def lista_zapisanych():
    return jsonify(zapisane())


@mpzp_bp.route("/zapisane", methods=["POST"])
def zapisz_zapisana():
    """Dodaje działkę do „Moich działek” albo zmienia jej notatkę."""
    dane = request.get_json(silent=True) or {}
    dzialka_id = str(dane.get("id") or "").strip()
    if not WZOR_ID_DZIALKI.match(dzialka_id):
        return jsonify({"blad": "Niepoprawny identyfikator działki."}), 400
    try:
        lat = liczba_skonczona(dane.get("lat"))
        lon = liczba_skonczona(dane.get("lon"))
        powierzchnia = dane.get("powierzchnia_m2")
        powierzchnia = None if powierzchnia in (None, "") else liczba_skonczona(powierzchnia)
    except (TypeError, ValueError):
        return jsonify({"blad": "Współrzędne i powierzchnia muszą być liczbami."}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"blad": "Współrzędne poza zakresem."}), 400
    notatka = str(dane.get("notatka") or "").strip()
    if len(notatka) > MAKS_DLUGOSC_NOTATKI:
        return jsonify({"blad": f"Notatka może mieć najwyżej {MAKS_DLUGOSC_NOTATKI} znaków."}), 400
    przeznaczenie = dane.get("przeznaczenie")
    przeznaczenie = str(przeznaczenie)[:100] if przeznaczenie else None
    return jsonify(zapisz_dzialke(dzialka_id, przeznaczenie, lat, lon, powierzchnia, notatka))


@mpzp_bp.route("/zapisane", methods=["DELETE"])
def usun_z_zapisanych():
    if not usun_zapisana(request.args.get("id", "")):
        return jsonify({"blad": "Tej działki nie ma w „Moich działkach”."}), 404
    return jsonify({"ok": True})


@mpzp_bp.route("/zapisane.csv")
def zapisane_csv():
    """„Moje działki” do arkusza (średnik i BOM — Excel z polskimi ustawieniami)."""
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";")
    zapis.writerow(["id_dzialki", "przeznaczenie", "powierzchnia_m2", "szerokosc_geogr", "dlugosc_geogr", "notatka", "data_dodania"])
    for w in zapisane():
        powierzchnia = "" if w["powierzchnia_m2"] is None else f"{w['powierzchnia_m2']:.1f}".replace(".", ",")
        zapis.writerow(
            [w["dzialka_id"], w["przeznaczenie"] or "", powierzchnia, f"{w['lat']:.6f}", f"{w['lon']:.6f}", w["notatka"], w["data_dodania"]]
        )
    return Response(
        "\ufeff" + bufor.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=moje_dzialki.csv"},
    )
