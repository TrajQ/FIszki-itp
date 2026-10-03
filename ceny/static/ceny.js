// Moduł ceny (ETAP 103): wybór wskaźnika GUS, miast, wykres, tabela zmian i ranking.
// Liczby (zmiany, ranking) liczy serwer — ceny/analiza.py; tu tylko rysujemy.
(function () {
    "use strict";

    const KOLORY = ["#0071e3", "#ff9f0a", "#34c759", "#ff375f", "#5e5ce6", "#8e6e4e"];
    const liczba = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 });
    const procent = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1, signDisplay: "exceptZero" });
    const komunikat = document.getElementById("komunikat");
    const poleWoj = document.getElementById("pole-woj");
    const listaPowiatow = document.getElementById("lista-powiatow");
    const wybraneEl = document.getElementById("wybrane");
    const poleRok = document.getElementById("pole-rok");
    let wybrane = odczytaj("ceny.wybrane", []); // [{id, nazwa, woj}]
    let dane = new Map(); // id → {szereg, podsumowanie}
    const indeksy = new Map(); // ETAP 181: `${id}:${rok bazowy}` → [{rok, wartosc}] albo null (brak danych w roku bazowym)
    const trybWykresu = document.getElementById("tryb-wykresu");
    const rokBazowy = document.getElementById("rok-bazowy");
    let numer = 0;

    function el(tag, klasa, tekst) {
        const e = document.createElement(tag);
        if (klasa) e.className = klasa;
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    function pokazBlad(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    function odczytaj(klucz, domyslne) {
        try {
            return JSON.parse(localStorage.getItem(klucz)) ?? domyslne;
        } catch (e) {
            return domyslne;
        }
    }

    function zapamietaj(klucz, wartosc) {
        try {
            localStorage.setItem(klucz, JSON.stringify(wartosc));
        } catch (e) {
            // tylko wygoda
        }
    }

    async function zapytaj(sciezka, opcje = {}) {
        const odp = await fetch(URL_CENY + sciezka, { ...opcje, headers: opcje.body ? { "Content-Type": "application/json" } : undefined });
        const wynik = await odp.json().catch(() => ({}));
        if (!odp.ok) throw new Error(wynik.blad || `Błąd ${odp.status}`);
        return wynik;
    }

    // ---------- 1. wskaźnik ----------

    // rodzaj: „zmienna” (cena) albo „wynagrodzenie” (ETAP 116) — ta sama wyszukiwarka GUS
    async function szukajZmiennych(fraza, rodzaj = "zmienna") {
        const lista = document.getElementById(rodzaj === "wynagrodzenie" ? "wyniki-wynagrodzen" : "wyniki-zmiennych");
        lista.replaceChildren(el("li", "wyciszony", "Szukam w GUS…"));
        try {
            const zmienne = await zapytaj(`zmienne?${new URLSearchParams({ q: fraza })}`);
            lista.replaceChildren();
            if (!zmienne.length) lista.appendChild(el("li", "wyciszony", "Nic nie znaleziono — spróbuj innych słów."));
            for (const z of zmienne) {
                const przycisk = el("button", "wynik-zmiennej", `${z.nazwa}${z.jednostka ? ` [${z.jednostka}]` : ""}`);
                przycisk.type = "button";
                przycisk.addEventListener("click", () => wybierzZmienna(z.id, rodzaj));
                const li = el("li");
                li.appendChild(przycisk);
                lista.appendChild(li);
            }
        } catch (e) {
            lista.replaceChildren(el("li", "komunikat komunikat--blad", e.message));
        }
    }

    async function wybierzZmienna(id, rodzaj = "zmienna") {
        try {
            await zapytaj("zmienna", { method: "PUT", body: JSON.stringify({ id, rodzaj }) });
            location.reload(); // nowy wskaźnik — wszystkie szeregi od nowa
        } catch (e) {
            pokazBlad(e.message);
        }
    }

    document.getElementById("formularz-zmiennej").addEventListener("submit", (e) => {
        e.preventDefault();
        szukajZmiennych(document.getElementById("pole-zmiennej").value);
    });
    for (const b of document.querySelectorAll(".szybki-wybor__fraza[data-fraza]")) {
        b.addEventListener("click", () => {
            document.getElementById("pole-zmiennej").value = b.dataset.fraza;
            szukajZmiennych(b.dataset.fraza);
        });
    }
    document.getElementById("formularz-wynagrodzenia").addEventListener("submit", (e) => {
        e.preventDefault();
        szukajZmiennych(document.getElementById("pole-wynagrodzenia").value, "wynagrodzenie");
    });
    for (const b of document.querySelectorAll("[data-fraza-wynagrodzenia]")) {
        b.addEventListener("click", () => {
            document.getElementById("pole-wynagrodzenia").value = b.dataset.frazaWynagrodzenia;
            szukajZmiennych(b.dataset.frazaWynagrodzenia, "wynagrodzenie");
        });
    }

    // ---------- 2. miasta ----------

    async function wczytajWojewodztwa() {
        try {
            const woj = await zapytaj("wojewodztwa");
            poleWoj.replaceChildren(new Option("— wybierz —", ""));
            for (const w of woj) poleWoj.appendChild(new Option(w.nazwa, w.bdl_id));
            const ostatnie = odczytaj("ceny.woj", "");
            if (ostatnie && woj.some((w) => w.bdl_id === ostatnie)) {
                poleWoj.value = ostatnie;
                await wczytajPowiaty();
            }
        } catch (e) {
            pokazBlad(e.message);
        }
    }

    async function wczytajPowiaty() {
        listaPowiatow.replaceChildren();
        if (!poleWoj.value) return;
        zapamietaj("ceny.woj", poleWoj.value);
        try {
            const powiaty = await zapytaj(`powiaty/${poleWoj.value}`);
            for (const p of powiaty) {
                const li = el("li", p.miasto ? "powiat powiat--miasto" : "powiat");
                const pole = el("input");
                pole.type = "checkbox";
                pole.checked = wybrane.some((w) => w.id === p.bdl_id);
                pole.addEventListener("change", () => przelacz(p, pole));
                const etykieta = el("label");
                etykieta.append(pole, " " + p.nazwa);
                li.appendChild(etykieta);
                listaPowiatow.appendChild(li);
            }
        } catch (e) {
            pokazBlad(e.message);
        }
        wczytajRanking();
    }

    function przelacz(powiat, pole) {
        if (pole.checked) {
            if (wybrane.length >= MAKS_MIAST) {
                pole.checked = false;
                return pokazBlad(`Najwyżej ${MAKS_MIAST} jednostek naraz — odznacz którąś.`);
            }
            wybrane.push({ id: powiat.bdl_id, nazwa: powiat.nazwa, woj: poleWoj.value });
        } else {
            wybrane = wybrane.filter((w) => w.id !== powiat.bdl_id);
        }
        pokazBlad("");
        zapamietaj("ceny.wybrane", wybrane);
        odswiez();
    }

    function pokazWybrane() {
        wybraneEl.replaceChildren();
        wybrane.forEach((w, i) => {
            const znacznik = el("span", "wybrany");
            znacznik.style.borderColor = KOLORY[i % KOLORY.length];
            const usun = el("button", "przycisk--tekst", "✕");
            usun.type = "button";
            usun.title = "Usuń z porównania";
            usun.addEventListener("click", () => {
                wybrane = wybrane.filter((x) => x.id !== w.id);
                zapamietaj("ceny.wybrane", wybrane);
                const pole = [...listaPowiatow.querySelectorAll("input")].find((x) => x.parentElement.textContent.trim() === w.nazwa);
                if (pole) pole.checked = false;
                odswiez();
            });
            znacznik.append(w.nazwa, usun);
            wybraneEl.appendChild(znacznik);
        });
    }

    // ---------- 3. wykres i tabela ----------

    const NS = "http://www.w3.org/2000/svg";

    function svg(tag, atrybuty, tekst) {
        const e = document.createElementNS(NS, tag);
        for (const [k, v] of Object.entries(atrybuty)) e.setAttribute(k, v);
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    // ETAP 181: lata bazowe — wspólne dla wszystkich wybranych miast (indeks każdego od tego samego roku)
    function ustawLataBazowe() {
        const szeregi = wybrane.map((w) => (dane.get(w.id) || {}).szereg || []).filter((s) => s.length);
        const wspolne = szeregi.length ? szeregi.map((s) => new Set(s.map((p) => p.rok))).reduce((a, b) => new Set([...a].filter((r) => b.has(r)))) : new Set();
        const lata = [...wspolne].sort((a, b) => a - b);
        const poprzedni = Number(rokBazowy.value);
        rokBazowy.replaceChildren(...lata.map((r) => new Option(String(r), String(r))));
        if (lata.length) rokBazowy.value = String(lata.includes(poprzedni) ? poprzedni : lata[0]);
    }

    async function wczytajIndeksy() {
        const rok = rokBazowy.value;
        await Promise.all(wybrane.filter((w) => !indeksy.has(`${w.id}:${rok}`)).map(async (w) => {
            try {
                indeksy.set(`${w.id}:${rok}`, (await zapytaj(`szereg/${w.id}?bazowy=${rok}`)).indeks);
            } catch (e) {
                indeksy.set(`${w.id}:${rok}`, null);
            }
        }));
    }

    async function zmienTrybWykresu() {
        const indeks = trybWykresu.value === "indeks";
        document.getElementById("etykieta-bazowego").hidden = !indeks;
        if (indeks) {
            if (!rokBazowy.options.length) ustawLataBazowe();
            await wczytajIndeksy();
        }
        rysujWykres();
    }
    trybWykresu.addEventListener("change", zmienTrybWykresu);
    rokBazowy.addEventListener("change", zmienTrybWykresu);

    function rysujWykres() {
        const pojemnik = document.getElementById("wykres");
        const indeks = trybWykresu.value === "indeks" && rokBazowy.value;
        const szeregSerii = (w) => (indeks ? indeksy.get(`${w.id}:${rokBazowy.value}`) : (dane.get(w.id) || {}).szereg) || [];
        const serie = wybrane.map((w, i) => ({ ...w, kolor: KOLORY[i % KOLORY.length], szereg: szeregSerii(w) })).filter((s) => s.szereg.length);
        pojemnik.replaceChildren();
        const opisIndeksu = document.getElementById("opis-indeksu");
        opisIndeksu.hidden = !indeks;
        opisIndeksu.textContent = indeks ? `Indeks: cena w roku ÷ cena w ${rokBazowy.value} r. × 100 (liczy serwer). 120 = o 20% drożej niż w roku bazowym — porównuje tempo zmian miast o różnych cenach.` : "";
        if (!serie.length) return;
        const punkty = serie.flatMap((s) => s.szereg);
        const [r0, r1] = [Math.min(...punkty.map((p) => p.rok)), Math.max(...punkty.map((p) => p.rok))];
        // „ładne” podziałki osi: krok 1, 2, 2,5 albo 5 × 10^k; przy indeksie oś od najmniejszej wartości
        const maks = Math.max(...punkty.map((p) => p.wartosc));
        const min = indeks ? Math.min(...punkty.map((p) => p.wartosc)) : 0;
        const potega = 10 ** Math.floor(Math.log10((maks - min) / 4 || 1));
        const krokY = [1, 2, 2.5, 5, 10].map((k) => k * potega).find((k) => (maks - min) / k <= 5) || potega * 10;
        const [w0, w1] = [Math.floor(min / krokY) * krokY, Math.ceil(maks / krokY) * krokY];
        const SZ = 760, WY = 300, M = { l: 70, p: 16, g: 12, d: 30 };
        const x = (r) => M.l + (r1 === r0 ? 0.5 : (r - r0) / (r1 - r0)) * (SZ - M.l - M.p);
        const y = (w) => WY - M.d - ((w - w0) / (w1 - w0 || 1)) * (WY - M.g - M.d);
        const wykres = svg("svg", { viewBox: `0 0 ${SZ} ${WY}`, role: "img", "aria-label": "Ceny w czasie" });
        for (let w = w0; w <= w1 + krokY / 2; w += krokY) {
            wykres.append(svg("line", { x1: M.l, x2: SZ - M.p, y1: y(w), y2: y(w), class: "wykres-cen__siatka" }),
                svg("text", { x: M.l - 8, y: y(w) + 4, "text-anchor": "end", class: "wykres-cen__opis" }, liczba.format(w)));
        }
        if (indeks) wykres.appendChild(svg("line", { x1: M.l, x2: SZ - M.p, y1: y(100), y2: y(100), stroke: "currentColor", "stroke-dasharray": "6 4", opacity: 0.6 }));
        const krok = Math.max(1, Math.ceil((r1 - r0) / 10));
        for (let r = r0; r <= r1; r += krok) wykres.appendChild(svg("text", { x: x(r), y: WY - 8, "text-anchor": "middle", class: "wykres-cen__opis" }, r));
        for (const s of serie) {
            wykres.appendChild(svg("polyline", { points: s.szereg.map((p) => `${x(p.rok).toFixed(1)},${y(p.wartosc).toFixed(1)}`).join(" "), fill: "none", stroke: s.kolor, "stroke-width": 2.5 }));
            for (const p of s.szereg) {
                const kropka = svg("circle", { cx: x(p.rok), cy: y(p.wartosc), r: 3, fill: s.kolor });
                kropka.appendChild(svg("title", {}, indeks ? `${s.nazwa}, ${p.rok}: indeks ${liczba.format(p.wartosc)}` : `${s.nazwa}, ${p.rok}: ${liczba.format(p.wartosc)} ${ZMIENNA.jednostka || ""}`));
                wykres.appendChild(kropka);
            }
        }
        pojemnik.appendChild(wykres);
    }

    function zmiana(z) {
        if (!z) return "—";
        return z.zmiana_proc === null ? liczba.format(z.zmiana) : `${procent.format(z.zmiana_proc)}%`;
    }

    function rysujTabele() {
        const tabela = document.getElementById("tabela-cen");
        const jednostka = ZMIENNA.jednostka ? ` [${ZMIENNA.jednostka}]` : "";
        const glowa = el("tr");
        for (const [t, k] of [["Miasto / powiat", ""], ["Rok", "liczba"], [`Cena${jednostka}`, "liczba"], ["Rok do roku", "liczba"], ["W 5 lat", "liczba"], ["Od początku", "liczba"], ["Średnio rocznie", "liczba"]]) glowa.appendChild(el("th", k, t));
        tabela.replaceChildren(glowa);
        wybrane.forEach((w, i) => {
            const d = dane.get(w.id);
            const tr = el("tr");
            const nazwa = el("td");
            const probka = el("span", "probka-cen");
            probka.style.background = KOLORY[i % KOLORY.length];
            nazwa.append(probka, w.nazwa);
            tr.appendChild(nazwa);
            const s = d && d.podsumowanie;
            if (!d) {
                tr.appendChild(el("td", "wyciszony", "wczytywanie…"));
            } else if (d.blad || !s) {
                const td = el("td", "wyciszony", d.blad || "brak danych GUS");
                td.colSpan = 6;
                tr.appendChild(td);
            } else {
                const od = s.od_poczatku ? `${zmiana(s.od_poczatku)} od ${s.od_poczatku.od}` : "—";
                tr.append(el("td", "liczba", s.rok), el("td", "liczba", liczba.format(s.wartosc)), el("td", "liczba", zmiana(s.rok_do_roku)),
                    el("td", "liczba", zmiana(s.w_5_lat)), el("td", "liczba", od),
                    el("td", "liczba", s.srednio_rocznie_proc === null ? "—" : `${procent.format(s.srednio_rocznie_proc)}%`));
            }
            tabela.appendChild(tr);
        });
        const link = document.getElementById("link-csv");
        const parametry = new URLSearchParams();
        for (const w of wybrane) {
            parametry.append("id", w.id);
            parametry.append("nazwa", w.nazwa);
        }
        link.href = `${URL_CENY}porownanie.csv?${parametry}`;
        document.getElementById("link-ods").href = `${URL_CENY}porownanie.ods?${parametry}`; // ETAP 189
        document.getElementById("link-raport-miast").href = `${URL_CENY}raport?${parametry}`; // ETAP 137
    }

    async function odswiez() {
        pokazWybrane();
        document.getElementById("sekcja-wyniku").hidden = !wybrane.length;
        const moj = ++numer;
        await Promise.all(wybrane.filter((w) => !dane.has(w.id)).map(async (w) => {
            try {
                dane.set(w.id, await zapytaj(`szereg/${w.id}`));
            } catch (e) {
                dane.set(w.id, { blad: e.message });
            }
        }));
        if (moj !== numer) return;
        ustawLataBazowe();
        if (trybWykresu.value === "indeks") await wczytajIndeksy();
        rysujWykres();
        rysujTabele();
        if (!ustawLata()) wczytajRanking(); // podświetlenie wybranych miast
        wczytajDostepnosc();
    }

    // ---------- 5. dostępność cenowa (ETAP 116) — liczy serwer (ceny/analiza.py: dostepnosc) ----------

    const dostepnosc = new Map(); // id → {lata, podsumowanie} albo {blad}
    const metry = new Intl.NumberFormat("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); // m² za wynagrodzenie: zwykle 0,5–1,5
    const ulamek = new Intl.NumberFormat("pl-PL", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

    async function wczytajDostepnosc() {
        const sekcja = document.getElementById("sekcja-dostepnosci");
        sekcja.hidden = !wybrane.length;
        if (!wybrane.length || !WYNAGRODZENIE) return;
        await Promise.all(wybrane.filter((w) => !dostepnosc.has(w.id)).map(async (w) => {
            try {
                dostepnosc.set(w.id, await zapytaj(`dostepnosc/${w.id}`));
            } catch (e) {
                dostepnosc.set(w.id, { blad: e.message });
            }
        }));
        rysujDostepnosc();
    }

    function rysujDostepnosc() {
        const serie = wybrane.map((w, i) => ({ ...w, kolor: KOLORY[i % KOLORY.length], d: dostepnosc.get(w.id) || {} }));
        const tabela = document.getElementById("tabela-dostepnosci");
        const glowa = el("tr");
        for (const [t, k] of [["Miasto / powiat", ""], ["Rok", "liczba"], ["m² za wynagrodzenie", "liczba"], ["Wynagrodzeń na 50 m²", "liczba"], ["Zmiana m² za wynagrodzenie", "liczba"]]) glowa.appendChild(el("th", k, t));
        tabela.replaceChildren(glowa);
        for (const s of serie) {
            const tr = el("tr");
            const nazwa = el("td");
            const probka = el("span", "probka-cen");
            probka.style.background = s.kolor;
            nazwa.append(probka, s.nazwa);
            tr.appendChild(nazwa);
            const p = s.d.podsumowanie;
            if (!p) {
                const td = el("td", "wyciszony", s.d.blad || "brak lat, w których GUS ma oba wskaźniki");
                td.colSpan = 4;
                tr.appendChild(td);
            } else {
                tr.append(el("td", "liczba", p.rok), el("td", "liczba", `${metry.format(p.m2_za_wynagrodzenie)} m²`),
                    el("td", "liczba", ulamek.format(p.wynagrodzen_na_mieszkanie)),
                    el("td", "liczba", p.zmiana_m2_proc === null ? "—" : `${procent.format(p.zmiana_m2_proc)}% od ${p.od}`));
            }
            tabela.appendChild(tr);
        }
        // wykres: m² za wynagrodzenie w latach (oś od zera)
        const pojemnik = document.getElementById("wykres-dostepnosci");
        pojemnik.replaceChildren();
        const zDanymi = serie.filter((s) => (s.d.lata || []).length);
        if (!zDanymi.length) return;
        const punkty = zDanymi.flatMap((s) => s.d.lata);
        const [r0, r1] = [Math.min(...punkty.map((p) => p.rok)), Math.max(...punkty.map((p) => p.rok))];
        const maks = Math.max(...punkty.map((p) => p.m2_za_wynagrodzenie));
        const potega = 10 ** Math.floor(Math.log10(maks / 4 || 1));
        const krokY = [1, 2, 2.5, 5, 10].map((k) => k * potega).find((k) => maks / k <= 5);
        const w1 = Math.ceil(maks / krokY) * krokY;
        const SZ = 760, WY = 260, M = { l: 50, p: 16, g: 12, d: 30 };
        const x = (r) => M.l + (r1 === r0 ? 0.5 : (r - r0) / (r1 - r0)) * (SZ - M.l - M.p);
        const y = (w) => WY - M.d - (w / (w1 || 1)) * (WY - M.g - M.d);
        const wykres = svg("svg", { viewBox: `0 0 ${SZ} ${WY}`, role: "img", "aria-label": "Metry kwadratowe za przeciętne wynagrodzenie w czasie" });
        for (let w = 0; w <= w1 + krokY / 2; w += krokY) {
            wykres.append(svg("line", { x1: M.l, x2: SZ - M.p, y1: y(w), y2: y(w), class: "wykres-cen__siatka" }),
                svg("text", { x: M.l - 8, y: y(w) + 4, "text-anchor": "end", class: "wykres-cen__opis" }, metry.format(w)));
        }
        const krok = Math.max(1, Math.ceil((r1 - r0) / 10));
        for (let r = r0; r <= r1; r += krok) wykres.appendChild(svg("text", { x: x(r), y: WY - 8, "text-anchor": "middle", class: "wykres-cen__opis" }, r));
        for (const s of zDanymi) {
            wykres.appendChild(svg("polyline", { points: s.d.lata.map((p) => `${x(p.rok).toFixed(1)},${y(p.m2_za_wynagrodzenie).toFixed(1)}`).join(" "), fill: "none", stroke: s.kolor, "stroke-width": 2.5 }));
            for (const p of s.d.lata) {
                const kropka = svg("circle", { cx: x(p.rok), cy: y(p.m2_za_wynagrodzenie), r: 3, fill: s.kolor });
                kropka.appendChild(svg("title", {}, `${s.nazwa}, ${p.rok}: ${metry.format(p.m2_za_wynagrodzenie)} m² (wynagrodzenie ${liczba.format(p.wynagrodzenie)} zł, cena ${liczba.format(p.cena_m2)} zł/m²)`));
                wykres.appendChild(kropka);
            }
        }
        pojemnik.appendChild(wykres);
    }

    // ---------- 4. ranking ----------

    function ustawLata() {
        const lata = [...new Set(wybrane.flatMap((w) => ((dane.get(w.id) || {}).szereg || []).map((p) => p.rok)))].sort((a, b) => b - a);
        const poprzedni = poleRok.value;
        if (!lata.length) return false;
        poleRok.replaceChildren(...lata.map((r) => new Option(r, r)));
        poleRok.value = lata.includes(Number(poprzedni)) ? poprzedni : String(lata[0]);
        if (poprzedni === poleRok.value) return false;
        wczytajRanking();
        return true; // ranking już się wczytuje
    }

    async function wczytajRanking() {
        const sekcja = document.getElementById("sekcja-rankingu");
        if (!poleWoj.value || !poleRok.value) {
            sekcja.hidden = true;
            return;
        }
        sekcja.hidden = false;
        const lista = document.getElementById("ranking");
        lista.replaceChildren(el("li", "wyciszony", "Wczytywanie…"));
        try {
            const r = await zapytaj(`ranking?${new URLSearchParams({ woj: poleWoj.value, rok: poleRok.value })}`);
            const maks = Math.max(...r.pozycje.map((p) => p.wartosc), 1);
            document.getElementById("opis-rankingu").textContent = r.liczba
                ? `${poleWoj.selectedOptions[0].textContent}, ${r.rok}: ${r.liczba} jednostek z danymi, mediana ${liczba.format(r.mediana)} ${ZMIENNA.jednostka || ""}.`
                : "Brak danych GUS dla tego roku.";
            lista.replaceChildren();
            for (const p of r.pozycje) {
                const li = el("li", "pozycja-cen" + (wybrane.some((w) => w.id === p.bdl_id) ? " pozycja-cen--wybrana" : "") + (p.miasto ? " pozycja-cen--miasto" : ""));
                const pasek = el("span", "pozycja-cen__pasek");
                pasek.style.width = `${(100 * p.wartosc) / maks}%`;
                li.append(el("span", "pozycja-cen__miejsce", `${p.miejsce}.`), el("span", "pozycja-cen__nazwa", p.nazwa),
                    el("span", "pozycja-cen__tor"), el("span", "pozycja-cen__wartosc", liczba.format(p.wartosc)));
                li.querySelector(".pozycja-cen__tor").appendChild(pasek);
                lista.appendChild(li);
            }
        } catch (e) {
            lista.replaceChildren(el("li", "komunikat komunikat--blad", e.message));
        }
    }

    poleWoj.addEventListener("change", wczytajPowiaty);
    poleRok.addEventListener("change", wczytajRanking);

    if (ZMIENNA) {
        wczytajWojewodztwa();
        odswiez();
    }
})();
