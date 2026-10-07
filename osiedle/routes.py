"""Moduł osiedle: koncepcje osiedla rysowane na mapie i ich bilans terenu."""

import json

from flask import Blueprint, Response, abort, jsonify, render_template, request, url_for
from shapely.geometry import mapping
from shapely.ops import unary_union
from werkzeug.utils import secure_filename

from dane import uldk

from . import baza, cien
from . import program as prog
from .obszar_z_pliku import obszar_z_geojson
from .bilans import BUDYNEK, DOMYSLNE_KONDYGNACJE_BUDYNKU, FUNKCJE, KOLOR_BUDYNKU, KOLOR_LINII, LINIA, OBSZAR, BladKoncepcji, bilans
from .koszty import STAWKI
from .program import ZALOZENIA
from .wskazniki import DOMYSLNE, BladParametru

osiedle_bp = Blueprint(
    "osiedle",
    __name__,
    template_folder="templates",
    static_folder="static",
)

MAKS_DLUGOSC_NAZWY = 80
MAKS_DZIALEK = 50

# Na poziomie modułu, żeby testy mogły podmienić usługę ULDK.
znajdz_dzialke_po_id = uldk.znajdz_dzialke_po_id


def _koncepcja_albo_404(koncepcja_id: int) -> dict:
    koncepcja = baza.pobierz(koncepcja_id)
    if koncepcja is None:
        abort(404)
    return koncepcja


def _nazwa(tekst) -> str:
    nazwa = " ".join(str(tekst or "").split())
    if not nazwa:
        raise BladKoncepcji("Podaj nazwę koncepcji, np. „Osiedle Jeżyce — wariant A”.")
    if len(nazwa) > MAKS_DLUGOSC_NAZWY:
        raise BladKoncepcji(f"Nazwa może mieć najwyżej {MAKS_DLUGOSC_NAZWY} znaków.")
    return nazwa


def podsumowanie() -> dict:
    """Liczba koncepcji — na kartę modułu na stronie głównej."""
    koncepcje = baza.lista()
    return {"liczba": len(koncepcje), "ostatnia": koncepcje[0]["nazwa"] if koncepcje else None}


@osiedle_bp.route("/")
def index():
    return render_template(
        "osiedle/index.html", funkcje=FUNKCJE, obszar=OBSZAR, budynek=BUDYNEK, kolor_budynku=KOLOR_BUDYNKU, linia=LINIA, kolor_linii=KOLOR_LINII,
        domyslne={**DOMYSLNE, BUDYNEK: {"kondygnacje": DOMYSLNE_KONDYGNACJE_BUDYNKU, "zielony_dach_proc": 0}},  # ETAP 173/239: kondygnacje i zielony dach
        zalozenia=ZALOZENIA, stawki=STAWKI,
    )


@osiedle_bp.route("/koncepcje")
def lista_koncepcji():
    return jsonify(baza.lista())


# ---------- własne zestawy założeń programu (ETAP 218) ----------


@osiedle_bp.route("/zestawy")
def lista_zestawow():
    return jsonify(baza.zestawy())


@osiedle_bp.route("/zestawy", methods=["POST"])
def zapisz_zestaw():
    """JSON {nazwa, zalozenia: {klucz: liczba}} — tylko wpisane założenia, sprawdzone jak w koncepcji."""
    dane = request.get_json(silent=True) or {}
    nazwa = " ".join(str(dane.get("nazwa") or "").split())[:60]
    wpisane = dane.get("zalozenia")
    try:
        if not nazwa:
            raise prog.BladZalozen("Podaj nazwę zestawu.")
        if not isinstance(wpisane, dict) or not any(v not in (None, "") for v in wpisane.values()):
            raise prog.BladZalozen("Zestaw musi mieć co najmniej jedno wpisane założenie.")
        pelne = prog.zalozenia({"program": wpisane})  # walidacja kluczy i zakresów
        if nazwa not in {z["nazwa"] for z in baza.zestawy()} and len(baza.zestawy()) >= baza.MAKS_ZESTAWOW:
            raise prog.BladZalozen(f"Najwyżej {baza.MAKS_ZESTAWOW} zestawów — usuń któryś.")
    except prog.BladZalozen as e:
        return jsonify({"blad": str(e)}), 400
    zalozenia = {k: pelne[k] for k, v in wpisane.items() if v not in (None, "")}
    return jsonify({"id": baza.zapisz_zestaw(nazwa, zalozenia), "nazwa": nazwa, "zalozenia": zalozenia}), 201


