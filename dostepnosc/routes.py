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

import math

from . import druk, lokalizacja, model, obszary, zasieg
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


# ---------- Szybki model z punktów usług (ETAP 47) ----------

ROZSZERZENIE_PUNKTOW = ".punkty.json"  # plik obok wyników: punkty i obszary obsługi


def _sciezka_punktow(nazwa: str) -> str:
    return os.path.join(_folder_wynikow(), nazwa + ROZSZERZENIE_PUNKTOW)


def _punkty_pliku(nazwa: str) -> dict | None:
    if nazwa in PLIKI_PRZYKLADOWE:
        return None
    sciezka = _sciezka_punktow(nazwa)
    if not os.path.isfile(sciezka):
        return None
    with open(sciezka, encoding="utf-8") as plik:
        return json.load(plik)


def _wolna_nazwa(nazwa: str) -> str:
    """Nie nadpisujemy istniejących plików: „x.csv” → „x_2.csv” itd."""
    podstawa = nazwa[: -len(".csv")]
    kandydat, numer = nazwa, 2
    while kandydat in PLIKI_PRZYKLADOWE or os.path.exists(os.path.join(_folder_wynikow(), kandydat)):
        kandydat = f"{podstawa}_{numer}.csv"
        numer += 1
    return kandydat


def _liczba(wartosc, domyslna: float) -> float:
    if wartosc in (None, ""):
        return domyslna
    liczba = float(str(wartosc).replace(",", "."))
    if not math.isfinite(liczba):
        raise ValueError("liczba nieskończona")
    return liczba


@dostepnosc_bp.route("/punkty-z-pliku", methods=["POST"])
def punkty_z_pliku():
    """Wczytuje punkty usług z CSV — do przejrzenia na mapie przed liczeniem."""
    plik = request.files.get("plik")
    if plik is None or not plik.filename:
        return jsonify({"blad": "Nie wybrano pliku."}), 400
    zawartosc = plik.read(1_000_001)
    if len(zawartosc) > 1_000_000:
        return jsonify({"blad": "Plik jest za duży (limit 1 MB)."}), 400
    try:
        punkty, bledy = model.punkty_z_csv(zawartosc.decode("utf-8-sig"))
    except UnicodeDecodeError:
        return jsonify({"blad": "Plik musi być zapisany w UTF-8."}), 400
    except model.BladModelu as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify({"punkty": punkty, "bledy": bledy[:20], "liczba_bledow": len(bledy)})


