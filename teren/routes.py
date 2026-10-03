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

from . import baza, podklad, porownanie, raport, trasa
from .projekt import FORMAT, RODZAJE, TYPY_POL, WZORY, BladDanych, braki, odczytaj_geojson, odczytaj_plik, sprawdz_poprawke, sprawdz_pola, sprawdz_tekst

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


@teren_bp.route("/projekty/<int:projekt_id>/podobny", methods=["POST"])
def podobny_projekt(projekt_id):
    """ETAP 134: nowy projekt z tymi samymi polami, rodzajem i obszarem mapy — bez punktów i terminu."""
    p = _projekt_albo_404(projekt_id)
    nazwa = f"{p['nazwa']} (kopia)"[:MAKS_DLUGOSC_NAZWY]
    nowy = baza.utworz_projekt(nazwa, p["pola"], p.get("rodzaj") or "inwentaryzacja")
    if p.get("obszar"):
        baza.ustaw_obszar(nowy, p["obszar"])
    return redirect(url_for("teren.widok_projektu", projekt_id=nowy))


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
    inne = [p for p in baza.projekty() if p["id"] != projekt_id]  # ETAP 157: do porównania
    return render_template("teren/projekt.html", projekt=_projekt_albo_404(projekt_id), typy=TYPY_POL, inne=inne)


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
        return jsonify({"blad": "To nie jest plik JSON z formularza terenowego ani GeoJSON."}), 400
    geojson = isinstance(dane, dict) and dane.get("type") == "FeatureCollection"  # ETAP 133: GeoJSON, np. z QGIS
    try:
        if geojson:
            punkty, niedopasowane = odczytaj_geojson(dane, p["pola"])
        else:
            punkty = odczytaj_plik(dane, p["klucz"], p["pola"])
    except BladDanych as e:
        return jsonify({"blad": str(e)}), 400
    dodane, pominiete = baza.zapisz_punkty(projekt_id, punkty)
    wynik = {"dodane": dodane, "pominiete": pominiete}
    if geojson:
        wynik["niedopasowane"] = niedopasowane
    return jsonify(wynik)


def _punkt_dla_strony(projekt_id: int, pt: dict, pola: list[dict]) -> dict:
    wynik = {k: pt[k] for k in ("id", "lat", "lng", "dokladnosc_m", "czas", "wartosci", "uwagi", "data_poprawki")}
    wynik["braki"] = braki(pt["wartosci"], pola)  # ETAP 166
    wynik["polozenie_reczne"] = bool(pt["polozenie_reczne"])
    wynik["zdjecie"] = url_for("teren.zdjecie", projekt_id=projekt_id, punkt_id=pt["id"]) if pt["zdjecie"] else None
    return wynik


@teren_bp.route("/projekty/<int:projekt_id>/punkty")
def lista_punktow(projekt_id):
    p = _projekt_albo_404(projekt_id)
    return jsonify([_punkt_dla_strony(projekt_id, pt, p["pola"]) for pt in baza.punkty(projekt_id)])


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
    return jsonify(_punkt_dla_strony(projekt_id, pt, p["pola"]))


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


def _wiersze_punktow(p: dict) -> list[list]:
    """Tabela punktów projektu — wspólna dla CSV i ODS (ETAP 189)."""
    nazwy_pol = [pole["nazwa"] for pole in p["pola"]]
    wiersze = [["id", "czas", "szerokosc", "dlugosc", "dokladnosc_m", "polozenie_reczne", *nazwy_pol, "uwagi", "zdjecie"]]
    for pt in baza.punkty(p["id"]):
        wartosci = []
        for nazwa in nazwy_pol:
            w = pt["wartosci"].get(nazwa, "")
            wartosci.append("tak" if w is True else "nie" if w is False else "; ".join(w) if isinstance(w, list) else w)
        wiersze.append([pt["id"], pt["czas"], pt["lat"], pt["lng"], pt["dokladnosc_m"], "tak" if pt["polozenie_reczne"] else "nie",
                        *wartosci, pt["uwagi"], pt["zdjecie"] or ""])
    return wiersze


