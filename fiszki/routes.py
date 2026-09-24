import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
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
    pdfy = db.execute("SELECT * FROM pdfy ORDER BY data_dodania DESC").fetchall()
    return render_template("fiszki/index.html", pdfy=pdfy)


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
