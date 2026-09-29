// Atlas: wybór gminy do raportu i zestaw wskaźników raportu (ETAP 63).
(function () {
    "use strict";

    const poleWoj = document.getElementById("pole-woj");
    const poleGmina = document.getElementById("pole-gmina");
    const otworz = document.getElementById("otworz-raport");
    const komunikat = document.getElementById("komunikat");
    const lista = document.getElementById("lista-wskaznikow");
    const pusty = document.getElementById("pusty-zestaw");
    const poleSzukaj = document.getElementById("pole-szukaj");
    const podpowiedzi = document.getElementById("podpowiedzi");
    const poleMianownik = document.getElementById("pole-mianownik");
    const poleMnoznik = document.getElementById("pole-mnoznik");
    let numerSzukania = 0;
    let opoznienie = null;

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function pokazBlad(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    async function zapytaj(url, opcje = {}) {
        const odpowiedz = await fetch(url, {
            ...opcje,
            headers: opcje.body ? { "Content-Type": "application/json" } : undefined,
        });
        const dane = await odpowiedz.json().catch(() => ({}));
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        return dane;
    }

    function zapamietaj(klucz, wartosc) {
        try {
            localStorage.setItem(klucz, wartosc);
        } catch (e) {
            // tylko wygoda
        }
    }

    function odczytaj(klucz) {
        try {
            return localStorage.getItem(klucz);
        } catch (e) {
            return null;
        }
    }

    // ---------- gmina ----------

    async function wczytajWojewodztwa() {
        const woj = await zapytaj(URL_WOJEWODZTWA);
        poleWoj.replaceChildren(new Option("— wybierz —", ""));
        for (const w of woj) poleWoj.appendChild(new Option(w.nazwa, w.bdl_id));
        const ostatnie = odczytaj("atlas.raport.woj");
        if (ostatnie && woj.some((w) => w.bdl_id === ostatnie)) {
            poleWoj.value = ostatnie;
            await wczytajGminy();
        }
    }

    async function wczytajGminy() {
        poleGmina.disabled = true;
        otworz.disabled = true;
        if (!poleWoj.value) return;
        zapamietaj("atlas.raport.woj", poleWoj.value);
        poleGmina.replaceChildren(new Option("Wczytywanie…", ""));
        const gminy = await zapytaj(URL_GMINY.replace("000000000000", poleWoj.value));
        const rodzaje = { 1: "gm. miejska", 2: "gm. wiejska", 3: "gm. miejsko-wiejska" };
        poleGmina.replaceChildren(new Option("— wybierz —", ""));
        for (const g of gminy) poleGmina.appendChild(new Option(`${g.nazwa} (${rodzaje[g.bdl_id.slice(-1)] || ""})`, g.bdl_id));
        poleGmina.disabled = false;
        const ostatnia = odczytaj("atlas.raport.gmina");
        if (ostatnia && gminy.some((g) => g.bdl_id === ostatnia)) poleGmina.value = ostatnia;
        otworz.disabled = !poleGmina.value;
    }

    poleWoj.addEventListener("change", () => wczytajGminy().catch((e) => pokazBlad(e.message)));
    poleGmina.addEventListener("change", () => (otworz.disabled = !poleGmina.value));
    document.getElementById("formularz-gminy").addEventListener("submit", (e) => {
        e.preventDefault();
        if (!poleGmina.value) return;
        zapamietaj("atlas.raport.gmina", poleGmina.value);
        location.href = URL_RAPORT.replace("000000000000", poleGmina.value);
    });

    // ---------- zestaw wskaźników ----------

    function pokazZestaw() {
        lista.replaceChildren();
        pusty.hidden = WSKAZNIKI.length > 0;
        const wybranyMianownik = poleMianownik.value;
        poleMianownik.replaceChildren(new Option("— bez przeliczenia —", ""));
        WSKAZNIKI.forEach((w, i) => {
            const li = element("li", "wskaznik-raportu");
            li.append(element("span", "wskaznik-raportu__nazwa", w.nazwa_pelna));
            const akcje = element("span", "wskaznik-raportu__akcje");
            const przyciski = [
                ["↑", "Wyżej", i === 0, () => zmien(`${URL_WSKAZNIKI}/${w.id}/przesun`, "POST", { o: -1 })],
                ["↓", "Niżej", i === WSKAZNIKI.length - 1, () => zmien(`${URL_WSKAZNIKI}/${w.id}/przesun`, "POST", { o: 1 })],
                ["✕", "Usuń z raportu", false, () => zmien(`${URL_WSKAZNIKI}/${w.id}`, "DELETE")],
            ];
            for (const [znak, tytul, wylaczony, akcja] of przyciski) {
                const b = element("button", "przycisk--tekst", znak);
                b.type = "button";
                b.title = tytul;
                b.setAttribute("aria-label", `${tytul}: ${w.nazwa_pelna}`);
                b.disabled = wylaczony;
                b.addEventListener("click", akcja);
                akcje.append(b);
            }
            li.append(akcje);
            lista.append(li);
            // mianownikiem może być tylko wskaźnik bez przeliczenia (np. ludność ogółem)
            if (!w.mianownik_id) poleMianownik.appendChild(new Option(w.nazwa, String(w.zmienna_id)));
        });
        if ([...poleMianownik.options].some((o) => o.value === wybranyMianownik)) poleMianownik.value = wybranyMianownik;
    }

    async function zmien(url, metoda, cialo) {
        try {
            const dane = await zapytaj(url, { method: metoda, body: cialo ? JSON.stringify(cialo) : undefined });
            WSKAZNIKI = dane.wskazniki;
            pokazZestaw();
            pokazBlad("");
        } catch (e) {
            pokazBlad(e.message);
        }
    }

    async function szukaj() {
        const fraza = poleSzukaj.value.trim();
        const moj = ++numerSzukania;
        if (fraza.length < 3) {
            podpowiedzi.hidden = true;
            return;
        }
        try {
            const wyniki = await zapytaj(`${URL_ZMIENNE}?q=${encodeURIComponent(fraza)}`);
            if (moj !== numerSzukania) return;
            podpowiedzi.replaceChildren();
            for (const z of wyniki) {
                const li = element("li");
                const b = element("button", "podpowiedz", z.nazwa);
                b.type = "button";
                if (z.jednostka) b.append(element("span", "wyciszony", ` [${z.jednostka}]`));
                b.addEventListener("click", () => {
                    podpowiedzi.hidden = true;
                    poleSzukaj.value = "";
                    const cialo = { zmienna: z.id };
                    if (poleMianownik.value) {
                        cialo.mianownik = Number(poleMianownik.value);
                        cialo.mnoznik = Number(poleMnoznik.value);
                    }
                    zmien(URL_WSKAZNIKI, "POST", cialo);
                });
                li.append(b);
                podpowiedzi.append(li);
            }
            if (!wyniki.length) podpowiedzi.append(element("li", "podpowiedzi__info", "Brak wskaźników o takiej nazwie na poziomie gmin."));
            podpowiedzi.hidden = false;
        } catch (e) {
            if (moj === numerSzukania) pokazBlad(e.message);
        }
    }

    poleSzukaj.addEventListener("input", () => {
        clearTimeout(opoznienie);
        opoznienie = setTimeout(szukaj, 300);
    });
    document.getElementById("formularz-wskaznika").addEventListener("submit", (e) => {
        e.preventDefault();
        szukaj();
    });
    for (const b of document.querySelectorAll(".szybki-wybor__fraza")) {
        b.addEventListener("click", () => {
            poleSzukaj.value = b.dataset.fraza;
            szukaj();
        });
    }

    pokazZestaw();
    wczytajWojewodztwa().catch((e) => pokazBlad(e.message));
})();
