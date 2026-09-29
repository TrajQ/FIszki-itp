import json
import os

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from . import wyniki as wyniki_h3
from .wyniki import BladWynikow

dostepnosc_bp = Blueprint(
    "dostepnosc",
    __name__,
    template_folder="templates",
    static_folder="static",
)

FOLDER_PRZYKLADU = os.path.join(os.path.dirname(__file__), "przyklad")
PLIK_PRZYKLADU = "przyklad_poznan_syntetyczny.csv"
# Drugi przykład: ten sam obszar po „budowie” nowej szkoły — do porównania scenariuszy.
PLIK_PRZYKLADU_SCENARIUSZ = "przyklad_poznan_nowa_szkola_syntetyczny.csv"
PLIKI_PRZYKLADOWE = (PLIK_PRZYKLADU, PLIK_PRZYKLADU_SCENARIUSZ)

# Wczytane pliki trzymamy w pamięci; klucz zawiera czas modyfikacji,
# więc podmieniony plik zostanie wczytany od nowa.
_cache: dict[tuple[str, float], dict] = {}


def _folder_wynikow() -> str:
    folder = os.path.join(current_app.instance_path, "dostepnosc", "wyniki")
    os.makedirs(folder, exist_ok=True)
    return folder


def _sciezka_pliku(nazwa: str) -> str:
    """Ścieżka do pliku wyników albo 404. Chroni przed '../' w nazwie."""
    if nazwa in PLIKI_PRZYKLADOWE:
        return os.path.join(FOLDER_PRZYKLADU, nazwa)
    if nazwa != secure_filename(nazwa) or not nazwa.endswith(".csv"):
        abort(404)
    sciezka = os.path.join(_folder_wynikow(), nazwa)
    if not os.path.isfile(sciezka):
        abort(404)
    return sciezka


def _wczytaj(nazwa: str) -> dict:
    sciezka = _sciezka_pliku(nazwa)
    klucz = (sciezka, os.path.getmtime(sciezka))
    if klucz not in _cache:
        with open(sciezka, encoding="utf-8") as plik:
            _cache[klucz] = wyniki_h3.wczytaj_csv(plik.read())
    return _cache[klucz]


def _lista_plikow() -> list[dict]:
    pliki = [{"nazwa": n, "przyklad": True} for n in PLIKI_PRZYKLADOWE]
    for nazwa in sorted(os.listdir(_folder_wynikow())):
        if nazwa.endswith(".csv"):
            pliki.append({"nazwa": nazwa, "przyklad": False})
    return pliki


def podsumowanie() -> dict:
    """Liczba własnych plików wyników — na kartę modułu na stronie głównej."""
    return {"pliki": sum(1 for p in _lista_plikow() if not p["przyklad"])}


@dostepnosc_bp.route("/")
def index():
    return render_template(
        "dostepnosc/index.html",
        pliki=_lista_plikow(),
        wybrany=request.args.get("plik") or PLIK_PRZYKLADU,
        blad=request.args.get("blad"),
    )


@dostepnosc_bp.route("/wgraj", methods=["POST"])
def wgraj():
    plik = request.files.get("plik")
    if plik is None or not plik.filename:
        return redirect(url_for("dostepnosc.index", blad="Nie wybrano pliku."))
    nazwa = secure_filename(plik.filename)
    if not nazwa.lower().endswith(".csv"):
        return redirect(url_for("dostepnosc.index", blad="Dozwolone są tylko pliki CSV."))
    # „Wyniki.CSV” → „Wyniki.csv”: lista plików i odczyt szukają małego „.csv”.
    nazwa = nazwa[: -len(".csv")] + ".csv"
    if nazwa in PLIKI_PRZYKLADOWE:
        nazwa = "wlasny_" + nazwa

    try:
        tekst = plik.read().decode("utf-8-sig")
        wyniki_h3.wczytaj_csv(tekst)  # walidacja przed zapisem
    except UnicodeDecodeError:
        return redirect(url_for("dostepnosc.index", blad="Plik musi być zapisany w UTF-8."))
    except BladWynikow as e:
        return redirect(url_for("dostepnosc.index", blad=f"{plik.filename}: {e}"))

    with open(os.path.join(_folder_wynikow(), nazwa), "w", encoding="utf-8") as cel:
        cel.write(tekst)
    return redirect(url_for("dostepnosc.index", plik=nazwa))


