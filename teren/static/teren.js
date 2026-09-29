// Moduł teren: strona projektu — mapa i tabela punktów, import pliku z
// telefonu, filtr po polu, edycja pól formularza (ETAP 65).
(function () {
    "use strict";

    const komunikatEl = document.getElementById("komunikat");
    const filtrPola = document.getElementById("filtr-pola");
    const legenda = document.getElementById("legenda");
    const PALETA = ["#0a84ff", "#ff9f0a", "#30d158", "#ff375f", "#bf5af2", "#64d2ff", "#ffd60a", "#ac8e68", "#5e5ce6", "#ff6961"];
    const BRAK = "(brak wartości)";
    let punkty = [];
    let ukryte = new Set(); // wartości filtra wyłączone kliknięciem w legendzie
    const znaczniki = new Map(); // id punktu → znacznik

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function komunikat(tekst, blad) {
        komunikatEl.textContent = tekst;
        komunikatEl.className = `komunikat ${blad ? "komunikat--blad" : "komunikat--sukces"}`;
        komunikatEl.hidden = !tekst;
    }

    async function zapytaj(url, opcje = {}) {
        const odpowiedz = await fetch(url, opcje);
        const dane = await odpowiedz.json().catch(() => ({}));
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        return dane;
    }

    const tekstWartosci = (w) => (w === true ? "tak" : w === false ? "nie" : w === undefined || w === null ? "" : String(w));

    // ---------- mapa ----------

    const mapa = L.map("mapa-terenu").setView([52.4064, 16.9252], 13);
    // OSM wymaga nagłówka Referer (zob. D-041) — łagodniejsza polityka tylko dla kafelków.
    const PODKLADY = {
        "Mapa (OpenStreetMap)": L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap", maxZoom: 19, referrerPolicy: "strict-origin-when-cross-origin",
        }),
        "Ortofotomapa (GUGiK)": L.tileLayer.wms("https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution", {
            layers: "Raster", format: "image/jpeg", version: "1.3.0", attribution: "ortofotomapa: GUGiK", maxZoom: 20,
        }),
        "Bez podkładu": L.layerGroup(),
    };
    PODKLADY["Mapa (OpenStreetMap)"].addTo(mapa);
    L.control.layers(PODKLADY, {}, { position: "topright" }).addTo(mapa);
    L.control.scale({ imperial: false }).addTo(mapa);
    const warstwaPunktow = L.featureGroup().addTo(mapa);

    function kolory() {
        const pole = PROJEKT.pola.find((p) => p.nazwa === filtrPola.value);
        if (!pole) return new Map();
        const wartosci = pole.typ === "wybor" ? pole.opcje : pole.typ === "tak_nie" ? ["tak", "nie"] : [];
        return new Map([...wartosci, BRAK].map((w, i) => [w, w === BRAK ? "#8e8e93" : PALETA[i % PALETA.length]]));
    }

    function wartoscFiltra(p) {
        return tekstWartosci(p.wartosci[filtrPola.value]) || BRAK;
    }

    function dymek(p) {
        const div = element("div", "dymek");
        if (p.zdjecie) {
            const a = element("a");
            a.href = p.zdjecie;
            a.target = "_blank";
            const img = element("img", "dymek__zdjecie");
            img.src = p.zdjecie;
            img.alt = "Zdjęcie punktu";
            a.appendChild(img);
            div.appendChild(a);
        }
        const lista = element("dl", "dymek__wartosci");
        for (const pole of PROJEKT.pola) {
            const w = tekstWartosci(p.wartosci[pole.nazwa]);
            if (w) lista.append(element("dt", "", pole.nazwa), element("dd", "", w));
        }
        div.appendChild(lista);
        if (p.uwagi) div.appendChild(element("p", "dymek__uwagi", p.uwagi));
        div.appendChild(element("p", "wyciszony", `${new Date(p.czas).toLocaleString("pl-PL")}${p.dokladnosc_m !== null ? ` · GPS ± ${Math.round(p.dokladnosc_m)} m` : ""}`));
        return div;
    }

    function rysuj() {
        warstwaPunktow.clearLayers();
        znaczniki.clear();
        const paleta = kolory();
        for (const p of punkty) {
            if (p.lat === null) continue;
            const wartosc = wartoscFiltra(p);
            if (ukryte.has(wartosc)) continue;
            const z = L.circleMarker([p.lat, p.lng], {
                radius: 7, weight: 2, color: "#ffffff", fillColor: paleta.get(wartosc) || "#0a84ff", fillOpacity: 0.95,
            }).bindPopup(() => dymek(p), { maxWidth: 280 });
            z.addTo(warstwaPunktow);
            znaczniki.set(p.id, z);
        }
        rysujLegende(paleta);
    }

    function rysujLegende(paleta) {
        legenda.replaceChildren();
        const liczby = new Map();
        for (const p of punkty) liczby.set(wartoscFiltra(p), (liczby.get(wartoscFiltra(p)) || 0) + 1);
        for (const [wartosc, kolor] of paleta) {
            if (!liczby.get(wartosc)) continue;
            const b = element("button", `legenda__pozycja${ukryte.has(wartosc) ? " legenda__pozycja--ukryta" : ""}`);
            b.type = "button";
            b.title = "Kliknij, żeby ukryć albo pokazać na mapie";
            const probka = element("span", "legenda__probka");
            probka.style.background = kolor;
            b.append(probka, element("span", "", wartosc), element("span", "wyciszony", ` ${liczby.get(wartosc)}`));
            b.addEventListener("click", () => {
                ukryte.has(wartosc) ? ukryte.delete(wartosc) : ukryte.add(wartosc);
                rysuj();
            });
            legenda.appendChild(b);
        }
    }

    // ---------- tabela ----------

    function rysujTabele() {
        const naglowek = document.getElementById("naglowek-tabeli");
        const tr = element("tr");
        tr.append(element("th", "", "Czas"), ...PROJEKT.pola.map((p) => element("th", "", p.nazwa)), element("th", "", "Uwagi"), element("th", "", "Położenie"), element("th", "", "Zdjęcie"), element("th"));
        naglowek.replaceChildren(tr);
        const tabela = document.getElementById("tabela-punktow");
        tabela.replaceChildren();
        for (const p of punkty) {
            const wiersz = element("tr");
            wiersz.append(element("td", "", new Date(p.czas).toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" })));
            for (const pole of PROJEKT.pola) wiersz.append(element("td", "", tekstWartosci(p.wartosci[pole.nazwa])));
            wiersz.append(element("td", "komorka-uwag", p.uwagi));
            const polozenie = element("td");
            if (p.lat === null) {
                polozenie.textContent = "brak";
            } else {
                const pokaz = element("button", "przycisk--tekst", p.dokladnosc_m !== null ? `± ${Math.round(p.dokladnosc_m)} m` : "ręcznie");
                pokaz.type = "button";
                pokaz.title = "Pokaż na mapie";
                pokaz.addEventListener("click", () => {
                    mapa.setView([p.lat, p.lng], Math.max(mapa.getZoom(), 18));
                    const z = znaczniki.get(p.id);
                    if (z) z.openPopup();
                    window.scrollTo({ top: 0, behavior: "smooth" });
                });
                polozenie.append(pokaz);
            }
            const foto = element("td");
            if (p.zdjecie) {
                const a = element("a");
                a.href = p.zdjecie;
                a.target = "_blank";
                const img = element("img", "miniatura");
                img.src = p.zdjecie;
                img.alt = "Zdjęcie";
                img.loading = "lazy";
                a.appendChild(img);
                foto.appendChild(a);
            }
            const usun = element("button", "przycisk--tekst przycisk--niebezpieczny-tekst", "Usuń");
            usun.type = "button";
            usun.addEventListener("click", async () => {
                if (!confirm("Usunąć ten punkt (razem ze zdjęciem)?")) return;
                try {
                    await zapytaj(`${URL_PROJEKTU}/punkty/${p.id}`, { method: "DELETE" });
                    await wczytaj(false);
                } catch (e) {
                    komunikat(e.message, true);
                }
            });
            const akcje = element("td");
            akcje.append(usun);
            wiersz.append(polozenie, foto, akcje);
            tabela.appendChild(wiersz);
        }
    }

    async function wczytaj(dopasuj) {
        punkty = await zapytaj(`${URL_PROJEKTU}/punkty`);
        const zPolozeniem = punkty.filter((p) => p.lat !== null).length;
        const zdjec = punkty.filter((p) => p.zdjecie).length;
        document.getElementById("podsumowanie").textContent = punkty.length
            ? `${punkty.length} pkt (na mapie: ${zPolozeniem}, ze zdjęciem: ${zdjec})`
            : "Brak punktów — pobierz formularz na telefon i zaimportuj plik z punktami.";
        rysuj();
        rysujTabele();
        if (dopasuj && warstwaPunktow.getLayers().length) mapa.fitBounds(warstwaPunktow.getBounds(), { padding: [40, 40], maxZoom: 18 });
    }

    let filtrUstawiony = false; // po pierwszym ustawieniu szanujemy wybór użytkownika (też „jednolity”)

    function wypelnijFiltr() {
        const poprzedni = filtrPola.value;
        filtrPola.replaceChildren(new Option("kolor punktów: jednolity", ""));
        for (const p of PROJEKT.pola) {
            if (p.typ === "wybor" || p.typ === "tak_nie") filtrPola.appendChild(new Option(`kolor wg: ${p.nazwa}`, p.nazwa));
        }
        if (filtrUstawiony && [...filtrPola.options].some((o) => o.value === poprzedni)) filtrPola.value = poprzedni;
        else if (filtrPola.options.length > 1) filtrPola.selectedIndex = 1; // domyślnie kolor wg pierwszego pola wyboru
        filtrUstawiony = true;
    }

    filtrPola.addEventListener("change", () => {
        ukryte = new Set();
        rysuj();
    });

    // ---------- import ----------

    document.getElementById("formularz-importu").addEventListener("submit", async (e) => {
        e.preventDefault();
        const plik = document.getElementById("plik-importu").files[0];
        if (!plik) return;
        const dane = new FormData();
        dane.append("plik", plik);
        try {
            const wynik = await zapytaj(`${URL_PROJEKTU}/import`, { method: "POST", body: dane });
            komunikat(`Zaimportowano punkty: ${wynik.dodane}${wynik.pominiete ? `, pominięte (już były): ${wynik.pominiete}` : ""}.`, false);
            e.target.reset();
            await wczytaj(true);
        } catch (err) {
            komunikat(`Import nieudany: ${err.message}`, true);
        }
    });

    // ---------- edycja pól ----------

    const edytor = document.getElementById("edytor-pol");

    function wierszPola(pole) {
        const li = element("li", "edytor-pol__wiersz");
        const nazwa = element("input");
        nazwa.type = "text";
        nazwa.maxLength = 200;
        nazwa.value = pole.nazwa;
        nazwa.placeholder = "nazwa pola";
        nazwa.dataset.rola = "nazwa";
        const typ = element("select");
        typ.dataset.rola = "typ";
        for (const [klucz, opis] of Object.entries(TYPY)) typ.appendChild(new Option(opis, klucz));
        typ.value = pole.typ;
        const opcje = element("input");
        opcje.type = "text";
        opcje.value = pole.opcje.join(", ");
        opcje.placeholder = "opcje po przecinku, np. dobry, średni, zły";
        opcje.dataset.rola = "opcje";
        opcje.hidden = pole.typ !== "wybor";
        typ.addEventListener("change", () => (opcje.hidden = typ.value !== "wybor"));
        const usun = element("button", "przycisk--tekst", "✕");
        usun.type = "button";
        usun.title = "Usuń pole";
        usun.addEventListener("click", () => li.remove());
        li.append(nazwa, typ, usun, opcje);
        return li;
    }

    function rysujEdytor() {
        edytor.replaceChildren(...PROJEKT.pola.map(wierszPola));
    }

    document.getElementById("dodaj-pole").addEventListener("click", () => edytor.appendChild(wierszPola({ nazwa: "", typ: "tekst", opcje: [] })));

    document.getElementById("zapisz-pola").addEventListener("click", async () => {
        const pola = [...edytor.children].map((li) => ({
            nazwa: li.querySelector("[data-rola=nazwa]").value,
            typ: li.querySelector("[data-rola=typ]").value,
            opcje: li.querySelector("[data-rola=opcje]").value.split(",").map((o) => o.trim()).filter(Boolean),
        }));
        try {
            const projekt = await zapytaj(URL_PROJEKTU, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ nazwa: document.getElementById("pole-nazwa").value, pola }),
            });
            PROJEKT.pola = projekt.pola;
            PROJEKT.nazwa = projekt.nazwa;
            document.getElementById("nazwa-projektu").textContent = projekt.nazwa;
            rysujEdytor();
            wypelnijFiltr();
            rysuj();
            rysujTabele();
            komunikat("Zapisano pola. Pobierz formularz na telefon jeszcze raz.", false);
        } catch (e) {
            komunikat(e.message, true);
        }
    });

    document.getElementById("usun-projekt").addEventListener("click", async () => {
        if (!confirm(`Usunąć projekt „${PROJEKT.nazwa}” razem ze wszystkimi punktami i zdjęciami?`)) return;
        try {
            await zapytaj(URL_PROJEKTU, { method: "DELETE" });
            location.href = URL_LISTY;
        } catch (e) {
            komunikat(e.message, true);
        }
    });

    rysujEdytor();
    wypelnijFiltr();
    wczytaj(true).catch((e) => komunikat(e.message, true));
})();
