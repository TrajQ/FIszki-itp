// Quiz ABCD z własnych fiszek. Pytania i odpowiedzi przygotowuje serwer
// (fiszki/quiz.py); tu tylko prowadzimy użytkownika i liczymy wynik.
(function () {
    "use strict";

    const LITERY = ["A", "B", "C", "D"];
    const karta = document.getElementById("karta-quizu");
    const pytanieEl = document.getElementById("pytanie-quizu");
    const odpowiedziEl = document.getElementById("odpowiedzi-quizu");
    const dalej = document.getElementById("przycisk-dalej");
    const postep = document.getElementById("postep-quizu");
    const pasek = document.getElementById("pasek-postepu-wypelnienie");
    const blad = document.getElementById("blad-quizu");

    let pytania = [];
    let indeks = 0;
    let dobre = 0;
    let odpowiedziano = false;
    const pomylki = [];

    function el(tag, klasa, tekst) {
        const e = document.createElement(tag);
        if (klasa) e.className = klasa;
        if (tekst !== undefined) e.textContent = tekst;
        return e;
    }

    function aktualizujPostep() {
        postep.textContent = `${Math.min(indeks + 1, pytania.length)} / ${pytania.length}`;
        pasek.style.width = `${(indeks / pytania.length) * 100}%`;
    }

    function pokazPytanie() {
        const p = pytania[indeks];
        odpowiedziano = false;
        dalej.hidden = true;
        pytanieEl.textContent = p.pytanie;
        odpowiedziEl.replaceChildren();
        p.odpowiedzi.forEach((tekst, i) => {
            const li = el("li");
            const przycisk = el("button", "odpowiedz-quizu");
            przycisk.type = "button";
            przycisk.append(el("span", "odpowiedz-quizu__litera", LITERY[i]), el("span", "", tekst));
            przycisk.addEventListener("click", () => wybierz(i));
            li.appendChild(przycisk);
            odpowiedziEl.appendChild(li);
        });
        karta.classList.remove("karta-powtorki--wejscie");
        void karta.offsetWidth;
        karta.classList.add("karta-powtorki--wejscie");
        aktualizujPostep();
    }

    function wybierz(i) {
        if (odpowiedziano) return;
        odpowiedziano = true;
        const p = pytania[indeks];
        const przyciski = odpowiedziEl.querySelectorAll(".odpowiedz-quizu");
        przyciski.forEach((b) => (b.disabled = true));
        przyciski[p.poprawna].classList.add("odpowiedz-quizu--dobra");
        if (i === p.poprawna) {
            dobre += 1;
        } else {
            przyciski[i].classList.add("odpowiedz-quizu--zla");
            pomylki.push(p);
        }
        dalej.hidden = false;
        dalej.focus();
    }

    function nastepne() {
        if (!odpowiedziano) return;
        indeks += 1;
        if (indeks < pytania.length) pokazPytanie();
        else pokazWynik();
    }

    function pokazWynik() {
        karta.hidden = true;
        pasek.style.width = "100%";
        const procent = Math.round((dobre / pytania.length) * 100);
        document.getElementById("wynik-tytul").textContent = `${dobre} / ${pytania.length} (${procent}%)`;
        document.getElementById("wynik-opis").textContent =
            procent >= 90 ? "Świetnie — materiał opanowany." : procent >= 60 ? "Dobrze, ale kilka rzeczy warto powtórzyć." : "Wróć do źródła przy pomyłkach poniżej.";
        if (pomylki.length) {
            document.getElementById("pomylki").hidden = false;
            const lista = document.getElementById("lista-pomylek");
            for (const p of pomylki) {
                const li = el("li");
                const link = el("a", "wynik-szukania");
                link.href = URL_PDF_WZOR.replace("/0/", `/${p.pdf_id}/`) + `?fiszka=${p.fiszka_id}`;
                link.append(
                    el("div", "fiszka-pytanie", p.pytanie),
                    el("span", "wynik-szukania__zrodlo", p.strona ? `s. ${p.strona} ↗` : "import ↗"),
                    el("div", "wynik-szukania__odpowiedz", p.odpowiedzi[p.poprawna])
                );
                li.appendChild(link);
                lista.appendChild(li);
            }
        }
        document.getElementById("wynik-quizu").hidden = false;
    }

    dalej.addEventListener("click", nastepne);
    document.addEventListener("keydown", (e) => {
        // Ctrl+C / Cmd+A itp. to skróty przeglądarki, nie wybór odpowiedzi.
        if (karta.hidden || e.ctrlKey || e.metaKey || e.altKey) return;
        const numer = "1234".indexOf(e.key) !== -1 ? Number(e.key) - 1 : LITERY.indexOf(e.key.toUpperCase());
        if (numer >= 0 && numer < LITERY.length && !odpowiedziano) wybierz(numer);
        else if (e.key === "Enter" && odpowiedziano) {
            e.preventDefault();
            nastepne();
        }
    });

    fetch(URL_PYTANIA)
        .then(async (odpowiedz) => {
            const dane = await odpowiedz.json();
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            pytania = dane;
            karta.hidden = false;
            pokazPytanie();
        })
        .catch((e) => {
            blad.textContent = e.message;
            blad.hidden = false;
        });
})();
