// Fiszki „gdzie to jest” (ETAP 248): kliknięcie na mapie wskazuje miejsce
// odpowiedzi, zapis tworzy zwykłą fiszkę z punktem (serwer: fiszki/trasy_mapa.py).
(function () {
    "use strict";

    const mapa = L.map("mapa-fiszek").setView([52.4064, 16.9252], 12);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap", maxZoom: 19, referrerPolicy: "strict-origin-when-cross-origin",
    }).addTo(mapa);
    const warstwaFiszek = L.featureGroup().addTo(mapa);
    const formularz = document.getElementById("formularz-miejsca");
    const lista = document.getElementById("lista-miejsc");
    let wskazane = null;
    let znacznik = null;
    let okrag = null;

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function dodajDoMapy(f) {
        L.circle([f.lat, f.lng], { radius: f.promien_m, color: "#0071e3", weight: 1, fillOpacity: 0.12, interactive: false }).addTo(warstwaFiszek);
        L.circleMarker([f.lat, f.lng], { radius: 5, color: "#0071e3", fillOpacity: 1 }).bindTooltip(f.odpowiedz).addTo(warstwaFiszek);
        const li = element("li");
        const przycisk = element("button", "przycisk--tekst", f.pytanie);
        przycisk.type = "button";
        przycisk.addEventListener("click", () => mapa.setView([f.lat, f.lng], Math.max(mapa.getZoom(), 14)));
        li.append(przycisk, element("span", "wyciszony", ` — ${f.odpowiedz}`));
        lista.prepend(li);
    }

    FISZKI_MIEJSC.slice().reverse().forEach(dodajDoMapy);
    if (FISZKI_MIEJSC.length) mapa.fitBounds(warstwaFiszek.getBounds(), { padding: [30, 30], maxZoom: 14 });

    function pokazWskazane() {
        const promien = Number(formularz.elements.promien_m.value);
        if (!znacznik) {
            znacznik = L.marker(wskazane, { draggable: true, keyboard: false }).addTo(mapa);
            znacznik.on("dragend", () => {
                wskazane = znacznik.getLatLng();
                pokazWskazane();
            });
            okrag = L.circle(wskazane, { radius: promien, color: "#ff9f0a", weight: 1, fillOpacity: 0.15, interactive: false }).addTo(mapa);
        }
        znacznik.setLatLng(wskazane);
        okrag.setLatLng(wskazane).setRadius(promien);
        document.getElementById("stan-miejsca").textContent = `Miejsce: ${wskazane.lat.toFixed(5)}, ${wskazane.lng.toFixed(5)} (znacznik można przeciągnąć).`;
    }

    if (!formularz) return;
    mapa.on("click", (e) => {
        wskazane = e.latlng;
        pokazWskazane();
    });
    formularz.elements.promien_m.addEventListener("change", () => wskazane && pokazWskazane());
    formularz.addEventListener("submit", async (e) => {
        e.preventDefault();
        const blad = document.getElementById("blad-miejsca");
        blad.hidden = true;
        if (!wskazane) {
            blad.textContent = "Najpierw kliknij na mapie miejsce odpowiedzi.";
            blad.hidden = false;
            return;
        }
        const dane = Object.fromEntries(new FormData(formularz));
        try {
            const odp = await fetch(URL_ZAPISZ, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...dane, pdf_id: Number(dane.pdf_id), promien_m: Number(dane.promien_m), lat: wskazane.lat, lng: wskazane.lng }),
            });
            const w = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(w.blad || `Błąd ${odp.status}`);
            dodajDoMapy(w);
            document.getElementById("liczba-miejsc").textContent = String(lista.children.length);
            formularz.elements.pytanie.value = formularz.elements.odpowiedz.value = "";
            mapa.removeLayer(znacznik);
            mapa.removeLayer(okrag);
            znacznik = okrag = wskazane = null;
            document.getElementById("stan-miejsca").textContent = "Zapisano. Kliknij na mapie miejsce następnej fiszki.";
            formularz.elements.pytanie.focus();
        } catch (err) {
            blad.textContent = err.message;
            blad.hidden = false;
        }
    });
})();
