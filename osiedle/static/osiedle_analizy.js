// Odległości od granicy, cień i przekrój koncepcji osiedla (ETAPy 94, 195, 238).
// Wydzielone z osiedle.js (ETAP 246). Liczy i rysuje serwer (osiedle/cien.py,
// osiedle/przekroj.py); tu tylko wyniki na mapie i w panelu.
(function () {
    "use strict";

    const osiedle = window.osiedle;
    const { mapa, rysunek, zaznacz, zapytaj, dokonczZapis, element, pokazKomunikat } = osiedle;
    const formatWsk = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 });
    const formatM2 = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 });
    const formatProc = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });

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
        if (!osiedle.koncepcja()) return;
        await dokonczZapis();
        let w;
        try {
            w = await zapytaj(`${URL_KONCEPCJE}/${osiedle.koncepcja().id}/cien?dzien=${document.getElementById("dzien-cienia").value}`);
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

    // ---------- przekrój A–A′ (ETAP 238) — liczy i rysuje serwer (osiedle/przekroj.py) ----------

    const warstwaPrzekroju = L.featureGroup().addTo(mapa);
    const wynikPrzekroju = document.getElementById("wynik-przekroju");
    const przyciskUkryjPrzekroj = document.getElementById("ukryj-przekroj");
    const suwakKata = document.getElementById("kat-przekroju");
    const suwakPrzesuniecia = document.getElementById("przesuniecie-przekroju");
    let opoznieniePrzekroju = null;
    let numerPrzekroju = 0;

    function kierunekSlownie(kat) {
        const nazwy = ["N–S", "NNE–SSW", "NE–SW", "ENE–WSW", "W–E", "WNW–ESE", "NW–SE", "NNW–SSE"];
        return nazwy[Math.round(kat / 22.5) % 8];
    }

    function opiszSuwaki() {
        document.getElementById("opis-kata").textContent = `${suwakKata.value}° (${kierunekSlownie(Number(suwakKata.value))})`;
        const p = Number(suwakPrzesuniecia.value);
        document.getElementById("opis-przesuniecia").textContent = p === 0 ? "przez środek" : `${p > 0 ? "+" : ""}${p}%`;
    }

    function ukryjPrzekroj() {
        numerPrzekroju += 1;
        warstwaPrzekroju.clearLayers();
        wynikPrzekroju.hidden = true;
        przyciskUkryjPrzekroj.hidden = true;
    }

    async function pokazPrzekroj() {
        if (!osiedle.koncepcja()) return;
        await dokonczZapis();
        const moj = ++numerPrzekroju;
        const parametry = `kat=${suwakKata.value}&przesuniecie=${suwakPrzesuniecia.value}`;
        let p;
        try {
            p = await zapytaj(`${URL_KONCEPCJE}/${osiedle.koncepcja().id}/przekroj?${parametry}`);
        } catch (e) {
            if (moj === numerPrzekroju) pokazKomunikat(e.message);
            return;
        }
        if (moj !== numerPrzekroju) return;
        warstwaPrzekroju.clearLayers();
        const [a, b] = p.linia.map(([lon, lat]) => [lat, lon]);
        L.polyline([a, b], { color: "#0071e3", weight: 3, dashArray: "10 6", interactive: false }).addTo(warstwaPrzekroju);
        for (const [punkt, litera] of [[a, "A"], [b, "A′"]]) {
            L.circleMarker(punkt, { radius: 4, color: "#0071e3", fillOpacity: 1, interactive: false })
                .bindTooltip(litera, { permanent: true, direction: "top", className: "przekroj__litera" }).addTo(warstwaPrzekroju);
        }
        const svg = `${URL_KONCEPCJE}/${osiedle.koncepcja().id}/przekroj.svg?${parametry}`;
        document.getElementById("rysunek-przekroju").src = svg;
        document.getElementById("pobierz-przekroj").href = `${svg}&pobierz=1`;
        document.getElementById("raport-przekroju").href = `${URL_KONCEPCJE}/${osiedle.koncepcja().id}/raport?przekroj_kat=${suwakKata.value}&przekroj_przes=${suwakPrzesuniecia.value}`;
        const budynki = new Set(p.budynki.map((x) => x.nr)).size;
        let opis = `Długość ${formatWsk.format(p.dlugosc_m)} m. ` + (budynki ? `Linia przecina ${budynki} ${budynki === 1 ? "budynek" : budynki < 5 ? "budynki" : "budynków"}` : "Linia nie przecina żadnego budynku — przesuń ją albo zmień kierunek");
        if (p.odstepy.length) opis += `; najmniejszy odstęp ${formatWsk.format(Math.min(...p.odstepy.map((o) => o.odstep_m)))} m`;
        document.getElementById("opis-przekroju").textContent = `${opis}.`;
        wynikPrzekroju.hidden = false;
        przyciskUkryjPrzekroj.hidden = false;
    }

    document.getElementById("pokaz-przekroj").addEventListener("click", pokazPrzekroj);
    przyciskUkryjPrzekroj.addEventListener("click", ukryjPrzekroj);
    for (const suwak of [suwakKata, suwakPrzesuniecia]) {
        suwak.addEventListener("input", () => {
            opiszSuwaki();
            if (wynikPrzekroju.hidden) return; // przelicza na bieżąco dopiero po „Pokaż”
            clearTimeout(opoznieniePrzekroju);
            opoznieniePrzekroju = setTimeout(pokazPrzekroj, 250);
        });
    }
    opiszSuwaki();

    document.addEventListener("osiedle:otwarto", () => {
        ukryjCien();
        ukryjPrzekroj();
    });
    // Rysunek zapisany po zmianie — policzony cień już nie obowiązuje.
    document.addEventListener("osiedle:zapisano", () => {
        if (!warstwaCienia.getLayers().length) return;
        ukryjCien();
        wynikCienia.hidden = false;
        wynikCienia.replaceChildren(element("p", "wyciszony", "Rysunek się zmienił — kliknij „Pokaż”, żeby policzyć cień od nowa."));
    });
})();
