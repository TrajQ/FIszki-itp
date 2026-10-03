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
        // ETAP 183: zasięgi jako wieloboki — tylko dla czasu dojścia i bez porównania scenariuszy
        const linkKontury = document.getElementById("link-kontury");
        linkKontury.hidden = Boolean(po) || !(kolumna === "laczny" || /_min$|^czas/i.test(kolumna));
        linkKontury.href = `${URL_KONTURY}?${new URLSearchParams({ plik: NAZWA_PLIKU, kolumna })}`;
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

    // ETAP 204: dostępność w grupach mieszkańców (wyniki.udzialy_grup)
    function pokazGrupy(grupy) {
        const blok = document.getElementById("grupy-mieszkancow");
        blok.hidden = !grupy || !grupy.length;
        if (blok.hidden) return;
        const tabela = document.getElementById("tabela-grup");
        const glowa = document.createElement("tr");
        const progi = grupy[0].udzialy.filter((u) => u.prog <= 15).map((u) => u.prog);
        for (const [t, k] of [["Grupa", ""], ["Osób", "liczba"], ...progi.map((p) => [`≤ ${p} min`, "liczba"]), ["Mediana", "liczba"]]) {
            const th = document.createElement("th");
            th.className = k;
            th.textContent = t;
            glowa.appendChild(th);
        }
        tabela.replaceChildren(glowa);
        for (const g of grupy) {
            const tr = document.createElement("tr");
            const komorki = [[g.nazwa, ""], [formatLiczby.format(g.razem), "liczba"],
                ...g.udzialy.filter((u) => u.prog <= 15).map((u) => [u.procent === null ? "—" : `${formatLiczby.format(u.procent)}%`, "liczba"]),
                [g.mediana_min === null ? "—" : `${formatLiczby.format(g.mediana_min)} min`, "liczba"]];
            for (const [t, k] of komorki) {
                const td = document.createElement("td");
                td.className = k;
                td.textContent = t;
                tr.appendChild(td);
            }
            tabela.appendChild(tr);
        }
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
        pokazGrupy(s.grupy);
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
        biezacaKolumna = kolumna;
        warstwaLokalizacji.clearLayers();
        document.getElementById("lista-lokalizacji").replaceChildren();
        document.getElementById("wynik-lokalizacji").hidden = true;
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
                    if (!wstawianie && !wskazywanieZasiegu) pokazKomorke(cecha.properties.h3, e.latlng);
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
        odswiezDzielnice(); // ETAP 163: tabela dzielnic dla nowego wskaźnika
        // „Gdzie nowa placówka?” — tylko dla czasu dojścia do jednej usługi.
        document.getElementById("lokalizacja-blok").hidden = !analiza.minuty || kolumna === WARTOSC_LACZNY;
        ustawLinkGeojson(null);
    }

    // ---------- wyniki w narysowanych dzielnicach (ETAP 163) — liczy serwer (dostepnosc/obszary.py) ----------

    const KOLORY_DZIELNIC = ["#0071e3", "#34c759", "#5e5ce6", "#ff375f", "#30b0c7", "#8e6e4e", "#bf5af2", "#1d1d1f"];
    const KLUCZ_DZIELNIC = `dostepnosc.dzielnice.${NAZWA_PLIKU}`;
    const warstwaDzielnic = L.featureGroup().addTo(mapa);
    let dzielnice = []; // [{nazwa, geometria}]
    try {
        dzielnice = JSON.parse(localStorage.getItem(KLUCZ_DZIELNIC) || "[]");
    } catch (e) {
        dzielnice = []; // bez localStorage obszary znikną po przeładowaniu
    }
    function zapamietajDzielnice() {
        try {
            localStorage.setItem(KLUCZ_DZIELNIC, JSON.stringify(dzielnice));
        } catch (e) {
            /* tylko wygoda */
        }
    }
    mapa.addControl(new L.Control.Draw({
        position: "topleft",
        draw: { polygon: { allowIntersection: false, showArea: false }, rectangle: { showArea: false }, polyline: false, circle: false, marker: false, circlemarker: false },
    }));
    mapa.on(L.Draw.Event.CREATED, (e) => {
        if (dzielnice.length >= 8) return pokazBlad("Najwyżej 8 obszarów — usuń któryś z listy.");
        const nazwa = (prompt("Nazwa obszaru (np. Jeżyce):", `Obszar ${dzielnice.length + 1}`) || "").trim();
        if (!nazwa) return;
        dzielnice.push({ nazwa, geometria: e.layer.toGeoJSON().geometry });
        zapamietajDzielnice();
        odswiezDzielnice();
    });

    async function odswiezDzielnice() {
        const lista = document.getElementById("lista-dzielnic");
        const tabela = document.getElementById("tabela-dzielnic");
        const status = document.getElementById("status-dzielnic");
        warstwaDzielnic.clearLayers();
        lista.replaceChildren();
        dzielnice.forEach((d, i) => {
            const kolor = KOLORY_DZIELNIC[i % KOLORY_DZIELNIC.length];
            const napis = document.createElement("span");
            napis.textContent = `${i + 1}. ${d.nazwa}`; // nazwa od użytkownika — jako tekst
            L.geoJSON(d.geometria, { style: { color: kolor, weight: 2.5, fill: false, dashArray: "6 4" }, interactive: false })
                .bindTooltip(napis).addTo(warstwaDzielnic);
            const li = document.createElement("li");
            const nr = document.createElement("span");
            nr.className = "lista-dzielnic__nr";
            nr.style.borderColor = nr.style.color = kolor;
            nr.textContent = i + 1;
            const nazwa = document.createElement("span");
            nazwa.textContent = d.nazwa;
            const usun = document.createElement("button");
            usun.type = "button";
            usun.className = "przycisk--tekst";
            usun.textContent = "Usuń";
            usun.addEventListener("click", () => {
                dzielnice.splice(i, 1);
                zapamietajDzielnice();
                odswiezDzielnice();
            });
            li.append(nr, nazwa, usun);
            lista.appendChild(li);
        });
        tabela.hidden = status.hidden = true;
        // ETAP 205: raport dzielnic do druku — jeden plik, bez porównania scenariuszy
        const linkRaportu = document.getElementById("link-raport-dzielnic");
        linkRaportu.hidden = !dzielnice.length || !biezacaKolumna || !trybPorownania.hidden;
        linkRaportu.href = `${URL_RAPORT}-dzielnic?${new URLSearchParams({ plik: NAZWA_PLIKU, kolumna: biezacaKolumna === WARTOSC_LACZNY ? "laczny" : biezacaKolumna })}`;
        if (!dzielnice.length || !biezacaKolumna) return;
        try {
            const odp = await fetch(`${urlPliku}/obszary`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ kolumna: biezacaKolumna === WARTOSC_LACZNY ? "laczny" : biezacaKolumna, obszary: dzielnice,
                    po: !trybPorownania.hidden && poleScenariusz.value ? poleScenariusz.value : undefined }),
            });
            const w = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(w.blad || `Błąd ${odp.status}`);
            if (w.porownanie) return pokazPorownanieDzielnic(w);
            const naglowek = document.createElement("tr");
            const kolumny = [["Obszar", ""], ["Komórek", "liczba"], ["Mieszkańcy", "liczba"], [w.minuty ? "Czas śr. [min]" : "Średnia", "liczba"], ["Mediana", "liczba"]];
            if (w.minuty) kolumny.push([`Do ${w.prog} min`, "liczba"]);
            for (const [t, k] of kolumny) {
                const th = document.createElement("th");
                th.className = k;
                th.textContent = t;
                naglowek.appendChild(th);
            }
            tabela.replaceChildren(naglowek);
            const wiersz = (nazwa, s) => {
                const tr = document.createElement("tr");
                const komorki = [nazwa, s.komorek, s.mieszkancy === undefined ? "—" : formatLiczby.format(s.mieszkancy),
                    s.srednia === undefined ? "—" : formatLiczby.format(s.srednia), s.mediana === undefined ? "—" : formatLiczby.format(s.mediana)];
                if (w.minuty) komorki.push(s.w_zasiegu_proc === undefined ? "—" : `${formatProcentu.format(s.w_zasiegu_proc)}%`);
                komorki.forEach((tekst, k) => {
                    const td = document.createElement("td");
                    td.className = k ? "liczba" : "";
                    td.textContent = tekst;
                    tr.appendChild(td);
                });
                return tr;
            };
            w.obszary.forEach((o, i) => tabela.appendChild(wiersz(`${i + 1}. ${o.nazwa}`, o)));
            const calosc = wiersz("cały plik", w.calosc);
            calosc.className = "tabela-dzielnic__calosc";
            tabela.appendChild(calosc);
            tabela.hidden = false;
        } catch (e) {
            status.textContent = e.message;
            status.hidden = false;
        }
    }

    // ETAP 184: dzielnice w porównaniu scenariuszy — przed → po i zmiana (liczy serwer)
    function pokazPorownanieDzielnic(w) {
        const tabela = document.getElementById("tabela-dzielnic");
        const td = (tekst, klasa = "liczba") => {
            const e = document.createElement("td");
            e.className = klasa;
            e.textContent = tekst;
            return e;
        };
        const naglowek = document.createElement("tr");
        const kolumny = [["Obszar", ""], [w.minuty ? "Czas śr. przed → po" : "Średnia przed → po", "liczba"], ["Zmiana", "liczba"]];
        if (w.minuty) kolumny.push([`Do ${w.prog} min przed → po`, "liczba"], ["Zmiana [p.p.]", "liczba"]);
        for (const [t, k] of kolumny) {
            const th = document.createElement("th");
            th.className = k;
            th.textContent = t;
            naglowek.appendChild(th);
        }
        tabela.replaceChildren(naglowek);
        const liczbaLub = (x) => (x === undefined ? "—" : formatLiczby.format(x));
        const wiersz = (nazwa, o) => {
            const tr = document.createElement("tr");
            tr.append(td(nazwa, ""), td(`${liczbaLub(o.przed.srednia)} → ${liczbaLub(o.po.srednia)}`));
            const zm = td(o.zmiana_srednia === undefined ? "—" : formatZmiany.format(o.zmiana_srednia));
            // krótszy czas = poprawa (jak kolory mapy zmian)
            if (w.minuty && o.zmiana_srednia !== undefined && Math.abs(o.zmiana_srednia) >= 0.05) zm.classList.add(o.zmiana_srednia < 0 ? "stan--ok" : "stan--zle");
            tr.appendChild(zm);
            if (w.minuty) {
                const proc = (x) => (x === undefined ? "—" : `${formatProcentu.format(x)}%`);
                tr.append(td(`${proc(o.przed.w_zasiegu_proc)} → ${proc(o.po.w_zasiegu_proc)}`),
                    td(o.zmiana_w_zasiegu_proc === undefined ? "—" : formatZmiany.format(o.zmiana_w_zasiegu_proc)));
            }
            return tr;
        };
        w.obszary.forEach((o, i) => tabela.appendChild(wiersz(`${i + 1}. ${o.nazwa}`, o)));
        const calosc = wiersz("cały plik", w.calosc);
        calosc.className = "tabela-dzielnic__calosc";
        tabela.appendChild(calosc);
        tabela.hidden = false;
    }

    // ---------- gdzie nowa placówka (ETAP 78) ----------
    // Wybór miejsc liczy serwer (dostepnosc/lokalizacja.py); tu je pokazujemy.

    let biezacaKolumna = null;
    const warstwaLokalizacji = L.layerGroup().addTo(mapa);

    function liczbaZPola(pole, domyslna) {
        const liczba = Number(String(pole.value).replace(",", "."));
        return Number.isFinite(liczba) ? liczba : domyslna;
    }

    document.getElementById("szukaj-lokalizacji").addEventListener("click", async (e) => {
        const przycisk = e.target;
        const wynikEl = document.getElementById("wynik-lokalizacji");
        const lista = document.getElementById("lista-lokalizacji");
        const prog = Number(suwakProgu.value) || 15;
        const adres = new URL(`${urlPliku}/lokalizacja`, location.href);
        adres.searchParams.set("kolumna", biezacaKolumna);
        adres.searchParams.set("prog", String(prog));
        adres.searchParams.set("ile", document.getElementById("ile-placowek").value);
        adres.searchParams.set("predkosc", String(liczbaZPola(document.getElementById("model-predkosc"), 4.8)));
        adres.searchParams.set("kretosc", String(liczbaZPola(document.getElementById("model-kretosc"), 1.3)));
        przycisk.disabled = true;
        try {
            const w = await pobierzJson(adres);
            warstwaLokalizacji.clearLayers();
            lista.replaceChildren();
            wynikEl.hidden = false;
            if (!w.propozycje.length) {
                wynikEl.textContent = `W progu ${prog} min wszystko jest w zasięgu — nowa placówka nic nie zmieni.`;
                return;
            }
            const jednostka = w.z_ludnoscia ? "mieszk." : "komórek";
            wynikEl.textContent = `W zasięgu ${prog} min: dziś ${formatProcentu.format(w.w_zasiegu_przed_proc)}%, z ${w.propozycje.length === 1 ? "nową placówką" : `${w.propozycje.length} nowymi placówkami`} ${formatProcentu.format(w.w_zasiegu_po_proc)}% ${w.z_ludnoscia ? "mieszkańców" : "powierzchni"}.`;
            for (const p of w.propozycje) {
                const ikona = L.divIcon({ className: "znacznik-lokalizacji", html: `<span>${p.nr}</span>`, iconSize: [30, 30], iconAnchor: [15, 15] });
                L.marker([p.lat, p.lng], { icon: ikona, title: `Propozycja ${p.nr}` }).addTo(warstwaLokalizacji);
                const li = document.createElement("li");
                const przyciskPokaz = document.createElement("button");
                przyciskPokaz.type = "button";
                przyciskPokaz.className = "przycisk--tekst";
                przyciskPokaz.textContent = `obejmie ${formatLiczby.format(p.obejmie)} ${jednostka} (${formatProcentu.format(p.obejmie_proc)}%)`;
                przyciskPokaz.addEventListener("click", () => mapa.setView([p.lat, p.lng], Math.max(mapa.getZoom(), 15)));
                li.append(przyciskPokaz);
                lista.appendChild(li);
            }
        } catch (err) {
            wynikEl.hidden = false;
            wynikEl.textContent = err.message;
        } finally {
            przycisk.disabled = false;
        }
    });

    // ---------- zasięg z punktu (ETAP 85) ----------
    // Liczby liczy serwer (dostepnosc/zasieg.py); tu okręgi i tabela.

    const KOLORY_ZASIEGU = { 5: "#30d158", 10: "#ffd60a", 15: "#ff9f0a" };
    const warstwaZasiegu = L.layerGroup().addTo(mapa);
    const przyciskZasieg = document.getElementById("wskaz-zasieg");
    const przyciskUsunZasieg = document.getElementById("usun-zasieg");
    const tabelaZasiegu = document.getElementById("wynik-zasiegu");
    const opisZasiegu = document.getElementById("opis-zasiegu");
    let wskazywanieZasiegu = false;
    let numerZasiegu = 0;

    function ustawWskazywanie(wlacz) {
        wskazywanieZasiegu = wlacz;
        if (wlacz && wstawianie) ustawWstawianie(false);
        przyciskZasieg.textContent = wlacz ? "Kliknij na mapie…" : "Wskaż punkt";
        przyciskZasieg.classList.toggle("model__wstawiaj--aktywny", wlacz);
        mapa.getContainer().classList.toggle("mapa--wstawianie", wlacz);
    }

    function komorkaTabeli(tag, tekst, klasa) {
        const el = document.createElement(tag);
        el.textContent = tekst;
        if (klasa) el.className = klasa;
        return el;
    }

    async function pokazZasieg(latlng) {
        const numer = ++numerZasiegu;
        const adres = new URL(`${urlPliku}/zasieg`, location.href);
        adres.searchParams.set("lat", latlng.lat.toFixed(6));
        adres.searchParams.set("lng", latlng.lng.toFixed(6));
        if (biezacaKolumna && biezacaKolumna !== WARTOSC_LACZNY) adres.searchParams.set("kolumna", biezacaKolumna);
        adres.searchParams.set("predkosc", String(liczbaZPola(document.getElementById("model-predkosc"), 4.8)));
        adres.searchParams.set("kretosc", String(liczbaZPola(document.getElementById("model-kretosc"), 1.3)));
        let w;
        try {
            w = await pobierzJson(adres);
        } catch (e) {
            opisZasiegu.textContent = e.message;
            opisZasiegu.hidden = false;
            return;
        }
        if (numer !== numerZasiegu) return;
        warstwaZasiegu.clearLayers();
        for (const p of [...w.progi].reverse()) {
            L.circle([w.lat, w.lng], {
                radius: p.promien_m, color: KOLORY_ZASIEGU[p.minuty], weight: 2, dashArray: "6 4",
                fillColor: KOLORY_ZASIEGU[p.minuty], fillOpacity: 0.08, interactive: false,
            }).addTo(warstwaZasiegu);
        }
        L.circleMarker([w.lat, w.lng], { radius: 6, color: "#ffffff", weight: 2, fillColor: "#1d1d1f", fillOpacity: 1 }).addTo(warstwaZasiegu);

        const jednostka = w.z_ludnoscia ? "Mieszkańcy" : "Komórki";
        const naglowek = document.createElement("tr");
        naglowek.append(komorkaTabeli("th", "Pieszo"), komorkaTabeli("th", "Promień", "liczba"), komorkaTabeli("th", jednostka, "liczba"));
        if (w.kolumna) naglowek.append(komorkaTabeli("th", "dziś dalej", "liczba"));
        tabelaZasiegu.replaceChildren(naglowek);
        for (const p of w.progi) {
            const tr = document.createElement("tr");
            const znak = komorkaTabeli("td", `${p.minuty} min`);
            znak.style.borderLeft = `4px solid ${KOLORY_ZASIEGU[p.minuty]}`;
            const ile = w.z_ludnoscia ? p.ludnosc : p.komorki;
            tr.append(znak, komorkaTabeli("td", `${formatLiczby.format(p.promien_m)} m`, "liczba"),
                komorkaTabeli("td", `${formatLiczby.format(ile)} (${formatProcentu.format(w.razem ? 100 * ile / w.razem : 0)}%)`, "liczba"));
            if (w.kolumna) tr.append(komorkaTabeli("td", formatLiczby.format(p.nowi), "liczba"));
            tabelaZasiegu.appendChild(tr);
        }
        tabelaZasiegu.hidden = false;
        opisZasiegu.textContent = !w.w_siatce
            ? "Punkt jest poza siatką pliku — w zasięgu 15 minut nie ma żadnej komórki."
            : w.kolumna
                ? `„dziś dalej” — ${w.z_ludnoscia ? "mieszkańcy" : "komórki"}, którzy do usługi z mapy mają dziś dalej niż dany próg; tylu obejmie nowa placówka w tym miejscu.`
                : "Wybierz czas dojścia do usługi, żeby zobaczyć, ilu z nich ma ją dziś dalej.";
        opisZasiegu.hidden = false;
        przyciskUsunZasieg.hidden = false;
    }

    przyciskZasieg.addEventListener("click", () => ustawWskazywanie(!wskazywanieZasiegu));
    przyciskUsunZasieg.addEventListener("click", () => {
        numerZasiegu++;
        warstwaZasiegu.clearLayers();
        tabelaZasiegu.hidden = true;
        opisZasiegu.hidden = true;
        przyciskUsunZasieg.hidden = true;
    });
    mapa.on("click", (e) => {
        if (!wskazywanieZasiegu) return;
        ustawWskazywanie(false);
        pokazZasieg(e.latlng);
    });

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
        odswiezDzielnice(); // ETAP 184: tabela dzielnic przed → po
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

    // ETAP 223: kolor punktu według usługi (pierwsza usługa — fiolet jak dotąd)
    const KOLORY_USLUG = ["#5e5ce6", "#ff9f0a", "#30b0c7", "#ff375f", "#34c759", "#8e6e4e", "#bf5af2", "#1d1d1f"];

    function ikonaPunktu(nr, kolor = KOLORY_USLUG[0]) {
        return L.divIcon({ className: "punkt-uslugi", html: `<span style="background:${kolor}">${nr}</span>`, iconSize: [26, 26] });
    }

    // klucz usługi jak nazwa kolumny na serwerze (model.nazwa_kolumny) — tylko do kolorów
    function kluczUslugi(nazwa) {
        return nazwa.trim().toLowerCase().replace(/[ąćęłńóśźż]/g, (z) => "acelnoszz"["ąćęłńóśźż".indexOf(z)]).replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    }

    function uslugaPunktu(wpis) {
        return wpis.usluga || modelUsluga.value;
    }

    function koloryUslug() {
        const kolory = new Map();
        for (const p of punktyModelu) {
            const k = kluczUslugi(uslugaPunktu(p));
            if (!kolory.has(k)) kolory.set(k, KOLORY_USLUG[kolory.size % KOLORY_USLUG.length]);
        }
        return kolory;
    }

    const listaPunktow = document.getElementById("lista-punktow-modelu");

    function podpisz(wpis) {
        wpis.znacznik.unbindTooltip();
        if (!wpis.nazwa) return;
        const napis = document.createElement("span");
        napis.textContent = wpis.nazwa; // nazwa od użytkownika albo z CSV — Leaflet wstawiłby napis jako HTML
        wpis.znacznik.bindTooltip(napis);
    }

    function usunPunkt(wpis) {
        warstwaPunktow.removeLayer(wpis.znacznik);
        punktyModelu.splice(punktyModelu.indexOf(wpis), 1);
        odswiezPunkty();
    }

    // ETAP 222: lista punktów pod mapą — nazwa (do tabeli obszarów obsługi), pokaż, usuń
    function odswiezListe() {
        listaPunktow.hidden = punktyModelu.length === 0;
        listaPunktow.replaceChildren(...punktyModelu.map((wpis, i) => {
            const li = document.createElement("li");
            const nr = document.createElement("button");
            nr.type = "button";
            nr.className = "lista-punktow-modelu__nr";
            nr.textContent = String(i + 1);
            nr.title = "Pokaż na mapie";
            nr.setAttribute("aria-label", `Pokaż punkt ${i + 1} na mapie`);
            nr.addEventListener("click", () => mapa.setView(wpis.latlng, Math.max(mapa.getZoom(), 15)));
            const nazwa = document.createElement("input");
            nazwa.type = "text";
            nazwa.maxLength = 60;
            nazwa.placeholder = "nazwa";
            nazwa.value = wpis.nazwa || "";
            nazwa.setAttribute("aria-label", `Nazwa punktu ${i + 1}`);
            nazwa.addEventListener("input", () => {
                wpis.nazwa = nazwa.value.trim();
                podpisz(wpis);
            });
            const usun = document.createElement("button");
            usun.type = "button";
            usun.className = "przycisk--tekst";
            usun.textContent = "✕";
            usun.title = "Usuń punkt";
            usun.setAttribute("aria-label", `Usuń punkt ${i + 1}`);
            usun.addEventListener("click", () => usunPunkt(wpis));
            const usluga = document.createElement("input"); // ETAP 223: własna usługa punktu
            usluga.type = "text";
            usluga.maxLength = 40;
            usluga.className = "lista-punktow-modelu__usluga";
            usluga.placeholder = modelUsluga.value || "usługa";
            usluga.value = wpis.usluga || "";
            usluga.setAttribute("list", "model-uslugi");
            usluga.setAttribute("aria-label", `Usługa punktu ${i + 1} (puste — jak w polu „Usługa”)`);
            usluga.addEventListener("change", () => {
                wpis.usluga = usluga.value.trim();
                odswiezKolory(); // bez przebudowy listy — „change” przychodzi przy opuszczaniu pola
            });
            li.append(nr, nazwa, usluga, usun);
            return li;
        }));
    }

    function odswiezKolory() {
        const kolory = koloryUslug();
        punktyModelu.forEach((p, i) => {
            const kolor = kolory.get(kluczUslugi(uslugaPunktu(p)));
            p.znacznik.setIcon(ikonaPunktu(i + 1, kolor));
            const nr = listaPunktow.children[i] && listaPunktow.children[i].querySelector(".lista-punktow-modelu__nr");
            if (nr) nr.style.background = kolor;
        });
    }

    function odswiezPunkty() {
        modelStan.textContent = wstawianie
            ? `Punkty: ${punktyModelu.length} — klikaj na mapie; klik w punkt go usuwa, przeciągnięcie przesuwa.`
            : punktyModelu.length ? `Punkty: ${punktyModelu.length} — przeciągnij punkt, żeby go przesunąć.` : "Punkty: 0";
        modelWyczysc.hidden = punktyModelu.length === 0;
        modelPolicz.disabled = punktyModelu.length === 0;
        odswiezListe();
        odswiezKolory();
    }

    function ustawWstawianie(wlacz) {
        if (wlacz && wskazywanieZasiegu) ustawWskazywanie(false);
        wstawianie = wlacz;
        modelWstawiaj.textContent = wlacz ? "Zakończ wstawianie" : "Wstawiaj punkty";
        modelWstawiaj.classList.toggle("model__wstawiaj--aktywny", wlacz);
        mapa.getContainer().classList.toggle("mapa--wstawianie", wlacz);
        odswiezPunkty();
    }

    function dodajPunkt(latlng, nazwa = "", usluga = "") {
        const znacznik = L.marker(latlng, { icon: ikonaPunktu(punktyModelu.length + 1), keyboard: false, draggable: true }).addTo(warstwaPunktow);
        const wpis = { latlng, znacznik, nazwa, usluga };
        podpisz(wpis);
        znacznik.on("click", () => {
            if (wstawianie) usunPunkt(wpis);
        });
        znacznik.on("dragend", () => {
            wpis.latlng = znacznik.getLatLng(); // ETAP 222: przesunięty punkt
        });
        punktyModelu.push(wpis);
        odswiezPunkty();
    }

    modelUsluga.addEventListener("input", odswiezPunkty); // ETAP 223: kolory i podpowiedzi usług punktów

    // Kliknięcie w heksagon w trybie wstawiania ma dodać punkt, a nie
    // otwierać okienko komórki — sprawdzamy tryb w obu miejscach.
    mapa.on("click", (e) => {
        if (wstawianie) dodajPunkt(e.latlng);
    });

    // Punkty z pliku CSV (ETAP 55): serwer sprawdza plik, tu stawiamy
    // znaczniki — można je jeszcze usunąć albo dołożyć kliknięciem.
    const modelPlik = document.getElementById("model-plik");
    modelPlik.addEventListener("change", async () => {
        if (!modelPlik.files.length) return;
        modelBlad.hidden = true;
        const formularz = new FormData();
        formularz.append("plik", modelPlik.files[0]);
        try {
            const odpowiedz = await fetch(URL_PUNKTY_Z_PLIKU, { method: "POST", body: formularz });
            const dane = await odpowiedz.json();
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            for (const p of dane.punkty) dodajPunkt(L.latLng(p.lat, p.lon), p.nazwa, p.usluga || "");
            mapa.fitBounds(L.latLngBounds(punktyModelu.map((p) => p.latlng)), { padding: [40, 40], maxZoom: 15 });
            if (dane.liczba_bledow) {
                modelBlad.textContent = `Pominięte wiersze (${dane.liczba_bledow}): ${dane.bledy.join("; ")}.`;
                modelBlad.hidden = false;
            }
        } catch (e) {
            modelBlad.textContent = e.message;
            modelBlad.hidden = false;
        } finally {
            modelPlik.value = "";
        }
    });

    // „Dodaj do istniejących” ma sens tylko na siatce bieżącego pliku.
    modelSiatka.addEventListener("change", () => {
        const polacz = document.getElementById("model-polacz");
        polacz.disabled = modelSiatka.value !== "plik";
        if (polacz.disabled) polacz.checked = false;
    });

    function podpowiedzUslugi(kolumny) {
        const lista = document.getElementById("model-uslugi");
        lista.replaceChildren();
        for (const k of kolumny) {
            const dopasowanie = /^czas_(.+)_min$/.exec(k.nazwa);
            if (dopasowanie) lista.appendChild(new Option(dopasowanie[1]));
        }
    }

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
            nazwy: punktyModelu.map((p) => p.nazwa || ""),
            uslugi: punktyModelu.map((p) => p.usluga || ""), // ETAP 223
            predkosc_kmh: modelPredkosc.value,
            kretosc: modelKretosc.value,
        };
        if (modelSiatka.value === "plik") {
            zapytanie.baza = NAZWA_PLIKU;
            zapytanie.polacz = document.getElementById("model-polacz").checked;
        }
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
        const grupy = punkty.grupy || [punkty]; // ETAP 223: pliki sprzed — jedna usługa na wierzchu
        const zLudnoscia = punkty.obszary.length > 0 && punkty.obszary[0].ludnosc !== undefined;
        document.getElementById("obszary-opis").textContent =
            (grupy.length > 1 ? `Usługi: ${grupy.map((g) => `„${g.usluga}” (${g.kolumna})`).join(", ")}` : `Usługa „${punkty.usluga}” (${punkty.kolumna})`) +
            `, ${formatLiczby.format(punkty.predkosc_kmh)} km/h, krętość ${formatLiczby.format(punkty.kretosc)}. ` +
            (punkty.polaczone
                ? "Nowe punkty dodane do istniejących usług. W tabeli tylko komórki, którym nowy punkt skrócił dojście"
                : "Każda komórka należy do obszaru najbliższego punktu") +
            (zLudnoscia
                ? punkty.polaczone ? " — mieszkańcy, którzy zyskali." : " — stąd liczba mieszkańców na placówkę."
                : ". Bez kolumny ludnosc w pliku bazowym nie ma liczby mieszkańców.");
        przygotujEdycje(punkty);
        const lista = document.getElementById("lista-obszarow");
        lista.replaceChildren();
        const warstwa = L.layerGroup().addTo(mapa);
        warstwaObszarowObslugi = warstwa;
        grupy.forEach((g, nrGrupy) => {
            const kolor = KOLORY_USLUG[nrGrupy % KOLORY_USLUG.length];
            if (grupy.length > 1) {
                const naglowek = document.createElement("tr");
                const th = document.createElement("th");
                th.colSpan = 3;
                th.className = "tabela-obszarow__usluga";
                th.style.color = kolor;
                th.textContent = g.usluga;
                naglowek.appendChild(th);
                lista.appendChild(naglowek);
            }
            for (const o of g.obszary) {
                const tr = document.createElement("tr");
                tr.title = `Komórek w obszarze: ${o.komorki}`;
                const komorki = [
                    o.nazwa ? `${o.nr}. ${o.nazwa}` : `${o.nr}`,
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
                L.marker([o.lat, o.lon], { icon: ikonaPunktu(o.nr, kolor), interactive: false, keyboard: false }).addTo(warstwa);
            }
        });
    }

    // ---------- ETAP 222: punkty policzonego pliku z powrotem do edycji ----------
    // Liczymy ponownie na pliku bazowym (tam, gdzie punkty liczono pierwszy raz):
    // zestaw punktów jedzie przez sessionStorage na stronę tamtego pliku.
    const KLUCZ_EDYCJI = "dostepnosc.edycjaPunktow";
    let warstwaObszarowObslugi = null;

    function przygotujEdycje(punkty) {
        const przycisk = document.getElementById("edytuj-punkty");
        const opis = document.getElementById("edytuj-punkty-opis");
        const cel = punkty.baza && punkty.baza_istnieje ? punkty.baza : punkty.baza ? null : NAZWA_PLIKU;
        opis.hidden = cel === NAZWA_PLIKU;
        opis.textContent = cel ? `Punkty otworzą się na pliku bazowym „${cel}” — tam, gdzie liczono je pierwszy raz.`
            : `Pliku bazowego „${punkty.baza}” już nie ma — punkty wczytają się tutaj, na siatce tego pliku` +
              (punkty.polaczone ? "; czas policzy się tylko z nich, bez usług, do których je wtedy dodano." : ".");
        przycisk.onclick = () => {
            const zestaw = {
                usluga: punkty.usluga, predkosc_kmh: punkty.predkosc_kmh, kretosc: punkty.kretosc,
                polacz: Boolean(punkty.polaczone && cel !== NAZWA_PLIKU),
                // ETAP 223: usługa pierwszej grupy w polu „Usługa”, pozostałe przy punktach
                punkty: (punkty.grupy || [punkty]).flatMap((g, i) => g.obszary.map((o) => ({ lat: o.lat, lon: o.lon, nazwa: o.nazwa || "", usluga: i ? g.usluga : "" }))),
            };
            if (!cel || cel === NAZWA_PLIKU) return wczytajDoEdycji(zestaw);
            try {
                sessionStorage.setItem(KLUCZ_EDYCJI, JSON.stringify(zestaw));
            } catch (e) {
                return wczytajDoEdycji(zestaw); // bez pamięci sesji — chociaż tutaj
            }
            window.location.href = `${URL_INDEKS}?plik=${encodeURIComponent(cel)}`;
        };
    }

    function wczytajDoEdycji(zestaw) {
        warstwaPunktow.clearLayers();
        punktyModelu.length = 0;
        if (warstwaObszarowObslugi) warstwaObszarowObslugi.clearLayers(); // stare numery pod przeciąganymi
        modelUsluga.value = zestaw.usluga || "";
        const liczba = (x) => String(x).replace(".", ",");
        modelPredkosc.value = liczba(zestaw.predkosc_kmh);
        modelKretosc.value = liczba(zestaw.kretosc);
        modelSiatka.value = "plik";
        modelSiatka.dispatchEvent(new Event("change"));
        document.getElementById("model-polacz").checked = Boolean(zestaw.polacz);
        for (const p of zestaw.punkty) dodajPunkt(L.latLng(p.lat, p.lon), p.nazwa, p.usluga || "");
        if (punktyModelu.length) mapa.fitBounds(L.latLngBounds(punktyModelu.map((p) => p.latlng)), { padding: [40, 40], maxZoom: 15 });
        modelStan.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    let zestawDoEdycji = null;
    try {
        zestawDoEdycji = JSON.parse(sessionStorage.getItem(KLUCZ_EDYCJI) || "null");
        sessionStorage.removeItem(KLUCZ_EDYCJI);
    } catch (e) {
        zestawDoEdycji = null;
    }

    pobierzJson(urlPliku)
        .then((meta) => {
            pokazObszaryObslugi(meta.punkty);
            if (zestawDoEdycji) wczytajDoEdycji(zestawDoEdycji);
            podpowiedzUslugi(meta.kolumny);
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
