// Moduł Praca i notatki — godziny z grafiku (ETAP 230).
// Strona tylko zbiera dane i pokazuje wynik; liczy serwer (praca/grafik.py).
(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);
    const PAMIEC = "praca.godziny"; // imię i stawka zapamiętane w tej przeglądarce

    function pokazBlad(tekst) {
        $("blad-godzin").textContent = tekst;
        $("blad-godzin").hidden = !tekst;
    }

    try {
        const zapisane = JSON.parse(localStorage.getItem(PAMIEC) || "{}");
        if (zapisane.imie) $("imie").value = zapisane.imie;
        if (zapisane.stawka) $("stawka").value = zapisane.stawka;
    } catch (e) {
        // brak pamięci przeglądarki — pola zostają puste
    }

    $("formularz-pliku").addEventListener("submit", async (e) => {
        e.preventDefault();
        const plik = $("plik-grafiku").files[0];
        if (!plik) return;
        pokazBlad("");
        const guzik = $("odczytaj");
        guzik.disabled = true;
        guzik.textContent = "Odczytuję…";
        const dane = new FormData();
        dane.append("plik", plik);
        try {
            const odp = await fetch(URL_ODCZYTAJ, { method: "POST", body: dane });
            const w = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(w.blad || `Błąd ${odp.status}`);
            $("tekst-grafiku").value = w.tekst;
            $("zrodlo-tekstu").textContent = w.zrodlo === "gemini"
                ? "Tekst przepisał Gemini ze zdjęcia — porównaj godziny z grafikiem (znak ? oznacza nieczytelną cyfrę), popraw w polu i kliknij „Policz godziny”."
                : "Tekst odczytany z PDF-u.";
            $("zrodlo-tekstu").hidden = false;
            if (w.zrodlo === "pdf" && $("imie").value.trim()) policz();
        } catch (err) {
            pokazBlad(err.message);
        } finally {
            guzik.disabled = false;
            guzik.textContent = "Odczytaj";
        }
    });

    // ETAP 232: zmiany odznaczone na liście (klucz „dzień|od|do”); nowy tekst grafiku — od nowa
    const pominiete = new Set();
    $("tekst-grafiku").addEventListener("input", () => pominiete.clear());

    function parametry() {
        return {
            tekst: $("tekst-grafiku").value,
            imie: $("imie").value.trim(),
            stawka: $("stawka").value.trim(),
            miesiac: $("miesiac").value,
            rok: $("rok").value,
            pominiete: [...pominiete],
        };
    }

    function pokazZmiany(zmiany) {
        $("liczba-zmian").textContent = `${zmiany.filter((z) => z.wliczona).length} z ${zmiany.length}`;
        $("lista-zmian").replaceChildren(...zmiany.map((z) => {
            const li = document.createElement("li");
            const etykieta = document.createElement("label");
            const pole = document.createElement("input");
            pole.type = "checkbox";
            pole.checked = z.wliczona;
            pole.addEventListener("change", () => {
                if (pole.checked) pominiete.delete(z.klucz);
                else pominiete.add(z.klucz);
                policz();
            });
            etykieta.append(pole, ` ${z.dzien}. · ${z.od}–${z.do} · ${z.godziny} h`);
            li.appendChild(etykieta);
            return li;
        }));
    }

    async function policz() {
        pokazBlad("");
        const cialo = parametry();
        try {
            localStorage.setItem(PAMIEC, JSON.stringify({ imie: cialo.imie, stawka: cialo.stawka }));
        } catch (e) {
            // bez pamięci — trudno
        }
        try {
            const odp = await fetch(URL_POLICZ, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cialo) });
            const w = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(w.blad || `Błąd ${odp.status}`);
            $("suma-godzin").textContent = w.godziny;
            $("kwota").textContent = `${w.kwota} zł`;
            $("opis-kwoty").textContent = `× ${w.stawka} zł/h`;
            $("tekst-wyniku").textContent = w.tekst;
            pokazZmiany(w.zmiany);
            const uwagi = [`Zmian w grafiku: ${w.wszystkich_zmian}, Twoich w tym miesiącu: ${w.zmiany.length}` +
                (w.wliczonych < w.zmiany.length ? `, w sumie: ${w.wliczonych}.` : ".")];
            if (w.pominiete_inny_miesiac) uwagi.push(`Pominięte zmiany z sąsiedniego miesiąca w tabeli: ${w.pominiete_inny_miesiac}.`);
            if (w.inne_osoby.length) uwagi.push(`Inne osoby w grafiku: ${w.inne_osoby.join(", ")}.`);
            if (!w.miesiac_z_tekstu) uwagi.push("Miesiąc i rok — z formularza (w tekście ich nie było).");
            $("uwagi-wyniku").textContent = uwagi.join(" ");
            $("wynik-godzin").hidden = false;
            $("stan-kopiowania").textContent = "";
        } catch (err) {
            $("wynik-godzin").hidden = true;
            pokazBlad(err.message);
        }
    }

    $("policz").addEventListener("click", policz);

    // ---------- historia rozliczeń (ETAP 232) ----------

    function komorka(tr, tekst, klasa) {
        const td = document.createElement("td");
        td.className = klasa || "";
        td.textContent = tekst;
        tr.appendChild(td);
        return td;
    }

    function guzik(tekst, etykieta, akcja) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "przycisk--tekst";
        b.textContent = tekst;
        b.setAttribute("aria-label", etykieta);
        b.addEventListener("click", akcja);
        return b;
    }

    function pokazHistorie(h) {
        const tabela = $("tabela-historii");
        const naglowek = document.createElement("tr");
        for (const [t, k] of [["Miesiąc", ""], ["Zmian", "liczba"], ["Godziny", "liczba"], ["Kwota", "liczba"], ["", ""]]) {
            const th = document.createElement("th");
            th.className = k;
            th.textContent = t;
            naglowek.appendChild(th);
        }
        const wiersze = [naglowek];
        for (const rok of h.lata) {
            for (const m of h.miesiace.filter((x) => x.rok === rok.rok)) {
                const tr = document.createElement("tr");
                komorka(tr, m.imie && h.miesiace.some((x) => x.imie !== m.imie) ? `${m.nazwa} — ${m.imie}` : m.nazwa);
                komorka(tr, String(m.zmian), "liczba");
                komorka(tr, `${m.godziny} h`, "liczba");
                komorka(tr, `${m.kwota_tekst} zł`, "liczba");
                const akcje = komorka(tr, "", "historia-pracy__akcje");
                akcje.append(
                    guzik("Kopiuj", `Kopiuj rozliczenie: ${m.nazwa}`, async (e) => {
                        try {
                            await navigator.clipboard.writeText(m.tekst);
                            e.target.textContent = "Skopiowano";
                        } catch (err) {
                            e.target.textContent = "Brak dostępu do schowka";
                        }
                    }),
                    guzik("✕", `Usuń rozliczenie: ${m.nazwa}`, async () => {
                        if (!confirm(`Usunąć zapisane rozliczenie „${m.nazwa}”?`)) return;
                        const odp = await fetch(`${URL_ROZLICZENIA}/${m.id}`, { method: "DELETE" });
                        if (odp.ok) pokazHistorie(await odp.json());
                    }),
                );
                wiersze.push(tr);
            }
            const suma = document.createElement("tr");
            suma.className = "historia-pracy__suma";
            komorka(suma, `Razem ${rok.rok} (${rok.miesiecy} mies.)`);
            komorka(suma, "");
            komorka(suma, `${rok.godziny} h`, "liczba");
            komorka(suma, `${rok.kwota} zł`, "liczba");
            komorka(suma, "");
            wiersze.push(suma);
        }
        tabela.replaceChildren(...wiersze);
        tabela.hidden = !h.miesiace.length;
        $("brak-historii").hidden = Boolean(h.miesiace.length);
    }

    pokazHistorie(HISTORIA);

    $("zapisz-miesiac").addEventListener("click", async () => {
        try {
            const odp = await fetch(URL_ROZLICZENIA, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(parametry()) });
            const w = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(w.blad || `Błąd ${odp.status}`);
            pokazHistorie(w);
            $("stan-kopiowania").textContent = "Zapisano w historii.";
        } catch (err) {
            pokazBlad(err.message);
        }
    });

    $("kopiuj").addEventListener("click", async () => {
        const tekst = $("tekst-wyniku").textContent;
        try {
            await navigator.clipboard.writeText(tekst);
            $("stan-kopiowania").textContent = "Skopiowano.";
        } catch (e) {
            // bez dostępu do schowka — zaznaczamy tekst do ręcznego skopiowania
            const zakres = document.createRange();
            zakres.selectNodeContents($("tekst-wyniku"));
            getSelection().removeAllRanges();
            getSelection().addRange(zakres);
            $("stan-kopiowania").textContent = "Zaznaczono — skopiuj Ctrl+C.";
        }
    });

    $("pobierz").addEventListener("click", () => {
        const tekst = $("tekst-wyniku").textContent;
        const nazwa = (tekst.split("\n")[0] || "godziny").replace(/\s+/g, "_");
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([tekst + "\n"], { type: "text/plain;charset=utf-8" }));
        a.download = `godziny_${nazwa}.txt`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            URL.revokeObjectURL(a.href);
            a.remove();
        }, 1000);
    });
})();

