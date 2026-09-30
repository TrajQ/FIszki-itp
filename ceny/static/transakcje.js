// Ceny: transakcje z Rejestru Cen Nieruchomości (ETAP 104).
// Statystyki i progi kolorów liczy serwer (ceny/rcn.py); tu filtry, wykresy i mapa.
// ETAP 105: obszary rysowane na mapie (Leaflet.draw) i ich porównanie.
// ETAP 106: ta sama strona dla działek (CO === "dzialki") — inne filtry i tabela grup.
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

    function klasa(cena, progi) {
        let i = 0;
        while (i < progi.length && cena > progi[i]) i++;
        return i;
    }

    function rysujMape(m) {
        warstwa.clearLayers();
        for (const [lat, lng, cenaM2, data, pow] of m.punkty) {
            L.circleMarker([lat, lng], { radius: 5, weight: 0.6, color: "#3a2a1a", fillColor: KOLORY[klasa(cenaM2, m.progi)], fillOpacity: 0.85 })
                .bindTooltip(`${liczba.format(cenaM2)} zł/m² · ${pow} m² · ${data}`)
                .addTo(warstwa);
        }
        if (pierwszeRysowanie && m.punkty.length) {
            mapa.fitBounds(warstwa.getBounds(), { padding: [20, 20] });
            pierwszeRysowanie = false;
        }
        const legenda = document.getElementById("legenda-rcn");
        legenda.replaceChildren();
        const granice = [null, ...m.progi, null];
        m.progi.length && KOLORY.forEach((kolor, i) => {
            const opis = granice[i] === null ? `do ${liczba.format(granice[i + 1])}` : granice[i + 1] === null ? `ponad ${liczba.format(granice[i])}` : `${liczba.format(granice[i])}–${liczba.format(granice[i + 1])}`;
            const pozycja = el("span", "legenda-rcn__pozycja");
            const probka = el("span", "legenda-rcn__probka");
            probka.style.background = kolor;
            pozycja.append(probka, `${opis} zł/m²`);
            legenda.appendChild(pozycja);
        });
        const uwaga = m.wszystkich_z_polozeniem > m.punkty.length ? ` (na mapie ${m.punkty.length} najnowszych z ${m.wszystkich_z_polozeniem})` : "";
        legenda.appendChild(el("span", "wyciszony", `Kolory: pięć równolicznych klas ceny za m²${uwaga}.`));
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

    async function wczytaj() {
        const moj = ++numer;
        const parametry = new URLSearchParams([...new FormData(filtry)].filter(([, v]) => v));
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
        } catch (e) {
            komunikat.textContent = e.message;
            komunikat.hidden = false;
        }
    }

    filtry.addEventListener("change", wczytaj);
    wczytaj();
})();
