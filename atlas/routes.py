import csv
import io
import json
import os
import statistics
from dataclasses import asdict

from flask import Blueprint, Response, jsonify, render_template, request

from dane import bdl
from dane.bdl import BladBDL
from dane.gemini import BladGemini, opisz_wskaznik

from . import autokorelacja, granice, statystyki
from .baza import folder_modulu, z_cache

atlas_bp = Blueprint(
    "atlas",
    __name__,
    template_folder="templates",
    static_folder="static",
)

MIN_DLUGOSC_FRAZY = 3


@atlas_bp.route("/")
def index():
    return render_template("atlas/index.html")


@atlas_bp.route("/zmienne")
def zmienne():
    fraza = (request.args.get("q") or "").strip()
    if len(fraza) < MIN_DLUGOSC_FRAZY:
        return jsonify({"blad": f"Wpisz co najmniej {MIN_DLUGOSC_FRAZY} znaki."}), 400
    try:
        wyniki = z_cache(
            f"zmienne:{fraza.lower()}",
            lambda: [asdict(z) for z in bdl.szukaj_zmiennych(fraza)],
        )
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify(wyniki)


@atlas_bp.route("/wojewodztwa")
def wojewodztwa():
    try:
        return jsonify(_wojewodztwa())
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502


@atlas_bp.route("/dane")
def dane():
    try:
        parametry = _parametry_zapytania(request.args)
        metoda, liczba_klas = _parametry_klasyfikacji(request.args)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    try:
        wynik = _policz_dane(**parametry)
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404
    wynik["klasyfikacja"] = statystyki.klasyfikuj([g["wartosc"] for g in wynik["gminy"]], metoda, liczba_klas)
    return jsonify(wynik)


def _parametry_klasyfikacji(zrodlo) -> tuple[str, int]:
    metoda = zrodlo.get("metoda") or "kwantyle"
    try:
        liczba_klas = int(zrodlo.get("klasy") or statystyki.LICZBA_KLAS)
    except ValueError:
        raise ValueError("Liczba klas musi być liczbą.")
    if metoda not in statystyki.METODY_KLASYFIKACJI:
        raise ValueError("Nieznana metoda klasyfikacji.")
    if not statystyki.MIN_KLAS <= liczba_klas <= statystyki.MAKS_KLAS:
        raise ValueError(f"Liczba klas od {statystyki.MIN_KLAS} do {statystyki.MAKS_KLAS}.")
    return metoda, liczba_klas


@atlas_bp.route("/klasy")
def klasy():
    """Podział na klasy inną metodą albo liczbą klas — bez przeładowania
    całych danych (wartości biorą się z cache BDL)."""
    try:
        parametry = _parametry_zapytania(request.args)
        metoda, liczba_klas = _parametry_klasyfikacji(request.args)
        wartosci = [
            g["wartosc"]
            for g in _wartosci_wskaznika(
                parametry["zmienna_id"], parametry["rok"], parametry["woj_bdl_id"], parametry["mianownik"], parametry["mnoznik"]
            )
        ]
        return jsonify(statystyki.klasyfikuj(wartosci, metoda, liczba_klas))
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502


# Sąsiedztwo gmin województwa liczy się z granic raz na uruchomienie aplikacji.
_sasiedzi_wojewodztw: dict[str, dict] = {}


@atlas_bp.route("/autokorelacja")
def autokorelacja_przestrzenna():
    """I Morana i klastry LISA dla wskaźnika z mapy (ETAP 41)."""
    try:
        parametry = _parametry_zapytania(request.args)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    wojewodztwo = next((w for w in _wojewodztwa() if w["bdl_id"] == parametry["woj_bdl_id"]), None)
    if wojewodztwo is None:
        return jsonify({"blad": "Nie znaleziono takiego województwa w BDL."}), 404
    try:
        gminy = _wartosci_wskaznika(
            parametry["zmienna_id"], parametry["rok"], parametry["woj_bdl_id"], parametry["mianownik"], parametry["mnoznik"]
        )
        teryt = wojewodztwo["teryt"]
        if teryt not in _sasiedzi_wojewodztw:
            kolekcja = granice.granice_gmin(teryt, os.path.join(folder_modulu(), "granice"))
            _sasiedzi_wojewodztw[teryt] = autokorelacja.sasiedzi(kolekcja)
        wynik = autokorelacja.analiza({g["teryt"]: g["wartosc"] for g in gminy}, _sasiedzi_wojewodztw[teryt])
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    except granice.BladGranic as e:
        return jsonify({"blad": f"Autokorelacja wymaga granic gmin: {e}"}), 502
    except ValueError as e:
        return jsonify({"blad": str(e)}), 422
    return jsonify(wynik)


