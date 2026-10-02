"""Transakcje z Rejestru Cen Nieruchomości: import pliku, statystyki, mapa (ETAP 104).

Plik GeoPackage powiatu bywa duży (setki MB w dużych miastach), a
Warsztat działa na tym samym komputerze — dlatego zamiast wgrywać go przez
przeglądarkę, można wskazać plik z katalogu Pobrane. Wgrywanie zostaje dla
mniejszych plików (limit wgrywania aplikacji). Wskazać można tylko plik
.gpkg z listy, którą pokazuje sam Warsztat (nie dowolną ścieżkę).
"""

import csv
import glob
import io
import json
import os
import tempfile
from datetime import date

from flask import Response, abort, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup
from werkzeug.utils import secure_filename

from mpzp.uklady import w_polsce

from . import baza, rcn
from .routes import ceny_bp

RYNKI = ("pierwotny", "wtórny", "nieznany")
CO = ("lokale", "dzialki")  # ETAP 106: mieszkania albo działki z tego samego pliku


def katalogi_pobranych() -> list[str]:
    dom = os.path.expanduser("~")
    return [os.path.join(dom, "Pobrane"), os.path.join(dom, "Downloads")]


def pliki_gpkg() -> list[dict]:
    """Pliki .gpkg w katalogach pobranych, od najnowszego."""
    pliki = [p for k in katalogi_pobranych() for p in glob.glob(os.path.join(k, "*.gpkg"))]
    return [
        {"sciezka": p, "nazwa": os.path.basename(p), "mb": round(os.path.getsize(p) / 1e6, 1)}
        for p in sorted(pliki, key=os.path.getmtime, reverse=True)
    ]


def _importuj(sciezka: str, nazwa: str):
    try:
        wynik = rcn.czytaj_plik(sciezka)
    except rcn.BladPliku as e:
        return redirect(url_for("ceny.transakcje", blad=str(e)))
    if not wynik["lokale"] and not wynik["dzialki"]:
        return redirect(url_for("ceny.transakcje", blad="W pliku nie ma transakcji lokali mieszkalnych ani działek, które dałoby się policzyć."))
    plik_id = baza.zapisz_plik_rcn(nazwa, wynik["lokale"], wynik["odrzucone"], wynik["dzialki"], wynik["odrzucone_dzialki"])
    return redirect(url_for("ceny.transakcje", plik=plik_id, co="lokale" if wynik["lokale"] else "dzialki"))


@ceny_bp.route("/transakcje")
def transakcje():
    return render_template(
        "ceny/transakcje.html",
        pliki=baza.pliki_rcn(),
        do_importu=pliki_gpkg(),
        katalogi=katalogi_pobranych(),
        wybrany=request.args.get("plik", type=int),
        co=request.args.get("co") if request.args.get("co") in CO else "lokale",
        blad=request.args.get("blad"),
        rynki=RYNKI,
        maks_obszarow=rcn.MAKS_OBSZAROW,
        promienie=rcn.PROMIENIE_M,
        min_w_roku=rcn.MIN_W_ROKU,
        tolerancje=rcn.TOLERANCJE,
        minima=rcn.MINIMA_W_KOMORCE,
        opisy_pieter=rcn.OPISY_PIETER,
        krawedzie_h3=[(r, rcn.krawedz_h3_m(r)) for r in rcn.ROZDZIELCZOSCI_H3],
    )


@ceny_bp.route("/transakcje/import", methods=["POST"])
def importuj_transakcje():
    sciezka = request.form.get("sciezka")
    if sciezka:
        # tylko plik z listy pokazanej przez Warsztat — żadnych dowolnych ścieżek
        if sciezka not in {p["sciezka"] for p in pliki_gpkg()}:
            abort(400)
        return _importuj(sciezka, os.path.basename(sciezka))
    plik = request.files.get("plik")
    if plik is None or not plik.filename.lower().endswith(".gpkg"):
        return redirect(url_for("ceny.transakcje", blad="Wybierz plik .gpkg z Rejestru Cen Nieruchomości."))
    with tempfile.TemporaryDirectory() as katalog:
        tymczasowy = os.path.join(katalog, "rcn.gpkg")
        plik.save(tymczasowy)
        return _importuj(tymczasowy, secure_filename(plik.filename) or "rcn.gpkg")


def _co() -> str:
    co = request.args.get("co") or "lokale"
    if co not in CO:
        raise ValueError("Niepoprawny rodzaj nieruchomości.")
    return co


