"""Moduł przepisy: biblioteka aktów prawnych (PDF) i wyszukiwarka (ETAP 61)."""

import os
import uuid

from flask import Blueprint, abort, jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from dane import gemini, sejm
from fiszki import zewnetrzne as fiszki_zewnetrzne

from . import baza, porownanie, pytania
from .odeslania import mapa_jednostek, z_odeslaniami
from .slowniczek import slowniczek
from .tekst import BladPdf, podziel, strony_z_pdf, teksty_stron

przepisy_bp = Blueprint(
    "przepisy",
    __name__,
    template_folder="templates",
    static_folder="static",
)

MAKS_DLUGOSC_NAZWY = 200


def _akt_albo_404(akt_id: int) -> dict:
    akt = baza.akt(akt_id)
    if akt is None:
        abort(404)
    return akt


def nazwa_z_tytulu(jednostki: list[dict], nazwa_pliku: str) -> str:
    """Nazwa aktu: początek tytułu z PDF-a („USTAWA z dnia … o …”), a bez
    niego — nazwa pliku bez rozszerzenia."""
    if jednostki and jednostki[0]["oznaczenie"] == "Tytuł":
        tytul = " ".join(jednostki[0]["tekst"].split())
        if tytul:
            return tytul[:MAKS_DLUGOSC_NAZWY]
    return os.path.splitext(nazwa_pliku)[0][:MAKS_DLUGOSC_NAZWY] or "Akt bez nazwy"


def podsumowanie() -> dict:
    """Liczba aktów — na kartę modułu na stronie głównej."""
    akty = baza.lista_aktow()
    return {"liczba": len(akty), "jednostki": sum(a["liczba_jednostek"] for a in akty)}


@przepisy_bp.route("/")
def index():
    return render_template(
        "przepisy/index.html",
        akty=baza.lista_aktow(),
        historia=baza.historia_pytan(),
        blad=request.args.get("blad"),
    )


@przepisy_bp.route("/akty", methods=["POST"])
def dodaj_akt():
    plik = request.files.get("plik")
    if plik is None or not plik.filename:
        return redirect(url_for("przepisy.index", blad="Nie wybrano pliku."))
    if not plik.filename.lower().endswith(".pdf") or plik.read(5) != b"%PDF-":
        return redirect(url_for("przepisy.index", blad="To nie jest plik PDF."))
    plik.seek(0)
    nazwa_na_dysku = f"{uuid.uuid4().hex}_{secure_filename(plik.filename) or 'akt.pdf'}"
    plik.save(os.path.join(baza.folder_plikow(), nazwa_na_dysku))
    try:
        akt_id = _zapisz_akt(nazwa_na_dysku, plik.filename)
    except BladPdf as e:
        return redirect(url_for("przepisy.index", blad=str(e)))
    return redirect(url_for("przepisy.widok_aktu", akt_id=akt_id))


def _zapisz_akt(nazwa_na_dysku: str, nazwa_pliku: str, nazwa: str | None = None) -> int:
    """PDF już zapisany w folderze modułu → podział na jednostki i wpis w bazie.
    Przy błędzie odczytu usuwa plik i przepuszcza BladPdf."""
    sciezka = os.path.join(baza.folder_plikow(), nazwa_na_dysku)
    try:
        strony = strony_z_pdf(sciezka)
    except BladPdf:
        os.remove(sciezka)
        raise
    jednostki = podziel(strony)
    return baza.dodaj_akt(nazwa or nazwa_z_tytulu(jednostki, nazwa_pliku), nazwa_na_dysku, len(strony), jednostki)


# ---------- akty z API Sejmu (ETAP 88) ----------


@przepisy_bp.route("/sejm/szukaj")
def szukaj_w_sejmie():
    try:
        return jsonify(sejm.szukaj_aktow(request.args.get("q", "")))
    except sejm.BladSejmu as e:
        return jsonify({"blad": str(e)}), 502


@przepisy_bp.route("/akty/<int:akt_id>/aktualnosc")
def aktualnosc_aktu(akt_id):
    """Czy w Dzienniku Ustaw jest nowszy tekst jednolity tej ustawy (ETAP 101)."""
    akt = _akt_albo_404(akt_id)
    try:
        return jsonify(sejm.nowsze_teksty_jednolite(akt["nazwa"]))
    except sejm.BladSejmu as e:
        return jsonify({"blad": str(e)}), 422 if "pobranych z Dziennika" in str(e) else 502


