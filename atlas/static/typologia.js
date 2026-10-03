// Atlas: typologia gmin (ETAP 124) — wybór wskaźników i k, wynik, kartogram, CSV.
// Podział liczy serwer (atlas/typologia.py); tu tylko tabele i obrazek mapy.
(function () {
    "use strict";

    const formularz = document.getElementById("formularz-typologii");
    if (!formularz) return; // za mało wskaźników w zestawie

    const poleWoj = document.getElementById("pole-woj");
    const poleRok = document.getElementById("pole-rok");
    const poleK = document.getElementById("pole-k");
    const komunikat = document.getElementById("komunikat");
    const stan = document.getElementById("stan");
    const pola = [...document.querySelectorAll(".wskaznik-typologii")];
    const KLUCZ = "atlas.typologia";
    let numerZapytania = 0;

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function liczba(x, miejsca) {
        return x.toLocaleString("pl-PL", { maximumFractionDigits: miejsca });
    }

    function pokazBlad(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    function zapamietaj() {
        try {
            localStorage.setItem(KLUCZ, JSON.stringify({ woj: poleWoj.value, rok: poleRok.value, k: poleK.value, wskazniki: pola.filter((p) => p.checked).map((p) => p.value) }));
        } catch (e) {
            // tylko wygoda
        }
    }

    function odczytaj() {
        try {
            return JSON.parse(localStorage.getItem(KLUCZ)) || {};
        } catch (e) {
            return {};
        }
    }

    function parametry() {
        const s = pola.filter((p) => p.checked).map((p) => `${p.value}:1:1`).join(",");
        return new URLSearchParams({ woj: poleWoj.value, rok: poleRok.value, k: poleK.value, s });
    }

    function probka(kolor, tekst) {
        const span = element("span", "probka-typu");
        span.style.background = kolor;
        const wynik = element("span", "typ-gminy");
        wynik.append(span, tekst);
        return wynik;
    }

    function pokazWynik(d, zapytanie) {
        document.getElementById("jakosc").textContent = d.sylwetka === null ? "" :
            `Średnia sylwetka ${liczba(d.sylwetka, 2)} (od −1 do 1): ${d.sylwetka >= 0.5 ? "typy wyraźnie oddzielone" : d.sylwetka >= 0.25 ? "typy oddzielone umiarkowanie" : "podział słaby — spróbuj innej liczby typów albo innych wskaźników"}.`;
        const pominiete = document.getElementById("pominiete");
        pominiete.textContent = d.pominiete.length ? `Pominięte (brak danych któregoś wskaźnika w ${d.rok} r.): ${d.pominiete.join(", ")}.` : "";
        pominiete.hidden = !d.pominiete.length;

        const profile = document.getElementById("profile");
        const glowa = element("tr");
        glowa.append(element("th", "", "Typ"), element("th", "liczba", "Gmin"), element("th", "", "Opis"));
        for (const n of d.skladowe) glowa.appendChild(element("th", "liczba", n));
        profile.replaceChildren(glowa);
        for (const t of d.typy) {
            const tr = element("tr");
            const typ = element("td");
            typ.appendChild(probka(d.kolory[t.nr - 1], `Typ ${t.nr}`));
            tr.append(typ, element("td", "liczba", String(t.liczba)), element("td", "", t.opis));
            t.srednie.forEach((x, i) => tr.appendChild(element("td", "liczba", `${liczba(x, 2)} (${t.profil_z[i] > 0 ? "+" : ""}${liczba(t.profil_z[i], 1)})`)));
            profile.appendChild(tr);
        }

        const gminy = document.getElementById("gminy");
        const g0 = element("tr");
        g0.append(element("th", "", "Typ"), element("th", "", "Gmina"));
        for (const n of d.skladowe) g0.appendChild(element("th", "liczba", n));
        gminy.replaceChildren(g0);
        for (const g of d.gminy) {
            const tr = element("tr");
            const typ = element("td");
            typ.appendChild(probka(d.kolory[g.typ - 1], String(g.typ)));
            tr.append(typ, element("td", "", g.nazwa));
            for (const x of g.surowe) tr.appendChild(element("td", "liczba", liczba(x, 2)));
            gminy.appendChild(tr);
        }

        // ETAP 177: lista gmin do „podobnych” (alfabetycznie)
        const wyborPodobnych = document.getElementById("pole-podobne");
        wyborPodobnych.replaceChildren(new Option("— wybierz gminę —", ""),
            ...[...d.gminy].sort((a, b) => a.nazwa.localeCompare(b.nazwa, "pl")).map((g) => new Option(g.nazwa, g.teryt)));
        wyborPodobnych.dataset.zapytanie = zapytanie;
        document.getElementById("podobne").replaceChildren();
        document.getElementById("link-mapy").href = `${URL_MAPA}?${zapytanie}`;
        document.getElementById("link-csv").href = `${URL_CSV}?${zapytanie}`;
        const mapa = document.getElementById("mapa");
        const mapaStan = document.getElementById("mapa-stan");
        mapaStan.textContent = "Wczytywanie granic gmin…";
        mapa.onload = () => { mapaStan.textContent = ""; };
        mapa.onerror = () => { mapaStan.textContent = "Nie udało się narysować kartogramu (granice gmin z PRG niedostępne?). Tabele i CSV są aktualne."; };
        mapa.src = `${URL_MAPA}?${zapytanie}`;
        document.getElementById("wynik").hidden = false;
    }

    document.getElementById("pole-podobne").addEventListener("change", async (e) => {
        const tabela = document.getElementById("podobne");
        tabela.replaceChildren();
        if (!e.target.value) return;
        try {
            const odpowiedz = await fetch(`${URL_PODOBNE}?${e.target.dataset.zapytanie}&gmina=${e.target.value}`);
            const d = await odpowiedz.json().catch(() => ({}));
            if (!odpowiedz.ok) throw new Error(d.blad || `Błąd ${odpowiedz.status}`);
            const glowa = element("tr");
            glowa.append(element("th", "", "Gmina"), element("th", "liczba", "Odległość"), element("th", "", "Różni się najbardziej"));
            for (const n of d.skladowe) glowa.appendChild(element("th", "liczba", n));
            const wybrana = element("tr", "tabela-bilansu__razem");
            wybrana.append(element("td", "", `${d.gmina.nazwa} (wybrana)`), element("td", "liczba", "0"), element("td", "", ""));
            for (const x of d.gmina.surowe) wybrana.appendChild(element("td", "liczba", liczba(x, 2)));
            tabela.replaceChildren(glowa, wybrana);
            for (const g of d.podobne) {
                const tr = element("tr");
                const r = g.najwieksza_roznica;
                tr.append(element("td", "", g.nazwa), element("td", "liczba", liczba(g.odleglosc, 2)),
                    element("td", "", `${r.wskaznik} (${r.z > 0 ? "wyżej" : "niżej"} o ${liczba(Math.abs(r.z), 1)} odch.)`));
                for (const x of g.surowe) tr.appendChild(element("td", "liczba", liczba(x, 2)));
                tabela.appendChild(tr);
            }
        } catch (blad) {
            pokazBlad(blad.message);
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
            if (numer !== numerZapytania) return;
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            pokazWynik(dane, zapytanie);
            stan.textContent = `${dane.gminy.length} gmin w ${dane.k} typach.`;
        } catch (e) {
            if (numer !== numerZapytania) return;
            stan.textContent = "";
            pokazBlad(e.message);
        }
    }

    async function start() {
        const u = odczytaj();
        if (u.rok) poleRok.value = u.rok;
        if (u.k) poleK.value = u.k;
        for (const p of pola) p.checked = (u.wskazniki || []).includes(p.value);
        try {
            const odpowiedz = await fetch(URL_WOJEWODZTWA);
            const woj = await odpowiedz.json();
            if (!odpowiedz.ok) throw new Error(woj.blad || "Nie udało się wczytać województw.");
            poleWoj.replaceChildren(new Option("— wybierz —", ""));
            for (const w of woj) poleWoj.appendChild(new Option(w.nazwa, w.bdl_id));
            let ostatnie = u.woj;
            try {
                ostatnie = ostatnie || localStorage.getItem("atlas.raport.woj");
            } catch (e) {
                // bez pamięci
            }
            if (ostatnie && woj.some((w) => w.bdl_id === ostatnie)) poleWoj.value = ostatnie;
        } catch (e) {
            pokazBlad(e.message);
        }
    }

    // ETAP 125: sylwetka dla k = 2…8 — pomoc w wyborze liczby typów
    async function porownajK() {
        pokazBlad("");
        zapamietaj();
        const sekcja = document.getElementById("sylwetki");
        const tabela = document.getElementById("tabela-sylwetek");
        const numer = ++numerZapytania;
        stan.textContent = "Liczę podziały dla 2–8 typów…";
        try {
            const odpowiedz = await fetch(`${URL_SYLWETKI}?${parametry()}`);
            const dane = await odpowiedz.json().catch(() => ({}));
            if (numer !== numerZapytania) return;
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            const glowa = element("tr");
            glowa.append(element("th", "liczba", "Typów"), element("th", "liczba", "Średnia sylwetka"), element("th", "", ""));
            tabela.replaceChildren(glowa);
            const maks = Math.max(...dane.map((w) => w.sylwetka || 0), 0.01);
            for (const w of dane) {
                const tr = element("tr", w.najlepsza ? "sylwetka--najlepsza" : "");
                tr.tabIndex = 0;
                tr.title = `Wybierz ${w.k} typów`;
                const pasek = element("span", "sylwetka__pasek");
                pasek.style.width = `${Math.max(0, (100 * (w.sylwetka || 0)) / maks)}%`;
                const tor = element("td", "sylwetka__tor");
                tor.appendChild(pasek);
                tr.append(element("td", "liczba", String(w.k)), element("td", "liczba", (w.sylwetka === null ? "—" : liczba(w.sylwetka, 2)) + (w.najlepsza ? " ★" : "")), tor);
                const wybierz = () => { poleK.value = String(w.k); zapamietaj(); formularz.requestSubmit(); };
                tr.addEventListener("click", wybierz);
                tr.addEventListener("keydown", (e) => { if (e.key === "Enter") wybierz(); });
                tabela.appendChild(tr);
            }
            sekcja.hidden = false;
            stan.textContent = "";
        } catch (e) {
            if (numer !== numerZapytania) return;
            stan.textContent = "";
            pokazBlad(e.message);
        }
    }

    document.getElementById("porownaj-k").addEventListener("click", porownajK);
    formularz.addEventListener("submit", policz);
    formularz.addEventListener("change", zapamietaj);
    start();
})();
