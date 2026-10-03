// Kalkulator wskaźników zabudowy: zbiera pola formularza, wysyła do
// /mpzp/kalkulator/licz (liczy serwer — mpzp/zabudowa.py) i pokazuje wynik.
(function () {
    "use strict";

    const formularz = document.getElementById("formularz-kalkulatora");
    const listaBudynkow = document.getElementById("budynki");
    const bladEl = document.getElementById("blad-kalkulatora");
    const wskaznikiEl = document.getElementById("wskazniki");
    const zgodnoscEl = document.getElementById("zgodnosc");
    const zapasEl = document.getElementById("zapas");
    const format = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 });
    let opoznienie = null;
    let numer = 0;

    function el(tag, klasa, tekst) {
        const e = document.createElement(tag);
        if (klasa) e.className = klasa;
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    // Polski przecinek dziesiętny: „0,6” → 0.6; puste → "".
    function liczba(tekst) {
        const t = (tekst || "").trim().replace(/\s/g, "").replace(",", ".");
        return t === "" ? "" : t;
    }

    function dodajBudynek(rzut = "", kondygnacje = "", wysokosc = "") {
        const wiersz = el("div", "wiersz-budynku");
        const opisy = { rzut_m2: "Rzut budynku [m²]", kondygnacje: "Kondygnacje", wysokosc_m: "Wysokość [m]" }; // ETAP 227: dla czytnika ekranu
        for (const [nazwa, wartosc, podpowiedz] of [["rzut_m2", rzut, "np. 150"], ["kondygnacje", kondygnacje, "np. 2"], ["wysokosc_m", wysokosc, "np. 8,5"]]) {
            const pole = el("input");
            pole.setAttribute("aria-label", opisy[nazwa]);
            pole.type = "text";
            pole.inputMode = "decimal";
            pole.dataset.pole = nazwa;
            pole.value = wartosc;
            pole.placeholder = podpowiedz;
            wiersz.appendChild(pole);
        }
        const usun = el("button", "przycisk--niebezpieczny", "✕");
        usun.type = "button";
        usun.title = "Usuń budynek";
        usun.addEventListener("click", () => {
            wiersz.remove();
            przelicz();
        });
        wiersz.appendChild(usun);
        listaBudynkow.appendChild(wiersz);
    }

    function zbierz() {
        const pole = (nazwa) => liczba(formularz.elements[nazwa].value);
        return {
            powierzchnia_dzialki: pole("powierzchnia_dzialki"),
            pbc_m2: pole("pbc_m2"),
            budynki: Array.from(listaBudynkow.children).map((w) => {
                const b = {};
                for (const p of w.querySelectorAll("input")) b[p.dataset.pole] = liczba(p.value);
                return b;
            }).filter((b) => b.rzut_m2 !== ""),
            ustalenia: Object.fromEntries(
                ["max_zabudowa_proc", "min_pbc_proc", "min_intensywnosc", "max_intensywnosc", "max_wysokosc_m", "max_kondygnacje"].map((n) => [n, pole(n)])
            ),
        };
    }

    function kafelek(etykieta, wartosc) {
        const k = el("div", "kafelek-kalkulatora");
        k.append(el("span", "kafelek__etykieta", etykieta), el("span", "kafelek-kalkulatora__wartosc", wartosc));
        return k;
    }

    function pokaz(wynik) {
        const w = wynik.wskazniki;
        wskaznikiEl.replaceChildren(
            kafelek("Powierzchnia zabudowy", `${format.format(w.zabudowa_proc)}%`),
            kafelek("Intensywność", format.format(w.intensywnosc)),
            kafelek("Biologicznie czynna", `${format.format(w.pbc_proc)}%`),
            kafelek("Pow. całkowita", `${format.format(w.powierzchnia_calkowita_m2)} m²`)
        );

        zgodnoscEl.replaceChildren();
        if (wynik.zgodnosc.length === 0) zgodnoscEl.appendChild(el("li", "wyciszony", "Wpisz ustalenia planu."));
        for (const z of wynik.zgodnosc) {
            const li = el("li", z.spelnione ? "zgodnosc--ok" : "zgodnosc--nie");
            const znak = z.rodzaj === "max" ? "≤" : "≥";
            const j = z.jednostka === "m" ? " m" : z.jednostka; // „8,5 m”, ale „24%”
            li.append(
                el("span", "zgodnosc__ikona", z.spelnione ? "✓" : "✗"),
                el("span", "", z.parametr),
                el("span", "zgodnosc__liczby", `${format.format(z.wartosc)}${j} ${znak} ${format.format(z.granica)}${j}`)
            );
            zgodnoscEl.appendChild(li);
        }

        zapasEl.replaceChildren();
        const zapas = wynik.zapas;
        if (zapas.rzut_m2 === null && zapas.powierzchnia_calkowita_m2 === null) {
            zapasEl.appendChild(el("p", "wyciszony", "Wpisz maks. % zabudowy, min. % PBC albo maks. intensywność."));
        }
        if (zapas.rzut_m2 !== null) zapasEl.appendChild(el("p", "", `Rzut: jeszcze ${format.format(zapas.rzut_m2)} m² zabudowy.`));
        if (zapas.powierzchnia_calkowita_m2 !== null) {
            zapasEl.appendChild(el("p", "", `Powierzchnia całkowita: jeszcze ${format.format(zapas.powierzchnia_calkowita_m2)} m² (wszystkie kondygnacje).`));
        }
    }

    async function przelicz() {
        const dane = zbierz();
        const moj = ++numer; // unieważnia odpowiedzi na wcześniejsze przeliczenia
        if (dane.powierzchnia_dzialki === "") {
            bladEl.hidden = false;
            bladEl.textContent = "Wpisz powierzchnię działki.";
            return;
        }
        try {
            const odpowiedz = await fetch(URL_LICZ, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(dane),
            });
            const wynik = await odpowiedz.json();
            if (moj !== numer) return;
            if (!odpowiedz.ok) throw new Error(wynik.blad || `Błąd ${odpowiedz.status}`);
            bladEl.hidden = true;
            pokaz(wynik);
        } catch (e) {
            if (moj !== numer) return;
            bladEl.hidden = false;
            bladEl.textContent = e.message;
        }
    }

    formularz.addEventListener("input", () => {
        clearTimeout(opoznienie);
        opoznienie = setTimeout(przelicz, 250);
    });
    formularz.addEventListener("submit", (e) => e.preventDefault());
    document.getElementById("dodaj-budynek").addEventListener("click", () => dodajBudynek());

    dodajBudynek();
    przelicz();
})();