@przepisy_bp.route("/sejm/pobierz", methods=["POST"])
def pobierz_z_sejmu():
    """Pobiera urzędowy PDF aktu i dodaje go jak wgrany plik."""
    dane = request.get_json(silent=True) or {}
    try:
        rok, pozycja = int(dane.get("rok")), int(dane.get("pozycja"))
    except (TypeError, ValueError):
        return jsonify({"blad": "Wymagane rok i pozycja (liczby)."}), 400
    tytul = " ".join(str(dane.get("tytul") or "").split())
    try:
        pdf = sejm.pobierz_pdf(rok, pozycja)
    except sejm.BladSejmu as e:
        return jsonify({"blad": str(e)}), 502
    nazwa_na_dysku = f"{uuid.uuid4().hex}_DU_{rok}_{pozycja}.pdf"
    with open(os.path.join(baza.folder_plikow(), nazwa_na_dysku), "wb") as f:
        f.write(pdf)
    nazwa = f"{tytul} (Dz.U. {rok} poz. {pozycja})"[:MAKS_DLUGOSC_NAZWY] if tytul else None
    try:
        akt_id = _zapisz_akt(nazwa_na_dysku, f"Dz.U. {rok} poz. {pozycja}", nazwa)
    except BladPdf as e:
        return jsonify({"blad": str(e)}), 422
    return jsonify({"id": akt_id, "url": url_for("przepisy.widok_aktu", akt_id=akt_id)}), 201


@przepisy_bp.route("/akty/<int:akt_id>")
def widok_aktu(akt_id):
    akt = _akt_albo_404(akt_id)
    jednostki = baza.jednostki_aktu(akt_id)
    mapa = mapa_jednostek(jednostki)
    for j in jednostki:  # ETAP 121: „art. 15 ust. 2” → odnośnik do artykułu tego aktu
        j["tekst_html"] = z_odeslaniami(j["tekst"], mapa, j["id"])
    return render_template("przepisy/akt.html", akt=akt, jednostki=jednostki, slowniczek=slowniczek(jednostki))


@przepisy_bp.route("/akty/<int:akt_id>/slowniczek")
def slowniczek_aktu(akt_id):
    """ETAP 120: definicje ustawowe i skróty z tekstu aktu (JSON)."""
    _akt_albo_404(akt_id)
    return jsonify(slowniczek(baza.jednostki_aktu(akt_id)))


@przepisy_bp.route("/akty/<int:akt_id>/plik")
def plik_aktu(akt_id):
    akt = _akt_albo_404(akt_id)
    return send_from_directory(baza.folder_plikow(), akt["nazwa_pliku"], mimetype="application/pdf")


@przepisy_bp.route("/akty/<int:akt_id>", methods=["PUT"])
def zmien_nazwe(akt_id):
    _akt_albo_404(akt_id)
    nazwa = " ".join(str((request.get_json(silent=True) or {}).get("nazwa") or "").split())
    if not nazwa or len(nazwa) > MAKS_DLUGOSC_NAZWY:
        return jsonify({"blad": f"Nazwa musi mieć od 1 do {MAKS_DLUGOSC_NAZWY} znaków."}), 400
    baza.zmien_nazwe(akt_id, nazwa)
    return jsonify(baza.akt(akt_id))


@przepisy_bp.route("/akty/<int:akt_id>", methods=["DELETE"])
def usun_akt(akt_id):
    _akt_albo_404(akt_id)
    nazwa_pliku = baza.usun_akt(akt_id)
    try:
        os.remove(os.path.join(baza.folder_plikow(), nazwa_pliku))
    except OSError:
        pass  # plik mógł zniknąć ręcznie — wpis w bazie i tak usunięty
    return jsonify({"ok": True})


@przepisy_bp.route("/szukaj")
def szukaj():
    tekst = (request.args.get("q") or "").strip()[:300]
    akt_id = request.args.get("akt", type=int)
    return jsonify({"zapytanie": tekst, "wyniki": baza.szukaj(tekst, akt_id) if tekst else []})