@osiedle_bp.route("/zestawy/<int:zestaw_id>", methods=["DELETE"])
def usun_zestaw(zestaw_id):
    if not baza.usun_zestaw(zestaw_id):
        abort(404)
    return jsonify({"ok": True})


@osiedle_bp.route("/kosz")
def kosz_koncepcji():
    """ETAP 212: usunięte koncepcje (do 30 dni)."""
    return jsonify(baza.w_koszu())


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>/przywroc", methods=["POST"])
def przywroc_koncepcje(koncepcja_id):
    if not baza.przywroc(koncepcja_id):
        abort(404)
    return jsonify({"ok": True, "id": koncepcja_id})


@osiedle_bp.route("/koncepcje", methods=["POST"])
def nowa_koncepcja():
    dane = request.get_json(silent=True) or {}
    try:
        koncepcja_id = baza.utworz(_nazwa(dane.get("nazwa")))
    except BladKoncepcji as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify(baza.pobierz(koncepcja_id)), 201


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>")
def koncepcja(koncepcja_id):
    k = _koncepcja_albo_404(koncepcja_id)
    return jsonify({**k, "bilans": bilans(k["geojson"], k["ustawienia"])})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>", methods=["PUT"])
def zapisz_koncepcje(koncepcja_id):
    """Zapis nazwy, rysunku albo ustawień; zwraca świeży bilans."""
    obecna = _koncepcja_albo_404(koncepcja_id)
    dane = request.get_json(silent=True) or {}
    try:
        nazwa = _nazwa(dane["nazwa"]) if "nazwa" in dane else None
        geojson = dane.get("geojson")
        ustawienia = dane.get("ustawienia")
        if ustawienia is not None and not isinstance(ustawienia, dict):
            raise BladKoncepcji("Ustawienia muszą być obiektem.")
        # ETAP 67: projekt z modułu teren pokazywany jako warstwa punktów
        teren = (ustawienia or {}).get("teren_projekt")
        if teren is not None and (isinstance(teren, bool) or not isinstance(teren, int)):
            raise BladKoncepcji("Projekt terenowy: oczekiwano numeru projektu.")
        # walidacja przed zapisem: nowy rysunek i nowe ustawienia razem
        wynik = bilans(
            geojson if geojson is not None else obecna["geojson"],
            ustawienia if ustawienia is not None else obecna["ustawienia"],
        )
    except BladKoncepcji as e:
        return jsonify({"blad": str(e)}), 400
    baza.zapisz(koncepcja_id, nazwa, geojson, ustawienia)
    return jsonify({**baza.pobierz(koncepcja_id), "bilans": wynik})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>/obszar-z-dzialek", methods=["POST"])
def obszar_z_dzialek(koncepcja_id):
    """Obszar opracowania = suma granic działek ewidencyjnych z ULDK
    (ETAP 75). Zastępuje dotychczasowy obszar; tereny zostają."""
    k = _koncepcja_albo_404(koncepcja_id)
    surowe = (request.get_json(silent=True) or {}).get("dzialki")
    if not isinstance(surowe, list) or not surowe:
        return jsonify({"blad": "Podaj co najmniej jeden identyfikator działki."}), 400
    identyfikatory = list(dict.fromkeys(" ".join(str(d).split()) for d in surowe if str(d).strip()))
    if len(identyfikatory) > MAKS_DZIALEK:
        return jsonify({"blad": f"Najwyżej {MAKS_DZIALEK} działek naraz."}), 400
    geometrie = []
    for dzialka_id in identyfikatory:
        try:
            dzialka = znajdz_dzialke_po_id(dzialka_id)
        except ValueError as e:
            return jsonify({"blad": f"{dzialka_id}: {e}"}), 400
        except uldk.BladULDK as e:
            return jsonify({"blad": str(e)}), 502
        if dzialka is None:
            return jsonify({"blad": f"ULDK nie zna działki {dzialka_id}."}), 404
        geometrie.append(dzialka.geometria)
    return _zastap_obszar(k, unary_union(geometrie), {"dzialki": identyfikatory})


