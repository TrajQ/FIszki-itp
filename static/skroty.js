// Skróty klawiszowe wspólne dla wszystkich stron (ETAP 167):
//   ?  — okno z listą skrótów (wspólne + tej strony, blok `skroty` w szablonie)
//   /  — wyszukiwarka (pole szukania na stronie, a gdy go nie ma — strona Szukaj)
//   m  — mapa dostaje fokus: strzałki przesuwają, + i − przybliżają (Leaflet)
// Skróty nie działają w polach tekstowych i z Ctrl / Alt / Cmd — to skróty przeglądarki.
(function () {
    "use strict";

    // link do zwiniętej sekcji (np. Pomoc#skroty z okna skrótów) — rozwiń ją
    function rozwinCel() {
        const cel = location.hash && document.getElementById(location.hash.slice(1));
        if (cel && cel.tagName === "DETAILS") cel.open = true;
    }
    rozwinCel();
    window.addEventListener("hashchange", rozwinCel);

    const okno = document.getElementById("okno-skrotow");
    if (!okno) return;

    function wPolu(cel) {
        return cel.closest("input, textarea, select, [contenteditable=''], [contenteditable='true']") !== null;
    }

    document.addEventListener("keydown", (e) => {
        if (e.ctrlKey || e.metaKey || e.altKey || okno.open || wPolu(e.target)) return;
        if (e.key === "?") {
            e.preventDefault();
            okno.showModal();
        } else if (e.key === "/") {
            e.preventDefault();
            const pole = document.querySelector("[data-skrot-szukaj]");
            if (pole) pole.focus();
            else location.href = okno.dataset.urlSzukaj;
        } else if (e.key === "m") {
            // pierwsza widoczna (Atlas pokazuje mapę dopiero po wyborze wskaźnika)
            const mapa = [...document.querySelectorAll(".leaflet-container")].find((m) => m.getClientRects().length);
            if (!mapa) return;
            e.preventDefault();
            mapa.scrollIntoView({ behavior: "smooth", block: "nearest" });
            mapa.focus({ preventScroll: true });
        }
    });

    document.getElementById("zamknij-skroty").addEventListener("click", () => okno.close());
    // klik w tło (poza ramką okna) zamyka okno
    okno.addEventListener("click", (e) => {
        if (e.target === okno) okno.close();
    });
})();
