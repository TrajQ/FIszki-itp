from flask import Blueprint, render_template

dostepnosc_bp = Blueprint(
    "dostepnosc",
    __name__,
    template_folder="templates",
    static_folder="static",
)


@dostepnosc_bp.route("/")
def index():
    return render_template("dostepnosc/index.html")
