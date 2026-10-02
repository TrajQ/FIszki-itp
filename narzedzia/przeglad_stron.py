"""Przegląd wszystkich stron Warsztatu w przeglądarce (ETAP 118).

Otwiera każdą stronę HTML (lista z tablicy tras Flaska + strony z
parametrami na danych testowych) na szerokości telefonu (390 px, tryb
ciemny) i komputera (1300 px, jasny). Zgłasza: kod HTTP ≥ 400, błędy
JavaScript, przewijanie poziome strony. Sieć zewnętrzna jest odcięta.

Wymaga Playwright z Chromium — narzędzie dla autora, nie część aplikacji
(nie ma go w requirements.txt):
    pip install playwright && playwright install chromium
    python narzedzia/przeglad_stron.py
Ścieżkę do Chromium można podać w zmiennej CHROMIUM.
"""

import os
import random
import sys
import tempfile
import threading

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KATALOG)
sys.path.insert(0, os.path.join(KATALOG, "tests"))
from app import create_app
from ceny import trasy_rcn
from test_ceny import plik_rcn, lokal, geometria_gpkg, dodaj_dzialki, dzialka
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
random.seed(3)
pobrane = tempfile.mkdtemp()
plik_rcn(os.path.join(pobrane, "rcn.gpkg"), [lokal(i, lok_nr_kond=i % 8, dok_data=f"{2021 + i % 4}-05-01", lok_cena_brutto=random.randint(400, 900) * 1000,
                                                  geom=geometria_gpkg(50.06 + random.gauss(0, 0.01), 19.94 + random.gauss(0, 0.015))) for i in range(1, 200)])
dodaj_dzialki(os.path.join(pobrane, "rcn.gpkg"), [dzialka(f"T{i}", i, dzi_cena_brutto=random.randint(50, 300) * 1000) for i in range(1, 40)])
trasy_rcn.katalogi_pobranych = lambda: [pobrane]
app = create_app(instance_path=tempfile.mkdtemp())
c = app.test_client()
c.post("/teren/projekty", data={"nazwa": "Ankieta — Rynek", "wzor": "ankieta"})
c.post("/osiedle/koncepcje", json={"nazwa": "A"})
c.post("/ceny/transakcje/import", data={"sciezka": os.path.join(pobrane, "rcn.gpkg")})
c.post("/ceny/transakcje/1/obszary", json={"nazwa": "Centrum", "geometria": {"type": "Polygon", "coordinates": [[[19.92, 50.05], [19.96, 50.05], [19.96, 50.07], [19.92, 50.07], [19.92, 50.05]]]}})
# Brak etykiet, nazw i tekstów alternatywnych — to, co czytnik ekranu
# przeczyta jako „przycisk”, „pole edycji” albo pominie (ETAP 130).
SPRAWDZ_DOSTEPNOSC = """() => {
    const widoczny = (e) => e.getClientRects().length > 0 && getComputedStyle(e).visibility !== "hidden";
    const nazwa = (e) => (e.getAttribute("aria-label") || e.getAttribute("title") || e.getAttribute("aria-labelledby") || "").trim();
    const p = [];
    if (!document.documentElement.lang) p.push("brak lang");
    for (const e of document.querySelectorAll("img")) if (!e.hasAttribute("alt")) p.push("img bez alt: " + (e.id || e.src.slice(-40)));
    for (const e of document.querySelectorAll("input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea")) {
        if (!widoczny(e)) continue;
        const etykieta = e.closest("label") || (e.id && document.querySelector(`label[for="${e.id}"]`));
        if (!etykieta && !nazwa(e) && !e.getAttribute("placeholder")) p.push("pole bez etykiety: " + (e.id || e.name || e.type));
    }
    for (const e of document.querySelectorAll("button, a[href]")) {
        if (!widoczny(e)) continue;
        if (!e.textContent.trim() && !nazwa(e) && !e.querySelector("img[alt]:not([alt=''])")) p.push(e.tagName.toLowerCase() + " bez nazwy: " + (e.id || e.className || e.getAttribute("href")));
    }
    const id = {};
    for (const e of document.querySelectorAll("[id]")) id[e.id] = (id[e.id] || 0) + 1;
    for (const [k, n] of Object.entries(id)) if (n > 1) p.push(`id powtórzony ${n}×: ${k}`);
    return p;
}"""

WYMAGAJA_PARAMETROW = ("/dostepnosc/raport", "/mpzp/raport")  # ?plik=, ?id=
POMIN = ("favicon.ico", ".csv", ".json", ".svg", ".geojson", ".ics", ".txt", ".html", "/static", "/plik", "/telefon")
STRONY = sorted({r.rule for r in app.url_map.iter_rules() if "GET" in r.methods and not r.arguments and not r.rule.endswith(POMIN) and "static" not in r.endpoint and r.rule not in WYMAGAJA_PARAMETROW})
STRONY += ["/teren/projekty/1", "/teren/projekty/1/raport", "/osiedle/koncepcje/1/raport", "/ceny/transakcje?plik=1", "/ceny/transakcje?plik=1&co=dzialki",
           "/ceny/transakcje/1/raport", "/ceny/transakcje/1/raport?co=dzialki", "/ceny/transakcje/1/wycena?lat=50.06&lng=19.94&pow=50&promien=1000&tolerancja=0.2"]
srv = make_server("127.0.0.1", 5218, app, threaded=True); threading.Thread(target=srv.serve_forever, daemon=True).start()
problemy = 0
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)
    for szer, schemat in ((390, "dark"), (1300, "light")):
        ctx = b.new_context(viewport={"width": szer, "height": 900}, color_scheme=schemat, accept_downloads=True)
        ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith("http://127.0.0.1") else route.abort())
        for adres in STRONY:
            pg = ctx.new_page(); bledy = []
            pg.on("pageerror", lambda e: bledy.append(str(e)[:120]))
            try:
                odp = pg.goto("http://127.0.0.1:5218" + adres); pg.wait_for_timeout(600)
            except Exception as e:
                if "Download is starting" in str(e):
                    pg.close(); continue  # plik do pobrania, nie strona
                raise
            typ = odp.headers.get("content-type", "")
            if "text/html" not in typ:
                pg.close(); continue
            sw = pg.evaluate("document.documentElement.scrollWidth")
            winni = pg.evaluate("[...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('nav, .leaflet-container, [class*=przewijanie], [class*=wrap], .zlozony__przewijanie, table')).slice(0,3).map(e => e.tagName + '.' + e.className)")
            # ETAP 130: podstawowa dostępność — tylko na jednej szerokości (wynik ten sam)
            dostepnosc = pg.evaluate(SPRAWDZ_DOSTEPNOSC) if szer == 1300 else []
            if dostepnosc:
                problemy += 1
                print("dostępność", adres, dostepnosc[:6])
            if odp.status >= 400 or bledy or sw > szer:
                problemy += 1
                print(szer, adres, odp.status, "| szer:", sw, winni, "| bledy:", bledy)
            pg.close()
        ctx.close()
    b.close()
srv.shutdown()
print("stron:", len(STRONY), "| problemów:", problemy)
sys.exit(1 if problemy else 0)
