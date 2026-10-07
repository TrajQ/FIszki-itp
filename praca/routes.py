"""Moduł Praca i notatki (ETAP 230): godziny pracy z grafiku.

Strona przyjmuje PDF grafiku albo zdjęcie/zrzut ekranu. Z PDF-u z warstwą
tekstu tekst czyta pypdf; zdjęcie (i PDF-skan) przepisuje Gemini. Tekst
trafia do pola na stronie — użytkownik może go poprawić — i dopiero z
niego kod liczy godziny i kwotę (praca/grafik.py).
"""

import io
import os
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, render_template, request

from dane.gemini import BladGemini, przepisz_grafik

from . import grafik

praca_bp = Blueprint("praca", __name__, template_folder="templates", static_folder="static")

TYPY_PO_ROZSZERZENIU = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                        ".webp": "image/webp", ".heic": "image/heic", ".heif": "image/heif"}
MAKS_PLIK_B = 20 * 1024 * 1024


@praca_bp.route("/")
def index():
    return render_template("praca/index.html", miesiace=grafik.MIESIACE, stawka=str(grafik.STAWKA_DOMYSLNA).replace(".", ","))


def tekst_pdf(dane: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        return "\n".join(strona.extract_text() or "" for strona in PdfReader(io.BytesIO(dane)).pages)
    except (PdfReadError, ValueError) as e:
        raise grafik.BladGrafiku("Nie udało się odczytać PDF-u.") from e


@praca_bp.route("/grafik/odczytaj", methods=["POST"])
def odczytaj_grafik():
    """Plik → tekst grafiku do pola na stronie (bez liczenia)."""
    plik = request.files.get("plik")
    if plik is None or not plik.filename:
        return jsonify({"blad": "Wybierz PDF albo zdjęcie grafiku."}), 400
    typ = TYPY_PO_ROZSZERZENIU.get(os.path.splitext(plik.filename.lower())[1])
    if typ is None:
        return jsonify({"blad": "Obsługiwane pliki: PDF, JPG, PNG, WebP, HEIC."}), 400
    dane = plik.read(MAKS_PLIK_B + 1)
    if len(dane) > MAKS_PLIK_B:
        return jsonify({"blad": "Plik jest za duży (limit 20 MB)."}), 400
    try:
        if typ == "application/pdf":
            tekst = tekst_pdf(dane)
            if grafik.odczytaj_zmiany(tekst):
                return jsonify({"tekst": tekst, "zrodlo": "pdf"})
            # PDF bez warstwy tekstu (skan, zrzut) — przepisuje Gemini
        return jsonify({"tekst": przepisz_grafik(dane, typ), "zrodlo": "gemini"})
    except grafik.BladGrafiku as e:
        return jsonify({"blad": str(e)}), 400
    except BladGemini as e:
        return jsonify({"blad": str(e)}), 502


@praca_bp.route("/grafik/policz", methods=["POST"])
def policz_grafik():
    dane = request.get_json(silent=True) or {}
    try:
        stawka = Decimal(str(dane.get("stawka") or grafik.STAWKA_DOMYSLNA).replace(",", ".").replace(" ", ""))
        miesiac = int(dane["miesiac"]) if dane.get("miesiac") else None
        rok = int(dane["rok"]) if dane.get("rok") else None
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"blad": "Stawka, miesiąc i rok muszą być liczbami."}), 400
    if not stawka.is_finite() or stawka > 10_000:
        return jsonify({"blad": "Niepoprawna stawka."}), 400
    try:
        return jsonify(grafik.rozliczenie(str(dane.get("tekst") or ""), str(dane.get("imie") or ""), stawka, miesiac, rok))
    except grafik.BladGrafiku as e:
        return jsonify({"blad": str(e)}), 400
