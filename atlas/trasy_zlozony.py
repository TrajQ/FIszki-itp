"""Wskaźnik złożony — strona, wynik, kartogram SVG i CSV (ETAP 84).

Składowe to wskaźniki z zestawu raportu gminy (tabela raport_wskazniki),
więc nie trzeba drugi raz szukać numerów zmiennych BDL. Wszystkie trasy
biorą te same parametry w adresie:

    woj=<12 cyfr BDL>&rok=2023&metoda=unitaryzacja&s=<id>:<kierunek>:<waga>,…

kierunek: 1 stymulanta (więcej = lepiej), -1 destymulanta; waga > 0.
Liczy atlas/zlozony.py, wartości pobiera routes._wartosci_wskaznika
(przez moduł — testy podmieniają BDL).
"""

import csv
import io
import os

from flask import Response, jsonify, render_template, request

from dane.bdl import BladBDL

from . import baza, granice, mapa_svg, routes, statystyki, zlozony
from .baza import folder_modulu
from .routes import atlas_bp
from .trasy_druk import _kolor_klasy, _numer_klasy
from .trasy_raport import _nazwa_wskaznika, _wskaznik_dla_strony


def _parametry(argumenty) -> dict:
    """Parametry z adresu → {woj, wojewodztwo, rok, metoda, skladowe}; ValueError z komunikatem."""
    woj = str(argumenty.get("woj") or "")
    if len(woj) != 12 or not woj.isdigit():
        raise ValueError("Wybierz województwo.")
    try:
        rok = int(argumenty.get("rok"))
    except (TypeError, ValueError):
        raise ValueError("Podaj rok (liczba).")
    if not 1995 <= rok <= 2100:
        raise ValueError("Niepoprawny rok.")
    metoda = argumenty.get("metoda") or "unitaryzacja"
    if metoda not in zlozony.METODY:
        raise ValueError("Metoda: unitaryzacja albo standaryzacja.")

    zestaw = {w["id"]: w for w in baza.wskazniki_raportu()}
    skladowe = []
    for czesc in (argumenty.get("s") or "").split(","):
        if not czesc:
            continue
        try:
            wid, kierunek, waga = czesc.split(":")
            wid, kierunek, waga = int(wid), int(kierunek), float(waga.replace(",", "."))
        except ValueError:
            raise ValueError("Składowe w postaci id:kierunek:waga.")
        if wid not in zestaw:
            raise ValueError("Tej składowej nie ma już w zestawie wskaźników raportu — odśwież stronę.")
        if any(s["wskaznik"]["id"] == wid for s in skladowe):
            raise ValueError("Każdy wskaźnik może być składową tylko raz.")
        skladowe.append({"wskaznik": zestaw[wid], "kierunek": kierunek, "waga": waga})

    wojewodztwo = next((w for w in routes._wojewodztwa() if w["bdl_id"] == woj), None)
    if wojewodztwo is None:
        raise ValueError("Nie znaleziono takiego województwa w BDL.")
    return {"woj": woj, "wojewodztwo": wojewodztwo, "rok": rok, "metoda": metoda, "skladowe": skladowe}


def _policz(argumenty) -> dict:
    p = _parametry(argumenty)
    skladowe = []
    for s in p["skladowe"]:
        w = s["wskaznik"]
        gminy = routes._wartosci_wskaznika(w["zmienna_id"], p["rok"], p["woj"], w["mianownik_id"], w["mnoznik"])
        skladowe.append({
            "nazwa": _nazwa_wskaznika(w),
            "kierunek": s["kierunek"],
            "waga": s["waga"],
            "gminy": [{"teryt": g["teryt"], "nazwa": g["nazwa"], "wartosc": g["wartosc"]} for g in gminy],
        })
    wynik = zlozony.wskaznik_zlozony(skladowe, p["metoda"])
    wynik.update({
        "rok": p["rok"],
        "wojewodztwo": p["wojewodztwo"],
        "nazwa_metody": zlozony.METODY[p["metoda"]],
        "skladowe": [{k: s[k] for k in ("nazwa", "kierunek", "waga")} for s in skladowe],
    })
    return wynik


def _odpowiedz_bledu(e: Exception):
    if isinstance(e, BladBDL | granice.BladGranic):
        return jsonify({"blad": str(e)}), 502
    return jsonify({"blad": str(e)}), 400


@atlas_bp.route("/wskaznik-zlozony")
def wskaznik_zlozony():
    return render_template(
        "atlas/zlozony.html",
        wskazniki=[_wskaznik_dla_strony(w) for w in baza.wskazniki_raportu()],
        metody=zlozony.METODY,
        maks=zlozony.MAKS_SKLADOWYCH,
    )


