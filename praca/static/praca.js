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

    async function policz() {
        pokazBlad("");
        const cialo = {
            tekst: $("tekst-grafiku").value,
            imie: $("imie").value.trim(),
            stawka: $("stawka").value.trim(),
            miesiac: $("miesiac").value,
            rok: $("rok").value,
        };
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
            const uwagi = [`Zmian w grafiku: ${w.wszystkich_zmian}, Twoich w tym miesiącu: ${w.zmiany.length}.`];
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
