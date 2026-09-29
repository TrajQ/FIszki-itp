"""Mapa do druku (ETAP 42): kartogram jako SVG i strona do druku/PDF.

Trasy rejestrują się na wspólnym blueprincie `atlas_bp` (import w
atlas/routes.py na końcu pliku). Dane i parametry liczy ten sam kod co
mapa na ekranie (_policz_dane, _parametry_zapytania).
"""

import os

from flask import Response, jsonify, render_template, request

from dane.bdl import BladBDL

from . import autokorelacja, granice, mapa_svg, statystyki
from .baza import folder_modulu
from .routes import _parametry_klasyfikacji, _parametry_zapytania, _policz_dane, _sasiedzi_wojewodztw, atlas_bp


# ---------- Mapa do druku (ETAP 42) ----------
# Te same palety co w atlas.js — kolory mapy do druku mają odpowiadać mapie
# na ekranie.
KOLORY_KLAS = ["#e3efff", "#b9d8ff", "#86bbff", "#4f97f5", "#1f73de", "#0b53ab", "#06336e"]
KOLORY_ZMIANY = ["#c2410c", "#fb923c", "#d1d1d6", "#60a5fa", "#1d4ed8"]
KOLORY_LISA = {"HH": "#d7191c", "LL": "#2c7bb6", "HL": "#fdae61", "LH": "#abd9e9", "ns": "#e5e5ea"}
TRYBY_MAPY = ("wartosc", "zmiana", "lisa")


def _numer_klasy(wartosc: float, progi: list[float]) -> int:
    i = 0
    while i < len(progi) and wartosc > progi[i]:
        i += 1
    return i


def _kolor_klasy(i: int, liczba_klas: int) -> str:
    # jak w atlas.js: przy mniejszej liczbie klas kolory z całej skali
    if liczba_klas == 1:
        return KOLORY_KLAS[-1]
    return KOLORY_KLAS[round(i * (len(KOLORY_KLAS) - 1) / (liczba_klas - 1))]


def _procent(liczba: float) -> str:
    return ("+" if liczba > 0 else "") + statystyki.format_liczby(round(liczba, 1)) + "%"


def _mapa_do_druku(argumenty) -> tuple[str, dict]:
    """(SVG, wynik danych) dla parametrów jak w /dane + tryb, metoda, klasy."""
    parametry = _parametry_zapytania(argumenty)
    metoda, liczba_klas = _parametry_klasyfikacji(argumenty)
    tryb = argumenty.get("tryb") or "wartosc"
    if tryb not in TRYBY_MAPY:
        raise ValueError("Tryb mapy: wartosc, zmiana albo lisa.")
    if tryb == "zmiana" and parametry["rok_bazowy"] is None:
        raise ValueError("Mapa zmiany wymaga roku porównania (rok_bazowy).")

    wynik = _policz_dane(**parametry)
    if not wynik["gminy"]:
        raise LookupError("Brak danych dla gmin w tym roku.")
    teryt_woj = wynik["wojewodztwo"]["teryt"]
    kolekcja = granice.granice_gmin(teryt_woj, os.path.join(folder_modulu(), "granice"))
    zmienna = wynik["zmienna"]
    jednostka = zmienna.get("jednostka") or ""
    tytul = zmienna["nazwa"]
    podtytul = f"Gminy województwa {wynik['wojewodztwo']['nazwa']}, {wynik['rok']}"
    przypisy = ["Źródło: GUS, Bank Danych Lokalnych; granice: PRG, GUGiK. Opracowanie własne w aplikacji Warsztat."]

    if tryb == "zmiana":
        porownanie = wynik["porownanie"]
        progi = porownanie["progi_zmiany_proc"]
        podtytul = f"Zmiana {porownanie['rok_bazowy']}–{wynik['rok']}, gminy województwa {wynik['wojewodztwo']['nazwa']}"
        kolory = {
            g["teryt"]: KOLORY_ZMIANY[_numer_klasy(g["zmiana_proc"], progi)]
            for g in porownanie["gminy"]
            if g.get("zmiana_proc") is not None
        }
        opisy = [f"≤ {_procent(progi[0])}"] + [
            f"{_procent(progi[i - 1])} … {_procent(progi[i])}" for i in range(1, len(progi))
        ] + [f"> {_procent(progi[-1])}"]
        liczebnosci = statystyki.liczebnosci_klas(
            [g["zmiana_proc"] for g in porownanie["gminy"] if g.get("zmiana_proc") is not None], progi
        )
        legenda = [(KOLORY_ZMIANY[i], opis, liczebnosci[i]) for i, opis in enumerate(opisy)]
        tytul_legendy = "Zmiana wartości"
    elif tryb == "lisa":
        teryt_sasiedzi = _sasiedzi_wojewodztw.get(teryt_woj) or autokorelacja.sasiedzi(kolekcja)
        _sasiedzi_wojewodztw[teryt_woj] = teryt_sasiedzi
        analiza = autokorelacja.analiza({g["teryt"]: g["wartosc"] for g in wynik["gminy"]}, teryt_sasiedzi)
        kolory = {l["teryt"]: KOLORY_LISA[l["kategoria"]] for l in analiza["lisa"]}
        ile = {k: 0 for k in KOLORY_LISA}
        for l in analiza["lisa"]:
            ile[l["kategoria"]] += 1
        legenda = [(KOLORY_LISA[k], analiza["kategorie"][k], ile[k]) for k in ("HH", "LL", "HL", "LH", "ns")]
        tytul_legendy = "Klastry LISA (p < 0,05)"
        przypisy.append(
            f"I Morana = {analiza['moran_i']:.3f}, p = {analiza['p']:.3f} ".replace(".", ",")
            + f"({analiza['permutacje']} permutacji), sąsiedztwo queen."
        )
    else:
        k = statystyki.klasyfikuj([g["wartosc"] for g in wynik["gminy"]], metoda, liczba_klas)
        granice_klas = [wynik["statystyki"]["min"]["wartosc"], *k["progi"], wynik["statystyki"]["max"]["wartosc"]]
        liczba = len(k["progi"]) + 1
        kolory = {g["teryt"]: _kolor_klasy(_numer_klasy(g["wartosc"], k["progi"]), liczba) for g in wynik["gminy"]}
        legenda = [
            (
                _kolor_klasy(i, liczba),
                f"{statystyki.format_liczby(round(granice_klas[i], 2))} – {statystyki.format_liczby(round(granice_klas[i + 1], 2))}",
                k["liczebnosci"][i],
            )
            for i in range(liczba)
        ]
        tytul_legendy = jednostka or "Wartość"
        gvf = "" if k["gvf"] is None else f", GVF = {statystyki.format_liczby(round(k['gvf'], 2))}"
        przypisy.append(f"Klasyfikacja: {k['nazwa_metody']}, {liczba} klas{gvf}.")

    if any(teryt not in kolory for teryt in (c["properties"]["teryt"] for c in kolekcja["features"])):
        legenda.append((mapa_svg.KOLOR_BRAK, "brak danych", None))
    svg = mapa_svg.kartogram_svg(kolekcja, kolory, tytul, podtytul, legenda, tytul_legendy, przypisy)
    return svg, wynik


@atlas_bp.route("/mapa.svg")
def mapa_do_druku_svg():
    try:
        svg, wynik = _mapa_do_druku(request.args)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404
    except (BladBDL, granice.BladGranic) as e:
        return jsonify({"blad": str(e)}), 502
    naglowki = {}
    if request.args.get("pobierz"):
        nazwa = f"kartogram_{wynik['wojewodztwo']['teryt']}_{wynik['rok']}_{request.args.get('tryb') or 'wartosc'}.svg"
        naglowki["Content-Disposition"] = f"attachment; filename={nazwa}"
    return Response(svg, mimetype="image/svg+xml", headers=naglowki)


@atlas_bp.route("/druk")
def druk():
    """Strona z mapą do druku: podgląd, „Drukuj / zapisz PDF”, „Pobierz SVG”."""
    parametry = request.args.to_dict()
    parametry.pop("pobierz", None)
    return render_template("atlas/druk.html", parametry=parametry)
