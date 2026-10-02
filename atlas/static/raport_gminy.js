// Atlas: raport gminy (ETAP 63). Każdy wskaźnik to osobne zapytanie —
// wiersze wypełniają się, gdy przychodzą dane z GUS (po kilka naraz,
// żeby nie przekroczyć limitu zapytań BDL).
(function () {
    "use strict";

    const ROWNOLEGLE = 3;
    const liczba = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 });
    const procent = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1, signDisplay: "exceptZero" });

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    // Mały wykres linii (sparkline) z szeregu — SVG bez biblioteki.
    function trend(szereg) {
        const NS = "http://www.w3.org/2000/svg";
        const szer = 120, wys = 32, m = 3;
        const svg = document.createElementNS(NS, "svg");
        svg.setAttribute("viewBox", `0 0 ${szer} ${wys}`);
        svg.setAttribute("width", szer);
        svg.setAttribute("height", wys);
        svg.setAttribute("role", "img");
        svg.setAttribute("aria-label", `Trend ${szereg[0].rok}–${szereg[szereg.length - 1].rok}`);
        if (szereg.length < 2) return svg;
        const lata = szereg.map((p) => p.rok), wartosci = szereg.map((p) => p.wartosc);
        const [r0, r1] = [Math.min(...lata), Math.max(...lata)];
        const [w0, w1] = [Math.min(...wartosci), Math.max(...wartosci)];
        const x = (r) => m + ((r - r0) / (r1 - r0)) * (szer - 2 * m);
        const y = (w) => (w1 === w0 ? wys / 2 : wys - m - ((w - w0) / (w1 - w0)) * (wys - 2 * m));
        const linia = document.createElementNS(NS, "polyline");
        linia.setAttribute("points", szereg.map((p) => `${x(p.rok).toFixed(1)},${y(p.wartosc).toFixed(1)}`).join(" "));
        linia.setAttribute("class", "raport-gminy__linia");
        const koniec = document.createElementNS(NS, "circle");
        const ost = szereg[szereg.length - 1];
        koniec.setAttribute("cx", x(ost.rok).toFixed(1));
        koniec.setAttribute("cy", y(ost.wartosc).toFixed(1));
        koniec.setAttribute("r", "2.5");
        koniec.setAttribute("class", "raport-gminy__punkt");
        const tytul = document.createElementNS(NS, "title");
        tytul.textContent = `${r0}: ${liczba.format(szereg[0].wartosc)} → ${r1}: ${liczba.format(ost.wartosc)}`;
        svg.append(tytul, linia, koniec);
        return svg;
    }

    function wypelnij(wiersz, dane) {
        const pole = (nazwa) => wiersz.querySelector(`[data-pole="${nazwa}"]`);
        if (dane.blad) {
            pole("wartosc").replaceChildren(element("span", "komunikat--blad-tekst", "błąd"));
            pole("wartosc").title = dane.blad;
            return;
        }
        const s = dane.podsumowanie;
        if (!s) {
            pole("wartosc").replaceChildren(element("span", "wyciszony", "brak danych"));
            return;
        }
        pole("rok").textContent = s.rok;
        pole("wartosc").textContent = liczba.format(s.wartosc);
        if (s.zmiana) {
            // Bez kolorów „dobrze/źle”: wzrost bezrobocia to nie to samo co wzrost ludności.
            const strzalka = s.zmiana.zmiana > 0 ? "▲ " : s.zmiana.zmiana < 0 ? "▼ " : "";
            const tekst = s.zmiana.zmiana_proc === null ? liczba.format(s.zmiana.zmiana) : `${procent.format(s.zmiana.zmiana_proc)}%`;
            const span = element("span", "raport-gminy__zmiana", strzalka + tekst);
            span.title = `od ${s.zmiana.od}: ${liczba.format(s.zmiana.wartosc_od)}`;
            pole("zmiana").replaceChildren(span, element("span", "wyciszony", ` od ${s.zmiana.od}`));
        } else {
            pole("zmiana").textContent = "—";
        }
        pole("pozycja").textContent = s.pozycja ? `${s.pozycja} / ${s.liczba_gmin}` : "—";
        pole("mediana").textContent = s.mediana_wojewodztwa === null ? "—" : liczba.format(s.mediana_wojewodztwa);
        pole("trend").replaceChildren(trend(s.szereg));
        // ETAP 92: ekstrapolacja trendu — liczy serwer, tu tylko podpis.
        if (s.prognoza) {
            const p = s.prognoza;
            const podpis = element("div", "raport-gminy__prognoza" + (p.stabilny ? "" : " raport-gminy__prognoza--niestabilny"),
                // 3 cyfry znaczące — ekstrapolacja na 5 lat nie ma dokładności do jedności
                `→ ${p.rok}: ~${liczba.format(Number(p.wartosc.toPrecision(3)))}${p.stabilny ? "" : " (trend niestabilny)"}`);
            podpis.title = `Trend liniowy ${p.od}–${p.do}: ${procent.format(p.zmiana_roczna)} rocznie, R² = ${liczba.format(Math.round(p.r2 * 100) / 100)}. Ekstrapolacja „gdyby zmiana się utrzymała”, nie prognoza GUS.`;
            pole("trend").appendChild(podpis);
        }
    }

    async function pobierzPodsumowanie(url) {
        try {
            const odpowiedz = await fetch(url);
            return await odpowiedz.json().catch(() => ({ blad: `Błąd ${odpowiedz.status}` }));
        } catch (e) {
            return { blad: "Brak połączenia z aplikacją." };
        }
    }

    // Druga gmina (ETAP 76): wartość i miejsce w jej własnym województwie.
    function wypelnijDruga(wiersz, dane) {
        const wartosc = wiersz.querySelector('[data-pole="druga-wartosc"]');
        const pozycja = wiersz.querySelector('[data-pole="druga-pozycja"]');
        const s = dane.podsumowanie;
        if (dane.blad || !s) {
            wartosc.replaceChildren(element("span", dane.blad ? "komunikat--blad-tekst" : "wyciszony", dane.blad ? "błąd" : "brak danych"));
            if (dane.blad) wartosc.title = dane.blad;
            return;
        }
        wartosc.textContent = liczba.format(s.wartosc);
        wartosc.title = `rok ${s.rok}`;
        pozycja.textContent = s.pozycja ? `${s.pozycja} / ${s.liczba_gmin}` : "—";
    }

    async function wczytaj(wiersz) {
        const id = wiersz.dataset.wskaznik;
        wypelnij(wiersz, await pobierzPodsumowanie(URL_WSKAZNIK + id));
        if (URL_WSKAZNIK_DRUGIEJ) wypelnijDruga(wiersz, await pobierzPodsumowanie(URL_WSKAZNIK_DRUGIEJ + id));
    }

    async function wczytajWszystkie() {
        const kolejka = [...document.querySelectorAll("tr[data-wskaznik]")];
        const robotnicy = Array.from({ length: ROWNOLEGLE }, async () => {
            while (kolejka.length) await wczytaj(kolejka.shift());
        });
        await Promise.all(robotnicy);
    }

    // ---------- opis Gemini ----------

    // ---------- wybór gminy do porównania (ETAP 76) ----------

    const porownajWoj = document.getElementById("porownaj-woj");
    const porownajGmina = document.getElementById("porownaj-gmina");
    fetch(URL_WOJEWODZTWA)
        .then((r) => r.json())
        .then((woj) => woj.forEach((w) => porownajWoj.appendChild(new Option(w.nazwa, w.bdl_id))))
        .catch(() => (porownajWoj.hidden = true));
    porownajWoj.addEventListener("change", async () => {
        porownajGmina.hidden = true;
        if (!porownajWoj.value) return;
        const gminy = await fetch(URL_GMINY.replace("000000000000", porownajWoj.value)).then((r) => r.json()).catch(() => []);
        porownajGmina.replaceChildren(new Option("— gmina —", ""));
        for (const g of gminy) if (g.bdl_id !== GMINA_ID) porownajGmina.appendChild(new Option(g.nazwa, g.bdl_id));
        porownajGmina.hidden = false;
    });
    porownajGmina.addEventListener("change", () => porownajGmina.value && porownajGmina.form.submit());

    const przycisk = document.getElementById("przycisk-opis"); // brak, gdy zestaw wskaźników jest pusty
    const opis = document.getElementById("opis");
    if (przycisk) przycisk.addEventListener("click", async () => {
        przycisk.disabled = true;
        opis.className = "wyciszony";
        opis.textContent = "Gemini pisze opis…";
        try {
            const odpowiedz = await fetch(URL_OPIS, { method: "POST" });
            const dane = await odpowiedz.json().catch(() => ({}));
            if (dane.fakty) {
                const lista = document.getElementById("lista-faktow");
                lista.replaceChildren(...dane.fakty.map((f) => element("li", "", f)));
                document.getElementById("fakty-opisu").hidden = false;
            }
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            opis.className = "raport-gminy__tekst-opisu";
            opis.textContent = dane.opis;
        } catch (e) {
            opis.className = "komunikat komunikat--blad";
            opis.textContent = e.message;
        } finally {
            przycisk.disabled = false;
        }
    });

    // Mapa położenia: przy błędzie PRG (np. brak sieci) zostaje sam podpis z przyczyną.
    const mapaPolozenia = document.getElementById("mapa-polozenia");
    async function brakMapy() {
        const figura = mapaPolozenia.closest("figure");
        figura.classList.add("raport-gminy__polozenie--brak");
        const odpowiedz = await fetch(mapaPolozenia.src).catch(() => null);
        const przyczyna = odpowiedz ? await odpowiedz.text() : "brak połączenia z aplikacją";
        figura.querySelector("figcaption").textContent = `Mapa położenia niedostępna: ${przyczyna}`;
    }
    // Obrazek mógł się już nie wczytać, zanim ten skrypt podpiął obsługę błędu.
    if (mapaPolozenia.complete && mapaPolozenia.naturalWidth === 0) brakMapy();
    else mapaPolozenia.addEventListener("error", brakMapy);

    wczytajWszystkie();
})();
