// Przepisy: akty z Dziennika Ustaw przez API Sejmu (ETAP 88).
(function () {
    "use strict";

    const formularz = document.getElementById("formularz-sejmu");
    const pole = document.getElementById("pole-sejmu");
    const stan = document.getElementById("stan-sejmu");
    const lista = document.getElementById("wyniki-sejmu");
    let numer = 0;

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function pokazStan(tekst) {
        stan.textContent = tekst;
        stan.hidden = !tekst;
    }

    async function pobierz(akt, przycisk) {
        przycisk.disabled = true;
        przycisk.textContent = "Pobieram…";
        try {
            const odpowiedz = await fetch(URL_SEJM_POBIERZ, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ rok: akt.rok, pozycja: akt.pozycja, tytul: akt.tytul }),
            });
            const dane = await odpowiedz.json().catch(() => ({}));
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            location.href = dane.url;
        } catch (e) {
            pokazStan(e.message);
            przycisk.disabled = false;
            przycisk.textContent = "Pobierz";
        }
    }

    formularz.addEventListener("submit", async (zdarzenie) => {
        zdarzenie.preventDefault();
        const moj = ++numer;
        lista.replaceChildren();
        pokazStan("Szukam w Dzienniku Ustaw…");
        try {
            const odpowiedz = await fetch(`${URL_SEJM_SZUKAJ}?${new URLSearchParams({ q: pole.value })}`);
            const akty = await odpowiedz.json().catch(() => ({}));
            if (moj !== numer) return;
            if (!odpowiedz.ok) throw new Error(akty.blad || `Błąd ${odpowiedz.status}`);
            pokazStan(akty.length ? "" : "Nic nie znaleziono — spróbuj innych słów z tytułu.");
            for (const akt of akty) {
                const li = element("li", "wynik-sejmu");
                const opis = element("div", "wynik-sejmu__opis");
                const tytul = element("span", "", akt.tytul);
                const meta = element("span", "wyciszony", `${akt.adres}${akt.status ? " · " + akt.status : ""}`);
                if (akt.tekst_jednolity) opis.append(element("span", "etykieta etykieta--akcent", "tekst jednolity"), " ");
                opis.append(tytul, element("br"), meta);
                li.append(opis);
                if (akt.ma_pdf) {
                    const przycisk = element("button", "przycisk--drugi", "Pobierz");
                    przycisk.type = "button";
                    przycisk.addEventListener("click", () => pobierz(akt, przycisk));
                    li.append(przycisk);
                } else {
                    li.append(element("span", "wyciszony", "bez PDF"));
                }
                lista.appendChild(li);
            }
        } catch (e) {
            if (moj === numer) pokazStan(e.message);
        }
    });
})();
