"""Moduł ceny: ceny mieszkań w miastach i powiatach z GUS BDL (ETAP 103).

GUS publikuje w Banku Danych Lokalnych m.in. medianę ceny 1 m² lokali
mieszkalnych sprzedanych w transakcjach rynkowych — dla powiatów, więc
także dla miast na prawach powiatu. Który wskaźnik BDL liczyć, wybiera
użytkownik z wyszukiwarki (bez numerów zmiennych wpisanych w kod, jak w
raporcie gminy — D-069). Moduł pokazuje szeregi w czasie dla kilku miast,
zmiany i ranking powiatów województwa.
"""

import csv
import io
from dataclasses import asdict

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup

from dane import bdl
from dane.bdl import BladBDL

from . import analiza, baza, rcn, rysunki_rcn

ceny_bp = Blueprint(
    "ceny",
    __name__,
    template_folder="templates",
    static_folder="static",
)

MAKS_MIAST = 6
FRAZY = ["mediana cen za 1 m2", "średnia cena lokali", "cena 1 m2 powierzchni użytkowej"]
FRAZY_WYNAGRODZEN = ["przeciętne miesięczne wynagrodzenia brutto", "wynagrodzenia brutto"]  # ETAP 116
USTAWIENIA_ZMIENNYCH = ("zmienna", "wynagrodzenie")  # wskaźnik ceny i (ETAP 116) wynagrodzenia
KOLORY_MIAST = ["#0071e3", "#ff9f0a", "#34c759", "#ff375f", "#5e5ce6", "#8e6e4e"]  # jak KOLORY w ceny.js


def _id_bdl(tekst: str) -> str:
    if len(tekst) != 12 or not tekst.isdigit():
        raise ValueError("Identyfikator jednostki BDL ma 12 cyfr.")
    return tekst


def _zmienna() -> dict | None:
    return baza.ustawienie("zmienna")


def _wymagana_zmienna() -> dict:
    zmienna = _zmienna()
    if zmienna is None:
        raise LookupError("Najpierw wybierz wskaźnik ceny z wyszukiwarki GUS.")
    return zmienna


def podsumowanie() -> dict:
    """Na kartę modułu na stronie głównej: wybrany wskaźnik."""
    zmienna = _zmienna()
    return {"zmienna": zmienna["nazwa"] if zmienna else None}


def _szereg(zmienna_id: int, powiat_id: str) -> list[dict]:
    return baza.z_cache(f"szereg:{zmienna_id}:{powiat_id}", lambda: bdl.szereg_gminy(zmienna_id, powiat_id))


def _powiaty(woj_id: str) -> list[dict]:
    return baza.z_cache(f"powiaty:{woj_id}", lambda: [asdict(p) for p in bdl.powiaty_wojewodztwa(woj_id)])


def _wartosci(zmienna_id: int, rok: int, woj_id: str) -> list[dict]:
    return baza.z_cache(
        f"wartosci:{zmienna_id}:{rok}:{woj_id}", lambda: [asdict(w) for w in bdl.wartosci_dla_powiatow(zmienna_id, rok, woj_id)]
    )


def _obsluz_bledy(funkcja):
    try:
        return funkcja()
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except LookupError as e:
        return jsonify({"blad": str(e)}), 409
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502


@ceny_bp.route("/")
def index():
    return render_template("ceny/index.html", zmienna=_zmienna(), frazy=FRAZY, maks_miast=MAKS_MIAST,
                           wynagrodzenie=baza.ustawienie("wynagrodzenie"), frazy_wynagrodzen=FRAZY_WYNAGRODZEN)


@ceny_bp.route("/zmienne")
def zmienne():
    """Wyszukiwarka zmiennych BDL dostępnych dla powiatów."""
    fraza = " ".join((request.args.get("q") or "").split())
    if len(fraza) < 3:
        return jsonify({"blad": "Wpisz co najmniej 3 znaki."}), 400
    return _obsluz_bledy(lambda: jsonify([asdict(z) for z in bdl.szukaj_zmiennych(fraza, bdl.POZIOM_POWIAT)]))


@ceny_bp.route("/zmienna", methods=["PUT"])
def ustaw_zmienna():
    """JSON {id, rodzaj}: rodzaj „zmienna” (cena, domyślnie) albo „wynagrodzenie” (ETAP 116)."""
    dane = request.get_json(silent=True) or {}
    rodzaj = dane.get("rodzaj") or "zmienna"
    try:
        zmienna_id = int(dane.get("id"))
    except (TypeError, ValueError):
        return jsonify({"blad": "Wymagany numer zmiennej (id)."}), 400
    if rodzaj not in USTAWIENIA_ZMIENNYCH:
        return jsonify({"blad": "Nieznany rodzaj wskaźnika."}), 400

    def zapisz():
        zmienna = asdict(bdl.pobierz_zmienna(zmienna_id))
        baza.zapisz_ustawienie(rodzaj, zmienna)
        return jsonify(zmienna)

    return _obsluz_bledy(zapisz)


