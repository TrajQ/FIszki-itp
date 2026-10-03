"""Typologia gmin (k-średnich) — strona, wynik, kartogram SVG i CSV (ETAP 124).

Wskaźniki wybiera się z zestawu raportu gminy, tak jak składowe
wskaźnika złożonego — te same parametry w adresie (kierunek i waga są
tu bez znaczenia), plus k = liczba typów:

    woj=<12 cyfr BDL>&rok=2023&k=4&s=<id>:1:1,…
"""

import csv
import io
import os

from flask import Response, jsonify, render_template, request

from dane.bdl import BladBDL

from . import baza, granice, mapa_svg, routes, typologia
from .baza import folder_modulu
from .routes import atlas_bp
from .trasy_raport import _nazwa_wskaznika, _wskaznik_dla_strony
from .trasy_zlozony import _odpowiedz_bledu, _parametry

# kolory typów — kategorie, nie skala (sąsiednie typy wyraźnie różne)
KOLORY_TYPOW = ["#0071e3", "#ff9f0a", "#34c759", "#ff375f", "#5e5ce6", "#a2845e", "#30b0c7", "#bf5af2"]


def _skladowe(p: dict) -> list[dict]:
    skladowe = []
    for s in p["skladowe"]:
        w = s["wskaznik"]
        gminy = routes._wartosci_wskaznika(w["zmienna_id"], p["rok"], p["woj"], w["mianownik_id"], w["mnoznik"])
        skladowe.append({"nazwa": _nazwa_wskaznika(w),
                         "gminy": [{"teryt": g["teryt"], "nazwa": g["nazwa"], "wartosc": g["wartosc"]} for g in gminy]})
    return skladowe


def _policz(argumenty) -> dict:
    p = _parametry(argumenty)
    try:
        k = int(argumenty.get("k", 4))
    except (TypeError, ValueError):
        raise ValueError("Liczba typów (k) musi być liczbą.")
    skladowe = _skladowe(p)
    wynik = typologia.typologia(skladowe, k)
    wynik.update({"rok": p["rok"], "wojewodztwo": p["wojewodztwo"], "skladowe": [s["nazwa"] for s in skladowe],
                  "kolory": KOLORY_TYPOW[:k]})
    return wynik


@atlas_bp.route("/typologia")
def typologia_gmin():
    return render_template("atlas/typologia.html", wskazniki=[_wskaznik_dla_strony(w) for w in baza.wskazniki_raportu()],
                           min_k=typologia.MIN_K, maks_k=typologia.MAKS_K)


@atlas_bp.route("/typologia/wynik")
def typologia_wynik():
    try:
        return jsonify(_policz(request.args))
    except (ValueError, BladBDL) as e:  # BladTypologii to też ValueError
        return _odpowiedz_bledu(e)


@atlas_bp.route("/typologia/sylwetki")
def typologia_sylwetki():
    """ETAP 125: jakość podziału dla każdej liczby typów — te same wskaźniki i dane."""
    try:
        return jsonify(typologia.sylwetki(_skladowe(_parametry(request.args))))
    except (ValueError, BladBDL) as e:
        return _odpowiedz_bledu(e)


@atlas_bp.route("/typologia/podobne")
def typologia_podobne():
    """ETAP 177: gminy podobne do wybranej — te same parametry co typologia + gmina=<TERYT>."""
    try:
        p = _parametry(request.args)
        wynik = typologia.podobne(_skladowe(p), str(request.args.get("gmina", "")))
        wynik["skladowe"] = [_nazwa_wskaznika(s["wskaznik"]) for s in p["skladowe"]]
        return jsonify(wynik)
    except (ValueError, BladBDL) as e:
        return _odpowiedz_bledu(e)


@atlas_bp.route("/typologia/mapa.svg")
def typologia_mapa():
    try:
        wynik = _policz(request.args)
        kolekcja = granice.granice_gmin(wynik["wojewodztwo"]["teryt"], os.path.join(folder_modulu(), "granice"))
        kolory = {g["teryt"]: KOLORY_TYPOW[g["typ"] - 1] for g in wynik["gminy"]}
        # w legendzie tylko „Typ N” — opisy są długie, idą do przypisów pod mapą
        legenda = [(KOLORY_TYPOW[t["nr"] - 1], f"Typ {t['nr']}", t["liczba"]) for t in wynik["typy"]]
        if any(c["properties"].get("teryt") not in kolory for c in kolekcja["features"]):
            legenda.append((mapa_svg.KOLOR_BRAK, "brak danych", None))
        opis = "; ".join(wynik["skladowe"])
        przypisy = [(f"Typ {t['nr']}: {t['opis']}")[:170] for t in wynik["typy"]] + [
            f"Metoda: k-średnich (k = {wynik['k']}) na wskaźnikach standaryzowanych; jakość podziału — średnia sylwetka "
            + (f"{wynik['sylwetka']:.2f}".replace(".", ",") if wynik["sylwetka"] is not None else "—") + ".",
            f"Wskaźniki: {opis[:169] + '…' if len(opis) > 170 else opis}",
            "Źródło: GUS, Bank Danych Lokalnych; granice: PRG, GUGiK. Opracowanie własne w aplikacji Warsztat.",
        ]
        svg = mapa_svg.kartogram_svg(kolekcja, kolory, "Typologia gmin",
                                     f"Gminy województwa {wynik['wojewodztwo']['nazwa']}, {wynik['rok']}", legenda, "Typ", przypisy)
    except (ValueError, BladBDL, granice.BladGranic) as e:
        return _odpowiedz_bledu(e)
    naglowki = {}
    if request.args.get("pobierz"):
        naglowki["Content-Disposition"] = f"attachment; filename=typologia_{wynik['wojewodztwo']['teryt']}_{wynik['rok']}_k{wynik['k']}.svg"
    return Response(svg, mimetype="image/svg+xml", headers=naglowki)


@atlas_bp.route("/typologia.csv")
def typologia_csv():
    try:
        wynik = _policz(request.args)
    except (ValueError, BladBDL) as e:
        return _odpowiedz_bledu(e)
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";")
    zapis.writerow(["typ", "teryt", "gmina", *wynik["skladowe"], *(f"{n} — z" for n in wynik["skladowe"])])
    for g in wynik["gminy"]:
        zapis.writerow([g["typ"], g["teryt"], g["nazwa"], *g["surowe"], *g["z"]])
    zapis.writerow([])
    for t in wynik["typy"]:
        zapis.writerow([f"Typ {t['nr']} ({t['liczba']} gmin): {t['opis']}"])
    zapis.writerow([f"k-średnich na wskaźnikach standaryzowanych, k = {wynik['k']}, średnia sylwetka: {wynik['sylwetka']}"])
    if wynik["pominiete"]:
        zapis.writerow(["Pominięte (brak danych któregoś wskaźnika): " + ", ".join(wynik["pominiete"])])
    nazwa = f"typologia_{wynik['wojewodztwo']['teryt']}_{wynik['rok']}_k{wynik['k']}.csv"
    return Response("﻿" + bufor.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={nazwa}"})
