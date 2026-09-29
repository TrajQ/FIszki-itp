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
    const linkGeojson = document.getElementById("link-geojson");

    // Link „GeoJSON do QGIS” zawsze odpowiada temu, co widać na mapie.
    function ustawLinkGeojson(po) {
        const kolumna = poleKolumna.value === WARTOSC_LACZNY ? "laczny" : poleKolumna.value;
        const parametry = new URLSearchParams({ plik: NAZWA_PLIKU, kolumna });
        if (po) parametry.set("po", po);
        linkGeojson.href = `${URL_GEOJSON}?${parametry}`;
    }
    // Zmiana czasu (po − przed): szybciej = niebieski, wolniej = pomarańczowy, szary = bez zmian.
    const KOLORY_ZMIANY = ["#1d4ed8", "#60a5fa", "#d1d1d6", "#fb923c", "#c2410c"];
    const poleScenariusz = document.getElementById("pole-scenariusz");
    const przyciskPorownaj = document.getElementById("przycisk-porownaj");
    const trybPorownania = document.getElementById("tryb-porownania");
    const opisPorownania = document.getElementById("opis-porownania");
    const formatProcentu = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });
    const formatZmiany = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1, signDisplay: "exceptZero" });
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
                // Z kolumną ludności: główna liczba to % mieszkańców, obok % powierzchni.
                if (u.procent_ludnosci !== undefined && u.procent_ludnosci !== null) {
                    kafelki.appendChild(
                        kafelek(
                            `Do ${u.prog} min`,
                            `${formatLiczby.format(u.procent_ludnosci)}% mieszk.`,
                            `${formatLiczby.format(u.ludnosc)} os. · ${formatLiczby.format(u.procent)}% pow.`
                        )
                    );
                } else {
                    kafelki.appendChild(
                        kafelek(`Do ${u.prog} min`, `${formatLiczby.format(u.procent)}%`, `${formatLiczby.format(u.powierzchnia_km2)} km²`)
                    );
                }
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
        ustawLinkGeojson(null);
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

    poleKolumna.addEventListener("change", () => {
        if (!trybPorownania.hidden) porownaj();
        else pokazKolumne(poleKolumna.value);
    });

    // ---------- porównanie scenariuszy ----------

    poleScenariusz.addEventListener("change", () => {
        przyciskPorownaj.disabled = !poleScenariusz.value;
    });
    przyciskPorownaj.addEventListener("click", porownaj);
    document.getElementById("zakoncz-porownanie").addEventListener("click", () => {
        trybPorownania.hidden = true;
        pokazKolumne(poleKolumna.value);
    });

    async function porownaj() {
        if (!poleScenariusz.value) return;
        pokazBlad("");
        const kolumna = poleKolumna.value === WARTOSC_LACZNY ? "laczny" : poleKolumna.value;
        const parametry = new URLSearchParams({ przed: NAZWA_PLIKU, po: poleScenariusz.value, kolumna });
        let wynik;
        try {
            wynik = await pobierzJson(`${URL_POROWNANIE}?${parametry}`);
        } catch (e) {
            pokazBlad(e.message);
            return;
        }
        trybPorownania.hidden = false;
        ustawLinkGeojson(poleScenariusz.value);
        opisPorownania.textContent = `Porównanie: ${NAZWA_PLIKU} → ${poleScenariusz.value}`;
        ogniwoEl.hidden = true;

        if (warstwa) mapa.removeLayer(warstwa);
        warstwa = L.geoJSON(wynik.geojson, {
            style: (cecha) => ({
                color: KOLORY_ZMIANY[cecha.properties.klasa],
                weight: 0.5,
                fillColor: KOLORY_ZMIANY[cecha.properties.klasa],
                fillOpacity: 0.75,
            }),
            onEachFeature: (cecha, w) => {
                const p = cecha.properties;
                w.bindTooltip(
                    `${formatLiczby.format(p.przed)} → ${formatLiczby.format(p.po)} min (${formatZmiany.format(p.zmiana)})`,
                    { sticky: true }
                );
            },
        }).addTo(mapa);

        const s = wynik.statystyki;
        kafelki.replaceChildren(
            kafelek(
                "W zasięgu 15 min",
                `${formatProcentu.format(s.procent_15_przed)} → ${formatProcentu.format(s.procent_15_po)}%`,
                `powierzchni; komórek +${s.komorki_weszly_15}` + (s.komorki_wypadly_15 ? `, −${s.komorki_wypadly_15}` : "")
            ),
            kafelek(
                "Poprawa ≥ 1 min",
                `${s.poprawa}`,
                `z ${s.liczba_komorek} komórek; gorzej: ${s.pogorszenie}`
            ),
            kafelek("Mediana zmiany", `${formatZmiany.format(s.mediana_zmiany)} min`),
            kafelek("Największa poprawa", `${formatZmiany.format(s.najwieksza_poprawa)} min`)
        );
        if (s.ludnosc_weszla_15 !== undefined) {
            kafelki.appendChild(
                kafelek("Mieszkańcy, którzy zyskali 15 min", `+${formatLiczby.format(s.ludnosc_weszla_15)}`,
                    s.ludnosc_wypadla_15 ? `stracili: ${formatLiczby.format(s.ludnosc_wypadla_15)}` : "")
            );
        }
        metaPliku.textContent = "Kolor = zmiana czasu dojścia po zmianie (niebieski: szybciej, pomarańczowy: wolniej).";

        legenda.replaceChildren();
        const tytul = document.createElement("div");
        tytul.className = "legenda__tytul";
        tytul.textContent = "zmiana czasu dojścia";
        legenda.appendChild(tytul);
        const opisy = ["szybciej o ≥ 5 min", "szybciej o 1–5 min", "bez zmian (±1 min)", "wolniej o 1–5 min", "wolniej o > 5 min"];
        opisy.forEach((opis, i) => {
            const wiersz = document.createElement("div");
            wiersz.className = "legenda__wiersz";
            const kolor = document.createElement("span");
            kolor.className = "legenda__kolor";
            kolor.style.background = KOLORY_ZMIANY[i];
            wiersz.append(kolor, opis);
            legenda.appendChild(wiersz);
        });
    }

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
