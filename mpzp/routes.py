import csv
import io
import json
import math
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, render_template, request
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point, Polygon, mapping, shape

from dane.uldk import BladULDK, Dzialka
from dane.uldk import znajdz_dzialke as _znajdz_dzialke
from dane.uldk import WZOR_ID_DZIALKI
from dane.uldk import szukaj_dzialek as _szukaj_dzialek
from dane.uldk import znajdz_dzialke_po_id as _znajdz_dzialke_po_id
from .baza import historia, usun_zapisana, zapisana, zapisane, zapisz_dzialke, zapisz_w_historii
from .gminy import GMINA_PILOTAZOWA, znajdz_gmine
from . import krajowe, skala, uklady, zabudowa
from .symbole import opisz_symbol
from .wfs import BladWFS, Wydzielenie
from .wfs import odswiez as _odswiez
from .wfs import wydzielenia_dzialki as _wydzielenia_dzialki
from .geometria import obszar_analizowany, powierzchnia_m2, szkic_svg, w_metrach, wymiary
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


# ---------- Moje działki (ETAP 44) ----------

MAKS_DLUGOSC_NOTATKI = 2000


@mpzp_bp.route("/zapisane")
def lista_zapisanych():
    return jsonify(zapisane())


@mpzp_bp.route("/zapisane", methods=["POST"])
def zapisz_zapisana():
    """Dodaje działkę do „Moich działek” albo zmienia jej notatkę."""
    dane = request.get_json(silent=True) or {}
    dzialka_id = str(dane.get("id") or "").strip()
    if not WZOR_ID_DZIALKI.match(dzialka_id):
        return jsonify({"blad": "Niepoprawny identyfikator działki."}), 400
    try:
        lat = _liczba_skonczona(dane.get("lat"))
        lon = _liczba_skonczona(dane.get("lon"))
        powierzchnia = dane.get("powierzchnia_m2")
        powierzchnia = None if powierzchnia in (None, "") else _liczba_skonczona(powierzchnia)
    except (TypeError, ValueError):
        return jsonify({"blad": "Współrzędne i powierzchnia muszą być liczbami."}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"blad": "Współrzędne poza zakresem."}), 400
    notatka = str(dane.get("notatka") or "").strip()
    if len(notatka) > MAKS_DLUGOSC_NOTATKI:
        return jsonify({"blad": f"Notatka może mieć najwyżej {MAKS_DLUGOSC_NOTATKI} znaków."}), 400
    przeznaczenie = dane.get("przeznaczenie")
    przeznaczenie = str(przeznaczenie)[:100] if przeznaczenie else None
    return jsonify(zapisz_dzialke(dzialka_id, przeznaczenie, lat, lon, powierzchnia, notatka))


@mpzp_bp.route("/zapisane", methods=["DELETE"])
def usun_z_zapisanych():
    if not usun_zapisana(request.args.get("id", "")):
        return jsonify({"blad": "Tej działki nie ma w „Moich działkach”."}), 404
    return jsonify({"ok": True})


@mpzp_bp.route("/zapisane.csv")
def zapisane_csv():
    """„Moje działki” do arkusza (średnik i BOM — Excel z polskimi ustawieniami)."""
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";")
    zapis.writerow(["id_dzialki", "przeznaczenie", "powierzchnia_m2", "szerokosc_geogr", "dlugosc_geogr", "notatka", "data_dodania"])
    for w in zapisane():
        powierzchnia = "" if w["powierzchnia_m2"] is None else f"{w['powierzchnia_m2']:.1f}".replace(".", ",")
        zapis.writerow(
            [w["dzialka_id"], w["przeznaczenie"] or "", powierzchnia, f"{w['lat']:.6f}", f"{w['lon']:.6f}", w["notatka"], w["data_dodania"]]
        )
    return Response(
        "\ufeff" + bufor.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=moje_dzialki.csv"},
    )


@mpzp_bp.route("/obszar-analizowany", methods=["POST"])
def obszar_analizowany_wz():
    """Obszar analizowany do decyzji WZ dla geometrii działki z mapy (ETAP 43)."""
    dane = request.get_json(silent=True) or {}
    try:
        geometria = shape(dane["geometria"])
        front = _liczba_skonczona(dane.get("front"))
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return jsonify({"blad": "Wymagane: geometria działki (GeoJSON) i szerokość frontu w metrach."}), 400
    if geometria.geom_type not in ("Polygon", "MultiPolygon") or geometria.is_empty:
        return jsonify({"blad": "Geometria działki musi być wielokątem."}), 400
    if powierzchnia_m2(geometria) > 10_000_000:  # 10 km² — to nie jest działka budowlana
        return jsonify({"blad": "Za duży obszar jak na działkę."}), 400
    try:
        return jsonify(obszar_analizowany(geometria, front))
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400


MAKS_PUNKTOW_POMIARU = 500


