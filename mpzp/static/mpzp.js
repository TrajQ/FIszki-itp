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

    function pokazBlad(tresc, dzialka) {
        panelWyniku.replaceChildren();
        if (dzialka) panelWyniku.appendChild(sekcjaDzialki(dzialka));
        const komunikat = document.createElement("p");
        komunikat.className = "komunikat komunikat--blad";
        komunikat.textContent = tresc;
        panelWyniku.appendChild(komunikat);
    }

    function sekcjaDzialki(dzialka) {
        const sekcja = document.createElement("div");
        const tytul = document.createElement("h3");
        tytul.textContent = "Działka";
        const id = document.createElement("div");
        id.className = "identyfikator wyciszony";
        id.textContent = dzialka.id;
        sekcja.append(tytul, id);
        return sekcja;
    }

    function pokazWynik(dzialka, wydzielenie) {
        panelWyniku.replaceChildren(sekcjaDzialki(dzialka));

        const przeznaczenie = document.createElement("div");
        przeznaczenie.className = "przeznaczenie";
        const symbol = document.createElement("span");
        symbol.className = "przeznaczenie__symbol";
        symbol.textContent = wydzielenie.przeznaczenie || "?";
        const opis = document.createElement("span");
        opis.className = "wyciszony";
        opis.textContent = "symbol przeznaczenia w planie";
        przeznaczenie.append(symbol, opis);
        panelWyniku.appendChild(przeznaczenie);

        const tytul = document.createElement("h3");
        tytul.textContent = "Atrybuty wydzielenia";
        panelWyniku.appendChild(tytul);

        const tabela = document.createElement("table");
        tabela.className = "tabela";
        for (const [klucz, wartosc] of Object.entries(wydzielenie.atrybuty)) {
            const wiersz = document.createElement("tr");
            const naglowek = document.createElement("th");
            naglowek.textContent = klucz;
            const komorka = document.createElement("td");
            komorka.textContent = wartosc;
            wiersz.append(naglowek, komorka);
            tabela.appendChild(wiersz);
        }
        panelWyniku.appendChild(tabela);
    }

    mapa.on("click", function (zdarzenie) {
        const lat = zdarzenie.latlng.lat;
        const lon = zdarzenie.latlng.lng;

        wyczyscWarstwy();
        panelWyniku.innerHTML = "<p class=\"pusty-stan\">Sprawdzam…</p>";

        fetch(`${URL_SPRAWDZ}?lat=${lat}&lon=${lon}`)
            .then((odpowiedz) => odpowiedz.json())
            .then((dane) => {
                if (dane.dzialka) {
                    warstwaDzialki = L.geoJSON(dane.dzialka.geometria, {
                        style: { color: "#0071e3", weight: 2, fillOpacity: 0.1 },
                    }).addTo(mapa);
                }

                if (dane.wydzielenie) {
                    warstwaWydzielenia = L.geoJSON(dane.wydzielenie.geometria, {
                        style: { color: "#34c759", weight: 2, fillOpacity: 0.3 },
                    }).addTo(mapa);
                    pokazWynik(dane.dzialka, dane.wydzielenie);
                } else if (dane.blad) {
                    pokazBlad(dane.blad, dane.dzialka);
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
