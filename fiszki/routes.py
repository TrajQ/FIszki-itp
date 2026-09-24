from flask import Blueprint, render_template

fiszki_bp = Blueprint(
    "fiszki",
    __name__,
    template_folder="templates",
    static_folder="static",
)


@fiszki_bp.route("/")
def index():
    return render_template("fiszki/index.html")
