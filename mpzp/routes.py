import json
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, render_template, request
from shapely.errors import GEOSException
from shapely.geometry import Point, mapping

from dane.uldk import BladULDK, Dzialka
from dane.uldk import znajdz_dzialke as _znajdz_dzialke
from dane.uldk import WZOR_ID_DZIALKI
from dane.uldk import szukaj_dzialek as _szukaj_dzialek
from dane.uldk import znajdz_dzialke_po_id as _znajdz_dzialke_po_id
from .baza import historia, zapisz_w_historii
from .gminy import GMINA_PILOTAZOWA, znajdz_gmine
from . import zabudowa
from .symbole import opisz_symbol
from .wfs import BladWFS, Wydzielenie
from .wfs import odswiez as _odswiez
from .wfs import wydzielenia_dzialki as _wydzielenia_dzialki
from .geometria import powierzchnia_m2, szkic_svg
from .wfs import znajdz_przeznaczenie as _znajdz_przeznaczenie

mpzp_bp = Blueprint(
    "mpzp",
    __name__,
    template_folder="templates",
    static_folder="static",
)


znajdz_dzialke = _znajdz_dzialke
znajdz_dzialke_po_id = _znajdz_dzialke_po_id
szukaj_dzialek = _szukaj_dzialek
znajdz_wydzielenia_dzialki = _wydzielenia_dzialki

MIN_DLUGOSC_FRAZY = 3
znajdz_przeznaczenie = _znajdz_przeznaczenie
odswiez_warstwe = _odswiez


@mpzp_bp.route("/")
def index():
    return render_template("mpzp/index.html")


def _dzialka_na_json(dzialka: Dzialka) -> dict:
    return {
        "id": dzialka.id,
        "geometria": mapping(dzialka.geometria),
        "teryt_gminy": dzialka.teryt_gminy,
        "powierzchnia_m2": round(powierzchnia_m2(dzialka.geometria), 1),
    }


# Części działki mniejsze niż ten próg to zwykle niedokładność granic
# (działka „dotyka” sąsiedniego wydzielenia) — nie pokazujemy ich.
MIN_UDZIAL_PROC = 0.5


def udzialy_przeznaczen(gmina, dzialka: Dzialka) -> list[dict]:
    """Jak działka dzieli się między przeznaczenia planu (m² i %).

    Części z tym samym symbolem przeznaczenia są sumowane.
    """
    calosc = powierzchnia_m2(dzialka.geometria)
    if calosc <= 0:
        return []
    szerokosc = dzialka.geometria.centroid.y
    po_symbolu: dict[str, float] = {}
    for wydzielenie, czesc in znajdz_wydzielenia_dzialki(gmina, dzialka.geometria):
        symbol = wydzielenie.atrybuty.get(gmina.pole_przeznaczenia) or "?"
        po_symbolu[symbol] = po_symbolu.get(symbol, 0.0) + powierzchnia_m2(czesc, szerokosc)

    udzialy = [
        {
            "przeznaczenie": symbol,
            "opis": opisz_symbol(symbol),
            "powierzchnia_m2": round(pole, 1),
            "procent": round(100 * pole / calosc, 1),
        }
        for symbol, pole in po_symbolu.items()
        if 100 * pole / calosc >= MIN_UDZIAL_PROC
    ]
    return sorted(udzialy, key=lambda u: -u["powierzchnia_m2"])


def _wydzielenie_na_json(wydzielenie: Wydzielenie) -> dict:
    return {
        "geometria": mapping(wydzielenie.geometria),
        "atrybuty": wydzielenie.atrybuty,
    }


@mpzp_bp.route("/sprawdz")
def sprawdz():
    lat_str = request.args.get("lat")
    lon_str = request.args.get("lon")
    if lat_str is None or lon_str is None:
        return jsonify({"blad": "Wymagane parametry lat i lon."}), 400

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        return jsonify({"blad": "Niepoprawne współrzędne."}), 400

    try:
        dzialka = znajdz_dzialke(lat, lon)
    except BladULDK as e:
        return jsonify({"blad": str(e)}), 502

    if dzialka is None:
        return jsonify({"blad": "Brak działki w tym miejscu."}), 404

    return _wynik_dla_dzialki(dzialka, Point(lon, lat))


