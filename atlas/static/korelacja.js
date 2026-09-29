// Korelacja wskaźnika z mapy z drugim wskaźnikiem: wykres rozrzutu (SVG)
// z linią regresji, r Pearsona, rho Spearmana, R². Liczy serwer
// (atlas/statystyki.py: korelacja); tu tylko rysujemy.
(function () {
    "use strict";

    const NS = "http://www.w3.org/2000/svg";
    const SZER = 520;
    const WYS = 320;
    const M = { gora: 16, prawo: 16, dol: 44, lewo: 64 };

    const pole = document.getElementById("pole-korelacja");
    const podpowiedzi = document.getElementById("podpowiedzi-korelacja");
    const status = document.getElementById("status-korelacji");
    const wynikEl = document.getElementById("wynik-korelacji");
    const wykresEl = document.getElementById("wykres-korelacji");
    const liczbyEl = document.getElementById("liczby-korelacji");
    const opisEl = document.getElementById("opis-korelacji");
    const format = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 3 });
    const formatOsi = new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 });

    let daneMapy = null;
    let opoznienie = null;

    function el(tag, klasa, tekst) {
        const e = document.createElement(tag);
        if (klasa) e.className = klasa;
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    function svg(nazwa, atrybuty, rodzic) {
        const e = document.createElementNS(NS, nazwa);
        for (const [k, v] of Object.entries(atrybuty)) e.setAttribute(k, v);
        if (rodzic) rodzic.appendChild(e);
        return e;
    }

    function skrot(tekst, n) {
        return tekst.length > n ? `${tekst.slice(0, n - 1)}…` : tekst;
    }

    document.addEventListener("atlas:dane", (e) => {
        daneMapy = e.detail;
        wynikEl.hidden = true;
        status.textContent = "";
        pole.value = "";
    });

    // ---------- wybór drugiego wskaźnika ----------

    pole.addEventListener("input", () => {
        clearTimeout(opoznienie);
        const fraza = pole.value.trim();
        if (fraza.length < 3) {
            podpowiedzi.hidden = true;
            return;
        }
        opoznienie = setTimeout(async () => {
            podpowiedzi.replaceChildren(el("li", "podpowiedzi__info", "Szukam…"));
            podpowiedzi.hidden = false;
            try {
                const odpowiedz = await fetch(`${URL_ZMIENNE}?q=${encodeURIComponent(fraza)}`);
                const zmienne = await odpowiedz.json();
                if (!odpowiedz.ok) throw new Error(zmienne.blad);
                podpowiedzi.replaceChildren();
                for (const z of zmienne) {
                    const li = el("li", "", z.nazwa);
                    li.appendChild(el("span", "etykieta", z.jednostka || "—"));
                    li.addEventListener("click", () => {
                        pole.value = z.nazwa;
                        podpowiedzi.hidden = true;
                        policz(z.id);
                    });
                    podpowiedzi.appendChild(li);
                }
                if (!zmienne.length) podpowiedzi.appendChild(el("li", "podpowiedzi__info", "Brak wskaźników o takiej nazwie."));
            } catch (err) {
                podpowiedzi.replaceChildren(el("li", "podpowiedzi__info", `Błąd: ${err.message}`));
            }
        }, 350);
    });

    document.addEventListener("click", (e) => {
        if (!e.target.closest(".pole-korelacji")) podpowiedzi.hidden = true;
    });

    // ---------- obliczenie i wykres ----------

    async function policz(zmienna2) {
        if (!daneMapy) return;
        status.textContent = "Liczę korelację…";
        wynikEl.hidden = true;
        const parametry = new URLSearchParams({
            zmienna: daneMapy.zmienna.id,
            zmienna2,
            rok: daneMapy.rok,
            woj: daneMapy.wojewodztwo.bdl_id,
        });
        try {
            const odpowiedz = await fetch(`${URL_KORELACJA}?${parametry}`);
            const wynik = await odpowiedz.json();
            if (!odpowiedz.ok) throw new Error(wynik.blad || `Błąd ${odpowiedz.status}`);
            pokaz(wynik);
        } catch (err) {
            status.textContent = err.message;
        }
    }

    function liczba(etykieta, wartosc) {
        const div = el("div", "profil__liczba");
        div.append(el("span", "kafelek__etykieta", etykieta), el("span", "profil__wartosc", wartosc));
        return div;
    }

    function pokaz(w) {
        status.textContent = "";
        const brak = (v) => (v === null ? "—" : format.format(v));
        liczbyEl.replaceChildren(
            liczba("r Pearsona", brak(w.pearson)),
            liczba("rho Spearmana", brak(w.spearman)),
            liczba("R²", brak(w.r2)),
            liczba("gmin", String(w.n))
        );
        opisEl.textContent = `Siła związku: ${w.opis}.`;
        if (w.r2 !== null) opisEl.textContent += ` Zróżnicowanie „${skrot(w.zmienna_x.nazwa, 40)}” wyjaśnia liniowo ${new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 }).format(w.r2 * 100)}% zróżnicowania drugiego wskaźnika.`;
        rysuj(w);
        wynikEl.hidden = false;
    }

    function rysuj(w) {
        wykresEl.replaceChildren();
        if (w.punkty.length < 2) return;
        const xs = w.punkty.map((p) => p.x);
        const ys = w.punkty.map((p) => p.y);
        const zakres = (v) => {
            const min = Math.min(...v);
            const max = Math.max(...v);
            const zapas = (max - min) * 0.06 || Math.abs(max) * 0.1 || 1;
            // Dane nieujemne (większość wskaźników GUS) — oś nie schodzi poniżej zera.
            return [min >= 0 ? Math.max(0, min - zapas) : min - zapas, max + zapas];
        };
        const [x0, x1] = zakres(xs);
        const [y0, y1] = zakres(ys);
        const x = (v) => M.lewo + ((v - x0) / (x1 - x0)) * (SZER - M.lewo - M.prawo);
        const y = (v) => M.gora + (1 - (v - y0) / (y1 - y0)) * (WYS - M.gora - M.dol);

        const s = svg("svg", { viewBox: `0 0 ${SZER} ${WYS}`, class: "wykres", role: "img" }, wykresEl);
        svg("title", {}, s).textContent = `Wykres rozrzutu: ${w.zmienna_x.nazwa} i ${w.zmienna_y.nazwa}`;

        for (let i = 0; i <= 3; i += 1) {
            const vy = y0 + ((y1 - y0) * i) / 3;
            svg("line", { x1: M.lewo, x2: SZER - M.prawo, y1: y(vy), y2: y(vy), class: "wykres__siatka" }, s);
            svg("text", { x: M.lewo - 6, y: y(vy) + 3, class: "wykres__os", "text-anchor": "end" }, s).textContent = formatOsi.format(vy);
            const vx = x0 + ((x1 - x0) * i) / 3;
            svg("text", { x: x(vx), y: WYS - M.dol + 14, class: "wykres__os", "text-anchor": "middle" }, s).textContent = formatOsi.format(vx);
        }
        svg("text", { x: (M.lewo + SZER - M.prawo) / 2, y: WYS - 8, class: "wykres__os wykres__tytul-osi", "text-anchor": "middle" }, s)
            .textContent = skrot(`${w.zmienna_x.nazwa} [${w.zmienna_x.jednostka || "–"}]`, 80);
        svg("text", { x: 12, y: (M.gora + WYS - M.dol) / 2, class: "wykres__os wykres__tytul-osi", "text-anchor": "middle",
            transform: `rotate(-90 12 ${(M.gora + WYS - M.dol) / 2})` }, s)
            .textContent = skrot(`${w.zmienna_y.nazwa} [${w.zmienna_y.jednostka || "–"}]`, 45);

        if (w.regresja) {
            const a = w.regresja.nachylenie;
            const b = w.regresja.wyraz_wolny;
            svg("line", { x1: x(x0), y1: y(a * x0 + b), x2: x(x1), y2: y(a * x1 + b), class: "wykres__odniesienie" }, s);
        }

        const dymek = el("div", "wykres__dymek");
        dymek.hidden = true;
        for (const p of w.punkty) {
            const punkt = svg("circle", { cx: x(p.x), cy: y(p.y), r: 4, class: "wykres__rozrzut" }, s);
            // Większe, niewidoczne pole trafienia niż sam punkt.
            const trafienie = svg("circle", { cx: x(p.x), cy: y(p.y), r: 9, fill: "transparent" }, s);
            trafienie.addEventListener("mouseenter", () => {
                punkt.classList.add("wykres__rozrzut--aktywny");
                const r = s.getBoundingClientRect();
                dymek.textContent = `${p.nazwa}: ${format.format(p.x)} | ${format.format(p.y)}`;
                dymek.hidden = false;
                dymek.style.left = `${(x(p.x) / SZER) * r.width}px`;
                dymek.style.top = `${(y(p.y) / WYS) * r.height - 34}px`;
            });
            trafienie.addEventListener("mouseleave", () => {
                punkt.classList.remove("wykres__rozrzut--aktywny");
                dymek.hidden = true;
            });
        }
        wykresEl.appendChild(dymek);
    }
})();