@dostepnosc_bp.route("/plik/<nazwa>")
def opis_pliku(nazwa):
    try:
        dane = _wczytaj(nazwa)
    except BladWynikow as e:
        return jsonify({"blad": str(e)}), 422
    return jsonify(
        {
            "nazwa": nazwa,
            "przyklad": nazwa in PLIKI_PRZYKLADOWE,
            "ma_ludnosc": dane.get("ludnosc") is not None,
            "liczba_komorek": len(dane["komorki"]),
            "rozdzielczosc": dane["rozdzielczosc"],
            "kolumny": [
                {"nazwa": k, "minuty": wyniki_h3.czy_minuty(k)} for k in dane["kolumny"]
            ],
            # Wskaźnik łączny ma sens dopiero przy co najmniej dwóch usługach.
            "laczny_dostepny": len(wyniki_h3.kolumny_minut(dane)) >= 2,
        }
    )


@dostepnosc_bp.route("/porownanie")
def porownanie():
    """Scenariusz „po” względem „przed” dla jednej kolumny czasu albo
    wskaźnika łącznego (kolumna=laczny)."""
    przed = request.args.get("przed", "")
    po = request.args.get("po", "")
    kolumna = request.args.get("kolumna", "")
    if kolumna == "laczny":
        kolumna = wyniki_h3.NAZWA_LACZNEGO
    if not przed or not po or przed == po:
        return jsonify({"blad": "Wybierz dwa różne pliki do porównania."}), 400
    try:
        return jsonify(wyniki_h3.porownaj_scenariusze(_wczytaj(przed), _wczytaj(po), kolumna))
    except KeyError:
        return jsonify({"blad": f"Oba pliki muszą mieć wskaźnik „{kolumna}”."}), 422
    except BladWynikow as e:
        return jsonify({"blad": str(e)}), 422


@dostepnosc_bp.route("/eksport.geojson")
def eksport_geojson():
    """Heksagony z wartościami do QGIS: jeden wskaźnik albo porównanie
    scenariuszy (gdy podano `po`). kolumna=laczny — wskaźnik łączny."""
    plik = request.args.get("plik", "")
    kolumna = request.args.get("kolumna", "")
    po = request.args.get("po")
    try:
        if kolumna == "laczny":
            kolumna = wyniki_h3.NAZWA_LACZNEGO
        if po:
            wynik = wyniki_h3.porownaj_scenariusze(_wczytaj(plik), _wczytaj(po), kolumna)
        elif kolumna == wyniki_h3.NAZWA_LACZNEGO:
            wynik = wyniki_h3.analiza_laczna(_wczytaj(plik))
        else:
            wynik = wyniki_h3.analiza_kolumny(_wczytaj(plik), kolumna)
    except KeyError:
        return jsonify({"blad": f"Plik nie ma wskaźnika „{kolumna}”."}), 404
    except BladWynikow as e:
        return jsonify({"blad": str(e)}), 422

    kolekcja = wynik["geojson"]
    for cecha in kolekcja["features"]:
        cecha["properties"]["wskaznik"] = kolumna
    nazwa = os.path.splitext(plik)[0] + ("_porownanie" if po else "") + f"_{kolumna}.geojson"
    return Response(
        json.dumps(kolekcja, ensure_ascii=False),
        mimetype="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={secure_filename(nazwa)}"},
    )


@dostepnosc_bp.route("/plik/<nazwa>/laczny")
def analiza_laczna(nazwa):
    try:
        return jsonify(wyniki_h3.analiza_laczna(_wczytaj(nazwa)))
    except BladWynikow as e:
        return jsonify({"blad": str(e)}), 422


@dostepnosc_bp.route("/plik/<nazwa>/<kolumna>")
def analiza(nazwa, kolumna):
    try:
        return jsonify(wyniki_h3.analiza_kolumny(_wczytaj(nazwa), kolumna))
    except KeyError:
        return jsonify({"blad": f"Plik nie ma kolumny „{kolumna}”."}), 404
    except BladWynikow as e:
        return jsonify({"blad": str(e)}), 422


@dostepnosc_bp.route("/plik/<nazwa>/usun", methods=["POST"])
def usun(nazwa):
    if nazwa in PLIKI_PRZYKLADOWE:
        abort(400, "Pliku przykładowego nie można usunąć.")
    os.remove(_sciezka_pliku(nazwa))
    return redirect(url_for("dostepnosc.index"))