@przepisy_bp.route("/pytanie", methods=["POST"])
def zadaj_pytanie():
    """Pytanie → jednostki z bazy → odpowiedź modelu sprawdzona w źródle."""
    dane = request.get_json(silent=True) or {}
    pytanie = " ".join(str(dane.get("pytanie") or "").split())
    if not pytanie:
        return jsonify({"blad": "Wpisz pytanie."}), 400
    if len(pytanie) > pytania.MAKS_DLUGOSC_PYTANIA:
        return jsonify({"blad": f"Pytanie może mieć najwyżej {pytania.MAKS_DLUGOSC_PYTANIA} znaków."}), 400
    akt_id = dane.get("akt") or None
    if akt_id is not None and (not isinstance(akt_id, int) or baza.akt(akt_id) is None):
        return jsonify({"blad": "Nie ma takiego aktu."}), 400

    jednostki = pytania.kandydaci(pytanie, akt_id)
    if not jednostki:
        return jsonify({"blad": "W wgranych aktach nie ma przepisów ze słowami z pytania. Zadaj je innymi słowami albo wgraj właściwy akt."}), 404
    try:
        surowa = gemini.odpowiedz_z_przepisow(pytanie, [pytania.fragment_dla_modelu(j) for j in jednostki])
        wynik = pytania.sprawdz(surowa, jednostki, pytanie)
    except (gemini.BladGemini, pytania.BladOdpowiedzi) as e:
        return jsonify({"blad": str(e)}), 502
    wynik["przeszukane"] = [{"oznaczenie": j["oznaczenie"], "nazwa_aktu": j["nazwa_aktu"]} for j in jednostki]
    pytanie_id = baza.zapisz_pytanie(pytanie, akt_id, wynik)
    return jsonify({"id": pytanie_id, "pytanie": pytanie, **wynik})


@przepisy_bp.route("/pytania/<int:pytanie_id>", methods=["DELETE"])
def usun_pytanie(pytanie_id):
    if not baza.usun_pytanie(pytanie_id):
        abort(404)
    return jsonify({"ok": True})


@przepisy_bp.route("/pytania/<int:pytanie_id>/fiszka", methods=["POST"])
def fiszka_z_cytatu(pytanie_id):
    """Fiszka z cytatu odpowiedzi (ETAP 68): kotwica w PDF-ie aktu — strona,
    na której naprawdę jest cytat, i sam cytat jako fragment do podświetlenia."""
    p = baza.pytanie(pytanie_id)
    if p is None:
        abort(404)
    dane = request.get_json(silent=True) or {}
    cytaty = p["wynik"].get("cytaty", [])
    nr = dane.get("cytat")
    if not isinstance(nr, int) or isinstance(nr, bool) or not 0 <= nr < len(cytaty):
        return jsonify({"blad": "Nie ma takiego cytatu."}), 400
    c = cytaty[nr]
    akt = baza.akt(c["akt_id"])
    if akt is None:
        return jsonify({"blad": "Akt z tym cytatem został usunięty."}), 404
    sciezka = os.path.join(baza.folder_plikow(), akt["nazwa_pliku"])
    j = baza.jednostka(c["jednostka_id"])
    strona = c["strona"]
    if j is not None:
        strona = pytania.strona_cytatu(teksty_stron(sciezka, j["strona_od"], j["strona_do"]), c["cytat"], strona)
    try:
        wynik = fiszki_zewnetrzne.dodaj_fiszke(
            sciezka, f"{akt['nazwa'][:120]}.pdf", strona, c["cytat"],
            str(dane.get("pytanie") or ""), str(dane.get("odpowiedz") or ""), dane.get("tematy"),
        )
    except fiszki_zewnetrzne.BladFiszki as e:
        return jsonify({"blad": str(e)}), 400
    return jsonify({**wynik, "strona": strona, "url": url_for("fiszki.widok_pdf", pdf_id=wynik["pdf_id"])}), 201


@przepisy_bp.route("/porownanie")
def porownanie_wersji():
    """Dwie wersje aktu obok siebie: co dodano, usunięto, zmieniono (ETAP 77)."""
    akty = baza.lista_aktow()
    a, b = request.args.get("stary", type=int), request.args.get("nowy", type=int)
    wynik = None
    if a and b:
        stary, nowy = _akt_albo_404(a), _akt_albo_404(b)
        wynik = {"stary": stary, "nowy": nowy, **porownanie.porownaj(baza.jednostki_aktu(a), baza.jednostki_aktu(b))}
    return render_template("przepisy/porownanie.html", akty=akty, wynik=wynik, stary_id=a, nowy_id=b,
                           tylko_zmiany=request.args.get("wszystkie") != "1")


