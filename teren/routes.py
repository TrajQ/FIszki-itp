"""Moduł teren: inwentaryzacja w terenie (ETAP 65).

Warsztat działa tylko na 127.0.0.1, więc telefon nie może się z nim
połączyć. Dlatego: projekt → samodzielny plik HTML z formularzem
(działa na telefonie bez internetu, dane trzyma w pamięci przeglądarki
telefonu) → plik JSON z punktami → import tutaj.
"""

import csv
import io
import json
import re
import unicodedata
from datetime import date

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

from markupsafe import Markup

from . import baza, podklad, raport
from .projekt import FORMAT, RODZAJE, TYPY_POL, WZORY, BladDanych, odczytaj_plik, sprawdz_poprawke, sprawdz_pola, sprawdz_tekst

teren_bp = Blueprint(
    "teren",
    __name__,
    template_folder="templates",
    static_folder="static",
)

MAKS_DLUGOSC_NAZWY = 80


def _projekt_albo_404(projekt_id: int) -> dict:
    p = baza.projekt(projekt_id)
    if p is None:
        abort(404)
    return p


def _nazwa_pliku(tekst: str) -> str:
    """„Zieleń — Jeżyce” → „zielen_jezyce” (bez polskich znaków, dla telefonu i QGIS)."""
    tekst = unicodedata.normalize("NFD", tekst.replace("ł", "l").replace("Ł", "L"))
    tekst = "".join(z for z in tekst if not unicodedata.combining(z)).lower()
    return re.sub(r"[^a-z0-9]+", "_", tekst).strip("_")[:40] or "projekt"


def podsumowanie() -> dict:
    """Liczba projektów i punktów — na kartę modułu na stronie głównej."""
    lista = baza.projekty()
    return {"projekty": len(lista), "punkty": sum(p["liczba_punktow"] for p in lista)}


def terminy() -> list[dict]:
    """Nadchodzące wyjścia w teren — do kalendarza na stronie głównej (ETAP 86)."""
    dzis = date.today()
    wynik = []
    for p in baza.projekty():
        if not p.get("termin"):
            continue
        dni = (date.fromisoformat(p["termin"]) - dzis).days
        if dni >= 0:
            wynik.append({
                "data": p["termin"],
                "dni": dni,
                "rodzaj": "teren",
                "nazwa": p["nazwa"],
                "opis": f"punkty: {p['liczba_punktow']}" + ("" if p["obszar"] else ", bez obszaru prac (mapa offline)"),
                "url": url_for("teren.widok_projektu", projekt_id=p["id"]),
            })
    return wynik


@teren_bp.route("/")
def index():
    return render_template("teren/index.html", projekty=baza.projekty(), wzory=WZORY, blad=request.args.get("blad"))


@teren_bp.route("/projekty.json")
def lista_projektow():
    """Lista projektów dla innych modułów (np. warstwa punktów w Osiedlu, ETAP 67)."""
    return jsonify([{"id": p["id"], "nazwa": p["nazwa"], "liczba_punktow": p["liczba_punktow"]} for p in baza.projekty()])


@teren_bp.route("/projekty", methods=["POST"])
def nowy_projekt():
    try:
        nazwa = sprawdz_tekst(request.form.get("nazwa"), "Nazwa projektu", MAKS_DLUGOSC_NAZWY)
        wzor = WZORY.get(request.form.get("wzor") or "")
        pola = sprawdz_pola(wzor["pola"] if wzor else [{"nazwa": "uwaga", "typ": "tekst", "opcje": []}])
    except BladDanych as e:
        return redirect(url_for("teren.index", blad=str(e)))
    rodzaj = (wzor or {}).get("rodzaj", "inwentaryzacja")
    return redirect(url_for("teren.widok_projektu", projekt_id=baza.utworz_projekt(nazwa, pola, rodzaj)))


@teren_bp.route("/projekty/<int:projekt_id>/rodzaj", methods=["POST"])
def ustaw_rodzaj(projekt_id):
    """Inwentaryzacja albo ankieta (ETAP 93) — zmienia wygląd formularza na telefon i raportu."""
    _projekt_albo_404(projekt_id)
    rodzaj = request.form.get("rodzaj")
    if rodzaj not in RODZAJE:
        abort(400)
    baza.ustaw_rodzaj(projekt_id, rodzaj)
    return redirect(url_for("teren.widok_projektu", projekt_id=projekt_id))


@teren_bp.route("/projekty/<int:projekt_id>")
def widok_projektu(projekt_id):
    return render_template("teren/projekt.html", projekt=_projekt_albo_404(projekt_id), typy=TYPY_POL)


@teren_bp.route("/projekty/<int:projekt_id>", methods=["PUT"])
def zmien_projekt(projekt_id):
    _projekt_albo_404(projekt_id)
    dane = request.get_json(silent=True) or {}
    try:
        nazwa = sprawdz_tekst(dane.get("nazwa"), "Nazwa projektu", MAKS_DLUGOSC_NAZWY)
        pola = sprawdz_pola(dane.get("pola"))
    except BladDanych as e:
        return jsonify({"blad": str(e)}), 400
    baza.zmien_projekt(projekt_id, nazwa, pola)
    return jsonify(baza.projekt(projekt_id))