@dostepnosc_bp.route("/z-punktow", methods=["POST"])
def z_punktow():
    """Czas dojścia do punktów usług wstawionych na mapie → nowy plik wyników.

    Siatka: komórki pliku bazowego (razem z jego wskaźnikami i ludnością)
    albo nowa siatka H3 dla widocznego obszaru mapy.
    """
    dane = request.get_json(silent=True) or {}
    try:
        kolumna = model.nazwa_kolumny(str(dane.get("usluga") or ""))
        predkosc = _liczba(dane.get("predkosc_kmh"), model.PREDKOSC_DOMYSLNA_KMH)
        kretosc = _liczba(dane.get("kretosc"), model.KRETOSC_DOMYSLNA)
        punkty = model.sprawdz_parametry(dane.get("punkty"), predkosc, kretosc)
        baza = dane.get("baza")
        if baza:
            wyniki = _wczytaj(str(baza))
            komorki = wyniki["komorki"]
            kolumny = dict(wyniki["kolumny"])
            ludnosc = wyniki.get("ludnosc")
            rdzen = str(baza)[: -len(".csv")]
        else:
            obszar = dane.get("obszar") or []
            if len(obszar) != 4:
                raise model.BladModelu("Brak obszaru mapy (południe, zachód, północ, wschód).")
            komorki = model.siatka_obszaru(*(float(v) for v in obszar))
            kolumny, ludnosc, rdzen = {}, None, "nowa_siatka"
    except (model.BladModelu, BladWynikow) as e:
        return jsonify({"blad": str(e)}), 400
    except (TypeError, ValueError):
        return jsonify({"blad": "Prędkość, krętość i obszar muszą być liczbami."}), 400

    czasy, najblizsze = model.czasy_dojscia(komorki, punkty, predkosc, kretosc)
    # „Dodaj do istniejących”: nowa szkoła obok obecnych — czas do najbliższej
    # z nich; obszary obsługi tylko tam, gdzie nowy punkt coś zmienił.
    polacz = bool(dane.get("polacz")) and bool(baza) and kolumna in wyniki["kolumny"]
    if bool(dane.get("polacz")) and not polacz:
        return jsonify(
            {"blad": f"Plik bazowy nie ma wskaźnika „{kolumna}” — nie ma z czym połączyć. Wybierz istniejącą usługę albo odznacz „dodaj do istniejących”."}
        ), 400
    maska = None
    czasy_nowych = czasy
    if polacz:
        czasy, maska = model.polacz_z_istniejacymi(wyniki["kolumny"][kolumna], czasy_nowych)
    kolumny[kolumna] = czasy
    tekst = model.csv_wynikow(komorki, kolumny, ludnosc)
    wyniki_h3.wczytaj_csv(tekst)  # ten sam format co wgrane pliki — sprawdzamy

    nazwa = secure_filename(str(dane.get("nazwa_pliku") or f"{rdzen}_{kolumna[len('czas_'):-len('_min')]}"))
    if not nazwa:
        nazwa = "wyniki"
    if not nazwa.lower().endswith(".csv"):
        nazwa += ".csv"
    nazwa = _wolna_nazwa(nazwa[: -len(".csv")] + ".csv")
    with open(os.path.join(_folder_wynikow(), nazwa), "w", encoding="utf-8") as cel:
        cel.write(tekst)

    punkty_pliku = {
        "usluga": str(dane.get("usluga")).strip(),
        "kolumna": kolumna,
        "predkosc_kmh": predkosc,
        "kretosc": kretosc,
        "baza": baza or None,
        "polaczone": polacz,
        "obszary": model.obszary_obslugi(punkty, czasy_nowych, najblizsze, ludnosc, maska),
    }
    # Nazwy punktów (np. z pliku CSV) — tylko do tabeli obszarów obsługi.
    nazwy = dane.get("nazwy") if isinstance(dane.get("nazwy"), list) else []
    for obszar, nazwa_punktu in zip(punkty_pliku["obszary"], nazwy):
        if nazwa_punktu:
            obszar["nazwa"] = str(nazwa_punktu).strip()[: model.MAKS_DLUGOSC_NAZWY]
    with open(_sciezka_punktow(nazwa), "w", encoding="utf-8") as cel:
        json.dump(punkty_pliku, cel, ensure_ascii=False)
    return jsonify({"plik": nazwa, **punkty_pliku})


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
            "punkty": _punkty_pliku(nazwa),
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


@dostepnosc_bp.route("/kontury.geojson")
def kontury_geojson():
    """ETAP 183: zasięgi 5/10/15/20/30 min jako wieloboki do QGIS."""
    plik = request.args.get("plik", "")
    kolumna = request.args.get("kolumna", "")
    if kolumna == "laczny":
        kolumna = wyniki_h3.NAZWA_LACZNEGO
    try:
        kolekcja = wyniki_h3.kontury(_wczytaj(plik), kolumna)
    except KeyError:
        return jsonify({"blad": f"Plik nie ma wskaźnika „{kolumna}”."}), 404
    except BladWynikow as e:
        return jsonify({"blad": str(e)}), 422
    for cecha in kolekcja["features"]:
        cecha["properties"]["wskaznik"] = kolumna
    nazwa = os.path.splitext(plik)[0] + f"_{kolumna}_zasiegi.geojson"
    return Response(json.dumps(kolekcja, ensure_ascii=False), mimetype="application/geo+json",
                    headers={"Content-Disposition": f"attachment; filename={secure_filename(nazwa)}"})


