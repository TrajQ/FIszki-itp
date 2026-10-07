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
from ochrona import dodaj_naglowki, sprawdz_zapytanie, za_duzy_plik

MAKS_TERMINOW = 6  # kalendarz na stronie głównej: tyle najbliższych terminów
MAKS_OSTATNICH = 6  # ETAP 141: „Wróć do pracy” — tyle ostatnio używanych rzeczy


def kiedy_opis(kiedy: str, teraz: datetime) -> str:
    """ISO → „dziś, 14:05” / „wczoraj, 9:12” / „3 dni temu” / „12.09.2026”."""
    try:
        chwila = datetime.fromisoformat(kiedy)
    except (TypeError, ValueError):
        return ""
    dni = (teraz.date() - chwila.date()).days
    if dni == 0:
        return f"dziś, {chwila.hour}:{chwila.minute:02d}"
    if dni == 1:
        return f"wczoraj, {chwila.hour}:{chwila.minute:02d}"
    if 2 <= dni <= 6:
        return f"{dni} dni temu"
    return chwila.strftime("%d.%m.%Y")


def create_app(instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    app.config.from_object(Config)
    dziennik.wlacz(app)  # ETAP 127: błędy w instance/logi/warsztat.log

    # Ochrona przed obcymi stronami w tej samej przeglądarce (ochrona.py).
    app.before_request(sprawdz_zapytanie)
    app.after_request(dodaj_naglowki)
    app.register_error_handler(413, za_duzy_plik)  # ETAP 229

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

    # ETAP 142: data i godzina w stopce wydruków (templates/_wydruk.html)
    app.jinja_env.globals["teraz_wydruku"] = lambda: datetime.now().strftime("%d.%m.%Y, %H:%M")

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
        import kopia

        ostatnie = ostatnio_uzywane()
        import przypiete as przypiete_mod  # ETAP 211

        przypiete = przypiete_mod.wczytaj(app.instance_path)
        adresy_przypietych = {p["url"] for p in przypiete}
        ostatnie = [{**o, "przypiete": o["url"] in adresy_przypietych} for o in ostatnie]
        import nowosci  # ETAP 159

        nowe_etapy = nowosci.nowe(app.instance_path)
        # ETAP 146: „Pierwsze kroki”, dopóki w żadnym module nie ma własnych danych
        pusta = not ostatnie and not podsumowania.get("atlas") and not (podsumowania.get("dostepnosc") or {}).get("pliki")
        pierwsze_kroki = {"klucz_gemini": bool(app.config.get("GEMINI_API_KEY")),
                          "klucz_gus": bool(app.config.get("GUS_BDL_API_KEY"))} if pusta else None
        return render_template(
            "index.html", p=podsumowania, terminy=terminy[:MAKS_TERMINOW], wiecej_terminow=len(terminy) > MAKS_TERMINOW,
            ostatnie=ostatnie, przypiete=przypiete, pierwsze_kroki=pierwsze_kroki, nowe_etapy=nowe_etapy,
            kopia_auto=kopia.ostatnia_kopia_automatyczna(app.config["AUTO_KOPIA_FOLDER"]) if app.config["AUTO_KOPIA_DNI"] > 0 else None,
            auto_kopia_dni=app.config["AUTO_KOPIA_DNI"],
            poza_dyskiem=_stan_kopii_poza_dyskiem(pusta),
        )

    def _stan_kopii_poza_dyskiem(pusta: bool) -> dict:
        """ETAP 168: kiedy ostatnio kopia trafiła poza ten komputer i czy
        przypomnieć (tylko gdy są już jakieś dane)."""
        import kopia

        data = kopia.kopia_poza_dyskiem(app.instance_path)
        dni = (datetime.now() - data).days if data else None
        return {
            "data": data,
            "dni": dni,
            "przypomnij": not pusta and (dni is None or dni >= kopia.PRZYPOMNIENIE_DNI),
            "ten_sam_dysk": app.config["AUTO_KOPIA_DNI"] > 0 and kopia.ten_sam_dysk(app.instance_path, app.config["AUTO_KOPIA_FOLDER"]),
        }

    def ostatnio_uzywane() -> list[dict]:
        """ETAP 141: każdy moduł podaje swoje ostatnio używane rzeczy (funkcja
        ostatnie w routes), tu łączymy je od najświeższej. Błąd modułu nie
        blokuje strony głównej."""
        from ceny.routes import ostatnie as w_cenach
        from fiszki.routes import ostatnie as w_fiszkach
        from mpzp.routes import ostatnie as w_mpzp
        from osiedle.routes import ostatnie as w_osiedlu
        from przepisy.routes import ostatnie as w_przepisach
        from teren.routes import ostatnie as w_terenie

        wszystkie = []
        for modul, funkcja in [("Fiszki", w_fiszkach), ("Przepisy", w_przepisach), ("MPZP", w_mpzp),
                               ("Osiedle", w_osiedlu), ("Teren", w_terenie), ("Ceny", w_cenach)]:
            try:
                wszystkie += [{**w, "modul": modul} for w in funkcja()]
            except Exception:
                app.logger.exception("Ostatnio używane: błąd w module %s", modul)
        teraz = datetime.now()
        wszystkie.sort(key=lambda w: w["kiedy"] or "", reverse=True)
        return [{**w, "kiedy_opis": kiedy_opis(w["kiedy"], teraz)} for w in wszystkie[:MAKS_OSTATNICH]]

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

    @app.route("/przypiete", methods=["POST"])
    def przypnij():
        """ETAP 211: JSON {url, tytul, modul?, opis?} → lista przypiętych."""
        import przypiete

        try:
            return jsonify(przypiete.przypnij(app.instance_path, request.get_json(silent=True) or {}))
        except przypiete.BladPrzypiecia as e:
            return jsonify({"blad": str(e)}), 400

    @app.route("/przypiete/usun", methods=["POST"])
    def odepnij():
        import przypiete

        return jsonify(przypiete.odepnij(app.instance_path, (request.get_json(silent=True) or {}).get("url")))

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

    @app.route("/co-nowego")
    def co_nowego():
        """ETAP 159: zmiany z docs/CHANGELOG.md; obejrzenie strony zeruje pasek na stronie głównej."""
        import nowosci

        lista = nowosci.wpisy()
        poprzedni = nowosci.widziany(app.instance_path)
        if lista:
            nowosci.zapisz_widziany(app.instance_path, lista[0]["etap"])
        return render_template("co_nowego.html", wpisy=lista[:40], poprzedni=poprzedni, wszystkich=len(lista))

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

    @app.route("/kopia-zapasowa/poza-dyskiem", methods=["POST"])
    def kopia_poza_dyskiem():
        """ETAP 168: użytkownik potwierdza, że skopiował kopię poza ten komputer."""
        from kopia import zapisz_kopie_poza_dyskiem

        zapisz_kopie_poza_dyskiem(app.instance_path)
        return redirect(url_for("index") + "#kopia")

    @app.route("/kopia-zapasowa/sprawdz", methods=["POST"])
    def sprawdz_kopie():
        """ETAP 168: sprawdzenie wybranej kopii bez przywracania."""
        from kopia import BladKopii, kopie_do_przywrocenia, sprawdz_kopie as sprawdz

        folder_kopii = app.config["AUTO_KOPIA_FOLDER"]
        dostepne = kopie_do_przywrocenia(folder_kopii)

        def strona(sprawdzenie, kod=200):
            return render_template("przywracanie.html", kopie=dostepne, folder_kopii=folder_kopii, wynik=None, blad=None, sprawdzenie=sprawdzenie), kod

        nazwa = request.form.get("z_folderu")
        if nazwa:
            if nazwa not in {k["nazwa"] for k in dostepne}:  # tylko pliki z listy
                return strona({"ok": False, "nazwa": "?", "opis": "Nie ma takiej kopii."}, 400)
            zrodlo = os.path.join(folder_kopii, nazwa)
        else:
            plik = request.files.get("plik")
            if plik is None or not plik.filename:
                return strona({"ok": False, "nazwa": "?", "opis": "Wybierz kopię z listy albo plik ZIP."}, 400)
            nazwa, zrodlo = plik.filename, plik.stream
        try:
            plikow = sprawdz(zrodlo)
        except BladKopii as e:
            return strona({"ok": False, "nazwa": nazwa, "opis": str(e)})
        return strona({"ok": True, "nazwa": nazwa, "opis": f"Kopia jest w porządku: {plikow} plików, bazy danych bez błędów — da się z niej przywrócić dane."})

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
        except (OSError, ValueError) as e:  # ValueError: BladKopii — kopia nie przeszła sprawdzenia (ETAP 168)
            print(f"Nie udało się zrobić kopii automatycznej: {e}")

    threading.Thread(target=zrob, daemon=True).start()


if __name__ == "__main__":
    app = create_app()
    kopia_przy_starcie(app)
    # Host zablokowany na stałe na 127.0.0.1 — aplikacja jest wyłącznie lokalna.
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG)