@mpzp_bp.route("/dzialka")
def dzialka_po_id():
    """Wyszukanie działki po identyfikatorze ewidencyjnym zamiast kliknięcia."""
    dzialka_id = request.args.get("id", "")
    try:
        dzialka = znajdz_dzialke_po_id(dzialka_id)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except BladULDK as e:
        return jsonify({"blad": str(e)}), 502

    if dzialka is None:
        return jsonify({"blad": f"ULDK nie zna działki {dzialka_id.strip()}."}), 404

    # Punkt na pewno wewnątrz działki (centroid bywa poza wielokątem w kształcie litery L).
    return _wynik_dla_dzialki(dzialka, dzialka.geometria.representative_point())


def podsumowanie() -> dict:
    """Ostatnio sprawdzona działka — na kartę modułu na stronie głównej."""
    wpisy = historia()
    return {"liczba": len(wpisy), "ostatnia": wpisy[0] if wpisy else None}


@mpzp_bp.route("/podpowiedzi")
def podpowiedzi():
    """Podpowiedzi przy wpisywaniu działki: najpierw pasujące wpisy z
    historii (od razu, bez sieci), potem działki z ULDK po obrębie i numerze.
    """
    fraza = " ".join((request.args.get("q") or "").split())
    if len(fraza) < MIN_DLUGOSC_FRAZY:
        return jsonify({"z_historii": [], "z_uldk": []})

    male = fraza.casefold()
    z_historii = [
        {"id": w["dzialka_id"], "przeznaczenie": w["przeznaczenie"]}
        for w in historia()
        if male in w["dzialka_id"].casefold()
    ][:5]

    # Pełny identyfikator nie wymaga wyszukiwania — wystarczy go wybrać.
    if WZOR_ID_DZIALKI.match(fraza):
        return jsonify({"z_historii": z_historii, "z_uldk": [{"id": fraza, "opis": "identyfikator działki"}]})

    # ULDK szuka po „obręb numer”, więc bez cyfry nie ma sensu pytać.
    if not any(znak.isdigit() for znak in fraza):
        return jsonify({"z_historii": z_historii, "z_uldk": [], "wskazowka": "Dopisz numer działki, np. „Jeżyce 18/14”."})

    try:
        znalezione = szukaj_dzialek(fraza)
    except BladULDK as e:
        return jsonify({"z_historii": z_historii, "z_uldk": [], "blad": str(e)}), 502

    znane = {w["id"] for w in z_historii}
    z_uldk = [
        {"id": d.id, "opis": f"{d.gmina}, obręb {d.obreb}, działka {d.numer}"}
        for d in znalezione
        if d.id not in znane
    ]
    return jsonify({"z_historii": z_historii, "z_uldk": z_uldk})


@mpzp_bp.route("/historia")
def lista_historii():
    return jsonify(historia())


def _wynik_dla_dzialki(dzialka: Dzialka, punkt: Point):
    """Wspólna ścieżka dla kliknięcia i wyszukania po identyfikatorze."""
    dane = {"dzialka": _dzialka_na_json(dzialka), "punkt": {"lat": punkt.y, "lon": punkt.x}}

    gmina = znajdz_gmine(dzialka.teryt_gminy)
    if gmina is None:
        dane["blad"] = (
            f"Ta gmina nie jest jeszcze obsługiwana (pilotaż: {GMINA_PILOTAZOWA.nazwa})."
        )
        return jsonify(dane), 200

    try:
        wydzielenie = znajdz_przeznaczenie(gmina, punkt)
    except BladWFS as e:
        dane["blad"] = str(e)
        return jsonify(dane), 502

    if wydzielenie is None:
        zapisz_w_historii(dzialka.id, None, punkt.y, punkt.x)
        dane["blad"] = "Brak planu miejscowego dla tej działki."
        return jsonify(dane), 200

    dane["wydzielenie"] = _wydzielenie_na_json(wydzielenie)
    # Symbol przeznaczenia wyciągnięty osobno, żeby panel mógł go wyróżnić,
    # plus orientacyjny opis ze słownika (mpzp/symbole.py).
    przeznaczenie = wydzielenie.atrybuty.get(gmina.pole_przeznaczenia)
    dane["wydzielenie"]["przeznaczenie"] = przeznaczenie
    dane["wydzielenie"]["opis_przeznaczenia"] = opisz_symbol(przeznaczenie)
    try:
        dane["udzialy"] = udzialy_przeznaczen(gmina, dzialka)
    except BladWFS:
        dane["udzialy"] = []  # główne przeznaczenie już mamy — udziały są dodatkiem
    zapisz_w_historii(dzialka.id, przeznaczenie, punkt.y, punkt.x)
    return jsonify(dane), 200


