import json
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, render_template, request, url_for
from shapely.errors import GEOSException
from shapely.geometry import Point, mapping

from dane.uldk import BladULDK, Dzialka
from dane.uldk import znajdz_dzialke as _znajdz_dzialke
from dane.uldk import WZOR_ID_DZIALKI
from dane.uldk import szukaj_dzialek as _szukaj_dzialek
from dane.uldk import znajdz_dzialke_po_id as _znajdz_dzialke_po_id
from .baza import historia, zapisana, zapisane, zapisz_w_historii
from .gminy import GMINA_PILOTAZOWA, znajdz_gmine
from . import dxf_dzialki, karta, krajowe, uklady, uslugi
from .symbole import opisz_symbol
from .wfs import BladWFS, Wydzielenie
from .wfs import odswiez as _odswiez
from .wfs import wydzielenia_dzialki as _wydzielenia_dzialki
from .geometria import powierzchnia_m2, szkic_svg, szkice_w_jednej_skali, wymiary
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
plan_krajowy = krajowe.plan_w_punkcie


@mpzp_bp.route("/")
def index():
    return render_template("mpzp/index.html")


def _dzialka_na_json(dzialka: Dzialka) -> dict:
    return {
        "id": dzialka.id,
        "geometria": mapping(dzialka.geometria),
        "teryt_gminy": dzialka.teryt_gminy,
        "powierzchnia_m2": round(powierzchnia_m2(dzialka.geometria), 1),
        "wymiary": wymiary(dzialka.geometria),
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
    dane = {
        "dzialka": _dzialka_na_json(dzialka),
        "punkt": {"lat": punkt.y, "lon": punkt.x},
        "wspolrzedne": _wspolrzedne(punkt.y, punkt.x),
    }

    gmina = znajdz_gmine(dzialka.teryt_gminy)
    if gmina is None:
        return _wynik_krajowy(dzialka, punkt, dane)

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


def _wspolrzedne(lat: float, lon: float) -> list[dict]:
    """Punkt w WGS84 i w polskich układach płaskich (ETAP 36)."""
    wynik = [{"uklad": "WGS84", "epsg": 4326, "szerokosc": round(lat, 6), "dlugosc": round(lon, 6)}]
    if uklady.w_polsce(lat, lon):
        for uklad in (uklady.pl1992(lat, lon), uklady.pl2000(lat, lon)):
            wynik.append({**uklad, "x": round(uklad["x"], 2), "y": round(uklad["y"], 2)})
    return wynik


def _plan_krajowy_na_json(obiekty: list) -> dict:
    przeznaczenie = krajowe.rozpoznaj_przeznaczenie(obiekty)
    return {
        "przeznaczenie": przeznaczenie,
        "opis_przeznaczenia": opisz_symbol(przeznaczenie),
        "tytul": krajowe.tytul_planu(obiekty),
        "linki": krajowe.linki(obiekty),
        "obiekty": [{"warstwa": o.warstwa, "atrybuty": o.atrybuty} for o in obiekty],
    }


def _wynik_krajowy(dzialka: Dzialka, punkt: Point, dane: dict):
    """Gmina bez własnego WFS — plan z krajowej integracji GUGiK (ETAP 35)."""
    try:
        obiekty = plan_krajowy(punkt.y, punkt.x)
    except krajowe.BladKIMPZP as e:
        dane["blad"] = str(e)
        return jsonify(dane), 502
    if not obiekty:
        zapisz_w_historii(dzialka.id, None, punkt.y, punkt.x)
        dane["blad"] = (
            "Krajowa integracja planów nie ma planu miejscowego w tym miejscu. "
            "Część gmin nie przekazała jeszcze planów — sprawdź też geoportal gminy."
        )
        return jsonify(dane), 200
    dane["plan_krajowy"] = _plan_krajowy_na_json(obiekty)
    zapisz_w_historii(dzialka.id, dane["plan_krajowy"]["przeznaczenie"] or "plan", punkt.y, punkt.x)
    return jsonify(dane), 200


@mpzp_bp.route("/warstwy-krajowe")
def warstwy_krajowe():
    """Warstwy WMS do mapy: plany (KIMPZP) i działki (KIEG)."""
    nazwy, z_uslugi = krajowe.nazwy_warstw()
    return jsonify(
        {
            "plany": {
                "url": krajowe.URL_KIMPZP,
                "warstwy": ",".join(nazwy),
                "z_uslugi": z_uslugi,
                "mercator": krajowe.czy_mercator(),
            },
            "dzialki": {"url": krajowe.URL_KIEG, "warstwy": krajowe.WARSTWY_KIEG},
        }
    )


@mpzp_bp.route("/usluga/<klucz>/warstwa")
def warstwa_uslugi(klucz):
    """Warstwa WMS innej usługi GUGiK (plan ogólny, ceny) do mapy — z GetCapabilities."""
    if klucz not in uslugi.USLUGI:
        abort(404)
    warstwa = uslugi.warstwa_mapy(klucz)
    if warstwa is None:
        return jsonify({"blad": f"{uslugi.USLUGI[klucz]['nazwa']}: usługa GUGiK nie odpowiada."}), 502
    return jsonify({**warstwa, "nazwa": uslugi.USLUGI[klucz]["nazwa"]})


@mpzp_bp.route("/usluga/<klucz>/punkt")
def usluga_w_punkcie(klucz):
    """Obiekty usługi (np. strefa planu ogólnego) w punkcie — atrybuty jak z usługi."""
    if klucz not in uslugi.USLUGI:
        abort(404)
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None or not uklady.w_polsce(lat, lon):
        return jsonify({"blad": "Wymagane lat i lon punktu w Polsce."}), 400
    try:
        obiekty = uslugi.w_punkcie(klucz, lat, lon)
    except uslugi.BladUslugi as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify({"nazwa": uslugi.USLUGI[klucz]["nazwa"], "obiekty": obiekty, "linki": uslugi.linki(obiekty)})


class _BladEksportu(Exception):
    def __init__(self, tresc: str, kod: int):
        super().__init__(tresc)
        self.kod = kod


def _cechy_eksportu(dzialka_id: str):
    """Działka i jej części w przeznaczeniach (WFS gminy) albo przeznaczenie
    z KIMPZP — wspólne dla GeoJSON i (ETAP 123) DXF."""
    try:
        dzialka = znajdz_dzialke_po_id(dzialka_id)
    except ValueError as e:
        raise _BladEksportu(str(e), 400) from e
    except BladULDK as e:
        raise _BladEksportu(str(e), 502) from e
    if dzialka is None:
        raise _BladEksportu("ULDK nie zna tej działki.", 404)

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
    if gmina is None:
        # Bez WFS nie ma części działki — dopisujemy przeznaczenie z KIMPZP.
        punkt = dzialka.geometria.representative_point()
        try:
            obiekty = plan_krajowy(punkt.y, punkt.x)
        except krajowe.BladKIMPZP:
            obiekty = []  # sama działka też się przyda w QGIS
        if obiekty:
            cechy[0]["properties"]["przeznaczenie_kimpzp"] = krajowe.rozpoznaj_przeznaczenie(obiekty)
            cechy[0]["properties"]["plan_kimpzp"] = krajowe.tytul_planu(obiekty)
    else:
        try:
            pary = znajdz_wydzielenia_dzialki(gmina, dzialka.geometria)
        except BladWFS as e:
            raise _BladEksportu(str(e), 502) from e
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
    return dzialka, cechy


def _nazwa_pliku(dzialka_id: str, rozszerzenie: str) -> str:
    return "dzialka_" + dzialka_id.replace("/", "-").replace(".", "_") + rozszerzenie


@mpzp_bp.route("/eksport.geojson")
def eksport_geojson():
    """Działka i jej części w przeznaczeniach planu — do QGIS."""
    try:
        dzialka, cechy = _cechy_eksportu(request.args.get("id", ""))
    except _BladEksportu as e:
        return jsonify({"blad": str(e)}), e.kod
    return Response(
        json.dumps({"type": "FeatureCollection", "features": cechy}, ensure_ascii=False),
        mimetype="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={_nazwa_pliku(dzialka.id, '.geojson')}"},
    )


