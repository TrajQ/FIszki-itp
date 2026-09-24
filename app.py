from flask import Flask, render_template

from atlas import atlas_bp
from mpzp import mpzp_bp
from fiszki import fiszki_bp
from dostepnosc import dostepnosc_bp
from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(atlas_bp, url_prefix="/atlas")
    app.register_blueprint(mpzp_bp, url_prefix="/mpzp")
    app.register_blueprint(fiszki_bp, url_prefix="/fiszki")
    app.register_blueprint(dostepnosc_bp, url_prefix="/dostepnosc")

    @app.route("/")
    def index():
        return render_template("index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    # Host zablokowany na stałe na 127.0.0.1 — aplikacja jest wyłącznie lokalna.
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG)
