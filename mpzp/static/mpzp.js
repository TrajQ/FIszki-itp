(function () {
    "use strict";

    const mapa = L.map("mapa").setView([52.4064, 16.9252], 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 19,
    }).addTo(mapa);

    const panelWyniku = document.getElementById("panel-wyniku");
    const przyciskOdswiez = document.getElementById("przycisk-odswiez");

    let warstwaDzialki = null;
    let warstwaWydzielenia = null;

    function wyczyscWarstwy() {
        if (warstwaDzialki) {
            mapa.removeLayer(warstwaDzialki);
            warstwaDzialki = null;
        }
        if (warstwaWydzielenia) {
            mapa.removeLayer(warstwaWydzielenia);
            warstwaWydzielenia = null;
        }
    }

    function pokazBlad(tresc) {
        panelWyniku.innerHTML = "<p class=\"blad\"></p>";
        panelWyniku.querySelector(".blad").textContent = tresc;
    }

    function pokazAtrybuty(atrybuty) {
        panelWyniku.innerHTML = "";
        const tabela = document.createElement("table");
        for (const [klucz, wartosc] of Object.entries(atrybuty)) {
            const wiersz = document.createElement("tr");
            const naglowek = document.createElement("th");
            naglowek.textContent = klucz;
            const komorka = document.createElement("td");
            komorka.textContent = wartosc;
            wiersz.appendChild(naglowek);
            wiersz.appendChild(komorka);
            tabela.appendChild(wiersz);
        }
        panelWyniku.appendChild(tabela);
    }

    mapa.on("click", function (zdarzenie) {
        const lat = zdarzenie.latlng.lat;
        const lon = zdarzenie.latlng.lng;

        wyczyscWarstwy();
        panelWyniku.innerHTML = "<p>Sprawdzam...</p>";

        fetch(`${URL_SPRAWDZ}?lat=${lat}&lon=${lon}`)
            .then((odpowiedz) => odpowiedz.json())
            .then((dane) => {
                if (dane.dzialka) {
                    warstwaDzialki = L.geoJSON(dane.dzialka.geometria, {
                        style: { color: "#3388ff", weight: 2, fillOpacity: 0.1 },
                    }).addTo(mapa);
                }

                if (dane.wydzielenie) {
                    warstwaWydzielenia = L.geoJSON(dane.wydzielenie.geometria, {
                        style: { color: "#2ecc71", weight: 2, fillOpacity: 0.3 },
                    }).addTo(mapa);
                    pokazAtrybuty(dane.wydzielenie.atrybuty);
                } else if (dane.blad) {
                    pokazBlad(dane.blad);
                }
            })
            .catch(() => pokazBlad("Błąd połączenia z serwerem."));
    });

    przyciskOdswiez.addEventListener("click", function () {
        przyciskOdswiez.disabled = true;
        przyciskOdswiez.textContent = "Odświeżanie danych gminy...";

        fetch(URL_ODSWIEZ, { method: "POST" })
            .then((odpowiedz) => odpowiedz.json())
            .then((dane) => {
                if (dane.blad) {
                    pokazBlad(dane.blad);
                }
            })
            .catch(() => pokazBlad("Błąd połączenia z serwerem."))
            .finally(() => {
                przyciskOdswiez.disabled = false;
                przyciskOdswiez.textContent = "Odśwież dane gminy";
            });
    });
})();