@mpzp_bp.route("/pomiar", methods=["POST"])
def pomiar():
    """Długość łamanej i powierzchnia wieloboku z punktów klikniętych na mapie.

    Te same wzory co powierzchnia działki (mpzp/geometria.py) — lokalna
    skala na średniej szerokości; dla odległości do kilkunastu km błąd
    jest znikomy.
    """
    dane = request.get_json(silent=True) or {}
    try:
        punkty = [(_liczba_skonczona(p[1]), _liczba_skonczona(p[0])) for p in dane.get("punkty") or []]
    except (TypeError, ValueError, IndexError, KeyError):
        return jsonify({"blad": "Punkty to lista par [szerokość, długość]."}), 400
    if not 2 <= len(punkty) <= MAKS_PUNKTOW_POMIARU:
        return jsonify({"blad": f"Pomiar wymaga od 2 do {MAKS_PUNKTOW_POMIARU} punktów."}), 400
    if any(not (-180 <= lon <= 180 and -90 <= lat <= 90) for lon, lat in punkty):
        return jsonify({"blad": "Współrzędne poza zakresem."}), 400

    szerokosc = sum(lat for _, lat in punkty) / len(punkty)
    linia = w_metrach(LineString(punkty), szerokosc)
    wynik = {
        "dlugosc_m": round(linia.length, 2),
        "ostatni_odcinek_m": round(LineString(linia.coords[-2:]).length, 2),
    }
    if len(punkty) >= 3:
        wielobok = w_metrach(Polygon(punkty), szerokosc)
        wynik["powierzchnia_m2"] = round(wielobok.area, 1)
        wynik["obwod_m"] = round(wielobok.exterior.length, 2)
        if not wielobok.is_valid:
            wynik["uwaga"] = "Obrys przecina sam siebie — powierzchnia jest niewiarygodna."
    return jsonify(wynik)


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


def _liczba_skonczona(tekst) -> float:
    """float z pola formularza, ale tylko skończony: „nan”, „inf”, „1e400”
    też są dla Pythona liczbami, a zepsułyby odpowiedź JSON."""
    wartosc = float(str(tekst).strip().replace(",", ".").replace(" ", ""))
    if not math.isfinite(wartosc):
        raise ValueError("liczba nieskończona")
    return wartosc


# ---------- Kalkulator skali mapy (ETAP 30) ----------


@mpzp_bp.route("/skala")
def skala_strona():
    return render_template(
        "mpzp/skala.html", skale=skala.SKALE_STANDARDOWE, arkusze=list(skala.ARKUSZE_MM)
    )


@mpzp_bp.route("/skala/licz", methods=["POST"])
def skala_licz():
    """Wszystkie przeliczenia naraz; puste pole = tej części nie liczymy."""
    dane = request.get_json(silent=True) or {}

    def liczba(klucz):
        wartosc = str(dane.get(klucz, "")).strip()
        return _liczba_skonczona(wartosc) if wartosc else None

    try:
        mianownik = liczba("mianownik")
        if mianownik is None:
            raise skala.BladSkali("Podaj skalę (np. 1000 dla 1:1000).")
        wynik = {"mianownik": mianownik}
        if (v := liczba("dlugosc_rysunek")) is not None:
            wynik["dlugosc_teren_m"] = skala.dlugosc_w_terenie(v, dane.get("jednostka_rysunek", "cm"), mianownik)
        if (v := liczba("dlugosc_teren")) is not None:
            wynik["dlugosc_rysunek_mm"] = skala.dlugosc_na_rysunku(v, dane.get("jednostka_teren", "m"), mianownik)
        if (v := liczba("pow_rysunek_cm2")) is not None:
            wynik["pow_teren_m2"] = skala.powierzchnia_w_terenie(v, mianownik)
        if (v := liczba("pow_teren")) is not None:
            wynik["pow_rysunek_cm2"] = skala.powierzchnia_na_rysunku(v, dane.get("jednostka_pow", "m2"), mianownik)
        szer, wys = liczba("teren_szer_m"), liczba("teren_wys_m")
        if szer is not None and wys is not None:
            margines = liczba("margines_mm")
            wynik["dobor"] = skala.dobierz_skale(
                szer, wys, dane.get("arkusz", "A3"), 20 if margines is None else margines
            )
    except KeyError:
        return jsonify({"blad": "Nieznana jednostka."}), 400
    except (ValueError, skala.BladSkali) as e:
        komunikat = str(e) if isinstance(e, skala.BladSkali) else "Wpisz liczby (np. 4,5)."
        return jsonify({"blad": komunikat}), 400
    return jsonify(wynik)


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
    liczba = _liczba_skonczona(wartosc)
    return int(liczba) if typ is int else liczba


@mpzp_bp.route("/kalkulator/licz", methods=["POST"])
def kalkulator_licz():
    dane = request.get_json(silent=True) or {}
    try:
        # Budynek z rzutem, ale bez liczby kondygnacji, dałby po cichu
        # powierzchnię całkowitą 0 — lepiej poprosić o uzupełnienie.
        for b in dane.get("budynki", []):
            if str(b.get("rzut_m2") or "").strip() and not str(b.get("kondygnacje") or "").strip():
                raise zabudowa.BladDanych("Podaj liczbę kondygnacji nadziemnych każdego budynku.")
        budynki = [
            zabudowa.Budynek(
                rzut_m2=_liczba_skonczona(b.get("rzut_m2") or 0),
                kondygnacje=int(_liczba_skonczona(b.get("kondygnacje") or 0)),
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
            _liczba_skonczona(dane.get("powierzchnia_dzialki") or 0),
            budynki,
            _liczba_skonczona(dane.get("pbc_m2") or 0),
            ustalenia,
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
        plan_krajowy=plan,
        zapis=zapisana(dzialka.id),
        data=datetime.now().strftime("%d.%m.%Y, %H:%M"),
    )


@mpzp_bp.route("/odswiez", methods=["POST"])
def odswiez():
    try:
        odswiez_warstwe(GMINA_PILOTAZOWA)
    except BladWFS as e:
        return jsonify({"blad": str(e)}), 502
    return jsonify({"ok": True}), 200
