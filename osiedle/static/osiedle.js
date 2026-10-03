// Moduł osiedle: rysowanie koncepcji na mapie (Leaflet.draw) i bilans terenu.
// Bilans i wskaźniki liczy serwer (osiedle/bilans.py, wskazniki.py) po
// każdym zapisie; tu tylko rysujemy, zapisujemy i wyświetlamy wynik.
(function () {
    "use strict";

    const wyborKoncepcji = document.getElementById("wybor-koncepcji");
    const formularzNowej = document.getElementById("formularz-nowej");
    const nazwaNowej = document.getElementById("nazwa-nowej");
    const akcjeKoncepcji = document.getElementById("akcje-koncepcji");
    const komunikat = document.getElementById("komunikat");
    const linkiKoncepcji = document.getElementById("linki-koncepcji");
    const linkGeojson = document.getElementById("link-geojson");
    const linkRaport = document.getElementById("link-raport");
    const warstwaTerenuEl = document.getElementById("warstwa-terenu");
    const sekcjaRysowania = document.getElementById("sekcja-rysowania");
    const sekcjaBilansu = document.getElementById("sekcja-bilansu");
    const wybranyTerenEl = document.getElementById("wybrany-teren");
    const funkcjaTerenu = document.getElementById("funkcja-terenu");
    const stanZapisu = document.getElementById("stan-zapisu");
    const sekcjaWskaznikow = document.getElementById("sekcja-wskaznikow");
    const polaParametrow = document.querySelectorAll("#parametry-terenu [data-parametr]");
    const polaUstalen = document.querySelectorAll("[data-ustalenie]");
    const polaZalozen = document.querySelectorAll("[data-zalozenie]");
    const polaStawek = document.querySelectorAll("[data-stawka]"); // ETAP 155
    const sekcjaProgramu = document.getElementById("sekcja-programu");
    const sekcjaCienia = document.getElementById("sekcja-cienia");
    const sekcjaCen = document.getElementById("sekcja-cen");
    const formatWsk = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 });
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
            headers: typeof opcje.body === "string" ? { "Content-Type": "application/json" } : undefined, // FormData: nagłówek ustawia przeglądarka
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
    const kontrolkaWarstw = L.control.layers(PODKLADY, {}, { position: "topright" }).addTo(mapa);

    // Plany miejscowe i działki pod rysunkiem (ETAP 81) — te same nakładki
    // krajowych integracji GUGiK co w module MPZP (jego trasa podaje nazwy
    // warstw z opisu usługi). Rysunek koncepcji leży zawsze nad nimi.
    // Włączone nakładki zapamiętujemy w przeglądarce.
    function nakladkaWms(opis, przezroczystosc) {
        return L.tileLayer.wms(opis.url, {
            layers: opis.warstwy,
            format: "image/png",
            transparent: true,
            version: "1.3.0",
            opacity: przezroczystosc,
            maxZoom: 20,
            attribution: "plany i działki: GUGiK",
            ...(opis.mercator === false ? { crs: L.CRS.EPSG4326 } : {}),
        });
    }

    function zapamietaneNakladki() {
        try {
            return JSON.parse(localStorage.getItem("osiedle.nakladki") || "[]");
        } catch (e) {
            return [];
        }
    }

    // Nakładki GUGiK; włączone zapamiętujemy w przeglądarce.
    const nakladki = {};
    const wlaczoneNakladki = zapamietaneNakladki();

    function dodajNakladke(nazwa, warstwa) {
        nakladki[nazwa] = warstwa;
        kontrolkaWarstw.addOverlay(warstwa, nazwa);
        if (wlaczoneNakladki.includes(nazwa)) warstwa.addTo(mapa);
    }

    mapa.on("overlayadd overlayremove", () => {
        const teraz = Object.entries(nakladki).filter(([, w]) => mapa.hasLayer(w)).map(([n]) => n);
        try {
            localStorage.setItem("osiedle.nakladki", JSON.stringify(teraz));
        } catch (e) {
            // tylko wygoda
        }
    });

    fetch(URL_WARSTWY_KRAJOWE)
        .then((odpowiedz) => odpowiedz.json())
        .then((dane) => {
            dodajNakladke("Plan miejscowy (GUGiK)", nakladkaWms(dane.plany, 0.55));
            dodajNakladke("Działki ewidencyjne (GUGiK)", nakladkaWms(dane.dzialki, 1));
        })
        .catch(() => {}); // bez nakładek rysowanie działa jak dotąd

    // ETAP 89: plan ogólny gminy — tylko gdy usługa odpowie.
    fetch(URL_PLAN_OGOLNY)
        .then((odpowiedz) => (odpowiedz.ok ? odpowiedz.json() : Promise.reject()))
        .then((opis) => dodajNakladke("Plan ogólny gminy (GUGiK)", nakladkaWms(opis, 0.55)))
        .catch(() => {});

    // ---------- rysowanie (Leaflet.draw) ----------

    // Polskie napisy narzędzi rysowania.
    Object.assign(L.drawLocal.draw.toolbar.buttons, {
        polygon: "Rysuj wielobok",
        rectangle: "Rysuj prostokąt",
        polyline: "Rysuj nieprzekraczalną linię zabudowy",
    });
    Object.assign(L.drawLocal.draw.toolbar.actions, { title: "Przerwij rysowanie", text: "Anuluj" });
    Object.assign(L.drawLocal.draw.toolbar.finish, { title: "Zakończ rysowanie", text: "Zakończ" });
    Object.assign(L.drawLocal.draw.toolbar.undo, { title: "Usuń ostatni punkt", text: "Cofnij punkt" });
    L.drawLocal.draw.handlers.polygon.tooltip = {
        start: "Kliknij, żeby zacząć wielobok.",
        cont: "Klikaj kolejne wierzchołki.",
        end: "Kliknij pierwszy punkt, żeby zamknąć.",
    };
    L.drawLocal.draw.handlers.polyline.tooltip = {
        start: "Kliknij, żeby zacząć linię zabudowy.",
        cont: "Klikaj kolejne punkty linii.",
        end: "Kliknij ostatni punkt jeszcze raz albo „Zakończ”.",
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
            // ETAP 175: łamana — tylko nieprzekraczalna linia zabudowy
            polyline: { shapeOptions: { color: KOLOR_LINII, weight: 3 } },
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
        if (funkcja === LINIA) {
            return { color: KOLOR_LINII, weight: wybrany ? 5 : 3, dashArray: "10 4 2 4", fill: false };
        }
        if (funkcja === BUDYNEK) {
            return { color: wybrany ? "#0071e3" : "#ffffff", weight: wybrany ? 3 : 1.5, fillColor: KOLOR_BUDYNKU, fillOpacity: 0.85, fill: true };
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
        rysunek.addLayer(warstwa);
        ulozWarstwy();
    }

    // Obszar pod spodem, nad terenami budynki (ETAP 173), na samej górze linie zabudowy (ETAP 175)
    function ulozWarstwy() {
        for (const [funkcja, naWierzch] of [[OBSZAR, false], [BUDYNEK, true], [LINIA, true]]) {
            rysunek.eachLayer((w) => {
                if (w.funkcja === funkcja) naWierzch ? w.bringToFront() : w.bringToBack();
            });
        }
    }

    function zaznacz(warstwa) {
        if (wybranaWarstwa) wybranaWarstwa.setStyle(styl(wybranaWarstwa.funkcja, false));
        wybranaWarstwa = warstwa;
        wybranyTerenEl.hidden = !warstwa;
        if (!warstwa) return;
        warstwa.setStyle(styl(warstwa.funkcja, true));
        funkcjaTerenu.value = warstwa.funkcja;
        funkcjaTerenu.disabled = warstwa.funkcja === LINIA; // linia nie może stać się wielobokiem (ETAP 175)
        pokazParametry(warstwa);
    }

    // Pola parametrów zaznaczonego terenu: tylko te, które funkcja ma
    // (zabudowa i kondygnacje — MN, MW, U); podpowiedź = wartość typowa.
    function pokazParametry(warstwa) {
        const domyslne = DOMYSLNE[warstwa.funkcja] || {};
        const wlasciwosci = warstwa.wlasciwosci || {};
        polaParametrow.forEach((etykieta) => {
            const klucz = etykieta.dataset.parametr;
            const pole = etykieta.querySelector("input");
            etykieta.hidden = !(klucz in domyslne);
            pole.placeholder = klucz in domyslne ? String(domyslne[klucz]) : "";
            pole.value = wlasciwosci[klucz] ?? "";
        });
        // ETAP 196: etap realizacji — tylko tereny z funkcją (nie obszar, budynek, linia)
        etapTerenu.hidden = !(warstwa.funkcja in DOMYSLNE);
        etapTerenu.querySelector("input").value = wlasciwosci.etap ?? "";
    }

    const etapTerenu = document.getElementById("etap-terenu");
    etapTerenu.querySelector("input").addEventListener("input", (e) => {
        if (!wybranaWarstwa) return;
        wybranaWarstwa.wlasciwosci = { ...(wybranaWarstwa.wlasciwosci || {}) };
        if (e.target.value === "") delete wybranaWarstwa.wlasciwosci.etap;
        else wybranaWarstwa.wlasciwosci.etap = Number(e.target.value);
        zapiszRysunek();
    });

    polaParametrow.forEach((etykieta) => {
        etykieta.querySelector("input").addEventListener("input", (e) => {
            if (!wybranaWarstwa) return;
            const klucz = etykieta.dataset.parametr;
            wybranaWarstwa.wlasciwosci = { ...(wybranaWarstwa.wlasciwosci || {}) };
            if (e.target.value === "") delete wybranaWarstwa.wlasciwosci[klucz];
            else wybranaWarstwa.wlasciwosci[klucz] = Number(e.target.value);
            zapiszRysunek();
        });
    });
    polaUstalen.forEach((pole) => pole.addEventListener("input", zapiszRysunek));
    polaZalozen.forEach((pole) => pole.addEventListener("input", zapiszRysunek));
    polaStawek.forEach((pole) => pole.addEventListener("input", zapiszRysunek));

    // Puste pole = brak wpisu (ustalenie planu: nie obowiązuje; założenie: wartość typowa).
    function wpisane(pola, atrybut) {
        const wynik = {};
        pola.forEach((pole) => {
            if (pole.value !== "") wynik[pole.dataset[atrybut]] = Number(pole.value);
        });
        return wynik;
    }

    function ustawieniaZFormularza() {
        return {
            ...(koncepcja.ustawienia || {}),
            plan: wpisane(polaUstalen, "ustalenie"),
            program: wpisane(polaZalozen, "zalozenie"),
            koszty: wpisane(polaStawek, "stawka"),
            teren_projekt: projektTerenu.value ? Number(projektTerenu.value) : null,
        };
    }

    // ---------- punkty z modułu Teren (ETAP 67) ----------
    // Tylko do podglądu: warstwa poza rysunkiem, nie wchodzi do bilansu.

    const projektTerenu = document.getElementById("projekt-terenu");
    const warstwaTerenu = L.featureGroup().addTo(mapa);
    let numerTerenu = 0;

    function tekstWartosci(w) {
        return w === true ? "tak" : w === false ? "nie" : String(w);
    }

    function dymekTerenu(p) {
        const div = element("div", "dymek-terenu");
        if (p.zdjecie) {
            const img = element("img", "dymek-terenu__zdjecie");
            img.src = p.zdjecie;
            img.alt = "Zdjęcie z terenu";
            div.appendChild(img);
        }
        for (const [nazwa, w] of Object.entries(p.wartosci)) {
            const wiersz = element("div");
            wiersz.append(element("span", "wyciszony", `${nazwa}: `), element("strong", "", tekstWartosci(w)));
            div.appendChild(wiersz);
        }
        if (p.uwagi) div.appendChild(element("p", "", p.uwagi));
        div.appendChild(element("span", "wyciszony", new Date(p.czas).toLocaleDateString("pl-PL")));
        return div;
    }

    async function pokazTeren() {
        const numer = ++numerTerenu;
        warstwaTerenu.clearLayers();
        if (!projektTerenu.value) return;
        try {
            const punkty = await zapytaj(URL_TEREN_PUNKTY.replace(/0\/punkty$/, `${projektTerenu.value}/punkty`));
            if (numer !== numerTerenu) return;
            for (const p of punkty) {
                if (p.lat === null) continue;
                L.circleMarker([p.lat, p.lng], { radius: 6, weight: 2, color: "#ffffff", fillColor: "#1d1d1f", fillOpacity: 0.9 })
                    .bindPopup(() => dymekTerenu(p), { maxWidth: 260 })
                    .addTo(warstwaTerenu);
            }
            warstwaTerenu.bringToFront();
            // Pusta koncepcja: pokaż miejsce inwentaryzacji, żeby od razu rysować w nim.
            if (!rysunek.getLayers().length && warstwaTerenu.getLayers().length) {
                mapa.fitBounds(warstwaTerenu.getBounds(), { padding: [60, 60], maxZoom: 18 });
            }
        } catch (e) {
            pokazKomunikat(`Punkty z terenu: ${e.message}`);
        }
    }

    async function wczytajProjektyTerenu() {
        try {
            const projekty = await zapytaj(URL_TEREN_PROJEKTY);
            for (const p of projekty) projektTerenu.appendChild(new Option(`${p.nazwa} (${p.liczba_punktow} pkt)`, String(p.id)));
        } catch (e) {
            // bez listy projektów wybór zostaje pusty — rysowanie działa dalej
        }
    }

    projektTerenu.addEventListener("change", () => {
        pokazTeren();
        zapiszRysunek();
    });

    mapa.on("click", () => zaznacz(null));

    mapa.on(L.Draw.Event.CREATED, (e) => {
        // łamana to zawsze linia zabudowy; wielobok przy wybranej linii — nie wiadomo, co to jest
        if (e.layerType !== "polyline" && funkcjaDoRysowania() === LINIA) {
            pokazKomunikat("Linię zabudowy rysuj narzędziem łamanej (pierwsza ikona) — wybierz inną funkcję, żeby narysować wielobok.");
            return;
        }
        const funkcja = e.layerType === "polyline" ? LINIA : funkcjaDoRysowania();
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
        ulozWarstwy();
        pokazParametry(wybranaWarstwa);
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

    // Zapis rysunku razem z ustaleniami planu — jedna droga zapisu, więc
    // żadna zmiana nie zgubi się w opóźnieniu drugiej.
    // Zapis po krótkiej przerwie (kilka zmian pod rząd = jeden zapis);
    // numer zapisu chroni przed pokazaniem bilansu ze starszej odpowiedzi.
    function zapiszRysunek() {
        if (!koncepcja) return;
        stanZapisu.textContent = "Zapisuję…";
        clearTimeout(opoznienieZapisu);
        opoznienieZapisu = setTimeout(wyslijZapis, 300);
    }

    // Treść zapisu (koncepcja, rysunek, ustawienia) bierzemy od razu, przy
    // wywołaniu — nie po odpowiedzi serwera. Inaczej przełączenie koncepcji
    // w trakcie zapisu mogłoby wysłać pusty rysunek do poprzedniej (ETAP 66).
    function trescZapisu() {
        return { id: koncepcja.id, body: JSON.stringify({ geojson: rysunekGeojson(), ustawienia: ustawieniaZFormularza() }) };
    }

    async function wyslijZapis() {
        opoznienieZapisu = null;
        if (!koncepcja) return;
        const { id, body } = trescZapisu();
        const numer = ++numerZapisu;
        try {
            const dane = await zapytaj(`${URL_KONCEPCJE}/${id}`, { method: "PUT", body });
            if (numer !== numerZapisu || !koncepcja || koncepcja.id !== id) return;
            koncepcja.ustawienia = dane.ustawienia;
            pokazKomunikat("");
            stanZapisu.textContent = "Zapisano";
            pokazBilans(dane.bilans);
            if (warstwaCienia.getLayers().length) {
                ukryjCien();
                wynikCienia.hidden = false;
                wynikCienia.replaceChildren(element("p", "wyciszony", "Rysunek się zmienił — kliknij „Pokaż”, żeby policzyć cień od nowa."));
            }
        } catch (e) {
            if (numer === numerZapisu) {
                stanZapisu.textContent = "Nie zapisano";
                pokazKomunikat(e.message);
            }
        }
    }

    // Zaległy zapis (czekający na koniec przerwy) wysyłamy od razu —
    // przed przełączeniem koncepcji.
    async function dokonczZapis() {
        if (opoznienieZapisu === null) return;
        clearTimeout(opoznienieZapisu);
        await wyslijZapis();
    }

    // Wyjście ze strony (np. w link „Raport”) w trakcie przerwy przed
    // zapisem: keepalive pozwala zapytaniu dokończyć się po zamknięciu strony.
    window.addEventListener("pagehide", () => {
        if (opoznienieZapisu === null || !koncepcja) return;
        clearTimeout(opoznienieZapisu);
        const { id, body } = trescZapisu();
        fetch(`${URL_KONCEPCJE}/${id}`, { method: "PUT", body, headers: { "Content-Type": "application/json" }, keepalive: true });
    });

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
        if (k.parametry_ponad_100) uwaga(`Terenów, na których zabudowa i powierzchnia biologicznie czynna razem przekraczają 100%: ${k.parametry_ponad_100}.`);
        pokazWskazniki(b);
        pokazProgram(b.program);
        pokazKoszty(b.koszty);
        pokazBudynki(b.budynki);
        pokazEtapy(b.etapy);
        pokazChlonnosc(b.chlonnosc);
    }

    // ETAP 197: chłonność terenu wg wpisanych ustaleń planu (osiedle/chlonnosc.py)
    function pokazChlonnosc(c) {
        const blok = document.getElementById("chlonnosc");
        blok.hidden = !c;
        if (!c) return;
        const pasek = document.getElementById("pasek-chlonnosci");
        pasek.style.width = `${Math.min(100, c.wykorzystanie_proc ?? 0)}%`;
        pasek.classList.toggle("pasek-chlonnosci--ponad", c.zapas_m2 < 0);
        const czesci = [`Plan pozwala na ${formatM2.format(c.maks_calkowita_m2)} m² powierzchni całkowitej (ogranicza: ${c.decyduje}).`,
            `Koncepcja: ${formatM2.format(c.calkowita_m2)} m² — ${formatProc.format(c.wykorzystanie_proc)}% chłonności.`];
        if (c.calkowita_budynkow_m2 !== undefined) czesci.push(`Z budynków: ${formatM2.format(c.calkowita_budynkow_m2)} m² — ${formatProc.format(c.wykorzystanie_budynkow_proc)}%.`);
        czesci.push(c.zapas_m2 >= 0
            ? `Zapas ${formatM2.format(c.zapas_m2)} m²${c.zapas_mieszkan ? ` ≈ ${c.zapas_mieszkan} mieszk. MW` : ""}.`
            : `Przekroczenie o ${formatM2.format(-c.zapas_m2)} m².`);
        if (c.min_calkowita_m2 !== null && c.calkowita_m2 < c.min_calkowita_m2) czesci.push(`Poniżej minimum z planu (${formatM2.format(c.min_calkowita_m2)} m²).`);
        document.getElementById("opis-chlonnosci").textContent = czesci.join(" ");
    }

    // ETAP 196: etapy realizacji — program i koszty liczy serwer (osiedle/etapy.py)
    function pokazEtapy(e) {
        const sekcja = document.getElementById("sekcja-etapow");
        sekcja.hidden = !e;
        if (!e) return;
        const zKosztem = e.lista.some((x) => x.koszt !== null);
        const tabela = document.getElementById("tabela-etapow");
        const naglowek = element("tr");
        ["Etap", "Pow. m²", "Mieszk. (narast.)", ...(zKosztem ? ["Koszt zł", "Narastająco"] : [])].forEach((t, i) => naglowek.appendChild(element("th", i ? "liczba" : "", t)));
        tabela.replaceChildren(naglowek);
        for (const x of e.lista) {
            const tr = element("tr", x.etap === null ? "wyciszony" : "");
            tr.append(element("td", "", x.etap === null ? "bez etapu" : String(x.etap)), element("td", "liczba", formatM2.format(x.powierzchnia_m2)),
                element("td", "liczba", `${x.mieszkania} (${x.mieszkania_narastajaco})`));
            if (zKosztem) tr.append(element("td", "liczba", formatM2.format(x.koszt)), element("td", "liczba", formatM2.format(x.koszt_narastajaco)));
            tabela.appendChild(tr);
        }
        const kontrole = document.getElementById("kontrole-etapow");
        kontrole.replaceChildren();
        for (const x of e.lista) {
            if (x.miejsca_brakuje) kontrole.appendChild(element("li", "", `${x.etap === null ? "Bez etapu" : `Etap ${x.etap}`}: na terenach KS tego etapu brakuje ${x.miejsca_brakuje} miejsc postojowych.`));
        }
        if (e.bez_etapu) kontrole.appendChild(element("li", "", "Część terenów nie ma numeru etapu — są w wierszu „bez etapu”."));
    }

    // ETAP 173: zestawienie budynków — rzut, kondygnacje, powierzchnia całkowita, teren pod budynkiem
    function pokazBudynki(bud) {
        const sekcja = document.getElementById("sekcja-budynkow");
        sekcja.hidden = !bud;
        if (!bud) return;
        document.getElementById("podsumowanie-budynkow").textContent =
            `${bud.liczba} ${bud.liczba === 1 ? "budynek" : bud.liczba < 5 ? "budynki" : "budynków"}: powierzchnia zabudowy ${formatM2.format(bud.zabudowa_m2)} m², całkowita ${formatM2.format(bud.calkowita_m2)} m².`;
        const tabela = document.getElementById("tabela-budynkow");
        const glowa = element("tr");
        glowa.append(element("th", "", "Nr"), element("th", "", "Teren"), element("th", "liczba", "Rzut m²"), element("th", "liczba", "Kond."), element("th", "liczba", "Całkowita m²"));
        if (bud.linii_zabudowy) glowa.append(element("th", "liczba", "Od linii m"));
        tabela.replaceChildren(glowa);
        for (const b of bud.lista) {
            const tr = element("tr");
            tr.append(element("td", "", String(b.nr)), element("td", b.teren ? "" : "wyciszony", b.teren || "—"),
                element("td", "liczba", formatM2.format(b.pole_m2)), element("td", "liczba", String(b.kondygnacje)), element("td", "liczba", formatM2.format(b.calkowita_m2)));
            if (bud.linii_zabudowy) tr.append(element("td", b.przecina_linie ? "liczba stan--zle" : "liczba", b.przecina_linie ? "przecina" : formatWsk.format(b.od_linii_m)));
            tabela.appendChild(tr);
        }
        const kontrole = document.getElementById("kontrole-budynkow");
        kontrole.replaceChildren();
        if (bud.poza_terenem_zabudowy) kontrole.appendChild(element("li", "", `Budynków nie na terenie zabudowy (MN, MW, U): ${bud.poza_terenem_zabudowy}.`));
        if (bud.poza_obszarem) kontrole.appendChild(element("li", "", `Budynków wychodzących poza obszar opracowania: ${bud.poza_obszarem}.`));
        if (bud.przecina_linie) kontrole.appendChild(element("li", "", `Budynków przecinających nieprzekraczalną linię zabudowy: ${bud.przecina_linie}.`));
    }

    // ETAP 164: podpowiedź stawki gruntu — mediana działek niezabudowanych z RCN (moduł Ceny).
    // Nic nie wpisuje się samo: użytkownik widzi liczbę transakcji i lata, i decyduje.
    document.getElementById("podpowiedz-grunt").addEventListener("click", async () => {
        const wynik = document.getElementById("wynik-gruntu");
        let obszar = null;
        rysunek.eachLayer((w) => {
            if (w.funkcja === OBSZAR) obszar = w.toGeoJSON().geometry;
        });
        wynik.hidden = false;
        if (!obszar) return wynik.replaceChildren(element("p", "", "Najpierw narysuj obszar opracowania."));
        wynik.replaceChildren(element("p", "wyciszony", "Szukam w plikach RCN…"));
        try {
            const d = await zapytaj(URL_CENY_OKOLICA, { method: "POST", body: JSON.stringify({ geometria: obszar, promien: 1000, tylko_niezabudowane: true }) });
            const s = d.dzialki;
            if (!d.plik || !s) {
                wynik.replaceChildren(element("p", "", d.pliki_zaimportowane ? "W zaimportowanych plikach RCN nie ma transakcji działek niezabudowanych do 1 km od obszaru." : "Najpierw zaimportuj plik RCN powiatu w module Ceny → Transakcje."));
                return;
            }
            const opis = element("p", "", `Działki niezabudowane do 1 km: mediana ${formatM2.format(s.mediana_m2)} zł/m² (połowa transakcji ${formatM2.format(s.q1_m2)}–${formatM2.format(s.q3_m2)}), ${s.liczba} transakcji z lat ${s.od.slice(0, 4)}–${s.do.slice(0, 4)}, plik ${d.plik.nazwa}.`);
            const wpisz = element("button", "przycisk--drugi", "Wpisz medianę jako stawkę gruntu");
            wpisz.type = "button";
            wpisz.addEventListener("click", () => {
                const pole = document.querySelector('[data-stawka="grunt"]');
                pole.value = Math.round(s.mediana_m2);
                pole.dispatchEvent(new Event("input"));
                document.getElementById("stawki-kosztow").open = true;
            });
            wynik.replaceChildren(opis, element("p", "wyciszony", s.liczba < 5 ? "Mniej niż 5 transakcji — mediana niepewna." : "Ceny z aktów notarialnych; przeznaczenie i stan działek bywają różne."), wpisz);
        } catch (e) {
            wynik.replaceChildren(element("p", "komunikat komunikat--blad", e.message));
        }
    });

    // ETAP 155: szacunek kosztów — ilości × stawki liczy serwer (osiedle/koszty.py)
    function pokazKoszty(k) {
        const sekcja = document.getElementById("sekcja-kosztow");
        const tabela = document.getElementById("tabela-kosztow");
        const podsumowanie = document.getElementById("podsumowanie-kosztow");
        sekcja.hidden = false;
        tabela.hidden = podsumowanie.hidden = !k;
        if (!k) return;
        const wiersz = (komorki, klasa) => {
            const tr = element("tr", klasa);
            komorki.forEach(([tekst, k2]) => tr.appendChild(element("td", k2 || "", tekst)));
            return tr;
        };
        // dwie kolumny (pozycja z „ilość × stawka” pod spodem | koszt) — mieszczą się w wąskim panelu
        tabela.replaceChildren(wiersz([["pozycja"], ["koszt [zł]", "liczba"]], "tabela-kosztow__naglowek"));
        for (const p of k.pozycje) {
            const tr = wiersz([[p.opis], [formatM2.format(p.koszt), "liczba"]]);
            tr.firstChild.appendChild(element("span", "tabela-kosztow__wyliczenie",
                `${formatM2.format(p.ilosc)} ${p.jednostka_ilosci} × ${formatWsk.format(p.stawka)} ${p.jednostka}`));
            tabela.appendChild(tr);
        }
        tabela.appendChild(wiersz([["razem"], [formatM2.format(k.razem), "liczba"]], "tabela-programu__wazne"));
        const czesci = [];
        if (k.na_mieszkanie !== null) czesci.push(`${formatM2.format(k.na_mieszkanie)} zł na mieszkanie / dom`);
        if (k.na_m2_calkowitej !== null) czesci.push(`${formatM2.format(k.na_m2_calkowitej)} zł na m² powierzchni całkowitej`);
        podsumowanie.textContent = czesci.length ? `Średnio: ${czesci.join(", ")}.` : "";
    }

    function pokazProgram(p) {
        sekcjaProgramu.hidden = false;
        sekcjaProgramu.querySelectorAll("[data-program]").forEach((td) => {
            const wartosc = p ? p[td.dataset.program] : null;
            td.textContent = wartosc === null || wartosc === undefined ? "—" : formatWsk.format(wartosc);
        });
        const uwaga = document.getElementById("uwaga-parkingi");
        uwaga.hidden = !(p && p.miejsca_brakuje > 0);
        if (p && p.miejsca_brakuje > 0) {
            uwaga.textContent = `Na terenach KS brakuje ${formatM2.format(p.miejsca_brakuje)} miejsc postojowych — dorysuj parkingi albo przyjmij garaże podziemne.`;
        }
    }

    function pokazWskazniki(b) {
        sekcjaWskaznikow.hidden = false;
        const w = b.wskazniki || {};
        document.getElementById("podstawa-wskaznikow").textContent = b.obszar_m2 !== null
            ? "Wskaźniki liczone od powierzchni obszaru opracowania."
            : "Bez obszaru opracowania wskaźniki liczone są od sumy terenów.";
        sekcjaWskaznikow.querySelectorAll("[data-wskaznik]").forEach((td) => {
            const wartosc = w[td.dataset.wskaznik];
            td.textContent = wartosc === null || wartosc === undefined ? "—" : formatWsk.format(wartosc);
        });
        // Wskaźnik spełnia plan, gdy spełnia wszystkie swoje granice (np. min i max intensywności).
        const stany = {};
        for (const z of b.zgodnosc) {
            const klucz = { max_zabudowa_proc: "zabudowa_proc", min_intensywnosc: "intensywnosc", max_intensywnosc: "intensywnosc", min_pbc_proc: "pbc_proc", max_kondygnacje: "max_kondygnacje" }[z.ustalenie];
            stany[klucz] = (stany[klucz] ?? true) && z.spelnione;
        }
        sekcjaWskaznikow.querySelectorAll("[data-stan]").forEach((td) => {
            const stan = stany[td.dataset.stan];
            td.textContent = stan === undefined ? "" : stan ? "✓" : "✗";
            td.title = stan === undefined ? "" : stan ? "zgodne z planem" : "niezgodne z planem";
            td.className = `stan ${stan === undefined ? "" : stan ? "stan--ok" : "stan--zle"}`;
        });
        // ETAP 174: kolumna z narysowanych budynków — wartość i zgodność przy niej
        const wb = b.wskazniki_budynkow;
        sekcjaWskaznikow.querySelectorAll(".kolumna-budynkow").forEach((el) => (el.hidden = !wb));
        document.getElementById("naglowek-koncepcji").textContent = wb ? "Tereny" : "Koncepcja"; // z parametrów terenów
        if (!wb) return;
        const stanyBudynkow = {};
        for (const z of b.zgodnosc_budynkow) {
            const klucz = { max_zabudowa_proc: "zabudowa_proc", min_intensywnosc: "intensywnosc", max_intensywnosc: "intensywnosc", max_kondygnacje: "max_kondygnacje" }[z.ustalenie];
            stanyBudynkow[klucz] = (stanyBudynkow[klucz] ?? true) && z.spelnione;
        }
        sekcjaWskaznikow.querySelectorAll("[data-wskaznik-budynkow]").forEach((td) => {
            const klucz = td.dataset.wskaznikBudynkow;
            const wartosc = wb[klucz];
            td.replaceChildren(wartosc === null || wartosc === undefined ? "—" : formatWsk.format(wartosc));
            const stan = stanyBudynkow[klucz];
            if (stan !== undefined) td.append(" ", element("span", stan ? "stan--ok" : "stan--zle", stan ? "✓" : "✗"));
        });
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

    // ---------- odległości i cień (ETAP 94) — liczy serwer (osiedle/cien.py) ----------

    const warstwaCienia = L.featureGroup().addTo(mapa);
    const wynikCienia = document.getElementById("wynik-cienia");
    const przyciskUkryjCien = document.getElementById("ukryj-cien");

    function ukryjCien() {
        warstwaCienia.clearLayers();
        wynikCienia.hidden = true;
        przyciskUkryjCien.hidden = true;
    }

    // n-ty teren rysunku (bez obszaru) — ta sama kolejność co w zapisanym GeoJSON
    function warstwaTerenuNr(nr) {
        const tereny = [];
        rysunek.eachLayer((w) => {
            if (w.funkcja !== OBSZAR) tereny.push(w);
        });
        return tereny[nr - 1];
    }

    function wierszTerenu(nr, tekst) {
        const przycisk = element("button", "przycisk--tekst", tekst);
        przycisk.type = "button";
        przycisk.title = "Zaznacz ten teren na mapie";
        przycisk.addEventListener("click", () => {
            const w = warstwaTerenuNr(nr);
            if (w) {
                zaznacz(w);
                mapa.fitBounds(w.getBounds(), { maxZoom: 18, padding: [40, 40] });
            }
        });
        return przycisk;
    }

    document.getElementById("pokaz-cien").addEventListener("click", async () => {
        if (!koncepcja) return;
        await dokonczZapis();
        let w;
        try {
            w = await zapytaj(`${URL_KONCEPCJE}/${koncepcja.id}/cien?dzien=${document.getElementById("dzien-cienia").value}`);
        } catch (e) {
            return pokazKomunikat(e.message);
        }
        ukryjCien();
        wynikCienia.hidden = false;
        przyciskUkryjCien.hidden = false;
        if (!w.tereny.length) {
            wynikCienia.replaceChildren(element("p", "wyciszony", "Brak terenów zabudowy (MN, MW, U) — nie ma czego liczyć."));
            return;
        }
        if (w.strefa) {
            L.geoJSON(w.strefa, { interactive: false, style: { color: "#48484a", weight: 1, dashArray: "4 3", fillColor: "#1d1d1f", fillOpacity: 0.22 } }).addTo(warstwaCienia);
        }
        const tabela = element("table", "tabela tabela-cienia");
        const glowa = element("tr");
        glowa.append(element("th", "", w.zrodlo === "budynki" ? "Budynek" : "Teren"), element("th", "liczba", "Wysokość"), element("th", "liczba", "Cień w południe"), element("th", "liczba", "Od granicy obszaru"));
        tabela.appendChild(glowa);
        for (const t of w.tereny) {
            const tr = element("tr");
            const nazwa = element("td");
            // ETAP 195: przy budynkach numer z karty „Budynki”
            nazwa.appendChild(t.funkcja === "budynek" ? element("span", "", `budynek ${t.nr}`) : wierszTerenu(t.nr, `${t.funkcja} (teren ${t.nr})`));
            const granica = t.od_granicy_m === null ? "— (brak obszaru)" : t.od_granicy_m === 0 ? "0 m — sięga granicy" : `${formatWsk.format(t.od_granicy_m)} m`;
            tr.append(nazwa, element("td", "liczba", `${formatWsk.format(t.wysokosc_m)} m`),
                element("td", "liczba", t.cien_w_poludnie_m === null ? "—" : `${formatWsk.format(t.cien_w_poludnie_m)} m`), element("td", "liczba", granica));
            tabela.appendChild(tr);
        }
        const czesci = [element("p", "wyciszony opis-panelu", (w.zrodlo === "budynki" ? "Cień od narysowanych budynków. " : "Najgorszy przypadek: budynki przy krawędzi terenów zabudowy (narysuj budynki, żeby liczyć od nich). ") + `${w.dzien}, szerokość ${formatWsk.format(w.szerokosc)}° N: słońce w południe ${formatWsk.format(w.slonce.find((s) => s.godzina === 12).wysokosc)}° nad horyzontem.`), tabela];
        if (w.tereny.some((t) => t.od_granicy_m === 0)) {
            czesci.push(element("p", "komunikat komunikat--ostrzezenie", "Teren zabudowy sięga granicy obszaru — budynki trzeba będzie odsunąć od granicy działki (minimalne odległości: § 12 warunków technicznych)."));
        }
        if (w.zacienione.length) {
            czesci.push(element("h4", "", "Tereny w strefie możliwego cienia"));
            const lista = element("ul", "lista-cienia");
            for (const z of w.zacienione) {
                const li = element("li");
                li.append(wierszTerenu(z.nr, `${z.funkcja} (teren ${z.nr})`), ` — ${formatM2.format(z.w_cieniu_m2)} m² (${formatProc.format(z.procent)}% terenu)`);
                lista.appendChild(li);
            }
            czesci.push(lista, element("p", "wyciszony opis-panelu", "Przy zabudowie blisko tych miejsc sprawdź na projekcie budynków nasłonecznienie (§ 60) i przesłanianie (§ 13) wg warunków technicznych."));
        } else {
            czesci.push(element("p", "wyciszony", "Cień nie sięga terenów MN, MW ani ZP."));
        }
        wynikCienia.replaceChildren(...czesci);
    });

    przyciskUkryjCien.addEventListener("click", ukryjCien);

    async function otworz(id) {
        await dokonczZapis();
        zaznacz(null);
        rysunek.clearLayers();
        pokazKomunikat("");
        if (!id) {
            koncepcja = null;
            mapa.removeControl(kontrolkaRysowania);
            [sekcjaRysowania, sekcjaBilansu, sekcjaWskaznikow, sekcjaProgramu, sekcjaCienia, sekcjaCen, akcjeKoncepcji, linkiKoncepcji, warstwaTerenuEl].forEach((el) => (el.hidden = true));
            ukryjCien();
            projektTerenu.value = "";
            pokazTeren();
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
        [sekcjaRysowania, sekcjaCienia, sekcjaCen, akcjeKoncepcji, linkiKoncepcji, warstwaTerenuEl].forEach((el) => (el.hidden = false));
        ukryjCien();
        wynikCen.hidden = true;
        const zapisanyTeren = (dane.ustawienia || {}).teren_projekt;
        // projekt mógł zostać usunięty w module Teren — wtedy nic nie pokazujemy
        projektTerenu.value = [...projektTerenu.options].some((o) => o.value === String(zapisanyTeren)) ? String(zapisanyTeren) : "";
        pokazTeren();
        linkGeojson.href = `${URL_KONCEPCJE}/${id}.geojson`;
        document.getElementById("link-ods").href = `${URL_KONCEPCJE}/${id}.ods`; // ETAP 189
        document.getElementById("link-dxf").href = `${URL_KONCEPCJE}/${id}.dxf`; // ETAP 122
        linkRaport.href = `${URL_KONCEPCJE}/${id}/raport`;
        stanZapisu.textContent = "";
        const plan = (dane.ustawienia || {}).plan || {};
        polaUstalen.forEach((pole) => (pole.value = plan[pole.dataset.ustalenie] ?? ""));
        const zalozenia = (dane.ustawienia || {}).program || {};
        polaZalozen.forEach((pole) => (pole.value = zalozenia[pole.dataset.zalozenie] ?? ""));
        const stawki = (dane.ustawienia || {}).koszty || {};
        polaStawek.forEach((pole) => (pole.value = stawki[pole.dataset.stawka] ?? ""));
        pokazBilans(dane.bilans);
        if (rysunek.getLayers().length) mapa.fitBounds(rysunek.getBounds(), { padding: [30, 30], maxZoom: 18 });
    }

    // Obszar z działek ewidencyjnych (ETAP 75): granice z ULDK liczy serwer.
    document.getElementById("obszar-z-dzialek").addEventListener("click", async (e) => {
        if (!koncepcja) return;
        const dzialki = document.getElementById("dzialki-obszaru").value.split(/[\n,;]+/).map((d) => d.trim()).filter(Boolean);
        if (!dzialki.length) return pokazKomunikat("Wpisz identyfikator co najmniej jednej działki.");
        e.target.disabled = true;
        stanZapisu.textContent = "Pobieram granice z ULDK…";
        try {
            await dokonczZapis(); // najpierw zaległe zmiany rysunku
            await zapytaj(`${URL_KONCEPCJE}/${koncepcja.id}/obszar-z-dzialek`, { method: "POST", body: JSON.stringify({ dzialki }) });
            await otworz(koncepcja.id); // przerysowanie z nowym obszarem i przybliżenie do niego
            stanZapisu.textContent = "Zapisano";
        } catch (err) {
            stanZapisu.textContent = "";
            pokazKomunikat(err.message);
        } finally {
            e.target.disabled = false;
        }
    });

    // Obszar z pliku GeoJSON (ETAP 138): układ współrzędnych rozpoznaje i przelicza serwer.
    document.getElementById("obszar-z-pliku").addEventListener("click", async (e) => {
        if (!koncepcja) return;
        const plik = document.getElementById("plik-obszaru").files[0];
        if (!plik) return pokazKomunikat("Wybierz plik GeoJSON z granicą obszaru.");
        const formularz = new FormData();
        formularz.append("plik", plik);
        e.target.disabled = true;
        try {
            await dokonczZapis();
            const wynik = await zapytaj(`${URL_KONCEPCJE}/${koncepcja.id}/obszar-z-pliku`, { method: "POST", body: formularz });
            await otworz(koncepcja.id);
            const obszar = wynik.geojson.features.find((c) => c.properties.funkcja === OBSZAR);
            stanZapisu.textContent = `Zapisano obszar z pliku (układ ${obszar.properties.uklad_pliku})`;
        } catch (err) {
            stanZapisu.textContent = "";
            pokazKomunikat(err.message);
        } finally {
            e.target.disabled = false;
        }
    });

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
    // ETAP 128: link z wyszukiwarki otwiera wskazaną koncepcję (?koncepcja=<id>)
    ostatnia = new URLSearchParams(location.search).get("koncepcja") || ostatnia;
    // Najpierw lista projektów terenowych — otwarta koncepcja ustawia z niej swój wybór.
    wczytajProjektyTerenu().then(() => wczytajListe(ostatnia).catch(() => wczytajListe().catch((e) => pokazKomunikat(e.message))));

    // ---------- ceny w okolicy (ETAP 109) — liczy moduł ceny z zaimportowanego pliku RCN ----------

    const wynikCen = document.getElementById("wynik-cen");

    function wierszCen(nazwa, s) {
        const tr = element("tr");
        tr.appendChild(element("th", "", nazwa));
        if (!s) {
            const brak = element("td", "wyciszony", "brak transakcji");
            brak.colSpan = 3;
            tr.appendChild(brak);
            return tr;
        }
        tr.append(element("td", "liczba", `${s.liczba}${s.w_srodku ? ` (w obszarze ${s.w_srodku})` : ""}`),
            element("td", "liczba", `${formatM2.format(s.mediana_m2)} zł`),
            element("td", "liczba", `${formatM2.format(s.q1_m2)}–${formatM2.format(s.q3_m2)}`));
        return tr;
    }

    document.getElementById("pokaz-ceny").addEventListener("click", async () => {
        let obszar = null;
        rysunek.eachLayer((w) => {
            if (w.funkcja === OBSZAR) obszar = w.toGeoJSON().geometry;
        });
        wynikCen.hidden = false;
        if (!obszar) {
            wynikCen.replaceChildren(element("p", "komunikat", "Najpierw narysuj obszar opracowania (albo złóż go z działek)."));
            return;
        }
        let d;
        try {
            d = await zapytaj(URL_CENY_OKOLICA, { method: "POST", body: JSON.stringify({ geometria: obszar, promien: Number(document.getElementById("promien-cen").value) }) });
        } catch (e) {
            wynikCen.replaceChildren(element("p", "komunikat komunikat--blad", e.message));
            return;
        }
        if (!d.plik) {
            const p = element("p", "wyciszony", d.pliki_zaimportowane
                ? "W zaimportowanych plikach RCN nie ma transakcji w tym zasięgu — zwiększ promień albo zaimportuj plik tego powiatu. "
                : "Nie zaimportowano jeszcze żadnego pliku RCN. ");
            const a = element("a", "", "Ceny → Transakcje");
            a.href = d.url_importu;
            p.appendChild(a);
            wynikCen.replaceChildren(p);
            return;
        }
        const tabela = element("table", "tabela tabela-cen-okolicy");
        const glowa = element("tr");
        glowa.append(element("th", "", ""), element("th", "liczba", "Transakcji"), element("th", "liczba", "Mediana za m²"), element("th", "liczba", "Połowa transakcji"));
        tabela.append(glowa, wierszCen("Mieszkania", d.lokale), wierszCen("Działki", d.dzialki));
        const przewijanie = element("div", "tabela-cen-okolicy-wrap");
        przewijanie.appendChild(tabela);
        const okres = [d.lokale, d.dzialki].filter(Boolean);
        const lata = `${okres.map((s) => s.od).sort()[0].slice(0, 4)}–${okres.map((s) => s.do).sort().at(-1).slice(0, 4)}`;
        const link = element("a", "przycisk przycisk--tekst", `Plik ${d.plik.nazwa} — mapa i podobne transakcje ↗`);
        link.href = d.plik.url;
        link.target = "_blank";
        wynikCen.replaceChildren(przewijanie,
            element("p", "wyciszony opis-panelu", `Transakcje z lat ${lata}, ceny brutto z aktów notarialnych. Działki: cena za m² gruntu; przy zabudowanych obejmuje budynek.`), link);
    });
})();
