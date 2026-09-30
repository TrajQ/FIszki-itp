"""Fiszki na zewnątrz i z zewnątrz: druk, eksport CSV/Anki, wyszukiwarka
i import z pliku.

Trasy rejestrują się na wspólnym blueprincie `fiszki_bp` (import w
fiszki/routes.py na końcu pliku).
"""

import csv
import html
import io
import os
from datetime import datetime

from flask import Response, jsonify, render_template, request
from werkzeug.utils import secure_filename

from . import importer, tematy
from .baza import get_db
from .routes import _fiszki_do_eksportu, _pobierz_pdf_albo_404, _temat_z_zapytania, fiszki_bp


# ---------- Fiszki do druku (ETAP 31) ----------


@fiszki_bp.route("/druk")
def druk():
    """Karty do wycięcia i złożenia na pół (pytanie | odpowiedź)."""
    pdf_id = request.args.get("pdf_id", type=int)
    pdf = _pobierz_pdf_albo_404(pdf_id) if pdf_id is not None else None
    temat = _temat_z_zapytania()
    fiszki = _fiszki_do_eksportu(pdf_id, temat)
    return render_template("fiszki/druk.html", pdf=pdf, fiszki=fiszki, temat=temat)


def _nazwa_pliku_eksportu(pdf, rozszerzenie):
    if pdf is None:
        return f"fiszki_wszystkie.{rozszerzenie}"
    nazwa_bez_pdf = os.path.splitext(secure_filename(pdf["nazwa_oryginalna"]))[0]
    return f"fiszki_{nazwa_bez_pdf or pdf['id']}.{rozszerzenie}"


def _odpowiedz_csv(fiszki, pdf):
    """CSV do arkusza. Przy eksporcie wszystkiego dochodzi kolumna „plik”."""
    bufor = io.StringIO()
    zapis = csv.writer(bufor)
    kolumny = ["strona", "pytanie", "odpowiedz", "fragment_tekstu", "data_utworzenia"]
    if pdf is None:
        kolumny = ["plik"] + kolumny
    zapis.writerow(kolumny)
    for f in fiszki:
        zapis.writerow([f["nazwa_oryginalna"] if k == "plik" else f[k] for k in kolumny])

    # utf-8-sig (z BOM), żeby LibreOffice/Excel poprawnie pokazały polskie znaki.
    return Response(
        bufor.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={_nazwa_pliku_eksportu(pdf, 'csv')}"
        },
    )


def _pole_anki(tekst):
    # Anki czyta pola jako HTML (nagłówek #html:true), więc escapujemy znaki
    # specjalne, a nowe linie zamieniamy na <br>. Tabulator rozdziela pola,
    # dlatego w treści zamieniamy go na spację.
    tekst = html.escape(tekst).replace("\t", " ")
    return tekst.replace("\r\n", "\n").replace("\n", "<br>")


def _tag_anki(temat: str) -> str:
    # Tagi w Anki rozdziela spacja, więc spacje w nazwie tematu → „_”.
    return "_".join(temat.split())


def _odpowiedz_anki(fiszki, pdf, temat=None):
    """Plik tekstowy rozdzielany tabulatorami — Anki importuje go przez
    Plik → Importuj. Kolumny: pytanie, odpowiedź, źródło (plik i strona),
    tagi. Tematy fiszek (ETAP 95) trafiają do Anki jako tagi — nagłówek
    „#tags column” wg podręcznika Anki (pliki tekstowe, Anki 2.1.54+)."""
    tagi = tematy.tematy_fiszek(get_db())  # {fiszka_id: [tematy]}
    wiersze = ["#separator:tab", "#html:true", "#tags column:4"]
    for f in fiszki:
        zrodlo = f"{f['nazwa_oryginalna']}, s. {f['strona']}" if f["strona"] else f["nazwa_oryginalna"]
        wiersze.append(
            "\t".join(
                [*(_pole_anki(t) for t in (f["pytanie"], f["odpowiedz"], zrodlo)),
                 " ".join(_tag_anki(t) for t in tagi.get(f["id"], []))]
            )
        )
    nazwa = _nazwa_pliku_eksportu(pdf, "txt") if temat is None else f"fiszki_{secure_filename(_tag_anki(temat)) or 'temat'}.txt"
    return Response(
        "\n".join(wiersze) + "\n",
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )


@fiszki_bp.route("/<int:pdf_id>/eksport.csv")
def eksport_csv(pdf_id):
    pdf = _pobierz_pdf_albo_404(pdf_id)
    return _odpowiedz_csv(_fiszki_do_eksportu(pdf_id), pdf)


@fiszki_bp.route("/<int:pdf_id>/eksport.txt")
def eksport_anki(pdf_id):
    pdf = _pobierz_pdf_albo_404(pdf_id)
    return _odpowiedz_anki(_fiszki_do_eksportu(pdf_id), pdf)


@fiszki_bp.route("/eksport.csv")
def eksport_csv_wszystkie():
    return _odpowiedz_csv(_fiszki_do_eksportu(), None)


@fiszki_bp.route("/eksport.txt")
def eksport_anki_wszystkie():
    """Wszystkie fiszki albo (?temat=) tylko jeden temat (ETAP 95)."""
    temat = _temat_z_zapytania()
    return _odpowiedz_anki(_fiszki_do_eksportu(temat=temat), None, temat)


# ---------- Wyszukiwarka i usuwanie PDF-a (ETAP 11) ----------

MAKS_WYNIKOW_SZUKANIA = 50


@fiszki_bp.route("/szukaj")
def szukaj():
    """Fiszki, których pytanie, odpowiedź albo fragment zawiera frazę.

    Porównanie bez rozróżniania wielkości liter także dla polskich znaków
    (SQLite LOWER() obsługuje tylko ASCII, więc filtrujemy w Pythonie —
    przy setkach czy tysiącach fiszek to bez znaczenia dla szybkości).
    """
    fraza = (request.args.get("q") or "").strip().casefold()
    if len(fraza) < 2:
        return jsonify({"blad": "Wpisz co najmniej 2 znaki."}), 400

    wyniki = []
    for f in _fiszki_do_eksportu():
        tekst = " ".join((f["pytanie"], f["odpowiedz"], f["fragment_tekstu"])).casefold()
        if fraza in tekst:
            wyniki.append(dict(f))
            if len(wyniki) >= MAKS_WYNIKOW_SZUKANIA:
                break
    return jsonify(wyniki)


# ---------- Import fiszek (ETAP 54) ----------


@fiszki_bp.route("/<int:pdf_id>/import", methods=["POST"])
def importuj(pdf_id):
    """Fiszki z pliku (Anki, Quizlet, CSV) do tego PDF-a; duplikaty pomijamy."""
    _pobierz_pdf_albo_404(pdf_id)
    plik = request.files.get("plik")
    if plik is None or not plik.filename:
        return jsonify({"blad": "Nie wybrano pliku."}), 400
    zawartosc = plik.read(importer.MAKS_ROZMIAR_B + 1)
    if len(zawartosc) > importer.MAKS_ROZMIAR_B:
        return jsonify({"blad": "Plik jest za duży (limit 1 MB)."}), 400
    try:
        tekst = zawartosc.decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"blad": "Plik musi być zapisany w UTF-8."}), 400
    try:
        nowe, bledne = importer.wczytaj(tekst)
        lista_tematow = tematy.normalizuj(request.form.get("tematy"))
    except (importer.BladImportu, tematy.BladTematow) as e:
        return jsonify({"blad": str(e)}), 400

    db = get_db()
    istniejace = {
        (w["pytanie"], w["odpowiedz"])
        for w in db.execute("SELECT pytanie, odpowiedz FROM fiszki WHERE pdf_id = ?", (pdf_id,))
    }
    dodane = duplikaty = 0
    teraz = datetime.now().isoformat()
    for f in nowe:
        klucz = (f["pytanie"], f["odpowiedz"])
        if klucz in istniejace:
            duplikaty += 1
            continue
        istniejace.add(klucz)
        kursor = db.execute(
            """INSERT INTO fiszki (pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, data_utworzenia)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (pdf_id, f["strona"], f["fragment_tekstu"], f["pytanie"], f["odpowiedz"], teraz),
        )
        tematy.ustaw(db, kursor.lastrowid, lista_tematow)
        dodane += 1
    db.commit()
    return jsonify({"dodane": dodane, "duplikaty": duplikaty, "bledne": bledne[:20], "liczba_blednych": len(bledne)})
