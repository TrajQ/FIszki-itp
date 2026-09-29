// Moduł osiedle: rysowanie koncepcji na mapie (Leaflet.draw) i bilans terenu.
// Bilans liczy serwer (osiedle/bilans.py) po każdym zapisie rysunku;
// tu tylko rysujemy, zapisujemy i wyświetlamy wynik.
(function () {
    "use strict";

    const wyborKoncepcji = document.getElementById("wybor-koncepcji");
    const formularzNowej = document.getElementById("formularz-nowej");
    const nazwaNowej = document.getElementById("nazwa-nowej");
    const akcjeKoncepcji = document.getElementById("akcje-koncepcji");
    const komunikat = document.getElementById("komunikat");
    const linkGeojson = document.getElementById("link-geojson");
    const sekcjaRysowania = document.getElementById("sekcja-rysowania");
    const sekcjaBilansu = document.getElementById("sekcja-bilansu");
    const wybranyTerenEl = document.getElementById("wybrany-teren");
    const funkcjaTerenu = document.getElementById("funkcja-terenu");
    const stanZapisu = document.getElementById("stan-zapisu");
    const formatM2 = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 });
    const formatProc = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });

    let koncepcja = null; // {id, nazwa, geojson, ustawienia}
    let wybranaWarstwa = null;
    let numerZapisu = 0;
    let opoznienieZapisu = null;

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function pokazKomunikat(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    async function zapytaj(url, opcje = {}) {
        const odpowiedz = await fetch(url, {
            ...opcje,
            headers: opcje.body ? { "Content-Type": "application/json" } : undefined,
        });
        const dane = await odpowiedz.json().catch(() => ({}));
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        return dane;
    }

    // ---------- mapa i podkłady ----------

    const mapa = L.map("mapa-osiedla").setView([52.4064, 16.9252], 15);
    // OSM wymaga nagłówka Referer (zob. D-041) — łagodniejsza polityka tylko dla kafelków.
    const PODKLADY = {
        "Mapa (OpenStreetMap)": L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap",
            maxZoom: 19,
            referrerPolicy: "strict-origin-when-cross-origin",
        }),
        "Ortofotomapa (GUGiK)": L.tileLayer.wms("https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution", {
            layers: "Raster",
            format: "image/jpeg",
            version: "1.3.0",
            attribution: "ortofotomapa: GUGiK",
            maxZoom: 20,
        }),
        "Bez podkładu": L.layerGroup(),
    };
    PODKLADY["Mapa (OpenStreetMap)"].addTo(mapa);
    L.control.layers(PODKLADY, {}, { position: "topright" }).addTo(mapa);

    // ---------- rysowanie (Leaflet.draw) ----------

    // Polskie napisy narzędzi rysowania.
    Object.assign(L.drawLocal.draw.toolbar.buttons, {
        polygon: "Rysuj wielobok",
        rectangle: "Rysuj prostokąt",
    });
    Object.assign(L.drawLocal.draw.toolbar.actions, { title: "Przerwij rysowanie", text: "Anuluj" });
    Object.assign(L.drawLocal.draw.toolbar.finish, { title: "Zakończ rysowanie", text: "Zakończ" });
    Object.assign(L.drawLocal.draw.toolbar.undo, { title: "Usuń ostatni punkt", text: "Cofnij punkt" });
    L.drawLocal.draw.handlers.polygon.tooltip = {
        start: "Kliknij, żeby zacząć wielobok.",
        cont: "Klikaj kolejne wierzchołki.",
        end: "Kliknij pierwszy punkt, żeby zamknąć.",
    };
    L.drawLocal.draw.handlers.rectangle.tooltip.start = "Kliknij i przeciągnij, żeby narysować prostokąt.";
    L.drawLocal.draw.handlers.simpleshape.tooltip.end = "Puść przycisk, żeby zakończyć.";
    Object.assign(L.drawLocal.edit.toolbar.buttons, {
        edit: "Edytuj kształty",
        editDisabled: "Brak kształtów do edycji",
        remove: "Usuń kształty",
        removeDisabled: "Brak kształtów do usunięcia",
    });
    Object.assign(L.drawLocal.edit.toolbar.actions.save, { title: "Zapisz zmiany", text: "Zapisz" });
    Object.assign(L.drawLocal.edit.toolbar.actions.cancel, { title: "Cofnij zmiany", text: "Anuluj" });
    Object.assign(L.drawLocal.edit.toolbar.actions.clearAll, { title: "Usuń wszystko", text: "Usuń wszystko" });
    L.drawLocal.edit.handlers.edit.tooltip = { text: "Przeciągaj wierzchołki, żeby zmienić kształt.", subtext: "Anuluj cofa zmiany." };
    L.drawLocal.edit.handlers.remove.tooltip = { text: "Kliknij kształt, żeby go usunąć." };

    const rysunek = new L.FeatureGroup().addTo(mapa);
    // showArea: false — pole liczy serwer; poza tym w wersji 1.0.4 włączone
    // showArea rzuca błąd z nowszym Leafletem.
    const kontrolkaRysowania = new L.Control.Draw({
        position: "topleft",
        draw: {
            polygon: { allowIntersection: false, showArea: false, shapeOptions: { color: "#0071e3" } },
            rectangle: { showArea: false, shapeOptions: { color: "#0071e3" } },
            polyline: false,
            circle: false,
            circlemarker: false,
            marker: false,
        },
        edit: { featureGroup: rysunek },
    });

    function funkcjaDoRysowania() {
        return document.querySelector("input[name=funkcja]:checked").value;
    }

    function styl(funkcja, wybrany) {
        if (funkcja === OBSZAR) {
            return { color: "#1d1d1f", weight: wybrany ? 4 : 2.5, dashArray: "8 6", fill: false };
        }
        const kolor = (FUNKCJE[funkcja] || {}).kolor || "#8e8e93";
        return { color: wybrany ? "#1d1d1f" : kolor, weight: wybrany ? 3 : 1.5, fillColor: kolor, fillOpacity: 0.55, fill: true };
    }

    function przygotujWarstwe(warstwa, funkcja) {
        warstwa.funkcja = funkcja;
        warstwa.setStyle(styl(funkcja, false));
        warstwa.on("click", (e) => {
            L.DomEvent.stopPropagation(e);
            zaznacz(warstwa);
        });
        // Obszar opracowania pod spodem — żeby dało się klikać tereny w środku.
        if (funkcja === OBSZAR) warstwa.bringToBack();
        rysunek.addLayer(warstwa);
    }

    function zaznacz(warstwa) {
        if (wybranaWarstwa) wybranaWarstwa.setStyle(styl(wybranaWarstwa.funkcja, false));
        wybranaWarstwa = warstwa;
        wybranyTerenEl.hidden = !warstwa;
        if (!warstwa) return;
        warstwa.setStyle(styl(warstwa.funkcja, true));
        funkcjaTerenu.value = warstwa.funkcja;
    }

    mapa.on("click", () => zaznacz(null));

    mapa.on(L.Draw.Event.CREATED, (e) => {
        const funkcja = funkcjaDoRysowania();
        // Obszar opracowania jest jeden — nowy zastępuje stary.
        if (funkcja === OBSZAR) {
            rysunek.eachLayer((w) => {
                if (w.funkcja === OBSZAR) rysunek.removeLayer(w);
            });
        }
        przygotujWarstwe(e.layer, funkcja);
        zapiszRysunek();
    });
    mapa.on(L.Draw.Event.EDITED, zapiszRysunek);
    mapa.on(L.Draw.Event.DELETED, () => {
        zaznacz(null);
        zapiszRysunek();
    });

    funkcjaTerenu.addEventListener("change", () => {
        if (!wybranaWarstwa) return;
        wybranaWarstwa.funkcja = funkcjaTerenu.value;
        wybranaWarstwa.setStyle(styl(wybranaWarstwa.funkcja, true));
        zapiszRysunek();
    });
    document.getElementById("usun-teren").addEventListener("click", () => {
        if (!wybranaWarstwa) return;
        rysunek.removeLayer(wybranaWarstwa);
        zaznacz(null);
        zapiszRysunek();
    });
    document.getElementById("odznacz-teren").addEventListener("click", () => zaznacz(null));

    function rysunekGeojson() {
        const cechy = [];
        rysunek.eachLayer((w) => {
            const cecha = w.toGeoJSON();
            cecha.properties = { ...(w.wlasciwosci || {}), funkcja: w.funkcja };
            cechy.push(cecha);
        });
        return { type: "FeatureCollection", features: cechy };
    }

    // Zapis po krótkiej przerwie (kilka zmian pod rząd = jeden zapis);
    // numer zapisu chroni przed pokazaniem bilansu ze starszej odpowiedzi.
    function zapiszRysunek() {
        if (!koncepcja) return;
        stanZapisu.textContent = "Zapisuję…";
        clearTimeout(opoznienieZapisu);
        opoznienieZapisu = setTimeout(async () => {
            const numer = ++numerZapisu;
            try {
                const dane = await zapytaj(`${URL_KONCEPCJE}/${koncepcja.id}`, {
                    method: "PUT",
                    body: JSON.stringify({ geojson: rysunekGeojson() }),
                });
                if (numer !== numerZapisu) return;
                pokazKomunikat("");
                stanZapisu.textContent = "Zapisano";
                pokazBilans(dane.bilans);
            } catch (e) {
                if (numer === numerZapisu) {
                    stanZapisu.textContent = "Nie zapisano";
                    pokazKomunikat(e.message);
                }
            }
        }, 300);
    }

    // ---------- bilans ----------

    function pokazBilans(b) {
        sekcjaBilansu.hidden = false;
        const tabela = document.getElementById("tabela-bilansu");
        const pasek = document.getElementById("pasek-bilansu");
        tabela.replaceChildren();
        pasek.replaceChildren();
        for (const f of b.funkcje) {
            const tr = element("tr");
            const nazwa = element("td");
            const probka = element("span", "funkcja__probka");
            probka.style.background = f.kolor;
            nazwa.append(probka, element("strong", "", ` ${f.funkcja} `), f.nazwa);
            tr.append(nazwa, element("td", "liczba", formatM2.format(f.powierzchnia_m2)), element("td", "liczba", f.procent === null ? "—" : formatProc.format(f.procent)));
            tabela.appendChild(tr);
            if (f.procent) {
                const kawalek = element("span");
                kawalek.style.flex = String(f.procent);
                kawalek.style.background = f.kolor;
                kawalek.title = `${f.funkcja}: ${formatProc.format(f.procent)}%`;
                pasek.appendChild(kawalek);
            }
        }
        const k = b.kontrole;
        if (k.niezagospodarowane_m2) {
            const tr = element("tr", "wyciszony");
            tr.append(element("td", "", "bez funkcji (w obszarze)"), element("td", "liczba", formatM2.format(k.niezagospodarowane_m2)), element("td", "liczba", formatProc.format(k.niezagospodarowane_proc)));
            tabela.appendChild(tr);
            const reszta = element("span", "pasek-bilansu__reszta");
            reszta.style.flex = String(k.niezagospodarowane_proc);
            pasek.appendChild(reszta);
        }
        const razem = element("tr", "tabela-bilansu__razem");
        razem.append(
            element("td", "", b.obszar_m2 !== null ? "obszar opracowania" : "razem (bez obszaru opracowania)"),
            element("td", "liczba", formatM2.format(b.obszar_m2 ?? b.razem_m2)),
            element("td", "liczba", b.obszar_m2 !== null || b.razem_m2 ? "100" : "—")
        );
        tabela.appendChild(razem);

        const kontrole = document.getElementById("kontrole");
        kontrole.replaceChildren();
        const uwaga = (tekst) => kontrole.appendChild(element("li", "", tekst));
        if (b.obszar_m2 === null && b.funkcje.length) uwaga("Narysuj obszar opracowania — procenty będą liczone od niego.");
        if (k.nakladanie_m2 >= 1) uwaga(`Tereny nakładają się na ${formatM2.format(k.nakladanie_m2)} m² — bilans liczy tę część podwójnie.`);
        if (k.poza_obszarem_m2 >= 1) uwaga(`${formatM2.format(k.poza_obszarem_m2)} m² terenów leży poza obszarem opracowania.`);
        if (!b.funkcje.length && b.obszar_m2 === null) uwaga("Jeszcze nic nie narysowano.");
    }

    // ---------- koncepcje ----------

    async function wczytajListe(wybierzId) {
        const lista = await zapytaj(URL_KONCEPCJE);
        wyborKoncepcji.replaceChildren(new Option(lista.length ? "— wybierz koncepcję —" : "— brak koncepcji, utwórz nową —", ""));
        for (const k of lista) wyborKoncepcji.appendChild(new Option(k.nazwa, String(k.id)));
        if (wybierzId) {
            wyborKoncepcji.value = String(wybierzId);
            await otworz(wybierzId);
        }
    }

    async function otworz(id) {
        zaznacz(null);
        rysunek.clearLayers();
        pokazKomunikat("");
        if (!id) {
            koncepcja = null;
            mapa.removeControl(kontrolkaRysowania);
            [sekcjaRysowania, sekcjaBilansu, akcjeKoncepcji, linkGeojson].forEach((el) => (el.hidden = true));
            return;
        }
        const dane = await zapytaj(`${URL_KONCEPCJE}/${id}`);
        koncepcja = dane;
        try {
            localStorage.setItem("osiedle.ostatnia", String(id));
        } catch (e) {
            // zapamiętanie ostatniej koncepcji to tylko wygoda
        }
        L.geoJSON(dane.geojson, {
            onEachFeature: (cecha, warstwa) => {
                warstwa.wlasciwosci = { ...cecha.properties };
                delete warstwa.wlasciwosci.funkcja;
                przygotujWarstwe(warstwa, cecha.properties.funkcja);
            },
        });
        kontrolkaRysowania.addTo(mapa);
        [sekcjaRysowania, akcjeKoncepcji, linkGeojson].forEach((el) => (el.hidden = false));
        linkGeojson.href = `${URL_KONCEPCJE}/${id}.geojson`;
        stanZapisu.textContent = "";
        pokazBilans(dane.bilans);
        if (rysunek.getLayers().length) mapa.fitBounds(rysunek.getBounds(), { padding: [30, 30], maxZoom: 18 });
    }

    wyborKoncepcji.addEventListener("change", () => otworz(wyborKoncepcji.value).catch((e) => pokazKomunikat(e.message)));

    formularzNowej.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
            const nowa = await zapytaj(URL_KONCEPCJE, { method: "POST", body: JSON.stringify({ nazwa: nazwaNowej.value }) });
            nazwaNowej.value = "";
            await wczytajListe(nowa.id);
        } catch (err) {
            pokazKomunikat(err.message);
        }
    });

    document.getElementById("zmien-nazwe").addEventListener("click", async () => {
        if (!koncepcja) return;
        const nazwa = window.prompt("Nowa nazwa koncepcji:", koncepcja.nazwa);
        if (nazwa === null) return;
        try {
            await zapytaj(`${URL_KONCEPCJE}/${koncepcja.id}`, { method: "PUT", body: JSON.stringify({ nazwa }) });
            await wczytajListe(koncepcja.id);
        } catch (err) {
            pokazKomunikat(err.message);
        }
    });

    document.getElementById("usun-koncepcje").addEventListener("click", async () => {
        if (!koncepcja || !window.confirm(`Usunąć koncepcję „${koncepcja.nazwa}” razem z rysunkiem?`)) return;
        try {
            await zapytaj(`${URL_KONCEPCJE}/${koncepcja.id}`, { method: "DELETE" });
            await otworz("");
            await wczytajListe();
        } catch (err) {
            pokazKomunikat(err.message);
        }
    });

    let ostatnia = null;
    try {
        ostatnia = localStorage.getItem("osiedle.ostatnia");
    } catch (e) {
        // bez localStorage zaczynamy od listy
    }
    wczytajListe(ostatnia).catch(() => wczytajListe().catch((e) => pokazKomunikat(e.message)));
})();
