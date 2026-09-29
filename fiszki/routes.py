import csv
import html
import io
import os
import random
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

from dane.gemini import BladGemini, zaproponuj_fiszke, zaproponuj_fiszki_ze_strony

from . import egzaminy, importer, powtorki, quiz as quiz_fiszek, statystyki_nauki, tematy
from .strona import zakotwiczone
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
        nauka=statystyki_nauki.policz(db, powtorki.dzisiaj()),
        najtrudniejsze=quiz_fiszek.najtrudniejsze(db),
        tematy=tematy.wszystkie(db, _WARUNEK_DO_POWTORKI, dzis),
        egzaminy=egzaminy.lista(db, powtorki.dzisiaj()),
        utrwalone=egzaminy.utrwalone_w_plikach(db),
        blad=request.args.get("blad"),
    )


# Fiszka jest do powtórki, gdy nie ma jeszcze stanu (nowa) albo termin minął.
# Używane w SQL z parametrem :dzis (data ISO — porównanie tekstowe działa).
_WARUNEK_DO_POWTORKI = (
    "fiszki.id IS NOT NULL AND "
    "(powtorki.fiszka_id IS NULL OR powtorki.nastepna_powtorka <= :dzis)"
)


# Filtr po temacie (ETAP 50) — dokładna pisownia z listy tematów.
_WARUNEK_TEMATU = "fiszki.id IN (SELECT fiszka_id FROM tematy_fiszek WHERE temat = :temat)"


def _temat_z_zapytania() -> str | None:
    temat = " ".join((request.args.get("temat") or "").split())
    return temat or None


def podsumowanie() -> dict:
    """Krótkie liczby na kartę modułu na stronie głównej."""
    db = get_db()
    dzis = powtorki.dzisiaj().isoformat()
    wiersz = db.execute(
        f"""SELECT COUNT(DISTINCT pdfy.id) AS pliki,
                   COUNT(fiszki.id) AS fiszki,
                   COALESCE(SUM({_WARUNEK_DO_POWTORKI}), 0) AS do_powtorki
            FROM pdfy
            LEFT JOIN fiszki ON fiszki.pdf_id = pdfy.id
            LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id""",
        {"dzis": dzis},
    ).fetchone()
    return dict(wiersz)


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
    wszystkie_tematy = [t["temat"] for t in tematy.wszystkie(get_db(), _WARUNEK_DO_POWTORKI, powtorki.dzisiaj().isoformat())]
    return render_template("fiszki/pdf.html", pdf=pdf, tematy=wszystkie_tematy)


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
    po_fiszce = tematy.tematy_fiszek(db)
    return jsonify([{**dict(f), "tematy": po_fiszce.get(f["id"], [])} for f in fiszki])


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


MIN_TEKST_STRONY = 80
MAKS_TEKST_STRONY = 20_000


@fiszki_bp.route("/<int:pdf_id>/szkice-strony", methods=["POST"])
def szkice_strony(pdf_id):
    """Kilka propozycji fiszek z całej strony; każda z kotwicą sprawdzoną w tekście."""
    _pobierz_pdf_albo_404(pdf_id)
    dane = request.get_json(silent=True) or {}
    tekst = (dane.get("tekst") or "").strip()
    if len(tekst) < MIN_TEKST_STRONY:
        return jsonify({"blad": "Na tej stronie prawie nie ma tekstu (może to skan albo rysunek)."}), 400
    tekst = tekst[:MAKS_TEKST_STRONY]

    try:
        propozycje = zaproponuj_fiszki_ze_strony(tekst)
    except BladGemini as e:
        return jsonify({"blad": str(e)}), 502

    dobre, odrzucone = zakotwiczone(propozycje, tekst)
    return jsonify({"propozycje": dobre, "odrzucone": odrzucone})


# ---------- Fiszki do druku (ETAP 31) ----------


@fiszki_bp.route("/druk")
def druk():
    """Karty do wycięcia i złożenia na pół (pytanie | odpowiedź)."""
    pdf_id = request.args.get("pdf_id", type=int)
    pdf = _pobierz_pdf_albo_404(pdf_id) if pdf_id is not None else None
    temat = _temat_z_zapytania()
    fiszki = _fiszki_do_eksportu(pdf_id, temat)
    return render_template("fiszki/druk.html", pdf=pdf, fiszki=fiszki, temat=temat)


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
    return jsonify(pytania)


