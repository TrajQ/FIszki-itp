// Atlas: „Na tle kraju” — ten sam wskaźnik dla wszystkich województw (ETAP 52).
// Ranking liczy serwer (/atlas/wojewodztwa-porownanie); tu tylko rysujemy.
(function () {
    "use strict";

    const sekcja = document.getElementById("na-tle-kraju");
    const opis = document.getElementById("opis-kraju");
    const lista = document.getElementById("lista-wojewodztw");
    const format = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 });
    let numer = 0;

    function el(tag, klasa, tekst) {
        const e = document.createElement(tag);
        if (klasa) e.className = klasa;
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    document.addEventListener("atlas:dane", async (zdarzenie) => {
        const dane = zdarzenie.detail;
        const moj = ++numer;
        const parametry = new URLSearchParams({ zmienna: dane.zmienna.id, rok: dane.rok, woj: dane.wojewodztwo.bdl_id });
        if (dane.zmienna.mianownik) {
            parametry.set("mianownik", dane.zmienna.mianownik.id);
            parametry.set("mnoznik", dane.zmienna.mnoznik);
        }
        sekcja.hidden = false;
        opis.textContent = "Pobieram dane województw…";
        lista.replaceChildren();
        let wynik;
        try {
            const odpowiedz = await fetch(`${URL_WOJEWODZTWA_POROWNANIE}?${parametry}`);
            wynik = await odpowiedz.json();
            if (!odpowiedz.ok) throw new Error(wynik.blad || `Błąd ${odpowiedz.status}`);
        } catch (e) {
            if (moj === numer) opis.textContent = e.message;
            return;
        }
        if (moj !== numer) return;

        const jednostka = dane.zmienna.jednostka ? ` ${dane.zmienna.jednostka}` : "";
        const wybrane = wynik.wybrane;
        opis.textContent = wybrane
            ? `Województwo ${wybrane.nazwa}: ${wybrane.miejsce}. miejsce z ${wynik.wojewodztwa.length} (${format.format(wybrane.wartosc)}${jednostka}; mediana województw ${format.format(wynik.mediana)}${jednostka}). Wartości dla całych województw, nie średnie gmin.`
            : `Mediana województw: ${format.format(wynik.mediana)}${jednostka}.`;

        const najwieksza = Math.max(...wynik.wojewodztwa.map((w) => Math.abs(w.wartosc)), 1e-12);
        for (const w of wynik.wojewodztwa) {
            const li = el("li", w.wybrane ? "wiersz-wojewodztwa wiersz-wojewodztwa--wybrane" : "wiersz-wojewodztwa");
            const tor = el("span", "wiersz-wojewodztwa__tor");
            const slupek = el("span", "wiersz-wojewodztwa__slupek");
            slupek.style.width = `${(100 * Math.abs(w.wartosc)) / najwieksza}%`;
            tor.appendChild(slupek);
            li.append(
                el("span", "wiersz-wojewodztwa__miejsce", `${w.miejsce}.`),
                el("span", "wiersz-wojewodztwa__nazwa", w.nazwa),
                tor,
                el("span", "wiersz-wojewodztwa__wartosc", format.format(w.wartosc))
            );
            lista.appendChild(li);
        }
    });
})();
