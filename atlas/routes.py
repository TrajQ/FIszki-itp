from flask import Blueprint, render_template

atlas_bp = Blueprint(
    "atlas",
    __name__,
    template_folder="templates",
    static_folder="static",
)


@atlas_bp.route("/")
def index():
    return render_template("atlas/index.html")