def _filtry(co: str) -> dict:
    rynek = request.args.get("rynek") or None
    if rynek not in (None, *RYNKI):
        raise ValueError("Niepoprawny filtr.")
    filtry = {
        "rynek": rynek,
        "od_roku": request.args.get("od", type=int),
        "do_roku": request.args.get("do", type=int),
        "rodzaj": request.args.get("rodzaj") or None,
    }
    if co == "dzialki":
        filtry["przeznaczenie"] = request.args.get("przeznaczenie") or None
        filtry["nieruchomosc"] = request.args.get("nieruchomosc") or None
    else:
        filtry["izby"] = request.args.get("izby") or None
        pietro = request.args.get("pietro") or None
        if filtry["izby"] not in (None, "1", "2", "3", "4+") or pietro not in (None, *rcn.PIETRA):
            raise ValueError("Niepoprawny filtr.")
        filtry["pietro"] = rcn.PIETRA[pietro] if pietro else None
    return filtry


def _rekordy(plik_id: int, co: str, filtry: dict | None = None) -> list[dict]:
    return (baza.dzialki_rcn if co == "dzialki" else baza.lokale_rcn)(plik_id, **(filtry or {}))


@ceny_bp.route("/transakcje/<int:plik_id>/dane")
def dane_transakcji(plik_id):
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        co = _co()
        filtry = _filtry(co)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    lokale = _rekordy(plik_id, co, filtry)
    obszary = baza.obszary_rcn(plik_id)
    tabela = "rcn_dzialki" if co == "dzialki" else "rcn_lokale"
    return jsonify({
        "plik": plik,
        "co": co,
        "lata": [w["wartosc"] for w in baza.wartosci_pola(plik_id, "rok", tabela)],  # bez drugiego wczytania wszystkich transakcji
        "listy": {pole: baza.wartosci_pola(plik_id, pole, tabela)
                  for pole in (("rodzaj", "przeznaczenie", "nieruchomosc") if co == "dzialki" else ("rodzaj",))},
        "statystyki": rcn.statystyki(lokale),
        "mapa": rcn.punkty_mapy(lokale),
        "obszary": obszary,
        "porownanie": rcn.porownanie(lokale, obszary),
    })


# ---------- obszary do porównania (ETAP 105) ----------


def _nazwa_obszaru(tekst) -> str:
    nazwa = " ".join(str(tekst or "").split())[:60]
    if not nazwa:
        raise rcn.BladPliku("Podaj nazwę obszaru.")
    return nazwa


@ceny_bp.route("/transakcje/<int:plik_id>/obszary", methods=["POST"])
def dodaj_obszar(plik_id):
    if baza.plik_rcn(plik_id) is None:
        abort(404)
    dane = request.get_json(silent=True) or {}
    try:
        if len(baza.obszary_rcn(plik_id)) >= rcn.MAKS_OBSZAROW:
            raise rcn.BladPliku(f"Najwyżej {rcn.MAKS_OBSZAROW} obszarów — usuń któryś.")
        obszar_id = baza.dodaj_obszar_rcn(plik_id, _nazwa_obszaru(dane.get("nazwa")), rcn.sprawdz_obszar(dane.get("geometria")))
    except rcn.BladPliku as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify({"id": obszar_id}), 201


@ceny_bp.route("/transakcje/obszary/<int:obszar_id>", methods=["PUT"])
def zmien_obszar(obszar_id):
    try:
        nazwa = _nazwa_obszaru((request.get_json(silent=True) or {}).get("nazwa"))
    except rcn.BladPliku as e:
        return jsonify({"blad": str(e)}), 400
    if not baza.zmien_nazwe_obszaru(obszar_id, nazwa):
        abort(404)
    return jsonify({"ok": True})


@ceny_bp.route("/transakcje/obszary/<int:obszar_id>", methods=["DELETE"])
def usun_obszar(obszar_id):
    if not baza.usun_obszar_rcn(obszar_id):
        abort(404)
    return jsonify({"ok": True})


# ---------- raport do druku (ETAP 105) ----------


