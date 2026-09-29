// Wyszukiwarka fiszek na liście plików. Wynik prowadzi do PDF-a z
// podświetlonym fragmentem (/fiszki/<pdf>/?fiszka=<id>).
(function () {
    "use strict";

    const pole = document.getElementById("pole-szukaj-fiszek");
    const lista = document.getElementById("wyniki-szukania");
    let opoznienie = null;
    let numerZapytania = 0;

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    // Tekst z wyróżnioną frazą (<mark>), bez innerHTML — treść fiszek to dane użytkownika.
    function zWyroznieniem(klasa, tekst, fraza) {
        const el = element("div", klasa);
        const male = tekst.toLocaleLowerCase("pl");
        let start = 0;
        let indeks = male.indexOf(fraza);
        while (indeks !== -1 && fraza) {
            el.append(tekst.slice(start, indeks), element("mark", "", tekst.slice(indeks, indeks + fraza.length)));
            start = indeks + fraza.length;
            indeks = male.indexOf(fraza, start);
        }
        el.append(tekst.slice(start));
        return el;
    }

    async function szukaj(fraza) {
        const numer = ++numerZapytania;
        const odpowiedz = await fetch(`${URL_SZUKAJ}?q=${encodeURIComponent(fraza)}`);
        const wyniki = await odpowiedz.json();
        if (numer !== numerZapytania) return;

        lista.replaceChildren();
        if (!odpowiedz.ok) return;
        if (wyniki.length === 0) {
            lista.appendChild(element("li", "wyciszony", "Brak fiszek z tą frazą."));
            return;
        }
        const malaFraza = fraza.toLocaleLowerCase("pl");
        for (const f of wyniki) {
            const li = element("li");
            const link = element("a", "wynik-szukania");
            link.href = URL_PDF_WZOR.replace("/0/", `/${f.pdf_id}/`) + `?fiszka=${f.id}`;
            link.append(
                zWyroznieniem("fiszka-pytanie", f.pytanie, malaFraza),
                element("span", "wynik-szukania__zrodlo", `${f.nazwa_oryginalna}\ns. ${f.strona}`),
                zWyroznieniem("wynik-szukania__odpowiedz", f.odpowiedz, malaFraza)
            );
            li.appendChild(link);
            lista.appendChild(li);
        }
    }

    pole.addEventListener("input", () => {
        clearTimeout(opoznienie);
        const fraza = pole.value.trim();
        if (fraza.length < 2) {
            numerZapytania += 1;
            lista.replaceChildren();
            return;
        }
        opoznienie = setTimeout(() => szukaj(fraza).catch(() => {}), 250);
    });
})();
