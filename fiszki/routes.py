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

from dane.gemini import BladGemini, zaproponuj_fiszke, zaproponuj_fiszki_ze_strony

from . import egzaminy, kosz, luki, obrazy, powtorki, quiz as quiz_fiszek, statystyki_nauki, tematy
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
    kosz.wyczysc_stare(db)  # ETAP 212: po 30 dniach kosz opróżnia się sam
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
        kosz=kosz.lista(db),
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


def terminy() -> list[dict]:
    """Nadchodzące egzaminy — do kalendarza na stronie głównej (ETAP 86)."""
    wynik = []
    for e in egzaminy.lista(get_db(), powtorki.dzisiaj()):
        if e["minal"]:
            continue
        zakres = e["temat"] or e["nazwa_oryginalna"] or "wszystkie fiszki"
        if not e["fiszki"]:
            opis = f"{zakres}: brak fiszek w zakresie"
        elif e["do_nauki"]:
            opis = f"{zakres}: utrwalone {e['procent']}%, ok. {e['dziennie']} fiszek dziennie"
        else:
            opis = f"{zakres}: wszystko utrwalone"
        wynik.append({
            "data": e["data"],
            "dni": e["dni"],
            "rodzaj": "egzamin",
            "nazwa": e["nazwa"],
            "opis": opis,
            "url": url_for("fiszki.index") + "#egzaminy",
        })
    return wynik


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
    obrazki = obrazy.obrazy_fiszek(db)
    zaslony = obrazy.zaslony_fiszek(db)  # ETAP 185
    return jsonify([{**dict(f), "tematy": po_fiszce.get(f["id"], []), "obraz": url_obrazu(obrazki.get(f["id"])), "zaslona": zaslony.get(f["id"])}
                    for f in fiszki])


def url_obrazu(nazwa: str | None) -> str | None:
    """ETAP 154: adres wycinka rysunku fiszki (albo None)."""
    return url_for("fiszki.obraz_fiszki", nazwa=nazwa) if nazwa else None


@fiszki_bp.route("/obrazy/<nazwa>")
def obraz_fiszki(nazwa):
    if not obrazy.WZOR_NAZWY.match(nazwa):
        abort(404)
    return send_from_directory(obrazy.folder(), nazwa, mimetype="image/png")


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
        obraz = obrazy.odczytaj(dane["obraz"]) if dane.get("obraz") else None  # ETAP 154
    except tematy.BladTematow as e:
        abort(400, str(e))
    except obrazy.BladObrazu as e:
        return jsonify({"blad": str(e)}), 400

    db = get_db()
    fiszka_id = _wstaw_fiszke(db, pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, lista_tematow)
    nazwa_obrazu = obrazy.zapisz(db, fiszka_id, obraz) if obraz else None
    db.commit()

    nowa = db.execute("SELECT * FROM fiszki WHERE id = ?", (fiszka_id,)).fetchone()
    return jsonify({**dict(nowa), "tematy": tematy.tematy_fiszek(db).get(fiszka_id, []), "obraz": url_obrazu(nazwa_obrazu)}), 201


