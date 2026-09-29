// Moduł dostępność: rysuje gotowe wyniki na siatce H3. Klasy, statystyki
// i udziały liczy serwer (dostepnosc/wyniki.py); tu tylko rysujemy.
(function () {
    "use strict";

    // Czas dojścia: zielony (blisko) → czerwony (daleko). 6 klas: ≤5, ≤10, ≤15, ≤20, ≤30, >30 min.
    const KOLORY_MINUT = ["#30d158", "#a3d94f", "#ffd60a", "#ff9f0a", "#ff6b3d", "#d70015"];
    // Inne wskaźniki: skala sekwencyjna niebieska.
    const KOLORY_INNE = ["#d6e8ff", "#9ecbff", "#5aa7ff", "#1f7ae0", "#0b4fa8", "#062f66"];

    const poleKolumna = document.getElementById("pole-kolumna");
    const kafelki = document.getElementById("kafelki");
    const metaPliku = document.getElementById("meta-pliku");
    const ogniwoEl = document.getElementById("ogniwo");
    const listaOgniw = document.getElementById("lista-ogniw");
    const WARTOSC_LACZNY = "__laczny__";
    const legenda = document.getElementById("legenda");
    const komunikat = document.getElementById("komunikat");

    const formatLiczby = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });
    const urlPliku = URL_PLIK.replace("__PLIK__", encodeURIComponent(NAZWA_PLIKU));

    const mapa = L.map("mapa-dostepnosci", { zoomSnap: 0.25 }).setView([52.4064, 16.9252], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap, siatka: H3",
        maxZoom: 19,
    }).addTo(mapa);

    let warstwa = null;
    let pierwszeRysowanie = true;

    async function pobierzJson(url) {
        const odpowiedz = await fetch(url);
        const dane = await odpowiedz.json().catch(() => ({}));
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        return dane;
    }

    function pokazBlad(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    function kolory(analiza) {
        if (analiza.minuty) return KOLORY_MINUT;
        // Mniej klas niż kolorów: bierzemy równomiernie z całej skali.
        const liczbaKlas = analiza.progi.length + 1;
        return Array.from({ length: liczbaKlas }, (_, i) =>
            KOLORY_INNE[liczbaKlas === 1 ? 3 : Math.round((i * (KOLORY_INNE.length - 1)) / (liczbaKlas - 1))]
        );
    }

    function kafelek(etykieta, wartosc, dopisek) {
        const div = document.createElement("div");
        div.className = "kafelek-maly";
        const e = document.createElement("span");
        e.className = "kafelek-maly__etykieta";
        e.textContent = etykieta;
        const w = document.createElement("span");
        w.className = "kafelek-maly__wartosc";
        w.textContent = wartosc;
        div.append(e, w);
        if (dopisek) {
            const d = document.createElement("span");
            d.className = "kafelek-maly__dopisek";
            d.textContent = dopisek;
            div.appendChild(d);
        }
        return div;
    }

    function pokazStatystyki(analiza) {
        const s = analiza.statystyki;
        const jednostka = analiza.minuty ? " min" : "";
        kafelki.replaceChildren();
        if (analiza.minuty) {
            for (const u of s.udzialy) {
                kafelki.appendChild(
                    kafelek(`Do ${u.prog} min`, `${formatLiczby.format(u.procent)}%`, `${formatLiczby.format(u.powierzchnia_km2)} km²`)
                );
            }
        }
        kafelki.appendChild(kafelek("Mediana", formatLiczby.format(s.mediana) + jednostka));
        kafelki.appendChild(kafelek("Maksimum", formatLiczby.format(s.max) + jednostka));
        kafelki.appendChild(kafelek("Komórki", formatLiczby.format(s.liczba_komorek)));

        metaPliku.textContent =
            `Rozdzielczość H3: ${s.rozdzielczosc} (śr. ${formatLiczby.format(s.pole_komorki_km2 * 100)} ha na komórkę)` +
            (s.komorki_bez_wartosci ? ` · bez wartości: ${s.komorki_bez_wartosci}` : "");
    }

    function pokazLegende(analiza, paleta) {
        legenda.replaceChildren();
        const tytul = document.createElement("div");
        tytul.className = "legenda__tytul";
        tytul.textContent = analiza.najslabsze_ogniwo ? "czas do wszystkich usług" : analiza.minuty ? "czas dojścia" : analiza.kolumna;
        legenda.appendChild(tytul);

        const p = analiza.progi;
        const s = analiza.statystyki;
        const jednostka = analiza.minuty ? " min" : "";
        for (let i = 0; i <= p.length; i += 1) {
            let opis;
            if (i === 0) opis = `≤ ${formatLiczby.format(p[0] ?? s.max)}${jednostka}`;
            else if (i === p.length) opis = `> ${formatLiczby.format(p[i - 1])}${jednostka}`;
            else opis = `${formatLiczby.format(p[i - 1])} – ${formatLiczby.format(p[i])}${jednostka}`;
            const wiersz = document.createElement("div");
            wiersz.className = "legenda__wiersz";
            const kolor = document.createElement("span");
            kolor.className = "legenda__kolor";
            kolor.style.background = paleta[i];
            wiersz.append(kolor, opis);
            legenda.appendChild(wiersz);
        }
    }

    async function pokazKolumne(kolumna) {
        pokazBlad("");
        let analiza;
        try {
            const adres = kolumna === WARTOSC_LACZNY ? `${urlPliku}/laczny` : `${urlPliku}/${encodeURIComponent(kolumna)}`;
            analiza = await pobierzJson(adres);
        } catch (e) {
            pokazBlad(e.message);
            return;
        }
        const paleta = kolory(analiza);
        const jednostka = analiza.minuty ? " min" : "";

        if (warstwa) mapa.removeLayer(warstwa);
        warstwa = L.geoJSON(analiza.geojson, {
            style: (cecha) => ({
                color: paleta[cecha.properties.klasa],
                weight: 0.5,
                fillColor: paleta[cecha.properties.klasa],
                fillOpacity: 0.72,
            }),
            onEachFeature: (cecha, w) => {
                w.bindTooltip(`${formatLiczby.format(cecha.properties.wartosc)}${jednostka}`, { sticky: true });
                w.on("mouseover", () => w.setStyle({ weight: 2.5, color: "#1d1d1f" }));
                w.on("mouseout", () => warstwa.resetStyle(w));
            },
        }).addTo(mapa);
        if (pierwszeRysowanie) {
            mapa.fitBounds(warstwa.getBounds(), { padding: [16, 16] });
            pierwszeRysowanie = false;
        }
        pokazStatystyki(analiza);
        pokazLegende(analiza, paleta);
        pokazOgniwo(analiza);
    }

    // Tylko dla wskaźnika łącznego: która usługa najczęściej jest najdalej.
    function pokazOgniwo(analiza) {
        ogniwoEl.hidden = !analiza.najslabsze_ogniwo;
        if (!analiza.najslabsze_ogniwo) return;
        listaOgniw.replaceChildren();
        for (const o of analiza.najslabsze_ogniwo) {
            const li = document.createElement("li");
            const nazwa = document.createElement("span");
            nazwa.textContent = o.kolumna;
            const tor = document.createElement("span");
            tor.className = "ogniwo__tor";
            const slupek = document.createElement("span");
            slupek.className = "ogniwo__slupek";
            slupek.style.width = `${o.procent}%`;
            tor.appendChild(slupek);
            const procent = document.createElement("span");
            procent.className = "ogniwo__procent";
            procent.textContent = `${formatLiczby.format(o.procent)}%`;
            li.append(nazwa, tor, procent);
            listaOgniw.appendChild(li);
        }
    }

    poleKolumna.addEventListener("change", () => pokazKolumne(poleKolumna.value));

    pobierzJson(urlPliku)
        .then((meta) => {
            if (meta.laczny_dostepny) {
                poleKolumna.add(new Option("★ Wszystkie usługi naraz (min)", WARTOSC_LACZNY));
            }
            for (const k of meta.kolumny) {
                poleKolumna.add(new Option(k.nazwa + (k.minuty ? " (min)" : ""), k.nazwa));
            }
            return pokazKolumne(poleKolumna.value);
        })
        .catch((e) => pokazBlad(`Nie udało się wczytać pliku: ${e.message}`));
})();
