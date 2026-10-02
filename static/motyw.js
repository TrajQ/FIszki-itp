// Przełącznik motywu (ETAP 151): jak system → jasny → ciemny.
// Wybór pamięta przeglądarka (localStorage) — to ustawienie wyglądu, nie dane.
// Atrybut data-motyw na <html> ustawia już skrypt w <head> base.html (bez
// mignięcia jasnej strony); tu tylko przycisk.
(function () {
    "use strict";

    const KLUCZ = "warsztat-motyw";
    const KOLEJNOSC = ["system", "jasny", "ciemny"];
    const NAZWY = { system: "jak w systemie", jasny: "jasny", ciemny: "ciemny" };
    const IKONY = { system: "◐", jasny: "☀", ciemny: "☾" };

    function odczytaj() {
        try {
            const zapisany = localStorage.getItem(KLUCZ);
            return KOLEJNOSC.includes(zapisany) ? zapisany : "system";
        } catch (e) {
            return "system"; // przeglądarka bez dostępu do localStorage
        }
    }

    function ustaw(motyw) {
        if (motyw === "system") document.documentElement.removeAttribute("data-motyw");
        else document.documentElement.setAttribute("data-motyw", motyw);
        try {
            if (motyw === "system") localStorage.removeItem(KLUCZ);
            else localStorage.setItem(KLUCZ, motyw);
        } catch (e) {
            /* wybór zadziała do przeładowania strony */
        }
        pokaz(motyw);
    }

    const przycisk = document.getElementById("przelacznik-motywu");
    if (!przycisk) return;

    function pokaz(motyw) {
        const nastepny = KOLEJNOSC[(KOLEJNOSC.indexOf(motyw) + 1) % KOLEJNOSC.length];
        przycisk.textContent = IKONY[motyw];
        przycisk.title = `Motyw: ${NAZWY[motyw]} — kliknij: ${NAZWY[nastepny]}`;
        przycisk.setAttribute("aria-label", `Motyw: ${NAZWY[motyw]}. Zmień motyw`);
    }

    pokaz(odczytaj());
    przycisk.addEventListener("click", () => {
        ustaw(KOLEJNOSC[(KOLEJNOSC.indexOf(odczytaj()) + 1) % KOLEJNOSC.length]);
    });
})();
