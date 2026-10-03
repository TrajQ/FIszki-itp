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

    const tekstWartosci = (w) => (w === true ? "tak" : w === false ? "nie" : w === undefined || w === null ? "" : Array.isArray(w) ? w.join("; ") : String(w));

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
        // Skala (ETAP 70): od najlepszej — zielony — do najgorszej — czerwony; ten sam wzór co teren/raport.py.
        const kolor = (i) => (pole.skala
            ? `hsl(${wartosci.length < 2 ? 130 : Math.round(130 - (130 * i) / (wartosci.length - 1))}, 70%, 42%)`
            : PALETA[i % PALETA.length]);
        return new Map([...wartosci, BRAK].map((w, i) => [w, w === BRAK ? "#8e8e93" : kolor(i)]));
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
        div.appendChild(element("p", "wyciszony", `${new Date(p.czas).toLocaleString("pl-PL")}${p.polozenie_reczne ? " · położenie poprawione ręcznie" : p.dokladnosc_m !== null ? ` · GPS ± ${Math.round(p.dokladnosc_m)} m` : ""}`));
        const popraw = element("button", "przycisk--tekst", "Popraw");
        popraw.type = "button";
        popraw.addEventListener("click", () => {
            mapa.closePopup();
            otworzPoprawke(p);
        });
        div.appendChild(popraw);
        const start = element("button", "przycisk--tekst", "Zacznij trasę tutaj"); // ETAP 198
        start.type = "button";
        start.addEventListener("click", () => {
            mapa.closePopup();
            wyznaczTrase(p.id);
        });
        div.appendChild(start);
        return div;
    }

    function rysuj() {
        ukryjTrase(); // trasa dotyczyła poprzedniego zestawu punktów
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

    // ---------- trasa obchodu (ETAP 198) ----------
    // Kolejność liczy serwer (teren/trasa.py); tu linia i numery na mapie.

    const warstwaTrasy = L.layerGroup().addTo(mapa);
    const opisTrasy = document.getElementById("opis-trasy");
    const linkGpx = document.getElementById("trasa-gpx");
    const przyciskUkryj = document.getElementById("ukryj-trase");
    const linkFormularza = document.getElementById("formularz-trasy"); // ETAP 199

    function ukryjTrase() {
        warstwaTrasy.clearLayers();
        znaczniki.forEach((z) => z.unbindTooltip());
        opisTrasy.hidden = linkGpx.hidden = przyciskUkryj.hidden = linkFormularza.hidden = true;
    }

    async function wyznaczTrase(startId) {
        const ids = [...znaczniki.keys()];
        const parametry = new URLSearchParams({ punkty: ids.join(",") });
        if (startId) parametry.set("start", startId);
        let t;
        try {
            t = await zapytaj(`${URL_PROJEKTU}/trasa?${parametry}`);
        } catch (e) {
            komunikat(e.message, true);
            return;
        }
        komunikat("");
        ukryjTrase();
        const polozenie = new Map(punkty.map((p) => [p.id, [p.lat, p.lng]]));
        L.polyline(t.kolejnosc.map((id) => polozenie.get(id)), { color: "#ff375f", weight: 3, dashArray: "6 6", interactive: false }).addTo(warstwaTrasy).bringToBack();
        t.kolejnosc.forEach((id, i) => znaczniki.get(id).bindTooltip(String(i + 1), { permanent: true, direction: "top", className: "numer-trasy" }));
        const km = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 }).format(t.dlugosc_m / 1000);
        opisTrasy.textContent = `${t.kolejnosc.length} pkt, ok. ${km} km w linii prostej (ok. ${t.czas_min} min marszu bez postojów; po ulicach dalej).`;
        linkGpx.href = `${URL_PROJEKTU}/trasa.gpx?${parametry}`;
        linkFormularza.href = `${URL_PROJEKTU}/formularz.html?do_sprawdzenia=${t.kolejnosc.join(",")}`;
        opisTrasy.hidden = linkGpx.hidden = przyciskUkryj.hidden = linkFormularza.hidden = false;
    }

    document.getElementById("wyznacz-trase").addEventListener("click", () => wyznaczTrase(null));
    przyciskUkryj.addEventListener("click", ukryjTrase);

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
            const czas = element("td", "", new Date(p.czas).toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" }));
            if (p.braki.length) {
                // ETAP 166: punkt niezgodny z regułami pól (np. zebrany starszym formularzem)
                const znak = element("span", "znak-brakow", " ⚠");
                znak.title = p.braki.join("; ");
                czas.append(znak);
                wiersz.classList.add("wiersz-z-brakami");
            }
            wiersz.append(czas);
            for (const pole of PROJEKT.pola) wiersz.append(element("td", "", tekstWartosci(p.wartosci[pole.nazwa])));
            wiersz.append(element("td", "komorka-uwag", p.uwagi));
            const polozenie = element("td");
            if (p.lat === null) {
                polozenie.textContent = "brak";
            } else {
                const pokaz = element("button", "przycisk--tekst", p.polozenie_reczne ? "poprawione" : p.dokladnosc_m !== null ? `± ${Math.round(p.dokladnosc_m)} m` : "ręcznie");
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
            const popraw = element("button", "przycisk--tekst", "Popraw");
            popraw.type = "button";
            popraw.addEventListener("click", () => otworzPoprawke(p));
            const akcje = element("td", "komorka-akcji");
            akcje.append(popraw, usun);
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
        const zBrakami = punkty.filter((p) => p.braki.length).length;
        const braki = document.getElementById("braki-punktow");
        braki.hidden = !zBrakami;
        braki.textContent = `${zBrakami} pkt nie spełnia reguł pól (brak wymaganej wartości albo liczba poza zakresem) — oznaczone ⚠ w tabeli; „Popraw” uzupełnia wartości.`;
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

    // ---------- poprawianie punktu (ETAP 72) ----------

    const panelPoprawki = document.getElementById("panel-poprawki");
    const polaPoprawki = document.getElementById("poprawka-pola");
    const opisPolozenia = document.getElementById("poprawka-polozenie");
    let poprawiany = null; // punkt w edycji
    let znacznikPrzesuwania = null; // przeciągalny znacznik nowego położenia

    function polePoprawki(pole, wartosc) {
        const etykieta = element("label", "", pole.nazwa);
        let kontrolka;
        if (pole.typ === "wybor" || pole.typ === "tak_nie") {
            kontrolka = element("select");
            kontrolka.appendChild(new Option("—", ""));
            const opcje = pole.typ === "wybor" ? pole.opcje : ["tak", "nie"];
            for (const o of opcje) kontrolka.appendChild(new Option(o, o));
            kontrolka.value = wartosc === undefined ? "" : tekstWartosci(wartosc);
        } else if (pole.typ === "wiele") {
            // ETAP 93: wielokrotny wybór — pola zaznaczania
            kontrolka = element("div", "poprawka-wiele");
            for (const o of pole.opcje) {
                const l = element("label", "poprawka-wiele__opcja");
                const c = element("input");
                c.type = "checkbox";
                c.value = o;
                c.checked = Array.isArray(wartosc) && wartosc.includes(o);
                l.append(c, " " + o);
                kontrolka.appendChild(l);
            }
        } else {
            kontrolka = element("input");
            kontrolka.type = pole.typ === "liczba" ? "number" : "text";
            if (pole.typ === "liczba") kontrolka.step = "any";
            kontrolka.value = wartosc === undefined ? "" : String(wartosc);
        }
        kontrolka.dataset.pole = pole.nazwa;
        kontrolka.dataset.typ = pole.typ;
        etykieta.append(kontrolka);
        return etykieta;
    }

    function zakonczPrzesuwanie() {
        if (znacznikPrzesuwania) mapa.removeLayer(znacznikPrzesuwania);
        znacznikPrzesuwania = null;
        document.getElementById("poprawka-przesun").textContent = "✥ Przesuń na mapie";
    }

    function otworzPoprawke(p) {
        zakonczPrzesuwanie();
        poprawiany = p;
        panelPoprawki.hidden = false;
        document.getElementById("poprawka-opis").textContent = new Date(p.czas).toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" });
        polaPoprawki.replaceChildren(...PROJEKT.pola.map((pole) => polePoprawki(pole, p.wartosci[pole.nazwa])));
        document.getElementById("poprawka-uwagi").value = p.uwagi;
        opisPolozenia.textContent = p.lat === null ? "punkt bez położenia" : "";
        panelPoprawki.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function zamknijPoprawke() {
        zakonczPrzesuwanie();
        poprawiany = null;
        panelPoprawki.hidden = true;
    }

    document.getElementById("poprawka-przesun").addEventListener("click", () => {
        if (!poprawiany) return;
        if (znacznikPrzesuwania) return zakonczPrzesuwanie();
        // Punkt bez położenia wstawiamy na środek mapy — potem przeciągnąć na miejsce.
        const start = poprawiany.lat === null ? mapa.getCenter() : L.latLng(poprawiany.lat, poprawiany.lng);
        znacznikPrzesuwania = L.marker(start, { draggable: true, autoPan: true, title: "Przeciągnij w poprawne miejsce" }).addTo(mapa);
        mapa.setView(start, Math.max(mapa.getZoom(), 18));
        document.getElementById("poprawka-przesun").textContent = "✕ Nie przesuwaj";
        opisPolozenia.textContent = "Przeciągnij znacznik w poprawne miejsce.";
        znacznikPrzesuwania.on("drag", () => {
            if (poprawiany.lat === null) return;
            const m = Math.round(mapa.distance(znacznikPrzesuwania.getLatLng(), L.latLng(poprawiany.lat, poprawiany.lng)));
            opisPolozenia.textContent = `przesunięcie: ${m} m`;
        });
    });

    document.getElementById("poprawka-anuluj").addEventListener("click", zamknijPoprawke);

    document.getElementById("poprawka-zapisz").addEventListener("click", async () => {
        if (!poprawiany) return;
        const wartosci = {};
        for (const k of polaPoprawki.querySelectorAll("[data-pole]")) {
            if (k.dataset.typ === "wiele") {
                const zaznaczone = [...k.querySelectorAll("input:checked")].map((c) => c.value);
                if (zaznaczone.length) wartosci[k.dataset.pole] = zaznaczone;
                continue;
            }
            if (k.value === "") continue;
            wartosci[k.dataset.pole] = k.dataset.typ === "liczba" ? Number(k.value) : k.dataset.typ === "tak_nie" ? k.value === "tak" : k.value;
        }
        const cialo = { wartosci, uwagi: document.getElementById("poprawka-uwagi").value };
        if (znacznikPrzesuwania) {
            const { lat, lng } = znacznikPrzesuwania.getLatLng();
            Object.assign(cialo, { lat, lng });
        }
        try {
            await zapytaj(`${URL_PROJEKTU}/punkty/${poprawiany.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(cialo),
            });
            zamknijPoprawke();
            komunikat("Zapisano poprawkę punktu.", false);
            await wczytaj(false);
        } catch (e) {
            komunikat(e.message, true);
        }
    });

    // ---------- obszar prac (ETAP 83) ----------

    const warstwaObszaru = L.layerGroup().addTo(mapa);

    function pokazObszar() {
        warstwaObszaru.clearLayers();
        const opis = document.getElementById("opis-obszaru");
        document.getElementById("usun-obszar").hidden = !PROJEKT.obszar;
        if (!PROJEKT.obszar) {
            opis.textContent = "Nie ustawiono — formularz na telefon będzie miał mapę bez podkładu.";
            return;
        }
        const [s, w, n, e] = PROJEKT.obszar;
        L.rectangle([[s, w], [n, e]], { color: "#0071e3", weight: 2, dashArray: "6 4", fill: false, interactive: false }).addTo(warstwaObszaru);
        const szer = Math.round(mapa.distance([s, w], [s, e]));
        const wys = Math.round(mapa.distance([s, w], [n, w]));
        opis.textContent = `Ustawiony: ${szer} × ${wys} m (niebieska przerywana ramka).`;
    }

    async function zapiszObszar(obszar) {
        try {
            const wynik = await zapytaj(`${URL_PROJEKTU}/obszar`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ obszar }),
            });
            PROJEKT.obszar = wynik.obszar;
            pokazObszar();
            komunikat(obszar ? "Zapisano obszar prac. Pobierz formularz na telefon jeszcze raz." : "Usunięto obszar prac.", false);
        } catch (e) {
            komunikat(e.message, true);
        }
    }

    document.getElementById("ustaw-obszar").addEventListener("click", () => {
        const g = mapa.getBounds();
        zapiszObszar([g.getSouth(), g.getWest(), g.getNorth(), g.getEast()]);
    });
    document.getElementById("usun-obszar").addEventListener("click", () => zapiszObszar(null));

    // ---------- import ----------

    document.getElementById("formularz-importu").addEventListener("submit", async (e) => {
        e.preventDefault();
        const plik = document.getElementById("plik-importu").files[0];
        if (!plik) return;
        const dane = new FormData();
        dane.append("plik", plik);
        try {
            const wynik = await zapytaj(`${URL_PROJEKTU}/import`, { method: "POST", body: dane });
            const reszta = (wynik.niedopasowane || []).length ? ` Atrybuty bez pola w projekcie (zapisane w uwagach): ${wynik.niedopasowane.join(", ")}.` : "";
            komunikat(`Zaimportowano punkty: ${wynik.dodane}${wynik.pominiete ? `, pominięte (już były): ${wynik.pominiete}` : ""}.${reszta}`, false);
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
        typ.setAttribute("aria-label", "Typ pola"); // ETAP 130: bez widocznej etykiety w wierszu edytora
        nazwa.setAttribute("aria-label", "Nazwa pola");
        for (const [klucz, opis] of Object.entries(TYPY)) typ.appendChild(new Option(opis, klucz));
        typ.value = pole.typ;
        const opcje = element("input");
        opcje.type = "text";
        opcje.value = pole.opcje.join(", ");
        opcje.placeholder = "opcje po przecinku, np. dobry, średni, zły";
        opcje.dataset.rola = "opcje";
        opcje.hidden = pole.typ !== "wybor" && pole.typ !== "wiele";
        const skala = element("label", "edytor-pol__skala");
        const skalaPole = element("input");
        skalaPole.type = "checkbox";
        skalaPole.checked = Boolean(pole.skala);
        skalaPole.dataset.rola = "skala";
        skala.append(skalaPole, " skala: opcje od najlepszej do najgorszej (kolory od zielonego do czerwonego)");
        skala.hidden = pole.typ !== "wybor";
        // ETAP 166: pole wymagane i zakres liczby — pilnuje ich formularz na telefonie
        const reguly = element("div", "edytor-pol__reguly");
        const wymagane = element("label");
        const wymaganePole = element("input");
        wymaganePole.type = "checkbox";
        wymaganePole.checked = Boolean(pole.wymagane);
        wymaganePole.dataset.rola = "wymagane";
        wymagane.append(wymaganePole, " wymagane");
        const zakres = element("span", "edytor-pol__zakres");
        const granica = (rola, opis) => {
            const input = element("input");
            input.type = "number";
            input.step = "any";
            input.dataset.rola = rola;
            input.value = pole[rola] ?? "";
            input.placeholder = opis;
            input.setAttribute("aria-label", `${opis} — ${pole.nazwa || "nowe pole"}`);
            return input;
        };
        zakres.append("od", granica("min", "min"), "do", granica("max", "max"));
        zakres.hidden = pole.typ !== "liczba";
        reguly.append(wymagane, zakres);
        typ.addEventListener("change", () => {
            opcje.hidden = typ.value !== "wybor" && typ.value !== "wiele";
            skala.hidden = typ.value !== "wybor";
            zakres.hidden = typ.value !== "liczba";
        });
        const usun = element("button", "przycisk--tekst", "✕");
        usun.type = "button";
        usun.title = "Usuń pole";
        usun.addEventListener("click", () => li.remove());
        li.append(nazwa, typ, usun, opcje, skala, reguly);
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
            skala: li.querySelector("[data-rola=skala]").checked,
            wymagane: li.querySelector("[data-rola=wymagane]").checked,
            ...(li.querySelector("[data-rola=typ]").value === "liczba"
                ? { min: li.querySelector("[data-rola=min]").value, max: li.querySelector("[data-rola=max]").value }
                : {}),
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
            await wczytaj(false); // braki punktów (ETAP 166) zależą od nowych reguł pól
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
    pokazObszar();
    wczytaj(true).catch((e) => komunikat(e.message, true));
})();