@teren_bp.route("/projekty/<int:projekt_id>.ods")
def eksport_ods(projekt_id):
    """ETAP 189: punkty projektu jako arkusz ODS (liczby jako liczby)."""
    from dane.arkusz import arkusz_ods

    p = _projekt_albo_404(projekt_id)
    plik = arkusz_ods([{"nazwa": "Punkty", "wiersze": _wiersze_punktow(p),
                        "przypisy": [f"Projekt „{p['nazwa']}” — inwentaryzacja w terenie (moduł Teren aplikacji Warsztat)."]}])
    return Response(plik, mimetype="application/vnd.oasis.opendocument.spreadsheet",
                    headers={"Content-Disposition": f"attachment; filename=teren_{_nazwa_pliku(p['nazwa'])}.ods"})


@teren_bp.route("/projekty/<int:projekt_id>.csv")
def eksport_csv(projekt_id):
    p = _projekt_albo_404(projekt_id)
    wyjscie = io.StringIO()
    zapis = csv.writer(wyjscie, delimiter=";")
    zapis.writerows(_wiersze_punktow(p))
    return Response(
        "﻿" + wyjscie.getvalue(),  # BOM — Excel otworzy polskie znaki poprawnie
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=teren_{_nazwa_pliku(p['nazwa'])}.csv"},
    )


def _trasa_z_zapytania(projekt_id: int) -> tuple[dict, list[dict], dict]:
    """ETAP 198: ?punkty=1,2,3 (puste — wszystkie z położeniem) i ?start=id."""
    p = _projekt_albo_404(projekt_id)
    punkty = [{"id": pt["id"], "lat": pt["lat"], "lng": pt["lng"]} for pt in baza.punkty(projekt_id) if pt["lat"] is not None]
    try:
        wybrane = {int(x) for x in request.args.get("punkty", "").split(",") if x.strip()}
        start = int(request.args["start"]) if request.args.get("start") else None
    except ValueError:
        raise trasa.BladTrasy("Numery punktów muszą być liczbami.") from None
    if wybrane:
        punkty = [pt for pt in punkty if pt["id"] in wybrane]
    return p, punkty, trasa.trasa(punkty, start)


@teren_bp.route("/projekty/<int:projekt_id>/trasa")
def trasa_obchodu(projekt_id):
    """Kolejność obchodu punktów: najbliższy sąsiad + 2-opt (teren/trasa.py)."""
    try:
        _, _, wynik = _trasa_z_zapytania(projekt_id)
    except trasa.BladTrasy as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify(wynik)


@teren_bp.route("/projekty/<int:projekt_id>/trasa.gpx")
def trasa_gpx(projekt_id):
    """Ta sama trasa jako GPX — do nawigacji na telefonie."""
    try:
        p, punkty, wynik = _trasa_z_zapytania(projekt_id)
    except trasa.BladTrasy as e:
        return Response(str(e), status=400, mimetype="text/plain")
    return Response(trasa.gpx(punkty, wynik["kolejnosc"], f"Trasa obchodu — {p['nazwa']}"), mimetype="application/gpx+xml",
                    headers={"Content-Disposition": f"attachment; filename=trasa_{_nazwa_pliku(p['nazwa'])}.gpx"})


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
    # ETAP 179: tabela krzyżowa dwóch pytań jednokrotnego wyboru (?krzyz_a=&krzyz_b=)
    krzyzowe = [x for x in p["pola"] if x["typ"] in raport.POLA_KRZYZOWE]
    po_nazwie = {x["nazwa"]: x for x in krzyzowe}
    krzyz_a, krzyz_b = po_nazwie.get(request.args.get("krzyz_a")), po_nazwie.get(request.args.get("krzyz_b"))
    tabela_krzyzowa = raport.tabela_krzyzowa(krzyz_a, krzyz_b, punkty) if krzyz_a and krzyz_b and krzyz_a is not krzyz_b else None
    kolory_krzyzowe = raport.kolory_kolumn(krzyz_b) if tabela_krzyzowa else []
    wykres_krzyzowy = Markup(raport.wykres_krzyzowy_svg(tabela_krzyzowa, kolory_krzyzowe)) if tabela_krzyzowa and tabela_krzyzowa["n"] else None  # ETAP 180
    return render_template(
        "teren/raport.html",
        pola_krzyzowe=krzyzowe,
        krzyz_a=krzyz_a,
        krzyz_b=krzyz_b,
        tabela_krzyzowa=tabela_krzyzowa,
        wykres_krzyzowy=wykres_krzyzowy,
        kolory_krzyzowe=kolory_krzyzowe,
        projekt=p,
        punkty=punkty,
        zestawienie=raport.zestawienie(p["pola"], punkty),
        mapa=Markup(raport.mapa_svg(punkty, pole)),  # tylko liczby i kolory z kodu
        heksagony=(h := raport.heksagony(punkty, pole)),  # ETAP 132: rozmieszczenie w heksagonach H3
        mapa_heksagonow=Markup(raport.heksagony_svg(h)) if h else None,
        kolory_gestosci=raport.KOLORY_GESTOSCI,
        pole=pole,
        pola_do_koloru=do_koloru,
        kolory=kolory,
        kolor_brak=raport.KOLOR_BRAK,
        od=min(czasy) if czasy else None,
        do=max(czasy) if czasy else None,
    )


