// Quiz z mapą (ETAP 248): pytanie → kliknięcie na mapie → serwer liczy
// odległość od miejsca i ocenę (fiszki/miejsca.py), tu pokazujemy wynik.
(function () {
    "use strict";

    const mapa = L.map("mapa-quizu").setView([52.4064, 16.9252], 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap", maxZoom: 19, referrerPolicy: "strict-origin-when-cross-origin",
    }).addTo(mapa);
    const warstwa = L.featureGroup().addTo(mapa);
    const pytanieEl = document.getElementById("pytanie-mapy");
    const wynikEl = document.getElementById("wynik-mapy");
    const dalej = document.getElementById("dalej-mapy");
    const format = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });
    const KOLORY = { trafione: "#34c759", blisko: "#ff9f0a", "pudło": "#ff3b30" };
    let pytania = [];
    let nr = 0;
    let czeka = false;
    const wyniki = { trafione: 0, blisko: 0, "pudło": 0 };

    function odleglosc(m) {
        return m < 1000 ? `${m} m` : `${format.format(m / 1000)} km`;
    }

    function pokazPytanie() {
        warstwa.clearLayers();
        wynikEl.textContent = "";
        dalej.hidden = true;
        if (nr >= pytania.length) {
            pytanieEl.textContent = `Koniec: trafione ${wyniki.trafione}, blisko ${wyniki.blisko}, pudło ${wyniki["pudło"]} z ${pytania.length}.`;
            document.getElementById("postep-mapy").textContent = "";
            czeka = false;
            return;
        }
        pytanieEl.textContent = pytania[nr].pytanie;
        document.getElementById("postep-mapy").textContent = `${nr + 1} / ${pytania.length}`;
        czeka = true;
    }

    mapa.on("click", async (e) => {
        if (!czeka) return;
        czeka = false;
        try {
            const odp = await fetch(URL_ODPOWIEDZ.replace(/0$/, String(pytania[nr].id)), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ lat: e.latlng.lat, lng: e.latlng.lng }),
            });
            const w = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(w.blad || `Błąd ${odp.status}`);
            wyniki[w.ocena] += 1;
            const kolor = KOLORY[w.ocena];
            L.circle([w.lat, w.lng], { radius: w.promien_m, color: "#0071e3", weight: 1, fillOpacity: 0.15, interactive: false }).addTo(warstwa);
            L.circleMarker([w.lat, w.lng], { radius: 6, color: "#0071e3", fillOpacity: 1, interactive: false }).addTo(warstwa);
            L.circleMarker(e.latlng, { radius: 6, color: kolor, fillColor: kolor, fillOpacity: 1, interactive: false }).addTo(warstwa);
            L.polyline([e.latlng, [w.lat, w.lng]], { color: kolor, dashArray: "5 5", interactive: false }).addTo(warstwa);
            mapa.fitBounds(warstwa.getBounds(), { padding: [40, 40], maxZoom: 15 });
            wynikEl.textContent = `${w.ocena === "trafione" ? "✓ Trafione" : w.ocena === "blisko" ? "≈ Blisko" : "✗ Pudło"} — ${odleglosc(w.odleglosc_m)} od miejsca. Odpowiedź: ${w.odpowiedz}`;
            wynikEl.className = `quiz-mapa__wynik quiz-mapa__wynik--${w.ocena === "pudło" ? "pudlo" : w.ocena}`;
            dalej.hidden = false;
            dalej.focus();
        } catch (err) {
            czeka = true;
            document.getElementById("blad-mapy").textContent = err.message;
            document.getElementById("blad-mapy").hidden = false;
        }
    });

    dalej.addEventListener("click", () => {
        nr += 1;
        pokazPytanie();
    });

    fetch(URL_PYTANIA)
        .then((odp) => odp.json())
        .then((lista) => {
            pytania = lista;
            if (!pytania.length) {
                pytanieEl.textContent = "Brak fiszek z miejscem — dodaj je na stronie „Fiszki z mapą”.";
                return;
            }
            pokazPytanie();
        })
        .catch(() => {
            pytanieEl.textContent = "Nie udało się wczytać pytań.";
        });
})();