@fiszki_bp.route("/statystyki")
def statystyki():
    return jsonify(statystyki_nauki.policz(get_db(), powtorki.dzisiaj()))


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
    try:
        lista_tematow = tematy.normalizuj(dane.get("tematy"))
    except tematy.BladTematow as e:
        abort(400, str(e))

    db = get_db()
    cursor = db.execute(
        """INSERT INTO fiszki (pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, data_utworzenia)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, datetime.now().isoformat()),
    )
    tematy.ustaw(db, cursor.lastrowid, lista_tematow)
    db.commit()

    nowa = db.execute("SELECT * FROM fiszki WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({**dict(nowa), "tematy": tematy.tematy_fiszek(db).get(cursor.lastrowid, [])}), 201


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
    try:
        # Bez pola „tematy” tematy zostają bez zmian (stare wywołania).
        lista_tematow = tematy.normalizuj(dane["tematy"]) if "tematy" in dane else None
    except tematy.BladTematow as e:
        abort(400, str(e))

    db = get_db()
    cursor = db.execute(
        "UPDATE fiszki SET pytanie = ?, odpowiedz = ? WHERE id = ? AND pdf_id = ?",
        (pytanie, odpowiedz, fiszka_id, pdf_id),
    )
    if cursor.rowcount == 0:
        abort(404)
    if lista_tematow is not None:
        tematy.ustaw(db, fiszka_id, lista_tematow)
    db.commit()

    zmieniona = db.execute("SELECT * FROM fiszki WHERE id = ?", (fiszka_id,)).fetchone()
    return jsonify({**dict(zmieniona), "tematy": tematy.tematy_fiszek(db).get(fiszka_id, [])})


def _fiszki_do_eksportu(pdf_id=None, temat=None):
    """Fiszki jednego PDF-a albo (pdf_id=None) wszystkie, z nazwą pliku;
    opcjonalnie tylko z danego tematu."""
    db = get_db()
    warunki, parametry = [], {}
    if pdf_id is not None:
        warunki.append("pdf_id = :pdf_id")
        parametry["pdf_id"] = pdf_id
    if temat is not None:
        warunki.append(_WARUNEK_TEMATU)
        parametry["temat"] = temat
    gdzie = (" WHERE " + " AND ".join(warunki)) if warunki else ""
    kolejnosc = " ORDER BY strona, fiszki.id" if pdf_id is not None else " ORDER BY pdfy.nazwa_oryginalna, strona, fiszki.id"
    return db.execute(
        "SELECT fiszki.*, pdfy.nazwa_oryginalna FROM fiszki JOIN pdfy ON pdfy.id = fiszki.pdf_id" + gdzie + kolejnosc,
        parametry,
    ).fetchall()


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


def _odpowiedz_anki(fiszki, pdf):
    """Plik tekstowy rozdzielany tabulatorami — Anki importuje go przez
    Plik → Importuj. Kolumny: pytanie, odpowiedź, źródło (plik i strona)."""
    wiersze = ["#separator:tab", "#html:true"]
    for f in fiszki:
        zrodlo = f"{f['nazwa_oryginalna']}, s. {f['strona']}" if f["strona"] else f["nazwa_oryginalna"]
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
    return _odpowiedz_anki(_fiszki_do_eksportu(), None)


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


@fiszki_bp.route("/<int:pdf_id>/usun", methods=["POST"])
def usun_pdf(pdf_id):
    """Usuwa PDF razem z jego fiszkami (i stanem powtórek — ON DELETE CASCADE)."""
    pdf = _pobierz_pdf_albo_404(pdf_id)
    db = get_db()
    db.execute("DELETE FROM fiszki WHERE pdf_id = ?", (pdf_id,))
    db.execute("DELETE FROM pdfy WHERE id = ?", (pdf_id,))
    db.commit()

    sciezka = os.path.join(folder_plikow(), pdf["nazwa_pliku"])
    if os.path.exists(sciezka):
        os.remove(sciezka)
    return redirect(url_for("fiszki.index"))


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
    fiszki = [dict(w) for w in wiersze]
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
