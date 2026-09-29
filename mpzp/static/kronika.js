// MPZP: Kronika zmian (ETAP 64) — ortofotomapy archiwalne na suwaku lat
// albo dwa lata obok siebie. Lata i sposób pobierania (parametr TIME albo
// osobna warstwa) podaje serwer z opisu usługi WMS (dane/ortofoto.py).
(function () {
    "use strict";

    const komunikat = document.getElementById("komunikat");
    const suwak = document.getElementById("suwak-lat");
    const rokSuwaka = document.getElementById("rok-suwaka");
    const odtworz = document.getElementById("odtworz");
    const rokLewy = document.getElementById("rok-lewy");
    const rokPrawy = document.getElementById("rok-prawy");
    const mapaPrawaEl = document.getElementById("mapa-prawa");
    let usluga = null; // {url, wersja, lata: [{rok, warstwa, time, przedzial}]}
    let tryb = "suwak";
    let odtwarzanie = null;

    function pokazBlad(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    // ---------- mapy ----------

    function nowaMapa(id) {
        const mapa = L.map(id, { zoomControl: true, maxZoom: 20 });
        if (DZIALKA) {
            const granica = L.geoJSON(DZIALKA.geometria, { style: { color: "#ffd60a", weight: 3, fill: false } }).addTo(mapa);
            mapa.fitBounds(granica.getBounds(), { padding: [60, 60], maxZoom: 19 });
        } else if (PUNKT) {
            mapa.setView(PUNKT, 17);
        } else {
            mapa.setView([52.4064, 16.9252], 15);
        }
        L.control.scale({ imperial: false }).addTo(mapa);
        return mapa;
    }

    const lewa = nowaMapa("mapa-lewa");
    let prawa = null;
    const warstwy = new Map(); // mapa → bieżąca warstwa zdjęć

    // Warstwa WMS danego roku. Opcje spoza listy Leafleta (np. TIME) trafiają
    // do adresu zapytania WMS jako parametry.
    function warstwaRoku(r) {
        const opcje = {
            layers: r.warstwa,
            format: "image/jpeg",
            version: usluga.wersja,
            maxZoom: 20,
            attribution: `ortofotomapa archiwalna ${r.rok}: GUGiK`,
        };
        if (r.time) opcje.TIME = r.time;
        return L.tileLayer.wms(usluga.url, opcje);
    }

    function pokazRok(mapa, r) {
        const nowa = warstwaRoku(r);
        nowa.addTo(mapa);
        nowa.bringToBack();
        const stara = warstwy.get(mapa);
        warstwy.set(mapa, nowa);
        // Stara warstwa znika dopiero po wczytaniu nowej — bez mrugania białym tłem.
        if (stara) nowa.once("load", () => mapa.removeLayer(stara));
        if (stara) setTimeout(() => mapa.hasLayer(stara) && mapa.removeLayer(stara), 4000);
    }

    // ---------- suwak ----------

    function ustawSuwak(indeks) {
        suwak.value = String(indeks);
        const r = usluga.lata[indeks];
        rokSuwaka.textContent = r.rok;
        pokazRok(lewa, r);
    }

    suwak.addEventListener("input", () => ustawSuwak(Number(suwak.value)));
    document.getElementById("rok-wstecz").addEventListener("click", () => usluga && ustawSuwak(Math.max(0, Number(suwak.value) - 1)));
    document.getElementById("rok-dalej").addEventListener("click", () => usluga && ustawSuwak(Math.min(usluga.lata.length - 1, Number(suwak.value) + 1)));

    function zatrzymaj() {
        clearInterval(odtwarzanie);
        odtwarzanie = null;
        odtworz.textContent = "▶ Odtwórz";
    }

    odtworz.addEventListener("click", () => {
        if (odtwarzanie) return zatrzymaj();
        odtworz.textContent = "■ Zatrzymaj";
        if (Number(suwak.value) === usluga.lata.length - 1) ustawSuwak(0);
        odtwarzanie = setInterval(() => {
            const nastepny = Number(suwak.value) + 1;
            if (nastepny >= usluga.lata.length) return zatrzymaj();
            ustawSuwak(nastepny);
        }, 2000);
    });

    // ---------- dwa lata obok siebie ----------

    function synchronizuj(a, b) {
        let wTrakcie = false;
        a.on("move", () => {
            if (wTrakcie) return;
            wTrakcie = true;
            b.setView(a.getCenter(), a.getZoom(), { animate: false });
            wTrakcie = false;
        });
    }

    function pokazPorownanie() {
        if (!prawa) {
            prawa = nowaMapa("mapa-prawa");
            prawa.setView(lewa.getCenter(), lewa.getZoom());
            synchronizuj(lewa, prawa);
            synchronizuj(prawa, lewa);
        }
        pokazRok(lewa, usluga.lata[Number(rokLewy.value)]);
        pokazRok(prawa, usluga.lata[Number(rokPrawy.value)]);
    }

    rokLewy.addEventListener("change", () => pokazRok(lewa, usluga.lata[Number(rokLewy.value)]));
    rokPrawy.addEventListener("change", () => pokazRok(prawa, usluga.lata[Number(rokPrawy.value)]));

    document.querySelectorAll("[data-tryb]").forEach((przycisk) => {
        przycisk.addEventListener("click", () => {
            if (!usluga) return;
            tryb = przycisk.dataset.tryb;
            document.querySelectorAll("[data-tryb]").forEach((p) => p.classList.toggle("aktywny", p === przycisk));
            document.getElementById("panel-suwaka").hidden = tryb !== "suwak";
            document.getElementById("panel-porownania").hidden = tryb !== "porownanie";
            mapaPrawaEl.hidden = tryb !== "porownanie";
            document.getElementById("mapy").classList.toggle("kronika__mapy--dwie", tryb === "porownanie");
            zatrzymaj();
            lewa.invalidateSize();
            if (tryb === "porownanie") {
                prawa && prawa.invalidateSize();
                pokazPorownanie();
            } else {
                ustawSuwak(Number(suwak.value));
            }
        });
    });

    // ---------- start ----------

    async function wczytajLata() {
        const odpowiedz = await fetch(URL_LATA);
        const dane = await odpowiedz.json().catch(() => ({}));
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        usluga = dane;
        const ostatni = usluga.lata.length - 1;
        suwak.max = String(ostatni);
        suwak.disabled = ostatni < 1;
        odtworz.disabled = ostatni < 1;
        for (const [i, r] of usluga.lata.entries()) {
            rokLewy.appendChild(new Option(String(r.rok), String(i)));
            rokPrawy.appendChild(new Option(String(r.rok), String(i)));
        }
        rokLewy.value = "0";
        rokPrawy.value = String(ostatni);
        document.getElementById("uwaga-przedzial").hidden = !usluga.lata.some((r) => r.przedzial);
        ustawSuwak(ostatni);
    }

    wczytajLata().catch((e) => {
        rokSuwaka.textContent = "—";
        pokazBlad(`Nie udało się wczytać lat zdjęć: ${e.message}`);
    });
})();
