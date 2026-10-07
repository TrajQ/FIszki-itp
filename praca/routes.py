"""Moduł Praca i notatki: godziny pracy z grafiku (ETAP 230) i notatki
w Wordzie z PDF-u albo zdjęć (ETAP 231).

Grafik: strona przyjmuje PDF albo zdjęcie/zrzut ekranu. Z PDF-u z warstwą
tekstu tekst czyta pypdf; zdjęcie (i PDF-skan) przepisuje Gemini. Tekst
trafia do pola na stronie — użytkownik może go poprawić — i dopiero z
niego kod liczy godziny i kwotę (praca/grafik.py).
"""

import io
import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, render_template, request

from dane.gemini import DLUGOSCI_NOTATEK, BladGemini, przepisz_grafik, utworz_notatki

from . import baza, grafik, notatki, word

praca_bp = Blueprint("praca", __name__, template_folder="templates", static_folder="static")

TYPY_PO_ROZSZERZENIU = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                        ".webp": "image/webp", ".heic": "image/heic", ".heif": "image/heif"}
MAKS_PLIK_B = 20 * 1024 * 1024
MAKS_PLIKOW_NOTATEK = 10
MIN_ZNAKOW_TEKSTU_PDF = 200  # mniej — PDF to najpewniej skan; wtedy Gemini czyta obraz strony
MIN_ZNAKOW_WKLEJONYCH = 50


@praca_bp.route("/")
def index():
    # ETAP 247: ?przyklad=1 z samouczka — gotowy tekst grafiku do policzenia
    przyklad = None
    if request.args.get("przyklad"):
        import samouczek

        przyklad = {"tekst": samouczek.GRAFIK, "imie": samouczek.IMIE_W_GRAFIKU}
    return render_template("praca/index.html", miesiace=grafik.MIESIACE, stawka=str(grafik.STAWKA_DOMYSLNA).replace(".", ","),
                           historia=historia(), przyklad=przyklad)


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


def _policz_z_zapytania() -> tuple[dict, Decimal]:
    """Wspólne dla „Policz” i „Zapisz miesiąc”: wynik liczy zawsze serwer z
    tekstu grafiku — także przy zapisie nie przyjmujemy liczb od strony."""
    dane = request.get_json(silent=True) or {}
    try:
        stawka = Decimal(str(dane.get("stawka") or grafik.STAWKA_DOMYSLNA).replace(",", ".").replace(" ", ""))
        miesiac = int(dane["miesiac"]) if dane.get("miesiac") else None
        rok = int(dane["rok"]) if dane.get("rok") else None
    except (InvalidOperation, ValueError, TypeError):
        raise grafik.BladGrafiku("Stawka, miesiąc i rok muszą być liczbami.") from None
    if not stawka.is_finite() or stawka > 10_000:
        raise grafik.BladGrafiku("Niepoprawna stawka.")
    pominiete = dane.get("pominiete") if isinstance(dane.get("pominiete"), list) else []
    wynik = grafik.rozliczenie(str(dane.get("tekst") or ""), str(dane.get("imie") or ""), stawka, miesiac, rok,
                               {str(k) for k in pominiete[:200]})
    return wynik, stawka


@praca_bp.route("/grafik/policz", methods=["POST"])
def policz_grafik():
    try:
        return jsonify(_policz_z_zapytania()[0])
    except grafik.BladGrafiku as e:
        return jsonify({"blad": str(e)}), 400


# ---------- historia rozliczeń (ETAP 232) ----------


def historia() -> dict:
    """Zapisane miesiące od najnowszego i sumy w latach (z dokładnych kwot)."""
    wiersze = baza.rozliczenia()
    lata: dict[int, dict] = {}
    for w in wiersze:
        rok = lata.setdefault(w["rok"], {"rok": w["rok"], "minuty": 0, "kwota": Decimal(0), "miesiecy": 0})
        rok["minuty"] += w["minuty"]
        rok["kwota"] += Decimal(w["kwota"])
        rok["miesiecy"] += 1
    return {
        "miesiace": [{**w, "nazwa": f"{grafik.MIESIACE[w['miesiac'] - 1]} {w['rok']}", "godziny": grafik.godziny_tekst(w["minuty"]),
                      "kwota_tekst": grafik.kwota_tekst(Decimal(w["kwota"]))} for w in wiersze],
        "lata": [{**r, "godziny": grafik.godziny_tekst(r["minuty"]), "kwota": grafik.kwota_tekst(r["kwota"])}
                 for r in sorted(lata.values(), key=lambda r: -r["rok"])],
    }


@praca_bp.route("/rozliczenia", methods=["POST"])
def zapisz_rozliczenie():
    try:
        wynik, stawka = _policz_z_zapytania()
    except grafik.BladGrafiku as e:
        return jsonify({"blad": str(e)}), 400
    imie = " ".join(str((request.get_json(silent=True) or {}).get("imie") or "").split())[:40]
    baza.zapisz(wynik["rok"], wynik["miesiac"], imie, wynik["minuty"], stawka, Decimal(wynik["kwota_dokladna"]),
                wynik["wliczonych"], wynik["tekst"])
    return jsonify(historia())


@praca_bp.route("/rozliczenia")
def lista_rozliczen():
    return jsonify(historia())


