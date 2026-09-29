(function () {
    "use strict";

    const mapa = L.map("mapa").setView([52.4064, 16.9252], 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 19,
    }).addTo(mapa);

    const panelWyniku = document.getElementById("panel-wyniku");
    const przyciskOdswiez = document.getElementById("przycisk-odswiez");
    const formularzSzukaj = document.getElementById("szukaj-dzialki");
    const poleIdDzialki = document.getElementById("pole-id-dzialki");
    const listaHistorii = document.getElementById("historia");

    let warstwaDzialki = null;
    let warstwaWydzielenia = null;
    // Numer ostatniego zapytania: odpowiedź na starsze kliknięcie, która
    // przyszła później, jest ignorowana (inaczej zostawiałaby na mapie
    // wielokąty, których nie da się już usunąć).
    let numerZapytania = 0;

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

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function pokazBlad(tresc, dzialka) {
        panelWyniku.replaceChildren();
        if (dzialka) panelWyniku.appendChild(sekcjaDzialki(dzialka));
        panelWyniku.appendChild(element("p", "komunikat komunikat--blad", tresc));
    }

    function sekcjaDzialki(dzialka) {
        const sekcja = element("div");
        sekcja.append(element("h3", "", "Działka"), element("div", "identyfikator wyciszony", dzialka.id));
        return sekcja;
    }

    // Opis symbolu ze słownika (np. MN/U → dwie pozycje).
    function sekcjaOpisu(opisy) {
        const lista = element("ul", "opis-symbolu");
        for (const { symbol, opis } of opisy) {
            const li = element("li");
            li.append(element("span", "etykieta etykieta--sukces", symbol), element("span", opis ? "" : "wyciszony", opis || "brak w słowniku — sprawdź legendę planu"));
            lista.appendChild(li);
        }
        return lista;
    }

    function pokazWynik(dzialka, wydzielenie) {
        panelWyniku.replaceChildren(sekcjaDzialki(dzialka));

        const przeznaczenie = element("div", "przeznaczenie");
        przeznaczenie.append(
            element("span", "przeznaczenie__symbol", wydzielenie.przeznaczenie || "?"),
            element("span", "wyciszony", "symbol przeznaczenia w planie")
        );
        panelWyniku.appendChild(przeznaczenie);

        if (wydzielenie.opis_przeznaczenia && wydzielenie.opis_przeznaczenia.length) {
            panelWyniku.appendChild(sekcjaOpisu(wydzielenie.opis_przeznaczenia));
            panelWyniku.appendChild(
                element("p", "przypis", "Opis orientacyjny wg rozporządzenia z 2003 r. Rozstrzyga tekst uchwały planu.")
            );
        }

        panelWyniku.appendChild(element("h3", "", "Atrybuty wydzielenia"));
        const tabela = element("table", "tabela");
        for (const [klucz, wartosc] of Object.entries(wydzielenie.atrybuty)) {
            const wiersz = element("tr");
            wiersz.append(element("th", "", klucz), element("td", "", wartosc));
            tabela.appendChild(wiersz);
        }
        panelWyniku.appendChild(tabela);
    }

    // Wspólna obsługa odpowiedzi z /sprawdz i /dzialka.
    function obsluzOdpowiedz(dane, przyblizDoDzialki) {
        wyczyscWarstwy();
        if (dane.dzialka) {
            warstwaDzialki = L.geoJSON(dane.dzialka.geometria, {
                style: { color: "#0071e3", weight: 2, fillOpacity: 0.1 },
            }).addTo(mapa);
            if (przyblizDoDzialki) mapa.fitBounds(warstwaDzialki.getBounds(), { maxZoom: 18, padding: [40, 40] });
        }

        if (dane.wydzielenie) {
            warstwaWydzielenia = L.geoJSON(dane.wydzielenie.geometria, {
                style: { color: "#34c759", weight: 2, fillOpacity: 0.3 },
            }).addTo(mapa);
            if (warstwaDzialki) warstwaDzialki.bringToFront();
            pokazWynik(dane.dzialka, dane.wydzielenie);
        } else if (dane.blad) {
            pokazBlad(dane.blad, dane.dzialka);
        }
        odswiezHistorie();
    }

    function zapytaj(url, przyblizDoDzialki) {
        const numer = ++numerZapytania;
        wyczyscWarstwy();
        panelWyniku.innerHTML = "<p class=\"pusty-stan\">Sprawdzam…</p>";
        return fetch(url)
            .then((odpowiedz) => odpowiedz.json())
            .then((dane) => {
                if (numer === numerZapytania) obsluzOdpowiedz(dane, przyblizDoDzialki);
                else odswiezHistorie(); // starsza odpowiedź: tylko historia
            })
            .catch(() => {
                if (numer === numerZapytania) pokazBlad("Błąd połączenia z serwerem.");
            });
    }

    function sprawdzPunkt(lat, lon, przyblizDoDzialki) {
        return zapytaj(`${URL_SPRAWDZ}?lat=${lat}&lon=${lon}`, przyblizDoDzialki);
    }

    mapa.on("click", (zdarzenie) => sprawdzPunkt(zdarzenie.latlng.lat, zdarzenie.latlng.lng, false));

    formularzSzukaj.addEventListener("submit", (zdarzenie) => {
        zdarzenie.preventDefault();
        const id = poleIdDzialki.value.trim();
        if (id) zapytaj(`${URL_DZIALKA}?id=${encodeURIComponent(id)}`, true);
    });

    // ---------- historia ----------

    function odswiezHistorie() {
        fetch(URL_HISTORIA)
            .then((odpowiedz) => odpowiedz.json())
            .then((wpisy) => {
                listaHistorii.replaceChildren();
                if (wpisy.length === 0) {
                    listaHistorii.appendChild(element("li", "wyciszony", "Jeszcze nic nie sprawdzono."));
                }
                for (const wpis of wpisy) {
                    const li = element("li");
                    const przycisk = element("button", "wpis-historii");
                    przycisk.type = "button";
                    przycisk.append(
                        element("span", "identyfikator", wpis.dzialka_id),
                        element("span", wpis.przeznaczenie ? "etykieta etykieta--sukces" : "etykieta", wpis.przeznaczenie || "bez planu")
                    );
                    przycisk.addEventListener("click", () => sprawdzPunkt(wpis.lat, wpis.lon, true));
                    li.appendChild(przycisk);
                    listaHistorii.appendChild(li);
                }
            })
            .catch(() => {});
    }

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

    odswiezHistorie();
})();
