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

    // Słowniczek (ETAP 120): filtr po pojęciu i treści definicji
    const filtrSlowniczka = document.getElementById("filtr-slowniczka");
    if (filtrSlowniczka) {
        filtrSlowniczka.addEventListener("input", () => {
            const szukany = filtrSlowniczka.value.trim().toLowerCase();
            document.querySelectorAll(".slowniczek__pozycja").forEach((p) => {
                p.hidden = Boolean(szukany) && !p.dataset.szukaj.includes(szukany);
            });
        });
    }

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

// ---------- druk zaznaczonych jednostek (ETAP 158) ----------
(function () {
    "use strict";

    const link = document.getElementById("druk-wybranych");
    const pola = [...document.querySelectorAll(".wybor-do-druku")];
    function odswiez() {
        const wybrane = pola.filter((p) => p.checked).map((p) => p.value);
        link.hidden = !wybrane.length;
        link.textContent = `Drukuj zaznaczone (${wybrane.length})`;
        link.href = `${URL_DRUKU}?${new URLSearchParams(wybrane.map((id) => ["j", id]))}`;
    }
    pola.forEach((p) => p.addEventListener("change", odswiez));
})();

// ---------- notatki przy jednostkach (ETAP 140) ----------
(function () {
    "use strict";

    function el(tag, klasa, tekst) {
        const e = document.createElement(tag);
        if (klasa) e.className = klasa;
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    function otworzEdytor(przycisk) {
        const sekcja = przycisk.closest(".jednostka");
        if (sekcja.querySelector(".edytor-notatki")) return;
        const notatka = sekcja.querySelector(".notatka");
        const edytor = el("div", "edytor-notatki");
        const pole = el("textarea");
        pole.rows = 4;
        pole.maxLength = MAKS_NOTATKI;
        pole.setAttribute("aria-label", `Notatka: ${sekcja.querySelector(".jednostka__pasek strong").textContent}`);
        pole.value = notatka.hidden ? "" : notatka.querySelector(".notatka__tekst").textContent;
        const zapisz = el("button", "", "Zapisz");
        const anuluj = el("button", "przycisk--drugi", "Anuluj");
        const blad = el("p", "komunikat komunikat--blad");
        blad.hidden = true;
        for (const b of [zapisz, anuluj]) b.type = "button";
        const rzad = el("div", "rzad");
        rzad.append(zapisz, anuluj);
        edytor.append(pole, rzad, blad);
        notatka.hidden = true;
        notatka.after(edytor);
        pole.focus();

        function zamknij() {
            edytor.remove();
            notatka.hidden = !notatka.querySelector(".notatka__tekst").textContent;
        }
        anuluj.addEventListener("click", zamknij);
        zapisz.addEventListener("click", async () => {
            zapisz.disabled = true;
            try {
                const odp = await fetch(`${URL_JEDNOSTKI}${przycisk.dataset.jednostka}/notatka`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ tekst: pole.value }),
                });
                const dane = await odp.json().catch(() => ({}));
                if (!odp.ok) throw new Error(dane.blad || `Błąd ${odp.status}`);
                const n = dane.notatka;
                notatka.querySelector(".notatka__tekst").textContent = n ? n.tekst : "";
                notatka.querySelector(".notatka__etykieta").textContent = n ? `Moja notatka · ${n.data_zmiany.slice(0, 10)}` : "Moja notatka";
                przycisk.textContent = n ? "✎ Notatka" : "✎ Dodaj notatkę";
                const wSpisie = document.querySelector(`#spis a[href="#${sekcja.id}"]`);
                const znak = wSpisie && wSpisie.querySelector(".spis-aktu__notatka");
                if (wSpisie && n && !znak) {
                    const nowy = el("span", "spis-aktu__notatka", "✎");
                    nowy.title = "Ma notatkę";
                    wSpisie.append(" ", nowy);
                } else if (znak && !n) {
                    znak.remove();
                }
                zamknij();
            } catch (e) {
                blad.textContent = e.message;
                blad.hidden = false;
                zapisz.disabled = false;
            }
        });
    }

    document.querySelectorAll(".przycisk-notatki").forEach((p) => p.addEventListener("click", () => otworzEdytor(p)));
})();

// ---------- czy jest nowszy tekst jednolity (ETAP 101) ----------
(function () {
    "use strict";

    const przycisk = document.getElementById("sprawdz-aktualnosc");
    const pole = document.getElementById("aktualnosc");
    if (!przycisk) return;

    function el(tag, klasa, tekst) {
        const e = document.createElement(tag);
        if (klasa) e.className = klasa;
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    async function pobierz(akt, guzik) {
        guzik.disabled = true;
        guzik.textContent = "Pobieram…";
        try {
            const odp = await fetch(URL_SEJM_POBIERZ, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ rok: akt.rok, pozycja: akt.pozycja, tytul: akt.tytul }),
            });
            const dane = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(dane.blad || `Błąd ${odp.status}`);
            location.href = dane.url;
        } catch (e) {
            guzik.disabled = false;
            guzik.textContent = "Pobierz";
            pole.appendChild(el("p", "komunikat komunikat--blad", e.message));
        }
    }

    przycisk.addEventListener("click", async () => {
        przycisk.disabled = true;
        pole.hidden = false;
        pole.replaceChildren(el("p", "wyciszony", "Sprawdzam w Dzienniku Ustaw…"));
        try {
            const odp = await fetch(URL_AKTUALNOSC);
            const w = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(w.blad || `Błąd ${odp.status}`);
            if (!w.nowsze.length) {
                pole.replaceChildren(el("p", "", `Nie znalazłem nowszego tekstu jednolitego ustawy „${w.przedmiot}” niż ${w.adres}.`),
                    el("p", "wyciszony", "Sprawdź też nowelizacje ogłoszone po ostatnim tekście jednolitym — tekst jednolity nie zawsze obejmuje najnowsze zmiany."));
                return;
            }
            pole.replaceChildren(el("p", "", `Jest nowszy tekst jednolity ustawy „${w.przedmiot}” (masz ${w.adres}):`));
            const lista = el("ul", "wyniki-sejmu");
            for (const a of w.nowsze) {
                const li = el("li", "wynik-sejmu");
                const opis = el("div", "wynik-sejmu__opis");
                opis.append(el("span", "", a.tytul), el("br"), el("span", "wyciszony", a.adres));
                li.appendChild(opis);
                if (a.ma_pdf) {
                    const guzik = el("button", "przycisk--drugi", "Pobierz");
                    guzik.type = "button";
                    guzik.addEventListener("click", () => pobierz(a, guzik));
                    li.appendChild(guzik);
                }
                lista.appendChild(li);
            }
            pole.appendChild(lista);
        } catch (e) {
            pole.replaceChildren(el("p", "komunikat komunikat--blad", e.message));
        } finally {
            przycisk.disabled = false;
        }
    });
})();

// ---------- Moje przepisy (ETAP 187) — zbiór artykułów z wielu aktów ----------
document.querySelectorAll(".przycisk-moje").forEach((przycisk) => {
    przycisk.addEventListener("click", async () => {
        przycisk.disabled = true;
        try {
            const odp = await fetch(`${URL_JEDNOSTKI}${przycisk.dataset.jednostka}/moje`, { method: "POST" });
            const dane = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(dane.blad || `Błąd ${odp.status}`);
            przycisk.textContent = dane.moje ? "★ Moje" : "☆ Moje";
            przycisk.setAttribute("aria-pressed", dane.moje ? "true" : "false");
        } catch (e) {
            alert(e.message);
        } finally {
            przycisk.disabled = false;
        }
    });
});