@atlas_bp.route("/gmina/<gmina_bdl_id>")
def profil_gminy(gmina_bdl_id):
    """Szereg czasowy wskaźnika dla jednej gminy (wykres w profilu gminy)."""
    try:
        zmienna_id = int(request.args.get("zmienna", ""))
    except ValueError:
        return jsonify({"blad": "Wymagany parametr zmienna (liczba)."}), 400
    if len(gmina_bdl_id) != 12 or not gmina_bdl_id.isdigit():
        return jsonify({"blad": "Identyfikator gminy BDL ma 12 cyfr."}), 400

    try:
        wzgledne = _parametry_wzgledne(request.args, zmienna_id)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400

    def szereg_zmiennej(zid):
        return z_cache(f"szereg:{zid}:{gmina_bdl_id}", lambda: bdl.szereg_gminy(zid, gmina_bdl_id))

    try:
        szereg = szereg_zmiennej(zmienna_id)
        if wzgledne["mianownik"] is not None:
            szereg = statystyki.podziel_szeregi(szereg, szereg_zmiennej(wzgledne["mianownik"]), wzgledne["mnoznik"])
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify({"szereg": szereg, "zmiana": statystyki.zmiana_w_szeregu(szereg)})


@atlas_bp.route("/granice/<teryt_woj>")
def granice_wojewodztwa(teryt_woj):
    if len(teryt_woj) != 2 or not teryt_woj.isdigit():
        return jsonify({"blad": "Kod TERYT województwa to dwie cyfry."}), 400
    try:
        kolekcja = granice.granice_gmin(teryt_woj, os.path.join(folder_modulu(), "granice"))
    except granice.BladGranic as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify(kolekcja)


@atlas_bp.route("/tlo-wojewodztw")
def tlo_wojewodztw():
    """Granice wszystkich województw — tło mapy zamiast kafelków OSM."""
    try:
        kolekcja = granice.granice_wojewodztw(os.path.join(folder_modulu(), "granice"))
    except granice.BladGranic as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify(kolekcja)


@atlas_bp.route("/opis", methods=["POST"])
def opis():
    """Opis przez Gemini. Liczby liczymy tu, na serwerze, z danych BDL —
    nie przyjmujemy ich od przeglądarki."""
    try:
        parametry = _parametry_zapytania(request.get_json(silent=True) or {})
        wynik = _policz_dane(**parametry)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404

    if wynik["statystyki"]["liczba_gmin"] == 0:
        return jsonify({"blad": "Brak danych do opisania."}), 404

    fakty = statystyki.fakty_do_opisu(
        wynik["zmienna"], wynik["rok"], wynik["wojewodztwo"]["nazwa"], wynik["statystyki"]
    )
    if "porownanie" in wynik:
        fakty += statystyki.fakty_zmiany(
            wynik["porownanie"]["rok_bazowy"], wynik["rok"], wynik["porownanie"]["statystyki"]
        )
    try:
        tekst = opisz_wskaznik(fakty)
    except BladGemini as e:
        return jsonify({"blad": str(e), "fakty": fakty}), 502
    return jsonify({"opis": tekst, "fakty": fakty})


