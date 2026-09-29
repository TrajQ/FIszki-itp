// Moduł dostępność: rysuje gotowe wyniki na siatce H3. Klasy, statystyki
// i udziały liczy serwer (dostepnosc/wyniki.py); tu tylko rysujemy.
(function () {
    "use strict";

    // Czas dojścia: zielony (blisko) → czerwony (daleko). 6 klas: ≤5, ≤10, ≤15, ≤20, ≤30, >30 min.
    const KOLORY_MINUT = ["#30d158", "#a3d94f", "#ffd60a", "#ff9f0a", "#ff6b3d", "#d70015"];
    // Inne wskaźniki: skala sekwencyjna niebieska.
    const KOLORY_INNE = ["#d6e8ff", "#9ecbff", "#5aa7ff", "#1f7ae0", "#0b4fa8", "#062f66"];

    const poleKolumna = document.getElementById("pole-kolumna");
    const kafelki = document.getElementById("kafelki");
    const metaPliku = document.getElementById("meta-pliku");
    const ogniwoEl = document.getElementById("ogniwo");
    const listaOgniw = document.getElementById("lista-ogniw");
    const WARTOSC_LACZNY = "__laczny__";
    const linkGeojson = document.getElementById("link-geojson");

    // Link „GeoJSON do QGIS” zawsze odpowiada temu, co widać na mapie.
    function ustawLinkGeojson(po) {
        const kolumna = poleKolumna.value === WARTOSC_LACZNY ? "laczny" : poleKolumna.value;
        const parametry = new URLSearchParams({ plik: NAZWA_PLIKU, kolumna });
        if (po) parametry.set("po", po);
        linkGeojson.href = `${URL_GEOJSON}?${parametry}`;
        // Raport do druku jest dla jednego wskaźnika — w porównaniu scenariuszy ukryty.
        const linkRaport = document.getElementById("link-raport");
        linkRaport.hidden = Boolean(po);
        linkRaport.href = `${URL_RAPORT}?${new URLSearchParams({ plik: NAZWA_PLIKU, kolumna })}`;
    }
    // Zmiana czasu (po − przed): szybciej = niebieski, wolniej = pomarańczowy, szary = bez zmian.
    const KOLORY_ZMIANY = ["#1d4ed8", "#60a5fa", "#d1d1d6", "#fb923c", "#c2410c"];
    const poleScenariusz = document.getElementById("pole-scenariusz");
    const przyciskPorownaj = document.getElementById("przycisk-porownaj");
    const trybPorownania = document.getElementById("tryb-porownania");
    const opisPorownania = document.getElementById("opis-porownania");
    const formatProcentu = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });
    const formatZmiany = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1, signDisplay: "exceptZero" });
    const legenda = document.getElementById("legenda");
    const krzywaBlok = document.getElementById("krzywa-blok");
    const krzywaSvg = document.getElementById("krzywa");
    const suwakProgu = document.getElementById("suwak-progu");
    const wartoscProgu = document.getElementById("wartosc-progu");
    const wynikProgu = document.getElementById("wynik-progu");
    const lukiBlok = document.getElementById("luki-blok");
    const listaLuk = document.getElementById("lista-luk");
    const opisLuk = document.getElementById("opis-luk");
    let biezacaKrzywa = null;
    const komunikat = document.getElementById("komunikat");

    const formatLiczby = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });
    const urlPliku = URL_PLIK.replace("__PLIK__", encodeURIComponent(NAZWA_PLIKU));

    const mapa = L.map("mapa-dostepnosci", { zoomSnap: 0.25 }).setView([52.4064, 16.9252], 12);
    // Podkłady (ETAP 34). OSM wymaga nagłówka Referer — bez niego zwraca
    // kafelki „Access blocked”, a nasz Referrer-Policy: same-origin go
    // wycina. Dlatego kafelki OSM dostają własną, łagodniejszą politykę
    // (wysyłany jest tylko adres http://127.0.0.1:port, bez ścieżki).
    const PODKLADY = {
        "Mapa (OpenStreetMap)": L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap, siatka: H3",
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
    const KLUCZ_PODKLADU = "dostepnosc.podklad";
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
    L.control.layers(PODKLADY, {}, { position: "topright" }).addTo(mapa);

    let warstwa = null;
    let pierwszeRysowanie = true;

    async function pobierzJson(url) {
        const odpowiedz = await fetch(url);
        const dane = await odpowiedz.json().catch(() => ({}));
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        return dane;
    }

    function pokazBlad(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    function kolory(analiza) {
        if (analiza.minuty) return KOLORY_MINUT;
        // Mniej klas niż kolorów: bierzemy równomiernie z całej skali.
        const liczbaKlas = analiza.progi.length + 1;
        return Array.from({ length: liczbaKlas }, (_, i) =>
            KOLORY_INNE[liczbaKlas === 1 ? 3 : Math.round((i * (KOLORY_INNE.length - 1)) / (liczbaKlas - 1))]
        );
    }

    function kafelek(etykieta, wartosc, dopisek) {
        const div = document.createElement("div");
        div.className = "kafelek-maly";
        const e = document.createElement("span");
        e.className = "kafelek-maly__etykieta";
        e.textContent = etykieta;
        const w = document.createElement("span");
        w.className = "kafelek-maly__wartosc";
        w.textContent = wartosc;
        div.append(e, w);
        if (dopisek) {
            const d = document.createElement("span");
            d.className = "kafelek-maly__dopisek";
            d.textContent = dopisek;
            div.appendChild(d);
        }
        return div;
    }

    function pokazStatystyki(analiza) {
        const s = analiza.statystyki;
        const jednostka = analiza.minuty ? " min" : "";
        kafelki.replaceChildren();
        if (analiza.minuty) {
            for (const u of s.udzialy) {
                // Z kolumną ludności: główna liczba to % mieszkańców, obok % powierzchni.
                if (u.procent_ludnosci !== undefined && u.procent_ludnosci !== null) {
                    kafelki.appendChild(
                        kafelek(
                            `Do ${u.prog} min`,
                            `${formatLiczby.format(u.procent_ludnosci)}% mieszk.`,
                            `${formatLiczby.format(u.ludnosc)} os. · ${formatLiczby.format(u.procent)}% pow.`
                        )
                    );
                } else {
                    kafelki.appendChild(
                        kafelek(`Do ${u.prog} min`, `${formatLiczby.format(u.procent)}%`, `${formatLiczby.format(u.powierzchnia_km2)} km²`)
                    );
                }
            }
        }
        kafelki.appendChild(kafelek("Mediana", formatLiczby.format(s.mediana) + jednostka));
        kafelki.appendChild(kafelek("Maksimum", formatLiczby.format(s.max) + jednostka));
        kafelki.appendChild(kafelek("Komórki", formatLiczby.format(s.liczba_komorek)));

        metaPliku.textContent =
            `Rozdzielczość H3: ${s.rozdzielczosc} (śr. ${formatLiczby.format(s.pole_komorki_km2 * 100)} ha na komórkę)` +
            (s.komorki_bez_wartosci ? ` · bez wartości: ${s.komorki_bez_wartosci}` : "");
    }

    function pokazLegende(analiza, paleta) {
        legenda.replaceChildren();
        const tytul = document.createElement("div");
        tytul.className = "legenda__tytul";
        tytul.textContent = analiza.najslabsze_ogniwo ? "czas do wszystkich usług" : analiza.minuty ? "czas dojścia" : analiza.kolumna;
        legenda.appendChild(tytul);

        const p = analiza.progi;
        const s = analiza.statystyki;
        const jednostka = analiza.minuty ? " min" : "";
        for (let i = 0; i <= p.length; i += 1) {
            let opis;
            if (i === 0) opis = `≤ ${formatLiczby.format(p[0] ?? s.max)}${jednostka}`;
            else if (i === p.length) opis = `> ${formatLiczby.format(p[i - 1])}${jednostka}`;
            else opis = `${formatLiczby.format(p[i - 1])} – ${formatLiczby.format(p[i])}${jednostka}`;
            const wiersz = document.createElement("div");
            wiersz.className = "legenda__wiersz";
            const kolor = document.createElement("span");
            kolor.className = "legenda__kolor";
            kolor.style.background = paleta[i];
            wiersz.append(kolor, opis);
            legenda.appendChild(wiersz);
        }
    }

    async function pokazKolumne(kolumna) {
        pokazBlad("");
        let analiza;
        try {
            const adres = kolumna === WARTOSC_LACZNY ? `${urlPliku}/laczny` : `${urlPliku}/${encodeURIComponent(kolumna)}`;
            analiza = await pobierzJson(adres);
        } catch (e) {
            pokazBlad(e.message);
            return;
        }
        const paleta = kolory(analiza);
        const jednostka = analiza.minuty ? " min" : "";

        if (warstwa) mapa.removeLayer(warstwa);
        warstwa = L.geoJSON(analiza.geojson, {
            style: (cecha) => ({
                color: paleta[cecha.properties.klasa],
                weight: 0.5,
                fillColor: paleta[cecha.properties.klasa],
                fillOpacity: 0.72,
            }),
            onEachFeature: (cecha, w) => {
                w.bindTooltip(`${formatLiczby.format(cecha.properties.wartosc)}${jednostka}`, { sticky: true });
                w.on("mouseover", () => w.setStyle({ weight: 2.5, color: "#1d1d1f" }));
                w.on("mouseout", () => warstwa.resetStyle(w));
                w.on("click", (e) => {
                    if (!wstawianie) pokazKomorke(cecha.properties.h3, e.latlng);
                });
            },
        }).addTo(mapa);
        if (pierwszeRysowanie) {
            mapa.fitBounds(warstwa.getBounds(), { padding: [16, 16] });
            pierwszeRysowanie = false;
        }
        pokazStatystyki(analiza);
        pokazLegende(analiza, paleta);
        pokazOgniwo(analiza);
        pokazKrzywa(analiza);
        pokazLuki(analiza);
        ustawLinkGeojson(null);
    }

    // ---------- krzywa dostępności i własny próg (ETAP 38) ----------
    // Punkty krzywej (udział w zasięgu t minut) liczy serwer; tu je rysujemy
    // i czytamy wartość dla minuty wybranej suwakiem.

    const SVG = "http://www.w3.org/2000/svg";
    const WYKRES = { lewo: 34, prawo: 312, gora: 8, dol: 146 };

    function svg(tag, atrybuty, tekst) {
        const el = document.createElementNS(SVG, tag);
        for (const [k, v] of Object.entries(atrybuty)) el.setAttribute(k, v);
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function pokazKrzywa(analiza) {
        const krzywa = analiza.minuty ? analiza.statystyki.krzywa : null;
        krzywaBlok.hidden = !krzywa || krzywa.length < 2;
        biezacaKrzywa = krzywaBlok.hidden ? null : krzywa;
        if (!biezacaKrzywa) return;

        const maksMin = krzywa[krzywa.length - 1].minuty;
        const x = (m) => WYKRES.lewo + ((WYKRES.prawo - WYKRES.lewo) * m) / maksMin;
        const y = (p) => WYKRES.dol - ((WYKRES.dol - WYKRES.gora) * p) / 100;
        krzywaSvg.replaceChildren();

        for (const p of [0, 50, 100]) {
            krzywaSvg.append(
                svg("line", { x1: WYKRES.lewo, x2: WYKRES.prawo, y1: y(p), y2: y(p), class: "krzywa__siatka" }),
                svg("text", { x: WYKRES.lewo - 6, y: y(p) + 4, class: "krzywa__os", "text-anchor": "end" }, `${p}%`)
            );
        }
        const krok = maksMin > 30 ? 15 : 5;
        for (let m = 0; m <= maksMin; m += krok) {
            krzywaSvg.append(svg("text", { x: x(m), y: WYKRES.dol + 16, class: "krzywa__os", "text-anchor": m === 0 ? "start" : x(m) > WYKRES.prawo - 20 ? "end" : "middle" }, `${m} min`));
        }

        const linia = (klucz, klasa) => {
            const punkty = krzywa.filter((p) => p[klucz] !== undefined && p[klucz] !== null).map((p) => `${x(p.minuty)},${y(p[klucz])}`);
            if (punkty.length > 1) krzywaSvg.append(svg("polyline", { points: punkty.join(" "), class: klasa }));
        };
        linia("procent", "krzywa__linia");
        linia("procent_ludnosci", "krzywa__linia krzywa__linia--ludnosc");
        krzywaSvg.append(svg("line", { id: "znacznik-progu", y1: WYKRES.gora, y2: WYKRES.dol, class: "krzywa__znacznik" }));

        suwakProgu.max = String(maksMin);
        if (Number(suwakProgu.value) > maksMin) suwakProgu.value = String(Math.min(15, maksMin));
        pokazProg();
    }

    function pokazProg() {
        if (!biezacaKrzywa) return;
        const minuty = Number(suwakProgu.value);
        const punkt = biezacaKrzywa[Math.min(minuty, biezacaKrzywa.length - 1)];
        const maksMin = biezacaKrzywa[biezacaKrzywa.length - 1].minuty;
        const pozycja = WYKRES.lewo + ((WYKRES.prawo - WYKRES.lewo) * punkt.minuty) / maksMin;
        const znacznik = document.getElementById("znacznik-progu");
        znacznik.setAttribute("x1", pozycja);
        znacznik.setAttribute("x2", pozycja);
        wartoscProgu.textContent = `${punkt.minuty} min`;
        let tekst = `${formatProcentu.format(punkt.procent)}% powierzchni`;
        if (punkt.procent_ludnosci !== undefined && punkt.procent_ludnosci !== null) {
            tekst += ` · ${formatProcentu.format(punkt.procent_ludnosci)}% mieszkańców (${formatLiczby.format(punkt.ludnosc)} os.)`;
        }
        wynikProgu.textContent = `${tekst} w zasięgu ${punkt.minuty} min.`;
    }

    suwakProgu.addEventListener("input", pokazProg);

    // ---------- luki: gdzie brakuje usługi (ETAP 38) ----------

    function pokazLuki(analiza) {
        const luki = analiza.minuty ? analiza.statystyki.luki : null;
        lukiBlok.hidden = !luki;
        if (!luki) return;
        listaLuk.replaceChildren();
        const zLudnoscia = luki.length > 0 && luki[0].ludnosc !== undefined;
        opisLuk.textContent = luki.length
            ? zLudnoscia
                ? "Komórki dalej niż 15 min, w których mieszka najwięcej osób — tu nowa usługa pomogłaby najbardziej."
                : "Komórki najdalej od usługi (powyżej 15 min). Dodaj kolumnę ludnosc, żeby uwzględnić mieszkańców."
            : "Żadna komórka (zamieszkana, jeśli plik podaje ludność) nie jest dalej niż 15 min.";
        for (const luka of luki) {
            const li = document.createElement("li");
            const przycisk = document.createElement("button");
            przycisk.type = "button";
            przycisk.className = "luka";
            const czas = document.createElement("strong");
            czas.textContent = `${formatLiczby.format(luka.wartosc)} min`;
            const opis = document.createElement("span");
            opis.className = "wyciszony";
            opis.textContent = zLudnoscia ? `${formatLiczby.format(luka.ludnosc)} mieszk.` : luka.h3;
            przycisk.append(czas, opis);
            przycisk.addEventListener("click", () => {
                mapa.setView([luka.lat, luka.lon], Math.max(mapa.getZoom(), 15));
                pokazKomorke(luka.h3, L.latLng(luka.lat, luka.lon));
            });
            li.appendChild(przycisk);
            listaLuk.appendChild(li);
        }
    }

    // ---------- szczegóły komórki po kliknięciu (ETAP 38) ----------

    let numerKomorki = 0;

    async function pokazKomorke(indeks, miejsce) {
        const numer = ++numerKomorki;
        let dane;
        try {
            dane = await pobierzJson(URL_KOMORKA.replace("__PLIK__", encodeURIComponent(NAZWA_PLIKU)).replace("__H3__", encodeURIComponent(indeks)));
        } catch (e) {
            return;
        }
        if (numer !== numerKomorki) return;
        const tresc = document.createElement("div");
        tresc.className = "okno-komorki";
        const tytul = document.createElement("div");
        tytul.className = "okno-komorki__tytul";
        tytul.textContent = `Komórka ${dane.h3}`;
        const tabela = document.createElement("table");
        const wiersz = (nazwa, wartosc) => {
            const tr = document.createElement("tr");
            const th = document.createElement("th");
            th.textContent = nazwa;
            const td = document.createElement("td");
            td.textContent = wartosc;
            tr.append(th, td);
            tabela.appendChild(tr);
        };
        for (const [nazwa, wartosc] of Object.entries(dane.wartosci)) {
            wiersz(nazwa, wartosc === null ? "—" : formatLiczby.format(wartosc) + (dane.minuty[nazwa] ? " min" : ""));
        }
        if (dane.czas_laczny !== undefined) wiersz("wszystkie usługi", dane.czas_laczny === null ? "—" : `${formatLiczby.format(dane.czas_laczny)} min`);
        if (dane.ludnosc !== undefined) wiersz("mieszkańcy", formatLiczby.format(dane.ludnosc));
        tresc.append(tytul, tabela);
        L.popup({ maxWidth: 320 }).setLatLng(miejsce).setContent(tresc).openOn(mapa);
    }

    // Tylko dla wskaźnika łącznego: która usługa najczęściej jest najdalej.
    function pokazOgniwo(analiza) {
        ogniwoEl.hidden = !analiza.najslabsze_ogniwo;
        if (!analiza.najslabsze_ogniwo) return;
        listaOgniw.replaceChildren();
        for (const o of analiza.najslabsze_ogniwo) {
            const li = document.createElement("li");
            const nazwa = document.createElement("span");
            nazwa.textContent = o.kolumna;
            const tor = document.createElement("span");
            tor.className = "ogniwo__tor";
            const slupek = document.createElement("span");
            slupek.className = "ogniwo__slupek";
            slupek.style.width = `${o.procent}%`;
            tor.appendChild(slupek);
            const procent = document.createElement("span");
            procent.className = "ogniwo__procent";
            procent.textContent = `${formatLiczby.format(o.procent)}%`;
            li.append(nazwa, tor, procent);
            listaOgniw.appendChild(li);
        }
    }

    poleKolumna.addEventListener("change", () => {
        if (!trybPorownania.hidden) porownaj();
        else pokazKolumne(poleKolumna.value);
    });

    // ---------- porównanie scenariuszy ----------

    poleScenariusz.addEventListener("change", () => {
        przyciskPorownaj.disabled = !poleScenariusz.value;
    });
    przyciskPorownaj.addEventListener("click", porownaj);
    document.getElementById("zakoncz-porownanie").addEventListener("click", () => {
        trybPorownania.hidden = true;
        pokazKolumne(poleKolumna.value);
    });

    async function porownaj() {
        if (!poleScenariusz.value) return;
        pokazBlad("");
        const kolumna = poleKolumna.value === WARTOSC_LACZNY ? "laczny" : poleKolumna.value;
        const parametry = new URLSearchParams({ przed: NAZWA_PLIKU, po: poleScenariusz.value, kolumna });
        let wynik;
        try {
            wynik = await pobierzJson(`${URL_POROWNANIE}?${parametry}`);
        } catch (e) {
            pokazBlad(e.message);
            return;
        }
        trybPorownania.hidden = false;
        ustawLinkGeojson(poleScenariusz.value);
        opisPorownania.textContent = `Porównanie: ${NAZWA_PLIKU} → ${poleScenariusz.value}`;
        ogniwoEl.hidden = true;
        krzywaBlok.hidden = true;
        lukiBlok.hidden = true;
        biezacaKrzywa = null;

        if (warstwa) mapa.removeLayer(warstwa);
        warstwa = L.geoJSON(wynik.geojson, {
            style: (cecha) => ({
                color: KOLORY_ZMIANY[cecha.properties.klasa],
                weight: 0.5,
                fillColor: KOLORY_ZMIANY[cecha.properties.klasa],
                fillOpacity: 0.75,
            }),
            onEachFeature: (cecha, w) => {
                const p = cecha.properties;
                w.bindTooltip(
                    `${formatLiczby.format(p.przed)} → ${formatLiczby.format(p.po)} min (${formatZmiany.format(p.zmiana)})`,
                    { sticky: true }
                );
            },
        }).addTo(mapa);

        const s = wynik.statystyki;
        kafelki.replaceChildren(
            kafelek(
                "W zasięgu 15 min",
                `${formatProcentu.format(s.procent_15_przed)} → ${formatProcentu.format(s.procent_15_po)}%`,
                `powierzchni; komórek +${s.komorki_weszly_15}` + (s.komorki_wypadly_15 ? `, −${s.komorki_wypadly_15}` : "")
            ),
            kafelek(
                "Poprawa ≥ 1 min",
                `${s.poprawa}`,
                `z ${s.liczba_komorek} komórek; gorzej: ${s.pogorszenie}`
            ),
            kafelek("Mediana zmiany", `${formatZmiany.format(s.mediana_zmiany)} min`),
            kafelek("Największa poprawa", `${formatZmiany.format(s.najwieksza_poprawa)} min`)
        );
        if (s.ludnosc_weszla_15 !== undefined) {
            kafelki.appendChild(
                kafelek("Mieszkańcy, którzy zyskali 15 min", `+${formatLiczby.format(s.ludnosc_weszla_15)}`,
                    s.ludnosc_wypadla_15 ? `stracili: ${formatLiczby.format(s.ludnosc_wypadla_15)}` : "")
            );
        }
        metaPliku.textContent = "Kolor = zmiana czasu dojścia po zmianie (niebieski: szybciej, pomarańczowy: wolniej).";

        legenda.replaceChildren();
        const tytul = document.createElement("div");
        tytul.className = "legenda__tytul";
        tytul.textContent = "zmiana czasu dojścia";
        legenda.appendChild(tytul);
        const opisy = ["szybciej o ≥ 5 min", "szybciej o 1–5 min", "bez zmian (±1 min)", "wolniej o 1–5 min", "wolniej o > 5 min"];
        opisy.forEach((opis, i) => {
            const wiersz = document.createElement("div");
            wiersz.className = "legenda__wiersz";
            const kolor = document.createElement("span");
            kolor.className = "legenda__kolor";
            kolor.style.background = KOLORY_ZMIANY[i];
            wiersz.append(kolor, opis);
            legenda.appendChild(wiersz);
        });
    }

    // ---------- szybki model: punkty usług na mapie (ETAP 47) ----------
    // Liczy serwer (dostepnosc/model.py); tu tylko zbieramy punkty.

    const modelUsluga = document.getElementById("model-usluga");
    const modelSiatka = document.getElementById("model-siatka");
    const modelPredkosc = document.getElementById("model-predkosc");
    const modelKretosc = document.getElementById("model-kretosc");
    const modelWstawiaj = document.getElementById("model-wstawiaj");
    const modelWyczysc = document.getElementById("model-wyczysc");
    const modelStan = document.getElementById("model-stan");
    const modelPolicz = document.getElementById("model-policz");
    const modelBlad = document.getElementById("model-blad");
    const warstwaPunktow = L.layerGroup().addTo(mapa);
    const punktyModelu = []; // [{latlng, znacznik}]
    let wstawianie = false;

    function ikonaPunktu(nr) {
        return L.divIcon({ className: "punkt-uslugi", html: `<span>${nr}</span>`, iconSize: [26, 26] });
    }

    function odswiezPunkty() {
        punktyModelu.forEach((p, i) => p.znacznik.setIcon(ikonaPunktu(i + 1)));
        modelStan.textContent = wstawianie
            ? `Punkty: ${punktyModelu.length} — klikaj na mapie; klik w punkt go usuwa.`
            : `Punkty: ${punktyModelu.length}`;
        modelWyczysc.hidden = punktyModelu.length === 0;
        modelPolicz.disabled = punktyModelu.length === 0;
    }

    function ustawWstawianie(wlacz) {
        wstawianie = wlacz;
        modelWstawiaj.textContent = wlacz ? "Zakończ wstawianie" : "Wstawiaj punkty";
        modelWstawiaj.classList.toggle("model__wstawiaj--aktywny", wlacz);
        mapa.getContainer().classList.toggle("mapa--wstawianie", wlacz);
        odswiezPunkty();
    }

    function dodajPunkt(latlng) {
        const znacznik = L.marker(latlng, { icon: ikonaPunktu(punktyModelu.length + 1), keyboard: false }).addTo(warstwaPunktow);
        const wpis = { latlng, znacznik };
        znacznik.on("click", () => {
            if (!wstawianie) return;
            warstwaPunktow.removeLayer(znacznik);
            punktyModelu.splice(punktyModelu.indexOf(wpis), 1);
            odswiezPunkty();
        });
        punktyModelu.push(wpis);
        odswiezPunkty();
    }

    // Kliknięcie w heksagon w trybie wstawiania ma dodać punkt, a nie
    // otwierać okienko komórki — sprawdzamy tryb w obu miejscach.
    mapa.on("click", (e) => {
        if (wstawianie) dodajPunkt(e.latlng);
    });

    modelWstawiaj.addEventListener("click", () => {
        ustawWstawianie(!wstawianie);
        // Na wąskim ekranie mapa jest nad panelem — pokaż ją.
        const ramka = mapa.getContainer().getBoundingClientRect();
        if (wstawianie && (ramka.bottom < 80 || ramka.top > window.innerHeight - 80)) {
            mapa.getContainer().scrollIntoView({ behavior: "smooth", block: "center" });
        }
    });
    modelWyczysc.addEventListener("click", () => {
        warstwaPunktow.clearLayers();
        punktyModelu.length = 0;
        odswiezPunkty();
    });

    modelPolicz.addEventListener("click", async () => {
        modelBlad.hidden = true;
        modelPolicz.disabled = true;
        modelPolicz.textContent = "Liczę…";
        const granice = mapa.getBounds();
        const zapytanie = {
            usluga: modelUsluga.value,
            punkty: punktyModelu.map((p) => [p.latlng.lat, p.latlng.lng]),
            predkosc_kmh: modelPredkosc.value,
            kretosc: modelKretosc.value,
        };
        if (modelSiatka.value === "plik") zapytanie.baza = NAZWA_PLIKU;
        else zapytanie.obszar = [granice.getSouth(), granice.getWest(), granice.getNorth(), granice.getEast()];
        try {
            const odpowiedz = await fetch(URL_Z_PUNKTOW, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(zapytanie),
            });
            const dane = await odpowiedz.json();
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            window.location.href = `${URL_INDEKS}?plik=${encodeURIComponent(dane.plik)}`;
        } catch (e) {
            modelBlad.textContent = e.message;
            modelBlad.hidden = false;
            modelPolicz.disabled = false;
            modelPolicz.textContent = "Policz i zapisz jako nowy plik";
        }
    });

    // Plik policzony z punktów: pokaż punkty i obszary obsługi.
    function pokazObszaryObslugi(punkty) {
        const sekcja = document.getElementById("obszary-obslugi");
        sekcja.hidden = !punkty;
        if (!punkty) return;
        const zLudnoscia = punkty.obszary.length > 0 && punkty.obszary[0].ludnosc !== undefined;
        document.getElementById("obszary-opis").textContent =
            `Usługa „${punkty.usluga}” (${punkty.kolumna}), ${formatLiczby.format(punkty.predkosc_kmh)} km/h, krętość ${formatLiczby.format(punkty.kretosc)}. ` +
            "Każda komórka należy do obszaru najbliższego punktu" +
            (zLudnoscia ? " — stąd liczba mieszkańców na placówkę." : ". Bez kolumny ludnosc w pliku bazowym nie ma liczby mieszkańców.");
        const lista = document.getElementById("lista-obszarow");
        lista.replaceChildren();
        const warstwa = L.layerGroup().addTo(mapa);
        for (const o of punkty.obszary) {
            const tr = document.createElement("tr");
            tr.title = `Komórek w obszarze: ${o.komorki}`;
            const komorki = [
                `${o.nr}`,
                zLudnoscia ? formatLiczby.format(o.ludnosc) : "—",
                o.sredni_czas_min === null ? "—" : `${formatLiczby.format(o.sredni_czas_min)} / ${formatLiczby.format(o.maks_czas_min)} min`,
            ];
            komorki.forEach((tekst, i) => {
                const td = document.createElement("td");
                if (i > 0) td.className = "liczba";
                td.textContent = tekst;
                tr.appendChild(td);
            });
            lista.appendChild(tr);
            L.marker([o.lat, o.lon], { icon: ikonaPunktu(o.nr), interactive: false, keyboard: false }).addTo(warstwa);
        }
    }

    pobierzJson(urlPliku)
        .then((meta) => {
            pokazObszaryObslugi(meta.punkty);
            if (meta.laczny_dostepny) {
                poleKolumna.add(new Option("★ Wszystkie usługi naraz (min)", WARTOSC_LACZNY));
            }
            for (const k of meta.kolumny) {
                poleKolumna.add(new Option(k.nazwa + (k.minuty ? " (min)" : ""), k.nazwa));
            }
            return pokazKolumne(poleKolumna.value);
        })
        .catch((e) => pokazBlad(`Nie udało się wczytać pliku: ${e.message}`));
})();
