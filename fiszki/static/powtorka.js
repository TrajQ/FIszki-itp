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

        pytanieEl.textContent = fiszka.pytanie;
        poleOdpowiedzi.value = "";
        poleOdpowiedzi.hidden = !trybPisania.checked;
        twojaBlok.hidden = true;
        if (trybPisania.checked) poleOdpowiedzi.focus();
        odpowiedzEl.textContent = fiszka.odpowiedz;
        fragmentEl.textContent = fiszka.fragment_tekstu;
        pudelkoEl.textContent = `Pudełko ${fiszka.pudelko} z 5`;
        zrodloEl.textContent = `${fiszka.nazwa_oryginalna}, s. ${fiszka.strona} ↗`;
        zrodloEl.href = URL_PDF_WZOR.replace("/0/", `/${fiszka.pdf_id}/`) + `?fiszka=${fiszka.id}`;

        // Animacja wejścia karty.
        kartaEl.classList.remove("karta-powtorki--wejscie");
        void kartaEl.offsetWidth;
        kartaEl.classList.add("karta-powtorki--wejscie");
    }

    function odslon() {
        if (odpowiedzWidoczna || kolejka.length === 0) return;
        odpowiedzWidoczna = true;
        pokazPorownanie(kolejka[0].odpowiedz, poleOdpowiedzi.value);
        poleOdpowiedzi.hidden = true;
        poleOdpowiedzi.blur(); // żeby działały skróty 1/2/3
        odpowiedzBlok.hidden = false;
        przyciskPokaz.hidden = true;
        przyciskiOceny.hidden = false;
    }

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
    trybPisania.addEventListener("change", () => {
        try {
            localStorage.setItem(KLUCZ_PISANIA, trybPisania.checked ? "1" : "0");
        } catch (e) {
            // zapamiętanie to tylko wygoda
        }
        if (!odpowiedzWidoczna && kolejka.length) {
            poleOdpowiedzi.hidden = !trybPisania.checked;
            if (trybPisania.checked) poleOdpowiedzi.focus();
        }
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

    fetch(URL_KOLEJKA)
        .then((odpowiedz) => {
            if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
            return odpowiedz.json();
        })
        .then((fiszki) => {
            kolejka = fiszki;
            liczbaStartowa = fiszki.length;
            aktualizujPostep();
            pokazFiszke();
        })
        .catch((e) => pokazBlad(`Nie udało się pobrać fiszek: ${e.message}`));
})();
