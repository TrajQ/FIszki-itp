// Słownik symboli planu (ETAP 45): filtr tabeli i „rozszyfruj symbol”.
// Opisy liter daje serwer (mpzp/symbole.py) — jeden słownik dla całego modułu.
(function () {
    "use strict";

    const poleSymbolu = document.getElementById("pole-symbolu");
    const wynikSymbolu = document.getElementById("wynik-symbolu");
    const filtr = document.getElementById("filtr-symboli");
    const wiersze = document.querySelectorAll("#lista-symboli tr");
    const brak = document.getElementById("brak-symboli");
    let numer = 0;
    let opoznienie = null;

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    async function rozszyfruj(symbol) {
        const moj = ++numer;
        if (!symbol) {
            wynikSymbolu.replaceChildren();
            return;
        }
        try {
            const odpowiedz = await fetch(`${URL_ROZSZYFRUJ}?q=${encodeURIComponent(symbol)}`);
            const dane = await odpowiedz.json();
            if (moj !== numer) return;
            wynikSymbolu.replaceChildren();
            if (!dane.opis.length) {
                wynikSymbolu.appendChild(element("li", "wyciszony", "W symbolu nie ma liter do rozszyfrowania."));
            }
            for (const { symbol: litery, opis, zwyczajowe } of dane.opis) {
                const li = element("li");
                li.append(
                    element("span", "etykieta etykieta--sukces", litery),
                    element("span", opis ? "" : "wyciszony", opis || "brak w słowniku — sprawdź legendę planu")
                );
                if (zwyczajowe) li.appendChild(element("span", "etykieta", "zwyczajowe"));
                wynikSymbolu.appendChild(li);
            }
        } catch (e) {
            if (moj === numer) wynikSymbolu.replaceChildren(element("li", "wyciszony", "Błąd połączenia z serwerem."));
        }
    }

    poleSymbolu.addEventListener("input", () => {
        clearTimeout(opoznienie);
        opoznienie = setTimeout(() => rozszyfruj(poleSymbolu.value.trim()), 200);
    });

    filtr.addEventListener("input", () => {
        const fraza = filtr.value.trim().toLocaleLowerCase("pl-PL");
        let widoczne = 0;
        for (const wiersz of wiersze) {
            const pasuje = !fraza || wiersz.dataset.szukaj.includes(fraza);
            wiersz.hidden = !pasuje;
            if (pasuje) widoczne += 1;
        }
        brak.hidden = widoczne > 0;
    });
})();
