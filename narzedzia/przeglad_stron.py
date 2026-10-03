"""Przegląd wszystkich stron Warsztatu w przeglądarce (ETAP 118).

Otwiera każdą stronę HTML (lista z tablicy tras Flaska + strony z
parametrami na danych testowych) na szerokości telefonu (390 px, tryb
ciemny) i komputera (1300 px, jasny). Zgłasza: kod HTTP ≥ 400, błędy
JavaScript, przewijanie poziome strony. Sieć zewnętrzna jest odcięta.

Wymaga Playwright z Chromium — narzędzie dla autora, nie część aplikacji
(nie ma go w requirements.txt):
    pip install playwright && playwright install chromium
    python narzedzia/przeglad_stron.py
Ścieżkę do Chromium można podać w zmiennej CHROMIUM. Zmienna ZRZUTY=katalog
zapisuje zrzut każdej strony (np. ZRZUTY=/tmp/zrzuty) — do przejrzenia oczami.
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
from dane import bdl
from przepisy import routes as przepisy_routes
from test_ceny import plik_rcn, lokal, geometria_gpkg, dodaj_dzialki, dzialka
from test_przepisy import STRONY as STRONY_AKTU
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


def pdf_z_tekstem(tekst: bytes) -> bytes:
    """Najmniejszy poprawny PDF z jedną linią tekstu — pdf.js go narysuje (ETAP 148)."""
    obiekty = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"]
    strumien = b"BT /F1 18 Tf 20 100 Td (" + tekst + b") Tj ET"
    obiekty += [b"<< /Length %d >>\nstream\n" % len(strumien) + strumien + b"\nendstream", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    wynik, przesuniecia = b"%PDF-1.4\n", []
    for i, o in enumerate(obiekty, 1):
        przesuniecia.append(len(wynik))
        wynik += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(wynik)
    wynik += b"xref\n0 %d\n0000000000 65535 f \n" % (len(obiekty) + 1) + b"".join(b"%010d 00000 n \n" % x for x in przesuniecia)
    return wynik + b"trailer << /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(obiekty) + 1, xref)


# ETAP 148: dane także dla stron z ETAPów 120–147 — fiszki (w tym z luką),
# akt z notatką, raport miast GUS (usługa podmieniona), wyszukiwarka z wynikami
import io  # noqa: E402
c.post("/fiszki/upload", data={"plik": (io.BytesIO(pdf_z_tekstem(b"Plan miejscowy jest aktem prawa miejscowego")), "wyklad.pdf")}, content_type="multipart/form-data")
c.post("/fiszki/1/luki", json={"strona": 1, "fragment_tekstu": "Plan miejscowy", "tekst": "Plan [[miejscowy]] jest aktem prawa"})
przepisy_routes.strony_z_pdf = lambda sciezka: STRONY_AKTU
c.post("/przepisy/akty", data={"plik": (io.BytesIO(b"%PDF-1.4 atrapa"), "ustawa.pdf")}, content_type="multipart/form-data")
c.put("/przepisy/jednostki/4/notatka", json={"tekst": "Notatka do kolokwium:\nintensywność zabudowy."})
bdl.pobierz_zmienna = lambda zid: bdl.Zmienna(zid, "Mediana cen za 1 m2 lokali mieszkalnych", "zł")
bdl.szereg_gminy = lambda zid, jid: [{"rok": r, "wartosc": 6000 + 400 * (r - 2015) + int(jid[-4:]) % 900} for r in range(2015, 2025)]
c.put("/ceny/zmienna", json={"id": 633})
c.put("/ceny/zmienna", json={"id": 64428, "rodzaj": "wynagrodzenie"})
# ETAP 160: strony z ETAPów 151–159 — porównanie inwentaryzacji, druk przepisów,
# koszty koncepcji, fiszka z wycinkiem rysunku
from test_fiszki_obrazy import png, data_url  # noqa: E402
c.post("/teren/projekty/1/podobny")
with app.app_context():
    from teren import baza as baza_terenu
    for projekt, przesuniecie in ((1, 0.0), (2, 0.00003)):
        baza_terenu.zapisz_punkty(projekt, [{"uid": f"p{projekt}{i:05d}", "lat": 52.40 + i * 0.0003 + przesuniecie, "lng": 16.90, "dokladnosc_m": 4,
                                             "czas": f"202{4 + projekt}-05-01T10:{i:02d}", "wartosci": {}, "uwagi": "", "zdjecie": None} for i in range(6)])
c.post("/fiszki/1/fiszki", json={"strona": 1, "fragment_tekstu": "[wycinek rysunku, s. 1]", "pytanie": "Co to za schemat?", "odpowiedz": "Plan", "obraz": data_url(png())})
c.put("/osiedle/koncepcje/1", json={"geojson": {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"funkcja": "obszar"}, "geometry": {"type": "Polygon", "coordinates": [[[16.9, 52.4], [16.902, 52.4], [16.902, 52.401], [16.9, 52.401], [16.9, 52.4]]]}},
    {"type": "Feature", "properties": {"funkcja": "MW", "zabudowa_proc": 30, "kondygnacje": 5}, "geometry": {"type": "Polygon", "coordinates": [[[16.9, 52.4], [16.901, 52.4], [16.901, 52.4005], [16.9, 52.4005], [16.9, 52.4]]]}}]},
    "ustawienia": {"koszty": {"budowa_mw": 6500, "grunt": 900}}})
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
    // ETAP 227: ARIA — to, czego czytnik ekranu nie ogłosi albo przeczyta jako symbol
    if (!document.querySelector("main")) p.push("brak <main>");
    if (document.querySelectorAll("h1").length !== 1) p.push(`h1: ${document.querySelectorAll("h1").length}`);
    let poziom = 1;
    for (const h of document.querySelectorAll("h1, h2, h3, h4, h5, h6")) {
        const n = Number(h.tagName[1]);
        // tylko informacja: WCAG nie wymaga kolejnych poziomów (porządkowanie — ETAP 249)
        if (n > poziom + 1) p.push(`info: nagłówek h${n} po h${poziom}: ${h.textContent.trim().slice(0, 30)}`);
        poziom = n;
    }
    for (const e of document.querySelectorAll("button, a[href]")) {
        if (!widoczny(e) || nazwa(e)) continue;
        const t = e.textContent.trim();
        if (t && !/[\p{L}\p{N}]/u.test(t)) p.push(`${e.tagName.toLowerCase()} z samym symbolem „${t}”: ${e.id || e.className}`);
    }
    for (const e of document.querySelectorAll(".komunikat, [id*=komunikat], [id*=blad]")) {
        if (e.closest("[aria-live], [role=status], [role=alert]")) continue;
        if (e.matches("input, select, textarea, button, label, template")) continue;
        p.push("komunikat bez aria-live: " + (e.id || e.className));
    }
    for (const e of document.querySelectorAll("svg")) {
        if (!widoczny(e) || e.closest("button, a, [aria-hidden=true], .leaflet-container")) continue;
        if (e.getBBox && (e.getBoundingClientRect().width < 40)) continue;  // ikonki
        const opisany = e.closest("[role=img][aria-label]") || (e.getAttribute("role") === "img" && (nazwa(e) || e.querySelector("title")));
        if (!opisany) p.push("svg bez role=img i opisu: " + (e.id || e.parentElement.id || e.parentElement.className));
    }
    for (const e of document.querySelectorAll("input:not([type=hidden]), select, textarea")) {
        if (!widoczny(e)) continue;
        const etykieta = e.closest("label") || (e.id && document.querySelector(`label[for="${e.id}"]`));
        if (!etykieta && !nazwa(e) && e.getAttribute("placeholder")) p.push("pole opisane tylko placeholderem: " + (e.id || e.name));
    }
    for (const e of document.querySelectorAll("[aria-hidden=true] a[href], [aria-hidden=true] button, [aria-hidden=true] input")) p.push("fokusowalny w aria-hidden: " + (e.id || e.className));
    return p;
}"""

