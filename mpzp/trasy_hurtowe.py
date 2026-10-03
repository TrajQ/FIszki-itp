"""Hurtowe sprawdzenie listy działek (ETAP 191).

Lista identyfikatorów (albo „obręb numer”) z arkusza czy z ogłoszenia
przetargu → dla każdej działki: gmina, powierzchnia, przeznaczenie w planie
(WFS gminy albo krajowa integracja GUGiK) i stan. Zapytania idą po kolei,
najwyżej MAKS_DZIALEK naraz — usługi publiczne nie są do masowego
pobierania. Wynik nie trafia do historii (to nie są działki „oglądane”).
"""

import re

from flask import render_template, request

from dane.uldk import WZOR_ID_DZIALKI, BladULDK

from . import krajowe, routes
from .geometria import powierzchnia_m2
from .gminy import znajdz_gmine
from .routes import mpzp_bp
from .symbole import opisz_symbol
from .wfs import BladWFS

MAKS_DZIALEK = 30


def wpisy_z_tekstu(tekst: str) -> list[str]:
    """Wiersze, średniki albo tabulatory (wklejone z arkusza) → lista wpisów
    bez powtórzeń; przecinek rozdziela tylko pełne identyfikatory (numer
    działki w „obręb numer” nie ma przecinka, ale nazwa obrębu może mieć)."""
    wpisy = []
    for linia in re.split(r"[\n;\t]+", tekst or ""):
        kawalki = [k.strip() for k in linia.split(",") if k.strip()]
        czesci = kawalki if len(kawalki) > 1 and all(WZOR_ID_DZIALKI.match(k) for k in kawalki) else [linia]
        for c in czesci:
            c = " ".join(c.split())
            if c and c not in wpisy:
                wpisy.append(c)
    return wpisy


def sprawdz_wpis(wpis: str) -> dict:
    """Jeden wpis → {"wpis", "stan", "dzialka_id", "gmina", "powierzchnia_m2", "przeznaczenie", "opis", "lat", "lon"}."""
    wynik = {"wpis": wpis, "stan": "ok", "dzialka_id": None, "powierzchnia_m2": None, "przeznaczenie": None, "opis": None, "uwaga": None}
    try:
        if WZOR_ID_DZIALKI.match(wpis):
            dzialka = routes.znajdz_dzialke_po_id(wpis)
        else:
            znalezione = routes.szukaj_dzialek(wpis)
            if len(znalezione) != 1:
                wynik.update(stan="niejednoznaczny" if znalezione else "nie znaleziono",
                             uwaga=f"{len(znalezione)} działek pasuje — podaj pełny identyfikator" if znalezione else "ULDK nie zna takiej działki")
                return wynik
            dzialka = routes.znajdz_dzialke_po_id(znalezione[0].id)
    except (ValueError, BladULDK) as e:
        wynik.update(stan="błąd", uwaga=str(e))
        return wynik
    if dzialka is None:
        wynik.update(stan="nie znaleziono", uwaga="ULDK nie zna takiej działki")
        return wynik
    punkt = dzialka.geometria.representative_point()
    wynik.update(dzialka_id=dzialka.id, powierzchnia_m2=round(powierzchnia_m2(dzialka.geometria), 1), lat=punkt.y, lon=punkt.x)
    try:
        gmina = znajdz_gmine(dzialka.teryt_gminy)
        if gmina is not None:
            wydzielenie = routes.znajdz_przeznaczenie(gmina, punkt)
            wynik["zrodlo"] = f"WFS gminy {gmina.nazwa}"
            wynik["przeznaczenie"] = wydzielenie.atrybuty.get(gmina.pole_przeznaczenia) if wydzielenie else None
        else:
            obiekty = routes.plan_krajowy(punkt.y, punkt.x)
            wynik["zrodlo"] = "krajowa integracja planów (GUGiK)"
            wynik["przeznaczenie"] = krajowe.rozpoznaj_przeznaczenie(obiekty) if obiekty else None
            if obiekty and not wynik["przeznaczenie"]:
                wynik["uwaga"] = "plan jest, symbolu nie odczytano — sprawdź na mapie"
            wynik["plan"] = bool(obiekty)
    except (BladWFS, krajowe.BladKIMPZP) as e:
        wynik.update(stan="błąd", uwaga=str(e))
        return wynik
    if wynik["przeznaczenie"]:
        wynik["opis"] = opisz_symbol(wynik["przeznaczenie"])
    elif not wynik.get("uwaga"):
        wynik.update(stan="bez planu", uwaga="brak planu miejscowego w tym miejscu")
    return wynik


@mpzp_bp.route("/hurtowo", methods=["GET", "POST"])
def hurtowo():
    tekst = request.form.get("lista", "") if request.method == "POST" else ""
    wpisy = wpisy_z_tekstu(tekst)
    blad = None
    if request.method == "POST" and not wpisy:
        blad = "Wklej co najmniej jeden identyfikator działki albo „obręb numer”."
    elif len(wpisy) > MAKS_DZIALEK:
        blad = f"Najwyżej {MAKS_DZIALEK} działek naraz (wklejono {len(wpisy)}) — podziel listę."
    wyniki = [sprawdz_wpis(w) for w in wpisy] if wpisy and not blad else []
    return render_template("mpzp/hurtowo.html", tekst=tekst, wyniki=wyniki, blad=blad, maks=MAKS_DZIALEK)