@mpzp_bp.route("/eksport.dxf")
def eksport_dxf():
    """ETAP 123: to samo co GeoJSON, do programu CAD (PL-2000 albo ?uklad=pl1992)."""
    uklad = request.args.get("uklad", "pl2000")
    if uklad not in dxf_dzialki.UKLADY:
        return jsonify({"blad": "Układ: pl2000 albo pl1992."}), 400
    try:
        dzialka, cechy = _cechy_eksportu(request.args.get("id", ""))
    except _BladEksportu as e:
        return jsonify({"blad": str(e)}), e.kod
    tekst, opis_ukladu = dxf_dzialki.dzialka_dxf(cechy, uklad)
    return Response(tekst, mimetype="application/dxf", headers={
        "Content-Disposition": f"attachment; filename={_nazwa_pliku(dzialka.id, f'_{uklad}.dxf')}", "X-Uklad-Wspolrzednych": opis_ukladu})


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
    czesci, udzialy, blad, plan = [], [], None, None
    if gmina is None:
        # Bez WFS gminy: plan z krajowej integracji, w punkcie wewnątrz działki.
        punkt = dzialka.geometria.representative_point()
        try:
            obiekty = plan_krajowy(punkt.y, punkt.x)
        except krajowe.BladKIMPZP as e:
            obiekty, blad = [], str(e)
        if obiekty:
            plan = _plan_krajowy_na_json(obiekty)
        elif blad is None:
            blad = "Krajowa integracja planów nie ma planu miejscowego dla tej działki."
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
    # Karta działki (ETAP 80): wymiary, położenie, ortofotomapa z obrysem.
    bbox = karta.prostokat(dzialka.geometria)
    return render_template(
        "mpzp/raport.html",
        wymiary=wymiary(dzialka.geometria),
        polozenie=karta.polozenie(dzialka.geometria),
        orto={
            "obecna": karta.adres_obrazu(karta.URL_ORTO, "Raster", bbox),
            "bbox": [round(v, 2) for v in bbox],
            "obrys": karta.obrys_svg(dzialka.geometria, bbox),
            "szerokosc": karta.SZEROKOSC_PX,
            "wysokosc": karta.WYSOKOSC_PX,
        },
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
        plan_krajowy=plan,
        zapis=zapisana(dzialka.id),
        geometria_okolicy=mapping(dzialka.geometria),  # ETAP 115: ceny w okolicy (moduł ceny)
        data=datetime.now().strftime("%d.%m.%Y, %H:%M"),
    )


