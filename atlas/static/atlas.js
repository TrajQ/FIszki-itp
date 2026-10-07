// Moduł atlas: wybór wskaźnika BDL, kartogram gmin, statystyki, ranking, opis.
// Wszystkie liczby przychodzą z serwera (dane GUS + statystyki liczone w
// Pythonie); tutaj tylko je formatujemy i rysujemy.
//
// Dwa tryby: „wartość” (rok badany) i „zmiana” (względem roku bazowego,
// dostępny, gdy wybrano porównanie).
(function () {
    "use strict";

    // Wartość: skala sekwencyjna 5 klas, od jasnego do ciemnego niebieskiego.
    // 7 kolorów — przy mniejszej liczbie klas brane równomiernie z całej skali.
    const KOLORY_KLAS = ["#e3efff", "#b9d8ff", "#86bbff", "#4f97f5", "#1f73de", "#0b53ab", "#06336e"];
    // Zmiana: skala rozbieżna — spadek (pomarańcz), bez zmian (szary), wzrost (niebieski).
    const KOLORY_ZMIANY = ["#c2410c", "#fb923c", "#d1d1d6", "#60a5fa", "#1d4ed8"];
    const KOLOR_BRAK = "#c7c7cc";
    const OSTATNI_ROK = new Date().getFullYear() - 1;
    const PIERWSZY_ROK = 2002;

    const formularz = document.getElementById("formularz-atlasu");
    const poleSzukaj = document.getElementById("pole-szukaj");
    const podpowiedzi = document.getElementById("podpowiedzi");
    const poleWoj = document.getElementById("pole-woj");
    const poleRok = document.getElementById("pole-rok");
    const poleRokBazowy = document.getElementById("pole-rok-bazowy");
    const przyciskPokaz = document.getElementById("przycisk-pokaz");
    const wybranyWskaznikEl = document.getElementById("wybrany-wskaznik");
    const komunikat = document.getElementById("komunikat-atlasu");
    const wynikiEl = document.getElementById("wyniki");
    const przelacznik = document.getElementById("przelacznik-trybu");
    const linkEksport = document.getElementById("link-eksport");
    const kafelkiEl = document.getElementById("kafelki");
    const komunikatMapy = document.getElementById("komunikat-mapy");
    const legendaEl = document.getElementById("legenda");
    const listaRankingu = document.getElementById("lista-rankingu");
    const filtrRankingu = document.getElementById("filtr-rankingu");
    const przyciskOpis = document.getElementById("przycisk-opis");
    const opisEl = document.getElementById("opis");
    const faktyEl = document.getElementById("fakty-opisu");
    const listaFaktow = document.getElementById("lista-faktow");
    const profilEl = document.getElementById("profil-gminy");
    const profilNazwa = document.getElementById("profil-nazwa");
    const profilMiejsce = document.getElementById("profil-miejsce");
    const profilLiczby = document.getElementById("profil-liczby");
    const profilWykres = document.getElementById("profil-wykres");
    const profilStatus = document.getElementById("profil-status");
    const profilTabelaWrap = document.getElementById("profil-tabela-wrap");
    const profilTabela = document.getElementById("profil-tabela");
    let numerProfilu = 0;

    const formatLiczby = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 2 });
    const formatProcentu = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1, signDisplay: "exceptZero" });

    let wybranaZmienna = null; // {id, nazwa, jednostka}
    let mianownik = null; // {id, nazwa, jednostka} — wskaźnik względny (ETAP 29)
    const poleMianownik = document.getElementById("pole-mianownik");
    const podpowiedziMianownik = document.getElementById("podpowiedzi-mianownik");
    const poleMnoznik = document.getElementById("pole-mnoznik");
    const wyczyscMianownik = document.getElementById("wyczysc-mianownik");
    let biezaceDane = null;
    let tryb = "wartosc";
    let granice = null; // GeoJSON gmin bieżącego województwa
    let warstwaGmin = null;
    let numerZapytania = 0; // chroni przed nadpisaniem wyniku starszą odpowiedzią
    const wierszePoTeryt = new Map();
    const warstwyPoTeryt = new Map();

    // ---------- mapa ----------

    // Bez kafelków OSM (ETAP 34): białe tło, a pod kartogramem szare
    // województwa z PRG — wokół wybranego widać sąsiednie. Gdy PRG nie
    // odpowie, zostaje samo białe tło (mapa działa dalej).
    const mapa = L.map("mapa-atlasu", { zoomSnap: 0.25, minZoom: 5, maxZoom: 13 }).setView([52.1, 19.4], 6);
    mapa.attributionControl.addAttribution("granice: PRG GUGiK, dane: GUS BDL");
    mapa.createPane("tlo").style.zIndex = 250; // pod warstwą gmin (400)
    let warstwaTla = null;
    let terytNaMapie = null; // województwo aktualnie pokazane kartogramem
    const etykietyWojewodztw = new Map(); // teryt → warstwa z etykietą

    function rysujTlo(kolekcja) {
        warstwaTla = L.geoJSON(kolekcja, {
            pane: "tlo",
            interactive: false,
            style: { className: "wojewodztwo-tla", weight: 1 },
            onEachFeature: (cecha, warstwa) => {
                // węzeł z textContent: Leaflet wstawia napis jako HTML, a nazwa przychodzi z pliku granic
                warstwa.bindTooltip(element("span", "", cecha.properties.nazwa), {
                    permanent: true,
                    direction: "center",
                    className: "etykieta-wojewodztwa",
                });
                etykietyWojewodztw.set(cecha.properties.teryt, warstwa);
            },
        }).addTo(mapa);
        // Tło bywa gotowe dopiero po kartogramie (pierwsze pobranie z PRG
        // trwa) — wtedy od razu chowamy nazwę pokazanego województwa.
        if (terytNaMapie) pokazEtykietyOprocz(terytNaMapie);
    }

    // Nazwa wybranego województwa zasłaniałaby kartogram — chowamy tylko ją.
    function pokazEtykietyOprocz(terytWybranego) {
        for (const [teryt, warstwa] of etykietyWojewodztw) {
            if (teryt === terytWybranego) warstwa.closeTooltip();
            else warstwa.openTooltip();
        }
    }

    pobierzJson(URL_TLO)
        .then(rysujTlo)
        .catch(() => {}); // bez tła mapa jest po prostu biała

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

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function pokazKomunikat(tresc) {
        komunikat.textContent = tresc;
        komunikat.hidden = !tresc;
    }

    function zJednostka(liczba) {
        const jednostka = biezaceDane && biezaceDane.zmienna.jednostka;
        return formatLiczby.format(liczba) + (jednostka ? ` ${jednostka}` : "");
    }

    function procent(liczba) {
        return liczba === null ? "—" : `${formatProcentu.format(liczba)}%`;
    }

    // Numer klasy według progów (klasa i obejmuje wartości ≤ progi[i]).
    function numerKlasy(wartosc, progi) {
        let i = 0;
        while (i < progi.length && wartosc > progi[i]) i += 1;
        return i;
    }

    // Klastry LISA (ETAP 41): kolory jak w GeoDa.
    const KOLORY_LISA = { HH: "#d7191c", LL: "#2c7bb6", HL: "#fdae61", LH: "#abd9e9", ns: "#e5e5ea" };
    let wynikMorana = null; // odpowiedź /autokorelacja dla bieżących danych
    let lisaPoTeryt = new Map();
    // Gorące punkty Gi* (ETAP 152): czerwone — gorące, niebieskie — zimne; liczy serwer
    const KOLORY_GI = { H99: "#b2182b", H95: "#ef8a62", H90: "#fddbc7", ns: "#e5e5ea", C90: "#d1e5f0", C95: "#67a9cf", C99: "#2166ac" };
    const KOLEJNOSC_GI = ["H99", "H95", "H90", "ns", "C90", "C95", "C99"];
    let giPoTeryt = new Map();
    // Iloraz lokalizacji (ETAP 153): stałe klasy z serwera, kolory od niebieskiego do czerwonego
    const KOLORY_LQ = ["#2166ac", "#92c5de", "#e5e5ea", "#f4a582", "#b2182b"];
    let lqPoTeryt = new Map();

    // Kolor dla gminy w bieżącym trybie.
    function kolorGminy(gmina) {
        if (!gmina) return KOLOR_BRAK;
        if (tryb === "lisa") {
            const lisa = lisaPoTeryt.get(gmina.teryt);
            return lisa ? KOLORY_LISA[lisa.kategoria] : KOLOR_BRAK;
        }
        if (tryb === "gi") {
            const gi = giPoTeryt.get(gmina.teryt);
            return gi ? KOLORY_GI[gi.kategoria] : KOLOR_BRAK;
        }
        if (tryb === "lq") {
            const lq = lqPoTeryt.get(gmina.teryt);
            return lq ? KOLORY_LQ[lq.klasa] : KOLOR_BRAK;
        }
        if (tryb === "zmiana") {
            if (gmina.zmiana_proc === null || gmina.zmiana_proc === undefined) return KOLOR_BRAK;
            return KOLORY_ZMIANY[numerKlasy(gmina.zmiana_proc, biezaceDane.porownanie.progi_zmiany_proc)];
        }
        const progi = biezaceDane.klasyfikacja.progi;
        const liczbaKlas = progi.length + 1;
        const i = numerKlasy(gmina.wartosc, progi);
        // Przy mniejszej liczbie klas rozciągamy kolory na całą skalę.
        return KOLORY_KLAS[liczbaKlas === 1 ? KOLORY_KLAS.length - 1 : Math.round((i * (KOLORY_KLAS.length - 1)) / (liczbaKlas - 1))];
    }

    // Gminy do pokazania w bieżącym trybie, już posortowane przez serwer.
    function gminyTrybu() {
        return tryb === "zmiana" ? biezaceDane.porownanie.gminy : biezaceDane.gminy;
    }

    // ---------- panel wyboru ----------

    for (let rok = OSTATNI_ROK; rok >= PIERWSZY_ROK; rok -= 1) {
        poleRok.add(new Option(String(rok), String(rok)));
        poleRokBazowy.add(new Option(String(rok), String(rok)));
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

    // Szybki wybór popularnych wskaźników: wpisuje frazę i od razu szuka.
    for (const przycisk of document.querySelectorAll(".szybki-wybor__fraza")) {
        przycisk.addEventListener("click", () => {
            poleSzukaj.value = przycisk.dataset.fraza;
            clearTimeout(opoznienieSzukania);
            poleSzukaj.focus();
            szukajZmiennych(przycisk.dataset.fraza);
        });
    }

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
        const li = element("li", zmienna ? "" : "podpowiedzi__info", tekst);
        if (!zmienna) return li;
        li.appendChild(element("span", "etykieta", zmienna.jednostka || "—"));
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
        if (!e.target.closest(".pole-wskaznika")) {
            podpowiedzi.hidden = true;
            podpowiedziMianownik.hidden = true;
        }
    });

    // Wyszukiwarka mianownika — ta sama lista wskaźników BDL.
    let opoznienieMianownika = null;
    poleMianownik.addEventListener("input", () => {
        clearTimeout(opoznienieMianownika);
        // Edycja tekstu ręcznie = rezygnacja z wybranego mianownika
        // (inaczej mapa dalej dzieliłaby przez niewidoczny już wskaźnik).
        if (mianownik && poleMianownik.value !== mianownik.nazwa) {
            mianownik = null;
            wyczyscMianownik.hidden = true;
        }
        const fraza = poleMianownik.value.trim();
        if (fraza.length < 3) {
            podpowiedziMianownik.hidden = true;
            return;
        }
        opoznienieMianownika = setTimeout(async () => {
            podpowiedziMianownik.replaceChildren(element("li", "podpowiedzi__info", "Szukam…"));
            podpowiedziMianownik.hidden = false;
            try {
                const zmienne = await pobierzJson(`${URL_ZMIENNE}?q=${encodeURIComponent(fraza)}`);
                podpowiedziMianownik.replaceChildren();
                for (const z of zmienne) {
                    const li = element("li", "", z.nazwa);
                    li.appendChild(element("span", "etykieta", z.jednostka || "—"));
                    li.addEventListener("click", () => {
                        mianownik = z;
                        poleMianownik.value = z.nazwa;
                        podpowiedziMianownik.hidden = true;
                        wyczyscMianownik.hidden = false;
                    });
                    podpowiedziMianownik.appendChild(li);
                }
                if (!zmienne.length) podpowiedziMianownik.appendChild(element("li", "podpowiedzi__info", "Brak wskaźników o takiej nazwie."));
            } catch (err) {
                podpowiedziMianownik.replaceChildren(element("li", "podpowiedzi__info", `Błąd: ${err.message}`));
            }
        }, 350);
    });
    wyczyscMianownik.addEventListener("click", () => {
        mianownik = null;
        poleMianownik.value = "";
        wyczyscMianownik.hidden = true;
    });
    poleWoj.addEventListener("change", aktualizujPrzycisk);

    // ---------- pobranie danych ----------

    formularz.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!wybranaZmienna || !poleWoj.value) return;
        if (poleRokBazowy.value && Number(poleRokBazowy.value) >= Number(poleRok.value)) {
            pokazKomunikat("Rok porównania musi być wcześniejszy niż rok badany.");
            return;
        }

        const numer = ++numerZapytania;
        const terytWoj = poleWoj.selectedOptions[0].dataset.teryt;
        pokazKomunikat("");
        przyciskPokaz.disabled = true;
        przyciskPokaz.textContent = "Pobieranie…";
        try {
            const parametry = new URLSearchParams({ zmienna: wybranaZmienna.id, rok: poleRok.value, woj: poleWoj.value });
            const powiaty = document.getElementById("pole-poziom").value === "powiaty"; // ETAP 216
            if (powiaty) parametry.set("poziom", "powiaty");
            if (poleRokBazowy.value) parametry.set("rok_bazowy", poleRokBazowy.value);
            if (mianownik) {
                parametry.set("mianownik", mianownik.id);
                parametry.set("mnoznik", poleMnoznik.value);
            }
            const parametryDanych = new URLSearchParams(parametry);
            parametry.set("metoda", poleMetoda.value);
            parametry.set("klasy", poleKlasy.value);
            const dane = await pobierzJson(`${URL_DANE}?${parametry}`);
            if (numer !== numerZapytania) return;
            if (dane.gminy.length === 0) {
                wynikiEl.hidden = true;
                pokazKomunikat(`Brak danych dla ${powiaty ? "powiatów" : "gmin"} w roku ${poleRok.value}. Spróbuj innego roku.`);
                return;
            }
            zakonczOdtwarzanie(false); // ETAP 235: nowe dane — odtwarzacz poprzednich znika
            biezaceDane = dane;
            biezaceParametry = parametryDanych;
            ustawJednostki(powiaty);
            resetujMorana();
            numerKlas += 1; // starsze odpowiedzi /klasy dotyczą poprzednich danych
            wybranyWskaznikEl.textContent = `Na mapie: ${dane.zmienna.nazwa} [${dane.zmienna.jednostka || "–"}], ${dane.rok}`;
            linkEksport.href = `${URL_EKSPORT}?${parametry}`;
            document.getElementById("link-ods").href = `${URL_EKSPORT.replace(/eksport\.csv$/, "eksport.ods")}?${parametry}`; // ETAP 188
            document.getElementById("link-geojson").href = `${URL_GEOJSON}?${parametry}`;
            const jestPorownanie = Boolean(dane.porownanie && dane.porownanie.gminy.length);
            if (dane.porownanie && !jestPorownanie) {
                pokazKomunikat(`Brak danych z roku ${dane.porownanie.rok_bazowy} do porównania — pokazuję same wartości.`);
            }
            // ETAP 153: iloraz lokalizacji — tylko dla wskaźnika względnego (z mianownikiem)
            lqPoTeryt = new Map(((dane.lq && dane.lq.gminy) || []).map((g) => [g.teryt, g]));
            przelacznik.hidden = !jestPorownanie && !lqPoTeryt.size;
            przelacznik.querySelector('[data-tryb="zmiana"]').hidden = !jestPorownanie;
            przelacznik.querySelector('[data-tryb="lq"]').hidden = !lqPoTeryt.size;
            ustawTryb(jestPorownanie ? "zmiana" : "wartosc", false);
            wynikiEl.hidden = false;
            profilEl.hidden = true;
            resetujOpis();
            // Dla innych skryptów strony (korelacja.js): nowe dane — od razu,
            // niezależnie od tego, czy granice do kartogramu się wczytają.
            document.dispatchEvent(new CustomEvent("atlas:dane", { detail: dane }));
            await wczytajGranice(terytWoj, numer);
            if (numer !== numerZapytania) return;
            odswiezWidok();
        } catch (err) {
            pokazKomunikat(err.message);
        } finally {
            przyciskPokaz.textContent = "Pokaż";
            aktualizujPrzycisk();
        }
    });

    function ustawTryb(nowy, odswiez = true) {
        tryb = nowy;
        for (const przycisk of przelacznik.querySelectorAll("button")) {
            przycisk.classList.toggle("przelacznik__opcja--aktywna", przycisk.dataset.tryb === nowy);
        }
        if (odswiez) odswiezWidok();
    }

    przelacznik.addEventListener("click", (e) => {
        const przycisk = e.target.closest("button[data-tryb]");
        if (przycisk && przycisk.dataset.tryb !== tryb) ustawTryb(przycisk.dataset.tryb);
    });

    // ---------- metoda klasyfikacji (ETAP 40) ----------
    // Progi liczy serwer (atlas/statystyki.py); zmiana metody albo liczby
    // klas pobiera tylko nowe progi i przerysowuje mapę.

    const poleMetoda = document.getElementById("pole-metoda");
    const poleKlasy = document.getElementById("pole-klasy");
    const gvfEl = document.getElementById("gvf");
    const klasyfikacjaEl = document.getElementById("klasyfikacja");
    let biezaceParametry = null; // parametry danych na mapie (bez metody)
    let numerKlas = 0;

    function pokazGvf() {
        const k = biezaceDane.klasyfikacja;
        gvfEl.textContent = k.gvf === null ? "" : `GVF ${k.gvf.toLocaleString("pl-PL", { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
        klasyfikacjaEl.classList.toggle("klasyfikacja--nieaktywna", tryb !== "wartosc");
        poleMetoda.disabled = poleKlasy.disabled = tryb !== "wartosc";
    }

    async function zmienKlasyfikacje() {
        if (!biezaceDane || !biezaceParametry) return;
        const numer = ++numerKlas;
        const parametry = new URLSearchParams(biezaceParametry);
        parametry.set("metoda", poleMetoda.value);
        parametry.set("klasy", poleKlasy.value);
        try {
            const klasyfikacja = await pobierzJson(`${URL_KLASY}?${parametry}`);
            if (numer !== numerKlas || !biezaceDane) return;
            biezaceDane.klasyfikacja = klasyfikacja;
            odswiezWidok();
        } catch (e) {
            pokazKomunikat(e.message);
        }
    }

    poleMetoda.addEventListener("change", zmienKlasyfikacje);
    poleKlasy.addEventListener("change", zmienKlasyfikacje);

    // ---------- autokorelacja przestrzenna (ETAP 41) ----------
    // Liczy serwer (atlas/autokorelacja.py) — na żądanie, bo permutacje
    // trwają 1–2 s dla dużego województwa.

    const przyciskMoran = document.getElementById("przycisk-moran");
    const statusMorana = document.getElementById("status-morana");
    const wynikMoranaEl = document.getElementById("wynik-morana");
    const liczbyMorana = document.getElementById("liczby-morana");
    const opisMorana = document.getElementById("opis-morana");
    const listaLisa = document.getElementById("lista-lisa");
    const przyciskLisa = przelacznik.querySelector('[data-tryb="lisa"]');
    const przyciskGi = przelacznik.querySelector('[data-tryb="gi"]');
    let numerMorana = 0;

    function liczKategorie() {
        const ile = {};
        for (const l of wynikMorana.lisa) ile[l.kategoria] = (ile[l.kategoria] || 0) + 1;
        return ile;
    }

    function resetujMorana() {
        numerMorana += 1;
        wynikMorana = null;
        lisaPoTeryt = new Map();
        giPoTeryt = new Map();
        wynikMoranaEl.hidden = true;
        statusMorana.hidden = true;
        przyciskLisa.hidden = true;
        przyciskGi.hidden = true;
        przyciskMoran.disabled = false;
        przyciskMoran.textContent = "Policz I Morana";
    }

    przyciskMoran.addEventListener("click", async () => {
        if (!biezaceParametry) return;
        const numer = ++numerMorana;
        przyciskMoran.disabled = true;
        przyciskMoran.textContent = "Liczę…";
        statusMorana.hidden = true;
        try {
            const wynik = await pobierzJson(`${URL_AUTOKORELACJA}?${biezaceParametry}`);
            if (numer !== numerMorana) return;
            wynikMorana = wynik;
            lisaPoTeryt = new Map(wynik.lisa.map((l) => [l.teryt, l]));
            giPoTeryt = new Map(wynik.gi.map((g) => [g.teryt, g]));
            const f3 = (x) => x.toLocaleString("pl-PL", { maximumFractionDigits: 3, minimumFractionDigits: 3 });
            liczbyMorana.replaceChildren(
                liczbaProfilu("I Morana", f3(wynik.moran_i)),
                liczbaProfilu("oczekiwane (losowo)", f3(wynik.oczekiwane_i)),
                liczbaProfilu("p", wynik.p.toLocaleString("pl-PL")),
                liczbaProfilu("z", wynik.z === null ? "—" : wynik.z.toLocaleString("pl-PL", { maximumFractionDigits: 2 }))
            );
            opisMorana.textContent =
                wynik.interpretacja +
                ` Gmin w analizie: ${wynik.liczba_gmin}` +
                (wynik.pominiete ? ` (pominięte bez sąsiadów z danymi: ${wynik.pominiete}).` : ".");
            const ile = liczKategorie();
            listaLisa.replaceChildren();
            for (const kategoria of ["HH", "LL", "HL", "LH"]) {
                const li = element("li");
                const probka = element("span", "legenda__kolor");
                probka.style.background = KOLORY_LISA[kategoria];
                li.append(probka, element("span", "", wynik.kategorie[kategoria]), element("strong", "", `${ile[kategoria] || 0}`));
                listaLisa.appendChild(li);
            }
            wynikMoranaEl.hidden = false;
            przyciskLisa.hidden = false;
            przyciskGi.hidden = false;
            przelacznik.hidden = false;
            przyciskMoran.textContent = "Policzone ✓";
            ustawTryb("lisa");
        } catch (e) {
            if (numer !== numerMorana) return;
            statusMorana.textContent = e.message;
            statusMorana.hidden = false;
            przyciskMoran.disabled = false;
            przyciskMoran.textContent = "Policz I Morana";
        }
    });

    // Link „Mapa do druku” zawsze odpowiada temu, co widać: tryb, metoda, klasy.
    function ustawLinkDruku() {
        if (!biezaceParametry) return;
        const parametry = new URLSearchParams(biezaceParametry);
        parametry.set("tryb", tryb);
        parametry.set("metoda", poleMetoda.value);
        parametry.set("klasy", poleKlasy.value);
        document.getElementById("link-druk").href = `${URL_DRUK}?${parametry}`;
        // ETAP 161: małe mapy w kilku latach — te same parametry wskaźnika, lata domyślnie co 3
        const lata = new URLSearchParams(biezaceParametry);
        lata.set("metoda", poleMetoda.value);
        lata.set("klasy", poleKlasy.value);
        lata.delete("rok_bazowy");
        document.getElementById("link-lata").href = `${URL_DRUK.replace(/druk$/, "lata")}?${lata}`;
        document.getElementById("link-gminy-czas").href = urlGminWCzasie("");
        // ETAP 178: trend w gminach — domyślnie ostatnie 10 lat do roku na mapie
        const trend = new URLSearchParams(biezaceParametry);
        trend.delete("rok_bazowy");
        document.getElementById("link-trend").href = `${URL_DRUK.replace(/druk$/, "trend")}?${trend}`;
    }

    // ETAP 171: kilka gmin na jednym wykresie w czasie — parametry wskaźnika, bez roku bazowego
    function urlGminWCzasie(gminy) {
        const p = new URLSearchParams(biezaceParametry);
        p.delete("rok_bazowy");
        if (gminy) p.set("gminy", gminy);
        return `${URL_DRUK.replace(/druk$/, "gminy-w-czasie")}?${p}`;
    }

    function odswiezWidok() {
        ustawLinkDruku();
        pokazGvf();
        pokazRozklad();
        pokazStatystyki();
        pokazRanking();
        rysujKartogram();
        pokazLegende();
    }

    // ---------- zróżnicowanie i histogram (wartości roku badanego) ----------

    function pokazRozklad() {
        const s = biezaceDane.statystyki;
        const z = s.zroznicowanie || {};
        const miary = document.getElementById("miary");
        miary.replaceChildren();
        const dodaj = (nazwa, wartosc, opis) => {
            if (wartosc === undefined || wartosc === null) return;
            const dt = element("dt", "", nazwa);
            if (opis) dt.title = opis;
            miary.append(dt, element("dd", "", wartosc));
        };
        const jedn = biezaceDane.zmienna.jednostka ? ` ${biezaceDane.zmienna.jednostka}` : "";
        dodaj("Średnia", formatLiczby.format(s.srednia) + jedn);
        dodaj("Mediana", formatLiczby.format(s.mediana) + jedn);
        dodaj("Odchylenie standardowe", formatLiczby.format(z.odchylenie_std) + jedn);
        if (z.wspolczynnik_zmiennosci !== undefined) {
            dodaj("Współczynnik zmienności", `${formatLiczby.format(z.wspolczynnik_zmiennosci)}% — ${z.ocena_zmiennosci}`,
                "odchylenie standardowe / średnia; < 25% słabe, 25–45% przeciętne, 45–100% silne, > 100% bardzo silne");
        }
        if (z.q1 !== undefined) {
            dodaj("Kwartyle Q1 – Q3", `${formatLiczby.format(z.q1)} – ${formatLiczby.format(z.q3)}${jedn}`, "połowa gmin mieści się w tym przedziale");
            dodaj("Rozstęp kwartylowy", formatLiczby.format(z.rozstep_kwartylowy) + jedn);
        }
        if (z.max_do_min !== undefined) dodaj("Maksimum / minimum", `${formatLiczby.format(z.max_do_min)} ×`);
        if (z.gini !== undefined) dodaj("Współczynnik Giniego", formatLiczby.format(z.gini));
        rysujHistogram(s.histogram || [], s.mediana);
    }

    function rysujHistogram(przedzialy, mediana) {
        const NS = "http://www.w3.org/2000/svg";
        const kontener = document.getElementById("histogram");
        kontener.replaceChildren();
        if (!przedzialy.length) return;
        const SZ = 420, WY = 200, M = { g: 12, p: 8, d: 30, l: 30 };
        const maks = Math.max(...przedzialy.map((p) => p.liczba)) || 1;
        const lo = przedzialy[0].od, hi = przedzialy[przedzialy.length - 1].do;
        const x = (v) => M.l + (hi === lo ? 0.5 : (v - lo) / (hi - lo)) * (SZ - M.l - M.p);
        const y = (n) => M.g + (1 - n / maks) * (WY - M.g - M.d);
        const s = document.createElementNS(NS, "svg");
        s.setAttribute("viewBox", `0 0 ${SZ} ${WY}`);
        s.setAttribute("class", "wykres");
        s.setAttribute("role", "img");
        const nowy = (nazwa, atr) => {
            const e = document.createElementNS(NS, nazwa);
            for (const [k, v] of Object.entries(atr)) e.setAttribute(k, v);
            s.appendChild(e);
            return e;
        };
        nowy("title", {}).textContent = "Histogram: liczba gmin w przedziałach wartości";
        for (const n of [0, Math.round(maks / 2), maks]) {
            nowy("line", { x1: M.l, x2: SZ - M.p, y1: y(n), y2: y(n), class: "wykres__siatka" });
            nowy("text", { x: M.l - 6, y: y(n) + 3, class: "wykres__os", "text-anchor": "end" }).textContent = n;
        }
        const dymek = element("div", "wykres__dymek");
        dymek.hidden = true;
        for (const p of przedzialy) {
            // 2 px odstępu między słupkami, zaokrąglone tylko u góry.
            const x0 = x(p.od) + 1, szer = Math.max(1, x(p.do) - x(p.od) - 2);
            const slupek = nowy("rect", {
                x: x0, y: y(p.liczba), width: szer, height: Math.max(0, WY - M.d - y(p.liczba)), rx: 3, class: "histogram__slupek",
            });
            slupek.addEventListener("mouseenter", () => {
                const r = s.getBoundingClientRect();
                dymek.textContent = `${formatLiczby.format(p.od)} – ${formatLiczby.format(p.do)}: ${p.liczba} gmin`;
                dymek.hidden = false;
                dymek.style.left = `${((x0 + szer / 2) / SZ) * r.width}px`;
                dymek.style.top = `${(y(p.liczba) / WY) * r.height - 34}px`;
            });
            slupek.addEventListener("mouseleave", () => (dymek.hidden = true));
        }
        const fmt = new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 });
        nowy("text", { x: M.l, y: WY - 10, class: "wykres__os" }).textContent = fmt.format(lo);
        nowy("text", { x: SZ - M.p, y: WY - 10, class: "wykres__os", "text-anchor": "end" }).textContent = fmt.format(hi);
        if (mediana !== undefined) {
            nowy("line", { x1: x(mediana), x2: x(mediana), y1: M.g, y2: WY - M.d, class: "wykres__odniesienie" });
            nowy("text", { x: x(mediana) + 4, y: M.g + 8, class: "wykres__os" }).textContent = "mediana";
        }
        kontener.append(s, dymek);
    }

    // ---------- kafelki ----------

    function kafelek(etykieta, wartosc, { szeroki = false, jednostka = "", klasaWartosci = "" } = {}) {
        const div = element("div", `karta kafelek${szeroki ? " kafelek--szeroki" : ""}`);
        const w = element("span", `kafelek__wartosc${szeroki ? " kafelek__wartosc--mala" : ""} ${klasaWartosci}`, wartosc);
        if (jednostka) w.appendChild(element("span", "kafelek__jednostka", jednostka));
        div.append(element("span", "kafelek__etykieta", etykieta), w);
        return div;
    }

    function pokazStatystyki() {
        kafelkiEl.replaceChildren();
        if (tryb === "zmiana") {
            const p = biezaceDane.porownanie;
            const s = p.statystyki;
            kafelkiEl.append(
                kafelek("Wzrost", String(s.wzrosty ?? 0), { jednostka: "gmin", klasaWartosci: "wartosc-plus" }),
                kafelek("Spadek", String(s.spadki ?? 0), { jednostka: "gmin", klasaWartosci: "wartosc-minus" })
            );
            if (s.mediana_zmiany_proc !== undefined) {
                const opisZmiany = (g, brak) => (g ? `${g.nazwa} · ${procent(g.zmiana_proc)}` : brak);
                kafelkiEl.append(
                    kafelek(`Mediana zmiany ${p.rok_bazowy}→${biezaceDane.rok}`, procent(s.mediana_zmiany_proc), { szeroki: true }),
                    kafelek("Największy wzrost", opisZmiany(s.najwiekszy_wzrost, "żadna gmina nie urosła"), { szeroki: true }),
                    kafelek("Największy spadek", opisZmiany(s.najwiekszy_spadek, "żadna gmina nie spadła"), { szeroki: true })
                );
            }
            return;
        }
        const s = biezaceDane.statystyki;
        kafelkiEl.append(
            kafelek("Gmin z danymi", String(s.liczba_gmin)),
            kafelek("Mediana", formatLiczby.format(s.mediana), { jednostka: biezaceDane.zmienna.jednostka }),
            kafelek("Najwyżej", `${s.max.nazwa} · ${zJednostka(s.max.wartosc)}`, { szeroki: true }),
            kafelek("Najniżej", `${s.min.nazwa} · ${zJednostka(s.min.wartosc)}`, { szeroki: true })
        );
    }

    // ---------- ranking (wykres słupkowy) ----------

    function pokazRanking() {
        listaRankingu.replaceChildren();
        wierszePoTeryt.clear();
        const gminy = gminyTrybu();
        const miara = (g) => Math.abs(tryb === "zmiana" ? g.zmiana_proc ?? 0 : g.wartosc);
        const maks = Math.max(...gminy.map(miara)) || 1;

        gminy.forEach((gmina, indeks) => {
            const li = element("li", "wiersz-rankingu");
            li.dataset.nazwa = gmina.nazwa.toLowerCase();

            const tor = element("span", "wiersz-rankingu__tor");
            const slupek = element("span", "wiersz-rankingu__slupek");
            slupek.style.width = `${(miara(gmina) / maks) * 100}%`;
            slupek.style.background = kolorGminy(gmina);
            tor.appendChild(slupek);

            let tekstWartosci = formatLiczby.format(gmina.wartosc);
            let klasa = "";
            if (tryb === "zmiana") {
                tekstWartosci = procent(gmina.zmiana_proc);
                klasa = gmina.zmiana > 0 ? " wartosc-plus" : gmina.zmiana < 0 ? " wartosc-minus" : "";
                li.title = `${formatLiczby.format(gmina.wartosc_bazowa)} → ${formatLiczby.format(gmina.wartosc)}`;
            }

            li.append(
                element("span", "wiersz-rankingu__miejsce", String(indeks + 1)),
                element("span", "wiersz-rankingu__nazwa", gmina.nazwa),
                tor,
                element("span", `wiersz-rankingu__wartosc${klasa}`, tekstWartosci)
            );
            li.addEventListener("mouseenter", () => podswietl(gmina.teryt, true));
            li.addEventListener("mouseleave", () => podswietl(gmina.teryt, false));
            li.addEventListener("click", () => {
                przybliz(gmina.teryt);
                pokazProfil(gmina.teryt);
            });
            listaRankingu.appendChild(li);
            wierszePoTeryt.set(gmina.teryt, li);
        });
        filtrujRanking();
    }

    function filtrujRanking() {
        const fraza = filtrRankingu.value.trim().toLowerCase();
        for (const li of listaRankingu.children) {
            li.hidden = fraza !== "" && !li.dataset.nazwa.includes(fraza);
        }
    }

    filtrRankingu.addEventListener("input", filtrujRanking);

    // ---------- kartogram ----------

    async function wczytajGranice(terytWoj, numer) {
        komunikatMapy.hidden = true;
        granice = null;
        try {
            const url = biezaceDane && biezaceDane.poziom === "powiaty" ? URL_GRANICE_POWIATOW : URL_GRANICE; // ETAP 216
            const wynik = await pobierzJson(url.replace("/00", `/${terytWoj}`));
            if (numer === numerZapytania) granice = wynik;
        } catch (e) {
            komunikatMapy.textContent = `Kartogram niedostępny: ${e.message}. Ranking i statystyki obok są kompletne.`;
            komunikatMapy.hidden = false;
        }
    }

    function rysujKartogram() {
        if (warstwaGmin) mapa.removeLayer(warstwaGmin);
        warstwaGmin = null;
        warstwyPoTeryt.clear();
        // Kontener mapy był ukryty przy pierwszym wczytaniu — bez tego
        // Leaflet liczy przybliżenie dla mapy o rozmiarze 0 × 0.
        mapa.invalidateSize();
        if (!granice) return;

        const poTeryt = new Map(gminyTrybu().map((g) => [g.teryt, g]));
        warstwaGmin = L.geoJSON(granice, {
            style: (cecha) => ({
                color: "#ffffff",
                weight: 0.8,
                fillOpacity: 0.85,
                fillColor: kolorGminy(poTeryt.get(cecha.properties.teryt)),
            }),
            onEachFeature: (cecha, warstwa) => {
                const gmina = poTeryt.get(cecha.properties.teryt);
                let tresc = "brak danych";
                if (gmina) {
                    tresc =
                        tryb === "zmiana"
                            ? `${procent(gmina.zmiana_proc)} (${formatLiczby.format(gmina.wartosc_bazowa)} → ${formatLiczby.format(gmina.wartosc)})`
                            : zJednostka(gmina.wartosc);
                    const lisa = lisaPoTeryt.get(gmina.teryt);
                    if (tryb === "lisa") {
                        tresc += lisa ? ` · ${wynikMorana.kategorie[lisa.kategoria]} (p = ${formatLiczby.format(lisa.p)})` : " · bez sąsiadów z danymi";
                    }
                    if (tryb === "lq") {
                        const lq = lqPoTeryt.get(gmina.teryt);
                        tresc += lq ? ` · iloraz lokalizacji ${formatLiczby.format(lq.lq)}` : " · brak mianownika";
                    }
                    if (tryb === "gi") {
                        const gi = giPoTeryt.get(gmina.teryt);
                        tresc += gi ? ` · ${wynikMorana.kategorie_gi[gi.kategoria]} (z = ${formatLiczby.format(gi.z)})` : " · bez sąsiadów z danymi";
                    }
                }
                const dymek = element("div");
                dymek.append(element("strong", "", cecha.properties.nazwa), element("br"), tresc);
                warstwa.bindTooltip(dymek, { sticky: true });
                warstwa.on("mouseover", () => podswietl(cecha.properties.teryt, true));
                warstwa.on("mouseout", () => podswietl(cecha.properties.teryt, false));
                warstwa.on("click", () => {
                    const wiersz = wierszePoTeryt.get(cecha.properties.teryt);
                    if (wiersz) wiersz.scrollIntoView({ block: "center", behavior: "smooth" });
                    pokazProfil(cecha.properties.teryt);
                });
                warstwyPoTeryt.set(cecha.properties.teryt, warstwa);
            },
        }).addTo(mapa);
        mapa.fitBounds(warstwaGmin.getBounds(), { padding: [12, 12] });
        terytNaMapie = biezaceDane.wojewodztwo.teryt;
        if (warstwaTla) pokazEtykietyOprocz(terytNaMapie);
    }

    function wierszLegendy(kolor, opis) {
        const wiersz = element("div", "legenda__wiersz");
        const probka = element("span", "legenda__kolor");
        probka.style.background = kolor;
        wiersz.append(probka, opis);
        return wiersz;
    }

    // ---------- odtwarzanie lat (ETAP 235) ----------
    // Kolory gmin w każdym roku we wspólnych klasach liczy serwer; tu tylko
    // przekolorowujemy istniejące warstwy (bez przerysowania mapy).

    const odtwarzacz = document.getElementById("odtwarzacz");
    const suwakLat = document.getElementById("suwak-lat");
    const przyciskGraj = document.getElementById("graj-lata");
    const LAT_WSTECZ = 9;
    const KROK_MS = 1300;
    let lataOdtwarzania = null;
    let zegarLat = null;

    function pokazRokOdtwarzania(i) {
        const rok = String(lataOdtwarzania.lata[i]);
        const kolory = lataOdtwarzania.kolory[rok] || {};
        const wartosci = lataOdtwarzania.wartosci[rok] || {};
        suwakLat.value = String(i);
        document.getElementById("rok-odtwarzania").textContent = rok;
        for (const [teryt, warstwa] of warstwyPoTeryt) {
            warstwa.setStyle({ fillColor: kolory[teryt] || KOLOR_BRAK });
            const dymek = element("div");
            dymek.append(element("strong", "", warstwa.feature.properties.nazwa), element("br"),
                `${rok}: ${teryt in wartosci ? zJednostka(wartosci[teryt]) : "brak danych"}`);
            warstwa.setTooltipContent(dymek);
        }
    }

    function legendaOdtwarzania() {
        legendaEl.replaceChildren(element("div", "legenda__tytul",
            `${lataOdtwarzania.klasyfikacja}, klasy wspólne dla lat ${lataOdtwarzania.lata[0]}–${lataOdtwarzania.lata.at(-1)}`));
        for (const [kolor, opis] of lataOdtwarzania.legenda) legendaEl.appendChild(wierszLegendy(kolor, opis));
        legendaEl.appendChild(wierszLegendy(KOLOR_BRAK, "brak danych"));
    }

    function grajLata(wlacz) {
        clearInterval(zegarLat);
        zegarLat = null;
        przyciskGraj.textContent = wlacz ? "❚❚" : "▶";
        if (!wlacz) return;
        zegarLat = setInterval(() => {
            const nastepny = Number(suwakLat.value) + 1;
            if (nastepny >= lataOdtwarzania.lata.length) return grajLata(false);
            pokazRokOdtwarzania(nastepny);
        }, KROK_MS);
    }

    function zakonczOdtwarzanie(przerysuj = true) {
        if (!lataOdtwarzania) return;
        grajLata(false);
        lataOdtwarzania = null;
        odtwarzacz.hidden = true;
        if (przerysuj) odswiezWidok(); // mapa, dymki i legenda bieżącego roku
    }

    document.getElementById("odtworz-lata").addEventListener("click", async (e) => {
        if (!biezaceDane) return;
        const guzik = e.currentTarget;
        const rok = Number(biezaceDane.rok);
        const p = new URLSearchParams(biezaceParametry);
        p.set("metoda", poleMetoda.value);
        p.set("klasy", poleKlasy.value);
        p.set("od", String(Math.max(PIERWSZY_ROK, rok - LAT_WSTECZ)));
        p.set("do", String(rok));
        guzik.disabled = true;
        guzik.textContent = "Pobieram lata…";
        try {
            const w = await pobierzJson(`${URL_DRUK.replace(/druk$/, "odtwarzanie")}?${p}`);
            if (tryb !== "wartosc") ustawTryb("wartosc");
            lataOdtwarzania = w;
            suwakLat.max = String(w.lata.length - 1);
            odtwarzacz.hidden = false;
            legendaOdtwarzania();
            pokazRokOdtwarzania(0);
            grajLata(true);
        } catch (err) {
            pokazKomunikat(err.message);
        } finally {
            guzik.disabled = false;
            guzik.textContent = "▶ Odtwórz lata";
        }
    });
    przyciskGraj.addEventListener("click", () => {
        if (zegarLat) return grajLata(false);
        if (Number(suwakLat.value) >= lataOdtwarzania.lata.length - 1) pokazRokOdtwarzania(0); // od początku
        grajLata(true);
    });
    suwakLat.addEventListener("input", () => {
        grajLata(false);
        pokazRokOdtwarzania(Number(suwakLat.value));
    });
    document.getElementById("zakoncz-odtwarzanie").addEventListener("click", () => zakonczOdtwarzanie());

    // ETAP 236: kolory z innego skryptu strony (mapa dwuzmiennowa z korelacja.js)
    document.addEventListener("atlas:kolory", (e) => {
        if (!biezaceDane) return;
        zakonczOdtwarzanie(false);
        const { kolory, dymki, legenda } = e.detail;
        for (const [teryt, warstwa] of warstwyPoTeryt) {
            warstwa.setStyle({ fillColor: kolory[teryt] || KOLOR_BRAK });
            const dymek = element("div");
            dymek.append(element("strong", "", warstwa.feature.properties.nazwa), element("br"), dymki[teryt] || "brak danych");
            warstwa.setTooltipContent(dymek);
        }
        const wroc = element("button", "przycisk--tekst", "✕ Wróć do mapy wskaźnika");
        wroc.type = "button";
        wroc.addEventListener("click", odswiezWidok);
        legendaEl.replaceChildren(legenda, wroc);
        mapa.getContainer().scrollIntoView({ behavior: "smooth", block: "center" });
    });

    function pokazLegende() {
        legendaEl.replaceChildren();
        if (tryb === "lq") {
            legendaEl.appendChild(element("div", "legenda__tytul", "iloraz lokalizacji (1 = jak w województwie)"));
            const ile = [0, 0, 0, 0, 0];
            for (const g of biezaceDane.lq.gminy) ile[g.klasa] += 1;
            biezaceDane.lq.opisy.forEach((opis, i) => {
                const wiersz = wierszLegendy(KOLORY_LQ[i], opis);
                wiersz.appendChild(element("span", "legenda__liczebnosc", `${ile[i]}`));
                legendaEl.appendChild(wiersz);
            });
            return;
        }
        if (tryb === "gi") {
            legendaEl.appendChild(element("div", "legenda__tytul", "gorące i zimne punkty Gi*"));
            const ile = {};
            for (const g of wynikMorana.gi) ile[g.kategoria] = (ile[g.kategoria] || 0) + 1;
            for (const kategoria of KOLEJNOSC_GI) {
                const wiersz = wierszLegendy(KOLORY_GI[kategoria], wynikMorana.kategorie_gi[kategoria]);
                wiersz.appendChild(element("span", "legenda__liczebnosc", `${ile[kategoria] || 0}`));
                legendaEl.appendChild(wiersz);
            }
            return;
        }
        if (tryb === "lisa") {
            legendaEl.appendChild(element("div", "legenda__tytul", "klastry LISA (p < 0,05)"));
            const ile = liczKategorie();
            for (const kategoria of ["HH", "LL", "HL", "LH", "ns"]) {
                const wiersz = wierszLegendy(KOLORY_LISA[kategoria], wynikMorana.kategorie[kategoria]);
                wiersz.appendChild(element("span", "legenda__liczebnosc", `${ile[kategoria] || 0}`));
                legendaEl.appendChild(wiersz);
            }
            return;
        }
        if (tryb === "zmiana") {
            const p = biezaceDane.porownanie.progi_zmiany_proc;
            legendaEl.appendChild(element("div", "legenda__tytul", `zmiana ${biezaceDane.porownanie.rok_bazowy}→${biezaceDane.rok}`));
            for (let i = 0; i <= p.length; i += 1) {
                let opis;
                if (i === 0) opis = `≤ ${procent(p[0])}`;
                else if (i === p.length) opis = `> ${procent(p[i - 1])}`;
                else opis = `${procent(p[i - 1])} … ${procent(p[i])}`;
                legendaEl.appendChild(wierszLegendy(KOLORY_ZMIANY[i], opis));
            }
            return;
        }
        const s = biezaceDane.statystyki;
        const k = biezaceDane.klasyfikacja;
        const progiLegendy = [s.min.wartosc, ...k.progi, s.max.wartosc];
        legendaEl.appendChild(element("div", "legenda__tytul", biezaceDane.zmienna.jednostka || "wartość"));
        for (let i = 0; i < progiLegendy.length - 1; i += 1) {
            const wiersz = wierszLegendy(
                kolorGminy({ wartosc: progiLegendy[i + 1] }),
                `${formatLiczby.format(progiLegendy[i])} – ${formatLiczby.format(progiLegendy[i + 1])}`
            );
            wiersz.appendChild(element("span", "legenda__liczebnosc", `${k.liczebnosci[i]}`));
            legendaEl.appendChild(wiersz);
        }
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

    // ---------- profil gminy (wykres w czasie) ----------

    function liczbaProfilu(etykieta, wartosc, klasa = "") {
        const div = element("div", "profil__liczba");
        div.append(element("span", "kafelek__etykieta", etykieta), element("span", `profil__wartosc ${klasa}`, wartosc));
        return div;
    }

    // ETAP 216: powiaty — bez profilu gminy (raport i wykres w czasie są dla gmin) i bez trendu gmin
    function ustawJednostki(powiaty) {
        document.getElementById("naglowek-rankingu").textContent = powiaty ? "Ranking powiatów" : "Ranking gmin";
        document.getElementById("filtr-rankingu").placeholder = powiaty ? "Szukaj powiatu…" : "Szukaj gminy…";
        for (const id of ["link-trend", "link-gminy-czas"]) document.getElementById(id).hidden = powiaty;
        if (powiaty) profilEl.hidden = true;
    }

    async function pokazProfil(teryt) {
        if (biezaceDane && biezaceDane.poziom === "powiaty") return; // profil i raport są dla gmin
        const gmina = biezaceDane.gminy.find((g) => g.teryt === teryt);
        if (!gmina) return;
        const numer = ++numerProfilu;
        const s = biezaceDane.statystyki;
        const miejsce = biezaceDane.gminy.indexOf(gmina) + 1;

        profilEl.hidden = false;
        profilNazwa.textContent = gmina.nazwa;
        document.getElementById("profil-raport").href = URL_RAPORT_GMINY.replace("000000000000", gmina.bdl_id);
        document.getElementById("profil-czas").href = urlGminWCzasie(gmina.bdl_id);
        profilMiejsce.textContent = `${miejsce}. miejsce z ${s.liczba_gmin} w województwie (${biezaceDane.rok})`;
        profilLiczby.replaceChildren(liczbaProfilu(String(biezaceDane.rok), zJednostka(gmina.wartosc)));
        if (s.mediana) {
            const odMediany = ((gmina.wartosc - s.mediana) / Math.abs(s.mediana)) * 100;
            profilLiczby.appendChild(
                liczbaProfilu("od mediany woj.", procent(odMediany), odMediany > 0 ? "wartosc-plus" : odMediany < 0 ? "wartosc-minus" : "")
            );
        }
        profilWykres.replaceChildren();
        profilTabelaWrap.hidden = true;
        profilStatus.textContent = "Pobieranie danych z lat…";
        profilEl.scrollIntoView({ block: "nearest", behavior: "smooth" });

        try {
            let url = URL_PROFIL.replace("000000000000", gmina.bdl_id) + `?zmienna=${biezaceDane.zmienna.id}`;
            if (biezaceDane.zmienna.mianownik) {
                url += `&mianownik=${biezaceDane.zmienna.mianownik.id}&mnoznik=${biezaceDane.zmienna.mnoznik}`;
            }
            const dane = await pobierzJson(url);
            if (numer !== numerProfilu) return;
            if (dane.szereg.length < 2) {
                profilStatus.textContent = "Za mało lat z danymi, żeby narysować zmiany.";
                return;
            }
            profilStatus.textContent = "";
            if (dane.zmiana) {
                const z = dane.zmiana;
                profilLiczby.appendChild(
                    liczbaProfilu(`${z.od}→${z.do}`, procent(z.zmiana_proc), z.zmiana > 0 ? "wartosc-plus" : z.zmiana < 0 ? "wartosc-minus" : "")
                );
            }
            const dymek = element("div", "wykres__dymek");
            dymek.hidden = true;
            WykresGminy.rysuj(profilWykres, dane.szereg, {
                tytul: `${gmina.nazwa}: ${biezaceDane.zmienna.nazwa}`,
                rokWybrany: biezaceDane.rok,
                mediana: s.mediana,
                opisMediany: `mediana ${biezaceDane.rok}`,
                formatOsi: (w) => new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 1 }).format(w),
                formatDymka: zJednostka,
                dymek,
            });
            profilTabela.replaceChildren();
            for (const p of [...dane.szereg].reverse()) {
                const wiersz = element("tr");
                wiersz.append(element("td", "", String(p.rok)), element("td", "liczba", zJednostka(p.wartosc)));
                profilTabela.appendChild(wiersz);
            }
            profilTabelaWrap.hidden = false;
        } catch (e) {
            if (numer === numerProfilu) profilStatus.textContent = `Nie udało się pobrać danych z lat: ${e.message}`;
        }
    }

    document.getElementById("profil-zamknij").addEventListener("click", () => {
        profilEl.hidden = true;
    });

    // ---------- opis przez Gemini ----------

    const TEKST_OPISU =
        "Gemini opisze wynik słowami. Liczby w opisie są sprawdzane: każda musi pochodzić z danych GUS.";

    function resetujOpis() {
        opisEl.className = "wyciszony";
        opisEl.textContent = TEKST_OPISU;
        faktyEl.hidden = true;
    }

    przyciskOpis.addEventListener("click", async () => {
        if (!biezaceDane) return;
        przyciskOpis.disabled = true;
        opisEl.className = "wyciszony";
        opisEl.textContent = "Generowanie opisu…";
        const zapytanie = { zmienna: biezaceDane.zmienna.id, rok: biezaceDane.rok, woj: biezaceDane.wojewodztwo.bdl_id };
        if (biezaceDane.zmienna.mianownik) {
            zapytanie.mianownik = biezaceDane.zmienna.mianownik.id;
            zapytanie.mnoznik = biezaceDane.zmienna.mnoznik;
        }
        if (biezaceDane.porownanie) zapytanie.rok_bazowy = biezaceDane.porownanie.rok_bazowy;
        if (biezaceDane.poziom === "powiaty") zapytanie.poziom = "powiaty"; // ETAP 216
        try {
            const odpowiedz = await fetch(URL_OPIS, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(zapytanie),
            });
            const dane = await odpowiedz.json();
            if (dane.fakty) {
                listaFaktow.replaceChildren(...dane.fakty.map((f) => element("li", "", f)));
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