# ---------- fiszki z artykułu (ETAP 82) ----------


def _jednostka_albo_404(jednostka_id: int) -> tuple[dict, dict]:
    j = baza.jednostka(jednostka_id)
    if j is None:
        abort(404)
    return j, _akt_albo_404(j["akt_id"])


@przepisy_bp.route("/jednostki/<int:jednostka_id>/szkice-fiszek", methods=["POST"])
def szkice_fiszek_z_jednostki(jednostka_id):
    """Propozycje fiszek z jednego artykułu — tylko z cytatem w tekście."""
    j, _ = _jednostka_albo_404(jednostka_id)
    try:
        propozycje = gemini.zaproponuj_fiszki_z_przepisu(j["tekst"][: pytania.MAKS_ZNAKOW_JEDNOSTKI], j["oznaczenie"])
    except gemini.BladGemini as e:
        return jsonify({"blad": str(e)}), 502
    dobre, odrzucone = pytania.sprawdz_propozycje_fiszek(propozycje, j)
    return jsonify({"propozycje": dobre, "odrzucone": odrzucone})


@przepisy_bp.route("/jednostki/<int:jednostka_id>/fiszki", methods=["POST"])
def fiszki_z_jednostki(jednostka_id):
    """Zapis wybranych fiszek z artykułu z kotwicą na stronie cytatu.
    Cytaty sprawdzamy jeszcze raz — przeglądarka mogła je zmienić."""
    j, akt = _jednostka_albo_404(jednostka_id)
    dane = request.get_json(silent=True) or {}
    wybrane = dane.get("fiszki")
    if not isinstance(wybrane, list) or not wybrane:
        return jsonify({"blad": "Zaznacz co najmniej jedną fiszkę."}), 400
    tekst = pytania.do_porownania(j["tekst"])
    sciezka = os.path.join(baza.folder_plikow(), akt["nazwa_pliku"])
    strony = teksty_stron(sciezka, j["strona_od"], j["strona_do"])
    # Najpierw sprawdzamy wszystkie — żadnego zapisu „do połowy”.
    do_zapisu = []
    for f in wybrane:
        if not isinstance(f, dict):
            return jsonify({"blad": "Zły format fiszki."}), 400
        fragment = " ".join(str(f.get("fragment") or "").split())
        pytanie, odpowiedz = str(f.get("pytanie") or "").strip(), str(f.get("odpowiedz") or "").strip()
        if not fragment or pytania.do_porownania(fragment) not in tekst:
            return jsonify({"blad": "Cytat fiszki nie pochodzi z tego artykułu."}), 400
        if not pytanie or not odpowiedz:
            return jsonify({"blad": "Każda fiszka musi mieć pytanie i odpowiedź."}), 400
        do_zapisu.append((pytania.strona_cytatu(strony, fragment, j["strona_od"]), fragment, pytanie, odpowiedz))
    pdf_id = None
    for strona, fragment, pytanie, odpowiedz in do_zapisu:
        try:
            wynik = fiszki_zewnetrzne.dodaj_fiszke(
                sciezka, f"{akt['nazwa'][:120]}.pdf", strona, fragment, pytanie, odpowiedz, dane.get("tematy"),
            )
        except fiszki_zewnetrzne.BladFiszki as e:  # np. za długi temat — sprawdzany przy pierwszej fiszce
            return jsonify({"blad": str(e)}), 400
        pdf_id = wynik["pdf_id"]
    return jsonify({"dodane": len(wybrane), "url": url_for("fiszki.widok_pdf", pdf_id=pdf_id)}), 201


# ---------- wyszukiwarka globalna (ETAP 128) ----------


def wyszukaj(fraza: str) -> list[dict]:
    """Jednostki aktów (wyszukiwarka pełnotekstowa modułu), najlepsze pierwsze."""
    return [
        {"tytul": f"{w['oznaczenie']} — {w['nazwa_aktu']}",
         "opis": w["podglad"].replace(baza.ZNACZNIK_OD, "").replace(baza.ZNACZNIK_DO, ""),
         "url": url_for("przepisy.widok_aktu", akt_id=w["akt_id"]) + f"#j{w['id']}"}
        for w in baza.szukaj(fraza)[:10]
    ]