@praca_bp.route("/rozliczenia/<int:rozliczenie_id>", methods=["DELETE"])
def usun_rozliczenie(rozliczenie_id):
    if not baza.usun(rozliczenie_id):
        return jsonify({"blad": "Nie ma takiego rozliczenia."}), 404
    return jsonify(historia())


def podsumowanie() -> dict:
    """Na kartę modułu na stronie głównej: ostatni zapisany miesiąc."""
    h = historia()
    return {"ostatni": h["miesiace"][0] if h["miesiace"] else None}


# ---------- notatki w Wordzie (ETAP 231) ----------


@praca_bp.route("/notatki/utworz", methods=["POST"])
def utworz_notatke():
    """PDF albo zdjęcia (do 10) → notatka jako JSON do podglądu na stronie.
    PDF z tekstem idzie do Gemini jako tekst (i liczby w notatce sprawdzamy
    z tym tekstem); zdjęcia i skany — jako obrazy."""
    pliki = [p for p in request.files.getlist("pliki") if p and p.filename]
    wklejony = (request.form.get("tekst") or "").strip()  # ETAP 233: tekst wklejony zamiast (albo obok) plików
    dlugosc = request.form.get("dlugosc") or "standard"
    if dlugosc not in DLUGOSCI_NOTATEK:
        return jsonify({"blad": "Nieznana długość notatek."}), 400
    if not pliki and len(wklejony) < MIN_ZNAKOW_WKLEJONYCH:
        return jsonify({"blad": "Wybierz PDF albo zdjęcia notatek, albo wklej tekst (co najmniej kilka zdań)."}), 400
    if len(pliki) > MAKS_PLIKOW_NOTATEK:
        return jsonify({"blad": f"Najwyżej {MAKS_PLIKOW_NOTATEK} plików naraz."}), 400
    teksty, obrazy, nazwy = [], [], []
    for plik in pliki:
        typ = TYPY_PO_ROZSZERZENIU.get(os.path.splitext(plik.filename.lower())[1])
        if typ is None:
            return jsonify({"blad": f"„{plik.filename}”: obsługiwane pliki to PDF, JPG, PNG, WebP, HEIC."}), 400
        dane = plik.read(MAKS_PLIK_B + 1)
        if len(dane) > MAKS_PLIK_B:
            return jsonify({"blad": f"„{plik.filename}” jest za duży (limit 20 MB)."}), 400
        nazwy.append(plik.filename)
        if typ == "application/pdf":
            try:
                tekst = tekst_pdf(dane)
            except grafik.BladGrafiku as e:
                return jsonify({"blad": f"„{plik.filename}”: {e}"}), 400
            if len(tekst.strip()) >= MIN_ZNAKOW_TEKSTU_PDF:
                teksty.append(tekst)
                continue
        obrazy.append((dane, typ))
    if wklejony:
        teksty.append(wklejony)
        nazwy.append("wklejony tekst")
    material = "\n\n".join(teksty)
    obciete = len(material) > notatki.MAKS_ZNAKOW_MATERIALU
    material = material[: notatki.MAKS_ZNAKOW_MATERIALU]
    try:
        n = notatki.oczysc(utworz_notatki(material or None, obrazy, dlugosc))
    except BladGemini as e:
        return jsonify({"blad": str(e)}), 502
    except notatki.BladNotatek as e:
        return jsonify({"blad": str(e)}), 422
    return jsonify({
        "notatki": n,
        "zrodlo": ", ".join(nazwy),
        # liczby da się sprawdzić tylko z tekstem; przy samych zdjęciach — None
        "liczby_do_sprawdzenia": notatki.liczby_spoza_materialu(n, material) if material and not obrazy else None,
        "obciete": obciete,
    })


def _nazwa_pliku(tytul: str) -> str:
    nazwa = re.sub(r"[^\w\- ]+", "", tytul, flags=re.UNICODE).strip().replace(" ", "_")[:60]
    return nazwa or "notatki"


@praca_bp.route("/notatki.docx", methods=["POST"])
def notatki_word():
    """Notatka (ta z podglądu, JSON) → plik Word. Treść sprawdzana jeszcze raz."""
    dane = request.get_json(silent=True) or {}
    try:
        n = notatki.oczysc(dane.get("notatki"))
    except notatki.BladNotatek as e:
        return jsonify({"blad": str(e)}), 400
    zrodlo = " ".join(str(dane.get("zrodlo") or "").split())[:300]
    stopka = (f"Źródło: {zrodlo} · " if zrodlo else "") + f"notatki ułożone przez Gemini z materiału — sprawdź z oryginałem · Warsztat, {date.today():%d.%m.%Y}"
    nazwa = _nazwa_pliku(n["tytul"])
    return Response(
        word.notatki_docx(n, stopka),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nazwa)}.docx"},
    )


@praca_bp.route("/notatki/fiszki.csv", methods=["POST"])
def notatki_fiszki():
    """ETAP 233: pytania kontrolne i pojęcia z notatki jako CSV do importu w Fiszkach."""
    dane = request.get_json(silent=True) or {}
    try:
        n = notatki.oczysc(dane.get("notatki"))
    except notatki.BladNotatek as e:
        return jsonify({"blad": str(e)}), 400
    if not n["pytania"] and not n["pojecia"]:
        return jsonify({"blad": "W notatkach nie ma pytań ani pojęć."}), 400
    return Response(
        "\ufeff" + notatki.fiszki_csv(n),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(_nazwa_pliku(n['tytul']))}_fiszki.csv"},
    )