def _parametry_zapytania(zrodlo) -> dict:
    try:
        zmienna_id = int(zrodlo.get("zmienna"))
        rok = int(zrodlo.get("rok"))
    except (TypeError, ValueError):
        raise ValueError("Wymagane parametry: zmienna (liczba) i rok (liczba).")
    woj = str(zrodlo.get("woj") or "")
    if len(woj) != 12 or not woj.isdigit():
        raise ValueError("Parametr woj musi być 12-cyfrowym identyfikatorem BDL województwa.")
    if not 1995 <= rok <= 2100:
        raise ValueError("Niepoprawny rok.")

    rok_bazowy = zrodlo.get("rok_bazowy")
    if rok_bazowy in (None, ""):
        rok_bazowy = None
    else:
        try:
            rok_bazowy = int(rok_bazowy)
        except (TypeError, ValueError):
            raise ValueError("rok_bazowy musi być liczbą.")
        if rok_bazowy >= rok:
            raise ValueError("Rok bazowy musi być wcześniejszy niż rok badany.")
    return {"zmienna_id": zmienna_id, "rok": rok, "woj_bdl_id": woj, "rok_bazowy": rok_bazowy, **_parametry_wzgledne(zrodlo, zmienna_id)}


def _parametry_wzgledne(zrodlo, zmienna_id: int) -> dict:
    """Opcjonalny wskaźnik względny: mianownik (id zmiennej) i mnożnik."""
    mianownik = zrodlo.get("mianownik")
    if mianownik in (None, ""):
        return {"mianownik": None, "mnoznik": 1}
    try:
        mianownik = int(mianownik)
        mnoznik = int(zrodlo.get("mnoznik") or 1000)
    except (TypeError, ValueError):
        raise ValueError("mianownik i mnoznik muszą być liczbami.")
    if mianownik == zmienna_id:
        raise ValueError("Mianownik musi być innym wskaźnikiem niż licznik.")
    if mnoznik not in statystyki.DOZWOLONE_MNOZNIKI:
        raise ValueError("Mnożnik: 1, 100, 1000 albo 10000.")
    return {"mianownik": mianownik, "mnoznik": mnoznik}


def _opis_zmiennej(zmienna_id: int, mianownik: int | None, mnoznik: int) -> dict:
    zmienna = z_cache(f"zmienna:{zmienna_id}", lambda: asdict(bdl.pobierz_zmienna(zmienna_id)))
    if mianownik is None:
        return zmienna
    mian = z_cache(f"zmienna:{mianownik}", lambda: asdict(bdl.pobierz_zmienna(mianownik)))
    na = "" if mnoznik == 1 else f"{mnoznik:,}".replace(",", " ") + " "
    return {
        "id": zmienna["id"],
        "nazwa": f"{zmienna['nazwa']} na {na}({mian['nazwa']})",
        "jednostka": f"{zmienna['jednostka'] or '–'} / {na}{mian['jednostka'] or '–'}",
        "mianownik": mian,
        "mnoznik": mnoznik,
    }


def _wartosci_wskaznika(zmienna_id: int, rok: int, woj_bdl_id: str, mianownik: int | None, mnoznik: int) -> list[dict]:
    gminy = _wartosci(zmienna_id, rok, woj_bdl_id)
    if mianownik is None:
        return gminy
    return statystyki.podziel(gminy, _wartosci(mianownik, rok, woj_bdl_id), mnoznik)


def _wojewodztwa() -> list[dict]:
    return z_cache("wojewodztwa", lambda: [asdict(j) for j in bdl.wojewodztwa()])


def _wartosci(zmienna_id: int, rok: int, woj_bdl_id: str) -> list[dict]:
    return z_cache(
        f"dane:{zmienna_id}:{rok}:{woj_bdl_id}",
        lambda: [asdict(w) for w in bdl.wartosci_dla_gmin(zmienna_id, rok, woj_bdl_id)],
    )


