import os

from flask import (
    Blueprint,
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

# Wczytane pliki trzymamy w pamięci; klucz zawiera czas modyfikacji,
# więc podmieniony plik zostanie wczytany od nowa.
_cache: dict[tuple[str, float], dict] = {}


def _folder_wynikow() -> str:
    folder = os.path.join(current_app.instance_path, "dostepnosc", "wyniki")
    os.makedirs(folder, exist_ok=True)
    return folder


def _sciezka_pliku(nazwa: str) -> str:
    """Ścieżka do pliku wyników albo 404. Chroni przed '../' w nazwie."""
    if nazwa == PLIK_PRZYKLADU:
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
    pliki = [{"nazwa": PLIK_PRZYKLADU, "przyklad": True}]
    for nazwa in sorted(os.listdir(_folder_wynikow())):
        if nazwa.endswith(".csv"):
            pliki.append({"nazwa": nazwa, "przyklad": False})
    return pliki


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
    if nazwa == PLIK_PRZYKLADU:
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
            "przyklad": nazwa == PLIK_PRZYKLADU,
            "liczba_komorek": len(dane["komorki"]),
            "rozdzielczosc": dane["rozdzielczosc"],
            "kolumny": [
                {"nazwa": k, "minuty": wyniki_h3.czy_minuty(k)} for k in dane["kolumny"]
            ],
        }
    )


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
    if nazwa == PLIK_PRZYKLADU:
        abort(400, "Pliku przykładowego nie można usunąć.")
    os.remove(_sciezka_pliku(nazwa))
    return redirect(url_for("dostepnosc.index"))
