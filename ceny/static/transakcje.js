// Ceny: transakcje z Rejestru Cen Nieruchomości (ETAP 104).
// Statystyki i progi kolorów liczy serwer (ceny/rcn.py); tu filtry, wykresy i mapa.
// ETAP 105: obszary rysowane na mapie (Leaflet.draw) i ich porównanie.
// ETAP 106: ta sama strona dla działek (CO === "dzialki") — inne filtry i tabela grup.
// ETAP 107: podobne transakcje wokół klikniętego miejsca (wycena porównawcza).
// ETAP 108: widok mapy „heksagony” — mediana ceny za m² w komórkach H3 (liczy serwer).
(function () {
    "use strict";

    if (PLIK_ID === null) return;

    // kwintyle ceny za m²: od najtańszych (jasne) do najdroższych (ciemne)
    const KOLORY = ["#ffe8a3", "#ffc55c", "#ff9f0a", "#e2630b", "#a33a00"];
    const liczba = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 });
    const filtry = document.getElementById("filtry");
    const komunikat = document.getElementById("komunikat");
    const NS = "http://www.w3.org/2000/svg";
    let numer = 0;
    let pierwszeRysowanie = true;
    const DZIALKI = CO === "dzialki";

    function el(tag, klasa, tekst) {
        const e = document.createElement(tag);
        if (klasa) e.className = klasa;
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    function svg(tag, atrybuty, tekst) {
        const e = document.createElementNS(NS, tag);
        for (const [k, v] of Object.entries(atrybuty)) e.setAttribute(k, v);
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    // ---------- mapa ----------

    const mapa = L.map("mapa-rcn", { preferCanvas: true }).setView([52.1, 19.4], 6);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap · transakcje: RCN, GUGiK",
        maxZoom: 19,
        referrerPolicy: "strict-origin-when-cross-origin", // OSM wymaga nagłówka Referer (jak w module dostępność)
    }).addTo(mapa);
    const warstwa = L.featureGroup().addTo(mapa);
    const warstwaObszarow = L.featureGroup().addTo(mapa);
    const warstwaHeksagonow = L.featureGroup().addTo(mapa);
    const widokMapy = document.getElementById("widok-mapy");
    let numerHeksagonow = 0;

    function klasa(cena, progi) {
        let i = 0;
        while (i < progi.length && cena > progi[i]) i++;
        return i;
    }

    function pokazLegende(progi, opis) {
        const legenda = document.getElementById("legenda-rcn");
        legenda.replaceChildren();
        const granice = [null, ...progi, null];
        progi.length && KOLORY.forEach((kolor, i) => {
            const zakres = granice[i] === null ? `do ${liczba.format(granice[i + 1])}` : granice[i + 1] === null ? `ponad ${liczba.format(granice[i])}` : `${liczba.format(granice[i])}–${liczba.format(granice[i + 1])}`;
            const pozycja = el("span", "legenda-rcn__pozycja");
            const probka = el("span", "legenda-rcn__probka");
            probka.style.background = kolor;
            pozycja.append(probka, `${zakres} zł/m²`);
            legenda.appendChild(pozycja);
        });
        legenda.appendChild(el("span", "wyciszony", opis));
    }

    function dopasujWidok(grupa) {
        if (pierwszeRysowanie && grupa.getLayers().length) {
            mapa.fitBounds(grupa.getBounds(), { padding: [20, 20] });
            pierwszeRysowanie = false;
        }
    }

    function rysujMape(m) {
        warstwa.clearLayers();
        if (widokMapy.elements.widok.value === "heksagony") return; // heksagony rysuje rysujHeksagony()
        for (const [lat, lng, cenaM2, data, pow] of m.punkty) {
            L.circleMarker([lat, lng], { radius: 5, weight: 0.6, color: "#3a2a1a", fillColor: KOLORY[klasa(cenaM2, m.progi)], fillOpacity: 0.85 })
                .bindTooltip(`${liczba.format(cenaM2)} zł/m² · ${pow} m² · ${data}`)
                .addTo(warstwa);
        }
        dopasujWidok(warstwa);
        const uwaga = m.wszystkich_z_polozeniem > m.punkty.length ? ` (na mapie ${m.punkty.length} najnowszych z ${m.wszystkich_z_polozeniem})` : "";
        pokazLegende(m.progi, `Kolory: pięć równolicznych klas ceny za m²${uwaga}.`);
    }

    // ---------- heksagony (ETAP 108) ----------

    async function rysujHeksagony() {
        warstwaHeksagonow.clearLayers();
        if (widokMapy.elements.widok.value !== "heksagony") return;
        const moj = ++numerHeksagonow;
        const parametry = parametryFiltrow();
        parametry.set("rozdzielczosc", widokMapy.elements.rozdzielczosc.value);
        parametry.set("minimum", widokMapy.elements.minimum.value);
        try {
            const odp = await fetch(`${URL_TRANSAKCJE}/${PLIK_ID}/heksagony?${parametry}`);
            const h = await odp.json();
            if (!odp.ok) throw new Error(h.blad || `Błąd ${odp.status}`);
            if (moj !== numerHeksagonow) return;
            warstwaHeksagonow.clearLayers();
            for (const k of h.komorki) {
                L.polygon(k.granica, { color: "#ffffff", weight: 0.8, fillColor: KOLORY[klasa(k.mediana_m2, h.progi)], fillOpacity: 0.75 })
                    .bindTooltip(`mediana ${liczba.format(k.mediana_m2)} zł/m² · ${k.liczba} transakcji`)
                    .addTo(warstwaHeksagonow);
            }
            dopasujWidok(warstwaHeksagonow);
            const ukryte = h.ukryte ? ` Ukryte heksagony z mniej niż ${h.minimum} transakcjami: ${h.ukryte} (transakcji w nich: ${liczba.format(h.transakcji_w_ukrytych)}).` : "";
            pokazLegende(h.progi, `Heksagony H3 o krawędzi ok. ${liczba.format(h.krawedz_m)} m: mediana ceny za m² transakcji w heksagonie, pięć równolicznych klas.${ukryte}`);
        } catch (e) {
            komunikat.textContent = e.message;
            komunikat.hidden = false;
        }
    }

    // ---------- wykresy ----------

    function wykresSlupkowy(pojemnik, slupki, opisX, tytulPunktu, linia) {
        pojemnik.replaceChildren();
        if (!slupki.length) return;
        const SZ = 520, WY = 220, M = { l: 56, p: 8, g: 10, d: 34 };
        const maks = Math.max(...slupki.map((s) => s.wartosc)) || 1;
        const potega = 10 ** Math.floor(Math.log10(maks / 4 || 1));
        const krok = [1, 2, 2.5, 5, 10].map((k) => k * potega).find((k) => maks / k <= 5);
        const gora = Math.ceil(maks / krok) * krok;
        const y = (w) => WY - M.d - (w / gora) * (WY - M.g - M.d);
        const szer = (SZ - M.l - M.p) / slupki.length;
        const s = svg("svg", { viewBox: `0 0 ${SZ} ${WY}`, role: "img" });
        for (let w = 0; w <= gora + krok / 2; w += krok) {
            s.append(svg("line", { x1: M.l, x2: SZ - M.p, y1: y(w), y2: y(w), class: "wykres-cen__siatka" }),
                svg("text", { x: M.l - 6, y: y(w) + 4, "text-anchor": "end", class: "wykres-cen__opis" }, liczba.format(w)));
        }
        const co = Math.ceil(slupki.length / 8);
        const punkty = [];
        slupki.forEach((sl, i) => {
            const x = M.l + i * szer;
            if (linia) {
                punkty.push(`${(x + szer / 2).toFixed(1)},${y(sl.wartosc).toFixed(1)}`);
                const kropka = svg("circle", { cx: x + szer / 2, cy: y(sl.wartosc), r: 3, fill: "#ff9f0a" });
                kropka.appendChild(svg("title", {}, tytulPunktu(sl)));
                s.appendChild(kropka);
            } else {
                const prost = svg("rect", { x: x + 1, y: y(sl.wartosc), width: Math.max(1, szer - 2), height: WY - M.d - y(sl.wartosc), fill: "#ff9f0a", rx: 2 });
                prost.appendChild(svg("title", {}, tytulPunktu(sl)));
                s.appendChild(prost);
            }
            if (i % co === 0) s.appendChild(svg("text", { x: x + szer / 2, y: WY - 14, "text-anchor": "middle", class: "wykres-cen__opis" }, opisX(sl)));
        });
        if (linia) s.insertBefore(svg("polyline", { points: punkty.join(" "), fill: "none", stroke: "#ff9f0a", "stroke-width": 2 }), s.querySelector("circle"));
        pojemnik.appendChild(s);
    }

    function kafelek(etykieta, wartosc, dopisek) {
        const k = el("div", "kafelek-rcn");
        k.append(el("span", "kafelek-rcn__etykieta", etykieta), el("span", "kafelek-rcn__wartosc", wartosc));
        if (dopisek) k.appendChild(el("span", "wyciszony kafelek-rcn__dopisek", dopisek));
        return k;
    }

    function pokaz(d) {
        const st = d.statystyki;
        const kafelki = document.getElementById("kafelki-rcn");
        if (!st) {
            kafelki.replaceChildren(el("p", "wyciszony", "Brak transakcji dla wybranych filtrów."));
            ["trend-rcn", "histogram-rcn", "grupy-rcn"].forEach((id) => document.getElementById(id).replaceChildren());
            warstwa.clearLayers();
            return;
        }
        kafelki.replaceChildren(
            kafelek("Mediana ceny za m²", `${liczba.format(st.mediana_m2)} zł`, `połowa transakcji: ${liczba.format(st.q1_m2)}–${liczba.format(st.q3_m2)} zł`),
            kafelek("Transakcji", liczba.format(st.liczba), `${st.od} – ${st.do}`),
            kafelek(DZIALKI ? "Mediana ceny transakcji" : "Mediana ceny lokalu", `${liczba.format(st.mediana_ceny)} zł`),
            kafelek("Mediana powierzchni", `${liczba.format(st.mediana_pow)} m²`),
        );
        const odrzucone = Object.entries(DZIALKI ? d.plik.odrzucone_dzialki : d.plik.odrzucone);
        document.getElementById("odrzucone-rcn").textContent = odrzucone.length
            ? `Przy imporcie pominięto: ${odrzucone.map(([k, v]) => `${k} — ${liczba.format(v)}`).join(", ")}.`
            : "";
        wykresSlupkowy(document.getElementById("trend-rcn"), st.trend.map((t) => ({ ...t, wartosc: t.mediana_m2 })),
            (t) => `${t.rok} Q${t.kwartal}`, (t) => `${t.rok}, kwartał ${t.kwartal}: ${liczba.format(t.mediana_m2)} zł/m² (${t.liczba} transakcji)`, true);
        wykresSlupkowy(document.getElementById("histogram-rcn"), st.histogram.map((h) => ({ ...h, wartosc: h.liczba })),
            (h) => liczba.format(h.od), (h) => `${liczba.format(h.od)}–${liczba.format(h.do)} zł/m²: ${h.liczba} transakcji`, false);
        const tabela = document.getElementById("grupy-rcn");
        const glowa = el("tr");
        glowa.append(el("th", "", DZIALKI ? "Przeznaczenie" : "Izby"), el("th", "liczba", "Transakcji"), el("th", "liczba", "Mediana za m²"), el("th", "liczba", "Mediana powierzchni"));
        tabela.replaceChildren(glowa);
        for (const i of st.grupy) {
            const tr = el("tr");
            tr.append(el("td", "", i.nazwa), el("td", "liczba", liczba.format(i.liczba)), el("td", "liczba", `${liczba.format(i.mediana_m2)} zł`), el("td", "liczba", `${liczba.format(i.mediana_pow)} m²`));
            tabela.appendChild(tr);
        }
        rysujMape(d.mapa);
    }

    // ---------- obszary do porównania (ETAP 105) ----------

    Object.assign(L.drawLocal.draw.toolbar.buttons, { polygon: "Rysuj obszar (wielobok)", rectangle: "Rysuj obszar (prostokąt)" });
    Object.assign(L.drawLocal.draw.toolbar.actions, { title: "Przerwij rysowanie", text: "Anuluj" });
    Object.assign(L.drawLocal.draw.toolbar.finish, { title: "Zakończ rysowanie", text: "Zakończ" });
    Object.assign(L.drawLocal.draw.toolbar.undo, { title: "Usuń ostatni punkt", text: "Cofnij punkt" });
    L.drawLocal.draw.handlers.polygon.tooltip = {
        start: "Kliknij, żeby zacząć obszar.",
        cont: "Klikaj kolejne wierzchołki.",
        end: "Kliknij pierwszy punkt, żeby zamknąć.",
    };
    L.drawLocal.draw.handlers.rectangle.tooltip.start = "Kliknij i przeciągnij, żeby narysować prostokąt.";
    L.drawLocal.draw.handlers.simpleshape.tooltip.end = "Puść przycisk, żeby zakończyć.";
    mapa.addControl(new L.Control.Draw({
        position: "topleft",
        draw: {
            polygon: { allowIntersection: false, showArea: false, shapeOptions: { color: "#0071e3" } },
            rectangle: { showArea: false, shapeOptions: { color: "#0071e3" } },
            polyline: false, circle: false, circlemarker: false, marker: false,
        },
    }));

    async function zapytanie(url, metoda, dane) {
        const odp = await fetch(url, { method: metoda, headers: { "Content-Type": "application/json" }, body: dane ? JSON.stringify(dane) : undefined });
        const wynik = await odp.json().catch(() => ({}));
        if (!odp.ok) throw new Error(wynik.blad || `Błąd ${odp.status}`);
        return wynik;
    }

    async function zmiana(obietnica) {
        try {
            await obietnica;
            await wczytaj();
        } catch (e) {
            komunikat.textContent = e.message;
            komunikat.hidden = false;
        }
    }

    mapa.on(L.Draw.Event.CREATED, (e) => {
        const nazwa = prompt("Nazwa obszaru (np. dzielnica, osiedle):", `Obszar ${warstwaObszarow.getLayers().length + 1}`);
        if (nazwa === null) return;
        zmiana(zapytanie(`${URL_TRANSAKCJE}/${PLIK_ID}/obszary`, "POST", { nazwa, geometria: e.layer.toGeoJSON().geometry }));
    });

    function numerObszaru(nr, kolor) {
        const znak = el("span", "obszar-rcn__nr", String(nr));
        znak.style.color = kolor;
        return znak;
    }

    // ETAP 110: mediana w latach dla obszarów (ta sama logika co rcn.wykres_lat_svg w raporcie);
    // MIN_W_ROKU przychodzi z serwera (rcn.MIN_W_ROKU)

    function wykresLatObszarow(por) {
        const pojemnik = document.getElementById("trend-obszarow");
        const opis = document.getElementById("opis-trendu-obszarow");
        pojemnik.replaceChildren();
        const lata = por.lata;
        const serie = por.obszary.map((o, i) => ({ kolor: o.kolor, med: o.lata || {}, n: o.lata_liczba || {}, numer: String(i + 1), przerywana: false }));
        serie.push({ kolor: "#8e8e93", med: por.calosc.lata || {}, n: por.calosc.lata_liczba || {}, numer: "", przerywana: true });
        const wartosci = serie.flatMap((s) => Object.values(s.med));
        const widoczny = por.obszary.length > 0 && lata.length >= 2 && wartosci.length > 0;
        pojemnik.hidden = opis.hidden = !widoczny;
        if (!widoczny) return;
        const SZ = 720, WY = 240, M = { l: 64, p: 40, g: 12, d: 28 };
        let lo = Math.min(...wartosci), hi = Math.max(...wartosci);
        const rozp = hi - lo || hi || 1;
        const potega = 10 ** Math.floor(Math.log10(rozp / 5));
        const krok = [1, 2, 2.5, 5, 10].map((k) => k * potega).find((k) => rozp / k <= 5);
        lo = Math.floor(lo / krok) * krok;
        hi = Math.ceil(hi / krok) * krok;
        const x = (rok) => M.l + lata.indexOf(rok) * (SZ - M.l - M.p) / (lata.length - 1);
        const y = (v) => WY - M.d - ((v - lo) / (hi - lo || 1)) * (WY - M.g - M.d);
        const s = svg("svg", { viewBox: `0 0 ${SZ} ${WY}`, role: "img", "aria-label": "Mediana ceny za m² w latach w obszarach" });
        for (let v = lo; v <= hi + krok / 2; v += krok) {
            s.append(svg("line", { x1: M.l, x2: SZ - M.p, y1: y(v), y2: y(v), class: "wykres-cen__siatka" }),
                svg("text", { x: M.l - 6, y: y(v) + 4, "text-anchor": "end", class: "wykres-cen__opis" }, liczba.format(v)));
        }
        for (const rok of lata) s.appendChild(svg("text", { x: x(rok), y: WY - 8, "text-anchor": "middle", class: "wykres-cen__opis" }, rok));
        for (const sr of serie) {
            const punkty = lata.filter((r) => String(r) in sr.med).map((r) => ({ r, a: x(r), b: y(sr.med[String(r)]), n: sr.n[String(r)] || 0 }));
            if (!punkty.length) continue;
            const linia = { points: punkty.map((p) => `${p.a.toFixed(1)},${p.b.toFixed(1)}`).join(" "), fill: "none", stroke: sr.kolor, "stroke-width": 2.5 };
            if (sr.przerywana) linia["stroke-dasharray"] = "6 4";
            s.appendChild(svg("polyline", linia));
            for (const p of punkty) {
                const kropka = svg("circle", { cx: p.a, cy: p.b, r: 4, fill: sr.kolor, stroke: sr.kolor, "stroke-width": 2 });
                if (p.n < MIN_W_ROKU) kropka.style.fill = "var(--tlo-karty)"; // pusty punkt: mediana niepewna
                kropka.appendChild(svg("title", {}, `${sr.numer ? `Obszar ${sr.numer}` : "Cały plik"}, ${p.r}: ${liczba.format(sr.med[String(p.r)])} zł/m² (${p.n} transakcji)`));
                s.appendChild(kropka);
            }
            if (sr.numer) {
                const ostatni = punkty[punkty.length - 1];
                s.appendChild(svg("text", { x: ostatni.a + 7, y: ostatni.b + 4, "font-weight": 700, fill: sr.kolor }, sr.numer));
            }
        }
        pojemnik.appendChild(s);
    }

    function pokazObszary(d) {
        const kolory = Object.fromEntries(d.porownanie.obszary.map((o) => [o.id, o.kolor]));
        warstwaObszarow.clearLayers();
        const lista = document.getElementById("obszary-rcn");
        lista.replaceChildren();
        d.obszary.forEach((o, i) => {
            const kolor = kolory[o.id];
            L.geoJSON(o.geometria, { style: { color: kolor, weight: 2.5, fillOpacity: 0.05 } })
                .bindTooltip(`${i + 1}. ${o.nazwa}`).addTo(warstwaObszarow);
            const li = el("li", "obszar-rcn");
            const zmien = el("button", "przycisk--tekst", "Zmień nazwę");
            zmien.type = "button";
            zmien.addEventListener("click", () => {
                const nazwa = prompt("Nowa nazwa obszaru:", o.nazwa);
                if (nazwa !== null) zmiana(zapytanie(`${URL_TRANSAKCJE}/obszary/${o.id}`, "PUT", { nazwa }));
            });
            const usun = el("button", "przycisk--tekst przycisk--niebezpieczny-tekst", "Usuń");
            usun.type = "button";
            usun.addEventListener("click", () => {
                if (confirm(`Usunąć obszar „${o.nazwa}”?`)) zmiana(zapytanie(`${URL_TRANSAKCJE}/obszary/${o.id}`, "DELETE"));
            });
            li.append(numerObszaru(i + 1, kolor), el("span", "obszar-rcn__nazwa", o.nazwa), zmien, usun);
            lista.appendChild(li);
        });
        if (!d.obszary.length) lista.appendChild(el("li", "wyciszony", "Jeszcze żadnego obszaru."));

        const tabela = document.getElementById("porownanie-rcn");
        tabela.replaceChildren();
        wykresLatObszarow(d.porownanie);
        if (!d.obszary.length) return;
        const glowa = el("tr");
        glowa.append(el("th", "", "Obszar"), el("th", "liczba", "Transakcji"), el("th", "liczba", "Mediana za m²"),
            el("th", "liczba", "Połowa transakcji"), el("th", "liczba", "Wobec całości"), el("th", "liczba", "Mediana powierzchni"));
        tabela.appendChild(glowa);
        const procent = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1, minimumFractionDigits: 1, signDisplay: "exceptZero" });
        const wiersze = d.porownanie.obszary.map((o, i) => [o, numerObszaru(i + 1, o.kolor)]);
        if (d.porownanie.calosc.liczba) wiersze.push([d.porownanie.calosc, null]);
        for (const [o, znak] of wiersze) {
            const tr = el("tr", znak ? "" : "raport-cen__calosc");
            const nazwa = el("td", "obszar-rcn");
            if (znak) nazwa.appendChild(znak);
            nazwa.append(o.nazwa);
            tr.append(nazwa, el("td", "liczba", liczba.format(o.liczba)));
            if (o.liczba) {
                tr.append(el("td", "liczba", `${liczba.format(o.mediana_m2)} zł`), el("td", "liczba", `${liczba.format(o.q1_m2)}–${liczba.format(o.q3_m2)}`),
                    el("td", "liczba", o.wobec_calosci_proc === undefined ? "" : `${procent.format(o.wobec_calosci_proc)}%`),
                    el("td", "liczba", `${liczba.format(o.mediana_pow)} m²`));
            } else {
                const brak = el("td", "wyciszony", "brak transakcji w obszarze");
                brak.colSpan = 4;
                tr.appendChild(brak);
            }
            tabela.appendChild(tr);
        }
    }

    function uzupelnijListy(d) {
        for (const nazwa of ["od", "do"]) {
            const pole = filtry.elements[nazwa];
            if (pole.options.length > 1) continue;
            for (const r of d.lata) pole.appendChild(new Option(r, r));
        }
        for (const [nazwa, wartosci] of Object.entries(d.listy)) {
            const pole = filtry.elements[nazwa];
            if (!pole || pole.options.length > 1) continue;
            for (const w of wartosci) pole.appendChild(new Option(`${w.wartosc || "(brak)"} — ${w.liczba}`, w.wartosc));
        }
    }

    // ---------- podobne transakcje (ETAP 107) ----------

    const formPodobnych = document.getElementById("podobne-form");
    const wynikPodobnych = document.getElementById("podobne-wynik");
    const warstwaPodobnych = L.featureGroup().addTo(mapa);
    let miejsce = null;
    let znacznik = null;
    let rysuje = false; // klik podczas rysowania obszaru nie przestawia miejsca
    mapa.on(L.Draw.Event.DRAWSTART, () => { rysuje = true; });
    // „click” mapy przychodzi zaraz po zakończeniu rysowania — flaga gaśnie chwilę później
    mapa.on(L.Draw.Event.DRAWSTOP, () => setTimeout(() => { rysuje = false; }, 300));

    mapa.on("click", (e) => {
        if (rysuje) return;
        miejsce = e.latlng;
        if (znacznik) znacznik.setLatLng(miejsce);
        else znacznik = L.marker(miejsce, { title: "Miejsce do wyceny porównawczej" }).addTo(mapa);
        document.getElementById("podobne-miejsce").textContent = `Miejsce: ${miejsce.lat.toFixed(5)}, ${miejsce.lng.toFixed(5)}.`;
        szukajPodobnych();
    });

    function parametryFiltrow() {
        return new URLSearchParams([...new FormData(filtry)].filter(([, v]) => v));
    }

    async function szukajPodobnych() {
        warstwaPodobnych.clearLayers();
        if (!miejsce) {
            wynikPodobnych.replaceChildren(el("p", "komunikat", "Najpierw kliknij na mapie miejsce."));
            return;
        }
        if (!formPodobnych.reportValidity()) return;
        const parametry = parametryFiltrow();
        for (const [k, v] of new FormData(formPodobnych)) parametry.set(k, v);
        parametry.set("lat", miejsce.lat.toFixed(6));
        parametry.set("lng", miejsce.lng.toFixed(6));
        try {
            const odp = await fetch(`${URL_TRANSAKCJE}/${PLIK_ID}/podobne?${parametry}`);
            const w = await odp.json();
            if (!odp.ok) throw new Error(w.blad || `Błąd ${odp.status}`);
            pokazPodobne(w);
        } catch (e) {
            wynikPodobnych.replaceChildren(el("p", "komunikat komunikat--blad", e.message));
        }
    }

    function pokazPodobne(w) {
        L.circle(miejsce, { radius: w.promien_m, color: "#0071e3", weight: 1.5, fill: false, dashArray: "6 5", interactive: false }).addTo(warstwaPodobnych);
        if (!w.liczba) {
            wynikPodobnych.replaceChildren(el("p", "komunikat", "Brak podobnych transakcji w tym promieniu — zwiększ promień albo tolerancję powierzchni, albo poluzuj filtry."));
            return;
        }
        const elementy = [];
        if (!w.wystarczy) {
            elementy.push(el("p", "komunikat", `Podobnych transakcji: ${w.liczba}, mniej niż ${w.min_podobnych} — mediana jest niepewna. Zwiększ promień albo tolerancję.`));
        }
        const kafelki = el("div", "kafelki-rcn");
        kafelki.append(
            kafelek("Podobnych transakcji", liczba.format(w.liczba), `${w.od} – ${w.do}`),
            kafelek("Mediana ceny za m²", `${liczba.format(w.mediana_m2)} zł`, `połowa: ${liczba.format(w.q1_m2)}–${liczba.format(w.q3_m2)} zł`),
            kafelek(`Orientacyjnie za ${liczba.format(w.pow_m2)} m²`, `${liczba.format(w.szacunek)} zł`, `połowa: ${liczba.format(w.szacunek_od)}–${liczba.format(w.szacunek_do)} zł`),
        );
        elementy.push(kafelki);
        const tabela = el("table", "tabela");
        const glowa = el("tr");
        glowa.append(el("th", "liczba", "Odległość"), el("th", "", "Data"), el("th", "liczba", "Powierzchnia"),
            el("th", "", DZIALKI ? "Przeznaczenie" : "Izby"), el("th", "liczba", "Cena"), el("th", "liczba", "Za m²"));
        tabela.appendChild(glowa);
        for (const t of w.transakcje) {
            const tr = el("tr");
            tr.append(el("td", "liczba", `${liczba.format(t.odleglosc_m)} m`), el("td", "", t.data), el("td", "liczba", `${liczba.format(t.pow_m2)} m²`),
                el("td", "", String((DZIALKI ? t.przeznaczenie : t.izby) || "—")), el("td", "liczba", `${liczba.format(t.cena)} zł`), el("td", "liczba", `${liczba.format(t.cena_m2)} zł`));
            tabela.appendChild(tr);
            L.circleMarker([t.lat, t.lng], { radius: 8, color: "#0071e3", weight: 2.5, fill: false })
                .bindTooltip(`${liczba.format(t.cena_m2)} zł/m² · ${liczba.format(t.pow_m2)} m² · ${t.data}`).addTo(warstwaPodobnych);
        }
        const przewijanie = el("div", "przewijanie-cen");
        przewijanie.appendChild(tabela);
        elementy.push(przewijanie);
        if (w.liczba > w.transakcje.length) elementy.push(el("p", "wyciszony opis-cen", `Lista: ${w.transakcje.length} najbliższych z ${w.liczba}; mediana ze wszystkich.`));
        wynikPodobnych.replaceChildren(...elementy);
    }

    formPodobnych.addEventListener("submit", (e) => {
        e.preventDefault();
        szukajPodobnych();
    });

    async function wczytaj() {
        const moj = ++numer;
        const parametry = parametryFiltrow();
        document.getElementById("link-csv-rcn").href = `${URL_TRANSAKCJE}/${PLIK_ID}.csv?${parametry}`;
        document.getElementById("link-raport-rcn").href = `${URL_TRANSAKCJE}/${PLIK_ID}/raport?${parametry}`;
        try {
            const odp = await fetch(`${URL_TRANSAKCJE}/${PLIK_ID}/dane?${parametry}`);
            const d = await odp.json();
            if (!odp.ok) throw new Error(d.blad || `Błąd ${odp.status}`);
            if (moj !== numer) return;
            komunikat.hidden = true;
            uzupelnijListy(d);
            pokaz(d);
            pokazObszary(d);
            if (miejsce) szukajPodobnych(); // te same filtry co reszta strony
            rysujHeksagony();
        } catch (e) {
            komunikat.textContent = e.message;
            komunikat.hidden = false;
        }
    }

    filtry.addEventListener("change", wczytaj);
    widokMapy.addEventListener("change", wczytaj); // punkty albo heksagony — oba z bieżących danych
    wczytaj();
})();
