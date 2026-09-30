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

    // Inne usługi GUGiK (ETAP 89–90): nakładka w przełączniku warstw, jeśli usługa odpowie.
    for (const [klucz, nazwa, przezroczystosc] of [["plany_ogolne", "Plany ogólne gmin (strefy)", 0.6], ["ceny", "Ceny transakcyjne (RCN)", 1]]) {
        fetch(`${URL_USLUGA}${klucz}/warstwa`)
            .then((odpowiedz) => (odpowiedz.ok ? odpowiedz.json() : Promise.reject()))
            .then((opis) => kontrolkaWarstw.addOverlay(nakladkaWms(opis, przezroczystosc), nazwa))
            .catch(() => {});
    }

    const panelWyniku = document.getElementById("panel-wyniku");
    const przyciskOdswiez = document.getElementById("przycisk-odswiez");
    const formularzSzukaj = document.getElementById("szukaj-dzialki");
    const poleIdDzialki = document.getElementById("pole-id-dzialki");
    const listaHistorii = document.getElementById("historia");

    let warstwaDzialki = null;
    let warstwaWydzielenia = null;
    // ETAP 43: podpisy długości boków, wybrany front i obszar analizowany WZ.
    const warstwaBokow = L.layerGroup().addTo(mapa);
    const warstwaAnalizy = L.layerGroup().addTo(mapa);
    let numerAnalizy = 0;
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
        warstwaBokow.clearLayers();
        warstwaAnalizy.clearLayers();
        numerAnalizy += 1;
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
    let ostatniaOdpowiedz = null; // cała odpowiedź — punkt i przeznaczenie do „Moich działek”
    const zapisaneDzialki = new Map(); // id → wpis z serwera (ETAP 44)

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
        const raport = element("a", "przycisk przycisk--tekst", "Karta działki ↗");
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
        const kronika = element("a", "przycisk przycisk--tekst", "Kronika zmian");
        kronika.href = `${URL_KRONIKA}?id=${encodeURIComponent(dzialka.id)}`;
        kronika.title = "Ortofotomapy z różnych lat w miejscu tej działki";
        const linki = element("div", "rzad");
        linki.append(kalkulator, raport, kronika, geojson, geoportal);
        naglowek.append(element("h3", "", "Działka"), linki);
        sekcja.append(naglowek, element("div", "identyfikator wyciszony", dzialka.id));
        sekcja.appendChild(sekcjaZapisu(dzialka));
        if (dzialka.powierzchnia_m2) {
            sekcja.appendChild(
                element("div", "powierzchnia", `Powierzchnia: ${formatM2.format(dzialka.powierzchnia_m2)} m² (${(dzialka.powierzchnia_m2 / 10000).toLocaleString("pl-PL", { maximumFractionDigits: 4 })} ha)`)
            );
        }
        if (dzialka.wymiary) sekcja.appendChild(sekcjaWymiarow(dzialka));
        if (ostatnieWspolrzedne) sekcja.appendChild(sekcjaWspolrzednych(ostatnieWspolrzedne));
        return sekcja;
    }

    // ---------- Moje działki: gwiazdka i notatka (ETAP 44) ----------

    function przeznaczenieZOdpowiedzi(dane) {
        if (!dane) return null;
        if (dane.wydzielenie) return dane.wydzielenie.przeznaczenie || null;
        if (dane.plan_krajowy) return dane.plan_krajowy.przeznaczenie || "plan";
        return null;
    }

    async function wyslijZapis(dzialka, notatka) {
        const dane = ostatniaOdpowiedz && ostatniaOdpowiedz.dzialka && ostatniaOdpowiedz.dzialka.id === dzialka.id ? ostatniaOdpowiedz : null;
        const zapisany = zapisaneDzialki.get(dzialka.id);
        const punkt = dane ? dane.punkt : zapisany ? { lat: zapisany.lat, lon: zapisany.lon } : null;
        if (!punkt) throw new Error("Brak położenia działki.");
        const odpowiedz = await fetch(URL_ZAPISANE, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                id: dzialka.id,
                lat: punkt.lat,
                lon: punkt.lon,
                powierzchnia_m2: dzialka.powierzchnia_m2,
                przeznaczenie: dane ? przeznaczenieZOdpowiedzi(dane) : zapisany.przeznaczenie,
                notatka,
            }),
        });
        const wynik = await odpowiedz.json();
        if (!odpowiedz.ok) throw new Error(wynik.blad || `Błąd ${odpowiedz.status}`);
        zapisaneDzialki.set(wynik.dzialka_id, wynik);
        rysujZapisane();
        return wynik;
    }

    function sekcjaZapisu(dzialka) {
        const blok = element("div", "zapis-dzialki");
        const gwiazdka = element("button", "zapis-dzialki__gwiazdka");
        gwiazdka.type = "button";
        const notatka = element("textarea", "zapis-dzialki__notatka");
        notatka.rows = 2;
        notatka.maxLength = 2000;
        notatka.placeholder = "Notatka, np. „projekt z urbanistyki — wariant B”";
        const stan = element("span", "zapis-dzialki__stan wyciszony");
        // Zapis notatki w toku: usunięcie gwiazdki czeka na niego, inaczej
        // spóźniony zapis przywróciłby właśnie usuniętą działkę.
        let trwajacyZapis = Promise.resolve();

        const odswiez = () => {
            const wpis = zapisaneDzialki.get(dzialka.id);
            gwiazdka.textContent = wpis ? "★ W moich działkach" : "☆ Zapisz do moich działek";
            gwiazdka.classList.toggle("zapis-dzialki__gwiazdka--aktywna", Boolean(wpis));
            notatka.hidden = !wpis;
            if (wpis && document.activeElement !== notatka) notatka.value = wpis.notatka;
        };

        gwiazdka.addEventListener("click", async () => {
            gwiazdka.disabled = true;
            try {
                await trwajacyZapis.catch(() => {});
                if (zapisaneDzialki.has(dzialka.id)) {
                    const odpowiedz = await fetch(`${URL_ZAPISANE}?id=${encodeURIComponent(dzialka.id)}`, { method: "DELETE" });
                    if (!odpowiedz.ok && odpowiedz.status !== 404) throw new Error(`Błąd ${odpowiedz.status}`);
                    zapisaneDzialki.delete(dzialka.id);
                    rysujZapisane();
                } else {
                    await wyslijZapis(dzialka, "");
                    notatka.hidden = false;
                    notatka.focus();
                }
                stan.textContent = "";
            } catch (e) {
                stan.textContent = e.message;
            } finally {
                gwiazdka.disabled = false;
                odswiez();
            }
        });

        // Notatka zapisuje się sama po wyjściu z pola.
        notatka.addEventListener("change", async () => {
            stan.textContent = "Zapisuję…";
            trwajacyZapis = wyslijZapis(dzialka, notatka.value);
            try {
                await trwajacyZapis;
                stan.textContent = "Zapisano";
                setTimeout(() => (stan.textContent = ""), 1500);
            } catch (e) {
                stan.textContent = e.message;
            }
        });

        odswiez();
        blok.append(gwiazdka, notatka, stan);
        return blok;
    }

    const listaZapisanych = document.getElementById("zapisane");

    function rysujZapisane() {
        listaZapisanych.replaceChildren();
        if (zapisaneDzialki.size === 0) {
            listaZapisanych.appendChild(element("li", "wyciszony", "Zapisz działkę gwiazdką w panelu wyniku."));
            return;
        }
        for (const wpis of zapisaneDzialki.values()) {
            const li = element("li");
            const przycisk = element("button", "wpis-historii wpis-zapisany");
            przycisk.type = "button";
            const gora = element("span", "wpis-zapisany__gora");
            gora.append(
                element("span", "identyfikator", `★ ${wpis.dzialka_id}`),
                element("span", wpis.przeznaczenie ? "etykieta etykieta--sukces" : "etykieta", wpis.przeznaczenie || "bez planu")
            );
            przycisk.appendChild(gora);
            if (wpis.notatka) przycisk.appendChild(element("span", "wpis-zapisany__notatka", wpis.notatka));
            przycisk.addEventListener("click", () => sprawdzPunkt(wpis.lat, wpis.lon, true));
            li.appendChild(przycisk);
            listaZapisanych.appendChild(li);
        }
    }

    function wczytajZapisane() {
        fetch(URL_ZAPISANE)
            .then((odpowiedz) => odpowiedz.json())
            .then((wpisy) => {
                zapisaneDzialki.clear();
                for (const wpis of wpisy) zapisaneDzialki.set(wpis.dzialka_id, wpis);
                rysujZapisane();
            })
            .catch(() => {});
    }

    // ---------- wymiary działki i obszar analizowany WZ (ETAP 43) ----------

    const formatMetry = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 });
    const MIN_BOK_Z_PODPISEM_M = 2;
    const MAKS_PODPISOW = 40;
    const ZOOM_PODPISOW = 17;

    function rysujBoki(wymiary) {
        warstwaBokow.clearLayers();
        const boki = wymiary.boki.filter((b) => b.dlugosc_m >= MIN_BOK_Z_PODPISEM_M);
        if (boki.length > MAKS_PODPISOW) return; // działka o bardzo krętej granicy — bez podpisów
        for (const bok of boki) {
            warstwaBokow.addLayer(
                L.tooltip({ permanent: true, direction: "center", className: "etykieta-boku", interactive: false })
                    .setLatLng(bok.srodek)
                    .setContent(`${formatMetry.format(bok.dlugosc_m)} m`)
            );
        }
    }

    // Podpisy boków tylko przy dużym przybliżeniu — inaczej się nakładają.
    function przelaczPodpisy() {
        mapa.getContainer().classList.toggle("mapa--bez-podpisow", mapa.getZoom() < ZOOM_PODPISOW);
    }
    mapa.on("zoomend", przelaczPodpisy);
    przelaczPodpisy();

    function sekcjaWymiarow(dzialka) {
        const w = dzialka.wymiary;
        const szczegoly = element("details", "wymiary");
        szczegoly.appendChild(element("summary", "", "Wymiary i obszar analizowany (WZ)"));

        const liczby = element("div", "wymiary__liczby");
        const liczba = (etykieta, wartosc, opis) => {
            const div = element("div", "wymiary__liczba");
            if (opis) div.title = opis;
            div.append(element("span", "wymiary__etykieta", etykieta), element("strong", "", wartosc));
            liczby.appendChild(div);
        };
        liczba("Szerokość × głębokość", `${formatMetry.format(w.szerokosc_m)} × ${formatMetry.format(w.glebokosc_m)} m`, "Boki najmniejszego prostokąta opisanego na działce");
        liczba("Obwód", `${formatMetry.format(w.obwod_m)} m`);
        liczba("Liczba boków", String(w.boki.length), "Po uproszczeniu granicy o 20 cm");
        if (w.zwartosc !== null) {
            liczba("Zwartość", w.zwartosc.toLocaleString("pl-PL"), "4π·P / obwód² — 1 dla koła, ok. 0,79 dla kwadratu; mało = działka wąska albo postrzępiona");
        }
        szczegoly.appendChild(liczby);

        // Obszar analizowany: front = bok od strony drogi, którą wskazuje student.
        const front = element("label", "wymiary__front", "Front działki (bok od strony drogi)");
        const wybor = element("select");
        wybor.appendChild(new Option(`szerokość działki — ${formatMetry.format(w.szerokosc_m)} m`, "szerokosc"));
        for (const bok of w.boki) wybor.appendChild(new Option(`bok ${bok.nr} — ${formatMetry.format(bok.dlugosc_m)} m`, String(bok.nr)));
        front.appendChild(wybor);
        const przycisk = element("button", "przycisk--drugi", "Pokaż obszar analizowany");
        przycisk.type = "button";
        const wynik = element("p", "wymiary__wynik wyciszony");
        const przypis = element(
            "p",
            "przypis",
            "Obszar analizowany do decyzji o warunkach zabudowy: wokół działki, w odległości co najmniej 3 × szerokość frontu, nie mniej niż 50 m (§ 3 ust. 2 rozporządzenia z 26.08.2003). Sprawdź aktualne przepisy — nowelizacja z 2023 r. zmieniła zasady wydawania WZ."
        );

        const dlugoscFrontu = () =>
            wybor.value === "szerokosc" ? w.szerokosc_m : w.boki.find((b) => String(b.nr) === wybor.value).dlugosc_m;

        wybor.addEventListener("change", () => {
            warstwaAnalizy.clearLayers();
            numerAnalizy += 1;
            wynik.textContent = "";
            if (wybor.value === "szerokosc") return;
            const bok = w.boki.find((b) => String(b.nr) === wybor.value);
            L.polyline([bok.od, bok.do], { color: "#ff375f", weight: 6, opacity: 0.9, interactive: false }).addTo(warstwaAnalizy);
        });

        przycisk.addEventListener("click", async () => {
            const numer = ++numerAnalizy;
            wynik.textContent = "Liczę…";
            try {
                const odpowiedz = await fetch(URL_OBSZAR_ANALIZOWANY, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ geometria: dzialka.geometria, front: dlugoscFrontu() }),
                });
                const dane = await odpowiedz.json();
                if (numer !== numerAnalizy) return;
                if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
                warstwaAnalizy.eachLayer((l) => {
                    if (l instanceof L.GeoJSON) warstwaAnalizy.removeLayer(l);
                });
                const obszar = L.geoJSON(dane.geometria, {
                    style: { color: "#bf5af2", weight: 2, dashArray: "8 6", fillOpacity: 0.06 },
                    interactive: false,
                }).addTo(warstwaAnalizy);
                mapa.fitBounds(obszar.getBounds(), { padding: [20, 20] });
                wynik.textContent =
                    `Odległość: ${formatMetry.format(dane.odleglosc_m)} m` +
                    (dane.z_minimum ? " (minimum 50 m, bo 3 × front jest mniej)" : ` (3 × ${formatMetry.format(dlugoscFrontu())} m)`) +
                    ` · powierzchnia obszaru ${(dane.powierzchnia_m2 / 10000).toLocaleString("pl-PL", { maximumFractionDigits: 2 })} ha.`;
            } catch (e) {
                if (numer === numerAnalizy) wynik.textContent = e.message;
            }
        });

        szczegoly.append(front, przycisk, wynik, przypis);
        return szczegoly;
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
        for (const { symbol, opis, zwyczajowe } of opisy) {
            const li = element("li");
            li.append(element("span", "etykieta etykieta--sukces", symbol), element("span", opis ? "" : "wyciszony", opis || "brak w słowniku — sprawdź legendę planu"));
            if (zwyczajowe) {
                const znak = element("span", "etykieta", "zwyczajowe");
                znak.title = "Oznaczenie spoza rozporządzenia z 2003 r. — znaczenie ustala legenda planu";
                li.appendChild(znak);
            }
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

    // Informacje innej usługi GUGiK w punkcie działki (ETAP 89–90).
    // Pobierane dopiero po rozwinięciu — nie spowalniają sprawdzania działki.
    function sekcjaUslugi(klucz, tytul, przypis, punkt) {
        const szczegoly = element("details", "usluga-w-punkcie");
        szczegoly.appendChild(element("summary", "", tytul));
        const tresc = element("div", "stos");
        szczegoly.appendChild(tresc);
        let pobrane = false;
        szczegoly.addEventListener("toggle", async () => {
            if (!szczegoly.open || pobrane) return;
            pobrane = true;
            tresc.replaceChildren(element("p", "wyciszony", "Sprawdzam w usłudze GUGiK…"));
            try {
                const odpowiedz = await fetch(`${URL_USLUGA}${klucz}/punkt?lat=${punkt.lat}&lon=${punkt.lon}`);
                const dane = await odpowiedz.json();
                if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
                tresc.replaceChildren();
                if (!dane.obiekty.length) {
                    tresc.appendChild(element("p", "wyciszony", "Usługa nie ma tu żadnych obiektów."));
                }
                for (const obiekt of dane.obiekty) {
                    const tabela = element("table", "tabela");
                    for (const [k, v] of Object.entries(obiekt.atrybuty)) {
                        const wiersz = element("tr");
                        wiersz.append(element("th", "", k), element("td", "", v));
                        tabela.appendChild(wiersz);
                    }
                    tresc.appendChild(tabela);
                }
                dane.linki.forEach((adres, i) => {
                    const a = element("a", "przycisk przycisk--tekst", dane.linki.length > 1 ? `Dokument ${i + 1} ↗` : "Dokument ↗");
                    a.href = adres;
                    a.target = "_blank";
                    a.rel = "noopener noreferrer";
                    tresc.appendChild(a);
                });
            } catch (e) {
                pobrane = false; // przy następnym rozwinięciu spróbuj jeszcze raz
                tresc.replaceChildren(element("p", "komunikat komunikat--blad", e.message));
            }
            tresc.appendChild(element("p", "przypis", przypis));
        });
        return szczegoly;
    }

    function sekcjeUslug(punkt) {
        return [
            sekcjaUslugi("plany_ogolne", "Plan ogólny gminy", "Źródło: plany ogólne gmin w usłudze GUGiK — na razie tylko gminy, które już uchwaliły plan ogólny. Atrybuty jak w usłudze; rozstrzyga uchwała.", punkt),
            sekcjaUslugi("ceny", "Ceny transakcyjne (RCN)", "Źródło: Rejestr Cen Nieruchomości (GUGiK) — transakcje obejmujące to miejsce, atrybuty jak w usłudze. Transakcje w okolicy zobaczysz, włączając warstwę „Ceny transakcyjne (RCN)” na mapie.", punkt),
        ];
    }

    // Wspólna obsługa odpowiedzi z /sprawdz i /dzialka.
    function obsluzOdpowiedz(dane, przyblizDoDzialki) {
        wyczyscWarstwy();
        ostatnieWspolrzedne = dane.wspolrzedne || null;
        ostatniaOdpowiedz = dane;
        if (dane.dzialka) {
            warstwaDzialki = L.geoJSON(dane.dzialka.geometria, {
                style: { color: "#0071e3", weight: 2, fillOpacity: 0.1 },
            }).addTo(mapa);
            if (przyblizDoDzialki) mapa.fitBounds(warstwaDzialki.getBounds(), { maxZoom: 18, padding: [40, 40] });
            if (dane.dzialka.wymiary) rysujBoki(dane.dzialka.wymiary);
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
        if (dane.dzialka && dane.punkt) panelWyniku.append(...sekcjeUslug(dane.punkt));
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
    wczytajZapisane();
})();