@ceny_bp.route("/transakcje/<int:plik_id>/raport")
def raport_transakcji(plik_id):
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        co = _co()
        filtry = _filtry(co)
    except ValueError:
        abort(400)
    lokale = _rekordy(plik_id, co, filtry)
    obszary = baza.obszary_rcn(plik_id)
    mapa = rcn.punkty_mapy(lokale)
    porownanie = rcn.porownanie(lokale, obszary)
    return render_template(
        "ceny/raport.html",
        plik=plik,
        co=co,
        filtry=filtry,
        statystyki=rcn.statystyki(lokale),
        porownanie=porownanie,
        min_w_roku=rcn.MIN_W_ROKU,
        min_w_rynku=rcn.MIN_W_RYNKU,
        opis_pietra=rcn.OPISY_PIETER.get(request.args.get("pietro")),
        wykres_lat=Markup(rcn.wykres_lat_svg(porownanie)),  # ETAP 110; tylko liczby i kolory z kodu
        mapa=Markup(rcn.mapa_svg(lokale, obszary, mapa["progi"], rcn.KOLORY_KLAS)),  # tylko liczby i kolory z kodu
        progi=mapa["progi"],
        kolory=rcn.KOLORY_KLAS,
        dzis=date.today().isoformat(),
    )


# ---------- podobne transakcje (ETAP 107) ----------


def _parametry_wyceny() -> dict:
    """Filtry strony + miejsce, powierzchnia, promień i tolerancja; ValueError, gdy złe."""
    p = {k: request.args.get(k, type=float) for k in ("lat", "lng", "pow", "tolerancja")}
    p["promien"] = request.args.get("promien", type=int)
    p["co"] = _co()
    p["filtry"] = _filtry(p["co"])
    if p["lat"] is None or p["lng"] is None or not w_polsce(p["lat"], p["lng"]):
        raise ValueError("Wskaż miejsce na mapie (kliknij).")
    if p["pow"] is None or not 1 <= p["pow"] <= 2_000_000:
        raise ValueError("Podaj powierzchnię w m².")
    if p["promien"] not in rcn.PROMIENIE_M or p["tolerancja"] not in rcn.TOLERANCJE:
        raise ValueError("Niepoprawny promień albo tolerancja.")
    return p


def _wynik_wyceny(plik_id: int, p: dict) -> dict:
    return rcn.podobne(_rekordy(plik_id, p["co"], p["filtry"]), p["lat"], p["lng"], p["promien"], p["pow"], p["tolerancja"])


@ceny_bp.route("/transakcje/<int:plik_id>/podobne")
def podobne_transakcje(plik_id):
    """Filtry strony (rynek, lata, izby, przeznaczenie…) + miejsce i powierzchnia."""
    if baza.plik_rcn(plik_id) is None:
        abort(404)
    try:
        p = _parametry_wyceny()
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify(_wynik_wyceny(plik_id, p))


@ceny_bp.route("/transakcje/<int:plik_id>/wycena")
def karta_wyceny(plik_id):
    """ETAP 113: karta wyceny porównawczej do druku — te same parametry co /podobne."""
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        p = _parametry_wyceny()
    except ValueError:
        abort(400)
    wynik = _wynik_wyceny(plik_id, p)
    opis_filtrow = [f"rynek {p['filtry']['rynek']}"] if p["filtry"].get("rynek") else []
    if p["filtry"].get("od_roku") or p["filtry"].get("do_roku"):
        opis_filtrow.append(f"lata {p['filtry'].get('od_roku') or '…'}–{p['filtry'].get('do_roku') or '…'}")
    for klucz, etykieta in (("izby", "izby"), ("rodzaj", "transakcje"), ("przeznaczenie", "przeznaczenie"), ("nieruchomosc", "nieruchomość")):
        if p["filtry"].get(klucz):
            opis_filtrow.append(f"{etykieta}: {p['filtry'][klucz]}")
    if request.args.get("pietro") in rcn.OPISY_PIETER:
        opis_filtrow.append(rcn.OPISY_PIETER[request.args["pietro"]])
    return render_template(
        "ceny/wycena.html", plik=plik, p=p, wynik=wynik, opis_filtrow=opis_filtrow,
        mapa=Markup(rcn.mapa_wyceny_svg(wynik, p["lat"], p["lng"])),  # tylko liczby i kolory z kodu
        powrot=url_for("ceny.transakcje", plik=plik_id, co=p["co"]), dzis=date.today().isoformat(),
    )


# ---------- mapa cen w heksagonach (ETAP 108) ----------