@teren_bp.route("/projekty/<int:projekt_id>/termin", methods=["POST"])
def ustaw_termin(projekt_id):
    """Planowany termin wyjścia w teren (ETAP 86); pusty — usuwa termin."""
    _projekt_albo_404(projekt_id)
    tekst = "" if request.form.get("usun") else (request.form.get("termin") or "").strip()
    if tekst:
        try:
            tekst = date.fromisoformat(tekst).isoformat()
        except ValueError:
            abort(400)
    baza.ustaw_termin(projekt_id, tekst or None)
    return redirect(url_for("teren.widok_projektu", projekt_id=projekt_id))


@teren_bp.route("/projekty/<int:projekt_id>/obszar", methods=["PUT"])
def ustaw_obszar(projekt_id):
    """Obszar prac (ETAP 83) — podkład mapy w formularzu na telefon."""
    _projekt_albo_404(projekt_id)
    obszar = (request.get_json(silent=True) or {}).get("obszar")
    try:
        obszar = podklad.sprawdz_obszar(obszar) if obszar is not None else None
    except podklad.BladObszaru as e:
        return jsonify({"blad": str(e)}), 400
    baza.ustaw_obszar(projekt_id, obszar)
    return jsonify({"obszar": obszar})


@teren_bp.route("/projekty/<int:projekt_id>", methods=["DELETE"])
def usun_projekt(projekt_id):
    _projekt_albo_404(projekt_id)
    baza.usun_projekt(projekt_id)
    return jsonify({"ok": True})


@teren_bp.route("/projekty/<int:projekt_id>/formularz.html")
def formularz(projekt_id):
    """Samodzielny formularz na telefon: cały CSS i JS w jednym pliku."""
    p = _projekt_albo_404(projekt_id)
    # ETAP 83: z obszarem prac — mapa z podkładem ortofotomapy w pliku.
    mapa = podklad.podklad(p["obszar"]) if p["obszar"] else None
    html = render_template("teren/telefon.html", projekt=p, format_pliku=FORMAT, mapa=mapa)
    return Response(
        html,
        mimetype="text/html",
        headers={"Content-Disposition": f"attachment; filename=teren_{_nazwa_pliku(p['nazwa'])}.html"},
    )


@teren_bp.route("/projekty/<int:projekt_id>/import", methods=["POST"])
def importuj(projekt_id):
    p = _projekt_albo_404(projekt_id)
    plik = request.files.get("plik")
    if plik is None or not plik.filename:
        return jsonify({"blad": "Nie wybrano pliku."}), 400
    try:
        dane = json.loads(plik.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"blad": "To nie jest plik JSON z formularza terenowego."}), 400
    try:
        punkty = odczytaj_plik(dane, p["klucz"], p["pola"])
    except BladDanych as e:
        return jsonify({"blad": str(e)}), 400
    dodane, pominiete = baza.zapisz_punkty(projekt_id, punkty)
    return jsonify({"dodane": dodane, "pominiete": pominiete})


def _punkt_dla_strony(projekt_id: int, pt: dict) -> dict:
    wynik = {k: pt[k] for k in ("id", "lat", "lng", "dokladnosc_m", "czas", "wartosci", "uwagi", "data_poprawki")}
    wynik["polozenie_reczne"] = bool(pt["polozenie_reczne"])
    wynik["zdjecie"] = url_for("teren.zdjecie", projekt_id=projekt_id, punkt_id=pt["id"]) if pt["zdjecie"] else None
    return wynik


@teren_bp.route("/projekty/<int:projekt_id>/punkty")
def lista_punktow(projekt_id):
    _projekt_albo_404(projekt_id)
    return jsonify([_punkt_dla_strony(projekt_id, pt) for pt in baza.punkty(projekt_id)])


@teren_bp.route("/projekty/<int:projekt_id>/punkty/<int:punkt_id>", methods=["PUT"])
def popraw_punkt(projekt_id, punkt_id):
    """Poprawka punktu po imporcie (ETAP 72): wartości, uwagi, położenie."""
    p = _projekt_albo_404(projekt_id)
    try:
        poprawka = sprawdz_poprawke(request.get_json(silent=True), p["pola"])
    except BladDanych as e:
        return jsonify({"blad": str(e)}), 400
    if not baza.popraw_punkt(projekt_id, punkt_id, poprawka):
        abort(404)
    pt = next(pt for pt in baza.punkty(projekt_id) if pt["id"] == punkt_id)
    return jsonify(_punkt_dla_strony(projekt_id, pt))


