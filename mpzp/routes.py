from flask import Blueprint, render_template

mpzp_bp = Blueprint(
    "mpzp",
    __name__,
    template_folder="templates",
    static_folder="static",
)


@mpzp_bp.route("/")
def index():
    return render_template("mpzp/index.html")
