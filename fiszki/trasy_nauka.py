"""Nauka z fiszek: powtórki Leitnera, quiz ABCD, statystyki i egzaminy.

Trasy rejestrują się na wspólnym blueprincie `fiszki_bp` (import w
fiszki/routes.py na końcu pliku). Pomocnicze funkcje z podkreśleniem
(_pobierz_pdf_albo_404, _temat_z_zapytania…) są wspólne dla modułu.
"""

import random

from flask import abort, jsonify, redirect, render_template, request, url_for

from . import egzaminy, obrazy, powtorki, quiz as quiz_fiszek, statystyki_nauki
from .baza import get_db
from .routes import (
    _WARUNEK_DO_POWTORKI,
    _WARUNEK_TEMATU,
    _fiszki_do_eksportu,
    _pobierz_pdf_albo_404,
    _temat_z_zapytania,
    fiszki_bp,
    url_obrazu,
)


# ---------- Quiz ABCD (ETAP 26) ----------

DOMYSLNA_LICZBA_PYTAN = 10


@fiszki_bp.route("/quiz")
def quiz():
    pdf_id = request.args.get("pdf_id", type=int)
    pdf = _pobierz_pdf_albo_404(pdf_id) if pdf_id is not None else None
    return render_template("fiszki/quiz.html", pdf=pdf, temat=_temat_z_zapytania())


@fiszki_bp.route("/quiz/pytania")
def quiz_pytania():
    """Pytania quizu: z jednego PDF-a (pdf_id) albo ze wszystkich.
    `ziarno` — powtarzalne losowanie (testy)."""
    pdf_id = request.args.get("pdf_id", type=int)
    liczba = max(1, min(request.args.get("liczba", DOMYSLNA_LICZBA_PYTAN, type=int), 50))
    ziarno = request.args.get("ziarno", type=int)

    db = get_db()
    # Dystraktory bierzemy ze wszystkich fiszek, pytania — z wybranego zakresu.
    wszystkie = [dict(w) for w in db.execute("SELECT * FROM fiszki ORDER BY id").fetchall()]
    temat = _temat_z_zapytania()
    z_tematem = {f["id"] for f in _fiszki_do_eksportu(None, temat)} if temat else None
    zakres = [
        f for f in wszystkie if (pdf_id is None or f["pdf_id"] == pdf_id) and (z_tematem is None or f["id"] in z_tematem)
    ]
    if not zakres:
        return jsonify({"blad": "Brak fiszek w tym zakresie."}), 404

    try:
        pytania = quiz_fiszek.uloz_quiz(zakres, wszystkie, liczba, random.Random(ziarno))
    except quiz_fiszek.ZaMaloFiszek as e:
        return jsonify({"blad": str(e)}), 400
    obrazki = obrazy.obrazy_fiszek(db)  # ETAP 154
    return jsonify([{**p, "obraz": url_obrazu(obrazki.get(p["fiszka_id"]))} for p in pytania])


@fiszki_bp.route("/statystyki")
def statystyki():
    return jsonify(statystyki_nauki.policz(get_db(), powtorki.dzisiaj()))


# ---------- Powtórki (ETAP 6, system Leitnera — zob. powtorki.py) ----------


@fiszki_bp.route("/powtorka")
def powtorka():
    pdf_id = request.args.get("pdf_id", type=int)
    pdf = _pobierz_pdf_albo_404(pdf_id) if pdf_id is not None else None
    # Tryb „przed egzaminem” (ETAP 39): wszystkie fiszki, bez zapisu ocen.
    wszystkie = request.args.get("wszystkie") == "1"
    return render_template("fiszki/powtorka.html", pdf=pdf, wszystkie=wszystkie, temat=_temat_z_zapytania())


@fiszki_bp.route("/powtorka/kolejka")
def kolejka_powtorki():
    """Fiszki do powtórki dziś: najpierw z niższych pudełek (słabiej znane).

    Z `wszystkie=1` — wszystkie fiszki (tryb przed egzaminem) w losowej
    kolejności; harmonogram się wtedy nie zmienia, bo przeglądarka nie
    zapisuje ocen.
    """
    pdf_id = request.args.get("pdf_id", type=int)
    wszystkie = request.args.get("wszystkie") == "1"
    parametry = {"dzis": powtorki.dzisiaj().isoformat()}
    warunek = "1 = 1" if wszystkie else _WARUNEK_DO_POWTORKI
    temat = _temat_z_zapytania()
    if temat:
        warunek += " AND " + _WARUNEK_TEMATU
        parametry["temat"] = temat
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
            WHERE {warunek} {filtr_pdf}
            ORDER BY pudelko, fiszki.id""",
        parametry,
    ).fetchall()
    obrazki = obrazy.obrazy_fiszek(db)  # ETAP 154
    fiszki = [{**dict(w), "obraz": url_obrazu(obrazki.get(w["id"]))} for w in wiersze]
    if wszystkie:
        random.shuffle(fiszki)
    return jsonify(fiszki)


@fiszki_bp.route("/powtorka/<int:fiszka_id>", methods=["POST"])
def zapisz_powtorke(fiszka_id):
    dane = request.get_json(silent=True) or {}
    wynik = dane.get("wynik")
    if wynik not in powtorki.WYNIKI:
        return jsonify({"blad": "Wynik musi być 'umiem', 'trudne' albo 'nie_umiem'."}), 400

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
    db.execute(
        "INSERT INTO dziennik_powtorek (fiszka_id, data, wynik) VALUES (?, ?, ?)",
        (fiszka_id, dzis.isoformat(), wynik),
    )
    db.commit()

    return jsonify(
        {"fiszka_id": fiszka_id, "pudelko": nowe_pudelko, "nastepna_powtorka": nastepna.isoformat()}
    )


# ---------- Egzaminy (ETAP 51) ----------


@fiszki_bp.route("/egzaminy", methods=["POST"])
def dodaj_egzamin():
    """Formularz ze strony fiszek. Zakres: „wszystko”, „temat:…” albo „pdf:<id>”."""
    zakres = request.form.get("zakres") or "wszystko"
    temat, pdf_id = None, None
    if zakres.startswith("temat:"):
        temat = zakres[len("temat:"):].strip() or None
    elif zakres.startswith("pdf:"):
        try:
            pdf_id = int(zakres[len("pdf:"):])
        except ValueError:
            return redirect(url_for("fiszki.index", blad="Nieznany zakres egzaminu."))
        _pobierz_pdf_albo_404(pdf_id)
    try:
        egzaminy.dodaj(get_db(), request.form.get("nazwa", ""), request.form.get("data", ""), temat, pdf_id, powtorki.dzisiaj())
    except egzaminy.BladEgzaminu as e:
        return redirect(url_for("fiszki.index", blad=str(e)))
    return redirect(url_for("fiszki.index"))


@fiszki_bp.route("/egzaminy/<int:egzamin_id>/usun", methods=["POST"])
def usun_egzamin(egzamin_id):
    egzaminy.usun(get_db(), egzamin_id)
    return redirect(url_for("fiszki.index"))
