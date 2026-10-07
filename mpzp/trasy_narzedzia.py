"""Narzędzia modułu mpzp niezależne od konkretnej działki z ULDK/planu:
kalkulatory skali i zabudowy, pomiar na mapie, obszar analizowany WZ
(z geometrii przesłanej z mapy) i słownik symboli.

Trasy rejestrują się na wspólnym blueprincie `mpzp_bp` (import w
mpzp/routes.py na końcu pliku).
"""

from flask import jsonify, render_template, request
from shapely.errors import ShapelyError
from shapely.geometry import LineString, Polygon, shape

from . import skala, zabudowa
from .geometria import obszar_analizowany, powierzchnia_m2, w_metrach
from .liczby import liczba_skonczona
from .routes import mpzp_bp
from .symbole import opisz_symbol, wszystkie_symbole


# ---------- Słownik symboli (ETAP 45) ----------


@mpzp_bp.route("/symbole")
def symbole():
    return render_template("mpzp/symbole.html", symbole=wszystkie_symbole())


@mpzp_bp.route("/symbole/rozszyfruj")
def rozszyfruj_symbol():
    """„3MN/U” → opisy liter; do pola „rozszyfruj” na stronie słownika."""
    symbol = (request.args.get("q") or "").strip()[:40]
    return jsonify({"symbol": symbol, "opis": opisz_symbol(symbol)})


@mpzp_bp.route("/obszar-analizowany", methods=["POST"])
def obszar_analizowany_wz():
    """Obszar analizowany do decyzji WZ dla geometrii działki z mapy (ETAP 43)."""
    dane = request.get_json(silent=True) or {}
    try:
        geometria = shape(dane["geometria"])
        front = liczba_skonczona(dane.get("front"))
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, ShapelyError):
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
        punkty = [(liczba_skonczona(p[1]), liczba_skonczona(p[0])) for p in dane.get("punkty") or []]
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
        return liczba_skonczona(wartosc) if wartosc else None

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
    # ETAP 237: ?dzialka=…&powierzchnia=… można powtórzyć — kilka działek razem
    identyfikatory = request.args.getlist("dzialka")
    powierzchnie = request.args.getlist("powierzchnia", type=float)
    dzialki = [
        {"identyfikator": identyfikator[:80], "powierzchnia_m2": powierzchnie[i] if i < len(powierzchnie) else None}
        for i, identyfikator in enumerate(identyfikatory[: zabudowa.MAKS_DZIALEK])
    ]
    if not dzialki and powierzchnie:
        dzialki = [{"identyfikator": "", "powierzchnia_m2": powierzchnie[0]}]
    return render_template("mpzp/kalkulator.html", dzialki=dzialki)


def _liczba_lub_none(slownik: dict, klucz: str, typ=float):
    wartosc = slownik.get(klucz)
    if wartosc in (None, ""):
        return None
    liczba = liczba_skonczona(wartosc)
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
                rzut_m2=liczba_skonczona(b.get("rzut_m2") or 0),
                kondygnacje=int(liczba_skonczona(b.get("kondygnacje") or 0)),
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
        # ETAP 237: kilka działek razem — wskaźniki dla sumy powierzchni
        teren = None
        wiersze = [d for d in dane.get("dzialki") or [] if str(d.get("powierzchnia_m2") or "").strip()]
        if wiersze:
            teren = zabudowa.teren_inwestycji([
                zabudowa.Dzialka(str(d.get("identyfikator") or "").strip()[:80], liczba_skonczona(d["powierzchnia_m2"]))
                for d in wiersze
            ])
            powierzchnia = teren["powierzchnia_m2"]
        else:
            powierzchnia = liczba_skonczona(dane.get("powierzchnia_dzialki") or 0)
        wynik = zabudowa.policz(
            powierzchnia,
            budynki,
            liczba_skonczona(dane.get("pbc_m2") or 0),
            ustalenia,
        )
    except (TypeError, ValueError) as e:
        komunikat = str(e) if isinstance(e, zabudowa.BladDanych) else "Wpisz liczby (np. 450 albo 0,6)."
        return jsonify({"blad": komunikat}), 400
    if teren:
        wynik["teren"] = teren
    return jsonify(wynik)