WYMAGAJA_PARAMETROW = ("/dostepnosc/raport", "/dostepnosc/raport-dzielnic", "/mpzp/raport", "/ceny/raport", "/teren/porownanie", "/atlas/gminy-w-czasie")  # ?plik=, ?id= — z parametrami niżej
POMIN = ("favicon.ico", ".csv", ".json", ".svg", ".geojson", ".ics", ".txt", ".html", "/static", "/plik", "/telefon")
STRONY = sorted({r.rule for r in app.url_map.iter_rules() if "GET" in r.methods and not r.arguments and not r.rule.endswith(POMIN) and "static" not in r.endpoint and r.rule not in WYMAGAJA_PARAMETROW})
STRONY += ["/teren/projekty/1", "/teren/projekty/1/raport", "/osiedle/koncepcje/1/raport", "/ceny/transakcje?plik=1", "/ceny/transakcje?plik=1&co=dzialki",
           "/ceny/transakcje/1/raport", "/ceny/transakcje/1/raport?co=dzialki", "/ceny/transakcje/1/wycena?lat=50.06&lng=19.94&pow=50&promien=1000&tolerancja=0.2",
           "/fiszki/1/", "/przepisy/akty/1", "/osiedle/?koncepcja=1", "/szukaj?q=plan", "/szukaj?q=centrum",
           "/ceny/raport?id=011212161000&nazwa=Kraków&id=023216264000&nazwa=Wrocław — miasto na prawach powiatu",
           "/teren/porownanie?a=1&b=2", "/przepisy/akty/1/druk?notatki=1", "/przepisy/akty/1/druk?j=2&j=4", "/fiszki/powtorka", "/fiszki/druk",
           "/teren/projekty/1/raport?krzyz_a=stan&krzyz_b=obiekt",
           "/dostepnosc/raport?plik=przyklad_poznan_syntetyczny.csv&kolumna=czas_szkola_min",
           "/dostepnosc/raport-dzielnic?plik=przyklad_poznan_syntetyczny.csv&kolumna=czas_szkola_min"]
