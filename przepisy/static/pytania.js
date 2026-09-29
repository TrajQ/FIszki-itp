// Moduł przepisy: pytania z odpowiedzią i cytatami (ETAP 62).
// Odpowiedź układa Gemini, ale serwer (przepisy/pytania.py) przepuszcza
// tylko cytaty znalezione w tekście przepisów; tu tylko wyświetlamy.
(function () {
    "use strict";

    const formularz = document.getElementById("formularz-pytania");
    const pole = document.getElementById("pole-pytania");
    const przycisk = document.getElementById("przycisk-pytania");
    const filtr = document.getElementById("filtr-aktu");
    const stan = document.getElementById("stan-pytania");
    const odpowiedzi = document.getElementById("odpowiedzi");

    function element(tag, klasa, tekst) {
        const el = document.createElement(tag);
        if (klasa) el.className = klasa;
        if (tekst !== undefined) el.textContent = tekst;
        return el;
    }

    function pokazStan(tekst, blad) {
        stan.textContent = tekst;
        stan.className = blad ? "komunikat komunikat--blad" : "komunikat";
        stan.hidden = !tekst;
    }

    function karta(p, data) {
        const w = p.wynik || p;
        const div = element("article", "odpowiedz");
        const pasek = element("div", "odpowiedz__pasek");
        pasek.append(element("strong", "odpowiedz__pytanie", p.pytanie));
        if (p.id) {
            const usun = element("button", "przycisk--tekst odpowiedz__usun", "Usuń");
            usun.type = "button";
            usun.addEventListener("click", async () => {
                const r = await fetch(`${URL_PYTANIA}${p.id}`, { method: "DELETE" });
                if (r.ok) div.remove();
            });
            pasek.append(usun);
        }
        div.append(pasek);
        if (data) div.append(element("span", "wyciszony odpowiedz__data", data.slice(0, 16).replace("T", " ")));
        div.append(element("p", w.brak_odpowiedzi ? "odpowiedz__tekst odpowiedz__tekst--brak" : "odpowiedz__tekst", w.odpowiedz));

        if (w.cytaty.length) {
            const lista = element("ol", "cytaty");
            for (const [nr, c] of w.cytaty.entries()) {
                const li = element("li", "cytat");
                li.append(element("blockquote", "", `„${c.cytat}”`));
                const zrodlo = element("div", "cytat__zrodlo");
                const link = element("a", "", c.oznaczenie);
                link.href = `${URL_AKT}${c.akt_id}#j${c.jednostka_id}`;
                const pdf = element("a", "wyciszony", `PDF s. ${c.strona}`);
                pdf.href = `${URL_AKT}${c.akt_id}/plik#page=${c.strona}`;
                pdf.target = "_blank";
                pdf.rel = "noopener";
                zrodlo.append(link, element("span", "wyciszony", ` · ${c.nazwa_aktu} · `), pdf);
                if (p.id) {
                    const przycisk = element("button", "przycisk--tekst cytat__fiszka", "+ Fiszka");
                    przycisk.type = "button";
                    przycisk.title = "Fiszka do nauki z kotwicą w PDF-ie aktu";
                    przycisk.addEventListener("click", () => {
                        przycisk.hidden = true;
                        li.append(formularzFiszki(p, nr, c, () => (przycisk.hidden = false)));
                    });
                    zrodlo.append(przycisk);
                }
                li.append(zrodlo);
                lista.append(li);
            }
            div.append(lista);
        }
        const uwagi = [];
        if (w.odrzucone_cytaty) uwagi.push(`odrzucone cytaty, których nie ma w tekście: ${w.odrzucone_cytaty}`);
        if (w.przeszukane && w.przeszukane.length) uwagi.push(`model widział: ${w.przeszukane.map((j) => j.oznaczenie).join(", ")}`);
        if (uwagi.length) div.append(element("p", "wyciszony odpowiedz__uwagi", uwagi.join(" · ")));
        return div;
    }

    // Fiszka z cytatu (ETAP 68): pytanie i odpowiedź do poprawienia przed
    // zapisem; kotwicą w źródle jest sam cytat na swojej stronie PDF-a.
    function formularzFiszki(p, nr, c, anuluj) {
        const f = element("form", "formularz-fiszki");
        const pole = (etykieta, wartosc, wiersze) => {
            const l = element("label", "", etykieta);
            const t = element("textarea");
            t.rows = wiersze;
            t.maxLength = 2000;
            t.value = wartosc;
            l.append(t);
            f.append(l);
            return t;
        };
        const pytanie = pole("Pytanie", p.pytanie, 2);
        const odpowiedz = pole("Odpowiedź", `${c.cytat} (${c.oznaczenie})`, 3);
        const temat = element("input");
        temat.type = "text";
        temat.value = "przepisy";
        temat.maxLength = 60;
        const lTemat = element("label", "", "Temat");
        lTemat.append(temat);
        f.append(lTemat);
        const stan = element("p", "wyciszony");
        const zapisz = element("button", "", "Utwórz fiszkę");
        zapisz.type = "submit";
        const wroc = element("button", "przycisk--tekst", "Anuluj");
        wroc.type = "button";
        wroc.addEventListener("click", () => {
            f.remove();
            anuluj();
        });
        const rzad = element("div", "rzad");
        rzad.append(zapisz, wroc);
        f.append(rzad, stan);
        f.addEventListener("submit", async (e) => {
            e.preventDefault();
            zapisz.disabled = true;
            try {
                const odp = await fetch(`${URL_PYTANIA}${p.id}/fiszka`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ cytat: nr, pytanie: pytanie.value, odpowiedz: odpowiedz.value, tematy: temat.value ? [temat.value] : [] }),
                });
                const dane = await odp.json().catch(() => ({}));
                if (!odp.ok) throw new Error(dane.blad || `Błąd ${odp.status}`);
                const gotowe = element("p", "komunikat komunikat--sukces");
                const link = element("a", "", "otwórz w Fiszkach ›");
                link.href = dane.url;
                gotowe.append(`Fiszka dodana (kotwica: strona ${dane.strona} PDF-a) — `, link);
                f.replaceWith(gotowe);
            } catch (err) {
                stan.textContent = err.message;
                stan.className = "komunikat komunikat--blad";
                zapisz.disabled = false;
            }
        });
        return f;
    }

    formularz.addEventListener("submit", async (e) => {
        e.preventDefault();
        const pytanie = pole.value.trim();
        if (!pytanie) return;
        przycisk.disabled = true;
        pokazStan("Szukam przepisów i pytam Gemini…", false);
        try {
            const odpowiedz = await fetch(URL_PYTANIE, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pytanie, akt: filtr.value ? Number(filtr.value) : null }),
            });
            const dane = await odpowiedz.json().catch(() => ({}));
            if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
            pokazStan("", false);
            odpowiedzi.prepend(karta(dane, null));
            pole.value = "";
        } catch (err) {
            pokazStan(err.message, true);
        } finally {
            przycisk.disabled = false;
        }
    });

    pole.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            formularz.requestSubmit();
        }
    });

    for (const p of HISTORIA) odpowiedzi.append(karta(p, p.data));
})();