def _zastap_obszar(k: dict, obszar, wlasciwosci: dict):
    """Nowy obszar opracowania w miejsce dotychczasowego; tereny zostają."""
    cechy = [c for c in k["geojson"]["features"] if (c.get("properties") or {}).get("funkcja") != OBSZAR]
    cechy.insert(0, {"type": "Feature", "properties": {"funkcja": OBSZAR, **wlasciwosci}, "geometry": mapping(obszar)})
    geojson = {"type": "FeatureCollection", "features": cechy}
    try:
        wynik = bilans(geojson, k["ustawienia"])
    except BladKoncepcji as e:
        return jsonify({"blad": str(e)}), 400
    baza.zapisz(k["id"], geojson=geojson)
    return jsonify({**baza.pobierz(k["id"]), "bilans": wynik})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>/obszar-z-pliku", methods=["POST"])
def obszar_z_pliku(koncepcja_id):
    """Obszar opracowania z pliku GeoJSON, np. granica narysowana w QGIS
    (ETAP 138). WGS84, PL-1992 albo PL-2000; zastępuje obecny obszar."""
    k = _koncepcja_albo_404(koncepcja_id)
    plik = request.files.get("plik")
    if plik is None or not plik.filename:
        return jsonify({"blad": "Wybierz plik GeoJSON."}), 400
    try:
        dane = json.loads(plik.read().decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"blad": "To nie jest plik GeoJSON (JSON) — w QGIS: Eksportuj → Zapisz obiekty jako… → GeoJSON."}), 400
    try:
        obszar, uklad = obszar_z_geojson(dane)
    except BladKoncepcji as e:
        return jsonify({"blad": str(e)}), 400
    return _zastap_obszar(k, obszar, {"plik": secure_filename(plik.filename) or "obszar.geojson", "uklad_pliku": uklad})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>/cien")
def cien_koncepcji(koncepcja_id):
    """Odległości terenów zabudowy od granicy obszaru i strefa możliwego
    cienia (ETAP 94, osiedle/cien.py) — dla zapisanego rysunku."""
    k = _koncepcja_albo_404(koncepcja_id)
    try:
        return jsonify(cien.analiza(k["geojson"], request.args.get("dzien", "rownonoc")))
    except (cien.BladCienia, BladKoncepcji, BladParametru) as e:
        return jsonify({"blad": str(e)}), 400


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>", methods=["DELETE"])
def usun_koncepcje(koncepcja_id):
    _koncepcja_albo_404(koncepcja_id)
    baza.usun(koncepcja_id)
    return jsonify({"ok": True})


# ETAP 189: arkusz ODS — opisy wierszy jak w raporcie
OPISY_WSKAZNIKOW = [("powierzchnia_zabudowy_m2", "powierzchnia zabudowy [m²]"), ("powierzchnia_calkowita_m2", "powierzchnia całkowita [m²]"),
                    ("zabudowa_proc", "wskaźnik zabudowy [%]"), ("intensywnosc", "intensywność zabudowy"),
                    ("pbc_proc", "powierzchnia biologicznie czynna [%]"), ("max_kondygnacje", "najwyższa zabudowa [kond.]")]
