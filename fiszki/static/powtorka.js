// Sesja powtórki (system Leitnera). Kolejka przychodzi z serwera; fiszka
// oceniona „nie umiem” wraca na koniec kolejki tej samej sesji.
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
            koniecTytul.textContent = "Na dziś nic do powtórki";
            koniecOpis.textContent = "Wróć jutro albo dodaj nowe fiszki.";
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
        odpowiedzBlok.hidden = false;
        przyciskPokaz.hidden = true;
        przyciskiOceny.hidden = false;
    }

    async function ocen(wynik) {
        if (!odpowiedzWidoczna || wysylanie || kolejka.length === 0) return;
        wysylanie = true;
        const fiszka = kolejka.shift();
        try {
            const odpowiedz = await fetch(`${URL_POWTORKA}/${fiszka.id}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ wynik }),
            });
            if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
            const stan = await odpowiedz.json();
            if (wynik === "umiem") {
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
    przyciskNieUmiem.addEventListener("click", () => ocen("nie_umiem"));

    document.addEventListener("keydown", (zdarzenie) => {
        if (zdarzenie.target.matches("input, textarea")) return;
        if (zdarzenie.code === "Space") {
            zdarzenie.preventDefault();
            odslon();
        } else if (zdarzenie.key === "1") {
            ocen("nie_umiem");
        } else if (zdarzenie.key === "2") {
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
