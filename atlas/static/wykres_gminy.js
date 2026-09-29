// Wykres liniowy szeregu czasowego jednej gminy (inline SVG, bez bibliotek).
// Jedna seria → bez legendy (tytuł karty mówi, co to jest). Linia 2 px,
// dyskretna siatka, etykieta tylko przy ostatnim punkcie, przerywana linia
// odniesienia (mediana województwa w badanym roku), celownik z dymkiem
// po najechaniu. Kolory z tokenów CSS, więc działa w jasnym i ciemnym motywie.
const WykresGminy = (function () {
    "use strict";

    const NS = "http://www.w3.org/2000/svg";
    const SZER = 360;
    const WYS = 180;
    const M = { gora: 14, prawo: 56, dol: 24, lewo: 48 };

    function el(nazwa, atrybuty, rodzic) {
        const e = document.createElementNS(NS, nazwa);
        for (const [k, v] of Object.entries(atrybuty)) e.setAttribute(k, v);
        if (rodzic) rodzic.appendChild(e);
        return e;
    }

    // „Ładne” granice osi: 0 w dół, jeśli dane są blisko zera; inaczej zapas 8%.
    function zakres(wartosci) {
        let min = Math.min(...wartosci);
        let max = Math.max(...wartosci);
        if (min === max) {
            min -= Math.abs(min) * 0.1 || 1;
            max += Math.abs(max) * 0.1 || 1;
        }
        const zapas = (max - min) * 0.08;
        min = min >= 0 && min - zapas < 0 ? 0 : min - zapas;
        return [min, max + zapas];
    }

    /**
     * rysuj(kontener, szereg [{rok, wartosc}], {rokWybrany, mediana, format, dymek})
     */
    function rysuj(kontener, szereg, opcje) {
        kontener.replaceChildren();
        const wartosci = szereg.map((p) => p.wartosc);
        if (opcje.mediana !== undefined && opcje.mediana !== null) wartosci.push(opcje.mediana);
        const [yMin, yMax] = zakres(wartosci);
        const lata = szereg.map((p) => p.rok);
        const xMin = Math.min(...lata);
        const xMax = Math.max(...lata);

        const x = (rok) => M.lewo + (xMax === xMin ? 0.5 : (rok - xMin) / (xMax - xMin)) * (SZER - M.lewo - M.prawo);
        const y = (w) => M.gora + (1 - (w - yMin) / (yMax - yMin)) * (WYS - M.gora - M.dol);

        const svg = el("svg", { viewBox: `0 0 ${SZER} ${WYS}`, class: "wykres", role: "img" }, kontener);
        el("title", {}, svg).textContent = opcje.tytul || "Wartości w kolejnych latach";

        // Siatka: 3 linie poziome z etykietami (dyskretna).
        for (let i = 0; i <= 2; i += 1) {
            const w = yMin + ((yMax - yMin) * i) / 2;
            el("line", { x1: M.lewo, x2: SZER - M.prawo, y1: y(w), y2: y(w), class: "wykres__siatka" }, svg);
            el("text", { x: M.lewo - 6, y: y(w) + 3, class: "wykres__os", "text-anchor": "end" }, svg).textContent =
                opcje.formatOsi(w);
        }
        // Oś X: pierwszy i ostatni rok.
        for (const rok of [xMin, xMax]) {
            el("text", { x: x(rok), y: WYS - 6, class: "wykres__os", "text-anchor": "middle" }, svg).textContent = rok;
        }

        // Linia odniesienia: mediana województwa w badanym roku.
        if (opcje.mediana !== undefined && opcje.mediana !== null) {
            el("line", {
                x1: M.lewo, x2: SZER - M.prawo, y1: y(opcje.mediana), y2: y(opcje.mediana), class: "wykres__odniesienie",
            }, svg);
            el("text", { x: SZER - M.prawo + 4, y: y(opcje.mediana) + 3, class: "wykres__os" }, svg).textContent =
                opcje.opisMediany;
        }

        // Seria.
        const punkty = szereg.map((p) => `${x(p.rok)},${y(p.wartosc)}`).join(" ");
        el("polyline", { points: punkty, class: "wykres__linia" }, svg);

        // Wyróżniony rok (badany) i ostatni punkt z etykietą.
        const wybrany = szereg.find((p) => p.rok === opcje.rokWybrany);
        if (wybrany) el("circle", { cx: x(wybrany.rok), cy: y(wybrany.wartosc), r: 4.5, class: "wykres__punkt" }, svg);
        const ostatni = szereg[szereg.length - 1];
        el("text", { x: x(ostatni.rok) + 6, y: y(ostatni.wartosc) - 6, class: "wykres__etykieta" }, svg).textContent =
            opcje.formatOsi(ostatni.wartosc);

        // Celownik + dymek po najechaniu (strefa całej wysokości wykresu).
        const celownik = el("line", { y1: M.gora, y2: WYS - M.dol, class: "wykres__celownik", visibility: "hidden" }, svg);
        const kropka = el("circle", { r: 4, class: "wykres__punkt", visibility: "hidden" }, svg);
        const strefa = el("rect", {
            x: M.lewo, y: 0, width: SZER - M.lewo - M.prawo, height: WYS, fill: "transparent",
        }, svg);
        const dymek = opcje.dymek;
        strefa.addEventListener("mousemove", (e) => {
            const r = svg.getBoundingClientRect();
            const mx = ((e.clientX - r.left) / r.width) * SZER;
            let najblizszy = szereg[0];
            for (const p of szereg) if (Math.abs(x(p.rok) - mx) < Math.abs(x(najblizszy.rok) - mx)) najblizszy = p;
            const px = x(najblizszy.rok);
            const py = y(najblizszy.wartosc);
            celownik.setAttribute("x1", px);
            celownik.setAttribute("x2", px);
            celownik.setAttribute("visibility", "visible");
            kropka.setAttribute("cx", px);
            kropka.setAttribute("cy", py);
            kropka.setAttribute("visibility", "visible");
            dymek.textContent = `${najblizszy.rok}: ${opcje.formatDymka(najblizszy.wartosc)}`;
            dymek.hidden = false;
            dymek.style.left = `${(px / SZER) * r.width}px`;
            dymek.style.top = `${(py / WYS) * r.height - 34}px`;
        });
        strefa.addEventListener("mouseleave", () => {
            celownik.setAttribute("visibility", "hidden");
            kropka.setAttribute("visibility", "hidden");
            dymek.hidden = true;
        });
        kontener.appendChild(dymek);
    }

    return { rysuj };
})();
