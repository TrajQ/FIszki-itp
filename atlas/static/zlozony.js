// Atlas: wskaźnik złożony (ETAP 84) — wybór składowych, wynik, kartogram, CSV.
(function () {
    "use strict";

    const formularz = document.getElementById("formularz-zlozony");
    if (!formularz) return; // za mało wskaźników w zestawie — strona tylko z odsyłaczem

    const poleWoj = document.getElementById("pole-woj");
    const poleRok = document.getElementById("pole-rok");
    const poleMetoda = document.getElementById("pole-metoda");
    const komunikat = document.getElementById("komunikat");
    const stan = document.getElementById("stan");
    const wynik = document.getElementById("wynik");
    const ranking = document.getElementById("ranking");
    const pominiete = document.getElementById("pominiete");
    const mapa = document.getElementById("mapa");
    const mapaStan = document.getElementById("mapa-stan");
    const wiersze = [...document.querySelectorAll(".tabela-skladowych tbody tr")];
    const KLUCZ = "atlas.zlozony";
    let numerZapytania = 0;

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function pokazBlad(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    function liczba(x, miejsca) {
        return x.toLocaleString("pl-PL", { maximumFractionDigits: miejsca });
    }

    // ---------- ustawienia zapamiętane w przeglądarce (tylko wygoda) ----------

    function zapamietaj() {
        const ustawienia = {
            woj: poleWoj.value,
            rok: poleRok.value,
            metoda: poleMetoda.value,
            skladowe: Object.fromEntries(wiersze.map((w) => [w.dataset.id, {
                wlaczona: w.querySelector(".skladowa-wlaczona").checked,
                kierunek: w.querySelector(".skladowa-kierunek").value,
                waga: w.querySelector(".skladowa-waga").value,
            }])),
        };
        try {
            localStorage.setItem(KLUCZ, JSON.stringify(ustawienia));
        } catch (e) {
            // bez pamięci też działa
        }
    }

    function odczytaj() {
        try {
            return JSON.parse(localStorage.getItem(KLUCZ)) || {};
        } catch (e) {
            return {};
        }
    }

    function oznaczWylaczone() {
        for (const w of wiersze) w.classList.toggle("wylaczona", !w.querySelector(".skladowa-wlaczona").checked);
    }

    // ---------- zapytanie ----------

    function parametry() {
        const skladowe = wiersze
            .filter((w) => w.querySelector(".skladowa-wlaczona").checked)
            .map((w) => `${w.dataset.id}:${w.querySelector(".skladowa-kierunek").value}:${w.querySelector(".skladowa-waga").value}`);
        return new URLSearchParams({ woj: poleWoj.value, rok: poleRok.value, metoda: poleMetoda.value, s: skladowe.join(",") });
    }

    function pokazWynik(dane, zapytanie) {
        ranking.replaceChildren();
        const naglowek = element("tr");
        naglowek.append(element("th", "liczba", "Miejsce"), element("th", "", "Gmina"), element("th", "liczba", "Wskaźnik"));
        for (const s of dane.skladowe) {
            const th = element("th", "liczba", `${s.nazwa} (${s.kierunek > 0 ? "+" : "−"})`);
            th.title = "wartość surowa / po normalizacji";
            naglowek.appendChild(th);
        }
        ranking.appendChild(element("thead")).appendChild(naglowek);
        const cialo = ranking.appendChild(element("tbody"));
        for (const g of dane.gminy) {
            const tr = element("tr");
            tr.append(element("td", "liczba", String(g.miejsce)), element("td", "", g.nazwa), element("td", "liczba", liczba(g.wartosc, 3)));
            g.surowe.forEach((x, i) => tr.appendChild(element("td", "liczba", `${liczba(x, 2)} / ${liczba(g.skladowe[i], 2)}`)));
            cialo.appendChild(tr);
        }
        pominiete.textContent = dane.pominiete.length
            ? `Pominięte (brak danych którejś składowej w ${dane.rok} r.): ${dane.pominiete.join(", ")}.`
            : "";
        pominiete.hidden = !dane.pominiete.length;

        document.getElementById("formularz-lat").dataset.zapytanie = zapytanie;
        if (!document.getElementById("pole-lat").value) {
            const rok = Number(new URLSearchParams(zapytanie).get("rok"));
            document.getElementById("pole-lat").value = [rok - 8, rok - 4, rok].join(",");
        }
        document.getElementById("link-mapy").href = `${URL_MAPA}?${zapytanie}`;
        document.getElementById("link-csv").href = `${URL_CSV}?${zapytanie}`;
        mapaStan.textContent = "Wczytywanie granic gmin…";
        mapa.onload = () => { mapaStan.textContent = ""; };
        mapa.onerror = () => { mapaStan.textContent = "Nie udało się narysować kartogramu (granice gmin z PRG niedostępne?). Ranking i CSV są aktualne."; };
        mapa.src = `${URL_MAPA}?${zapytanie}`;
        wynik.hidden = false;
    }

    // ETAP 194: stabilność rankingu — liczy serwer (atlas/zlozony.stabilnosc)
    document.getElementById("formularz-lat").addEventListener("submit", async (e) => {
        e.preventDefault();
        const opis = document.getElementById("opis-stabilnosci");
        const tabela = document.getElementById("tabela-stabilnosci");
        const parametry = new URLSearchParams(e.target.dataset.zapytanie);
        parametry.set("lata", document.getElementById("pole-lat").value.replace(/\s/g, ""));
        opis.hidden = false;
        opis.textContent = "Liczę… (każdy rok to osobne zapytanie do GUS)";
        tabela.hidden = true;
        try {
            const odpowiedz = await fetch(`${URL_LATA}?${parametry}`);
            const d = await odpowiedz.json().catch(() => ({}));
            if (!odpowiedz.ok) throw new Error(d.blad || `Błąd ${odpowiedz.status}`);
            const glowa = element("tr");
            glowa.appendChild(element("th", "", "Gmina"));
            for (const r of d.lata) glowa.appendChild(element("th", "liczba", String(r)));
            glowa.appendChild(element("th", "liczba", "Zmiana miejsca"));
            tabela.replaceChildren(glowa);
            for (const g of d.gminy) {
                const tr = element("tr");
                tr.appendChild(element("td", "", g.nazwa));
                for (const r of d.lata) tr.appendChild(element("td", "liczba", String(g.miejsca[r])));
                tr.appendChild(element("td", `liczba ${g.zmiana > 0 ? "wartosc-plus" : g.zmiana < 0 ? "wartosc-minus" : ""}`, g.zmiana > 0 ? `↑ ${g.zmiana}` : g.zmiana < 0 ? `↓ ${-g.zmiana}` : "="));
                tabela.appendChild(tr);
            }
            opis.textContent = `Miejsca wśród ${d.liczba_gmin} gmin z danymi we wszystkich latach. Zgodność rankingu ${d.lata[0]} i ${d.lata[d.lata.length - 1]} (rho Spearmana): ${d.rho === null ? "—" : liczba(d.rho, 2)} — ${d.opis_rho}. Blisko 1 — kolejność gmin prawie się nie zmienia.`;
            tabela.hidden = false;
        } catch (blad) {
            opis.textContent = blad.message;
        }
    });

    async function policz(zdarzenie) {
        zdarzenie.preventDefault();
        pokazBlad("");
        zapamietaj();
        const zapytanie = parametry().toString();
        const numer = ++numerZapytania;
        stan.textContent = "Liczę… (pierwsze pobranie z GUS może chwilę potrwać)";
        try {
            const odpowiedz = await fetch(`${URL_WYNIK}?${zapytanie}`);
            const dane = await odpowiedz.json().catch(() => ({}));
            if (numer !== numerZapytania) return; // w międzyczasie nowsze zapytanie
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            pokazWynik(dane, zapytanie);
            stan.textContent = `${dane.gminy.length} gmin, ${dane.nazwa_metody}.`;
        } catch (e) {
            if (numer !== numerZapytania) return;
            stan.textContent = "";
            pokazBlad(e.message);
        }
    }

    // ---------- start ----------

    async function start() {
        const ustawienia = odczytaj();
        if (ustawienia.rok) poleRok.value = ustawienia.rok;
        if (ustawienia.metoda) poleMetoda.value = ustawienia.metoda;
        for (const w of wiersze) {
            const s = (ustawienia.skladowe || {})[w.dataset.id];
            if (!s) continue;
            w.querySelector(".skladowa-wlaczona").checked = s.wlaczona;
            w.querySelector(".skladowa-kierunek").value = s.kierunek;
            w.querySelector(".skladowa-waga").value = s.waga;
        }
        oznaczWylaczone();
        try {
            const odpowiedz = await fetch(URL_WOJEWODZTWA);
            const woj = await odpowiedz.json();
            if (!odpowiedz.ok) throw new Error(woj.blad || "Nie udało się wczytać województw.");
            poleWoj.replaceChildren(new Option("— wybierz —", ""));
            for (const w of woj) poleWoj.appendChild(new Option(w.nazwa, w.bdl_id));
            const ostatnie = ustawienia.woj || localStorageRaportu();
            if (ostatnie && woj.some((w) => w.bdl_id === ostatnie)) poleWoj.value = ostatnie;
        } catch (e) {
            pokazBlad(e.message);
        }
    }

    function localStorageRaportu() {
        try {
            return localStorage.getItem("atlas.raport.woj"); // województwo wybrane w raporcie gminy
        } catch (e) {
            return null;
        }
    }

    formularz.addEventListener("submit", policz);
    formularz.addEventListener("change", () => { oznaczWylaczone(); zapamietaj(); });
    start();
})();