def _policz_dane(
    zmienna_id: int,
    rok: int,
    woj_bdl_id: str,
    rok_bazowy: int | None = None,
    mianownik: int | None = None,
    mnoznik: int = 1,
) -> dict:
    wojewodztwo = next((w for w in _wojewodztwa() if w["bdl_id"] == woj_bdl_id), None)
    if wojewodztwo is None:
        raise LookupError("Nie znaleziono takiego województwa w BDL.")

    zmienna = _opis_zmiennej(zmienna_id, mianownik, mnoznik)
    gminy = sorted(
        _wartosci_wskaznika(zmienna_id, rok, woj_bdl_id, mianownik, mnoznik),
        key=lambda g: g["wartosc"],
        reverse=True,
    )

    wynik = {
        "zmienna": zmienna,
        "rok": rok,
        "wojewodztwo": wojewodztwo,
        "gminy": gminy,
        "statystyki": statystyki.statystyki(gminy),
        "progi_klas": statystyki.progi_klas([g["wartosc"] for g in gminy]),
        "klasyfikacja": statystyki.klasyfikuj([g["wartosc"] for g in gminy]),
    }
    if rok_bazowy is not None:
        porownanie = statystyki.porownaj(
            gminy, _wartosci_wskaznika(zmienna_id, rok_bazowy, woj_bdl_id, mianownik, mnoznik)
        )
        wynik["porownanie"] = {
            "rok_bazowy": rok_bazowy,
            "gminy": porownanie,
            "statystyki": statystyki.statystyki_zmiany(porownanie),
            "progi_zmiany_proc": statystyki.PROGI_ZMIANY_PROC,
        }
    return wynik


# ---------- Na tle kraju: porównanie województw (ETAP 52) ----------


def _wartosci_wojewodztw(zmienna_id: int, rok: int) -> list[dict]:
    return z_cache(
        f"woj:{zmienna_id}:{rok}",
        lambda: [asdict(w) for w in bdl.wartosci_dla_wojewodztw(zmienna_id, rok)],
    )


@atlas_bp.route("/wojewodztwa-porownanie")
def wojewodztwa_porownanie():
    """Ten sam wskaźnik (i rok) dla wszystkich województw — ranking z
    wyróżnionym województwem z mapy. Wskaźnik względny też działa."""
    try:
        parametry = _parametry_zapytania(request.args)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    try:
        wartosci = _wartosci_wojewodztw(parametry["zmienna_id"], parametry["rok"])
        if parametry["mianownik"] is not None:
            wartosci = statystyki.podziel(
                wartosci, _wartosci_wojewodztw(parametry["mianownik"], parametry["rok"]), parametry["mnoznik"]
            )
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    if not wartosci:
        return jsonify({"blad": "BDL nie ma tego wskaźnika na poziomie województw w tym roku."}), 404

    ranking = sorted(wartosci, key=lambda w: w["wartosc"], reverse=True)
    for miejsce, w in enumerate(ranking, start=1):
        w["miejsce"] = miejsce
        w["wybrane"] = w["bdl_id"] == parametry["woj_bdl_id"]
    liczby = [w["wartosc"] for w in ranking]
    return jsonify(
        {
            "rok": parametry["rok"],
            "wojewodztwa": ranking,
            "mediana": statistics.median(liczby),
            "wybrane": next((w for w in ranking if w["wybrane"]), None),
        }
    )


@atlas_bp.route("/korelacja")
def korelacja():
    """Korelacja wskaźnika z mapy (zmienna) z drugim (zmienna2) w tym samym
    roku i województwie. Liczby liczy atlas/statystyki.py."""
    try:
        parametry = _parametry_zapytania(request.args)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    try:
        zmienna2 = int(request.args.get("zmienna2", ""))
    except ValueError:
        return jsonify({"blad": "Wymagany parametr zmienna2 (liczba)."}), 400
    if zmienna2 == parametry["zmienna_id"]:
        return jsonify({"blad": "Wybierz inny wskaźnik niż ten na mapie."}), 400
    try:
        gminy_x = _wartosci_wskaznika(
            parametry["zmienna_id"], parametry["rok"], parametry["woj_bdl_id"], parametry["mianownik"], parametry["mnoznik"]
        )
        gminy_y = _wartosci(zmienna2, parametry["rok"], parametry["woj_bdl_id"])
        zmienna_x = _opis_zmiennej(parametry["zmienna_id"], parametry["mianownik"], parametry["mnoznik"])
        zmienna_y = z_cache(f"zmienna:{zmienna2}", lambda: asdict(bdl.pobierz_zmienna(zmienna2)))
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    wynik = statystyki.korelacja(gminy_x, gminy_y)
    wynik.update(zmienna_x=zmienna_x, zmienna_y=zmienna_y, rok=parametry["rok"])
    return jsonify(wynik)