# ---------- Kalkulator wskaźników zabudowy (ETAP 23) ----------


@mpzp_bp.route("/kalkulator")
def kalkulator():
    return render_template(
        "mpzp/kalkulator.html",
        powierzchnia=request.args.get("powierzchnia", type=float),
        dzialka_id=request.args.get("dzialka", ""),
    )


def _liczba_lub_none(slownik: dict, klucz: str, typ=float):
    wartosc = slownik.get(klucz)
    if wartosc in (None, ""):
        return None
    return typ(wartosc)


@mpzp_bp.route("/kalkulator/licz", methods=["POST"])
def kalkulator_licz():
    dane = request.get_json(silent=True) or {}
    try:
        budynki = [
            zabudowa.Budynek(
                rzut_m2=float(b.get("rzut_m2") or 0),
                kondygnacje=int(b.get("kondygnacje") or 0),
                wysokosc_m=_liczba_lub_none(b, "wysokosc_m"),
            )
            for b in dane.get("budynki", [])
        ]
        plan = dane.get("ustalenia", {})
        ustalenia = zabudowa.Ustalenia(
            max_zabudowa_proc=_liczba_lub_none(plan, "max_zabudowa_proc"),
            min_intensywnosc=_liczba_lub_none(plan, "min_intensywnosc"),
            max_intensywnosc=_liczba_lub_none(plan, "max_intensywnosc"),
            min_pbc_proc=_liczba_lub_none(plan, "min_pbc_proc"),
            max_wysokosc_m=_liczba_lub_none(plan, "max_wysokosc_m"),
            max_kondygnacje=_liczba_lub_none(plan, "max_kondygnacje", int),
        )
        wynik = zabudowa.policz(
            float(dane.get("powierzchnia_dzialki") or 0), budynki, float(dane.get("pbc_m2") or 0), ustalenia
        )
    except (TypeError, ValueError) as e:
        komunikat = str(e) if isinstance(e, zabudowa.BladDanych) else "Wpisz liczby (np. 450 albo 0,6)."
        return jsonify({"blad": komunikat}), 400
    return jsonify(wynik)


