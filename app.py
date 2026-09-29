from flask import Flask, render_template

from atlas import atlas_bp
from mpzp import mpzp_bp
from fiszki import fiszki_bp
from dostepnosc import dostepnosc_bp
from config import Config
from ochrona import dodaj_naglowki, sprawdz_zapytanie


def create_app(instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    app.config.from_object(Config)

    # Ochrona przed obcymi stronami w tej samej przeglądarce (ochrona.py).
    app.before_request(sprawdz_zapytanie)
    app.after_request(dodaj_naglowki)

    app.register_blueprint(atlas_bp, url_prefix="/atlas")
    app.register_blueprint(mpzp_bp, url_prefix="/mpzp")
    app.register_blueprint(fiszki_bp, url_prefix="/fiszki")
    app.register_blueprint(dostepnosc_bp, url_prefix="/dostepnosc")

    from fiszki.baza import init_db as init_db_fiszki, close_db as close_db_fiszki
    from atlas.baza import init_db as init_db_atlas, close_db as close_db_atlas
    from mpzp.baza import init_db as init_db_mpzp, close_db as close_db_mpzp

    with app.app_context():
        init_db_fiszki()
        init_db_atlas()
        init_db_mpzp()
    app.teardown_appcontext(close_db_fiszki)
    app.teardown_appcontext(close_db_atlas)
    app.teardown_appcontext(close_db_mpzp)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    # Host zablokowany na stałe na 127.0.0.1 — aplikacja jest wyłącznie lokalna.
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG)
