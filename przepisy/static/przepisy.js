// Moduł przepisy: wyszukiwarka jednostek (artykułów, paragrafów).
// Szuka serwer (przepisy/baza.py, SQLite FTS5); tu tylko wysyłamy
// zapytanie i pokazujemy wyniki. Trafienia w podglądzie serwer otacza
// znakami \x02 … \x03 — zamieniamy je na <mark> bez innerHTML.
(function () {
    "use strict";

    const pole = document.getElementById("pole-szukania");
    const filtr = document.getElementById("filtr-aktu");
    const wyniki = document.getElementById("wyniki");
    const stan = document.getElementById("stan-szukania");
    let numer = 0;
    let opoznienie = null;

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function podglad(tekst) {
        const p = element("p", "wynik__podglad");
        // części na zmianę: zwykły tekst, trafienie, zwykły tekst, …
        tekst.split(/[\x02\x03]/).forEach((czesc, i) => {
            p.appendChild(i % 2 ? element("mark", "", czesc) : document.createTextNode(czesc));
        });
        return p;
    }

    function pokazStan(tekst) {
        stan.textContent = tekst;
        stan.hidden = !tekst;
    }

    async function szukaj() {
        const tekst = pole.value.trim();
        const moj = ++numer;
        if (!tekst) {
            wyniki.replaceChildren();
            pokazStan("");
            return;
        }
        const adres = new URL(URL_SZUKAJ, location.href);
        adres.searchParams.set("q", tekst);
        if (filtr.value) adres.searchParams.set("akt", filtr.value);
        try {
            const odpowiedz = await fetch(adres);
            const dane = await odpowiedz.json();
            if (moj !== numer) return; // przyszła odpowiedź na starsze zapytanie
            wyniki.replaceChildren();
            pokazStan(dane.wyniki.length ? "" : "Nic nie znaleziono. Spróbuj krótszego słowa albo innego sformułowania.");
            for (const w of dane.wyniki) {
                const li = element("li", "wynik");
                const naglowek = element("div", "wynik__naglowek");
                const link = element("a", "", w.oznaczenie);
                link.href = `${URL_AKT}${w.akt_id}#j${w.id}`;
                naglowek.append(link, element("span", "wyciszony", ` · ${w.nazwa_aktu} · s. ${w.strona_od}`));
                li.append(naglowek, podglad(w.podglad));
                wyniki.appendChild(li);
            }
        } catch (e) {
            if (moj === numer) pokazStan("Nie udało się wyszukać. Odśwież stronę.");
        }
    }

    function zaplanuj() {
        clearTimeout(opoznienie);
        opoznienie = setTimeout(szukaj, 250);
    }

    pole.addEventListener("input", zaplanuj);
    filtr.addEventListener("change", szukaj);
    document.getElementById("formularz-szukania").addEventListener("submit", (e) => {
        e.preventDefault();
        szukaj();
    });
})();