@atlas_bp.route("/wskaznik-zlozony/wynik")
def wskaznik_zlozony_wynik():
    try:
        return jsonify(_policz(request.args))
    except (ValueError, BladBDL) as e:  # BladWskaznika to też ValueError
        return _odpowiedz_bledu(e)


@atlas_bp.route("/wskaznik-zlozony/mapa.svg")
def wskaznik_zlozony_mapa():
    try:
        wynik = _policz(request.args)
        kolekcja = granice.granice_gmin(wynik["wojewodztwo"]["teryt"], os.path.join(folder_modulu(), "granice"))
        liczby = [g["wartosc"] for g in wynik["gminy"]]
        progi = statystyki.progi_klas(liczby)
        liczba = len(progi) + 1
        kolory = {g["teryt"]: _kolor_klasy(_numer_klasy(g["wartosc"], progi), liczba) for g in wynik["gminy"]}
        granice_klas = [min(liczby), *progi, max(liczby)]
        liczebnosci = statystyki.liczebnosci_klas(liczby, progi)
        legenda = [
            (
                _kolor_klasy(i, liczba),
                f"{statystyki.format_liczby(round(granice_klas[i], 3))} – {statystyki.format_liczby(round(granice_klas[i + 1], 3))}",
                liczebnosci[i],
            )
            for i in range(liczba)
        ]
        if any(c["properties"].get("teryt") not in kolory for c in kolekcja["features"]):
            legenda.append((mapa_svg.KOLOR_BRAK, "brak danych", None))
        opis_skladowych = "; ".join(
            f"{s['nazwa']} ({'+' if s['kierunek'] > 0 else '−'}, waga {statystyki.format_liczby(s['waga'])})"
            for s in wynik["skladowe"]
        )
        if len(opis_skladowych) > 170:  # przypis ma się zmieścić w szerokości arkusza
            opis_skladowych = opis_skladowych[:169] + "…"
        przypisy = [
            f"Metoda: {wynik['nazwa_metody']}" + ("" if wynik["metoda"] == "hellwig" else ", średnia ważona składowych") + "; klasy kwantylowe.",
            f"Składowe: {opis_skladowych}",
            "Źródło: GUS, Bank Danych Lokalnych; granice: PRG, GUGiK. Opracowanie własne w aplikacji Warsztat.",
        ]
        svg = mapa_svg.kartogram_svg(
            kolekcja, kolory, "Wskaźnik złożony",
            f"Gminy województwa {wynik['wojewodztwo']['nazwa']}, {wynik['rok']}",
            legenda, "Wartość wskaźnika", przypisy,
        )
    except (ValueError, BladBDL, granice.BladGranic) as e:
        return _odpowiedz_bledu(e)
    naglowki = {}
    if request.args.get("pobierz"):
        naglowki["Content-Disposition"] = (
            f"attachment; filename=wskaznik_zlozony_{wynik['wojewodztwo']['teryt']}_{wynik['rok']}.svg"
        )
    return Response(svg, mimetype="image/svg+xml", headers=naglowki)


@atlas_bp.route("/wskaznik-zlozony.csv")
def wskaznik_zlozony_csv():
    try:
        wynik = _policz(request.args)
    except (ValueError, BladBDL) as e:
        return _odpowiedz_bledu(e)
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";")
    nazwy = [s["nazwa"] for s in wynik["skladowe"]]
    zapis.writerow(["miejsce", "teryt", "gmina", "wskaźnik złożony", *nazwy, *(f"{n} — po normalizacji" for n in nazwy)])
    for g in wynik["gminy"]:
        zapis.writerow([g["miejsce"], g["teryt"], g["nazwa"], g["wartosc"], *g["surowe"], *g["skladowe"]])
    zapis.writerow([])
    zapis.writerow([f"Metoda: {wynik['nazwa_metody']}; kierunki i wagi: "
                    + "; ".join(f"{s['nazwa']} {'+' if s['kierunek'] > 0 else '-'} waga {s['waga']:g}" for s in wynik["skladowe"])])
    if wynik["pominiete"]:
        zapis.writerow(["Pominięte (brak danych którejś składowej): " + ", ".join(wynik["pominiete"])])
    nazwa = f"wskaznik_zlozony_{wynik['wojewodztwo']['teryt']}_{wynik['rok']}.csv"
    return Response(
        "﻿" + bufor.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )
