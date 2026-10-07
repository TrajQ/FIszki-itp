"""Mapa do druku (ETAP 42): kartogram jako SVG i strona do druku/PDF.

Trasy rejestrują się na wspólnym blueprincie `atlas_bp` (import w
atlas/routes.py na końcu pliku). Dane i parametry liczy ten sam kod co
mapa na ekranie (_policz_dane, _parametry_zapytania).
"""


from flask import Response, jsonify, render_template, request

from dane.bdl import BladBDL

from . import autokorelacja, granice, mapa_svg, statystyki
from .routes import _granice_poziomu, _parametry_klasyfikacji, _parametry_zapytania, _policz_dane, _sasiedzi_wojewodztw, atlas_bp


# ---------- Mapa do druku (ETAP 42) ----------
# Te same palety co w atlas.js — kolory mapy do druku mają odpowiadać mapie
# na ekranie.
KOLORY_KLAS = ["#e3efff", "#b9d8ff", "#86bbff", "#4f97f5", "#1f73de", "#0b53ab", "#06336e"]
KOLORY_ZMIANY = ["#c2410c", "#fb923c", "#d1d1d6", "#60a5fa", "#1d4ed8"]
KOLORY_LISA = {"HH": "#d7191c", "LL": "#2c7bb6", "HL": "#fdae61", "LH": "#abd9e9", "ns": "#e5e5ea"}
TRYBY_MAPY = ("wartosc", "zmiana", "lisa", "gi", "lq")
KOLORY_LQ = ["#2166ac", "#92c5de", "#e5e5ea", "#f4a582", "#b2182b"]  # ETAP 153, jak w atlas.js
# ETAP 152: jak KOLORY_GI w atlas.js
KOLORY_GI = {"H99": "#b2182b", "H95": "#ef8a62", "H90": "#fddbc7", "ns": "#e5e5ea", "C90": "#d1e5f0", "C95": "#67a9cf", "C99": "#2166ac"}


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
        raise ValueError("Tryb mapy: wartosc, zmiana, lisa, gi albo lq.")
    if tryb == "lq" and parametry["mianownik"] is None:
        raise ValueError("Iloraz lokalizacji wymaga wskaźnika względnego (mianownik).")
    if tryb == "zmiana" and parametry["rok_bazowy"] is None:
        raise ValueError("Mapa zmiany wymaga roku porównania (rok_bazowy).")

    wynik = _policz_dane(**parametry)
    if not wynik["gminy"]:
        raise LookupError("Brak danych dla gmin w tym roku.")
    teryt_woj = wynik["wojewodztwo"]["teryt"]
    kolekcja = _granice_poziomu(teryt_woj, parametry["poziom"])  # ETAP 216: gminy albo powiaty
    jednostki = "Powiaty" if parametry["poziom"] == "powiaty" else "Gminy"
    klucz_sasiadow = teryt_woj + (":powiaty" if parametry["poziom"] == "powiaty" else "")
    zmienna = wynik["zmienna"]
    jednostka = zmienna.get("jednostka") or ""
    tytul = zmienna["nazwa"]
    podtytul = f"{jednostki} województwa {wynik['wojewodztwo']['nazwa']}, {wynik['rok']}"
    przypisy = ["Źródło: GUS, Bank Danych Lokalnych; granice: PRG, GUGiK. Opracowanie własne w aplikacji Warsztat."]

    if tryb == "zmiana":
        porownanie = wynik["porownanie"]
        progi = porownanie["progi_zmiany_proc"]
        podtytul = f"Zmiana {porownanie['rok_bazowy']}–{wynik['rok']}, {jednostki.lower()} województwa {wynik['wojewodztwo']['nazwa']}"
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
    elif tryb == "lq":
        lq = wynik["lq"]
        if lq is None:
            raise LookupError("Brak danych do ilorazu lokalizacji.")
        kolory = {g["teryt"]: KOLORY_LQ[g["klasa"]] for g in lq["gminy"]}
        ile = [sum(1 for g in lq["gminy"] if g["klasa"] == i) for i in range(len(KOLORY_LQ))]
        legenda = [(KOLORY_LQ[i], opis, ile[i]) for i, opis in enumerate(lq["opisy"])]
        tytul_legendy = "Iloraz lokalizacji"
        podtytul = f"Iloraz lokalizacji, {jednostki.lower()} województwa {wynik['wojewodztwo']['nazwa']}, {wynik['rok']}"
        udzial = statystyki.format_liczby(round(lq["udzial_wojewodztwa"] * zmienna.get("mnoznik", 1), 3))
        przypisy.append(f"LQ = wskaźnik gminy / wskaźnik województwa ({udzial}); 1 — jak w województwie.")
    elif tryb == "gi":
        teryt_sasiedzi = _sasiedzi_wojewodztw.get(klucz_sasiadow) or autokorelacja.sasiedzi(kolekcja)
        _sasiedzi_wojewodztw[klucz_sasiadow] = teryt_sasiedzi
        analiza = autokorelacja.analiza({g["teryt"]: g["wartosc"] for g in wynik["gminy"]}, teryt_sasiedzi)
        kolory = {g["teryt"]: KOLORY_GI[g["kategoria"]] for g in analiza["gi"]}
        ile = {k: 0 for k in KOLORY_GI}
        for g in analiza["gi"]:
            ile[g["kategoria"]] += 1
        legenda = [(KOLORY_GI[k], analiza["kategorie_gi"][k], ile[k]) for k in KOLORY_GI]
        tytul_legendy = "Gorące i zimne punkty Gi*"
        przypisy.append("Getis-Ord Gi*: wagi binarne z samą gminą, sąsiedztwo queen; z-score, progi 90/95/99%.")
    elif tryb == "lisa":
        teryt_sasiedzi = _sasiedzi_wojewodztw.get(klucz_sasiadow) or autokorelacja.sasiedzi(kolekcja)
        _sasiedzi_wojewodztw[klucz_sasiadow] = teryt_sasiedzi
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


MAKS_LAT_MAP = 6


def _lata_z_zapytania(argumenty) -> list[int]:
    try:
        lata = sorted({int(r) for r in (argumenty.get("lata") or "").replace(";", ",").split(",") if r.strip()})
    except ValueError:
        raise ValueError("Lata: liczby po przecinku, np. 2014,2018,2023.") from None
    if not 2 <= len(lata) <= MAKS_LAT_MAP or not all(1995 <= r <= 2100 for r in lata):
        raise ValueError(f"Wybierz od 2 do {MAKS_LAT_MAP} lat.")
    return lata


def _wyniki_w_latach(argumenty, lata: list[int]) -> dict:
    """Ten sam wskaźnik w kilku latach i WSPÓLNE klasy z wartości wszystkich
    lat razem — kolor znaczy to samo w każdym roku (ETAP 161; wydzielone w
    ETAPie 235 dla odtwarzania lat na mapie)."""
    metoda, liczba_klas = _parametry_klasyfikacji(argumenty)
    wyniki = {}
    for rok in lata:
        parametry = _parametry_zapytania({**argumenty.to_dict(), "rok": str(rok)})
        parametry["rok_bazowy"] = None
        wynik = _policz_dane(**parametry)
        if wynik["gminy"]:
            wyniki[rok] = wynik
    if len(wyniki) < 2:
        raise LookupError("Dane GUS są tylko dla jednego z wybranych lat (albo żadnego) — wybierz inne lata.")
    wszystkie = [g["wartosc"] for w in wyniki.values() for g in w["gminy"]]
    k = statystyki.klasyfikuj(wszystkie, metoda, liczba_klas)
    liczba = len(k["progi"]) + 1
    granice_klas = [min(wszystkie), *k["progi"], max(wszystkie)]
    legenda = [(_kolor_klasy(i, liczba), f"{statystyki.format_liczby(round(granice_klas[i], 2))} – {statystyki.format_liczby(round(granice_klas[i + 1], 2))}", None)
               for i in range(liczba)]
    return {
        "wyniki": wyniki,
        "klasyfikacja": k,
        "kolory": {rok: {g["teryt"]: _kolor_klasy(_numer_klasy(g["wartosc"], k["progi"]), liczba) for g in w["gminy"]} for rok, w in wyniki.items()},
        "legenda": legenda,
        "liczba_klas": liczba,
        "brakujace": [r for r in lata if r not in wyniki],
    }


def _mapy_w_latach(argumenty) -> tuple[str, dict]:
    """ETAP 161: ten sam wskaźnik w kilku latach — małe mapy we wspólnych klasach."""
    lata = _lata_z_zapytania(argumenty)
    w = _wyniki_w_latach(argumenty, lata)
    wyniki, k, liczba, brakujace = w["wyniki"], w["klasyfikacja"], w["liczba_klas"], w["brakujace"]
    pierwszy = next(iter(wyniki.values()))
    mapy = [(str(rok), kolory) for rok, kolory in w["kolory"].items()]
    legenda = [*w["legenda"], (mapa_svg.KOLOR_BRAK, "brak danych", None)]
    zmienna = pierwszy["zmienna"]
    przypisy = ["Źródło: GUS, Bank Danych Lokalnych; granice: PRG, GUGiK. Opracowanie własne w aplikacji Warsztat.",
                f"Klasyfikacja: {k['nazwa_metody']}, {liczba} klas wspólnych dla wszystkich lat (z wartości gmin ze wszystkich map)."]
    if brakujace:
        przypisy.append(f"Bez danych GUS w latach: {', '.join(map(str, brakujace))} — pominięte.")
    kolekcja = _granice_poziomu(pierwszy["wojewodztwo"]["teryt"], pierwszy["poziom"])
    jednostki = "Powiaty" if pierwszy["poziom"] == "powiaty" else "Gminy"
    svg = mapa_svg.male_mapy_svg(kolekcja, mapy, zmienna["nazwa"], f"{jednostki} województwa {pierwszy['wojewodztwo']['nazwa']}, {', '.join(map(str, wyniki))}",
                                 legenda, zmienna.get("jednostka") or "Wartość", przypisy)
    return svg, pierwszy


@atlas_bp.route("/lata.svg")
def mapy_w_latach_svg():
    try:
        svg, wynik = _mapy_w_latach(request.args)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404
    except (BladBDL, granice.BladGranic) as e:
        return jsonify({"blad": str(e)}), 502
    naglowki = {}
    if request.args.get("pobierz"):
        naglowki["Content-Disposition"] = f"attachment; filename=lata_{wynik['wojewodztwo']['teryt']}_{request.args.get('lata', '').replace(',', '-')}.svg"
    return Response(svg, mimetype="image/svg+xml", headers=naglowki)


MAKS_LAT_ODTWARZANIA = 15


@atlas_bp.route("/odtwarzanie")
def odtwarzanie_lat():
    """ETAP 235: wskaźnik rok po roku do odtwarzania na mapie — kolory
    gmin w każdym roku we wspólnych klasach (jak „Mapy w latach”) i
    wartości do dymków. Lata: od–do (?od=2014&do=2023), najwyżej 15."""
    try:
        od, do = int(request.args.get("od", "")), int(request.args.get("do", ""))
    except ValueError:
        return jsonify({"blad": "Podaj lata od i do."}), 400
    if not (1995 <= od < do <= 2100) or do - od + 1 > MAKS_LAT_ODTWARZANIA:
        return jsonify({"blad": f"Od 2 do {MAKS_LAT_ODTWARZANIA} kolejnych lat."}), 400
    try:
        w = _wyniki_w_latach(request.args, list(range(od, do + 1)))
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify({
        "lata": list(w["wyniki"]),
        "kolory": {str(r): k for r, k in w["kolory"].items()},
        "wartosci": {str(r): {g["teryt"]: g["wartosc"] for g in wynik["gminy"]} for r, wynik in w["wyniki"].items()},
        "legenda": [[kolor, opis] for kolor, opis, _ in w["legenda"]],
        "klasyfikacja": w["klasyfikacja"]["nazwa_metody"],
        "brakujace": w["brakujace"],
    })


@atlas_bp.route("/lata")
def mapy_w_latach():
    """Strona: wybór lat i podgląd arkusza z małymi mapami (ETAP 161)."""
    parametry = request.args.to_dict()
    parametry.pop("pobierz", None)
    rok = request.args.get("rok", type=int)
    if "lata" not in parametry and rok:
        parametry["lata"] = ",".join(str(r) for r in (rok - 9, rok - 6, rok - 3, rok))
    return render_template("atlas/lata.html", parametry=parametry)


@atlas_bp.route("/druk")
def druk():
    """Strona z mapą do druku: podgląd, „Drukuj / zapisz PDF”, „Pobierz SVG”."""
    parametry = request.args.to_dict()
    parametry.pop("pobierz", None)
    return render_template("atlas/druk.html", parametry=parametry)
