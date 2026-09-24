// Moduł ES (nie IIFE) — wymagane przez pdf.js, który jest wektorowany
// wyłącznie jako .mjs. Tag <script type="module"> daje ten sam efekt
// izolacji zasięgu co IIFE, więc nie łamie to duchu konwencji z CLAUDE.md.
import * as pdfjsLib from "./pdfjs/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = URL_WORKER;

const SKALA = 1.5;

const canvas = document.getElementById("canvas-pdf");
const kontekstCanvas = canvas.getContext("2d");
const warstwaTekstu = document.getElementById("warstwa-tekstu");
const numerStronyEl = document.getElementById("numer-strony");
const przyciskPoprzednia = document.getElementById("strona-poprzednia");
const przyciskNastepna = document.getElementById("strona-nastepna");
const przyciskZaproponuj = document.getElementById("przycisk-zaproponuj");
const formularzFiszki = document.getElementById("formularz-fiszki");
const podgladFragmentu = document.getElementById("podglad-fragmentu");
const statusGemini = document.getElementById("status-gemini");
const polePytanie = document.getElementById("pole-pytanie");
const poleOdpowiedz = document.getElementById("pole-odpowiedz");
const przyciskZapisz = document.getElementById("zapisz-fiszke");
const przyciskAnuluj = document.getElementById("anuluj-fiszke");
const listaFiszekEl = document.getElementById("lista-fiszek");

let dokumentPdf = null;
let numerStrony = 1;
let zaznaczonyFragment = null; // { tekst, strona }

async function wczytajDokument() {
    dokumentPdf = await pdfjsLib.getDocument(URL_PLIK).promise;
    await renderujStrone(1);
}

async function renderujStrone(nr) {
    numerStrony = Math.min(Math.max(nr, 1), dokumentPdf.numPages);
    numerStronyEl.textContent = `Strona ${numerStrony} / ${dokumentPdf.numPages}`;

    const strona = await dokumentPdf.getPage(numerStrony);
    const viewport = strona.getViewport({ scale: SKALA });

    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await strona.render({ canvasContext: kontekstCanvas, viewport }).promise;

    warstwaTekstu.style.width = `${viewport.width}px`;
    warstwaTekstu.style.height = `${viewport.height}px`;
    warstwaTekstu.style.setProperty("--total-scale-factor", SKALA);
    warstwaTekstu.replaceChildren();

    const warstwa = new pdfjsLib.TextLayer({
        textContentSource: strona.streamTextContent(),
        container: warstwaTekstu,
        viewport,
    });
    await warstwa.render();

    ukryjPrzyciskZaproponuj();
}

function tekstZaznaczenia() {
    const zaznaczenie = window.getSelection();
    if (!zaznaczenie || zaznaczenie.rangeCount === 0) return null;
    const tekst = zaznaczenie.toString().trim();
    if (!tekst) return null;
    if (!warstwaTekstu.contains(zaznaczenie.anchorNode)) return null;
    return { tekst, zakres: zaznaczenie.getRangeAt(0) };
}

function ukryjPrzyciskZaproponuj() {
    przyciskZaproponuj.hidden = true;
    zaznaczonyFragment = null;
}

warstwaTekstu.addEventListener("mouseup", () => {
    const wynik = tekstZaznaczenia();
    if (!wynik) {
        ukryjPrzyciskZaproponuj();
        return;
    }
    zaznaczonyFragment = { tekst: wynik.tekst, strona: numerStrony };

    const prostokat = wynik.zakres.getBoundingClientRect();
    const kontener = document.getElementById("warstwa-pdf").getBoundingClientRect();
    przyciskZaproponuj.style.left = `${prostokat.left - kontener.left}px`;
    przyciskZaproponuj.style.top = `${prostokat.bottom - kontener.top + 4}px`;
    przyciskZaproponuj.hidden = false;
});

przyciskPoprzednia.addEventListener("click", () => renderujStrone(numerStrony - 1));
przyciskNastepna.addEventListener("click", () => renderujStrone(numerStrony + 1));

