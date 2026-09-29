// Moduł atlas: wybór wskaźnika BDL, kartogram gmin, statystyki, ranking, opis.
// Wszystkie liczby przychodzą z serwera (dane GUS + statystyki liczone w
// Pythonie); tutaj tylko je formatujemy i rysujemy.
(function () {
    "use strict";

    // Skala sekwencyjna 5 klas: od jasnego do ciemnego niebieskiego.
    const KOLORY_KLAS = ["#d6e8ff", "#9ecbff", "#5aa7ff", "#1f7ae0", "#0b4fa8"];
    const KOLOR_BRAK = "#c7c7cc";
    const OSTATNI_ROK = new Date().getFullYear() - 1;
    const PIERWSZY_ROK = 2002;

    const formularz = document.getElementById("formularz-atlasu");
    const poleSzukaj = document.getElementById("pole-szukaj");
    const podpowiedzi = document.getElementById("podpowiedzi");
    const poleWoj = document.getElementById("pole-woj");
    const poleRok = document.getElementById("pole-rok");
    const przyciskPokaz = document.getElementById("przycisk-pokaz");
    const wybranyWskaznikEl = document.getElementById("wybrany-wskaznik");
    const komunikat = document.getElementById("komunikat-atlasu");
    const wynikiEl = document.getElementById("wyniki");
    const komunikatMapy = document.getElementById("komunikat-mapy");
    const legendaEl = document.getElementById("legenda");
    const listaRankingu = document.getElementById("lista-rankingu");
    const filtrRankingu = document.getElementById("filtr-rankingu");
    const przyciskOpis = document.getElementById("przycisk-opis");
    const opisEl = document.getElementById("opis");
    const faktyEl = document.getElementById("fakty-opisu");
    const listaFaktow = document.getElementById("lista-faktow");

    const formatLiczby = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 });

    let wybranaZmienna = null; // {id, nazwa, jednostka}
    let biezaceDane = null;
    let warstwaGmin = null;
    let numerZapytania = 0; // chroni przed nadpisaniem wyniku starszą odpowiedzią
    const wierszePoTeryt = new Map();
    const warstwyPoTeryt = new Map();

    // ---------- mapa ----------

    const mapa = L.map("mapa-atlasu", { zoomSnap: 0.25 }).setView([52.1, 19.4], 6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap, granice: PRG GUGiK, dane: GUS BDL",
        maxZoom: 18,
        opacity: 0.5,
    }).addTo(mapa);

    // ---------- pomocnicze ----------

    async function pobierzJson(url, opcje) {
        const odpowiedz = await fetch(url, opcje);
        let dane = null;
        try {
            dane = await odpowiedz.json();
        } catch (e) {
            throw new Error(`Serwer zwrócił błąd ${odpowiedz.status}`);
        }
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        return dane;
    }

    function pokazKomunikat(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    function zJednostka(liczba) {
        const jednostka = biezaceDane && biezaceDane.zmienna.jednostka;
        return formatLiczby.format(liczba) + (jednostka ? ` ${jednostka}` : "");
    }

    function klasa(wartosc) {
        const progi = biezaceDane.progi_klas;
        let i = 0;
        while (i < progi.length && wartosc > progi[i]) i += 1;
        // Przy mniejszej liczbie klas rozciągamy kolory na całą skalę.
        const liczbaKlas = progi.length + 1;
        return liczbaKlas === 1 ? KOLORY_KLAS.length - 1 : Math.round((i * (KOLORY_KLAS.length - 1)) / (liczbaKlas - 1));
    }

    // ---------- panel wyboru ----------

    for (let rok = OSTATNI_ROK; rok >= PIERWSZY_ROK; rok -= 1) {
        poleRok.add(new Option(String(rok), String(rok)));
    }
    poleRok.value = String(OSTATNI_ROK - 1); // najnowszy rok bywa jeszcze niepełny

    function aktualizujPrzycisk() {
        przyciskPokaz.disabled = !(wybranaZmienna && poleWoj.value);
    }

    pobierzJson(URL_WOJEWODZTWA)
        .then((lista) => {
            poleWoj.replaceChildren(new Option("Wybierz…", ""));
            for (const woj of lista) {
                const opcja = new Option(woj.nazwa, woj.bdl_id);
                opcja.dataset.teryt = woj.teryt;
                poleWoj.add(opcja);
            }
        })
        .catch((e) => {
            poleWoj.replaceChildren(new Option("Niedostępne", ""));
            pokazKomunikat(`Nie udało się pobrać listy województw z BDL: ${e.message}`);
        });

    let opoznienieSzukania = null;
    poleSzukaj.addEventListener("input", () => {
        clearTimeout(opoznienieSzukania);
        const fraza = poleSzukaj.value.trim();
        if (fraza.length < 3) {
            podpowiedzi.hidden = true;
            return;
        }
        opoznienieSzukania = setTimeout(() => szukajZmiennych(fraza), 350);
    });

    async function szukajZmiennych(fraza) {
        podpowiedzi.replaceChildren(elementPodpowiedzi("Szukam…", null));
        podpowiedzi.hidden = false;
        try {
            const zmienne = await pobierzJson(`${URL_ZMIENNE}?q=${encodeURIComponent(fraza)}`);
            podpowiedzi.replaceChildren();
            if (zmienne.length === 0) {
                podpowiedzi.appendChild(elementPodpowiedzi("Brak wskaźników dla gmin o takiej nazwie.", null));
            }
            for (const zmienna of zmienne) {
                podpowiedzi.appendChild(elementPodpowiedzi(zmienna.nazwa, zmienna));
            }
        } catch (e) {
            podpowiedzi.replaceChildren(elementPodpowiedzi(`Błąd: ${e.message}`, null));
        }
    }

    function elementPodpowiedzi(tekst, zmienna) {
        const li = document.createElement("li");
        li.textContent = tekst;
        if (!zmienna) {
            li.className = "podpowiedzi__info";
            return li;
        }
        const jednostka = document.createElement("span");
        jednostka.className = "etykieta";
        jednostka.textContent = zmienna.jednostka || "—";
        li.appendChild(jednostka);
        li.tabIndex = 0;
        const wybierz = () => {
            wybranaZmienna = zmienna;
            wybranyWskaznikEl.textContent = `Wybrany wskaźnik: ${zmienna.nazwa} (id ${zmienna.id})`;
            poleSzukaj.value = zmienna.nazwa;
            podpowiedzi.hidden = true;
            aktualizujPrzycisk();
        };
        li.addEventListener("click", wybierz);
        li.addEventListener("keydown", (e) => e.key === "Enter" && (e.preventDefault(), wybierz()));
        return li;
    }

    document.addEventListener("click", (e) => {
        if (!e.target.closest(".pole-wskaznika")) podpowiedzi.hidden = true;
    });
    poleWoj.addEventListener("change", aktualizujPrzycisk);

    // ---------- pobranie danych ----------

    formularz.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!wybranaZmienna || !poleWoj.value) return;

        const numer = ++numerZapytania;
        const terytWoj = poleWoj.selectedOptions[0].dataset.teryt;
        pokazKomunikat("");
        przyciskPokaz.disabled = true;
        przyciskPokaz.textContent = "Pobieranie…";
        try {
            const parametry = new URLSearchParams({ zmienna: wybranaZmienna.id, rok: poleRok.value, woj: poleWoj.value });
            const dane = await pobierzJson(`${URL_DANE}?${parametry}`);
            if (numer !== numerZapytania) return;
            if (dane.gminy.length === 0) {
                wynikiEl.hidden = true;
                pokazKomunikat(`Brak danych dla gmin w roku ${poleRok.value}. Spróbuj innego roku.`);
                return;
            }
            biezaceDane = dane;
            wynikiEl.hidden = false;
            pokazStatystyki();
            pokazRanking();
            resetujOpis();
            await pokazKartogram(terytWoj, numer);
        } catch (err) {
            pokazKomunikat(err.message);
        } finally {
            przyciskPokaz.textContent = "Pokaż";
            aktualizujPrzycisk();
        }
    });

    function pokazStatystyki() {
        const s = biezaceDane.statystyki;
        document.getElementById("stat-liczba").textContent = s.liczba_gmin;
        const mediana = document.getElementById("stat-mediana");
        const jednostka = document.createElement("span");
        jednostka.className = "kafelek__jednostka";
        jednostka.textContent = biezaceDane.zmienna.jednostka || "";
        mediana.replaceChildren(formatLiczby.format(s.mediana), jednostka);
        document.getElementById("stat-max").textContent = `${s.max.nazwa} · ${zJednostka(s.max.wartosc)}`;
        document.getElementById("stat-min").textContent = `${s.min.nazwa} · ${zJednostka(s.min.wartosc)}`;
    }

    // ---------- ranking (wykres słupkowy) ----------

    function pokazRanking() {
        listaRankingu.replaceChildren();
        wierszePoTeryt.clear();
        const maks = Math.max(...biezaceDane.gminy.map((g) => Math.abs(g.wartosc))) || 1;

        biezaceDane.gminy.forEach((gmina, indeks) => {
            const li = document.createElement("li");
            li.className = "wiersz-rankingu";
            li.dataset.nazwa = gmina.nazwa.toLowerCase();

            const miejsce = document.createElement("span");
            miejsce.className = "wiersz-rankingu__miejsce";
            miejsce.textContent = indeks + 1;

            const nazwa = document.createElement("span");
            nazwa.className = "wiersz-rankingu__nazwa";
            nazwa.textContent = gmina.nazwa;

            const tor = document.createElement("span");
            tor.className = "wiersz-rankingu__tor";
            const slupek = document.createElement("span");
            slupek.className = "wiersz-rankingu__slupek";
            slupek.style.width = `${(Math.abs(gmina.wartosc) / maks) * 100}%`;
            slupek.style.background = KOLORY_KLAS[klasa(gmina.wartosc)];
            tor.appendChild(slupek);

            const wartosc = document.createElement("span");
            wartosc.className = "wiersz-rankingu__wartosc";
            wartosc.textContent = formatLiczby.format(gmina.wartosc);

            li.append(miejsce, nazwa, tor, wartosc);
            li.addEventListener("mouseenter", () => podswietl(gmina.teryt, true));
            li.addEventListener("mouseleave", () => podswietl(gmina.teryt, false));
            li.addEventListener("click", () => przybliz(gmina.teryt));
            listaRankingu.appendChild(li);
            wierszePoTeryt.set(gmina.teryt, li);
        });
        filtrRankingu.value = "";
    }

    filtrRankingu.addEventListener("input", () => {
        const fraza = filtrRankingu.value.trim().toLowerCase();
        for (const li of listaRankingu.children) {
            li.hidden = fraza !== "" && !li.dataset.nazwa.includes(fraza);
        }
    });

    // ---------- kartogram ----------

    async function pokazKartogram(terytWoj, numer) {
        komunikatMapy.hidden = true;
        if (warstwaGmin) mapa.removeLayer(warstwaGmin);
        warstwaGmin = null;
        warstwyPoTeryt.clear();
        pokazLegende();
        setTimeout(() => mapa.invalidateSize(), 0);

        let granice;
        try {
            granice = await pobierzJson(URL_GRANICE.replace("/00", `/${terytWoj}`));
        } catch (e) {
            komunikatMapy.textContent = `Kartogram niedostępny: ${e.message}. Ranking i statystyki obok są kompletne.`;
            komunikatMapy.hidden = false;
            return;
        }
        if (numer !== numerZapytania) return;

        const wartosci = new Map(biezaceDane.gminy.map((g) => [g.teryt, g]));
        warstwaGmin = L.geoJSON(granice, {
            style: (cecha) => {
                const gmina = wartosci.get(cecha.properties.teryt);
                return {
                    color: "#ffffff",
                    weight: 0.8,
                    fillOpacity: 0.85,
                    fillColor: gmina ? KOLORY_KLAS[klasa(gmina.wartosc)] : KOLOR_BRAK,
                };
            },
            onEachFeature: (cecha, warstwa) => {
                const gmina = wartosci.get(cecha.properties.teryt);
                const dymek = document.createElement("div");
                const nazwa = document.createElement("strong");
                nazwa.textContent = cecha.properties.nazwa;
                dymek.append(nazwa, document.createElement("br"), gmina ? zJednostka(gmina.wartosc) : "brak danych");
                warstwa.bindTooltip(dymek, { sticky: true });
                warstwa.on("mouseover", () => podswietl(cecha.properties.teryt, true));
                warstwa.on("mouseout", () => podswietl(cecha.properties.teryt, false));
                warstwa.on("click", () => {
                    const wiersz = wierszePoTeryt.get(cecha.properties.teryt);
                    if (wiersz) wiersz.scrollIntoView({ block: "center", behavior: "smooth" });
                });
                warstwyPoTeryt.set(cecha.properties.teryt, warstwa);
            },
        }).addTo(mapa);
        mapa.fitBounds(warstwaGmin.getBounds(), { padding: [12, 12] });
    }

    function pokazLegende() {
        legendaEl.replaceChildren();
        const progi = biezaceDane.progi_klas;
        const s = biezaceDane.statystyki;
        const granice = [s.min.wartosc, ...progi, s.max.wartosc];
        for (let i = 0; i < granice.length - 1; i += 1) {
            const wiersz = document.createElement("div");
            wiersz.className = "legenda__wiersz";
            const kolor = document.createElement("span");
            kolor.className = "legenda__kolor";
            kolor.style.background = KOLORY_KLAS[klasa(granice[i + 1])];
            wiersz.append(kolor, `${formatLiczby.format(granice[i])} – ${formatLiczby.format(granice[i + 1])}`);
            legendaEl.appendChild(wiersz);
        }
        const tytul = document.createElement("div");
        tytul.className = "legenda__tytul";
        tytul.textContent = biezaceDane.zmienna.jednostka || "wartość";
        legendaEl.prepend(tytul);
    }

    function podswietl(teryt, wlacz) {
        const wiersz = wierszePoTeryt.get(teryt);
        if (wiersz) wiersz.classList.toggle("wiersz-rankingu--aktywny", wlacz);
        const warstwa = warstwyPoTeryt.get(teryt);
        if (warstwa) {
            warstwa.setStyle({ weight: wlacz ? 3 : 0.8, color: wlacz ? "#1d1d1f" : "#ffffff" });
            if (wlacz) warstwa.bringToFront();
        }
    }

    function przybliz(teryt) {
        const warstwa = warstwyPoTeryt.get(teryt);
        if (warstwa) {
            mapa.fitBounds(warstwa.getBounds(), { maxZoom: 11 });
            warstwa.openTooltip();
        }
    }

    // ---------- opis przez Gemini ----------

    function resetujOpis() {
        opisEl.className = "wyciszony";
        opisEl.textContent = "Gemini opisze wynik słowami. Liczby w opisie są sprawdzane: każda musi pochodzić z danych GUS.";
        faktyEl.hidden = true;
    }

    przyciskOpis.addEventListener("click", async () => {
        if (!biezaceDane) return;
        przyciskOpis.disabled = true;
        opisEl.className = "wyciszony";
        opisEl.textContent = "Generowanie opisu…";
        try {
            const odpowiedz = await fetch(URL_OPIS, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ zmienna: biezaceDane.zmienna.id, rok: biezaceDane.rok, woj: biezaceDane.wojewodztwo.bdl_id }),
            });
            const dane = await odpowiedz.json();
            if (dane.fakty) {
                listaFaktow.replaceChildren(...dane.fakty.map((f) => Object.assign(document.createElement("li"), { textContent: f })));
                faktyEl.hidden = false;
            }
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            opisEl.className = "opis-tekst";
            opisEl.textContent = dane.opis;
        } catch (e) {
            opisEl.className = "komunikat komunikat--blad";
            opisEl.textContent = e.message;
        } finally {
            przyciskOpis.disabled = false;
        }
    });
})();