def _wstaw_fiszke(db, pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, lista_tematow) -> int:
    cursor = db.execute(
        """INSERT INTO fiszki (pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, data_utworzenia)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (pdf_id, strona, fragment_tekstu, pytanie, odpowiedz, datetime.now().isoformat()),
    )
    tematy.ustaw(db, cursor.lastrowid, lista_tematow)
    return cursor.lastrowid


@fiszki_bp.route("/<int:pdf_id>/luki", methods=["POST"])
def zapisz_luki(pdf_id):
    """ETAP 139: fiszki z luką — po jednej na każde [[słowa]] w tekście.
    Kotwica (strona, fragment) ta sama dla wszystkich."""
    _pobierz_pdf_albo_404(pdf_id)
    dane = request.get_json(silent=True) or {}
    strona = dane.get("strona")
    fragment_tekstu = (dane.get("fragment_tekstu") or "").strip()
    if not isinstance(strona, int) or not fragment_tekstu:
        return jsonify({"blad": "Brak strony albo fragmentu źródła."}), 400
    try:
        nowe = luki.fiszki_z_luk(dane.get("tekst"))
        lista_tematow = tematy.normalizuj(dane.get("tematy"))
    except (luki.BladLuk, tematy.BladTematow) as e:
        return jsonify({"blad": str(e)}), 400
    db = get_db()
    identyfikatory = [_wstaw_fiszke(db, pdf_id, strona, fragment_tekstu, f["pytanie"], f["odpowiedz"], lista_tematow) for f in nowe]
    db.commit()
    return jsonify({"liczba": len(identyfikatory), "id": identyfikatory}), 201


@fiszki_bp.route("/<int:pdf_id>/fiszki/<int:fiszka_id>/zaslony", methods=["POST"])
def zaslon_fragmenty(pdf_id, fiszka_id):
    """ETAP 185: z fiszki z obrazem — nowe fiszki, każda z jednym zasłoniętym
    fragmentem. JSON {prostokaty: [[x, y, w, h], …] (0–1), odpowiedzi: [tekst, …],
    pytanie?: tekst}. Kotwica (strona, fragment) i tematy jak w fiszce wzorcowej."""
    _pobierz_pdf_albo_404(pdf_id)
    db = get_db()
    wzor = db.execute("SELECT * FROM fiszki WHERE id = ? AND pdf_id = ?", (fiszka_id, pdf_id)).fetchone()
    plik = obrazy.obrazy_fiszek(db).get(fiszka_id)
    if wzor is None or plik is None:
        abort(404)
    dane = request.get_json(silent=True) or {}
    try:
        prostokaty = obrazy.sprawdz_zaslony(dane.get("prostokaty"))
    except obrazy.BladObrazu as e:
        return jsonify({"blad": str(e)}), 400
    odpowiedzi = dane.get("odpowiedzi")
    if not isinstance(odpowiedzi, list) or len(odpowiedzi) != len(prostokaty) or not all(isinstance(o, str) and o.strip() for o in odpowiedzi):
        return jsonify({"blad": "Wpisz odpowiedź dla każdego zasłoniętego fragmentu."}), 400
    pytanie = (dane.get("pytanie") or "").strip()[:500] or "Co jest w zasłoniętym miejscu?"
    lista_tematow = tematy.tematy_fiszek(db).get(fiszka_id, [])
    nowe = []
    for (x, y, w, h), odpowiedz in zip(prostokaty, odpowiedzi):
        nowa = _wstaw_fiszke(db, pdf_id, wzor["strona"], wzor["fragment_tekstu"], pytanie, odpowiedz.strip()[:2000], lista_tematow)
        db.execute("INSERT INTO obrazy_fiszek (fiszka_id, plik) VALUES (?, ?)", (nowa, plik))  # ten sam plik obrazu
        db.execute("INSERT INTO zaslony_fiszek (fiszka_id, x, y, w, h) VALUES (?, ?, ?, ?, ?)", (nowa, x, y, w, h))
        nowe.append(nowa)
    db.commit()
    return jsonify({"liczba": len(nowe), "id": nowe}), 201


@fiszki_bp.route("/<int:pdf_id>/fiszki/<int:fiszka_id>", methods=["DELETE"])
def usun_fiszke(pdf_id, fiszka_id):
    _pobierz_pdf_albo_404(pdf_id)
    db = get_db()
    if db.execute("SELECT 1 FROM fiszki WHERE id = ? AND pdf_id = ?", (fiszka_id, pdf_id)).fetchone() is None:
        abort(404)
    kosz_id = kosz.odloz(db, folder_plikow(), obrazy.folder(), fiszka_id=fiszka_id)  # ETAP 212: do cofnięcia
    db.execute("DELETE FROM fiszki WHERE id = ? AND pdf_id = ?", (fiszka_id, pdf_id))
    db.commit()
    obrazy.usun_osierocone(db)
    return jsonify({"kosz_id": kosz_id})


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
        "SELECT fiszki.*, pdfy.nazwa_oryginalna, obrazy_fiszek.plik AS obraz_plik,"
        " zaslony_fiszek.x AS zas_x, zaslony_fiszek.y AS zas_y, zaslony_fiszek.w AS zas_w, zaslony_fiszek.h AS zas_h"
        " FROM fiszki JOIN pdfy ON pdfy.id = fiszki.pdf_id"
        " LEFT JOIN obrazy_fiszek ON obrazy_fiszek.fiszka_id = fiszki.id"
        " LEFT JOIN zaslony_fiszek ON zaslony_fiszek.fiszka_id = fiszki.id" + gdzie + kolejnosc,  # ETAP 185: zasłona  # ETAP 154: wycinek do druku
        parametry,
    ).fetchall()


@fiszki_bp.route("/<int:pdf_id>/usun", methods=["POST"])
def usun_pdf(pdf_id):
    """Usuwa PDF razem z jego fiszkami (i stanem powtórek — ON DELETE CASCADE)."""
    _pobierz_pdf_albo_404(pdf_id)
    db = get_db()
    kosz.odloz(db, folder_plikow(), obrazy.folder(), pdf_id=pdf_id)  # ETAP 212: plik PDF trafia do kosza
    db.execute("DELETE FROM fiszki WHERE pdf_id = ?", (pdf_id,))
    db.execute("DELETE FROM pdfy WHERE id = ?", (pdf_id,))
    db.commit()
    obrazy.usun_osierocone(db)
    return redirect(url_for("fiszki.index"))


@fiszki_bp.route("/kosz/<int:kosz_id>/przywroc", methods=["POST"])
def przywroc_z_kosza(kosz_id):
    """ETAP 212: przywraca usunięty PDF z fiszkami albo jedną fiszkę.
    Z fetch (Accept: application/json) — JSON; z formularza — przekierowanie."""
    jako_json = request.accept_mimetypes.best == "application/json"
    try:
        wynik = kosz.przywroc(get_db(), kosz_id, folder_plikow(), obrazy.folder())
    except kosz.BladKosza as e:
        return (jsonify({"blad": str(e)}), 400) if jako_json else redirect(url_for("fiszki.index", blad=str(e)))
    if jako_json:
        return jsonify(wynik)
    return redirect(url_for("fiszki.widok_pdf", pdf_id=wynik["pdf_id"]))


# ---------- ostatnio używane na stronie głównej (ETAP 141) ----------


def ostatnie(limit: int = 3) -> list[dict]:
    """PDF-y od ostatniej pracy: dodanie pliku, nowa fiszka, powtórka."""
    wiersze = get_db().execute(
        """SELECT pdfy.id, pdfy.nazwa_oryginalna, COUNT(fiszki.id) AS liczba,
                  MAX(pdfy.data_dodania, COALESCE(MAX(fiszki.data_utworzenia), ''), COALESCE(MAX(powtorki.ostatnia_powtorka), '')) AS kiedy
           FROM pdfy LEFT JOIN fiszki ON fiszki.pdf_id = pdfy.id LEFT JOIN powtorki ON powtorki.fiszka_id = fiszki.id
           GROUP BY pdfy.id ORDER BY kiedy DESC LIMIT ?""", (limit,)
    ).fetchall()
    return [{"tytul": w["nazwa_oryginalna"], "opis": f"PDF z fiszkami · fiszek: {w['liczba']}", "kiedy": w["kiedy"],
             "url": url_for("fiszki.widok_pdf", pdf_id=w["id"])} for w in wiersze]


# Pozostałe trasy modułu — w osobnych plikach, rejestrują się na fiszki_bp.
# Import na końcu, bo tamte pliki importują fiszki_bp z tego modułu.
from . import trasy_nauka, trasy_telefon, trasy_wymiana  # noqa: E402, F401


# ---------- wyszukiwarka globalna (ETAP 128) ----------

MAKS_WYNIKOW_GLOBALNYCH = 10


def wyszukaj(fraza: str) -> list[dict]:
    """Fiszki z frazą w pytaniu, odpowiedzi albo fragmencie (bez wielkości liter)."""
    szukane = fraza.casefold()
    wyniki = []
    for f in _fiszki_do_eksportu():
        if szukane in " ".join((f["pytanie"], f["odpowiedz"], f["fragment_tekstu"] or "")).casefold():
            wyniki.append({"tytul": f["pytanie"], "opis": f"{f['nazwa_oryginalna']}, s. {f['strona']} — {f['odpowiedz'][:120]}",
                           "url": url_for("fiszki.widok_pdf", pdf_id=f["pdf_id"])})
            if len(wyniki) == MAKS_WYNIKOW_GLOBALNYCH:
                break
    return wyniki