@ceny_bp.route("/wojewodztwa")
def wojewodztwa():
    return _obsluz_bledy(lambda: jsonify(baza.z_cache("wojewodztwa", lambda: [asdict(w) for w in bdl.wojewodztwa()])))


@ceny_bp.route("/powiaty/<woj_id>")
def powiaty(woj_id):
    def lista():
        wynik = [{**p, "miasto": analiza.miasto_na_prawach_powiatu(p["teryt"])} for p in _powiaty(_id_bdl(woj_id))]
        return jsonify(sorted(wynik, key=lambda p: (not p["miasto"], p["nazwa"])))  # miasta najpierw

    return _obsluz_bledy(lista)


@ceny_bp.route("/szereg/<powiat_id>")
def szereg(powiat_id):
    def wynik():
        zmienna = _wymagana_zmienna()
        s = _szereg(zmienna["id"], _id_bdl(powiat_id))
        wynik = {"szereg": s, "podsumowanie": analiza.podsumuj(s)}
        rok_bazowy = request.args.get("bazowy", type=int)
        if rok_bazowy is not None:  # ETAP 181: indeks (rok bazowy = 100)
            wynik["indeks"] = analiza.indeks(s, rok_bazowy)
        return jsonify(wynik)

    return _obsluz_bledy(wynik)


@ceny_bp.route("/ranking")
def ranking():
    def wynik():
        zmienna = _wymagana_zmienna()
        woj_id = _id_bdl(request.args.get("woj") or "")
        rok = request.args.get("rok", type=int)
        if rok is None or not 1995 <= rok <= 2100:
            raise ValueError("Podaj rok.")
        return jsonify({"rok": rok, **analiza.ranking(_wartosci(zmienna["id"], rok, woj_id))})

    return _obsluz_bledy(wynik)


@ceny_bp.route("/dostepnosc/<powiat_id>")
def dostepnosc(powiat_id):
    """ETAP 116: m² za przeciętne wynagrodzenie — z dwóch szeregów GUS dla powiatu."""
    def wynik():
        zmienna = _wymagana_zmienna()
        wynagrodzenie = baza.ustawienie("wynagrodzenie")
        if wynagrodzenie is None:
            raise LookupError("Najpierw wybierz wskaźnik wynagrodzenia z wyszukiwarki GUS.")
        powiat = _id_bdl(powiat_id)
        return jsonify(analiza.dostepnosc(_szereg(zmienna["id"], powiat), _szereg(wynagrodzenie["id"], powiat)))

    return _obsluz_bledy(wynik)


def _tabela_porownania() -> tuple[list[list], str]:
    """Szeregi wybranych miast obok siebie (rok; miasto 1; …) i opis źródła — CSV i ODS (ETAP 189)."""
    zmienna = _wymagana_zmienna()
    identyfikatory = [_id_bdl(i) for i in request.args.getlist("id")[:MAKS_MIAST]]
    nazwy = request.args.getlist("nazwa")[: len(identyfikatory)]
    if not identyfikatory:
        raise ValueError("Wybierz co najmniej jedno miasto.")
    szeregi = [{p["rok"]: p["wartosc"] for p in _szereg(zmienna["id"], i)} for i in identyfikatory]
    lata = sorted({rok for s in szeregi for rok in s})
    naglowek = [" ".join(n.split())[:80] for n in nazwy] + identyfikatory[len(nazwy):]
    wiersze = [["rok", *naglowek]] + [[rok, *(s.get(rok, "") for s in szeregi)] for rok in lata]
    return wiersze, f"{zmienna['nazwa']} [{zmienna['jednostka']}]. Źródło: GUS, Bank Danych Lokalnych."


@ceny_bp.route("/porownanie.ods")
def porownanie_ods():
    """ETAP 189: to samo zestawienie co porownanie.csv jako arkusz ODS."""
    from dane.arkusz import arkusz_ods

    def plik():
        wiersze, przypis = _tabela_porownania()
        return Response(arkusz_ods([{"nazwa": "Ceny w czasie", "wiersze": wiersze, "przypisy": [przypis]}]),
                        mimetype="application/vnd.oasis.opendocument.spreadsheet",
                        headers={"Content-Disposition": "attachment; filename=ceny_porownanie.ods"})

    return _obsluz_bledy(plik)