@mpzp_bp.route("/eksport.geojson")
def eksport_geojson():
    """Działka i jej części w przeznaczeniach planu — do QGIS."""
    dzialka_id = request.args.get("id", "")
    try:
        dzialka = znajdz_dzialke_po_id(dzialka_id)
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400
    except BladULDK as e:
        return jsonify({"blad": str(e)}), 502
    if dzialka is None:
        return jsonify({"blad": "ULDK nie zna tej działki."}), 404

    cechy = [
        {
            "type": "Feature",
            "properties": {
                "warstwa": "dzialka",
                "id_dzialki": dzialka.id,
                "powierzchnia_m2": round(powierzchnia_m2(dzialka.geometria), 1),
            },
            "geometry": mapping(dzialka.geometria),
        }
    ]
    gmina = znajdz_gmine(dzialka.teryt_gminy)
    if gmina is not None:
        try:
            pary = znajdz_wydzielenia_dzialki(gmina, dzialka.geometria)
        except BladWFS as e:
            return jsonify({"blad": str(e)}), 502
        calosc = powierzchnia_m2(dzialka.geometria)
        szerokosc = dzialka.geometria.centroid.y
        for wydzielenie, czesc in pary:
            pole = powierzchnia_m2(czesc, szerokosc)
            cechy.append(
                {
                    "type": "Feature",
                    "properties": {
                        "warstwa": "czesc_w_przeznaczeniu",
                        "id_dzialki": dzialka.id,
                        "przeznaczenie": wydzielenie.atrybuty.get(gmina.pole_przeznaczenia),
                        "powierzchnia_m2": round(pole, 1),
                        "procent": round(100 * pole / calosc, 1) if calosc else None,
                        **{f"wfs_{k}": v for k, v in wydzielenie.atrybuty.items()},
                    },
                    "geometry": mapping(czesc),
                }
            )
    nazwa = "dzialka_" + dzialka.id.replace("/", "-").replace(".", "_") + ".geojson"
    return Response(
        json.dumps({"type": "FeatureCollection", "features": cechy}, ensure_ascii=False),
        mimetype="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )


# Kolory części działki w raporcie — stała kolejność, żeby ten sam
# układ zawsze wyglądał tak samo (kolor wg kolejności udziału).
KOLORY_RAPORTU = ["#34c759", "#ff9f0a", "#0a84ff", "#bf5af2", "#ff375f", "#64d2ff"]


@mpzp_bp.route("/raport")
def raport():
    """Raport działki do wydruku / zapisu jako PDF (Ctrl+P w przeglądarce)."""
    dzialka_id = request.args.get("id", "")
    try:
        dzialka = znajdz_dzialke_po_id(dzialka_id)
    except ValueError as e:
        abort(400, str(e))
    except BladULDK as e:
        abort(502, str(e))
    if dzialka is None:
        abort(404, "ULDK nie zna tej działki.")

    gmina = znajdz_gmine(dzialka.teryt_gminy)
    czesci, udzialy, blad = [], [], None
    if gmina is None:
        blad = f"Gmina tej działki nie jest jeszcze obsługiwana (pilotaż: {GMINA_PILOTAZOWA.nazwa})."
    else:
        try:
            pary = znajdz_wydzielenia_dzialki(gmina, dzialka.geometria)
            udzialy = udzialy_przeznaczen(gmina, dzialka)
        except BladWFS as e:
            pary, blad = [], str(e)
        kolor_symbolu = {u["przeznaczenie"]: i for i, u in enumerate(udzialy)}
        for u in udzialy:
            u["kolor"] = KOLORY_RAPORTU[kolor_symbolu[u["przeznaczenie"]] % len(KOLORY_RAPORTU)]
        # Na szkicu całe wydzielenia wokół działki, przycięte do okolicy.
        otoczenie = dzialka.geometria.buffer(dzialka.geometria.length * 0.15)
        for wydzielenie, czesc in pary:
            symbol = wydzielenie.atrybuty.get(gmina.pole_przeznaczenia) or "?"
            if symbol not in kolor_symbolu:
                continue
            try:
                ksztalt = wydzielenie.geometria.intersection(otoczenie)
            except GEOSException:
                ksztalt = czesc  # awaryjnie sama część w działce
            czesci.append((ksztalt, kolor_symbolu[symbol]))
        if not udzialy and blad is None:
            blad = "Brak planu miejscowego dla tej działki."

    czesci_id = dzialka.id.split(".")
    return render_template(
        "mpzp/raport.html",
        dzialka=dzialka,
        jednostka=czesci_id[0],
        obreb=czesci_id[1] if len(czesci_id) > 1 else "",
        numer=".".join(czesci_id[2:]),
        powierzchnia=powierzchnia_m2(dzialka.geometria),
        udzialy=udzialy,
        szkic=szkic_svg(dzialka.geometria, czesci),
        kolory=KOLORY_RAPORTU,
        blad=blad,
        gmina=gmina,
        data=datetime.now().strftime("%d.%m.%Y, %H:%M"),
    )


@mpzp_bp.route("/odswiez", methods=["POST"])
def odswiez():
    try:
        odswiez_warstwe(GMINA_PILOTAZOWA)
    except BladWFS as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify({"ok": True}), 200
