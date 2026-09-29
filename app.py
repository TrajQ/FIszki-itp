from datetime import datetime

from flask import Flask, Response, redirect, render_template, url_for

from atlas import atlas_bp
from mpzp import mpzp_bp
from fiszki import fiszki_bp
from dostepnosc import dostepnosc_bp
from osiedle import osiedle_bp
from przepisy import przepisy_bp
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
    app.register_blueprint(osiedle_bp, url_prefix="/osiedle")
    app.register_blueprint(przepisy_bp, url_prefix="/przepisy")

    from fiszki.baza import init_db as init_db_fiszki, close_db as close_db_fiszki
    from atlas.baza import init_db as init_db_atlas, close_db as close_db_atlas
    from mpzp.baza import init_db as init_db_mpzp, close_db as close_db_mpzp
    from osiedle.baza import init_db as init_db_osiedle, close_db as close_db_osiedle
    from przepisy.baza import init_db as init_db_przepisy, close_db as close_db_przepisy

    with app.app_context():
        init_db_fiszki()
        init_db_atlas()
        init_db_mpzp()
        init_db_osiedle()
        init_db_przepisy()
    app.teardown_appcontext(close_db_fiszki)
    app.teardown_appcontext(close_db_atlas)
    app.teardown_appcontext(close_db_mpzp)
    app.teardown_appcontext(close_db_osiedle)
    app.teardown_appcontext(close_db_przepisy)

    @app.route("/")
    def index():
        # Każdy moduł sam liczy swoje podsumowanie; strona główna tylko je
        # wyświetla. Błąd w jednym module nie może zablokować strony głównej.
        from atlas.baza import liczba_zapisanych_zestawow
        from dostepnosc.routes import podsumowanie as podsumowanie_dostepnosci
        from fiszki.routes import podsumowanie as podsumowanie_fiszek
        from mpzp.routes import podsumowanie as podsumowanie_mpzp
        from osiedle.routes import podsumowanie as podsumowanie_osiedla
        from przepisy.routes import podsumowanie as podsumowanie_przepisow

        podsumowania = {}
        for modul, funkcja in [
            ("atlas", liczba_zapisanych_zestawow),
            ("mpzp", podsumowanie_mpzp),
            ("fiszki", podsumowanie_fiszek),
            ("dostepnosc", podsumowanie_dostepnosci),
            ("osiedle", podsumowanie_osiedla),
            ("przepisy", podsumowanie_przepisow),
        ]:
            try:
                podsumowania[modul] = funkcja()
            except Exception:
                app.logger.exception("Nie udało się policzyć podsumowania modułu %s", modul)
                podsumowania[modul] = None
        return render_template("index.html", p=podsumowania)

    @app.route("/kopia-zapasowa")
    def kopia_zapasowa():
        from kopia import utworz_kopie

        nazwa = f"warsztat_kopia_{datetime.now():%Y%m%d_%H%M}.zip"
        return Response(
            utworz_kopie(app.instance_path),
            mimetype="application/zip",
            headers={"Content-Disposition": f"attachment; filename={nazwa}"},
        )

    @app.route("/favicon.ico")
    def favicon():
        # Przeglądarki pytają o /favicon.ico także bez <link rel="icon">.
        return redirect(url_for("static", filename="favicon.svg"))

    return app


if __name__ == "__main__":
    app = create_app()
    # Host zablokowany na stałe na 127.0.0.1 — aplikacja jest wyłącznie lokalna.
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG)