@atlas_bp.route("/eksport.geojson")
def eksport_geojson():
    """Kartogram do QGIS: granice gmin + wartości (i zmiana, jeśli porównanie)."""
    try:
        parametry = _parametry_zapytania(request.args)
        wynik = _policz_dane(**parametry)
        kolekcja = granice.granice_gmin(
            wynik["wojewodztwo"]["teryt"], os.path.join(folder_modulu(), "granice")
        )
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except (BladBDL, granice.BladGranic) as e:
        return jsonify({"blad": str(e)}), 502
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404

    wartosci = {g["teryt"]: g for g in wynik["gminy"]}
    zmiany = {g["teryt"]: g for g in wynik.get("porownanie", {}).get("gminy", [])}
    cechy = []
    for cecha in kolekcja["features"]:
        teryt = cecha["properties"]["teryt"]
        wlasciwosci = {
            "teryt": teryt,
            "gmina": cecha["properties"]["nazwa"],
            "wartosc": wartosci.get(teryt, {}).get("wartosc"),
            "rok": wynik["rok"],
            "wskaznik": wynik["zmienna"]["nazwa"],
            "jednostka": wynik["zmienna"]["jednostka"],
        }
        if "porownanie" in wynik:
            z = zmiany.get(teryt, {})
            wlasciwosci.update(
                rok_bazowy=wynik["porownanie"]["rok_bazowy"],
                wartosc_bazowa=z.get("wartosc_bazowa"),
                zmiana=z.get("zmiana"),
                zmiana_proc=z.get("zmiana_proc"),
            )
        cechy.append({"type": "Feature", "properties": wlasciwosci, "geometry": cecha["geometry"]})

    nazwa = f"atlas_{parametry['zmienna_id']}_{wynik['wojewodztwo']['teryt']}_{wynik['rok']}.geojson"
    return _plik_geojson({"type": "FeatureCollection", "features": cechy}, nazwa)


def _plik_geojson(kolekcja: dict, nazwa: str) -> Response:
    return Response(
        json.dumps(kolekcja, ensure_ascii=False),
        mimetype="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )


@atlas_bp.route("/eksport.csv")
def eksport_csv():
    """Tabela gmin do arkusza (UTF-8 z BOM — polskie znaki w LibreOffice/Excelu)."""
    try:
        parametry = _parametry_zapytania(request.args)
        wynik = _policz_dane(**parametry)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except BladBDL as e:
        return jsonify({"blad": str(e)}), 502
    except LookupError as e:
        return jsonify({"blad": str(e)}), 404

    bufor = io.StringIO()
    zapis = csv.writer(bufor)
    rok = wynik["rok"]
    if "porownanie" in wynik:
        rb = wynik["porownanie"]["rok_bazowy"]
        zapis.writerow(["teryt", "gmina", f"wartosc_{rb}", f"wartosc_{rok}", "zmiana", "zmiana_proc"])
        for g in wynik["porownanie"]["gminy"]:
            proc = "" if g["zmiana_proc"] is None else round(g["zmiana_proc"], 2)
            zapis.writerow([g["teryt"], g["nazwa"], g["wartosc_bazowa"], g["wartosc"], g["zmiana"], proc])
    else:
        zapis.writerow(["teryt", "gmina", f"wartosc_{rok}"])
        for g in wynik["gminy"]:
            zapis.writerow([g["teryt"], g["nazwa"], g["wartosc"]])

    nazwa = f"atlas_{parametry['zmienna_id']}_{wynik['wojewodztwo']['teryt']}_{rok}.csv"
    return Response(
        bufor.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )


# Mapa do druku i raport gminy — w osobnych plikach, rejestrują się na atlas_bp.
# Import na końcu, bo tamten plik importuje atlas_bp z tego modułu.
from . import trasy_druk, trasy_raport, trasy_zlozony  # noqa: E402, F401
