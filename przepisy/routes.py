"""Moduł przepisy: biblioteka aktów prawnych (PDF) i wyszukiwarka (ETAP 61)."""

import os
import uuid

from flask import Blueprint, abort, jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from dane import gemini

from . import baza, pytania
from .tekst import BladPdf, podziel, strony_z_pdf

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
    sciezka = os.path.join(baza.folder_plikow(), nazwa_na_dysku)
    plik.save(sciezka)
    try:
        strony = strony_z_pdf(sciezka)
    except BladPdf as e:
        os.remove(sciezka)
        return redirect(url_for("przepisy.index", blad=str(e)))
    jednostki = podziel(strony)
    akt_id = baza.dodaj_akt(nazwa_z_tytulu(jednostki, plik.filename), nazwa_na_dysku, len(strony), jednostki)
    return redirect(url_for("przepisy.widok_aktu", akt_id=akt_id))


@przepisy_bp.route("/akty/<int:akt_id>")
def widok_aktu(akt_id):
    akt = _akt_albo_404(akt_id)
    return render_template("przepisy/akt.html", akt=akt, jednostki=baza.jednostki_aktu(akt_id))


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