OPISY_PROGRAMU = [("mieszkania_mw", "mieszkania MW"), ("mieszkania_mn", "domy MN"), ("mieszkancy", "mieszkańcy"),
                  ("gestosc_os_na_ha", "gęstość [os./ha]"), ("powierzchnia_uslug_m2", "powierzchnia usług [m²]"),
                  ("miejsca_potrzebne", "miejsca postojowe — potrzeba"), ("miejsca_na_terenach_ks", "miejsca postojowe — na KS"),
                  ("miejsca_brakuje", "miejsca postojowe — brakuje"), ("oddzialy_przedszkolne", "oddziały przedszkolne"),
                  ("oddzialy_szkolne", "oddziały szkolne"), ("zielen_na_mieszkanca_m2", "zieleń na mieszkańca [m²]")]


def arkusze_koncepcji(k: dict, b: dict) -> list[dict]:
    """Bilans, wskaźniki (z terenów i budynków), program, koszty i budynki jako arkusze ODS."""
    zrodlo = [f"Koncepcja „{k['nazwa']}” — opracowanie w aplikacji Warsztat (moduł Osiedle); liczby z rysunku i wpisanych założeń."]
    bilans_w = [["funkcja", "nazwa", "powierzchnia [m²]", "udział [%]"]] + [[f["funkcja"], f["nazwa"], f["powierzchnia_m2"], f["procent"]] for f in b["funkcje"]]
    if b["obszar_m2"] is not None:
        bilans_w.append(["obszar", "obszar opracowania", b["obszar_m2"], 100])
    arkusze = [{"nazwa": "Bilans", "wiersze": bilans_w, "przypisy": zrodlo}]
    if b["wskazniki"]:
        wb = b.get("wskazniki_budynkow")
        wiersze = [["wskaźnik", "z terenów", *(["z budynków"] if wb else [])]]
        wiersze += [[opis, b["wskazniki"][klucz], *([wb[klucz]] if wb else [])] for klucz, opis in OPISY_WSKAZNIKOW]
        zgodnosc = [[f"plan: {z['nazwa']} {z['rodzaj']} {z['granica']}", z["wartosc"], "zgodne" if z["spelnione"] else "niezgodne"] for z in b["zgodnosc"]]
        ch = b.get("chlonnosc")  # ETAP 197
        chlonnosc = [[f"chłonność: pow. całkowita z ustalenia „{o['z']}” [m²]", o["calkowita_m2"]] for o in ch["ograniczenia"]] + [
            ["chłonność: wykorzystanie [%]", ch["wykorzystanie_proc"]], ["chłonność: zapas [m²]", ch["zapas_m2"]],
            ["chłonność: zapas mieszkań MW", ch["zapas_mieszkan"]]] if ch else []
        arkusze.append({"nazwa": "Wskaźniki", "wiersze": wiersze + ([[]] + zgodnosc if zgodnosc else []) + ([[]] + chlonnosc if chlonnosc else []),
                        "przypisy": zrodlo})
    if b["program"]:
        arkusze.append({"nazwa": "Program", "wiersze": [["pozycja", "wartość"]] + [[opis, b["program"][klucz]] for klucz, opis in OPISY_PROGRAMU],
                        "przypisy": zrodlo})
    if b["koszty"]:
        kz = b["koszty"]
        wiersze = [["pozycja", "ilość", "jednostka", "stawka [zł]", "za", "koszt [zł]"]]
        wiersze += [[p["opis"], p["ilosc"], p["jednostka_ilosci"], p["stawka"], p["jednostka"], p["koszt"]] for p in kz["pozycje"]]
        wiersze += [["razem", None, None, None, None, kz["razem"]], ["na mieszkanie", None, None, None, None, kz["na_mieszkanie"]],
                    ["na m² powierzchni całkowitej", None, None, None, None, kz["na_m2_calkowitej"]]]
        arkusze.append({"nazwa": "Koszty", "wiersze": wiersze, "przypisy": ["Stawki wpisane przez użytkownika.", *zrodlo]})
    if b.get("etapy"):
        wiersze = [["etap", "tereny", "powierzchnia [m²]", "powierzchnia całkowita [m²]", "mieszkania", "mieszkania narastająco",
                    "mieszkańcy", "brak miejsc postojowych", "koszt [zł]", "koszt narastająco [zł]"]]
        wiersze += [[x["etap"] if x["etap"] is not None else "bez etapu", x["terenow"], x["powierzchnia_m2"], x["calkowita_m2"], x["mieszkania"],
                     x["mieszkania_narastajaco"], x["mieszkancy"], x["miejsca_brakuje"], x["koszt"], x["koszt_narastajaco"]] for x in b["etapy"]["lista"]]
        arkusze.append({"nazwa": "Etapy", "wiersze": wiersze,
                        "przypisy": ["Każdy etap liczony osobno; koszt gruntu tylko w całości (zakładka Koszty).", *zrodlo]})
    if b.get("budynki"):
        wiersze = [["nr", "teren", "rzut [m²]", "kondygnacje", "powierzchnia całkowita [m²]"]]
        wiersze += [[x["nr"], x["teren"], x["pole_m2"], x["kondygnacje"], x["calkowita_m2"]] for x in b["budynki"]["lista"]]
        arkusze.append({"nazwa": "Budynki", "wiersze": wiersze, "przypisy": zrodlo})
    return arkusze


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>.ods")
def eksport_ods(koncepcja_id):
    """ETAP 189: liczby koncepcji jako arkusz ODS z zakładkami."""
    from dane.arkusz import arkusz_ods

    k = _koncepcja_albo_404(koncepcja_id)
    b = bilans(k["geojson"], k["ustawienia"])
    nazwa = secure_filename(f"koncepcja_{k['id']}_{k['nazwa']}.ods") or "koncepcja.ods"
    return Response(arkusz_ods(arkusze_koncepcji(k, b)), mimetype="application/vnd.oasis.opendocument.spreadsheet",
                    headers={"Content-Disposition": f"attachment; filename={nazwa}"})


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>.geojson")
def eksport_geojson(koncepcja_id):
    """Rysunek koncepcji do QGIS (funkcja jako atrybut)."""
    k = _koncepcja_albo_404(koncepcja_id)
    for cecha in k["geojson"]["features"]:
        funkcja = (cecha.get("properties") or {}).get("funkcja")
        if funkcja in FUNKCJE:
            cecha["properties"]["nazwa_funkcji"] = FUNKCJE[funkcja]["nazwa"]
        elif funkcja == BUDYNEK:
            cecha["properties"]["nazwa_funkcji"] = "budynek"
        elif funkcja == LINIA:
            cecha["properties"]["nazwa_funkcji"] = "nieprzekraczalna linia zabudowy"
    nazwa = secure_filename(f"koncepcja_{k['id']}_{k['nazwa']}.geojson") or "koncepcja.geojson"
    return Response(
        json.dumps(k["geojson"], ensure_ascii=False),
        mimetype="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )


# Raport, szkic i porównanie — w osobnym pliku, rejestruje się na osiedle_bp.
# Import na końcu, bo tamten plik importuje osiedle_bp z tego modułu.
from . import trasy_druk  # noqa: E402, F401


# ---------- wyszukiwarka globalna (ETAP 128) ----------


def wyszukaj(fraza: str) -> list[dict]:
    """Koncepcje po nazwie; link otwiera koncepcję w edytorze (?koncepcja=)."""
    szukane = fraza.casefold()
    return [
        {"tytul": k["nazwa"], "opis": f"koncepcja osiedla, zmieniona {k['data_zmiany'][:10]}",
         "url": url_for("osiedle.index", koncepcja=k["id"])}
        for k in baza.lista() if szukane in k["nazwa"].casefold()
    ][:10]

# ---------- ostatnio używane na stronie głównej (ETAP 141) ----------


def ostatnie(limit: int = 3) -> list[dict]:
    return [{"tytul": k["nazwa"], "opis": "koncepcja osiedla", "kiedy": k["data_zmiany"], "url": url_for("osiedle.index", koncepcja=k["id"])}
            for k in baza.lista()[:limit]]