@dostepnosc_bp.route("/plik/<nazwa>/laczny")
def analiza_laczna(nazwa):
    try:
        return jsonify(wyniki_h3.analiza_laczna(_wczytaj(nazwa)))
    except BladWynikow as e:
        return jsonify({"blad": str(e)}), 422


@dostepnosc_bp.route("/plik/<nazwa>/komorka/<indeks>")
def komorka(nazwa, indeks):
    try:
        return jsonify(wyniki_h3.komorka(_wczytaj(nazwa), indeks))
    except KeyError:
        return jsonify({"blad": "Plik nie ma takiej komórki."}), 404


@dostepnosc_bp.route("/plik/<nazwa>/lokalizacja")
def nowa_placowka(nazwa):
    """Gdzie postawić nową placówkę, żeby objąć najwięcej mieszkańców poza
    zasięgiem progu (ETAP 78, dostepnosc/lokalizacja.py)."""
    kolumna = request.args.get("kolumna", "")
    try:
        dane = _wczytaj(nazwa)
        if kolumna not in dane["kolumny"] or not wyniki_h3.czy_minuty(kolumna):
            return jsonify({"blad": "Wybierz wskaźnik czasu dojścia (w minutach) jednej usługi."}), 400
        wynik = lokalizacja.najlepsze_lokalizacje(
            dane["komorki"],
            dane["kolumny"][kolumna],
            dane.get("ludnosc"),
            request.args.get("prog", 15, type=float),
            request.args.get("ile", 1, type=int),
            request.args.get("predkosc", model.PREDKOSC_DOMYSLNA_KMH, type=float),
            request.args.get("kretosc", model.KRETOSC_DOMYSLNA, type=float),
        )
    except (lokalizacja.BladLokalizacji, BladWynikow) as e:
        return jsonify({"blad": str(e)}), 422
    return jsonify(wynik)


@dostepnosc_bp.route("/plik/<nazwa>/zasieg")
def zasieg_z_punktu(nazwa):
    """Ilu mieszkańców dojdzie z klikniętego punktu w 5, 10 i 15 minut
    (ETAP 85, dostepnosc/zasieg.py). Z kolumną czasu dojścia — także, ilu
    z nich ma dziś dalej niż próg."""
    kolumna = request.args.get("kolumna", "")
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    if lat is None or lng is None:
        return jsonify({"blad": "Wymagane lat i lng (stopnie WGS84)."}), 400
    try:
        dane = _wczytaj(nazwa)
        czasy = dane["kolumny"][kolumna] if kolumna in dane["kolumny"] and wyniki_h3.czy_minuty(kolumna) else None
        wynik = zasieg.zasieg_punktu(
            dane["komorki"],
            dane.get("ludnosc"),
            lat,
            lng,
            czasy,
            request.args.get("predkosc", model.PREDKOSC_DOMYSLNA_KMH, type=float),
            request.args.get("kretosc", model.KRETOSC_DOMYSLNA, type=float),
        )
    except (model.BladModelu, BladWynikow) as e:
        return jsonify({"blad": str(e)}), 422
    wynik["kolumna"] = kolumna if czasy is not None else None
    return jsonify(wynik)


@dostepnosc_bp.route("/plik/<nazwa>/obszary", methods=["POST"])
def wyniki_w_obszarach(nazwa):
    """ETAP 163: JSON {kolumna, obszary: [{nazwa, geometria}]} → statystyki w każdym obszarze."""
    dane = request.get_json(silent=True) or {}
    kolumna = dane.get("kolumna") or ""
    if kolumna == "laczny":
        kolumna = wyniki_h3.NAZWA_LACZNEGO
    try:
        return jsonify(obszary.w_obszarach(_wczytaj(nazwa), kolumna, dane.get("obszary")))
    except KeyError:
        return jsonify({"blad": f"Plik nie ma kolumny „{kolumna}”."}), 404
    except BladWynikow as e:
        return jsonify({"blad": str(e)}), 400


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
    if os.path.isfile(_sciezka_punktow(nazwa)):
        os.remove(_sciezka_punktow(nazwa))
    return redirect(url_for("dostepnosc.index"))


