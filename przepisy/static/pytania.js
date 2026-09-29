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
            for (const c of w.cytaty) {
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
