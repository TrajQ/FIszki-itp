import os
from datetime import datetime

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

import dziennik

from atlas import atlas_bp
from mpzp import mpzp_bp
from fiszki import fiszki_bp
from dostepnosc import dostepnosc_bp
from osiedle import osiedle_bp
from przepisy import przepisy_bp
from teren import teren_bp
from ceny import ceny_bp
from config import Config
from ochrona import dodaj_naglowki, sprawdz_zapytanie

MAKS_TERMINOW = 6  # kalendarz na stronie głównej: tyle najbliższych terminów


def create_app(instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    app.config.from_object(Config)
    dziennik.wlacz(app)  # ETAP 127: błędy w instance/logi/warsztat.log

    # Ochrona przed obcymi stronami w tej samej przeglądarce (ochrona.py).
    app.before_request(sprawdz_zapytanie)
    app.after_request(dodaj_naglowki)

    app.register_blueprint(atlas_bp, url_prefix="/atlas")
    app.register_blueprint(mpzp_bp, url_prefix="/mpzp")
    app.register_blueprint(fiszki_bp, url_prefix="/fiszki")
    app.register_blueprint(dostepnosc_bp, url_prefix="/dostepnosc")
    app.register_blueprint(osiedle_bp, url_prefix="/osiedle")
    app.register_blueprint(przepisy_bp, url_prefix="/przepisy")
    app.register_blueprint(teren_bp, url_prefix="/teren")
    app.register_blueprint(ceny_bp, url_prefix="/ceny")

    from fiszki.baza import init_db as init_db_fiszki, close_db as close_db_fiszki
    from atlas.baza import init_db as init_db_atlas, close_db as close_db_atlas
    from mpzp.baza import init_db as init_db_mpzp, close_db as close_db_mpzp
    from osiedle.baza import init_db as init_db_osiedle, close_db as close_db_osiedle
    from przepisy.baza import init_db as init_db_przepisy, close_db as close_db_przepisy
    from teren.baza import init_db as init_db_teren, close_db as close_db_teren
    from ceny.baza import init_db as init_db_ceny, close_db as close_db_ceny

    with app.app_context():
        init_db_fiszki()
        init_db_atlas()
        init_db_mpzp()
        init_db_osiedle()
        init_db_przepisy()
        init_db_teren()
        init_db_ceny()
    app.teardown_appcontext(close_db_fiszki)
    app.teardown_appcontext(close_db_atlas)
    app.teardown_appcontext(close_db_mpzp)
    app.teardown_appcontext(close_db_osiedle)
    app.teardown_appcontext(close_db_przepisy)
    app.teardown_appcontext(close_db_teren)
    app.teardown_appcontext(close_db_ceny)

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
        from teren.routes import podsumowanie as podsumowanie_terenu
        from ceny.routes import podsumowanie as podsumowanie_cen

        podsumowania = {}
        for modul, funkcja in [
            ("atlas", liczba_zapisanych_zestawow),
            ("mpzp", podsumowanie_mpzp),
            ("fiszki", podsumowanie_fiszek),
            ("dostepnosc", podsumowanie_dostepnosci),
            ("osiedle", podsumowanie_osiedla),
            ("przepisy", podsumowanie_przepisow),
            ("teren", podsumowanie_terenu),
            ("ceny", podsumowanie_cen),
        ]:
            try:
                podsumowania[modul] = funkcja()
            except Exception:
                app.logger.exception("Nie udało się policzyć podsumowania modułu %s", modul)
                podsumowania[modul] = None

        terminy = wszystkie_terminy()
        from kopia import ostatnia_kopia_automatyczna

        return render_template(
            "index.html", p=podsumowania, terminy=terminy[:MAKS_TERMINOW], wiecej_terminow=len(terminy) > MAKS_TERMINOW,
            kopia_auto=ostatnia_kopia_automatyczna(app.config["AUTO_KOPIA_FOLDER"]) if app.config["AUTO_KOPIA_DNI"] > 0 else None,
            auto_kopia_dni=app.config["AUTO_KOPIA_DNI"],
        )

    def wszystkie_terminy() -> list[dict]:
        """Kalendarz (ETAP 86): egzaminy z Fiszek i wyjścia w teren, od najbliższego.
        Błąd jednego modułu nie blokuje reszty."""
        from fiszki.routes import terminy as terminy_fiszek
        from teren.routes import terminy as terminy_terenu

        terminy = []
        for modul, funkcja in [("fiszki", terminy_fiszek), ("teren", terminy_terenu)]:
            try:
                terminy += funkcja()
            except Exception:
                app.logger.exception("Nie udało się odczytać terminów modułu %s", modul)
        return sorted(terminy, key=lambda t: (t["data"], t["rodzaj"], t["nazwa"]))

    @app.route("/kalendarz.ics")
    def kalendarz_ics():
        """Wszystkie nadchodzące terminy jako plik iCalendar (ETAP 102)."""
        from kalendarz import plik_ics

        return Response(
            plik_ics(wszystkie_terminy(), request.host_url.rstrip("/")),
            mimetype="text/calendar",
            headers={"Content-Disposition": "attachment; filename=warsztat_terminy.ics"},
        )

    @app.route("/pomoc")
    def pomoc():
        """Krótkie przepisy „jak zrobić…” dla każdego modułu (ETAP 87)."""
        return render_template("pomoc.html")

    @app.route("/szukaj")
    def szukaj():
        """Wyszukiwarka globalna (ETAP 128): każdy moduł przeszukuje swoje dane
        (funkcja wyszukaj w routes modułu), tu tylko zbieramy wyniki."""
        from ceny.routes import wyszukaj as w_cenach
        from fiszki.routes import wyszukaj as w_fiszkach
        from mpzp.routes import wyszukaj as w_mpzp
        from osiedle.routes import wyszukaj as w_osiedlu
        from przepisy.routes import wyszukaj as w_przepisach
        from teren.routes import wyszukaj as w_terenie

        fraza = " ".join((request.args.get("q") or "").split())[:100]
        grupy, bledy = [], []
        if len(fraza) >= 2:
            for nazwa, funkcja in [("Fiszki", w_fiszkach), ("Przepisy", w_przepisach), ("MPZP — moje działki", w_mpzp),
                                   ("Osiedle", w_osiedlu), ("Teren", w_terenie), ("Ceny", w_cenach)]:
                try:
                    wyniki = funkcja(fraza)
                except Exception:
                    app.logger.exception("Wyszukiwarka: błąd w module %s", nazwa)
                    bledy.append(nazwa)
                    continue
                if wyniki:
                    grupy.append({"nazwa": nazwa, "wyniki": wyniki})
        return render_template("szukaj.html", fraza=fraza, grupy=grupy, bledy=bledy)

    @app.route("/diagnostyka")
    def diagnostyka():
        """Stan konfiguracji, danych i wersji (ETAP 126); usługi — na żądanie."""
        import diagnostyka as d

        return render_template("diagnostyka.html", s=d.stan(app.config, app.instance_path),
                               uslugi=d.USLUGI, limit=d.LIMIT_CZASU_S, wpisy=dziennik.ostatnie(app.instance_path))

    @app.route("/diagnostyka/dziennik/wyczysc", methods=["POST"])
    def wyczysc_dziennik():
        dziennik.wyczysc(app.instance_path)
        return redirect(url_for("diagnostyka"))

    @app.route("/diagnostyka/uslugi")
    def diagnostyka_uslug():
        import diagnostyka as d

        return jsonify(d.sprawdz_uslugi())

    @app.route("/kopia-zapasowa")
    def kopia_zapasowa():
        from kopia import utworz_kopie

        nazwa = f"warsztat_kopia_{datetime.now():%Y%m%d_%H%M}.zip"
        return Response(
            utworz_kopie(app.instance_path),
            mimetype="application/zip",
            headers={"Content-Disposition": f"attachment; filename={nazwa}"},
        )

    @app.route("/kopia-zapasowa/przywroc", methods=["GET", "POST"])
    def przywroc_kopie():
        """Przywracanie danych z kopii (ETAP 129): wgrany ZIP albo kopia z folderu kopii."""
        from kopia import BladKopii, kopie_do_przywrocenia, przywroc_kopie as przywroc

        folder_kopii = app.config["AUTO_KOPIA_FOLDER"]
        dostepne = kopie_do_przywrocenia(folder_kopii)
        if request.method == "GET":
            return render_template("przywracanie.html", kopie=dostepne, folder_kopii=folder_kopii, wynik=None, blad=None)
        if request.form.get("potwierdzam") != "tak":
            blad = "Zaznacz, że rozumiesz, że obecne dane zostaną zastąpione (zostaną zachowane w kopii i w folderze instance_stary)."
            return render_template("przywracanie.html", kopie=dostepne, folder_kopii=folder_kopii, wynik=None, blad=blad), 400
        nazwa = request.form.get("z_folderu")
        if nazwa:
            if nazwa not in {k["nazwa"] for k in dostepne}:  # tylko pliki z listy — żadnych dowolnych ścieżek
                return render_template("przywracanie.html", kopie=dostepne, folder_kopii=folder_kopii, wynik=None, blad="Nie ma takiej kopii."), 400
            zrodlo = os.path.join(folder_kopii, nazwa)
        else:
            plik = request.files.get("plik")
            if plik is None or not plik.filename:
                return render_template("przywracanie.html", kopie=dostepne, folder_kopii=folder_kopii, wynik=None, blad="Wybierz plik ZIP z kopią."), 400
            zrodlo = plik.stream
        try:
            wynik = przywroc(app.instance_path, zrodlo, folder_kopii)
        except BladKopii as e:
            return render_template("przywracanie.html", kopie=dostepne, folder_kopii=folder_kopii, wynik=None, blad=str(e)), 400
        app.logger.warning("Przywrócono dane z kopii (%s plików); poprzednie w %s", wynik["plikow"], wynik["stary_folder"])
        return render_template("przywracanie.html", kopie=kopie_do_przywrocenia(folder_kopii), folder_kopii=folder_kopii, wynik=wynik, blad=None)

    @app.route("/favicon.ico")
    def favicon():
        # Przeglądarki pytają o /favicon.ico także bez <link rel="icon">.
        return redirect(url_for("static", filename="favicon.svg"))

    return app


def kopia_przy_starcie(app):
    """Kopia automatyczna w tle (ETAP 97) — start aplikacji nie czeka na ZIP."""
    import threading

    from kopia import kopia_automatyczna

    def zrob():
        try:
            sciezka = kopia_automatyczna(app.instance_path, Config.AUTO_KOPIA_FOLDER, Config.AUTO_KOPIA_DNI)
            if sciezka:
                print(f"Kopia automatyczna danych: {sciezka}")
        except OSError as e:
            print(f"Nie udało się zrobić kopii automatycznej: {e}")

    threading.Thread(target=zrob, daemon=True).start()


if __name__ == "__main__":
    app = create_app()
    kopia_przy_starcie(app)
    # Host zablokowany na stałe na 127.0.0.1 — aplikacja jest wyłącznie lokalna.
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG)
