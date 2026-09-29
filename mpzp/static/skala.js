// Kalkulator skali: wysyła pola do /mpzp/skala/licz (mpzp/skala.py) i
// wpisuje wyniki pod odpowiednimi polami.
(function () {
    "use strict";

    const formularz = document.getElementById("formularz-skali");
    const bladEl = document.getElementById("blad-skali");
    const f = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 });
    let opoznienie = null;
    let numer = 0;

    function wynik(nazwa, tekst) {
        formularz.querySelector(`[data-wynik="${nazwa}"]`).textContent = tekst;
    }

    function metry(m) {
        return m >= 1000 ? `${f.format(m / 1000)} km (${f.format(m)} m)` : `${f.format(m)} m`;
    }

    function pokaz(w) {
        const mian = `1:${f.format(w.mianownik)}`;
        wynik("dlugosc_teren_m", w.dlugosc_teren_m !== undefined ? `= ${metry(w.dlugosc_teren_m)} w terenie` : "—");
        wynik("dlugosc_rysunek_mm", w.dlugosc_rysunek_mm !== undefined ? `= ${f.format(w.dlugosc_rysunek_mm)} mm (${f.format(w.dlugosc_rysunek_mm / 10)} cm) na rysunku ${mian}` : "—");
        wynik("pow_teren_m2", w.pow_teren_m2 !== undefined ? `= ${f.format(w.pow_teren_m2)} m² (${f.format(w.pow_teren_m2 / 10000)} ha) w terenie` : "—");
        wynik("pow_rysunek_cm2", w.pow_rysunek_cm2 !== undefined ? `= ${f.format(w.pow_rysunek_cm2)} cm² na rysunku ${mian}` : "—");
        if (!w.dobor) {
            wynik("dobor", "—");
        } else if (w.dobor.mianownik === null) {
            wynik("dobor", "Teren nie mieści się na tym arkuszu nawet w skali 1:100 000 — wybierz większy arkusz.");
        } else {
            const d = w.dobor;
            wynik(
                "dobor",
                `Skala 1:${f.format(d.mianownik)}, orientacja ${d.orientacja}. Rysunek ${f.format(d.rysunek_mm[0])} × ${f.format(d.rysunek_mm[1])} mm, wypełnia ${f.format(d.wypelnienie_proc)}% pola arkusza.`
            );
        }
    }

    async function przelicz() {
        const dane = Object.fromEntries(new FormData(formularz).entries());
        const moj = ++numer;
        try {
            const odpowiedz = await fetch(URL_SKALA, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(dane),
            });
            const w = await odpowiedz.json();
            if (moj !== numer) return;
            if (!odpowiedz.ok) throw new Error(w.blad || `Błąd ${odpowiedz.status}`);
            bladEl.hidden = true;
            pokaz(w);
        } catch (e) {
            if (moj !== numer) return;
            bladEl.textContent = e.message;
            bladEl.hidden = false;
            // Stare wyniki nie mogą udawać odpowiedzi na błędne dane.
            for (const pole of formularz.querySelectorAll("[data-wynik]")) pole.textContent = "—";
        }
    }

    function zaplanuj() {
        clearTimeout(opoznienie);
        opoznienie = setTimeout(przelicz, 200);
    }

    formularz.addEventListener("input", zaplanuj);
    formularz.addEventListener("change", zaplanuj);
    formularz.addEventListener("submit", (e) => e.preventDefault());
    for (const przycisk of formularz.querySelectorAll("[data-skala]")) {
        przycisk.addEventListener("click", () => {
            formularz.elements.mianownik.value = przycisk.dataset.skala;
            przelicz();
        });
    }
    przelicz();
})();
