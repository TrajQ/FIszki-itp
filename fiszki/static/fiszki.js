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
const bladPdfEl = document.getElementById("blad-pdf");
const licznikFiszekEl = document.getElementById("licznik-fiszek");

let dokumentPdf = null;
let numerStrony = 1;
let zaznaczonyFragment = null; // { tekst, strona }

async function wczytajDokument() {
    try {
        // pdf.js 6.x przyjmuje wyłącznie obiekt parametrów (sam string z URL już nie działa).
        dokumentPdf = await pdfjsLib.getDocument({ url: URL_PLIK }).promise;
        await renderujStrone(1);
    } catch (e) {
        // Bez tego błąd widać tylko w konsoli, a strona jest po prostu pusta.
        bladPdfEl.textContent = `Nie udało się wyświetlić PDF-a: ${e.message}`;
        bladPdfEl.hidden = false;
        console.error(e);
    }
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

    licznikFiszekEl.textContent = fiszki.length;
    listaFiszekEl.replaceChildren();
    if (fiszki.length === 0) {
        const pusto = document.createElement("li");
        pusto.className = "wyciszony";
        pusto.textContent = "Jeszcze nie ma fiszek. Zaznacz fragment tekstu w PDF-ie.";
        listaFiszekEl.appendChild(pusto);
        return;
    }

    for (const fiszka of fiszki) {
        const li = document.createElement("li");

        const pytanie = document.createElement("div");
        pytanie.className = "fiszka-pytanie";
        pytanie.textContent = fiszka.pytanie;
        const odpowiedzEl = document.createElement("div");
        odpowiedzEl.className = "fiszka-odpowiedz";
        odpowiedzEl.textContent = fiszka.odpowiedz;
        li.append(pytanie, odpowiedzEl);

        const akcje = document.createElement("div");
        akcje.className = "fiszka-akcje";

        akcje.appendChild(przycisk("Pokaż w źródle", "przycisk--tekst", () => pokazWZrodle(fiszka)));
        akcje.appendChild(przycisk("Edytuj", "przycisk--tekst", () => pokazEdycje(li, fiszka)));
        akcje.appendChild(
            przycisk("Usuń", "przycisk--niebezpieczny", async () => {
                await fetch(`${URL_FISZKI}/${fiszka.id}`, { method: "DELETE" });
                await odswiezListeFiszek();
            })
        );

        const strona = document.createElement("span");
        strona.className = "etykieta fiszka-strona";
        strona.textContent = `s. ${fiszka.strona}`;
        akcje.appendChild(strona);

        li.appendChild(akcje);
        listaFiszekEl.appendChild(li);
    }
}

function przycisk(tekst, klasa, poKliknieciu) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = klasa;
    el.textContent = tekst;
    el.addEventListener("click", poKliknieciu);
    return el;
}

// Edycja w miejscu: treść fiszki w <li> zastępujemy dwoma polami tekstowymi.
// Strona i fragment (kotwica w źródle) nie są edytowalne.
function pokazEdycje(li, fiszka) {
    li.replaceChildren();

    const polePytanieEdycja = document.createElement("textarea");
    polePytanieEdycja.value = fiszka.pytanie;
    const poleOdpowiedzEdycja = document.createElement("textarea");
    poleOdpowiedzEdycja.value = fiszka.odpowiedz;
    const statusEdycji = document.createElement("p");

    const przyciskZapiszZmiany = przycisk("Zapisz zmiany", "", async () => {
        const pytanie = polePytanieEdycja.value.trim();
        const odpowiedz = poleOdpowiedzEdycja.value.trim();
        if (!pytanie || !odpowiedz) {
            statusEdycji.textContent = "Pytanie i odpowiedź nie mogą być puste.";
            return;
        }
        const wynik = await fetch(`${URL_FISZKI}/${fiszka.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pytanie, odpowiedz }),
        });
        if (!wynik.ok) {
            statusEdycji.textContent = "Nie udało się zapisać zmian.";
            return;
        }
        await odswiezListeFiszek();
    });
    const przyciskAnulujEdycje = przycisk("Anuluj", "przycisk--drugi", odswiezListeFiszek);

    const etykietaPytania = document.createElement("label");
    etykietaPytania.append("Pytanie", polePytanieEdycja);
    const etykietaOdpowiedzi = document.createElement("label");
    etykietaOdpowiedzi.append("Odpowiedź", poleOdpowiedzEdycja);
    const przyciski = document.createElement("div");
    przyciski.className = "rzad";
    przyciski.append(przyciskZapiszZmiany, przyciskAnulujEdycje);

    statusEdycji.className = "wyciszony";
    li.append(etykietaPytania, etykietaOdpowiedzi, statusEdycji, przyciski);
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
