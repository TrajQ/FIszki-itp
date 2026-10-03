"""Trend liniowy wskaźnika w gminach jako kartogram (ETAP 178).

Dla każdej gminy: nachylenie prostej najmniejszych kwadratów przez
wartości z wybranych lat (ta sama funkcja co prognoza w raporcie gminy,
`raport.prognoza_trendu`), wyrażone jako średnia roczna zmiana w % średniej
gminy — wtedy gminy duże i małe są porównywalne. R² mówi, czy zmiana była
równomierna (od 0,7 — trend stabilny).
"""

import os
import statistics

from flask import Response, jsonify, render_template, request

from dane.bdl import BladBDL

from . import granice, mapa_svg, raport, statystyki
from .baza import folder_modulu
from .routes import _opis_zmiennej, _parametry_wzgledne, _wartosci_wskaznika, _wojewodztwa, atlas_bp
from .trasy_druk import KOLORY_ZMIANY, _numer_klasy

PROGI_TRENDU_PROC = [-3.0, -0.5, 0.5, 3.0]  # % średniej na rok
MIN_LAT, MAKS_LAT = raport.MIN_PUNKTOW_TRENDU, raport.LAT_WSTECZ + 1


def _parametry(argumenty) -> dict:
    try:
        zmienna_id = int(argumenty.get("zmienna"))
        od, do = int(argumenty.get("od")), int(argumenty.get("do"))
    except (TypeError, ValueError):
        raise ValueError("Wymagane: zmienna, od i do (lata).") from None
    woj = str(argumenty.get("woj") or "")
    if len(woj) != 12 or not woj.isdigit():
        raise ValueError("Parametr woj musi być 12-cyfrowym identyfikatorem BDL województwa.")
    if not (1995 <= od < do <= 2100) or not MIN_LAT <= do - od + 1 <= MAKS_LAT:
        raise ValueError(f"Lata od–do: od {MIN_LAT} do {MAKS_LAT} kolejnych lat.")
    return {"zmienna_id": zmienna_id, "woj": woj, "od": od, "do": do, **_parametry_wzgledne(argumenty, zmienna_id)}


def trendy_gmin(wartosci_w_latach: dict[int, list[dict]]) -> list[dict]:
    """{rok: [{"teryt", "nazwa", "wartosc"}]} → trend każdej gminy z co
    najmniej MIN_LAT latami danych (inaczej pominięta)."""
    szeregi: dict[str, dict] = {}
    for rok in sorted(wartosci_w_latach):
        for g in wartosci_w_latach[rok]:
            s = szeregi.setdefault(g["teryt"], {"nazwa": g["nazwa"], "szereg": []})
            s["szereg"].append({"rok": rok, "wartosc": g["wartosc"]})
    wynik = []
    for teryt, s in szeregi.items():
        t = raport.prognoza_trendu(s["szereg"])
        srednia = statistics.fmean(p["wartosc"] for p in s["szereg"])
        if t is None or srednia == 0:
            continue
        wynik.append({"teryt": teryt, "nazwa": s["nazwa"], "zmiana_roczna": t["zmiana_roczna"], "lat": len(s["szereg"]),
                      "zmiana_roczna_proc": 100 * t["zmiana_roczna"] / abs(srednia), "r2": t["r2"], "stabilny": t["stabilny"]})
    return sorted(wynik, key=lambda g: -g["zmiana_roczna_proc"])


def _policz(argumenty) -> dict:
    p = _parametry(argumenty)
    wojewodztwo = next((w for w in _wojewodztwa() if w["bdl_id"] == p["woj"]), None)
    if wojewodztwo is None:
        raise LookupError("Nie znaleziono takiego województwa w BDL.")
    lata = {rok: _wartosci_wskaznika(p["zmienna_id"], rok, p["woj"], p["mianownik"], p["mnoznik"]) for rok in range(p["od"], p["do"] + 1)}
    gminy = trendy_gmin(lata)
    if not gminy:
        raise LookupError(f"Żadna gmina nie ma danych z co najmniej {MIN_LAT} lat w wybranym okresie.")
    return {**p, "wojewodztwo": wojewodztwo, "zmienna": _opis_zmiennej(p["zmienna_id"], p["mianownik"], p["mnoznik"]), "gminy": gminy,
            "niestabilnych": sum(1 for g in gminy if not g["stabilny"]), "lata_z_danymi": sorted(r for r, w in lata.items() if w)}


