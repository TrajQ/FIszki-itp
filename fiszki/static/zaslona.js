// Zasłonięty fragment obrazu w fiszce (ETAP 185) — nakładka na <img>.
// Zasłona przychodzi z serwera jako [x, y, w, h] we współrzędnych względnych
// obrazu (0–1), więc pasuje przy każdej szerokości ekranu. Zakryta — pełny
// prostokąt; odsłonięta — tylko obrys, żeby było widać, o które miejsce chodziło.
const ZaslonaObrazu = (function () {
    "use strict";

    function opakowanie(img) {
        if (img.parentElement.classList.contains("obraz-z-zaslona")) return img.parentElement;
        const owijka = document.createElement("span");
        owijka.className = "obraz-z-zaslona";
        img.replaceWith(owijka);
        owijka.appendChild(img);
        const nakladka = document.createElement("span");
        nakladka.className = "zaslona";
        nakladka.hidden = true;
        owijka.appendChild(nakladka);
        return owijka;
    }

    /** ustaw(img, zaslona [x, y, w, h] albo null, zakryta: bool) */
    function ustaw(img, zaslona, zakryta) {
        const owijka = opakowanie(img);
        owijka.hidden = img.hidden;
        const nakladka = owijka.querySelector(".zaslona");
        nakladka.hidden = img.hidden || !zaslona;
        if (!zaslona) return;
        const [x, y, w, h] = zaslona;
        Object.assign(nakladka.style, { left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` });
        nakladka.classList.toggle("zaslona--odslonieta", !zakryta);
        nakladka.title = zakryta ? "Zasłonięty fragment — co tu jest?" : "To miejsce było zasłonięte";
    }

    return { ustaw };
})();
