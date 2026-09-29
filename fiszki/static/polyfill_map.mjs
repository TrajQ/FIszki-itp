// Polyfill dla Map/WeakMap.prototype.getOrInsert i getOrInsertComputed
// (propozycja TC39 "upsert"). pdf.js 6.x z nich korzysta, a nie każda
// przeglądarka je ma — bez tego PDF się nie rysuje. Dodajemy metody tylko
// wtedy, gdy przeglądarka ich nie ma; jeśli ma, ten plik nic nie robi.
// Importowany jako pierwszy w fiszki.js i w pdf_worker.mjs (worker to
// osobny kontekst JS, więc potrzebuje własnej kopii).

for (const Klasa of [Map, WeakMap]) {
    if (!Klasa.prototype.getOrInsert) {
        Object.defineProperty(Klasa.prototype, "getOrInsert", {
            value(klucz, wartosc) {
                if (!this.has(klucz)) this.set(klucz, wartosc);
                return this.get(klucz);
            },
            writable: true,
            configurable: true,
        });
    }
    if (!Klasa.prototype.getOrInsertComputed) {
        Object.defineProperty(Klasa.prototype, "getOrInsertComputed", {
            value(klucz, oblicz) {
                if (!this.has(klucz)) this.set(klucz, oblicz(klucz));
                return this.get(klucz);
            },
            writable: true,
            configurable: true,
        });
    }
}
