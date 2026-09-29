(function () {
    "use strict";

    const mapa = L.map("mapa").setView([52.4064, 16.9252], 13);

    // Podkłady (ETAP 34). OSM wymaga nagłówka Referer — bez niego zwraca
    // kafelki „Access blocked”, a nasz Referrer-Policy: same-origin go
    // wycina. Dlatego kafelki OSM dostają własną, łagodniejszą politykę
    // (wysyłany jest tylko adres http://127.0.0.1:port, bez ścieżki).
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
    const KLUCZ_PODKLADU = "mpzp.podklad";
    let nazwaPodkladu = "Mapa (OpenStreetMap)";
    try {
        const zapisany = localStorage.getItem(KLUCZ_PODKLADU);
        if (zapisany && PODKLADY[zapisany]) nazwaPodkladu = zapisany;
    } catch (e) {
        // brak dostępu do localStorage — zostaje domyślny podkład
    }
    PODKLADY[nazwaPodkladu].addTo(mapa);
    mapa.on("baselayerchange", (e) => {
        try {
            localStorage.setItem(KLUCZ_PODKLADU, e.name);
        } catch (err) {
            // zapamiętanie wyboru to tylko wygoda
        }
    });
    const kontrolkaWarstw = L.control.layers(PODKLADY, {}, { position: "topright" }).addTo(mapa);

    // Nakładki z krajowych integracji GUGiK: plany miejscowe całej Polski
    // i granice działek. Obrazki ładuje przeglądarka wprost z GUGiK; nazwy
    // warstw planów serwer odczytuje z opisu usługi (GetCapabilities).
    function nakladkaWms(opis, przezroczystosc) {
        return L.tileLayer.wms(opis.url, {
            layers: opis.warstwy,
            format: "image/png",
            transparent: true,
            version: "1.3.0",
            opacity: przezroczystosc,
            maxZoom: 20,
            attribution: "plany i działki: GUGiK",
            // Usługa bez EPSG:3857 dostaje zapytania w EPSG:4326.
            ...(opis.mercator === false ? { crs: L.CRS.EPSG4326 } : {}),
        });
    }

    fetch(URL_WARSTWY_KRAJOWE)
        .then((odpowiedz) => odpowiedz.json())
        .then((dane) => {
            const plany = nakladkaWms(dane.plany, 0.65).addTo(mapa);
            const dzialki = nakladkaWms(dane.dzialki, 1);
            kontrolkaWarstw.addOverlay(plany, "Plany miejscowe (cała Polska)");
            kontrolkaWarstw.addOverlay(dzialki, "Działki ewidencyjne");
        })
        .catch(() => {}); // bez nakładek mapa działa jak dotąd

    const panelWyniku = document.getElementById("panel-wyniku");
    const przyciskOdswiez = document.getElementById("przycisk-odswiez");
    const formularzSzukaj = document.getElementById("szukaj-dzialki");
    const poleIdDzialki = document.getElementById("pole-id-dzialki");
    const listaHistorii = document.getElementById("historia");

    let warstwaDzialki = null;
    let warstwaWydzielenia = null;
    // Numer ostatniego zapytania: odpowiedź na starsze kliknięcie, która
    // przyszła później, jest ignorowana (inaczej zostawiałaby na mapie
    // wielokąty, których nie da się już usunąć).
    let numerZapytania = 0;

    function wyczyscWarstwy() {
        if (warstwaDzialki) {
            mapa.removeLayer(warstwaDzialki);
            warstwaDzialki = null;
        }
        if (warstwaWydzielenia) {
            mapa.removeLayer(warstwaWydzielenia);
            warstwaWydzielenia = null;
        }
    }

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function pokazBlad(tresc, dzialka) {
        panelWyniku.replaceChildren();
        if (dzialka) panelWyniku.appendChild(sekcjaDzialki(dzialka));
        panelWyniku.appendChild(element("p", "komunikat komunikat--blad", tresc));
    }

    const KOLORY_UDZIALOW = ["#34c759", "#ff9f0a", "#0a84ff", "#bf5af2", "#ff375f", "#64d2ff"];
    const formatM2 = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 });

    let ostatnieWspolrzedne = null; // z ostatniej odpowiedzi serwera (ETAP 36)

    const formatWsp = new Intl.NumberFormat("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: false });

    // Przycisk „kopiuj” obok wartości — do QGIS-a, operatu, notatek.
    function przyciskKopiuj(tekst) {
        const przycisk = element("button", "przycisk-kopiuj", "Kopiuj");
        przycisk.type = "button";
        przycisk.title = tekst;
        przycisk.addEventListener("click", () => {
            navigator.clipboard.writeText(tekst).then(
                () => {
                    przycisk.textContent = "Skopiowano";
                    setTimeout(() => (przycisk.textContent = "Kopiuj"), 1500);
                },
                () => (przycisk.textContent = "Brak dostępu")
            );
        });
        return przycisk;
    }

    // Współrzędne klikniętego punktu: WGS84 + PL-1992 + PL-2000 (X = północ).
    function sekcjaWspolrzednych(wspolrzedne) {
        const szczegoly = element("details", "wspolrzedne");
        szczegoly.appendChild(element("summary", "", "Współrzędne punktu"));
        const lista = element("div", "wspolrzedne__lista");
        for (const w of wspolrzedne) {
            const wiersz = element("div", "wspolrzedne__wiersz");
            let wartosc;
            let doSchowka;
            if (w.epsg === 4326) {
                wartosc = `φ ${w.szerokosc.toFixed(6)}°, λ ${w.dlugosc.toFixed(6)}°`;
                doSchowka = `${w.szerokosc.toFixed(6)}, ${w.dlugosc.toFixed(6)}`;
            } else {
                wartosc = `X ${formatWsp.format(w.x)}  Y ${formatWsp.format(w.y)}`;
                doSchowka = `${w.x.toFixed(2)} ${w.y.toFixed(2)}`;
            }
            const opis = element("div", "wspolrzedne__uklad");
            opis.append(element("strong", "", w.uklad), element("span", "wspolrzedne__epsg", `EPSG:${w.epsg}`));
            wiersz.append(opis, element("div", "wspolrzedne__wartosc", wartosc), przyciskKopiuj(doSchowka));
            lista.appendChild(wiersz);
        }
        szczegoly.append(lista, element("p", "przypis", "X — oś północna, Y — wschodnia (konwencja geodezyjna; w QGIS kolejność jest odwrotna: najpierw Y). PL-2000: strefa wg południka."));
        return szczegoly;
    }

    function sekcjaDzialki(dzialka) {
        const sekcja = element("div", "stos");
        const naglowek = element("div", "rzad rzad--miedzy");
        const raport = element("a", "przycisk przycisk--tekst", "Raport do druku ↗");
        raport.href = `${URL_RAPORT}?id=${encodeURIComponent(dzialka.id)}`;
        raport.target = "_blank";
        const kalkulator = element("a", "przycisk przycisk--tekst", "Kalkulator zabudowy");
        kalkulator.href = `${URL_KALKULATOR}?dzialka=${encodeURIComponent(dzialka.id)}` + (dzialka.powierzchnia_m2 ? `&powierzchnia=${Math.round(dzialka.powierzchnia_m2)}` : "");
        const geojson = element("a", "przycisk przycisk--tekst", "GeoJSON");
        geojson.href = `${URL_GEOJSON}?id=${encodeURIComponent(dzialka.id)}`;
        geojson.title = "Działka i jej części w przeznaczeniach — do QGIS";
        // Geoportal otwiera działkę po identyfikatorze (parametr identifyParcel).
        const geoportal = element("a", "przycisk przycisk--tekst", "Geoportal ↗");
        geoportal.href = `https://mapy.geoportal.gov.pl/imap/Imgp_2.html?identifyParcel=${encodeURIComponent(dzialka.id)}`;
        geoportal.target = "_blank";
        geoportal.rel = "noopener noreferrer";
        geoportal.title = "Działka w serwisie geoportal.gov.pl (ewidencja, ortofotomapa, plany)";
        const linki = element("div", "rzad");
        linki.append(kalkulator, raport, geojson, geoportal);
        naglowek.append(element("h3", "", "Działka"), linki);
        sekcja.append(naglowek, element("div", "identyfikator wyciszony", dzialka.id));
        if (dzialka.powierzchnia_m2) {
            sekcja.appendChild(
                element("div", "powierzchnia", `Powierzchnia: ${formatM2.format(dzialka.powierzchnia_m2)} m² (${(dzialka.powierzchnia_m2 / 10000).toLocaleString("pl-PL", { maximumFractionDigits: 4 })} ha)`)
            );
        }
        if (ostatnieWspolrzedne) sekcja.appendChild(sekcjaWspolrzednych(ostatnieWspolrzedne));
        return sekcja;
    }

    // Jak działka dzieli się między przeznaczenia: pasek + lista z m² i %.
    function sekcjaUdzialow(udzialy) {
        const sekcja = element("div", "stos");
        sekcja.appendChild(element("h3", "", "Podział działki"));
        const pasek = element("div", "pasek-udzialow");
        const lista = element("ul", "lista-udzialow");
        udzialy.forEach((u, i) => {
            const kolor = KOLORY_UDZIALOW[i % KOLORY_UDZIALOW.length];
            const kawalek = element("span");
            kawalek.style.flex = String(u.procent);
            kawalek.style.background = kolor;
            kawalek.title = `${u.przeznaczenie}: ${u.procent}%`;
            pasek.appendChild(kawalek);
            const li = element("li");
            const probka = element("span", "raport__kolor");
            probka.style.background = kolor;
            li.append(
                probka,
                element("strong", "", u.przeznaczenie),
                element("span", "lista-udzialow__liczby", `${u.procent.toLocaleString("pl-PL")}% · ${formatM2.format(u.powierzchnia_m2)} m²`),
                element("span", "lista-udzialow__opis wyciszony", u.opis.map((o) => o.opis || o.symbol).join(" / "))
            );
            lista.appendChild(li);
        });
        sekcja.append(pasek, lista);
        return sekcja;
    }

    // Opis symbolu ze słownika (np. MN/U → dwie pozycje).
    function sekcjaOpisu(opisy) {
        const lista = element("ul", "opis-symbolu");
        for (const { symbol, opis } of opisy) {
            const li = element("li");
            li.append(element("span", "etykieta etykieta--sukces", symbol), element("span", opis ? "" : "wyciszony", opis || "brak w słowniku — sprawdź legendę planu"));
            lista.appendChild(li);
        }
        return lista;
    }

    function pokazWynik(dzialka, wydzielenie, udzialy) {
        panelWyniku.replaceChildren(sekcjaDzialki(dzialka));
        // Podział pokazujemy, gdy działka leży w więcej niż jednym przeznaczeniu.
        if (udzialy && udzialy.length > 1) panelWyniku.appendChild(sekcjaUdzialow(udzialy));

        const przeznaczenie = element("div", "przeznaczenie");
        przeznaczenie.append(
            element("span", "przeznaczenie__symbol", wydzielenie.przeznaczenie || "?"),
            element("span", "wyciszony", "przeznaczenie w klikniętym punkcie")
        );
        panelWyniku.appendChild(przeznaczenie);

        if (wydzielenie.opis_przeznaczenia && wydzielenie.opis_przeznaczenia.length) {
            panelWyniku.appendChild(sekcjaOpisu(wydzielenie.opis_przeznaczenia));
            panelWyniku.appendChild(
                element("p", "przypis", "Opis orientacyjny wg rozporządzenia z 2003 r. Rozstrzyga tekst uchwały planu.")
            );
        }

        panelWyniku.appendChild(element("h3", "", "Atrybuty wydzielenia"));
        const tabela = element("table", "tabela");
        for (const [klucz, wartosc] of Object.entries(wydzielenie.atrybuty)) {
            const wiersz = element("tr");
            wiersz.append(element("th", "", klucz), element("td", "", wartosc));
            tabela.appendChild(wiersz);
        }
        panelWyniku.appendChild(tabela);
    }

    // Gmina bez własnego WFS: atrybuty planu z krajowej integracji (ETAP 35).
    function pokazPlanKrajowy(dzialka, plan) {
        panelWyniku.replaceChildren(sekcjaDzialki(dzialka));

        const przeznaczenie = element("div", "przeznaczenie");
        przeznaczenie.append(
            element("span", "przeznaczenie__symbol", plan.przeznaczenie || "?"),
            element("span", "wyciszony", plan.przeznaczenie ? "symbol rozpoznany z atrybutów planu" : "nie rozpoznano symbolu — zobacz atrybuty niżej")
        );
        panelWyniku.appendChild(przeznaczenie);
        if (plan.tytul) panelWyniku.appendChild(element("p", "", plan.tytul));

        if (plan.opis_przeznaczenia && plan.opis_przeznaczenia.length) {
            panelWyniku.appendChild(sekcjaOpisu(plan.opis_przeznaczenia));
        }

        if (plan.linki.length) {
            const linki = element("div", "plan-krajowy__linki");
            plan.linki.forEach((adres, i) => {
                const a = element("a", "przycisk przycisk--tekst", plan.linki.length > 1 ? `Dokument planu ${i + 1} ↗` : "Dokument planu ↗");
                a.href = adres;
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                a.title = adres;
                linki.appendChild(a);
            });
            panelWyniku.appendChild(linki);
        }

        for (const obiekt of plan.obiekty) {
            const szczegoly = element("details", "plan-krajowy__warstwa");
            szczegoly.open = plan.obiekty.length === 1;
            szczegoly.appendChild(element("summary", "", `Atrybuty — warstwa ${obiekt.warstwa || "?"}`));
            const tabela = element("table", "tabela");
            for (const [klucz, wartosc] of Object.entries(obiekt.atrybuty)) {
                const wiersz = element("tr");
                wiersz.append(element("th", "", klucz), element("td", "", wartosc));
                tabela.appendChild(wiersz);
            }
            szczegoly.appendChild(tabela);
            panelWyniku.appendChild(szczegoly);
        }
        panelWyniku.appendChild(
            element("p", "przypis", "Źródło: krajowa integracja planów miejscowych (GUGiK). Przeznaczenie w klikniętym punkcie; podział działki liczymy tylko tam, gdzie gmina ma usługę WFS (Poznań). Rozstrzyga tekst uchwały planu.")
        );
    }

    // Wspólna obsługa odpowiedzi z /sprawdz i /dzialka.
    function obsluzOdpowiedz(dane, przyblizDoDzialki) {
        wyczyscWarstwy();
        ostatnieWspolrzedne = dane.wspolrzedne || null;
        if (dane.dzialka) {
            warstwaDzialki = L.geoJSON(dane.dzialka.geometria, {
                style: { color: "#0071e3", weight: 2, fillOpacity: 0.1 },
            }).addTo(mapa);
            if (przyblizDoDzialki) mapa.fitBounds(warstwaDzialki.getBounds(), { maxZoom: 18, padding: [40, 40] });
        }

        if (dane.wydzielenie) {
            warstwaWydzielenia = L.geoJSON(dane.wydzielenie.geometria, {
                style: { color: "#34c759", weight: 2, fillOpacity: 0.3 },
            }).addTo(mapa);
            if (warstwaDzialki) warstwaDzialki.bringToFront();
            pokazWynik(dane.dzialka, dane.wydzielenie, dane.udzialy);
        } else if (dane.plan_krajowy) {
            pokazPlanKrajowy(dane.dzialka, dane.plan_krajowy);
        } else if (dane.blad) {
            pokazBlad(dane.blad, dane.dzialka);
        }
        odswiezHistorie();
    }

    function zapytaj(url, przyblizDoDzialki) {
        const numer = ++numerZapytania;
        wyczyscWarstwy();
        ostatnieWspolrzedne = null;
        panelWyniku.innerHTML = "<p class=\"pusty-stan\">Sprawdzam…</p>";
        return fetch(url)
            .then((odpowiedz) => odpowiedz.json())
            .then((dane) => {
                if (numer === numerZapytania) obsluzOdpowiedz(dane, przyblizDoDzialki);
                else odswiezHistorie(); // starsza odpowiedź: tylko historia
            })
            .catch(() => {
                if (numer === numerZapytania) pokazBlad("Błąd połączenia z serwerem.");
            });
    }

    function sprawdzPunkt(lat, lon, przyblizDoDzialki) {
        return zapytaj(`${URL_SPRAWDZ}?lat=${lat}&lon=${lon}`, przyblizDoDzialki);
    }

    mapa.on("click", (zdarzenie) => {
        if (pomiarWlaczony) dodajPunktPomiaru(zdarzenie.latlng);
        else sprawdzPunkt(zdarzenie.latlng.lat, zdarzenie.latlng.lng, false);
    });

    // ---------- pomiar odległości i powierzchni (ETAP 36) ----------
    // W trybie pomiaru kliknięcia dodają wierzchołki zamiast sprawdzać
    // działkę. Liczby liczy serwer (/pomiar) tymi samymi wzorami co
    // powierzchnię działki.

    let pomiarWlaczony = false;
    let punktyPomiaru = [];
    let warstwaPomiaru = L.layerGroup().addTo(mapa);
    let numerPomiaru = 0;

    const KontrolkaPomiaru = L.Control.extend({
        options: { position: "topleft" },
        onAdd() {
            const pudelko = L.DomUtil.create("div", "pomiar");
            L.DomEvent.disableClickPropagation(pudelko);
            this.przycisk = L.DomUtil.create("a", "pomiar__przycisk", pudelko);
            this.przycisk.href = "#";
            this.przycisk.title = "Pomiar odległości i powierzchni (Esc — koniec)";
            this.przycisk.setAttribute("role", "button");
            this.przycisk.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 17 17 3l4 4L7 21z"/><path d="m7 13 2 2M10 10l2 2M13 7l2 2"/></svg>';
            this.wynik = L.DomUtil.create("div", "pomiar__wynik", pudelko);
            this.wynik.hidden = true;
            L.DomEvent.on(this.przycisk, "click", (e) => {
                L.DomEvent.preventDefault(e);
                przelaczPomiar(!pomiarWlaczony);
            });
            return pudelko;
        },
    });
    const kontrolkaPomiaru = new KontrolkaPomiaru().addTo(mapa);

    function przelaczPomiar(wlacz) {
        pomiarWlaczony = wlacz;
        punktyPomiaru = [];
        numerPomiaru += 1;
        warstwaPomiaru.clearLayers();
        kontrolkaPomiaru.przycisk.classList.toggle("pomiar__przycisk--aktywny", wlacz);
        mapa.getContainer().classList.toggle("mapa--pomiar", wlacz);
        mapa.doubleClickZoom[wlacz ? "disable" : "enable"]();
        kontrolkaPomiaru.wynik.hidden = !wlacz;
        kontrolkaPomiaru.wynik.textContent = "Klikaj kolejne punkty na mapie.";
    }

    function rysujPomiar() {
        warstwaPomiaru.clearLayers();
        const styl = { color: "#ff9f0a", weight: 3, dashArray: "6 6" };
        if (punktyPomiaru.length >= 3) {
            L.polygon(punktyPomiaru, { ...styl, fillOpacity: 0.12, interactive: false }).addTo(warstwaPomiaru);
        } else if (punktyPomiaru.length === 2) {
            L.polyline(punktyPomiaru, { ...styl, interactive: false }).addTo(warstwaPomiaru);
        }
        for (const p of punktyPomiaru) {
            L.circleMarker(p, { radius: 4, color: "#ff9f0a", fillColor: "#ffffff", fillOpacity: 1, weight: 2, interactive: false }).addTo(warstwaPomiaru);
        }
    }

    async function dodajPunktPomiaru(latlng) {
        punktyPomiaru.push([latlng.lat, latlng.lng]);
        rysujPomiar();
        if (punktyPomiaru.length < 2) return;
        const numer = ++numerPomiaru;
        try {
            const odpowiedz = await fetch(URL_POMIAR, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ punkty: punktyPomiaru }),
            });
            const dane = await odpowiedz.json();
            if (numer !== numerPomiaru) return;
            pokazWynikPomiaru(dane);
        } catch (e) {
            if (numer === numerPomiaru) kontrolkaPomiaru.wynik.textContent = "Błąd połączenia z serwerem.";
        }
    }

    const formatMetrow = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });

    function dlugosc(m) {
        return m >= 1000 ? `${(m / 1000).toLocaleString("pl-PL", { maximumFractionDigits: 3 })} km` : `${formatMetrow.format(m)} m`;
    }

    function pokazWynikPomiaru(dane) {
        const wynik = kontrolkaPomiaru.wynik;
        wynik.replaceChildren();
        if (dane.blad) {
            wynik.textContent = dane.blad;
            return;
        }
        const wiersz = (etykieta, wartosc) => {
            const w = element("div", "pomiar__wiersz");
            w.append(element("span", "wyciszony", etykieta), element("strong", "", wartosc));
            return w;
        };
        wynik.append(wiersz("Łamana", dlugosc(dane.dlugosc_m)), wiersz("Ostatni odcinek", dlugosc(dane.ostatni_odcinek_m)));
        if (dane.powierzchnia_m2 !== undefined) {
            wynik.append(
                wiersz("Powierzchnia", `${formatM2.format(dane.powierzchnia_m2)} m² · ${(dane.powierzchnia_m2 / 10000).toLocaleString("pl-PL", { maximumFractionDigits: 4 })} ha`),
                wiersz("Obwód", dlugosc(dane.obwod_m))
            );
        }
        if (dane.uwaga) wynik.appendChild(element("p", "pomiar__uwaga", dane.uwaga));
        const cofnij = element("button", "przycisk--tekst", "Cofnij punkt");
        cofnij.type = "button";
        cofnij.addEventListener("click", (e) => {
            e.stopPropagation();
            punktyPomiaru.pop();
            rysujPomiar();
            numerPomiaru += 1;
            if (punktyPomiaru.length >= 2) {
                const ostatni = punktyPomiaru.pop();
                dodajPunktPomiaru({ lat: ostatni[0], lng: ostatni[1] });
            } else {
                wynik.textContent = "Klikaj kolejne punkty na mapie.";
            }
        });
        wynik.appendChild(cofnij);
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && pomiarWlaczony) przelaczPomiar(false);
    });

    // ---------- wyszukiwanie z podpowiedziami ----------
    // Wpisujesz „obręb numer” (albo pełny identyfikator), lista podpowiedzi
    // pojawia się sama; klik albo Enter od razu pokazuje działkę na mapie.

    const listaPodpowiedzi = document.getElementById("podpowiedzi-dzialek");
    let podpowiedzi = []; // [{id, opis}]
    let zaznaczona = -1;
    let opoznienie = null;
    let numerPodpowiedzi = 0;

    function pokazDzialke(id) {
        ukryjPodpowiedzi();
        poleIdDzialki.value = id;
        zapytaj(`${URL_DZIALKA}?id=${encodeURIComponent(id)}`, true);
    }

    function ukryjPodpowiedzi() {
        listaPodpowiedzi.hidden = true;
        poleIdDzialki.setAttribute("aria-expanded", "false");
        zaznaczona = -1;
    }

    function zaznacz(indeks) {
        const elementy = listaPodpowiedzi.querySelectorAll("[role=option]");
        if (elementy.length === 0) return;
        zaznaczona = (indeks + elementy.length) % elementy.length;
        elementy.forEach((el, i) => el.classList.toggle("podpowiedz--zaznaczona", i === zaznaczona));
        elementy[zaznaczona].scrollIntoView({ block: "nearest" });
    }

    function naglowek(tekst) {
        return element("li", "podpowiedzi-dzialek__naglowek", tekst);
    }

    function rysujPodpowiedzi(dane) {
        listaPodpowiedzi.replaceChildren();
        podpowiedzi = [];
        const dodaj = (id, opis, etykieta) => {
            const li = element("li", "podpowiedz");
            li.setAttribute("role", "option");
            const tekst = element("span", "podpowiedz__tekst");
            tekst.append(element("span", "identyfikator", id));
            if (opis) tekst.append(element("span", "podpowiedz__opis", opis));
            li.appendChild(tekst);
            if (etykieta) li.appendChild(element("span", "etykieta etykieta--sukces", etykieta));
            const indeks = podpowiedzi.length;
            li.addEventListener("mousedown", (e) => {
                e.preventDefault(); // nie zabieraj fokusu polu przed kliknięciem
                pokazDzialke(podpowiedzi[indeks].id);
            });
            podpowiedzi.push({ id });
            listaPodpowiedzi.appendChild(li);
        };

        if (dane.z_historii.length) {
            listaPodpowiedzi.appendChild(naglowek("Ostatnio sprawdzane"));
            for (const p of dane.z_historii) dodaj(p.id, "", p.przeznaczenie || "bez planu");
        }
        if (dane.z_uldk.length) {
            listaPodpowiedzi.appendChild(naglowek("Ewidencja gruntów (ULDK)"));
            for (const p of dane.z_uldk) dodaj(p.id, p.opis);
        }
        const informacja = dane.blad || dane.wskazowka || (podpowiedzi.length ? "" : "Nie znaleziono działki. Sprawdź nazwę obrębu i numer.");
        if (informacja) listaPodpowiedzi.appendChild(element("li", dane.blad ? "podpowiedzi-dzialek__blad" : "podpowiedzi-dzialek__info", informacja));

        listaPodpowiedzi.hidden = false;
        poleIdDzialki.setAttribute("aria-expanded", "true");
        zaznaczona = -1;
    }

    async function pobierzPodpowiedzi(fraza) {
        const numer = ++numerPodpowiedzi;
        listaPodpowiedzi.replaceChildren(element("li", "podpowiedzi-dzialek__info", "Szukam…"));
        listaPodpowiedzi.hidden = false;
        try {
            const odpowiedz = await fetch(`${URL_PODPOWIEDZI}?q=${encodeURIComponent(fraza)}`);
            const dane = await odpowiedz.json();
            if (numer === numerPodpowiedzi) rysujPodpowiedzi(dane);
        } catch (e) {
            if (numer === numerPodpowiedzi) rysujPodpowiedzi({ z_historii: [], z_uldk: [], blad: "Błąd połączenia z serwerem." });
        }
    }

    poleIdDzialki.addEventListener("input", () => {
        clearTimeout(opoznienie);
        const fraza = poleIdDzialki.value.trim();
        if (fraza.length < 3) {
            numerPodpowiedzi += 1;
            ukryjPodpowiedzi();
            return;
        }
        opoznienie = setTimeout(() => pobierzPodpowiedzi(fraza), 400);
    });

    poleIdDzialki.addEventListener("keydown", (e) => {
        if (listaPodpowiedzi.hidden) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            zaznacz(zaznaczona + 1);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            zaznacz(zaznaczona - 1);
        } else if (e.key === "Escape") {
            ukryjPodpowiedzi();
        }
    });

    poleIdDzialki.addEventListener("blur", () => setTimeout(ukryjPodpowiedzi, 150));

    formularzSzukaj.addEventListener("submit", (zdarzenie) => {
        zdarzenie.preventDefault();
        // Enter: zaznaczona podpowiedź, a gdy nic nie zaznaczono — pierwsza.
        if (!listaPodpowiedzi.hidden && podpowiedzi.length) {
            pokazDzialke(podpowiedzi[Math.max(zaznaczona, 0)].id);
            return;
        }
        const fraza = poleIdDzialki.value.trim();
        if (fraza.length >= 3) pobierzPodpowiedzi(fraza);
    });

    // ---------- historia ----------

    function odswiezHistorie() {
        fetch(URL_HISTORIA)
            .then((odpowiedz) => odpowiedz.json())
            .then((wpisy) => {
                listaHistorii.replaceChildren();
                if (wpisy.length === 0) {
                    listaHistorii.appendChild(element("li", "wyciszony", "Jeszcze nic nie sprawdzono."));
                }
                for (const wpis of wpisy) {
                    const li = element("li");
                    const przycisk = element("button", "wpis-historii");
                    przycisk.type = "button";
                    przycisk.append(
                        element("span", "identyfikator", wpis.dzialka_id),
                        element("span", wpis.przeznaczenie ? "etykieta etykieta--sukces" : "etykieta", wpis.przeznaczenie || "bez planu")
                    );
                    przycisk.addEventListener("click", () => sprawdzPunkt(wpis.lat, wpis.lon, true));
                    li.appendChild(przycisk);
                    listaHistorii.appendChild(li);
                }
            })
            .catch(() => {});
    }

    przyciskOdswiez.addEventListener("click", function () {
        przyciskOdswiez.disabled = true;
        przyciskOdswiez.textContent = "Odświeżanie danych Poznania…";

        fetch(URL_ODSWIEZ, { method: "POST" })
            .then((odpowiedz) => odpowiedz.json())
            .then((dane) => {
                if (dane.blad) {
                    pokazBlad(dane.blad);
                }
            })
            .catch(() => pokazBlad("Błąd połączenia z serwerem."))
            .finally(() => {
                przyciskOdswiez.disabled = false;
                przyciskOdswiez.textContent = "Odśwież dane Poznania";
            });
    });

    odswiezHistorie();
})();
