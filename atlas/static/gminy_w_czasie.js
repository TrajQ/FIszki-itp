// Gminy w czasie (ETAP 171): dodawanie i usuwanie gmin na wykresie.
// Wybór trafia do ukrytego pola `gminy` (identyfikatory BDL) i strona
// przeładowuje się — wykres i tabelę liczy serwer.
(function () {
    "use strict";

    const formularz = document.getElementById("formularz-gmin");
    if (!formularz) return;
    const pole = document.getElementById("pole-gminy");
    const wpis = document.getElementById("dodaj-gmine");

    function wybrane() {
        return pole.value ? pole.value.split(",") : [];
    }

    function zapisz(lista) {
        pole.value = lista.join(",");
        formularz.submit();
    }

    function dodaj() {
        const tekst = wpis.value.trim();
        const teryt = (tekst.match(/\((\d{7})\)$/) || [])[1];
        let i = teryt ? TERYTY.indexOf(teryt) : -1;
        if (i < 0) {
            // sama nazwa — tylko gdy jednoznaczna (np. gmina miejska i wiejska o tej samej nazwie mają różne TERYT)
            const pasujace = OPISY.map((o, j) => [o, j]).filter(([o]) => o.toLowerCase() === tekst.toLowerCase());
            if (pasujace.length === 1) i = pasujace[0][1];
        }
        if (i < 0) {
            wpis.setCustomValidity("Wybierz gminę z listy podpowiedzi.");
            wpis.reportValidity();
            return;
        }
        const lista = wybrane();
        if (lista.includes(GMINY[i])) return;
        if (lista.length >= MAKS) {
            wpis.setCustomValidity(`Najwyżej ${MAKS} gmin na wykresie.`);
            wpis.reportValidity();
            return;
        }
        zapisz([...lista, GMINY[i]]);
    }

    wpis.addEventListener("input", () => wpis.setCustomValidity(""));
    wpis.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            dodaj();
        }
    });
    document.getElementById("przycisk-dodaj").addEventListener("click", dodaj);
    formularz.addEventListener("click", (e) => {
        const przycisk = e.target.closest("[data-usun]");
        if (przycisk) zapisz(wybrane().filter((id) => id !== przycisk.dataset.usun));
    });
})();
