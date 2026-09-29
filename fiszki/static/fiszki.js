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

// Temat nowych fiszek (ETAP 50) — zapamiętany osobno dla każdego pliku,
// żeby przy kolejnym otwarciu PDF-a nie trzeba było go wpisywać.
const poleTematowNowych = document.getElementById("pole-tematy-nowych");
const kluczTematow = `fiszki.tematyNowych.${location.pathname}`;
try {
    poleTematowNowych.value = localStorage.getItem(kluczTematow) || "";
} catch (e) {
    // bez localStorage pole jest po prostu puste
}
poleTematowNowych.addEventListener("change", () => {
    try {
        localStorage.setItem(kluczTematow, poleTematowNowych.value.trim());
    } catch (e) {
        // zapamiętanie to tylko wygoda
    }
});
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
            statusGemini.textContent = `Gemini nie odpowiedział: ${(dane.blad || "nieznany błąd").replace(/\.+$/, "")}. Uzupełnij ręcznie.`;
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

    let wynik;
    try {
        wynik = await fetch(URL_FISZKI, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                strona: zaznaczonyFragment.strona,
                fragment_tekstu: zaznaczonyFragment.tekst,
                pytanie,
                odpowiedz,
                tematy: poleTematowNowych.value,
            }),
        });
    } catch (e) {
        statusGemini.textContent = "Błąd połączenia z serwerem — fiszka nie została zapisana.";
        return;
    }
    // Formularz znika dopiero po udanym zapisie — inaczej treść przepadłaby po cichu.
    if (!wynik.ok) {
        statusGemini.textContent =
            wynik.status === 400 ? "Nie zapisano: sprawdź tematy (najwyżej 10, każdy do 30 znaków)." : `Nie zapisano (błąd ${wynik.status}).`;
        return;
    }

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
        return fiszki;
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
        if (fiszka.tematy && fiszka.tematy.length) {
            const tematyEl = document.createElement("div");
            tematyEl.className = "fiszka-tematy";
            for (const temat of fiszka.tematy) {
                const znacznik = document.createElement("span");
                znacznik.className = "etykieta etykieta--temat";
                znacznik.textContent = temat;
                tematyEl.appendChild(znacznik);
            }
            li.appendChild(tematyEl);
        }

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
    return fiszki;
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
    // Tematy (ETAP 50): po przecinku, np. „kolokwium 1, planowanie”.
    const poleTematowEdycja = document.createElement("input");
    poleTematowEdycja.type = "text";
    poleTematowEdycja.value = (fiszka.tematy || []).join(", ");
    poleTematowEdycja.placeholder = "np. kolokwium 1, planowanie";
    poleTematowEdycja.setAttribute("list", "lista-tematow-podpowiedzi");
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
            body: JSON.stringify({ pytanie, odpowiedz, tematy: poleTematowEdycja.value }),
        });
        if (!wynik.ok) {
            statusEdycji.textContent = wynik.status === 400 ? "Sprawdź tematy: najwyżej 10, każdy do 30 znaków." : "Nie udało się zapisać zmian.";
            return;
        }
        await odswiezListeFiszek();
    });
    const przyciskAnulujEdycje = przycisk("Anuluj", "przycisk--drugi", odswiezListeFiszek);

    const etykietaPytania = document.createElement("label");
    etykietaPytania.append("Pytanie", polePytanieEdycja);
    const etykietaOdpowiedzi = document.createElement("label");
    etykietaOdpowiedzi.append("Odpowiedź", poleOdpowiedzEdycja);
    const etykietaTematow = document.createElement("label");
    etykietaTematow.append("Tematy (po przecinku)", poleTematowEdycja);
    const przyciski = document.createElement("div");
    przyciski.className = "rzad";
    przyciski.append(przyciskZapiszZmiany, przyciskAnulujEdycje);

    statusEdycji.className = "wyciszony";
    li.append(etykietaPytania, etykietaOdpowiedzi, etykietaTematow, statusEdycji, przyciski);
}

async function pokazWZrodle(fiszka) {
    await renderujStrone(fiszka.strona);
    podswietlFragment(fiszka.fragment_tekstu);
}

// Szukamy fragmentu w tekście strony z pominięciem białych znaków:
// zaznaczenie myszką przez kilka linii zawiera „\n”, a sklejone spany
// warstwy tekstu nie — bez tego fiszki z dłuższych fragmentów się nie
// podświetlały (ta sama zasada co fiszki/strona.py po stronie serwera).
function podswietlFragment(fragment) {
    const szukany = fragment.replace(/\s+/g, "");
    if (!szukany) return false;

    const spany = Array.from(warstwaTekstu.querySelectorAll("span"));
    let polaczonyTekst = "";
    const zakresySpanow = spany.map((span) => {
        const start = polaczonyTekst.length;
        polaczonyTekst += span.textContent.replace(/\s+/g, "");
        return { span, start, end: polaczonyTekst.length };
    });

    const indeks = polaczonyTekst.indexOf(szukany);
    if (indeks === -1) return false;

    const koniec = indeks + szukany.length;
    let pierwszy = true;
    for (const { span, start, end } of zakresySpanow) {
        if (end <= indeks || start >= koniec || start === end) continue;
        span.classList.add("fiszka-podswietlenie");
        if (pierwszy) {
            span.scrollIntoView({ block: "center" });
            pierwszy = false;
        }
    }
    return true;
}

// ---------- Fiszki z całej strony (Gemini proponuje, użytkownik wybiera) ----------

const przyciskFiszkiStrony = document.getElementById("przycisk-fiszki-strony");
const propozycjeEl = document.getElementById("propozycje-strony");
const listaPropozycji = document.getElementById("lista-propozycji");
const statusPropozycji = document.getElementById("status-propozycji");
const przyciskZapiszPropozycje = document.getElementById("zapisz-propozycje");
const przyciskOdrzucPropozycje = document.getElementById("odrzuc-propozycje");
let stronaPropozycji = null;