srv = make_server("127.0.0.1", 5218, app, threaded=True); threading.Thread(target=srv.serve_forever, daemon=True).start()
problemy = informacje = 0
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
            if os.environ.get("ZRZUTY"):
                os.makedirs(os.environ["ZRZUTY"], exist_ok=True)
                nazwa = "".join(z if z.isalnum() else "_" for z in adres.strip("/"))[:80] or "glowna"
                pg.screenshot(path=os.path.join(os.environ["ZRZUTY"], f"{szer}_{nazwa}.png"), full_page=True)
            sw = pg.evaluate("document.documentElement.scrollWidth")
            winni = pg.evaluate("[...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('nav, .leaflet-container, [class*=przewijanie], [class*=wrap], .zlozony__przewijanie, table')).slice(0,3).map(e => e.tagName + '.' + e.className)")
            # ETAP 130: podstawowa dostępność — tylko na jednej szerokości (wynik ten sam)
            dostepnosc = pg.evaluate(SPRAWDZ_DOSTEPNOSC) if szer == 1300 else []
            informacje += sum(1 for x in dostepnosc if x.startswith("info:"))
            dostepnosc = [x for x in dostepnosc if not x.startswith("info:")]
            if dostepnosc:
                problemy += 1
                print("dostępność", adres, dostepnosc[:int(os.environ.get("ILE", 6))])
            if odp.status >= 400 or bledy or sw > szer:
                problemy += 1
                print(szer, adres, odp.status, "| szer:", sw, winni, "| bledy:", bledy)
            pg.close()
        ctx.close()
    b.close()
srv.shutdown()
print("stron:", len(STRONY), "| problemów:", problemy, "| informacji (kolejność nagłówków):", informacje)
sys.exit(1 if problemy else 0)