// ---------- notatki w Wordzie (ETAP 231) ----------
(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);
    let biezace = null; // {notatki, zrodlo}

    function el(tag, klasa, tekst) {
        const e = document.createElement(tag);
        if (klasa) e.className = klasa;
        if (tekst !== undefined) wstawTekst(e, tekst);
        return e;
    }

    // „**słowo**” → <strong>; reszta jako tekst (treść od modelu nigdy jako HTML)
    function wstawTekst(e, tekst) {
        String(tekst).split(/\*\*(.+?)\*\*/).forEach((kawalek, i) => {
            if (!kawalek) return;
            e.appendChild(i % 2 ? Object.assign(document.createElement("strong"), { textContent: kawalek }) : document.createTextNode(kawalek));
        });
    }

    function lista(punkty, klasa) {
        const ul = el("ul", klasa);
        for (const p of punkty) ul.appendChild(el("li", "", p));
        return ul;
    }

    function pokaz(n) {
        const a = $("podglad-notatek");
        a.replaceChildren(el("h3", "podglad-notatek__tytul", n.tytul));
        if (n.podtytul) a.appendChild(el("p", "podglad-notatek__podtytul", n.podtytul));
        if (n.streszczenie) a.appendChild(el("p", "podglad-notatek__streszczenie", n.streszczenie));
        for (const s of n.sekcje) {
            a.appendChild(el("h4", "podglad-notatek__naglowek", s.naglowek));
            for (const b of s.bloki) {
                if (b.typ === "akapit") a.appendChild(el("p", "", b.tekst));
                else if (b.typ === "lista") a.appendChild(lista(b.punkty, "podglad-notatek__lista"));
                else if (b.typ === "ramka") {
                    const r = el("div", "podglad-notatek__ramka");
                    r.append(el("strong", "", b.tytul), el("p", "", b.tekst));
                    a.appendChild(r);
                }
            }
        }
        if (n.pojecia.length) {
            a.appendChild(el("h4", "podglad-notatek__naglowek", "Pojęcia"));
            const owijka = el("div", "przewijanie-tabeli");
            const t = el("table", "podglad-notatek__pojecia");
            const naglowek = el("tr");
            naglowek.append(el("th", "", "Pojęcie"), el("th", "", "Znaczenie"));
            t.appendChild(naglowek);
            for (const p of n.pojecia) {
                const tr = el("tr");
                tr.append(el("td", "", p.pojecie), el("td", "", p.definicja));
                t.appendChild(tr);
            }
            owijka.appendChild(t);
            a.appendChild(owijka);
        }
        if (n.do_zapamietania.length) {
            const z = el("div", "podglad-notatek__zapamietaj");
            z.append(el("strong", "", "Do zapamiętania"), lista(n.do_zapamietania, ""));
            a.appendChild(z);
        }
        if (n.pytania && n.pytania.length) { // ETAP 233: odpowiedź po rozwinięciu
            a.appendChild(el("h4", "podglad-notatek__naglowek", "Sprawdź się"));
            const ol = el("ol", "podglad-notatek__pytania");
            for (const p of n.pytania) {
                const li = el("li");
                const d = el("details");
                d.append(el("summary", "", p.pytanie), el("p", "", p.odpowiedz));
                li.appendChild(d);
                ol.appendChild(li);
            }
            a.appendChild(ol);
        }
        if (n.nieczytelne.length) {
            a.append(el("h4", "podglad-notatek__naglowek", "Nie udało się odczytać"), lista(n.nieczytelne, "podglad-notatek__lista"));
        }
    }

    $("formularz-notatek").addEventListener("submit", async (e) => {
        e.preventDefault();
        const pliki = $("pliki-notatek").files;
        const tekst = $("tekst-notatek").value.trim();
        $("blad-notatek").hidden = true;
        if (!pliki.length && !tekst) {
            $("blad-notatek").textContent = "Wybierz PDF albo zdjęcia, albo wklej tekst.";
            $("blad-notatek").hidden = false;
            return;
        }
        const guzik = $("utworz-notatki");
        guzik.disabled = true;
        $("stan-notatek").textContent = "Gemini układa notatki — to może potrwać do minuty…";
        const dane = new FormData();
        for (const p of pliki) dane.append("pliki", p);
        dane.append("tekst", tekst);
        dane.append("dlugosc", $("dlugosc-notatek").value);
        try {
            const odp = await fetch(URL_NOTATKI, { method: "POST", body: dane });
            const w = await odp.json().catch(() => ({}));
            if (!odp.ok) throw new Error(w.blad || `Błąd ${odp.status}`);
            biezace = { notatki: w.notatki, zrodlo: w.zrodlo };
            pokaz(w.notatki);
            $("pobierz-fiszki").hidden = !(w.notatki.pytania.length || w.notatki.pojecia.length);
            const uwagi = [];
            if (w.liczby_do_sprawdzenia === null) uwagi.push("Notatki ze zdjęć — porównaj liczby, daty i nazwy z oryginałem.");
            else if (w.liczby_do_sprawdzenia.length) uwagi.push(`Liczby, których nie ma w materiale — sprawdź je: ${w.liczby_do_sprawdzenia.join(", ")}.`);
            if (w.obciete) uwagi.push("Materiał był bardzo długi — notatki obejmują jego początek (ok. 50 stron).");
            $("liczby-notatek").textContent = uwagi.join(" ");
            $("liczby-notatek").hidden = !uwagi.length;
            $("wynik-notatek").hidden = false;
            $("stan-notatek").textContent = "Gotowe.";
        } catch (err) {
            $("blad-notatek").textContent = err.message;
            $("blad-notatek").hidden = false;
            $("stan-notatek").textContent = "";
        } finally {
            guzik.disabled = false;
        }
    });

    async function pobierzPlik(url, zapasowaNazwa) {
        if (!biezace) return;
        $("stan-docx").textContent = "";
        try {
            const odp = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(biezace) });
            if (!odp.ok) throw new Error((await odp.json().catch(() => ({}))).blad || `Błąd ${odp.status}`);
            const naglowek = odp.headers.get("Content-Disposition") || "";
            const nazwa = decodeURIComponent((/filename\*=UTF-8''([^;]+)/.exec(naglowek) || [])[1] || zapasowaNazwa);
            const a = document.createElement("a");
            a.href = URL.createObjectURL(await odp.blob());
            a.download = nazwa;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                URL.revokeObjectURL(a.href);
                a.remove();
            }, 1000);
            $("stan-docx").textContent = `Zapisano ${nazwa}.`;
        } catch (err) {
            $("stan-docx").textContent = err.message;
        }
    }

    $("pobierz-docx").addEventListener("click", () => pobierzPlik(URL_DOCX, "notatki.docx"));
    $("pobierz-fiszki").addEventListener("click", () => pobierzPlik(URL_FISZKI, "notatki_fiszki.csv"));
})();
