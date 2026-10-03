// Sesja powtórki (system Leitnera). Kolejka przychodzi z serwera; fiszka
// oceniona „nie umiem” wraca na koniec kolejki tej samej sesji.
//
// ETAP 39: ocena „trudne”, tryb wpisywania odpowiedzi i tryb „przed
// egzaminem” (TRYB_EGZAMINU) — wszystkie fiszki, oceny nie są zapisywane.
(function () {
    "use strict";

    const kartaEl = document.getElementById("karta-powtorki");
    const koniecEl = document.getElementById("koniec-powtorki");
    const koniecTytul = document.getElementById("koniec-tytul");
    const koniecOpis = document.getElementById("koniec-opis");
    const bladEl = document.getElementById("blad-powtorki");
    const pytanieEl = document.getElementById("pytanie-powtorki");
    const obrazPrzod = document.getElementById("obraz-przod");
    const obrazTyl = document.getElementById("obraz-tyl");
    const odpowiedzEl = document.getElementById("odpowiedz-powtorki");
    const fragmentEl = document.getElementById("fragment-powtorki");
    const odpowiedzBlok = document.getElementById("odpowiedz-blok");
    const pudelkoEl = document.getElementById("pudelko-fiszki");
    const zrodloEl = document.getElementById("zrodlo-fiszki");
    const przyciskPokaz = document.getElementById("przycisk-pokaz");
    const przyciskiOceny = document.getElementById("przyciski-oceny");
    const przyciskUmiem = document.getElementById("przycisk-umiem");
    const przyciskTrudne = document.getElementById("przycisk-trudne");
    const trybPisania = document.getElementById("tryb-pisania");
    const poleOdpowiedzi = document.getElementById("pole-odpowiedzi");
    const twojaBlok = document.getElementById("twoja-odpowiedz-blok");
    const twojaEl = document.getElementById("twoja-odpowiedz");
    const trafieniaEl = document.getElementById("trafienia");
    const KLUCZ_PISANIA = "fiszki.trybPisania";
    // ETAP 51: odwrócona karta — przód to odpowiedź, a przypomnieć trzeba pytanie.
    const trybOdwrocony = document.getElementById("tryb-odwrocony");
    const etykietaPrzod = document.getElementById("etykieta-przod");
    const etykietaTyl = document.getElementById("etykieta-tyl");
    const KLUCZ_ODWROCENIA = "fiszki.trybOdwrocony";

    function przod(fiszka) {
        return trybOdwrocony.checked ? fiszka.odpowiedz : fiszka.pytanie;
    }

    function tyl(fiszka) {
        return trybOdwrocony.checked ? fiszka.pytanie : fiszka.odpowiedz;
    }
    const przyciskNieUmiem = document.getElementById("przycisk-nie-umiem");
    const postepTekst = document.getElementById("postep-tekst");
    const postepWypelnienie = document.getElementById("pasek-postepu-wypelnienie");

    let kolejka = [];
    let liczbaStartowa = 0;
    let opanowane = 0;
    let odpowiedzWidoczna = false;
    let wysylanie = false;

    function pokazBlad(tresc) {
        bladEl.textContent = tresc;
        bladEl.hidden = false;
    }

    function aktualizujPostep() {
        postepTekst.textContent = `${opanowane} / ${liczbaStartowa}`;
        const procent = liczbaStartowa ? (opanowane / liczbaStartowa) * 100 : 0;
        postepWypelnienie.style.width = `${procent}%`;
    }

    function pokazKoniec() {
        kartaEl.hidden = true;
        koniecEl.hidden = false;
        if (liczbaStartowa === 0) {
            koniecTytul.textContent = TRYB_EGZAMINU ? "Brak fiszek" : "Na dziś nic do powtórki";
            koniecOpis.textContent = TRYB_EGZAMINU ? "Dodaj fiszki do pliku." : "Wróć jutro albo dodaj nowe fiszki.";
        } else if (TRYB_EGZAMINU) {
            koniecTytul.textContent = "Wszystko przerobione";
            koniecOpis.textContent = `Fiszki: ${liczbaStartowa}. Harmonogram powtórek się nie zmienił — powodzenia na egzaminie!`;
        } else {
            koniecTytul.textContent = "Wszystko powtórzone";
            koniecOpis.textContent = `Opanowane fiszki: ${liczbaStartowa}. Kolejne wrócą zgodnie z harmonogramem.`;
        }
    }

    function pokazFiszke() {
        if (kolejka.length === 0) {
            pokazKoniec();
            return;
        }
        const fiszka = kolejka[0];
        kartaEl.hidden = false;
        odpowiedzWidoczna = false;
        odpowiedzBlok.hidden = true;
        przyciskPokaz.hidden = false;
        przyciskiOceny.hidden = true;

        pokazPytanie(fiszka);
        etykietaPrzod.textContent = trybOdwrocony.checked ? "Odpowiedź — jakie to pojęcie?" : "Pytanie";
        etykietaTyl.textContent = trybOdwrocony.checked ? "Pytanie" : "Odpowiedź";
        poleOdpowiedzi.value = "";
        poleOdpowiedzi.hidden = !trybPisania.checked || Boolean(poleLuki);
        twojaBlok.hidden = true;
        if (trybPisania.checked) (poleLuki || poleOdpowiedzi).focus();
        odpowiedzEl.textContent = tyl(fiszka);
        // ETAP 154: wycinek rysunku należy do pytania — w trybie odwróconym jest z tyłu karty
        for (const [obraz, widoczny] of [[obrazPrzod, !trybOdwrocony.checked], [obrazTyl, trybOdwrocony.checked]]) {
            obraz.hidden = !(fiszka.obraz && widoczny);
            if (!obraz.hidden) obraz.src = fiszka.obraz;
            // ETAP 185: zasłonięty fragment — zakryty przy pytaniu, z tyłu karty tylko obrys
            ZaslonaObrazu.ustaw(obraz, fiszka.zaslona, obraz === obrazPrzod);
        }
        fragmentEl.textContent = fiszka.fragment_tekstu;
        fragmentEl.hidden = !fiszka.fragment_tekstu; // fiszka z importu nie ma cytatu
        pudelkoEl.textContent = `Pudełko ${fiszka.pudelko} z 5`;
        const tematEl = document.getElementById("temat-fiszki"); // ETAP 206
        tematEl.hidden = !(fiszka.tematy && fiszka.tematy.length);
        tematEl.textContent = (fiszka.tematy || []).join(", ");
        zrodloEl.textContent = fiszka.strona ? `${fiszka.nazwa_oryginalna}, s. ${fiszka.strona} ↗` : `${fiszka.nazwa_oryginalna} (import) ↗`;
        zrodloEl.href = URL_PDF_WZOR.replace("/0/", `/${fiszka.pdf_id}/`) + `?fiszka=${fiszka.id}`;

        // Animacja wejścia karty.
        kartaEl.classList.remove("karta-powtorki--wejscie");
        void kartaEl.offsetWidth;
        kartaEl.classList.add("karta-powtorki--wejscie");
    }

    // ---------- ETAP 172: fiszka z luką w trybie pisania ----------
    // Pole do wpisania stoi w miejscu „[…]” (luki z ETAPu 139), a wpis
    // porównujemy z całą odpowiedzią: dokładnie / bez polskich znaków /
    // literówka / inaczej. Ocenę i tak wybiera użytkownik.

    const ZNAK_LUKI = "[…]";
    let poleLuki = null;

    function pokazPytanie(fiszka) {
        const tekst = przod(fiszka);
        const czesci = tekst.split(ZNAK_LUKI);
        poleLuki = null;
        if (!trybPisania.checked || trybOdwrocony.checked || czesci.length !== 2) {
            pytanieEl.textContent = tekst;
            return;
        }
        poleLuki = document.createElement("input");
        poleLuki.type = "text";
        poleLuki.className = "pole-luki";
        poleLuki.autocomplete = "off";
        poleLuki.spellcheck = false;
        poleLuki.setAttribute("aria-label", "Brakujące słowa");
        poleLuki.size = Math.max(8, Math.min(30, tyl(fiszka).length + 2));
        poleLuki.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                odslon();
            }
        });
        pytanieEl.replaceChildren(czesci[0], poleLuki, czesci[1]);
    }

    function bezZnakow(tekst) {
        return tekst.normalize("NFD").replace(/\p{M}/gu, "").replace(/ł/g, "l").replace(/Ł/g, "L");
    }

    function uprosc(tekst) {
        return tekst.toLocaleLowerCase("pl-PL").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
    }

    function odlegloscEdycji(a, b) {
        let poprzedni = Array.from({ length: b.length + 1 }, (_, i) => i);
        for (let i = 1; i <= a.length; i++) {
            const biezacy = [i];
            for (let j = 1; j <= b.length; j++) {
                biezacy[j] = Math.min(poprzedni[j] + 1, biezacy[j - 1] + 1, poprzedni[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
            }
            poprzedni = biezacy;
        }
        return poprzedni[b.length];
    }

    // wynik porównania wpisu z luką — tekst dla użytkownika, bez punktów
    function ocenaLuki(poprawna, wpisana) {
        const p = uprosc(poprawna);
        const w = uprosc(wpisana);
        if (!w) return "Pole było puste.";
        if (p === w) return "✓ Dokładnie tak.";
        if (bezZnakow(p) === bezZnakow(w)) return "✓ Dobrze — tylko bez polskich znaków.";
        if (odlegloscEdycji(bezZnakow(p), bezZnakow(w)) <= Math.max(1, Math.floor(p.length / 8))) return "≈ Prawie — literówka.";
        return "✗ Inaczej niż w odpowiedzi.";
    }

    function odslon() {
        if (odpowiedzWidoczna || kolejka.length === 0) return;
        odpowiedzWidoczna = true;
        ZaslonaObrazu.ustaw(obrazPrzod, kolejka[0].zaslona, false); // ETAP 185: odsłonięcie pokazuje miejsce
        if (poleLuki) {
            const wpisana = poleLuki.value;
            poleLuki.disabled = true;
            poleLuki.blur();
            odpowiedzEl.textContent = tyl(kolejka[0]);
            twojaEl.textContent = wpisana.trim() || "—";
            trafieniaEl.textContent = ocenaLuki(tyl(kolejka[0]), wpisana);
            twojaBlok.hidden = false;
        } else {
            pokazPorownanie(tyl(kolejka[0]), poleOdpowiedzi.value);
        }
        poleOdpowiedzi.hidden = true;
        poleOdpowiedzi.blur(); // żeby działały skróty 1/2/3
        pokazWyjasnienie(kolejka[0]);
        odpowiedzBlok.hidden = false;
        przyciskPokaz.hidden = true;
        przyciskiOceny.hidden = false;
    }

    // ---------- ETAP 207: wyjaśnienie po odsłonięciu (własne albo z Gemini — fiszki/wyjasnienia.py) ----------
    const wyjasnienieNaglowek = document.getElementById("wyjasnienie-naglowek");
    const wyjasnienieTekst = document.getElementById("wyjasnienie-tekst");
    const edycjaWyjasnienia = document.getElementById("edycja-wyjasnienia");
    const poleWyjasnienia = document.getElementById("pole-wyjasnienia");
    const stanWyjasnienia = document.getElementById("stan-wyjasnienia");
    const przyciskGemini = document.getElementById("wyjasnij-gemini");
    const przyciskWlasne = document.getElementById("wyjasnienie-wlasne");
    const przyciskUsunWyjasnienie = document.getElementById("usun-wyjasnienie");
    const urlWyjasnienia = (id) => URL_WYJASNIENIE_WZOR.replace(/\/0$/, `/${id}`);

    function pokazWyjasnienie(fiszka) {
        const w = fiszka.wyjasnienie;
        wyjasnienieNaglowek.hidden = wyjasnienieTekst.hidden = !w;
        wyjasnienieTekst.textContent = w ? w.tekst : "";
        document.getElementById("zrodlo-wyjasnienia").textContent = w ? (w.zrodlo === "gemini" ? "· Gemini, z fragmentu źródła" : "· własne") : "";
        przyciskGemini.textContent = w ? "Wyjaśnij jeszcze raz (Gemini)" : "Wyjaśnij z fragmentu (Gemini)";
        przyciskWlasne.textContent = w ? "Popraw wyjaśnienie" : "Własne wyjaśnienie";
        edycjaWyjasnienia.hidden = stanWyjasnienia.hidden = true;
        przyciskUsunWyjasnienie.hidden = !w;
    }

    async function wyslijWyjasnienie(url, opcje, opisCzekania) {
        const fiszka = kolejka[0];
        stanWyjasnienia.hidden = false;
        stanWyjasnienia.textContent = opisCzekania;
        przyciskGemini.disabled = true;
        try {
            const odp = await fetch(url, opcje);
            const dane = odp.status === 204 ? null : await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error((dane && dane.blad) || `Błąd ${odp.status}`);
            fiszka.wyjasnienie = dane;
            if (kolejka[0] === fiszka) pokazWyjasnienie(fiszka);
        } catch (e) {
            stanWyjasnienia.textContent = e.message;
        } finally {
            przyciskGemini.disabled = false;
        }
    }

    przyciskGemini.addEventListener("click", () => wyslijWyjasnienie(`${urlWyjasnienia(kolejka[0].id)}/gemini`, { method: "POST" }, "Gemini czyta fragment źródła…"));
    przyciskWlasne.addEventListener("click", () => {
        edycjaWyjasnienia.hidden = !edycjaWyjasnienia.hidden;
        poleWyjasnienia.value = kolejka[0].wyjasnienie ? kolejka[0].wyjasnienie.tekst : "";
        if (!edycjaWyjasnienia.hidden) poleWyjasnienia.focus();
    });
    document.getElementById("zapisz-wyjasnienie").addEventListener("click", () => wyslijWyjasnienie(urlWyjasnienia(kolejka[0].id), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tekst: poleWyjasnienia.value }),
    }, "Zapisuję…"));
    przyciskUsunWyjasnienie.addEventListener("click", () => wyslijWyjasnienie(urlWyjasnienia(kolejka[0].id), { method: "DELETE" }, "Usuwam…"));

    // ---------- porównanie wpisanej odpowiedzi ----------
    // Bez oceniania „na procenty” — tylko podświetlamy w poprawnej
    // odpowiedzi słowa, które pojawiły się też we wpisanej. Porównujemy
    // początki słów (5 liter), żeby „planowania” pasowało do „planowanie”.

    const DLUGOSC_RDZENIA = 5;
    const MIN_DLUGOSC_SLOWA = 3;

    function slowa(tekst) {
        return tekst.toLocaleLowerCase("pl-PL").match(/[\p{L}\p{N}]+/gu) || [];
    }

    function rdzen(slowo) {
        return slowo.slice(0, DLUGOSC_RDZENIA);
    }

    function pokazPorownanie(poprawna, wpisana) {
        odpowiedzEl.replaceChildren();
        const rdzenieWpisane = new Set(slowa(wpisana).filter((s) => s.length >= MIN_DLUGOSC_SLOWA).map(rdzen));
        if (!wpisana.trim()) {
            odpowiedzEl.textContent = poprawna;
            twojaBlok.hidden = true;
            return;
        }
        // Tekst dzielimy na słowa i resztę, żeby zachować interpunkcję.
        const kawalki = poprawna.split(/([\p{L}\p{N}]+)/u);
        const kluczowe = new Set();
        const trafione = new Set();
        for (const kawalek of kawalki) {
            const male = kawalek.toLocaleLowerCase("pl-PL");
            const jestSlowem = /^[\p{L}\p{N}]+$/u.test(kawalek) && male.length >= MIN_DLUGOSC_SLOWA;
            if (jestSlowem) kluczowe.add(rdzen(male));
            if (jestSlowem && rdzenieWpisane.has(rdzen(male))) {
                trafione.add(rdzen(male));
                const mark = document.createElement("mark");
                mark.textContent = kawalek;
                odpowiedzEl.appendChild(mark);
            } else {
                odpowiedzEl.appendChild(document.createTextNode(kawalek));
            }
        }
        twojaEl.textContent = wpisana;
        trafieniaEl.textContent = `Wspólne słowa: ${trafione.size} z ${kluczowe.size} (podświetlone w odpowiedzi). Oceń się sam — liczy się sens, nie słowa.`;
        twojaBlok.hidden = false;
    }

    async function ocen(wynik) {
        if (!odpowiedzWidoczna || wysylanie || kolejka.length === 0) return;
        wysylanie = true;
        const fiszka = kolejka.shift();
        if (TRYB_EGZAMINU) {
            // Bez zapisu: harmonogram Leitnera zostaje nietknięty.
            if (wynik === "nie_umiem") kolejka.push(fiszka);
            else opanowane += 1;
            wysylanie = false;
            aktualizujPostep();
            pokazFiszke();
            return;
        }
        try {
            const odpowiedz = await fetch(`${URL_POWTORKA}/${fiszka.id}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ wynik }),
            });
            if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
            const stan = await odpowiedz.json();
            if (wynik !== "nie_umiem") {
                opanowane += 1;
            } else {
                // Wraca na koniec sesji już z pudełka 1.
                kolejka.push({ ...fiszka, pudelko: stan.pudelko });
            }
        } catch (e) {
            kolejka.unshift(fiszka);
            pokazBlad(`Nie udało się zapisać odpowiedzi: ${e.message}`);
        } finally {
            wysylanie = false;
        }
        aktualizujPostep();
        pokazFiszke();
    }

    przyciskPokaz.addEventListener("click", odslon);
    przyciskUmiem.addEventListener("click", () => ocen("umiem"));
    przyciskTrudne.addEventListener("click", () => ocen("trudne"));

    try {
        trybPisania.checked = localStorage.getItem(KLUCZ_PISANIA) === "1";
    } catch (e) {
        // bez localStorage tryb pisania jest po prostu wyłączony
    }
    try {
        trybOdwrocony.checked = localStorage.getItem(KLUCZ_ODWROCENIA) === "1";
    } catch (e) {
        // bez localStorage — zwykły kierunek
    }
    trybOdwrocony.addEventListener("change", () => {
        try {
            localStorage.setItem(KLUCZ_ODWROCENIA, trybOdwrocony.checked ? "1" : "0");
        } catch (e) {
            // zapamiętanie to tylko wygoda
        }
        // Zmiana w trakcie: bieżąca karta od nowa, w nowym kierunku.
        if (kolejka.length) pokazFiszke();
    });

    trybPisania.addEventListener("change", () => {
        try {
            localStorage.setItem(KLUCZ_PISANIA, trybPisania.checked ? "1" : "0");
        } catch (e) {
            // zapamiętanie to tylko wygoda
        }
        // bieżąca karta od nowa — przy luce pole wpisu pojawia się w pytaniu (ETAP 172)
        if (!odpowiedzWidoczna && kolejka.length) pokazFiszke();
    });

    poleOdpowiedzi.addEventListener("keydown", (zdarzenie) => {
        if (zdarzenie.key === "Enter" && (zdarzenie.ctrlKey || zdarzenie.metaKey)) {
            zdarzenie.preventDefault();
            odslon();
        }
    });
    przyciskNieUmiem.addEventListener("click", () => ocen("nie_umiem"));

    document.addEventListener("keydown", (zdarzenie) => {
        if (zdarzenie.target.matches("input:not([type=checkbox]), textarea")) return;
        if (document.querySelector("dialog[open]")) return; // okno skrótów (ETAP 167) — spacja nie odsłania za nim
        if (zdarzenie.code === "Space") {
            zdarzenie.preventDefault();
            odslon();
        } else if (zdarzenie.key === "1") {
            ocen("nie_umiem");
        } else if (zdarzenie.key === "2") {
            ocen("trudne");
        } else if (zdarzenie.key === "3") {
            ocen("umiem");
        }
    });

    // ---------- ETAP 206: przeplatanie tematów — kolejność układa serwer (powtorki.przeplec) ----------
    const trybPrzeplatania = document.getElementById("tryb-przeplatania"); // brak przy powtórce jednego tematu
    const KLUCZ_PRZEPLATANIA = "fiszki.trybPrzeplatania";
    try {
        if (trybPrzeplatania) trybPrzeplatania.checked = localStorage.getItem(KLUCZ_PRZEPLATANIA) === "1";
    } catch (e) {
        // bez localStorage — zwykła kolejność
    }

    function adresKolejki() {
        if (!trybPrzeplatania || !trybPrzeplatania.checked) return URL_KOLEJKA;
        return `${URL_KOLEJKA}${URL_KOLEJKA.includes("?") ? "&" : "?"}przeplatanie=1`;
    }

    function pobierzKolejke() {
        return fetch(adresKolejki()).then((odpowiedz) => {
            if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
            return odpowiedz.json();
        });
    }

    if (trybPrzeplatania) {
        trybPrzeplatania.addEventListener("change", () => {
            try {
                localStorage.setItem(KLUCZ_PRZEPLATANIA, trybPrzeplatania.checked ? "1" : "0");
            } catch (e) {
                // zapamiętanie to tylko wygoda
            }
            if (!kolejka.length) return;
            // Te same fiszki, które zostały w kolejce — tylko w nowej kolejności;
            // karta z odsłoniętą odpowiedzią zostaje na miejscu do oceny.
            const biezaca = odpowiedzWidoczna ? kolejka[0] : null;
            const zostaly = new Set(kolejka.filter((f) => f !== biezaca).map((f) => f.id));
            pobierzKolejke().then((fiszki) => {
                const reszta = fiszki.filter((f) => zostaly.has(f.id));
                if (biezaca) {
                    kolejka = [biezaca, ...reszta];
                } else {
                    kolejka = reszta;
                    pokazFiszke();
                }
            }).catch((e) => pokazBlad(`Nie udało się pobrać fiszek: ${e.message}`));
        });
    }

    pobierzKolejke()
        .then((fiszki) => {
            kolejka = fiszki;
            liczbaStartowa = fiszki.length;
            aktualizujPostep();
            pokazFiszke();
        })
        .catch((e) => pokazBlad(`Nie udało się pobrać fiszek: ${e.message}`));
})();