# ---------- Raport do druku (ETAP 48) ----------

PROGI_RAPORTU_MIN = (5, 10, 15, 20, 30)


def _raport(plik: str, kolumna: str) -> dict:
    """Analiza + opis do mapy i strony raportu. kolumna=laczny — wszystkie usługi."""
    dane = _wczytaj(plik)
    if kolumna == "laczny":
        analiza = wyniki_h3.analiza_laczna(dane)
        tytul = "Czas dojścia do wszystkich usług naraz"
    else:
        analiza = wyniki_h3.analiza_kolumny(dane, kolumna)
        tytul = f"Czas dojścia: {kolumna}" if analiza["minuty"] else f"Wskaźnik: {kolumna}"
    stat = analiza["statystyki"]
    punkty_pliku = _punkty_pliku(plik)
    punkty = punkty_pliku["obszary"] if punkty_pliku and punkty_pliku["kolumna"] == kolumna else None

    przypisy = []
    if plik in PLIKI_PRZYKLADOWE:
        przypisy.append("Dane syntetyczne (plik przykładowy) — nie opisują rzeczywistej dostępności.")
    elif punkty:
        przypisy.append(
            f"Szybki model: odległość w linii prostej × krętość {punkty_pliku['kretosc']:g}, prędkość "
            f"{punkty_pliku['predkosc_kmh']:g} km/h".replace(".", ",") + " — bez sieci ulic i barier."
        )
    else:
        przypisy.append(f"Źródło: wyniki analizy z pliku {plik}.")
    przypisy.append("Siatka heksagonalna H3 (Uber). Opracowanie w aplikacji Warsztat.")

    krzywa = {p["minuty"]: p for p in stat.get("krzywa", [])}
    return {
        "plik": plik,
        "kolumna": kolumna,
        "analiza": analiza,
        "tytul": tytul,
        "podtytul": f"{plik} · rozdzielczość H3 {stat['rozdzielczosc']} · komórek: {stat['liczba_komorek']}",
        "przypisy": przypisy,
        "punkty": punkty,
        "punkty_pliku": punkty_pliku if punkty else None,
        "legenda": druk.legenda(analiza),
        "progi_raportu": [_punkt_krzywej(krzywa, m) for m in PROGI_RAPORTU_MIN] if krzywa else [],
    }


def _punkt_krzywej(krzywa: dict, minuty: int) -> dict:
    """Punkt krzywej dla progu. Krzywa kończy się przy pełnym pokryciu —
    próg dalej niż jej koniec ma ten sam udział co ostatni punkt."""
    return krzywa.get(minuty) or krzywa[max(krzywa)]


@dostepnosc_bp.route("/mapa.svg")
def mapa_do_druku():
    try:
        r = _raport(request.args.get("plik", ""), request.args.get("kolumna", ""))
        svg = druk.mapa_svg(r["analiza"], r["tytul"], r["podtytul"], r["przypisy"], r["punkty"])
    except KeyError:
        return jsonify({"blad": "Plik nie ma takiego wskaźnika."}), 404
    except (BladWynikow, ValueError) as e:
        return jsonify({"blad": str(e)}), 422
    naglowki = {}
    if request.args.get("pobierz"):
        nazwa = secure_filename(f"mapa_{r['plik'][:-4]}_{r['kolumna']}.svg")
        naglowki["Content-Disposition"] = f"attachment; filename={nazwa}"
    return Response(svg, mimetype="image/svg+xml", headers=naglowki)


@dostepnosc_bp.route("/raport")
def raport():
    try:
        r = _raport(request.args.get("plik", ""), request.args.get("kolumna", ""))
    except KeyError:
        abort(404, "Plik nie ma takiego wskaźnika.")
    except BladWynikow as e:
        abort(422, str(e))
    return render_template("dostepnosc/raport.html", r=r, progi_minut=PROGI_RAPORTU_MIN)