def _svg(wynik: dict) -> str:
    kolekcja = granice.granice_gmin(wynik["wojewodztwo"]["teryt"], os.path.join(folder_modulu(), "granice"))
    kolory = {g["teryt"]: KOLORY_ZMIANY[_numer_klasy(g["zmiana_roczna_proc"], PROGI_TRENDU_PROC)] for g in wynik["gminy"]}
    ile = [0] * len(KOLORY_ZMIANY)
    for g in wynik["gminy"]:
        ile[_numer_klasy(g["zmiana_roczna_proc"], PROGI_TRENDU_PROC)] += 1
    p = [statystyki.format_liczby(x) for x in PROGI_TRENDU_PROC]
    opisy = [f"spadek ponad {p[0][1:]}%", f"spadek {p[1][1:]}–{p[0][1:]}%", f"stabilnie (±{p[2]}%)", f"wzrost {p[2]}–{p[3]}%", f"wzrost ponad {p[3]}%"]
    legenda = [(KOLORY_ZMIANY[i], opis, ile[i]) for i, opis in enumerate(opisy)]
    if any(c["properties"]["teryt"] not in kolory for c in kolekcja["features"]):
        legenda.append((mapa_svg.KOLOR_BRAK, f"mniej niż {MIN_LAT} lat danych", None))
    przypisy = ["Źródło: GUS, Bank Danych Lokalnych; granice: PRG, GUGiK. Opracowanie własne w aplikacji Warsztat.",
                "Trend liniowy (najmniejsze kwadraty), średnia roczna zmiana w % średniej wartości gminy w okresie.",
                f"Trend niestabilny (R² < {statystyki.format_liczby(raport.R2_STABILNY)}): {wynik['niestabilnych']} z {len(wynik['gminy'])} gmin."]
    return mapa_svg.kartogram_svg(kolekcja, kolory, wynik["zmienna"]["nazwa"],
                                  f"Gminy województwa {wynik['wojewodztwo']['nazwa']}, trend {wynik['od']}–{wynik['do']}",
                                  legenda, "Średnia roczna zmiana", przypisy)


@atlas_bp.route("/trend.svg")
def trend_svg():
    try:
        wynik = _policz(request.args)
        svg = _svg(wynik)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404
    except (BladBDL, granice.BladGranic) as e:
        return jsonify({"blad": str(e)}), 502
    naglowki = {"Content-Disposition": f"attachment; filename=trend_{wynik['wojewodztwo']['teryt']}_{wynik['od']}-{wynik['do']}.svg"} if request.args.get("pobierz") else {}
    return Response(svg, mimetype="image/svg+xml", headers=naglowki)


@atlas_bp.route("/trend")
def trend_strona():
    """Strona: wybór lat, kartogram trendu i tabela gmin (ETAP 178)."""
    parametry = {k: v for k, v in request.args.items() if k != "pobierz"}
    rok = request.args.get("rok", type=int)
    if rok and "od" not in parametry:
        parametry["od"], parametry["do"] = str(rok - raport.LAT_WSTECZ), str(rok)
    wynik, blad = None, None
    try:
        wynik = _policz(parametry)
    except (ValueError, LookupError, BladBDL) as e:
        blad = str(e)
    return render_template("atlas/trend.html", parametry=parametry, wynik=wynik, blad=blad, maks_lat=MAKS_LAT, min_lat=MIN_LAT,
                           r2_stabilny=raport.R2_STABILNY)