@ceny_bp.route("/transakcje/<int:plik_id>/heksagony")
def heksagony_transakcji(plik_id):
    if baza.plik_rcn(plik_id) is None:
        abort(404)
    rozdzielczosc = request.args.get("rozdzielczosc", type=int)
    minimum = request.args.get("minimum", type=int)
    try:
        co = _co()
        filtry = _filtry(co)
        if rozdzielczosc not in rcn.ROZDZIELCZOSCI_H3 or minimum not in rcn.MINIMA_W_KOMORCE:
            raise ValueError("Niepoprawna wielkość heksagonów albo minimum transakcji.")
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify(rcn.heksagony(_rekordy(plik_id, co, filtry), rozdzielczosc, minimum))


# ---------- ceny w okolicy działki (MPZP) i obszaru osiedla (ETAP 109) ----------


@ceny_bp.route("/okolica", methods=["POST"])
def okolica():
    """JSON {geometria: GeoJSON punktu/wieloboku, promien: m} → podsumowanie
    mieszkań i działek z tego zaimportowanego pliku RCN, który ma w zasięgu
    najwięcej transakcji (pliki różnych powiatów się nie mieszają)."""
    dane = request.get_json(silent=True) or {}
    promien = dane.get("promien")
    try:
        ksztalt = rcn.ksztalt_okolicy(dane.get("geometria"))
        if promien not in rcn.PROMIENIE_OKOLICY_M:
            raise rcn.BladPliku("Niepoprawny promień.")
    except rcn.BladPliku as e:
        return jsonify({"blad": str(e)}), 400
    prostokat = rcn.prostokat_okolicy(ksztalt, promien)
    wyniki: dict[int, dict] = {}
    for co, tabela in (("lokale", "rcn_lokale"), ("dzialki", "rcn_dzialki")):
        for plik_id, rekordy in baza.w_prostokacie(tabela, *prostokat).items():
            wyniki.setdefault(plik_id, {"lokale": None, "dzialki": None})[co] = rcn.okolica(rekordy, ksztalt, promien)

    def razem(w):
        return sum(s["liczba"] for s in w.values() if s)

    najlepszy = max((p for p in wyniki if razem(wyniki[p])), key=lambda p: razem(wyniki[p]), default=None)
    odpowiedz = {"promien": promien, "promienie": list(rcn.PROMIENIE_OKOLICY_M), "pliki_zaimportowane": len(baza.pliki_rcn()),
                 "url_importu": url_for("ceny.transakcje"), "plik": None, "lokale": None, "dzialki": None}
    if najlepszy is not None:
        plik = baza.plik_rcn(najlepszy)
        odpowiedz.update(wyniki[najlepszy])
        odpowiedz["plik"] = {"id": plik["id"], "nazwa": plik["nazwa"], "data_importu": plik["data_importu"][:10],
                             "url": url_for("ceny.transakcje", plik=plik["id"])}
    return jsonify(odpowiedz)


@ceny_bp.route("/transakcje/<int:plik_id>/zmiana-heksagonow")
def zmiana_heksagonow(plik_id):
    """ETAP 111: okresy A i B zastępują filtr lat strony; pozostałe filtry obowiązują."""
    if baza.plik_rcn(plik_id) is None:
        abort(404)
    rozdzielczosc = request.args.get("rozdzielczosc", type=int)
    minimum = request.args.get("minimum", type=int)
    okresy = [request.args.get(k, type=int) for k in ("a_od", "a_do", "b_od", "b_do")]
    try:
        co = _co()
        filtry = {**_filtry(co), "od_roku": None, "do_roku": None}
        if rozdzielczosc not in rcn.ROZDZIELCZOSCI_H3 or minimum not in rcn.MINIMA_W_KOMORCE:
            raise ValueError("Niepoprawna wielkość heksagonów albo minimum transakcji.")
        if None in okresy or okresy[0] > okresy[1] or okresy[2] > okresy[3] or okresy[1] >= okresy[2]:
            raise ValueError("Wybierz dwa okresy: A wcześniejszy, B późniejszy, bez wspólnych lat.")
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify(rcn.zmiana_heksagonow(_rekordy(plik_id, co, filtry), rozdzielczosc, minimum,
                                         (okresy[0], okresy[1]), (okresy[2], okresy[3])))