@mpzp_bp.route("/odswiez", methods=["POST"])
def odswiez():
    try:
        odswiez_warstwe(GMINA_PILOTAZOWA)
    except BladWFS as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify({"ok": True}), 200


# ---------- Porównanie działek (ETAP 53) ----------

MAKS_DO_POROWNANIA = 4
LADNE_PODZIALKI_M = (1, 2, 5, 10, 20, 25, 50, 100, 200, 500)


def _dzialka_do_porownania(dzialka_id: str) -> dict:
    """Wymiary i przeznaczenie jednej działki; błąd usługi — w polu „blad”."""
    wpis = {"id": dzialka_id, "zapis": zapisana(dzialka_id)}
    try:
        dzialka = znajdz_dzialke_po_id(dzialka_id)
    except (ValueError, BladULDK) as e:
        return {**wpis, "blad": str(e)}
    if dzialka is None:
        return {**wpis, "blad": "ULDK nie zna tej działki."}
    wpis.update(
        geometria=dzialka.geometria,
        powierzchnia_m2=powierzchnia_m2(dzialka.geometria),
        wymiary=wymiary(dzialka.geometria),
        udzialy=[],
        plan=None,
    )
    wpis["obszar_wz_m"] = max(3 * wpis["wymiary"]["szerokosc_m"], 50.0)
    gmina = znajdz_gmine(dzialka.teryt_gminy)
    try:
        if gmina is not None:
            wpis["udzialy"] = udzialy_przeznaczen(gmina, dzialka)
        else:
            punkt = dzialka.geometria.representative_point()
            obiekty = plan_krajowy(punkt.y, punkt.x)
            wpis["plan"] = _plan_krajowy_na_json(obiekty) if obiekty else None
    except (BladWFS, krajowe.BladKIMPZP) as e:
        wpis["blad_planu"] = str(e)
    return wpis


@mpzp_bp.route("/porownanie")
def porownanie():
    """Wybór działek z „Moich działek” i tabela porównania obok siebie."""
    wybrane = list(dict.fromkeys(request.args.getlist("id")))[:MAKS_DO_POROWNANIA]
    dzialki = [_dzialka_do_porownania(i) for i in wybrane]
    z_geometria = [d for d in dzialki if "geometria" in d]
    podzialka = None
    if z_geometria:
        szkice, skala = szkice_w_jednej_skali([d["geometria"] for d in z_geometria])
        for d, szkic in zip(z_geometria, szkice):
            d["szkic"] = szkic
        # podziałka ok. 1/4 szerokości szkicu, „ładna” długość
        metry = max((m for m in LADNE_PODZIALKI_M if m * skala <= 60), default=LADNE_PODZIALKI_M[0])
        podzialka = {"metry": metry, "px": metry * skala}
    return render_template(
        "mpzp/porownanie.html",
        zapisane=zapisane(),
        wybrane=wybrane,
        dzialki=dzialki,
        podzialka=podzialka,
        maks=MAKS_DO_POROWNANIA,
    )


# Pozostałe trasy modułu — w osobnych plikach, rejestrują się na mpzp_bp.
# Import na końcu, bo tamte pliki importują mpzp_bp z tego modułu.
# ---------- ostatnio używane na stronie głównej (ETAP 141) ----------


def ostatnie(limit: int = 3) -> list[dict]:
    """Ostatnio sprawdzone działki (historia wyszukiwania)."""
    return [{"tytul": f"Działka {d['dzialka_id']}", "opis": d["przeznaczenie"] or "bez planu w danych",
             "kiedy": d["data_sprawdzenia"], "url": url_for("mpzp.raport", id=d["dzialka_id"])}
            for d in historia()[:limit]]


from . import trasy_kronika, trasy_narzedzia, trasy_zapisane  # noqa: E402, F401


# ---------- wyszukiwarka globalna (ETAP 128) ----------


def wyszukaj(fraza: str) -> list[dict]:
    """Zapisane działki („Moje działki”): numer, przeznaczenie, notatka."""
    szukane = fraza.casefold()
    wyniki = []
    for d in zapisane():
        if szukane in " ".join((d["dzialka_id"], d["przeznaczenie"] or "", d["notatka"] or "")).casefold():
            opis = ", ".join(x for x in (d["przeznaczenie"], d["notatka"][:120] if d["notatka"] else None) if x)
            wyniki.append({"tytul": f"Działka {d['dzialka_id']}", "opis": opis or "zapisana działka",
                           "url": url_for("mpzp.raport", id=d["dzialka_id"])})
    return wyniki[:10]
