// Moduł przepisy: strona aktu — filtr spisu, zmiana nazwy, usunięcie.
(function () {
    "use strict";

    const komunikat = document.getElementById("komunikat");

    function pokazBlad(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    // Filtr spisu: „15a” zostawia jednostki, których numer zaczyna się od wpisanego.
    const filtrSpisu = document.getElementById("filtr-spisu");
    filtrSpisu.addEventListener("input", () => {
        const szukany = filtrSpisu.value.trim().toLowerCase().replace(/^(art\.?|§)\s*/, "");
        document.querySelectorAll("#spis li").forEach((li) => {
            const link = li.querySelector("a");
            if (!link) {
                li.hidden = Boolean(szukany); // nagłówki rozdziałów tylko bez filtra
                return;
            }
            const numer = link.dataset.oznaczenie.toLowerCase().replace(/^(art\.|§)\s*/, "");
            li.hidden = Boolean(szukany) && !numer.startsWith(szukany);
        });
    });
    filtrSpisu.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        const pierwszy = [...document.querySelectorAll("#spis li:not([hidden]) a")][0];
        if (pierwszy) location.hash = pierwszy.getAttribute("href");
    });

    async function zapytaj(metoda, cialo) {
        const odpowiedz = await fetch(URL_AKTU, {
            method: metoda,
            headers: cialo ? { "Content-Type": "application/json" } : undefined,
            body: cialo ? JSON.stringify(cialo) : undefined,
        });
        const dane = await odpowiedz.json().catch(() => ({}));
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        return dane;
    }

    document.getElementById("zmien-nazwe").addEventListener("click", async () => {
        const naglowek = document.getElementById("nazwa-aktu");
        const nazwa = window.prompt("Nazwa aktu (np. „Ustawa o planowaniu i zagospodarowaniu przestrzennym”):", naglowek.textContent);
        if (nazwa === null) return;
        try {
            const akt = await zapytaj("PUT", { nazwa });
            naglowek.textContent = akt.nazwa;
            pokazBlad("");
        } catch (e) {
            pokazBlad(e.message);
        }
    });

    document.getElementById("usun-akt").addEventListener("click", async () => {
        if (!window.confirm("Usunąć ten akt razem z plikiem PDF?")) return;
        try {
            await zapytaj("DELETE");
            location.href = URL_LISTY;
        } catch (e) {
            pokazBlad(e.message);
        }
    });
})();

// Fiszki z artykułu (ETAP 82): propozycje Gemini (tylko z cytatem w tekście
// artykułu, sprawdza serwer) → zaznaczenie i poprawki → zapis do Fiszek.
(function () {
    "use strict";

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    async function wyslij(url, cialo) {
        const odpowiedz = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cialo || {}) });
        const dane = await odpowiedz.json().catch(() => ({}));
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        return dane;
    }

    function panelPropozycji(id, dane) {
        const panel = element("div", "propozycje-fiszek");
        const stan = element("p", "wyciszony");
        if (!dane.propozycje.length) {
            panel.append(element("p", "wyciszony", `Brak propozycji z cytatem w tekście${dane.odrzucone ? ` (odrzucone: ${dane.odrzucone})` : ""}. Spróbuj jeszcze raz.`));
            return panel;
        }
        if (dane.odrzucone) panel.append(element("p", "wyciszony", `Odrzucone propozycje bez cytatu w tekście albo z obcymi liczbami: ${dane.odrzucone}.`));
        const wiersze = dane.propozycje.map((p) => {
            const w = element("div", "propozycja");
            const wybor = element("input");
            wybor.type = "checkbox";
            wybor.checked = true;
            wybor.setAttribute("aria-label", "Zapisz tę fiszkę");
            const pola = element("div", "propozycja__pola");
            const pytanie = element("textarea");
            pytanie.rows = 2;
            pytanie.value = p.pytanie;
            const odpowiedz = element("textarea");
            odpowiedz.rows = 2;
            odpowiedz.value = p.odpowiedz;
            pola.append(pytanie, odpowiedz, element("blockquote", "wyciszony", `„${p.fragment}”`));
            w.append(wybor, pola);
            panel.append(w);
            return { wybor, pytanie, odpowiedz, fragment: p.fragment };
        });
        const temat = element("input");
        temat.type = "text";
        temat.value = "przepisy";
        temat.maxLength = 60;
        const lTemat = element("label", "propozycje-fiszek__temat", "Temat ");
        lTemat.append(temat);
        const zapisz = element("button", "", "Zapisz zaznaczone");
        zapisz.type = "button";
        zapisz.addEventListener("click", async () => {
            const fiszki = wiersze.filter((w) => w.wybor.checked).map((w) => ({ pytanie: w.pytanie.value, odpowiedz: w.odpowiedz.value, fragment: w.fragment }));
            if (!fiszki.length) return (stan.textContent = "Zaznacz co najmniej jedną fiszkę.");
            zapisz.disabled = true;
            try {
                const wynik = await wyslij(`${URL_JEDNOSTKI}${id}/fiszki`, { fiszki, tematy: temat.value ? [temat.value] : [] });
                const gotowe = element("p", "komunikat komunikat--sukces");
                const link = element("a", "", "otwórz w Fiszkach ›");
                link.href = wynik.url;
                gotowe.append(`Dodane fiszki: ${wynik.dodane} (z kotwicą w PDF-ie aktu) — `, link);
                panel.replaceChildren(gotowe);
            } catch (e) {
                stan.textContent = e.message;
                zapisz.disabled = false;
            }
        });
        const rzad = element("div", "rzad");
        rzad.append(lTemat, zapisz);
        panel.append(rzad, stan);
        return panel;
    }

    document.querySelectorAll(".przycisk-fiszek").forEach((przycisk) => {
        przycisk.addEventListener("click", async () => {
            const sekcja = przycisk.closest(".jednostka");
            const stary = sekcja.querySelector(".propozycje-fiszek");
            if (stary) stary.remove();
            przycisk.disabled = true;
            przycisk.textContent = "✦ Gemini myśli…";
            try {
                sekcja.append(panelPropozycji(przycisk.dataset.jednostka, await wyslij(`${URL_JEDNOSTKI}${przycisk.dataset.jednostka}/szkice-fiszek`)));
            } catch (e) {
                const blad = element("p", "komunikat komunikat--blad propozycje-fiszek", e.message);
                sekcja.append(blad);
            } finally {
                przycisk.disabled = false;
                przycisk.textContent = "✦ Fiszki";
            }
        });
    });
})();
