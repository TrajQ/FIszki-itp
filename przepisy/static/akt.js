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