@ceny_bp.route("/porownanie.csv")
def porownanie_csv():
    """Szeregi wybranych miast obok siebie: rok; miasto 1; miasto 2; …"""

    def plik():
        wiersze, przypis = _tabela_porownania()
        bufor = io.StringIO()
        zapis = csv.writer(bufor, delimiter=";")
        zapis.writerows(wiersze)
        zapis.writerow([])
        zapis.writerow([przypis])
        return Response(
            "﻿" + bufor.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=ceny_porownanie.csv"},
        )

    return _obsluz_bledy(plik)


# ---------- raport porównania miast do druku (ETAP 137) ----------


def _wybrane_miasta() -> list[tuple[str, str]]:
    """Parametry id/nazwa jak w CSV → [(bdl_id, nazwa)]; 400 przy złym id."""
    try:
        identyfikatory = [_id_bdl(i) for i in request.args.getlist("id")[:MAKS_MIAST]]
    except ValueError:
        abort(400)
    if not identyfikatory:
        abort(400)
    nazwy = [" ".join(n.split())[:80] for n in request.args.getlist("nazwa")]
    return [(i, nazwy[k] if k < len(nazwy) and nazwy[k] else i) for k, i in enumerate(identyfikatory)]


@ceny_bp.route("/raport")
def raport_miast():
    """Szeregi, zmiany i (gdy wybrano wynagrodzenie) dostępność cenowa
    wybranych miast na jednej stronie do druku. Wszystkie liczby z GUS
    i z ceny/analiza.py; błąd BDL dla jednego miasta nie psuje raportu."""
    zmienna = _zmienna()
    if zmienna is None:
        return redirect(url_for("ceny.index"))
    wynagrodzenie = baza.ustawienie("wynagrodzenie")
    miasta = []
    for k, (bdl_id, nazwa) in enumerate(_wybrane_miasta()):
        miasto = {"id": bdl_id, "nazwa": nazwa, "kolor": KOLORY_MIAST[k % len(KOLORY_MIAST)], "szereg": [], "blad": None, "dostepnosc": None}
        try:
            miasto["szereg"] = _szereg(zmienna["id"], bdl_id)
            if wynagrodzenie:
                miasto["dostepnosc"] = analiza.dostepnosc(miasto["szereg"], _szereg(wynagrodzenie["id"], bdl_id))
        except BladBDL as e:
            miasto["blad"] = str(e)
        miasto["po_roku"] = {p["rok"]: p["wartosc"] for p in miasto["szereg"]}
        miasto["podsumowanie"] = analiza.podsumuj(miasto["szereg"])
        miasta.append(miasto)
    lata = sorted({rok for m in miasta for rok in m["po_roku"]})
    # wykres ten sam co w raporcie transakcji; GUS podaje jedną wartość na rok,
    # więc wszystkie punkty pełne (liczba „transakcji” = próg)
    wykres = rysunki_rcn.wykres_lat_svg({
        "lata": lata, "calosc": {},
        "obszary": [{"kolor": m["kolor"], "lata": m["po_roku"], "lata_liczba": dict.fromkeys(m["po_roku"], rcn.MIN_W_ROKU)} for m in miasta],
    })
    return render_template("ceny/raport_miast.html", zmienna=zmienna, wynagrodzenie=wynagrodzenie, miasta=miasta, lata=lata,
                           wykres=Markup(wykres), powierzchnia_m2=analiza.POWIERZCHNIA_WZORCOWA_M2)  # tylko liczby i kolory z kodu


# ---------- wyszukiwarka globalna (ETAP 128) ----------


def wyszukaj(fraza: str) -> list[dict]:
    """Zaimportowane pliki RCN i narysowane w nich obszary (dzielnice)."""
    szukane = fraza.casefold()
    wyniki = []
    for p in baza.pliki_rcn():
        url = url_for("ceny.transakcje", plik=p["id"])
        if szukane in p["nazwa"].casefold():
            wyniki.append({"tytul": p["nazwa"], "opis": f"plik RCN: {p['liczba']} lokali, {p['liczba_dzialek']} działek", "url": url})
        for o in baza.obszary_rcn(p["id"]):
            if szukane in o["nazwa"].casefold():
                wyniki.append({"tytul": o["nazwa"], "opis": f"obszar porównania w pliku {p['nazwa']}", "url": url})
    return wyniki[:10]


# ---------- ostatnio używane na stronie głównej (ETAP 141) ----------


def ostatnie(limit: int = 3) -> list[dict]:
    """Zaimportowane pliki RCN od najnowszego importu."""
    pliki = sorted(baza.pliki_rcn(), key=lambda p: p["data_importu"], reverse=True)[:limit]
    return [{"tytul": p["nazwa"], "opis": f"transakcje RCN · {p['liczba']} lokali, {p['liczba_dzialek']} działek",
             "kiedy": p["data_importu"], "url": url_for("ceny.transakcje", plik=p["id"])} for p in pliki]


from . import trasy_rcn  # noqa: E402, F401
