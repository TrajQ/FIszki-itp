import csv
import html
import io
import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from dane.gemini import BladGemini, zaproponuj_fiszke

from . import powtorki
from .baza import folder_plikow, get_db

fiszki_bp = Blueprint(
    "fiszki",
    __name__,
    template_folder="templates",
    static_folder="static",
)


def _pobierz_pdf_albo_404(pdf_id):
    db = get_db()
    pdf = db.execute("SELECT * FROM pdfy WHERE id = ?", (pdf_id,)).fetchone()
    if pdf is None:
        abort(404)
    return pdf


@fiszki_bp.route("/")
def index():
    db = get_db()
    dzis = powtorki.dzisiaj().isoformat()
    pdfy = db.execute(
        f"""SELECT pdfy.*,
                  COUNT(fiszki.id) AS liczba_fiszek,
                  COALESCE(SUM({_WARUNEK_DO_POWTORKI}), 0) AS do_powtorki
           FROM pdfy
           LEFT JOIN fiszki ON fiszki.pdf_id = pdfy.id
           LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id
           GROUP BY pdfy.id ORDER BY pdfy.data_dodania DESC""",
        {"dzis": dzis},
    ).fetchall()
    return render_template(
        "fiszki/index.html",
        pdfy=pdfy,
        do_powtorki=sum(p["do_powtorki"] for p in pdfy),
        pudelka=_liczby_w_pudelkach(),
    )


# Fiszka jest do powtórki, gdy nie ma jeszcze stanu (nowa) albo termin minął.
# Używane w SQL z parametrem :dzis (data ISO — porównanie tekstowe działa).
_WARUNEK_DO_POWTORKI = (
    "fiszki.id IS NOT NULL AND "
    "(powtorki.fiszka_id IS NULL OR powtorki.nastepna_powtorka <= :dzis)"
)


def _liczby_w_pudelkach() -> list[int]:
    """Ile fiszek jest w każdym pudełku (indeks 0 = pudełko 1)."""
    db = get_db()
    wiersze = db.execute(
        """SELECT COALESCE(powtorki.pudelko, 1) AS pudelko, COUNT(*) AS ile
           FROM fiszki LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id
           GROUP BY 1"""
    ).fetchall()
    liczby = [0] * powtorki.PUDELKO_MAX
    for w in wiersze:
        liczby[w["pudelko"] - 1] = w["ile"]
    return liczby


@fiszki_bp.route("/upload", methods=["POST"])
def upload():
    plik = request.files.get("plik")
    if plik is None or plik.filename == "":
        abort(400, "Nie wybrano pliku.")

    if not plik.filename.lower().endswith(".pdf"):
        abort(400, "Dozwolone są tylko pliki PDF.")

    naglowek = plik.read(5)
    plik.seek(0)
    if naglowek != b"%PDF-":
        abort(400, "Plik nie jest prawidłowym PDF-em.")

    nazwa_bezpieczna = secure_filename(plik.filename)
    nazwa_na_dysku = f"{uuid.uuid4().hex}_{nazwa_bezpieczna}"
    plik.save(os.path.join(folder_plikow(), nazwa_na_dysku))

    db = get_db()
    cursor = db.execute(
        "INSERT INTO pdfy (nazwa_oryginalna, nazwa_pliku, data_dodania) VALUES (?, ?, ?)",
        (plik.filename, nazwa_na_dysku, datetime.now().isoformat()),
    )
    db.commit()

    return redirect(url_for("fiszki.widok_pdf", pdf_id=cursor.lastrowid))


@fiszki_bp.route("/<int:pdf_id>/")
def widok_pdf(pdf_id):
    pdf = _pobierz_pdf_albo_404(pdf_id)
    return render_template("fiszki/pdf.html", pdf=pdf)


@fiszki_bp.route("/<int:pdf_id>/plik")
def plik_pdf(pdf_id):
    pdf = _pobierz_pdf_albo_404(pdf_id)
    return send_from_directory(
        folder_plikow(), pdf["nazwa_pliku"], mimetype="application/pdf"
    )