@teren_bp.route("/okolica", methods=["POST"])
def okolica():
    """ETAP 176: JSON {geometria: GeoJSON punktu/wieloboku, promien: m} →
    punkty ze wszystkich projektów w zasięgu (dla karty działki w MPZP)."""
    from . import okolica as ok

    dane = request.get_json(silent=True) or {}
    promien = dane.get("promien", 100)
    if promien not in ok.PROMIENIE_M:
        return jsonify({"blad": f"Promień: {', '.join(map(str, ok.PROMIENIE_M))} m."}), 400
    try:
        k = ok.ksztalt(dane.get("geometria"))
    except ok.BladOkolicy as e:
        return jsonify({"blad": str(e)}), 400
    projekty = baza.projekty()
    w_zasiegu = ok.punkty_w_okolicy(k, promien, [(p, baza.punkty(p["id"])) for p in projekty])
    return jsonify({
        "promien": promien,
        "projektow": len(projekty),
        "punkty": [{
            "projekt": w["projekt"]["nazwa"],
            "projekt_url": url_for("teren.widok_projektu", projekt_id=w["projekt"]["id"]),
            "odleglosc_m": w["odleglosc_m"],
            "czas": w["punkt"]["czas"],
            "wartosci": w["punkt"]["wartosci"],
            "uwagi": w["punkt"]["uwagi"],
            "zdjecie": url_for("teren.zdjecie", projekt_id=w["projekt"]["id"], punkt_id=w["punkt"]["id"]) if w["punkt"]["zdjecie"] else None,
        } for w in w_zasiegu],
    })


@teren_bp.route("/porownanie")
def porownanie_projektow():
    """ETAP 157: dwie inwentaryzacje obok siebie (?a=…&b=…)."""
    a = _projekt_albo_404(request.args.get("a", type=int) or 0)
    b = _projekt_albo_404(request.args.get("b", type=int) or 0)
    if a["id"] == b["id"]:
        abort(400)
    punkty_a, punkty_b = raport.ponumeruj(baza.punkty(a["id"])), raport.ponumeruj(baza.punkty(b["id"]))
    pola = porownanie.wspolne_pola(a["pola"], b["pola"])
    polaczone = porownanie.pary(punkty_a, punkty_b)
    return render_template(
        "teren/porownanie.html", a=a, b=b, liczba_a=len(punkty_a), liczba_b=len(punkty_b), pola=pola,
        zestawienie=porownanie.zestawienie_obok(pola, punkty_a, punkty_b),
        polaczone=polaczone, zmiany=porownanie.zmiany_w_miejscach(pola, polaczone), prog_m=porownanie.PROG_M,
        tylko_a=[p["nazwa"] for p in a["pola"] if p not in pola], tylko_b=[p["nazwa"] for p in b["pola"] if p["nazwa"] not in {x["nazwa"] for x in pola}],
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

# ---------- ostatnio używane na stronie głównej (ETAP 141) ----------


def ostatnie(limit: int = 3) -> list[dict]:
    """Projekty od ostatnio zmienionego (utworzenie albo import punktów)."""
    return [{"tytul": p["nazwa"], "opis": f"projekt terenowy · punktów: {p['liczba_punktow']}", "kiedy": p["kiedy"],
             "url": url_for("teren.widok_projektu", projekt_id=p["id"])}
            for p in baza.ostatnio_zmienione(limit)]