@teren_bp.route("/projekty/<int:projekt_id>/punkty/<int:punkt_id>", methods=["DELETE"])
def usun_punkt(projekt_id, punkt_id):
    if not baza.usun_punkt(projekt_id, punkt_id):
        abort(404)
    return jsonify({"ok": True})


@teren_bp.route("/projekty/<int:projekt_id>/zdjecia/<int:punkt_id>.jpg")
def zdjecie(projekt_id, punkt_id):
    pt = next((pt for pt in baza.punkty(projekt_id) if pt["id"] == punkt_id), None)
    if pt is None or not pt["zdjecie"]:
        abort(404)
    return send_from_directory(baza.folder_zdjec(), pt["zdjecie"], mimetype="image/jpeg")


@teren_bp.route("/projekty/<int:projekt_id>.geojson")
def eksport_geojson(projekt_id):
    """Punkty z położeniem do QGIS; wartości pól jako atrybuty."""
    p = _projekt_albo_404(projekt_id)
    cechy = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [pt["lng"], pt["lat"]]},
            "properties": {"id": pt["id"], "czas": pt["czas"], "dokladnosc_m": pt["dokladnosc_m"],
                           "polozenie_reczne": bool(pt["polozenie_reczne"]), **pt["wartosci"],
                           "uwagi": pt["uwagi"], "zdjecie": pt["zdjecie"]},
        }
        for pt in baza.punkty(projekt_id)
        if pt["lat"] is not None
    ]
    return Response(
        json.dumps({"type": "FeatureCollection", "features": cechy}, ensure_ascii=False),
        mimetype="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename=teren_{_nazwa_pliku(p['nazwa'])}.geojson"},
    )


@teren_bp.route("/projekty/<int:projekt_id>.csv")
def eksport_csv(projekt_id):
    p = _projekt_albo_404(projekt_id)
    wyjscie = io.StringIO()
    zapis = csv.writer(wyjscie, delimiter=";")
    nazwy_pol = [pole["nazwa"] for pole in p["pola"]]
    zapis.writerow(["id", "czas", "szerokosc", "dlugosc", "dokladnosc_m", "polozenie_reczne", *nazwy_pol, "uwagi", "zdjecie"])
    for pt in baza.punkty(projekt_id):
        wartosci = []
        for nazwa in nazwy_pol:
            w = pt["wartosci"].get(nazwa, "")
            wartosci.append("tak" if w is True else "nie" if w is False else "; ".join(w) if isinstance(w, list) else w)
        zapis.writerow([pt["id"], pt["czas"], pt["lat"], pt["lng"], pt["dokladnosc_m"], "tak" if pt["polozenie_reczne"] else "nie",
                        *wartosci, pt["uwagi"], pt["zdjecie"] or ""])
    return Response(
        "﻿" + wyjscie.getvalue(),  # BOM — Excel otworzy polskie znaki poprawnie
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=teren_{_nazwa_pliku(p['nazwa'])}.csv"},
    )


@teren_bp.route("/projekty/<int:projekt_id>/raport")
def raport_projektu(projekt_id):
    """Raport do druku (ETAP 69): mapa, zestawienie, punkty, zdjęcia."""
    p = _projekt_albo_404(projekt_id)
    punkty = raport.ponumeruj(baza.punkty(projekt_id))
    do_koloru = [pole for pole in p["pola"] if pole["typ"] in ("wybor", "tak_nie")]
    nazwa = request.args.get("pole")
    if nazwa is None:
        pole = do_koloru[0] if do_koloru else None  # domyślnie pierwsze pole wyboru
    else:
        pole = next((x for x in do_koloru if x["nazwa"] == nazwa), None)
    kolory = raport.kolory_pola(pole)
    for pt in punkty:
        pt["kolor"] = raport.kolor_punktu(pt, pole, kolory)
        pt["url_zdjecia"] = url_for("teren.zdjecie", projekt_id=projekt_id, punkt_id=pt["id"]) if pt["zdjecie"] else None
    czasy = [pt["czas"] for pt in punkty]
    return render_template(
        "teren/raport.html",
        projekt=p,
        punkty=punkty,
        zestawienie=raport.zestawienie(p["pola"], punkty),
        mapa=Markup(raport.mapa_svg(punkty, pole)),  # tylko liczby i kolory z kodu
        pole=pole,
        pola_do_koloru=do_koloru,
        kolory=kolory,
        kolor_brak=raport.KOLOR_BRAK,
        od=min(czasy) if czasy else None,
        do=max(czasy) if czasy else None,
    )


# ---------- wyszukiwarka globalna (ETAP 128) ----------


def wyszukaj(fraza: str) -> list[dict]:
    """Projekty inwentaryzacji po nazwie."""
    szukane = fraza.casefold()
    return [
        {"tytul": p["nazwa"], "opis": f"projekt terenowy, {p['liczba_punktow']} punktów",
         "url": url_for("teren.widok_projektu", projekt_id=p["id"])}
        for p in baza.projekty() if szukane in p["nazwa"].casefold()
    ][:10]