async function tekstBiezacejStrony() {
    const strona = await dokumentPdf.getPage(numerStrony);
    const tresc = await strona.getTextContent();
    return tresc.items.map((el) => el.str + (el.hasEOL ? "\n" : "")).join("");
}

przyciskFiszkiStrony.addEventListener("click", async () => {
    if (!dokumentPdf) return;
    stronaPropozycji = numerStrony;
    propozycjeEl.hidden = false;
    listaPropozycji.replaceChildren();
    przyciskZapiszPropozycje.hidden = true;
    statusPropozycji.className = "wyciszony";
    statusPropozycji.textContent = `Gemini czyta stronę ${stronaPropozycji}…`;
    przyciskFiszkiStrony.disabled = true;
    try {
        const odpowiedz = await fetch(URL_SZKICE_STRONY, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ strona: stronaPropozycji, tekst: await tekstBiezacejStrony() }),
        });
        const dane = await odpowiedz.json();
        if (!odpowiedz.ok) throw new Error(dane.blad || `Błąd ${odpowiedz.status}`);
        pokazPropozycje(dane);
    } catch (e) {
        statusPropozycji.className = "komunikat komunikat--blad";
        statusPropozycji.textContent = e.message;
    } finally {
        przyciskFiszkiStrony.disabled = false;
    }
});

function pokazPropozycje(dane) {
    listaPropozycji.replaceChildren();
    let opis = `Propozycje ze strony ${stronaPropozycji}: ${dane.propozycje.length}. Odznacz zbędne, popraw i zapisz.`;
    if (dane.odrzucone) {
        opis += ` Pominięto ${dane.odrzucone}, bo ich cytatu nie ma na stronie (brak kotwicy w źródle).`;
    }
    statusPropozycji.className = "wyciszony";
    statusPropozycji.textContent = opis;

    for (const p of dane.propozycje) {
        const li = document.createElement("li");
        li.className = "propozycja";
        const wybor = document.createElement("input");
        wybor.type = "checkbox";
        wybor.checked = true;
        wybor.className = "propozycja__wybor";
        const pytanie = document.createElement("textarea");
        pytanie.value = p.pytanie;
        pytanie.className = "propozycja__pytanie";
        const odpowiedz = document.createElement("textarea");
        odpowiedz.value = p.odpowiedz;
        const cytat = document.createElement("blockquote");
        cytat.textContent = p.fragment;
        cytat.title = "Pokaż na stronie";
        cytat.addEventListener("click", async () => {
            await renderujStrone(stronaPropozycji);
            podswietlFragment(p.fragment);
        });
        const tresc = document.createElement("div");
        tresc.className = "stos";
        tresc.append(pytanie, odpowiedz, cytat);
        li.append(wybor, tresc);
        li.dataset.fragment = p.fragment;
        listaPropozycji.appendChild(li);
    }
    przyciskZapiszPropozycje.hidden = dane.propozycje.length === 0;
}

przyciskZapiszPropozycje.addEventListener("click", async () => {
    const wybrane = Array.from(listaPropozycji.querySelectorAll(".propozycja")).filter(
        (li) => li.querySelector(".propozycja__wybor").checked
    );
    przyciskZapiszPropozycje.disabled = true;
    let zapisane = 0;
    let nieudane = 0;
    try {
        for (const li of wybrane) {
            const [pytanie, odpowiedz] = li.querySelectorAll("textarea");
            if (!pytanie.value.trim() || !odpowiedz.value.trim()) {
                nieudane += 1;
                li.classList.add("propozycja--blad");
                continue;
            }
            let ok = false;
            try {
                const wynik = await fetch(URL_FISZKI, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        strona: stronaPropozycji,
                        fragment_tekstu: li.dataset.fragment,
                        pytanie: pytanie.value.trim(),
                        odpowiedz: odpowiedz.value.trim(),
                        tematy: poleTematowNowych.value,
                    }),
                });
                ok = wynik.ok;
            } catch (e) {
                ok = false;
            }
            // Zapisane znikają z listy; nieudane zostają do poprawy i ponownej próby.
            if (ok) {
                zapisane += 1;
                li.remove();
            } else {
                nieudane += 1;
                li.classList.add("propozycja--blad");
            }
        }
    } finally {
        przyciskZapiszPropozycje.disabled = false;
    }
    const zostalo = listaPropozycji.querySelectorAll(".propozycja").length;
    przyciskZapiszPropozycje.hidden = zostalo === 0;
    if (nieudane) {
        statusPropozycji.className = "komunikat komunikat--blad";
        statusPropozycji.textContent = `Zapisano ${zapisane}, nie udało się zapisać ${nieudane} (zaznaczone na czerwono) — popraw i spróbuj ponownie.`;
    } else {
        statusPropozycji.className = "komunikat komunikat--sukces";
        statusPropozycji.textContent = `Zapisano fiszki: ${zapisane} (strona ${stronaPropozycji}).`;
    }
    await odswiezListeFiszek();
});

przyciskOdrzucPropozycje.addEventListener("click", () => {
    propozycjeEl.hidden = true;
});

// Link z sesji powtórki: /fiszki/<pdf>/?fiszka=<id> od razu pokazuje fiszkę w źródle.
async function start() {
    await wczytajDokument();
    const fiszki = await odswiezListeFiszek();
    const idZAdresu = Number(new URLSearchParams(window.location.search).get("fiszka"));
    const fiszka = fiszki.find((f) => f.id === idZAdresu);
    if (dokumentPdf && fiszka) await pokazWZrodle(fiszka);
}

start();
