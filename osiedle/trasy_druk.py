"""Raport koncepcji do druku, szkic SVG i porównanie wariantów (ETAP 60)."""

from flask import Response, render_template, request
from markupsafe import Markup
from werkzeug.utils import secure_filename

from . import baza
from .bilans import FUNKCJE, bilans
from .program import ZALOZENIA
from .routes import _koncepcja_albo_404, osiedle_bp
from .rysunek_svg import skala_dla, szkic_svg
from .wskazniki import USTALENIA

MAKS_WARIANTOW = 4


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>/raport")
def raport(koncepcja_id):
    k = _koncepcja_albo_404(koncepcja_id)
    return render_template(
        "osiedle/raport.html",
        k=k,
        b=bilans(k["geojson"], k["ustawienia"]),
        szkic=Markup(szkic_svg(k["geojson"], 1000, 620)),  # tylko liczby i kolory z kodu
        funkcje=FUNKCJE,
        ustalenia=USTALENIA,
        zalozenia=ZALOZENIA,
    )


@osiedle_bp.route("/koncepcje/<int:koncepcja_id>.svg")
def szkic(koncepcja_id):
    k = _koncepcja_albo_404(koncepcja_id)
    nazwa = secure_filename(f"koncepcja_{k['id']}_{k['nazwa']}.svg") or "koncepcja.svg"
    return Response(
        szkic_svg(k["geojson"], 1000, 620),
        mimetype="image/svg+xml",
        headers={"Content-Disposition": f"attachment; filename={nazwa}"},
    )


@osiedle_bp.route("/porownanie")
def porownanie():
    """Warianty obok siebie: bilans, wskaźniki, program, szkice w jednej skali."""
    wszystkie = baza.lista()
    wybrane = []
    for tekst in request.args.getlist("id")[:MAKS_WARIANTOW]:
        if tekst.isdigit() and (k := baza.pobierz(int(tekst))) is not None:
            wybrane.append(k)
    warianty = []
    if len(wybrane) >= 2:
        skala = skala_dla([k["geojson"] for k in wybrane], 360, 260)
        for k in wybrane:
            warianty.append(
                {
                    "k": k,
                    "b": bilans(k["geojson"], k["ustawienia"]),
                    "szkic": Markup(szkic_svg(k["geojson"], 360, 260, skala)),
                }
            )
    # funkcje obecne w którymkolwiek wariancie, w kolejności z FUNKCJE
    obecne = {f["funkcja"] for w in warianty for f in w["b"]["funkcje"]}
    return render_template(
        "osiedle/porownanie.html",
        wszystkie=wszystkie,
        wybrane_id=[k["id"] for k in wybrane],
        warianty=warianty,
        funkcje=[(kod, f) for kod, f in FUNKCJE.items() if kod in obecne],
        maks=MAKS_WARIANTOW,
    )