@ceny_bp.route("/transakcje/<int:plik_id>.csv")
def csv_transakcji(plik_id):
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        co = _co()
        lokale = _rekordy(plik_id, co, _filtry(co))
    except ValueError:
        abort(400)
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";")
    pola = ["data", "rynek", "rodzaj", "pow_m2", "cena", "cena_m2"]
    pola += ["przeznaczenie", "uzytek", "nieruchomosc", "dzialek"] if co == "dzialki" else ["izby", "kondygnacja"]
    pola += ["lat", "lng"]
    zapis.writerow(pola)
    for l in sorted(lokale, key=lambda l: l["data"]):
        zapis.writerow([l[p] if l[p] is not None else "" for p in pola])
    zapis.writerow([])
    zapis.writerow([f"Źródło: Rejestr Cen Nieruchomości (GUGiK), plik {plik['nazwa']}. Opracowanie: Warsztat."])
    return Response(
        "﻿" + bufor.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=rcn_{co}_{plik_id}.csv"},
    )


# ---------- eksport GeoJSON do QGIS (ETAP 114) ----------


def _geojson(cechy: list[dict], nazwa_pliku: str) -> Response:
    """FeatureCollection (RFC 7946: WGS84, kolejność lon, lat) do pobrania."""
    return Response(
        json.dumps({"type": "FeatureCollection", "features": cechy}, ensure_ascii=False),
        mimetype="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={nazwa_pliku}"},
    )


def _filtry_eksportu(plik_id: int) -> tuple[dict, str, dict]:
    plik = baza.plik_rcn(plik_id)
    if plik is None:
        abort(404)
    try:
        co = _co()
        return plik, co, _filtry(co)
    except ValueError:
        abort(400)


@ceny_bp.route("/transakcje/<int:plik_id>.geojson")
def geojson_transakcji(plik_id):
    _, co, filtry = _filtry_eksportu(plik_id)
    pola = ["data", "rynek", "rodzaj", "pow_m2", "cena", "cena_m2"]
    pola += ["przeznaczenie", "uzytek", "nieruchomosc", "dzialek"] if co == "dzialki" else ["izby", "kondygnacja"]
    cechy = [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(r["lng"], 6), round(r["lat"], 6)]},
         "properties": {p: r[p] for p in pola}}
        for r in sorted(_rekordy(plik_id, co, filtry), key=lambda r: r["data"]) if r["lat"] is not None
    ]
    return _geojson(cechy, f"rcn_{co}_{plik_id}.geojson")


@ceny_bp.route("/transakcje/<int:plik_id>/heksagony.geojson")
def geojson_heksagonow(plik_id):
    _, co, filtry = _filtry_eksportu(plik_id)
    rozdzielczosc = request.args.get("rozdzielczosc", type=int)
    minimum = request.args.get("minimum", type=int)
    if rozdzielczosc not in rcn.ROZDZIELCZOSCI_H3 or minimum not in rcn.MINIMA_W_KOMORCE:
        abort(400)
    h = rcn.heksagony(_rekordy(plik_id, co, filtry), rozdzielczosc, minimum)
    cechy = []
    for k in h["komorki"]:
        pierscien = [[b, a] for a, b in k["granica"]]  # h3: (lat, lng) → GeoJSON: [lng, lat]
        cechy.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [pierscien + pierscien[:1]]},
                      "properties": {"h3": k["h3"], "liczba": k["liczba"], "mediana_m2": k["mediana_m2"]}})
    return _geojson(cechy, f"rcn_{co}_{plik_id}_h3_{rozdzielczosc}.geojson")


@ceny_bp.route("/transakcje/<int:plik_id>/obszary.geojson")
def geojson_obszarow(plik_id):
    _, co, filtry = _filtry_eksportu(plik_id)
    obszary = baza.obszary_rcn(plik_id)
    por = rcn.porownanie(_rekordy(plik_id, co, filtry), obszary)
    cechy = []
    for nr, (o, w) in enumerate(zip(obszary, por["obszary"]), start=1):
        wlasciwosci = {"nr": nr, "nazwa": o["nazwa"], "liczba": w["liczba"]}
        wlasciwosci.update({k: w.get(k) for k in ("mediana_m2", "q1_m2", "q3_m2", "mediana_pow", "wobec_calosci_proc")})
        cechy.append({"type": "Feature", "geometry": o["geometria"], "properties": wlasciwosci})
    return _geojson(cechy, f"rcn_{co}_{plik_id}_obszary.geojson")


@ceny_bp.route("/transakcje/<int:plik_id>/usun", methods=["POST"])
def usun_transakcje(plik_id):
    if not baza.usun_plik_rcn(plik_id):
        abort(404)
    return redirect(url_for("ceny.transakcje"))