przyciskZaproponuj.addEventListener("click", async () => {
    if (!zaznaczonyFragment) return;
    const fragment = zaznaczonyFragment;

    formularzFiszki.hidden = false;
    podgladFragmentu.textContent = fragment.tekst;
    polePytanie.value = "";
    poleOdpowiedz.value = "";
    statusGemini.textContent = "Generowanie szkicu przez Gemini…";
    przyciskZaproponuj.hidden = true;

    try {
        const odpowiedz = await fetch(URL_SZKIC, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fragment: fragment.tekst, strona: fragment.strona }),
        });
        const dane = await odpowiedz.json();
        if (!odpowiedz.ok || dane.blad) {
            statusGemini.textContent = `Gemini nie odpowiedział: ${dane.blad || "nieznany błąd"}. Uzupełnij ręcznie.`;
        } else {
            polePytanie.value = dane.pytanie;
            poleOdpowiedz.value = dane.odpowiedz;
            statusGemini.textContent = "";
        }
    } catch (e) {
        statusGemini.textContent = "Błąd połączenia z serwerem. Uzupełnij ręcznie.";
    }
});

przyciskAnuluj.addEventListener("click", () => {
    formularzFiszki.hidden = true;
    ukryjPrzyciskZaproponuj();
});

przyciskZapisz.addEventListener("click", async () => {
    if (!zaznaczonyFragment) return;
    const pytanie = polePytanie.value.trim();
    const odpowiedz = poleOdpowiedz.value.trim();
    if (!pytanie || !odpowiedz) {
        statusGemini.textContent = "Pytanie i odpowiedź nie mogą być puste.";
        return;
    }

    await fetch(URL_FISZKI, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            strona: zaznaczonyFragment.strona,
            fragment_tekstu: zaznaczonyFragment.tekst,
            pytanie,
            odpowiedz,
        }),
    });

    formularzFiszki.hidden = true;
    ukryjPrzyciskZaproponuj();
    await odswiezListeFiszek();
});

async function odswiezListeFiszek() {
    const odpowiedz = await fetch(URL_FISZKI);
    const fiszki = await odpowiedz.json();

    listaFiszekEl.replaceChildren();
    for (const fiszka of fiszki) {
        const li = document.createElement("li");

        const tresc = document.createElement("div");
        tresc.innerHTML = `<strong>${escapeHtml(fiszka.pytanie)}</strong><br>${escapeHtml(fiszka.odpowiedz)}`;
        li.appendChild(tresc);

        const przyciskPokaz = document.createElement("button");
        przyciskPokaz.type = "button";
        przyciskPokaz.textContent = "pokaż w źródle";
        przyciskPokaz.addEventListener("click", () => pokazWZrodle(fiszka));
        li.appendChild(przyciskPokaz);

        const przyciskUsun = document.createElement("button");
        przyciskUsun.type = "button";
        przyciskUsun.textContent = "usuń";
        przyciskUsun.addEventListener("click", async () => {
            await fetch(`${URL_FISZKI}/${fiszka.id}`, { method: "DELETE" });
            await odswiezListeFiszek();
        });
        li.appendChild(przyciskUsun);

        listaFiszekEl.appendChild(li);
    }
}

function escapeHtml(tekst) {
    const div = document.createElement("div");
    div.textContent = tekst;
    return div.innerHTML;
}

async function pokazWZrodle(fiszka) {
    await renderujStrone(fiszka.strona);
    podswietlFragment(fiszka.fragment_tekstu);
}

function podswietlFragment(fragment) {
    const spany = Array.from(warstwaTekstu.querySelectorAll("span"));
    let polaczonyTekst = "";
    const zakresySpanow = spany.map((span) => {
        const start = polaczonyTekst.length;
        polaczonyTekst += span.textContent;
        return { span, start, end: polaczonyTekst.length };
    });

    const indeks = polaczonyTekst.indexOf(fragment);
    if (indeks === -1) return;

    const koniec = indeks + fragment.length;
    let pierwszy = true;
    for (const { span, start, end } of zakresySpanow) {
        if (end <= indeks || start >= koniec) continue;
        span.classList.add("fiszka-podswietlenie");
        if (pierwszy) {
            span.scrollIntoView({ block: "center" });
            pierwszy = false;
        }
    }
}

wczytajDokument();
odswiezListeFiszek();