@fiszki_bp.route("/<int:pdf_id>/fiszki")
def lista_fiszek(pdf_id):
    _pobierz_pdf_albo_404(pdf_id)
    db = get_db()
    fiszki = db.execute(
        "SELECT * FROM fiszki WHERE pdf_id = ? ORDER BY strona, id", (pdf_id,)
    ).fetchall()
    return jsonify([dict(f) for f in fiszki])


@fiszki_bp.route("/<int:pdf_id>/szkic", methods=["POST"])
def szkic_fiszki(pdf_id):
    _pobierz_pdf_albo_404(pdf_id)
    dane = request.get_json(silent=True) or {}
    fragment = (dane.get("fragment") or "").strip()
    if not fragment:
        return jsonify({"blad": "Brak zaznaczonego fragmentu."}), 400

    try:
        szkic = zaproponuj_fiszke(fragment)
    except BladGemini as e:
        return jsonify({"blad": str(e)}), 502

    return jsonify(szkic)


@fiszki_bp.route("/<int:pdf_id>/fiszki", methods=["POST"])
def zapisz_fiszke(pdf_id):
    _pobierz_pdf_albo_404(pdf_id)
    dane = request.get_json(silent=True) or {}

    strona = dane.get("strona")
    fragment_tekstu = (dane.get("fragment_tekstu") or "").strip()
    pytanie = (dane.get("pytanie") or "").strip()
    odpowiedz = (dane.get("odpowiedz") or "").strip()

    if not isinstance(strona, int) or not fragment_tekstu or not pytanie or not odpowiedz:
        abort(400, "Brak wymaganych pól fiszki.")

    db = get_db()
    cursor = db.execute(
        """INSERT INTO fiszki (pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, data_utworzenia)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, datetime.now().isoformat()),
    )
    db.commit()

    nowa = db.execute("SELECT * FROM fiszki WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(dict(nowa)), 201


@fiszki_bp.route("/<int:pdf_id>/fiszki/<int:fiszka_id>", methods=["DELETE"])
def usun_fiszke(pdf_id, fiszka_id):
    _pobierz_pdf_albo_404(pdf_id)
    db = get_db()
    db.execute("DELETE FROM fiszki WHERE id = ? AND pdf_id = ?", (fiszka_id, pdf_id))
    db.commit()
    return "", 204


@fiszki_bp.route("/<int:pdf_id>/fiszki/<int:fiszka_id>", methods=["PUT"])
def edytuj_fiszke(pdf_id, fiszka_id):
    _pobierz_pdf_albo_404(pdf_id)
    dane = request.get_json(silent=True) or {}
    pytanie = (dane.get("pytanie") or "").strip()
    odpowiedz = (dane.get("odpowiedz") or "").strip()

    # Edytowalne są tylko pytanie i odpowiedź — strona i fragment to kotwica
    # w źródle, więc zmiana ich oderwałaby fiszkę od PDF-a.
    if not pytanie or not odpowiedz:
        abort(400, "Pytanie i odpowiedź nie mogą być puste.")

    db = get_db()
    cursor = db.execute(
        "UPDATE fiszki SET pytanie = ?, odpowiedz = ? WHERE id = ? AND pdf_id = ?",
        (pytanie, odpowiedz, fiszka_id, pdf_id),
    )
    db.commit()
    if cursor.rowcount == 0:
        abort(404)

    zmieniona = db.execute("SELECT * FROM fiszki WHERE id = ?", (fiszka_id,)).fetchone()
    return jsonify(dict(zmieniona))


def _fiszki_do_eksportu(pdf_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM fiszki WHERE pdf_id = ? ORDER BY strona, id", (pdf_id,)
    ).fetchall()


def _nazwa_pliku_eksportu(pdf, rozszerzenie):
    nazwa_bez_pdf = os.path.splitext(secure_filename(pdf["nazwa_oryginalna"]))[0]
    return f"fiszki_{nazwa_bez_pdf or pdf['id']}.{rozszerzenie}"


@fiszki_bp.route("/<int:pdf_id>/eksport.csv")
def eksport_csv(pdf_id):
    pdf = _pobierz_pdf_albo_404(pdf_id)
    bufor = io.StringIO()
    zapis = csv.writer(bufor)
    zapis.writerow(["strona", "pytanie", "odpowiedz", "fragment_tekstu", "data_utworzenia"])
    for f in _fiszki_do_eksportu(pdf_id):
        zapis.writerow(
            [f["strona"], f["pytanie"], f["odpowiedz"], f["fragment_tekstu"], f["data_utworzenia"]]
        )

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


@fiszki_bp.route("/<int:pdf_id>/eksport.txt")
def eksport_anki(pdf_id):
    """Plik tekstowy rozdzielany tabulatorami — Anki importuje go przez
    Plik → Importuj. Kolumny: pytanie, odpowiedź, źródło (plik i strona)."""
    pdf = _pobierz_pdf_albo_404(pdf_id)
    wiersze = ["#separator:tab", "#html:true"]
    for f in _fiszki_do_eksportu(pdf_id):
        zrodlo = f"{pdf['nazwa_oryginalna']}, s. {f['strona']}"
        wiersze.append(
            "\t".join(_pole_anki(t) for t in (f["pytanie"], f["odpowiedz"], zrodlo))
        )

    return Response(
        "\n".join(wiersze) + "\n",
        mimetype="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={_nazwa_pliku_eksportu(pdf, 'txt')}"
        },
    )


# ---------- Powtórki (ETAP 6, system Leitnera — zob. powtorki.py) ----------


@fiszki_bp.route("/powtorka")
def powtorka():
    pdf_id = request.args.get("pdf_id", type=int)
    pdf = _pobierz_pdf_albo_404(pdf_id) if pdf_id is not None else None
    return render_template("fiszki/powtorka.html", pdf=pdf)


@fiszki_bp.route("/powtorka/kolejka")
def kolejka_powtorki():
    """Fiszki do powtórki dziś: najpierw z niższych pudełek (słabiej znane)."""
    pdf_id = request.args.get("pdf_id", type=int)
    parametry = {"dzis": powtorki.dzisiaj().isoformat()}
    filtr_pdf = ""
    if pdf_id is not None:
        filtr_pdf = "AND fiszki.pdf_id = :pdf_id"
        parametry["pdf_id"] = pdf_id

    db = get_db()
    wiersze = db.execute(
        f"""SELECT fiszki.*, pdfy.nazwa_oryginalna,
                   COALESCE(powtorki.pudelko, 1) AS pudelko
            FROM fiszki
            JOIN pdfy ON pdfy.id = fiszki.pdf_id
            LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id
            WHERE {_WARUNEK_DO_POWTORKI} {filtr_pdf}
            ORDER BY pudelko, fiszki.id""",
        parametry,
    ).fetchall()
    return jsonify([dict(w) for w in wiersze])


@fiszki_bp.route("/powtorka/<int:fiszka_id>", methods=["POST"])
def zapisz_powtorke(fiszka_id):
    dane = request.get_json(silent=True) or {}
    wynik = dane.get("wynik")
    if wynik not in powtorki.WYNIKI:
        return jsonify({"blad": "Wynik musi być 'umiem' albo 'nie_umiem'."}), 400

    db = get_db()
    if db.execute("SELECT 1 FROM fiszki WHERE id = ?", (fiszka_id,)).fetchone() is None:
        abort(404)

    stan = db.execute(
        "SELECT pudelko FROM powtorki WHERE fiszka_id = ?", (fiszka_id,)
    ).fetchone()
    pudelko = stan["pudelko"] if stan else powtorki.PUDELKO_MIN

    dzis = powtorki.dzisiaj()
    nowe_pudelko, nastepna = powtorki.nastepny_stan(pudelko, wynik, dzis)

    db.execute(
        """INSERT INTO powtorki (fiszka_id, pudelko, nastepna_powtorka, liczba_powtorek, ostatnia_powtorka)
           VALUES (?, ?, ?, 1, ?)
           ON CONFLICT(fiszka_id) DO UPDATE SET
               pudelko = excluded.pudelko,
               nastepna_powtorka = excluded.nastepna_powtorka,
               liczba_powtorek = powtorki.liczba_powtorek + 1,
               ostatnia_powtorka = excluded.ostatnia_powtorka""",
        (fiszka_id, nowe_pudelko, nastepna.isoformat(), dzis.isoformat()),
    )
    db.commit()

    return jsonify(
        {"fiszka_id": fiszka_id, "pudelko": nowe_pudelko, "nastepna_powtorka": nastepna.isoformat()}
    )
